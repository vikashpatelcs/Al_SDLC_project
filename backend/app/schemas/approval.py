"""
Human-in-the-Loop approval gate schemas per PS §16 and Master Plan Phase 12.
"""
from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class GateType(str, Enum):
    BASELINE = "baseline"
    REQUIREMENT_CHANGE = "requirement_change"
    REGULATORY_INTERPRETATION = "regulatory_interpretation"
    HIGH_RISK_SECURITY = "high_risk_security"
    CONFLICT_DECISION = "conflict_decision"
    ARCHITECTURE_CRITICAL = "architecture_critical"
    SDLC_SELECTION = "sdlc_selection"
    PRODUCTION_READINESS = "production_readiness"


class ApprovalAction(str, Enum):
    ACCEPT = "accept"
    REJECT = "reject"
    EDIT = "edit"
    REGENERATE = "regenerate"
    EXPLAIN = "explain"


class ActingRole(str, Enum):
    PRODUCT_OWNER = "product_owner"
    COMPLIANCE_OFFICER = "compliance_officer"
    SECURITY_ARCHITECT = "security_architect"
    RISK_OFFICER = "risk_officer"
    PROJECT_MANAGER = "project_manager"
    SOFTWARE_ARCHITECT = "software_architect"


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    REVISED = "revised"


class ApprovalRequest(BaseModel):
    id: str = Field(description="Unique approval request ID e.g. APR-001")
    chat_id: str = Field(description="Associated chat session")
    gate_type: GateType = Field(description="One of the 8 mandatory PS §16 gates")
    subject_id: str = Field(description="ID of target requirement, SDLC recommendation, or document")
    title: str = Field(description="Human-readable approval gate summary")
    description: str = Field(description="Detailed context or rationale needing human sign-off")
    required_role: ActingRole = Field(default=ActingRole.PRODUCT_OWNER, description="Mandated reviewer role")
    status: ApprovalStatus = Field(default=ApprovalStatus.PENDING, description="Current gate status")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ApprovalDecision(BaseModel):
    approval_id: str = Field(description="ID of the gate being acted upon")
    action: ApprovalAction = Field(description="Accept, Reject, Edit, Regenerate, or Explain")
    acting_role: ActingRole = Field(description="Role signed under (PM, architect, security, compliance)")
    comment: Optional[str] = Field(default=None, description="Human reviewer notes or justification")
    modified_payload: Optional[str] = Field(default=None, description="Edited content if action == 'edit'")
    decided_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
