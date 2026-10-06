"""
SQLAlchemy database models for persistence.
Supports chats, messages, uploaded files, projects, stakeholders, requirements,
immutable requirement versions, and the assumptions register per Phase 6.
"""
import uuid
from datetime import datetime, timezone, timedelta
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text, Boolean, Float
from sqlalchemy.orm import relationship, Session

from backend.app.db.session import Base
from backend.app.core.crypto import EncryptedText


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Chat(Base):
    __tablename__ = "chats"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    owner_token_hash = Column(String(64), index=True, nullable=False)
    title = Column(String(255), nullable=False, default="New Financial Requirement")
    state = Column(String(64), nullable=False, default="INTAKE")
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)
    deleted_at = Column(DateTime, nullable=True)

    messages = relationship("Message", back_populates="chat", cascade="all, delete-orphan", order_by="Message.created_at")
    files = relationship("UploadedFile", back_populates="chat", cascade="all, delete-orphan")
    project = relationship("Project", back_populates="chat", uselist=False, cascade="all, delete-orphan")
    sdlc_recommendations = relationship("SDLCRecommendationModel", back_populates="chat", cascade="all, delete-orphan")
    approvals = relationship("ApprovalModel", back_populates="chat", cascade="all, delete-orphan")
    generated_documents = relationship("GeneratedDocumentModel", back_populates="chat", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLogModel", back_populates="chat", cascade="all, delete-orphan")
    agent_executions = relationship("AgentExecutionModel", back_populates="chat", cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = "messages"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    chat_id = Column(String(36), ForeignKey("chats.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(32), nullable=False)  # user, assistant, system
    sender_agent = Column(String(64), nullable=True)
    content_masked = Column(EncryptedText, nullable=False)
    action_cards_json = Column(Text, nullable=True)  # JSON-encoded array of ActionCard objects
    created_at = Column(DateTime, default=utcnow, nullable=False)

    chat = relationship("Chat", back_populates="messages")


class UploadedFile(Base):
    __tablename__ = "uploaded_files"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    chat_id = Column(String(36), ForeignKey("chats.id", ondelete="CASCADE"), nullable=False, index=True)
    filename = Column(String(255), nullable=False)
    file_path = Column(String(512), nullable=False)
    file_size = Column(Integer, nullable=False)
    mime_type = Column(String(128), nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    chat = relationship("Chat", back_populates="files")


class Project(Base):
    __tablename__ = "projects"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    chat_id = Column(String(36), ForeignKey("chats.id", ondelete="CASCADE"), nullable=True, index=True)
    title = Column(String(255), nullable=False, default="Financial Project")
    domain = Column(String(128), nullable=False, default="general_finance")
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    chat = relationship("Chat", back_populates="project")
    requirements = relationship("RequirementModel", back_populates="project", cascade="all, delete-orphan")
    stakeholders = relationship("Stakeholder", back_populates="project", cascade="all, delete-orphan")
    assumptions = relationship("Assumption", back_populates="project", cascade="all, delete-orphan")
    issues = relationship("RequirementIssueModel", back_populates="project", cascade="all, delete-orphan")
    compliance_mappings = relationship("ComplianceMappingModel", back_populates="project", cascade="all, delete-orphan")
    risks = relationship("RiskModel", back_populates="project", cascade="all, delete-orphan")
    sdlc_recommendations = relationship("SDLCRecommendationModel", back_populates="project", cascade="all, delete-orphan")
    approvals = relationship("ApprovalModel", back_populates="project", cascade="all, delete-orphan")
    traceability = relationship("TraceabilityModel", back_populates="project", cascade="all, delete-orphan")
    generated_documents = relationship("GeneratedDocumentModel", back_populates="project", cascade="all, delete-orphan")


class Stakeholder(Base):
    __tablename__ = "stakeholders"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(128), nullable=False)
    role = Column(String(64), nullable=False)  # product_owner, compliance_officer, security, etc.
    department = Column(String(128), nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    project = relationship("Project", back_populates="stakeholders")


class RequirementModel(Base):
    __tablename__ = "requirements"

    id = Column(String(64), primary_key=True)  # e.g. "REQ-ONB-001" or "FR-001"
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    statement = Column(EncryptedText, nullable=False)
    category = Column(String(64), nullable=False)  # 13 PS canonical categories
    sub_category = Column(String(128), nullable=True)
    priority = Column(String(32), nullable=False, default="Medium")
    version = Column(Integer, nullable=False, default=1)
    status = Column(String(64), nullable=False, default="draft")
    source_statement_id = Column(String(128), nullable=True)
    business_justification = Column(Text, nullable=True)
    dependencies_json = Column(Text, nullable=True)
    acceptance_criteria_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    project = relationship("Project", back_populates="requirements")
    versions = relationship("RequirementVersion", back_populates="requirement", cascade="all, delete-orphan", order_by="RequirementVersion.version")
    issues = relationship("RequirementIssueModel", back_populates="requirement", cascade="all, delete-orphan")
    compliance_mappings = relationship("ComplianceMappingModel", back_populates="requirement", cascade="all, delete-orphan")
    risks = relationship("RiskModel", back_populates="requirement")


class RequirementVersion(Base):
    __tablename__ = "requirement_versions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    requirement_id = Column(String(64), ForeignKey("requirements.id", ondelete="CASCADE"), nullable=False, index=True)
    version = Column(Integer, nullable=False)
    statement = Column(EncryptedText, nullable=False)
    category = Column(String(64), nullable=False)
    priority = Column(String(32), nullable=False)
    status = Column(String(64), nullable=False)
    changed_by = Column(String(128), nullable=True)
    change_reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    requirement = relationship("RequirementModel", back_populates="versions")


class Assumption(Base):
    __tablename__ = "assumptions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    statement = Column(Text, nullable=False)
    rationale = Column(Text, nullable=True)
    category = Column(String(64), nullable=True)
    status = Column(String(64), nullable=False, default="unverified")
    created_at = Column(DateTime, default=utcnow, nullable=False)
    project = relationship("Project", back_populates="assumptions")


class KnowledgeBaseVersion(Base):
    __tablename__ = "knowledge_base_versions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    version_tag = Column(String(64), nullable=False)
    manifest_hash = Column(String(64), nullable=False)
    documents_count = Column(Integer, nullable=False)
    total_chunks = Column(Integer, nullable=False)
    collection_name = Column(String(128), nullable=False, default="financial_kb_authoritative")
    created_at = Column(DateTime, default=utcnow, nullable=False)


class RequirementIssueModel(Base):
    __tablename__ = "requirement_issues"

    id = Column(String(64), primary_key=True)  # e.g. "ISS-001" or uuid
    requirement_id = Column(String(64), ForeignKey("requirements.id", ondelete="CASCADE"), nullable=True, index=True)
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    issue_type = Column(String(64), nullable=False)  # ambiguity, conflict, duplicate, incompleteness, etc.
    severity = Column(String(32), nullable=False, default="medium")
    detail = Column(Text, nullable=False)
    suggestion = Column(Text, nullable=False)
    rationale = Column(Text, nullable=False)
    status = Column(String(64), nullable=False, default="open")  # open, resolved, dismissed
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    requirement = relationship("RequirementModel", back_populates="issues")
    project = relationship("Project", back_populates="issues")


class AgentExecutionModel(Base):
    __tablename__ = "agent_executions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    chat_id = Column(String(36), ForeignKey("chats.id", ondelete="CASCADE"), nullable=False, index=True)
    agent_name = Column(String(64), nullable=False, index=True)
    phase = Column(String(64), nullable=False)
    input_payload = Column(Text, nullable=True)
    output_payload = Column(Text, nullable=True)
    duration_ms = Column(Integer, nullable=False, default=0)
    status = Column(String(32), nullable=False, default="success")  # success, error
    model_version = Column(String(64), nullable=True)
    kb_version = Column(String(64), nullable=True)
    prompt_version = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    chat = relationship("Chat", back_populates="agent_executions")


class ComplianceMappingModel(Base):
    __tablename__ = "compliance_mappings"

    id = Column(String(64), primary_key=True)
    requirement_id = Column(String(64), ForeignKey("requirements.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    regulation_name = Column(String(128), nullable=False)
    section_reference = Column(String(128), nullable=False)
    citation_quote = Column(Text, nullable=False)
    citation_doc_id = Column(String(64), nullable=False)
    citation_verified = Column(Boolean, default=False, nullable=False)
    compliance_status = Column(String(32), default="compliant", nullable=False)  # compliant, gap, needs_review
    control_required = Column(Text, nullable=False)
    gap_description = Column(Text, nullable=True)
    escalation_flag = Column(Boolean, default=False, nullable=False)
    escalation_reason = Column(Text, nullable=True)
    confidence_score = Column(Float, default=1.0, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    requirement = relationship("RequirementModel", back_populates="compliance_mappings")
    project = relationship("Project", back_populates="compliance_mappings")


class RiskModel(Base):
    __tablename__ = "risks"

    id = Column(String(64), primary_key=True)  # e.g. RSK-001
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    requirement_id = Column(String(64), ForeignKey("requirements.id", ondelete="SET NULL"), nullable=True, index=True)
    title = Column(String(256), nullable=False)
    category = Column(String(64), nullable=False)  # business, technical, security, compliance, operational, availability, legacy
    probability = Column(Integer, nullable=False)   # 1 to 5
    impact = Column(Integer, nullable=False)        # 1 to 5
    risk_score = Column(Integer, nullable=False)    # probability * impact
    severity = Column(String(32), nullable=False)   # low, medium, high, critical
    mitigation = Column(Text, nullable=False)
    owner = Column(String(128), default="Compliance & Risk Team", nullable=False)
    status = Column(String(32), default="identified", nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    requirement = relationship("RequirementModel", back_populates="risks")
    project = relationship("Project", back_populates="risks")


class SDLCRecommendationModel(Base):
    __tablename__ = "sdlc_recommendations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    chat_id = Column(String(36), ForeignKey("chats.id", ondelete="CASCADE"), nullable=True, index=True)
    selected_model = Column(String(64), nullable=False)
    rankings_json = Column(Text, nullable=False)   # JSON array of ModelScoreRanking
    factors_json = Column(Text, nullable=False)    # JSON dict of SDLCFactor
    explanation = Column(Text, nullable=False)
    workflow_json = Column(Text, nullable=False)   # JSON array of SDLCPhaseWorkflow
    is_approved = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    project = relationship("Project", back_populates="sdlc_recommendations")
    chat = relationship("Chat", back_populates="sdlc_recommendations")


class ApprovalModel(Base):
    __tablename__ = "approvals"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    chat_id = Column(String(36), ForeignKey("chats.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    gate_type = Column(String(64), nullable=False)   # baseline, requirement_change, sdlc_selection, etc.
    subject_id = Column(String(64), nullable=False)  # REQ-001, SDLC-001, etc.
    title = Column(String(256), nullable=False)
    description = Column(Text, nullable=False)
    required_role = Column(String(64), nullable=False)
    status = Column(String(32), default="pending", nullable=False)  # pending, approved, rejected, revised
    action_taken = Column(String(32), nullable=True)  # accept, reject, edit, regenerate, explain
    acting_role = Column(String(64), nullable=True)
    reviewer_comment = Column(Text, nullable=True)
    modified_payload = Column(Text, nullable=True)
    sdlc_signoffs_json = Column(Text, nullable=True)  # JSON dict of signed roles
    evidence_data_json = Column(Text, nullable=True)
    confidence_score = Column(Float, default=1.0, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    decided_at = Column(DateTime, nullable=True)

    chat = relationship("Chat", back_populates="approvals")
    project = relationship("Project", back_populates="approvals")


class TraceabilityModel(Base):
    __tablename__ = "traceability"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    source_statement_id = Column(String(128), nullable=True)
    requirement_id = Column(String(64), ForeignKey("requirements.id", ondelete="CASCADE"), nullable=False, index=True)
    regulation_chunk = Column(String(128), nullable=True)
    control = Column(String(128), nullable=True)
    acceptance_criteria_id = Column(String(128), nullable=True)
    risk_id = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    project = relationship("Project", back_populates="traceability")
    requirement = relationship("RequirementModel")


class GeneratedDocumentModel(Base):
    __tablename__ = "generated_documents"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    chat_id = Column(String(36), ForeignKey("chats.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=True, index=True)
    doc_type = Column(String(64), nullable=False)  # srs, rtm, risk_register, compliance_matrix
    version = Column(Integer, default=1, nullable=False)
    file_path = Column(String(512), nullable=False)
    sha256 = Column(String(64), nullable=False)
    status = Column(String(32), default="generated", nullable=False)  # generated, signed_off, archived
    created_at = Column(DateTime, default=utcnow, nullable=False)

    chat = relationship("Chat", back_populates="generated_documents")
    project = relationship("Project", back_populates="generated_documents")


class AuditLogModel(Base):
    __tablename__ = "audit_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    chat_id = Column(String(36), ForeignKey("chats.id", ondelete="CASCADE"), nullable=True, index=True)
    event = Column(String(64), nullable=False, index=True)
    actor = Column(String(128), nullable=False)
    payload_json = Column(Text, nullable=False)
    prev_hash = Column(String(64), nullable=False)
    hash = Column(String(64), nullable=False, unique=True, index=True)
    created_at = Column(DateTime, default=utcnow, nullable=False, index=True)

    chat = relationship("Chat", back_populates="audit_logs")


class ModelVersionModel(Base):
    __tablename__ = "model_versions"

    id = Column(String(64), primary_key=True)  # e.g. "qwen2.5:7b-instruct" or "req-engineer-ft:v1"
    name = Column(String(128), nullable=False)
    base_model = Column(String(128), nullable=False)
    parameters = Column(String(32), nullable=True)  # 7B, 3B, 14B
    context_len = Column(Integer, default=4096, nullable=False)
    checksum = Column(String(64), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)


def purge_expired_chats(db: Session, retention_days: int = 30) -> int:
    """
    Purges soft-deleted chats whose deleted_at is older than retention_days.
    Returns the number of purged chats.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    expired = db.query(Chat).filter(Chat.deleted_at.isnot(None), Chat.deleted_at < cutoff).all()
    count = len(expired)
    for c in expired:
        db.delete(c)
    db.commit()
    return count



