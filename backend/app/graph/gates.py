"""
Human-in-the-Loop Approval Gate Manager per Problem Statement §16 and Master Plan Phase 12.
Manages the 8 mandatory gates, processes 5 reviewer actions (Accept, Reject, Edit, Regenerate, Explain),
enforces baseline immutability with version snapshots & impact analysis, and handles multi-role SDLC sign-offs.
"""
import json
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
from sqlalchemy.orm import Session

from backend.app.db.models import (
    ApprovalModel,
    RequirementModel,
    RequirementVersion,
    SDLCRecommendationModel,
    Project,
)
from backend.app.schemas.approval import GateType, ApprovalAction, ActingRole, ApprovalStatus


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


SDLC_MANDATORY_ROLES = [
    ActingRole.PROJECT_MANAGER.value,
    ActingRole.SOFTWARE_ARCHITECT.value,
    ActingRole.SECURITY_ARCHITECT.value,
    ActingRole.COMPLIANCE_OFFICER.value,
]


class ApprovalGateManager:
    def create_approval_request(
        self,
        db: Session,
        chat_id: str,
        project_id: str,
        gate_type: str,
        subject_id: str,
        title: str,
        description: str,
        required_role: str,
        evidence_data: Optional[Dict[str, Any]] = None,
        confidence_score: float = 1.0
    ) -> ApprovalModel:
        """Creates and stores a new pending approval request gate in the database."""
        approval = ApprovalModel(
            id=str(uuid.uuid4()),
            chat_id=chat_id,
            project_id=project_id,
            gate_type=gate_type,
            subject_id=subject_id,
            title=title,
            description=description,
            required_role=required_role,
            status=ApprovalStatus.PENDING.value,
            evidence_data_json=json.dumps(evidence_data or {}),
            confidence_score=confidence_score,
            sdlc_signoffs_json=json.dumps({}) if gate_type == GateType.SDLC_SELECTION.value else None,
            created_at=utcnow()
        )
        db.add(approval)
        db.commit()
        db.refresh(approval)
        return approval

    def process_decision(
        self,
        db: Session,
        approval_id: str,
        action: str,
        acting_role: str,
        comment: Optional[str] = None,
        modified_payload: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Executes one of the 5 reviewer actions on an approval gate:
        - accept: approves gate (or logs role signature for SDLC)
        - reject: marks rejected and routes back to analysis
        - edit: enforces immutability, creates v+1 snapshot, produces impact report
        - regenerate: flags for AI regeneration
        - explain: returns evidence quotes, citations, and confidence without altering status
        """
        approval = db.query(ApprovalModel).filter(ApprovalModel.id == approval_id).first()
        if not approval:
            raise ValueError(f"Approval gate '{approval_id}' not found.")

        # Action: EXPLAIN
        if action == ApprovalAction.EXPLAIN.value:
            return self.get_explainability_dossier(approval)

        approval.action_taken = action
        approval.acting_role = acting_role
        approval.reviewer_comment = comment
        approval.decided_at = utcnow()

        # Action: ACCEPT
        if action == ApprovalAction.ACCEPT.value:
            # Special handling for SDLC 4-role sign-off
            if approval.gate_type == GateType.SDLC_SELECTION.value:
                signoffs = json.loads(approval.sdlc_signoffs_json or "{}")
                signoffs[acting_role] = {
                    "signed_at": utcnow().isoformat(),
                    "comment": comment
                }
                approval.sdlc_signoffs_json = json.dumps(signoffs)

                # Check if all 4 mandatory roles have signed off
                signed_roles = set(signoffs.keys())
                mandatory_set = set(SDLC_MANDATORY_ROLES)
                remaining_roles = list(mandatory_set - signed_roles)

                if not remaining_roles:
                    approval.status = ApprovalStatus.APPROVED.value
                    # Mark SDLC recommendation as approved in database
                    rec = db.query(SDLCRecommendationModel).filter(
                        SDLCRecommendationModel.project_id == approval.project_id
                    ).first()
                    if rec:
                        rec.is_approved = True
                else:
                    approval.status = ApprovalStatus.PENDING.value

                db.commit()
                return {
                    "approval_id": approval.id,
                    "status": approval.status,
                    "action": action,
                    "signed_roles": list(signed_roles),
                    "remaining_roles": remaining_roles,
                    "fully_approved": approval.status == ApprovalStatus.APPROVED.value
                }

            # Standard gate acceptance
            approval.status = ApprovalStatus.APPROVED.value
            if approval.gate_type == GateType.BASELINE.value:
                # Lock all project requirements as approved
                reqs = db.query(RequirementModel).filter(
                    RequirementModel.project_id == approval.project_id
                ).all()
                for r in reqs:
                    r.status = "approved"

            db.commit()
            return {
                "approval_id": approval.id,
                "status": approval.status,
                "action": action,
                "message": f"Gate '{approval.gate_type}' accepted under role '{acting_role}'."
            }

        # Action: REJECT
        elif action == ApprovalAction.REJECT.value:
            approval.status = ApprovalStatus.REJECTED.value
            # If subject is a requirement, update status
            req = db.query(RequirementModel).filter(
                RequirementModel.id == approval.subject_id
            ).first()
            if req:
                req.status = "revision_requested"

            db.commit()
            return {
                "approval_id": approval.id,
                "status": approval.status,
                "action": action,
                "message": f"Proposal rejected by {acting_role}: routed back for clarification.",
                "comment": comment
            }

        # Action: EDIT (Enforces Immutability & Version Snapshots)
        elif action == ApprovalAction.EDIT.value:
            approval.status = ApprovalStatus.REVISED.value
            approval.modified_payload = modified_payload

            impact_report = {}
            req = db.query(RequirementModel).filter(
                RequirementModel.id == approval.subject_id
            ).first()

            if req and modified_payload:
                current_ver = req.version
                new_ver = current_ver + 1

                # Snapshot the prior version into requirement_versions to guarantee immutability
                snap = RequirementVersion(
                    id=str(uuid.uuid4()),
                    requirement_id=req.id,
                    version=current_ver,
                    statement=req.statement,
                    category=req.category,
                    priority=req.priority,
                    status=req.status,
                    changed_by=f"Human Reviewer ({acting_role})",
                    change_reason=comment or f"Human edit via approval gate {approval.id}"
                )
                db.add(snap)

                # Update requirement to new version
                req.statement = modified_payload
                req.version = new_ver
                req.status = "draft"  # requires re-verification

                # Generate impact report
                impact_report = {
                    "requirement_id": req.id,
                    "previous_version": current_ver,
                    "new_version": new_ver,
                    "affected_compliance_mappings": len(req.compliance_mappings) if hasattr(req, "compliance_mappings") else 0,
                    "affected_issues": len(req.issues) if hasattr(req, "issues") else 0,
                    "reanalysis_required": True,
                    "note": f"Version {current_ver} archived immutably in requirement_versions. Version {new_ver} created."
                }

            db.commit()
            return {
                "approval_id": approval.id,
                "status": approval.status,
                "action": action,
                "modified_payload": modified_payload,
                "impact_analysis": impact_report
            }

        # Action: REGENERATE
        elif action == ApprovalAction.REGENERATE.value:
            approval.status = ApprovalStatus.PENDING.value
            db.commit()
            return {
                "approval_id": approval.id,
                "status": approval.status,
                "action": action,
                "message": "Flagged for AI re-synthesis and formulation."
            }

        else:
            raise ValueError(f"Unknown approval action '{action}'.")

    def get_explainability_dossier(self, approval: ApprovalModel) -> Dict[str, Any]:
        """Returns fact-grounded explainability evidence, statutory citations, and confidence score."""
        evidence = json.loads(approval.evidence_data_json or "{}")
        return {
            "approval_id": approval.id,
            "gate_type": approval.gate_type,
            "title": approval.title,
            "confidence_score": approval.confidence_score,
            "rationale": evidence.get("rationale", approval.description),
            "evidence_quote": evidence.get("evidence_quote", "Derived from verified project stakeholder input."),
            "applicable_citations": evidence.get("citations", []),
            "suggested_action": "Review evidence quote against regulatory baselines before signing."
        }


# Singleton gate manager
approval_gate_manager = ApprovalGateManager()
