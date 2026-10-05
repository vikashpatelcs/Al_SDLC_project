"""
Issue and quality defect schemas per PS §10 (Quality analysis) and Master Plan Phase 1.
"""
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class IssueType(str, Enum):
    AMBIGUITY = "ambiguity"
    CONFLICT = "conflict"
    DUPLICATE = "duplicate"
    INCOMPLETENESS = "incompleteness"
    WEAK_WORD = "weak_word"
    MISSING_SOURCE = "missing_source"
    NON_MEASURABLE = "non_measurable"
    FEASIBILITY = "feasibility"
    UNTESTABLE = "untestable"
    REGULATORY_GAP = "regulatory_gap"


class IssueSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class IssueStatus(str, Enum):
    OPEN = "open"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


class RequirementIssue(BaseModel):
    id: str = Field(description="Unique issue identifier e.g. ISS-001")
    requirement_id: Optional[str] = Field(default=None, description="Linked requirement ID")
    issue_type: IssueType = Field(description="Categorization of quality defect")
    severity: IssueSeverity = Field(default=IssueSeverity.MEDIUM, description="Impact severity")
    detail: str = Field(description="Specific finding or problematic phrase")
    suggestion: str = Field(description="Measurable improvement or rewrite")
    rationale: str = Field(description="Engineering or compliance rationale for flag")
    status: IssueStatus = Field(default=IssueStatus.OPEN, description="Resolution status")
