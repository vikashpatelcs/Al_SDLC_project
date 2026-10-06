"""
Documentation & Validation Agent (PS §12, Master Plan Phase 14).
Synthesizes user stories, acceptance criteria, use cases, process workflows, data/interface requirements,
runs the pre-generation specification validator, builds the RTM, and compiles the IEEE 29148 SRS PDF.
"""
import os
import uuid
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from backend.app.docs_gen.validation import SpecificationValidator, ValidationResult
from backend.app.docs_gen.traceability import TraceabilityEngine
from backend.app.docs_gen.pdf import SRSPDFGenerator
from backend.app.schemas.message import ActionCard, ActionCardType


class DocumentationAgent:
    """Agent responsible for IEEE 29148 SRS compilation, artefact synthesis, and RTM generation."""

    def __init__(self):
        self.validator = SpecificationValidator()
        self.traceability_engine = TraceabilityEngine()
        self.pdf_generator = SRSPDFGenerator()

    def synthesize_user_stories(self, requirements: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        stories = []
        for req in requirements:
            req_id = req.get("id", "REQ")
            statement = req.get("statement", "")
            cat = req.get("category", "Functional")
            actor = "retail customer" if cat == "Functional" else "system security officer" if cat in ("Security", "Privacy") else "compliance auditor"

            # Use existing acceptance criteria if present
            raw_acs = req.get("acceptance_criteria", [])
            acs = []
            if raw_acs:
                for a in raw_acs:
                    if isinstance(a, dict):
                        acs.append(a)
                    else:
                        acs.append({"given": getattr(a, "given", ""), "when": getattr(a, "when", ""), "then": getattr(a, "then", "")})
            else:
                acs.append({
                    "id": f"AC-{req_id}-01",
                    "given": f"The system is operational and authenticated user is in {cat} context",
                    "when": f"The user or system triggers requirement [{req_id}]",
                    "then": f"The expected outcome is achieved in accordance with '{statement}'"
                })

            stories.append({
                "id": f"US-{req_id}",
                "requirement_id": req_id,
                "narrative": f"As a {actor}, I want to ensure '{statement}' so that financial statutory obligations and business requirements are fulfilled.",
                "criteria": acs
            })
        return stories

    def synthesize_use_cases(self, requirements: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        use_cases = []
        if not requirements:
            return use_cases

        # Group by category or provide representative use cases
        categories = {r.get("category", "Functional") for r in requirements}
        for idx, cat in enumerate(sorted(categories), 1):
            cat_reqs = [r for r in requirements if r.get("category") == cat]
            req_ids = [r.get("id") for r in cat_reqs]
            use_cases.append({
                "id": f"UC-00{idx}",
                "name": f"Execute {cat} Orchestration Cycle",
                "actor": "End User / Automated Service",
                "requirements": req_ids,
                "pre": f"System active in project context; secure token present.",
                "flow": f"1. Trigger event received for {cat} domain. 2. Verify inputs against rules. 3. Execute {len(cat_reqs)} specifications ({', '.join(req_ids[:3])}). 4. Log audit record.",
                "post": f"State updated successfully; all acceptance criteria satisfied."
            })
        return use_cases

    def synthesize_process_workflows(self, requirements: List[Dict[str, Any]]) -> Dict[str, Any]:
        return {
            "diagram_type": "sequence",
            "mermaid_code": (
                "sequenceDiagram\n"
                "  autonumber\n"
                "  actor User as Customer\n"
                "  participant App as Client Portal\n"
                "  participant Core as FinReq Orchestrator\n"
                "  participant Ext as Statutory Authority (UIDAI/CERSAI)\n"
                "  User->>App: Submit Customer Data & Consent\n"
                "  App->>Core: Mask PII & Encrypt Token\n"
                "  Core->>Ext: Verify Identity Credentials\n"
                "  Ext-->>Core: Verification Status & Token\n"
                "  Core-->>App: Confirmed Onboarding State\n"
            ),
            "description": "End-to-end statutory verification and identity ingestion workflow sequence."
        }

    def synthesize_data_and_interface_reqs(self, requirements: List[Dict[str, Any]]) -> Dict[str, Any]:
        data_fields = [
            ("Customer Name & Identifiers", "Confidential PII", "AES-256 Fernet at rest, TLS 1.3 in transit", "10 years post-account closure (PMLA §12)"),
            ("Aadhaar Virtual ID / Token", "Restricted Statutory", "SHA-256 Vault Token; Raw numbers prohibited", "Immediate erasure post-auth (UIDAI Circular)"),
            ("Biometric / Video-CIP Media", "Biometric Record", "AES-256 encrypted storage with SHA-256 hash", "5 years post-account closure (RBI MD-KYC)"),
            ("Audit Trail & State Logs", "Statutory Log", "SHA-256 Linked Chain; Write-Once-Read-Many", "8 years (RBI IT Governance Direction)")
        ]
        interfaces = [
            ("UIDAI Aadhaar e-KYC", "REST / XML over mTLS", "Response time < 2000ms; 256-bit signature"),
            ("CERSAI CKYC Gateway", "SOAP / SFTP Batch", "Real-time query & daily reconciliation"),
            ("Core Banking Engine (CBS)", "ISO 8583 / REST JSON", "Immediate account opening & CIF generation")
        ]
        return {
            "data_reqs": data_fields,
            "interfaces": interfaces
        }

    def compile_srs(
        self,
        db: Optional[Session],
        chat_id: str,
        project_data: Dict[str, Any],
        requirements: List[Dict[str, Any]],
        compliance_mappings: Optional[List[Dict[str, Any]]] = None,
        risks: Optional[List[Dict[str, Any]]] = None,
        sdlc_recommendation: Optional[Dict[str, Any]] = None,
        issues: Optional[List[Dict[str, Any]]] = None,
        is_approved: bool = True,
        output_dir: str = "./storage/documents"
    ) -> Dict[str, Any]:
        """
        Compiles the full IEEE 29148 SRS specification:
        1. Filters approved requirements if is_approved is True.
        2. Validates completeness, consistency, and evidence.
        3. Builds and persists RTM.
        4. Synthesizes all 23-section artefacts.
        5. Renders ReportLab PDF and computes SHA-256.
        """
        compliance_mappings = compliance_mappings or []
        risks = risks or []
        sdlc_recommendation = sdlc_recommendation or {"selected_model": "Agile-DevSecOps Hybrid", "explanation": "Statutory compliance."}
        issues = issues or []

        # 1. Filter requirements: if baseline is approved, exclude unapproved/rejected items
        active_reqs = []
        if is_approved:
            for r in requirements:
                status = str(r.get("status", "")).lower()
                # Exclude if explicitly marked rejected or unapproved
                if status in ("rejected", "unapproved", "draft"):
                    continue
                active_reqs.append(r)
            # Fallback if all were untagged or standard approved
            if not active_reqs and requirements:
                active_reqs = [r for r in requirements if str(r.get("status", "")).lower() != "rejected"]
        else:
            active_reqs = list(requirements)

        # 2. Run Specification Validation
        val_result = self.validator.validate(active_reqs, compliance_mappings, issues)

        # 3. Build RTM
        rtm_rows = self.traceability_engine.build_matrix(active_reqs, compliance_mappings, risks)
        coverage_score = self.traceability_engine.calculate_coverage(rtm_rows, active_reqs)

        # Persist RTM if DB session provided
        if db and project_data.get("id"):
            self.traceability_engine.persist_traceability(db, project_data["id"], rtm_rows)

        # 4. Synthesize Artefacts
        user_stories = self.synthesize_user_stories(active_reqs)
        use_cases = self.synthesize_use_cases(active_reqs)
        workflows = self.synthesize_process_workflows(active_reqs)
        data_interfaces = self.synthesize_data_and_interface_reqs(active_reqs)

        artefacts = {
            "executive_summary": (
                f"Statutory Software Requirements Specification for {project_data.get('title', 'Digital Banking')}. "
                f"Comprises {len(active_reqs)} validated specifications with {int(coverage_score * 100)}% RTM traceability."
            ),
            "assumptions": [
                "UIDAI e-KYC service SLA guarantees 99.9% uptime with responses within 2000ms.",
                "SMS OTP delivery gateways provide OTP within 15 seconds.",
                "Customer devices possess HTML5 WebRTC-compatible cameras for Video-CIP."
            ],
            "interfaces": data_interfaces["interfaces"],
            "data_reqs": data_interfaces["data_reqs"],
            "user_stories": user_stories,
            "use_cases": use_cases,
            "workflows": workflows
        }

        # 5. Compile PDF
        out_folder = os.path.join(output_dir, str(chat_id))
        os.makedirs(out_folder, exist_ok=True)
        version = project_data.get("version", 1)
        pdf_path = os.path.join(out_folder, f"srs_v{version}.pdf")

        pdf_meta = self.pdf_generator.generate_pdf(
            output_path=pdf_path,
            project_data=project_data,
            requirements=active_reqs,
            compliance_mappings=compliance_mappings,
            risks=risks,
            sdlc_recommendation=sdlc_recommendation,
            rtm_rows=rtm_rows,
            artefacts=artefacts,
            is_approved=is_approved
        )

        # 6. Build Action Card for UI Download
        action_card = ActionCard(
            id=f"card-doc-{uuid.uuid4().hex[:8]}",
            card_type=ActionCardType.DOWNLOAD_PDF,
            title="IEEE 29148 SRS Document Package Ready",
            payload={
                "doc_type": "srs",
                "version": version,
                "is_approved": is_approved,
                "file_path": pdf_path,
                "download_url": f"/api/chats/{chat_id}/documents/export",
                "sha256": pdf_meta["sha256"],
                "total_requirements": len(active_reqs),
                "traceability_coverage": coverage_score,
                "validation": val_result.model_dump(mode="json")
            },
            actions=["Download PDF", "View RTM", "Sign-Off Document"]
        )

        return {
            "pdf_meta": pdf_meta,
            "validation": val_result,
            "rtm_rows": rtm_rows,
            "coverage_score": coverage_score,
            "active_requirements": active_reqs,
            "action_card": action_card
        }
