"""
Canonical structured requirement schemas per PS §8, §9 and Master Plan A7.
"""
from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field

from backend.app.schemas.issue import RequirementIssue


class RequirementCategory(str, Enum):
    BUSINESS = "Business"
    FUNCTIONAL = "Functional"
    NON_FUNCTIONAL = "Non-Functional"
    TECHNICAL = "Technical"
    SECURITY = "Security"
    PRIVACY = "Privacy"
    COMPLIANCE = "Compliance"
    PERFORMANCE = "Performance"
    AVAILABILITY = "Availability"
    AUDITABILITY = "Auditability"
    OPERATIONAL = "Operational"
    INTERFACE = "Interface"
    DATA = "Data"


class Priority(str, Enum):
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


class RequirementStatus(str, Enum):
    DRAFT = "draft"
    ANALYZED = "analyzed"
    BASELINE_APPROVED = "baseline_approved"
    REJECTED = "rejected"
    MODIFIED = "modified"


class AcceptanceCriteria(BaseModel):
    id: str = Field(description="AC Identifier e.g. AC-001")
    given: str = Field(description="Preconditions / Initial system context")
    when: str = Field(description="Trigger action or stakeholder event")
    then: str = Field(description="Expected verifiable outcome")


class Requirement(BaseModel):
    id: str = Field(description="Structured identifier e.g. FR-ONB-001, SR-ONB-002")
    project_id: Optional[str] = Field(default=None, description="Linked project or chat session ID")
    statement: str = Field(description="Formal requirement statement using RFC 2119 / IEEE keywords ('shall')")
    category: RequirementCategory = Field(description="Multi-label dimension from 13 PS classes")
    sub_category: Optional[str] = Field(default=None, description="Granular subtype e.g. KYC, Encryption, SLA")
    priority: Priority = Field(default=Priority.MEDIUM, description="Business and compliance priority")
    version: int = Field(default=1, description="Sequential requirement version number")
    status: RequirementStatus = Field(default=RequirementStatus.DRAFT, description="Lifecycle status")
    source_statement_id: Optional[str] = Field(
        default=None,
        description="Link to original user utterance or uploaded document chunk ID"
    )
    business_justification: Optional[str] = Field(
        default=None,
        description="Value proposition or regulatory trigger requiring this specification"
    )
    dependencies: List[str] = Field(
        default_factory=list,
        description="IDs of prerequisite or correlated requirements"
    )
    acceptance_criteria: List[AcceptanceCriteria] = Field(
        default_factory=list,
        description="Testable Gherkin verification scenarios"
    )
    evidence_ids: List[str] = Field(
        default_factory=list,
        description="Citations to authoritative regulatory KB chunks or document references"
    )
    issues: List[RequirementIssue] = Field(
        default_factory=list,
        description="Quality and conflict findings flagged by Analysis agent"
    )
    kb_version: str = Field(default="1.0.0", description="Financial Knowledge Base version active when mapped")
    model_version: str = Field(default="qwen2.5:3b", description="LLM/LoRA version that generated/extracted this requirement")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Creation timestamp"
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Last modification timestamp"
    )
