"""
Question-bank slots and role-based interview template schemas per PS §2, §7 and Master Plan A6.
"""
from enum import Enum
from typing import List, Optional, Any
from pydantic import BaseModel, Field


class TopicGroup(str, Enum):
    BUSINESS = "Business"
    USERS_ROLES = "Users and Roles"
    WORKFLOW = "Workflow and Processes"
    DATA = "Data and Retention"
    SECURITY = "Security and Encryption"
    COMPLIANCE = "Regulatory Compliance"
    PERFORMANCE = "Performance and Scalability"
    INTEGRATION = "External Integrations"
    RISK = "Risk and Failure Modes"
    CONSTRAINTS_EXCEPTIONS = "Constraints, Limits and Audit"


class SlotItem(BaseModel):
    name: str = Field(description="Dotted slot key e.g. data.retention_period, limits.max_transaction")
    topic: TopicGroup = Field(description="Parent topic group")
    question_text: str = Field(description="Natural language question to elicit this slot")
    required: bool = Field(default=True, description="Whether slot is mandatory for baseline freeze")
    filled: bool = Field(default=False, description="Whether slot has been extracted from user input")
    value: Optional[Any] = Field(default=None, description="Extracted value or default assumption")
    is_assumption: bool = Field(default=False, description="True if value was assumed upon user 'I don't know'")
    evidence_quote: Optional[str] = Field(default=None, description="Direct excerpt from stakeholder answer")


class InterviewTemplate(BaseModel):
    role_name: str = Field(description="e.g. Product Owner, Compliance Officer, Security Architect")
    description: str = Field(description="Focus areas and perspective for this interview persona")
    priority_topics: List[TopicGroup] = Field(description="Ordered list of topic groups to emphasize")
    recommended_slots: List[str] = Field(description="Specific slot keys critical for this role")
