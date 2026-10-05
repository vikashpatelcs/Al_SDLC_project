"""
Pydantic v2 core schemas for AI Requirement Engineer (FinReq).
"""
from backend.app.schemas.issue import (
    RequirementIssue,
    IssueType,
    IssueSeverity,
    IssueStatus,
)
from backend.app.schemas.requirement import (
    Requirement,
    RequirementCategory,
    RequirementStatus,
    Priority,
    AcceptanceCriteria,
)
from backend.app.schemas.approval import (
    ApprovalRequest,
    ApprovalDecision,
    GateType,
    ApprovalAction,
    ActingRole,
    ApprovalStatus,
)
from backend.app.schemas.risk import (
    RiskItem,
    RiskCategory,
    RiskSeverity,
    RiskStatus,
)
from backend.app.schemas.sdlc import (
    SDLCRecommendation,
    SDLCFactor,
    SDLCModelType,
    SDLCPhaseWorkflow,
    ModelScoreRanking,
)
from backend.app.schemas.message import (
    AgentMessage,
    ActionCard,
    ActionCardType,
    MessageRole,
    AgentSender,
)
from backend.app.schemas.slots import (
    SlotItem,
    InterviewTemplate,
    TopicGroup,
)

__all__ = [
    "Requirement",
    "RequirementCategory",
    "RequirementStatus",
    "Priority",
    "AcceptanceCriteria",
    "RequirementIssue",
    "IssueType",
    "IssueSeverity",
    "IssueStatus",
    "ApprovalRequest",
    "ApprovalDecision",
    "GateType",
    "ApprovalAction",
    "ActingRole",
    "ApprovalStatus",
    "RiskItem",
    "RiskCategory",
    "RiskSeverity",
    "RiskStatus",
    "SDLCRecommendation",
    "SDLCFactor",
    "SDLCModelType",
    "SDLCPhaseWorkflow",
    "ModelScoreRanking",
    "AgentMessage",
    "ActionCard",
    "ActionCardType",
    "MessageRole",
    "AgentSender",
    "SlotItem",
    "InterviewTemplate",
    "TopicGroup",
]
