"""
Agent Permission Matrix and Security Boundary per Master Plan A4, Phase 9, and Rule 7.

Rule 7: Agents other than the Coordinator never write to the DB.
The Coordinator is the single authoritative writer for database persistence.
All other agents return typed results / state modifications to the Coordinator.
"""
from enum import Enum
from typing import Dict, Set


class AgentPermission(str, Enum):
    READ_DB = "read_db"
    WRITE_DB = "write_db"
    INVOKE_LLM = "invoke_llm"
    QUERY_RAG = "query_rag"
    GENERATE_ACTION_CARD = "generate_action_card"


# Permission assignment matrix across the 6 system agents
AGENT_PERMISSIONS: Dict[str, Set[AgentPermission]] = {
    "coordinator": {
        AgentPermission.READ_DB,
        AgentPermission.WRITE_DB,
        AgentPermission.INVOKE_LLM,
        AgentPermission.QUERY_RAG,
        AgentPermission.GENERATE_ACTION_CARD,
    },
    "requirement_engineer": {
        AgentPermission.READ_DB,
        AgentPermission.INVOKE_LLM,
        AgentPermission.GENERATE_ACTION_CARD,
    },
    "analysis": {
        AgentPermission.READ_DB,
        AgentPermission.QUERY_RAG,
        AgentPermission.GENERATE_ACTION_CARD,
    },
    "compliance_security_risk": {
        AgentPermission.READ_DB,
        AgentPermission.QUERY_RAG,
        AgentPermission.INVOKE_LLM,
    },
    "sdlc": {
        AgentPermission.READ_DB,
        AgentPermission.GENERATE_ACTION_CARD,
    },
    "documentation_validation": {
        AgentPermission.READ_DB,
        AgentPermission.GENERATE_ACTION_CARD,
    },
}


class PermissionDeniedError(PermissionError):
    """Raised when an agent attempts an unauthorized operation."""
    pass


def check_permission(agent_name: str, permission: AgentPermission) -> bool:
    """Check if the given agent has permission for the requested action."""
    perms = AGENT_PERMISSIONS.get(agent_name, set())
    return permission in perms


def assert_can_write_db(agent_name: str) -> None:
    """
    Enforce Rule 7: Only Coordinator may write to the database.
    Raises PermissionDeniedError if any other agent attempts a DB write.
    """
    if not check_permission(agent_name, AgentPermission.WRITE_DB):
        raise PermissionDeniedError(
            f"Rule 7 Violation: Agent '{agent_name}' is forbidden from writing to the database. "
            f"Only the Coordinator agent has database write permissions."
        )


def assert_permission(agent_name: str, permission: AgentPermission) -> None:
    """Verify agent has the required permission, raising PermissionDeniedError if not."""
    if not check_permission(agent_name, permission):
        raise PermissionDeniedError(
            f"Agent '{agent_name}' lacks permission '{permission.value}'."
        )
