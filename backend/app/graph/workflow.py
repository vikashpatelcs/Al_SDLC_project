"""
LangGraph Orchestration Workflow and State Machine per Master Plan A4, A5, and Phase 9.
"""
from typing import Any, Dict, Optional
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.base import BaseCheckpointSaver

from backend.app.graph.state import AgentState, ConversationPhase
from backend.app.graph.nodes import (
    requirement_engineer_node,
    analysis_node,
    approval_gate_node,
    compliance_security_risk_node,
    sdlc_node,
    documentation_validation_node,
)
from backend.app.graph.checkpointer import SqliteCheckpointer


def route_after_requirement_engineer(state: AgentState) -> str:
    """Route after requirement engineer: wait for answers or proceed to analysis."""
    phase = state.get("phase", "")
    if phase == ConversationPhase.QUESTIONS_SENT.value:
        return END
    return "analysis"


def route_after_analysis(state: AgentState) -> str:
    """Route after analysis to approval gate."""
    return "approval_gate"


def route_after_approval_gate(state: AgentState) -> str:
    """Route after approval gate: proceed if approved, re-analyze if rejected, halt if pending."""
    status = state.get("approval_status", {}).get("requirement_baseline")
    if status == "approved":
        return "compliance_security_risk"
    elif status == "rejected":
        return "analysis"
    return END


def build_orchestration_graph(
    checkpointer: Optional[BaseCheckpointSaver] = None,
    with_interrupts: bool = False
) -> Any:
    """
    Construct the 6-agent StateGraph workflow with deterministic routing,
    approval gates, and state persistence.
    """
    workflow = StateGraph(AgentState)

    # 1. Register agent nodes
    workflow.add_node("requirement_engineer", requirement_engineer_node)
    workflow.add_node("analysis", analysis_node)
    workflow.add_node("approval_gate", approval_gate_node)
    workflow.add_node("compliance_security_risk", compliance_security_risk_node)
    workflow.add_node("sdlc", sdlc_node)
    workflow.add_node("documentation_validation", documentation_validation_node)

    # 2. Add edges and conditional routing
    workflow.add_edge(START, "requirement_engineer")

    workflow.add_conditional_edges(
        "requirement_engineer",
        route_after_requirement_engineer,
        {
            END: END,
            "analysis": "analysis"
        }
    )

    workflow.add_conditional_edges(
        "analysis",
        route_after_analysis,
        {
            "approval_gate": "approval_gate",
            "compliance_security_risk": "compliance_security_risk"
        }
    )

    workflow.add_conditional_edges(
        "approval_gate",
        route_after_approval_gate,
        {
            "compliance_security_risk": "compliance_security_risk",
            "analysis": "analysis",
            END: END
        }
    )

    workflow.add_edge("compliance_security_risk", "sdlc")
    workflow.add_edge("sdlc", "documentation_validation")
    workflow.add_edge("documentation_validation", END)

    # 3. Checkpointing and interrupts
    cp = checkpointer or SqliteCheckpointer()
    interrupts = ["approval_gate"] if with_interrupts else []

    return workflow.compile(checkpointer=cp, interrupt_before=interrupts)
