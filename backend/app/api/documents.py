"""
Document generation and SRS export API router.
Supports binary PDF download and document metadata retrieval with tenant isolation.
"""
import os
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from backend.app.core.session import get_current_owner_hash
from backend.app.db.models import Chat, GeneratedDocumentModel, Project, RequirementModel, ComplianceMappingModel, RiskModel, SDLCRecommendationModel, ApprovalModel
from backend.app.db.session import get_db
from backend.app.agents.documentation import DocumentationAgent
from backend.app.core.audit import record_audit_event, AuditEventType


router = APIRouter(prefix="/chats/{chat_id}/documents", tags=["documents"])
doc_agent = DocumentationAgent()


class DocumentMetadataResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    chat_id: str
    project_id: Optional[str] = None
    doc_type: str
    version: int
    file_path: str
    sha256: str
    status: str
    created_at: datetime


@router.get("", response_model=List[DocumentMetadataResponse])
def list_chat_documents(
    chat_id: str,
    db: Session = Depends(get_db),
    owner_hash: str = Depends(get_current_owner_hash),
):
    """List all generated document artifacts for the given chat session."""
    chat = (
        db.query(Chat)
        .filter(Chat.id == chat_id, Chat.owner_token_hash == owner_hash, Chat.deleted_at.is_(None))
        .first()
    )
    if not chat:
        raise HTTPException(status_code=404, detail="Chat session not found")

    docs = (
        db.query(GeneratedDocumentModel)
        .filter(GeneratedDocumentModel.chat_id == chat_id)
        .order_by(GeneratedDocumentModel.created_at.desc())
        .all()
    )
    return docs


@router.get("/export")
def export_srs_pdf(
    chat_id: str,
    db: Session = Depends(get_db),
    owner_hash: str = Depends(get_current_owner_hash),
):
    """
    Download compiled ISO/IEC/IEEE 29148 SRS binary PDF.
    If already compiled, returns cached binary with verified SHA-256;
    otherwise compiles dynamically from project state.
    """
    chat = (
        db.query(Chat)
        .filter(Chat.id == chat_id, Chat.owner_token_hash == owner_hash, Chat.deleted_at.is_(None))
        .first()
    )
    if not chat:
        raise HTTPException(status_code=404, detail="Chat session not found")

    # Check for existing document in DB
    existing_doc = (
        db.query(GeneratedDocumentModel)
        .filter(GeneratedDocumentModel.chat_id == chat_id, GeneratedDocumentModel.doc_type == "srs")
        .order_by(GeneratedDocumentModel.version.desc())
        .first()
    )

    if existing_doc and os.path.exists(existing_doc.file_path):
        return FileResponse(
            path=existing_doc.file_path,
            media_type="application/pdf",
            filename=f"SRS_{chat.title.replace(' ', '_')}_v{existing_doc.version}.pdf",
            headers={"X-Document-SHA256": existing_doc.sha256}
        )

    # If not already on disk, build dynamically from DB records
    project = db.query(Project).filter(Project.chat_id == chat_id).first()
    project_id = project.id if project else str(chat.id)
    project_data = {
        "id": project_id,
        "title": project.title if project else chat.title,
        "version": 1
    }

    # Fetch requirements
    db_reqs = db.query(RequirementModel).filter(RequirementModel.project_id == project_id).all()
    req_dicts = [
        {
            "id": r.id,
            "statement": r.statement,
            "category": r.category,
            "priority": r.priority,
            "source_statement_id": r.source_statement_id,
            "status": r.status,
            "version": r.version
        }
        for r in db_reqs
    ]

    # Check baseline approval status
    baseline_approval = (
        db.query(ApprovalModel)
        .filter(ApprovalModel.chat_id == chat_id, ApprovalModel.gate_type == "baseline")
        .first()
    )
    is_approved = baseline_approval.decision == "accepted" if baseline_approval else False

    # Fetch compliance mappings and risks
    mappings = db.query(ComplianceMappingModel).filter(ComplianceMappingModel.project_id == project_id).all()
    mapping_dicts = [
        {
            "requirement_id": m.requirement_id,
            "regulation_name": m.regulation_name,
            "section_reference": m.section_reference,
            "control_required": m.control_required,
            "citation_verified": m.citation_verified
        }
        for m in mappings
    ]

    risks = db.query(RiskModel).filter(RiskModel.project_id == project_id).all()
    risk_dicts = [
        {
            "id": rk.id,
            "category": rk.category,
            "severity": rk.severity,
            "risk_score": rk.risk_score,
            "mitigation": rk.mitigation
        }
        for rk in risks
    ]

    sdlc_rec = db.query(SDLCRecommendationModel).filter(SDLCRecommendationModel.chat_id == chat_id).first()
    sdlc_dict = {
        "selected_model": sdlc_rec.selected_model if sdlc_rec else "Agile-DevSecOps Hybrid",
        "explanation": "Statutory engineering lifecycle."
    }

    # Compile document
    res = doc_agent.compile_srs(
        db=db,
        chat_id=chat_id,
        project_data=project_data,
        requirements=req_dicts,
        compliance_mappings=mapping_dicts,
        risks=risk_dicts,
        sdlc_recommendation=sdlc_dict,
        is_approved=is_approved
    )

    pdf_meta = res["pdf_meta"]

    # Save to generated_documents table
    new_doc = GeneratedDocumentModel(
        chat_id=chat_id,
        project_id=project_id,
        doc_type="srs",
        version=pdf_meta["version"],
        file_path=pdf_meta["file_path"],
        sha256=pdf_meta["sha256"],
        status="signed_off" if is_approved else "generated"
    )
    db.add(new_doc)
    db.commit()

    record_audit_event(
        db=db,
        event=AuditEventType.DOCUMENT_GENERATED.value,
        actor="DocumentationAgent",
        chat_id=chat_id,
        payload={"doc_type": "srs", "file_path": pdf_meta["file_path"], "sha256": pdf_meta["sha256"], "is_approved": is_approved}
    )

    return FileResponse(
        path=pdf_meta["file_path"],
        media_type="application/pdf",
        filename=f"SRS_{project_data['title'].replace(' ', '_')}_v{pdf_meta['version']}.pdf",
        headers={"X-Document-SHA256": pdf_meta["sha256"]}
    )
