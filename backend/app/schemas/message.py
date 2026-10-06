"""
Chat, Agent message, and inline Action Card schemas per Master Plan A13 and Phase 2.
"""
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class AgentSender(str, Enum):
    COORDINATOR = "coordinator"
    REQUIREMENT_ENGINEER = "requirement_engineer"
    ANALYSIS = "analysis"
    COMPLIANCE_SECURITY_RISK = "compliance_security_risk"
    SDLC = "sdlc"
    DOCUMENTATION_VALIDATION = "documentation_validation"


class ActionCardType(str, Enum):
    QUESTION_GROUP = "question_group"
    ISSUE_SUMMARY = "issue_summary"
    REQUIREMENT_CARD = "requirement_card"
    APPROVAL_REQUEST = "approval_request"
    SDLC_RANKING = "sdlc_ranking"
    DOWNLOAD_PDF = "download_pdf"
    COMPLIANCE_CARD = "compliance_card"
    RISK_CARD = "risk_card"


class ActionCard(BaseModel):
    id: str = Field(description="Unique card identifier")
    card_type: ActionCardType = Field(description="Type of inline card to render in chat")
    title: str = Field(description="Card heading")
    payload: Dict[str, Any] = Field(default_factory=dict, description="Structured data for card UI")
    actions: List[str] = Field(default_factory=list, description="Available inline buttons e.g. Accept, Edit, Reject")


class AgentMessage(BaseModel):
    id: str = Field(description="Unique message identifier")
    chat_id: str = Field(description="Session chat ID")
    role: MessageRole = Field(description="Sender role: user, assistant, system")
    sender_agent: Optional[AgentSender] = Field(default=None, description="Specific agent producing message")
    content: str = Field(description="Display content (masked for sensitive entities)")
    action_cards: List[ActionCard] = Field(default_factory=list, description="Inline action cards embedded in message")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
