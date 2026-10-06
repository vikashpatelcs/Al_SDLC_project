"""
Approval Gates & Change Control REST API per Problem Statement §16 and Master Plan Phase 12.
Supports listing pending gates, submitting reviewer actions (Accept, Reject, Edit, Regenerate, Explain),
and 4-role SDLC sign-offs.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.db.models import ApprovalModel
from backend.app.schemas.approval import ApprovalDecision, ApprovalAction
from backend.app.graph.gates import approval_gate_manager

router = APIRouter(prefix="/approvals", tags=["approvals"])


@router.get("")
def list_approvals(
    chat_id: Optional[str] = Query(None, description="Filter by chat ID"),
    project_id: Optional[str] = Query(None, description="Filter by project ID"),
    status: Optional[str] = Query(None, description="Filter by status (pending, approved, rejected, revised)"),
    db: Session = Depends(get_db)
):
    """List approval requests matching criteria."""
    query = db.query(ApprovalModel)
    if chat_id:
        query = query.filter(ApprovalModel.chat_id == chat_id)
    if project_id:
        query = query.filter(ApprovalModel.project_id == project_id)
    if status:
        query = query.filter(ApprovalModel.status == status)

    approvals = query.order_by(ApprovalModel.created_at.desc()).all()
    return [
        {
            "id": a.id,
            "chat_id": a.chat_id,
            "project_id": a.project_id,
            "gate_type": a.gate_type,
            "subject_id": a.subject_id,
            "title": a.title,
            "description": a.description,
            "required_role": a.required_role,
            "status": a.status,
            "action_taken": a.action_taken,
            "acting_role": a.acting_role,
            "confidence_score": a.confidence_score,
            "created_at": a.created_at.isoformat() if a.created_at else None,
            "decided_at": a.decided_at.isoformat() if a.decided_at else None
        }
        for a in approvals
    ]


@router.get("/{approval_id}")
def get_approval(
    approval_id: str,
    db: Session = Depends(get_db)
):
    """Retrieve full details of a specific approval gate."""
    approval = db.query(ApprovalModel).filter(ApprovalModel.id == approval_id).first()
    if not approval:
        raise HTTPException(status_code=404, detail=f"Approval '{approval_id}' not found.")

    return {
        "id": approval.id,
        "chat_id": approval.chat_id,
        "project_id": approval.project_id,
        "gate_type": approval.gate_type,
        "subject_id": approval.subject_id,
        "title": approval.title,
        "description": approval.description,
        "required_role": approval.required_role,
        "status": approval.status,
        "action_taken": approval.action_taken,
        "acting_role": approval.acting_role,
        "reviewer_comment": approval.reviewer_comment,
        "modified_payload": approval.modified_payload,
        "sdlc_signoffs_json": approval.sdlc_signoffs_json,
        "confidence_score": approval.confidence_score,
        "created_at": approval.created_at.isoformat() if approval.created_at else None,
        "decided_at": approval.decided_at.isoformat() if approval.decided_at else None
    }


@router.post("/{approval_id}/decision")
def submit_decision(
    approval_id: str,
    decision: ApprovalDecision,
    db: Session = Depends(get_db)
):
    """Submit one of the 5 reviewer actions on an approval gate."""
    try:
        result = approval_gate_manager.process_decision(
            db=db,
            approval_id=approval_id,
            action=decision.action.value,
            acting_role=decision.acting_role.value,
            comment=decision.comment,
            modified_payload=decision.modified_payload
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{approval_id}/explain")
def get_explain(
    approval_id: str,
    db: Session = Depends(get_db)
):
    """Returns fact-grounded explainability evidence quotes, citations, and confidence score."""
    approval = db.query(ApprovalModel).filter(ApprovalModel.id == approval_id).first()
    if not approval:
        raise HTTPException(status_code=404, detail=f"Approval '{approval_id}' not found.")

    return approval_gate_manager.get_explainability_dossier(approval)
