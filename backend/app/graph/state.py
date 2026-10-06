"""
Typed Graph State and Conversation Phase Definitions per Master Plan A5 and Phase 9.
"""
from enum import Enum
from typing import Any, Dict, List, Optional
from typing_extensions import TypedDict


class ConversationPhase(str, Enum):
    INTAKE = "INTAKE"
    QUESTIONS_SENT = "QUESTIONS_SENT"
    ANSWERS_RECEIVED = "ANSWERS_RECEIVED"
    EXTRACTED = "EXTRACTED"
    ANALYSED = "ANALYSED"
    ISSUE_REVIEW = "ISSUE_REVIEW"
    REQUIREMENT_BASELINE_APPROVAL = "REQUIREMENT_BASELINE_APPROVAL"
    ENRICH = "ENRICH"
    HIGH_RISK_APPROVAL = "HIGH_RISK_APPROVAL"
    ARTEFACTS = "ARTEFACTS"
    SDLC_ANALYSED = "SDLC_ANALYSED"
    FINAL_APPROVAL = "FINAL_APPROVAL"
    DONE = "DONE"


class AgentState(TypedDict, total=False):
    chat_id: str
    project_id: str
    phase: str
    user_input: str
    uploaded_chunks: List[Dict[str, Any]]
    requirements: List[Dict[str, Any]]
    issues: List[Dict[str, Any]]
    assumptions: List[Dict[str, Any]]
    compliance_mappings: List[Dict[str, Any]]
    risks: List[Dict[str, Any]]
    sdlc_recommendations: Dict[str, Any]
    approval_status: Dict[str, Any]
    action_cards: List[Dict[str, Any]]
    progress_messages: List[str]
    iteration_count: int
    error: Optional[str]
    response_text: str
