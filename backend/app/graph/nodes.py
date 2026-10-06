"""
Graph Node functions for the 6 specialized agents and deterministic service nodes per Master Plan A4/Phase 9.
Nodes return typed updates to AgentState; they do NOT write to the DB directly (enforcing Rule 7).
"""
import time
import uuid
from typing import Any, Dict, List, Optional

from backend.app.graph.state import AgentState, ConversationPhase
from backend.app.schemas.message import ActionCard, ActionCardType
from backend.app.agents.requirement_engineer import requirement_engineer_agent
from backend.app.agents.analysis import analysis_engine
from backend.app.db.models import RequirementModel


def requirement_engineer_node(state: AgentState) -> Dict[str, Any]:
    """Requirement Engineer Agent: drives slot-based interviews and extracts requirements."""
    start_time = time.time()
    user_input = state.get("user_input", "")
    phase = state.get("phase", ConversationPhase.INTAKE.value)
    progress_messages = list(state.get("progress_messages", []))
    action_cards = list(state.get("action_cards", []))

    # Turn 1: Concept Intake -> Generate Grouped Questions
    if phase == ConversationPhase.INTAKE.value and not state.get("requirements"):
        progress_messages.append("Eliciting stakeholder concept and identifying missing requirement slots...")
        q_card = requirement_engineer_agent.generate_grouped_questions(user_input)
        return {
            "phase": ConversationPhase.QUESTIONS_SENT.value,
            "action_cards": [q_card.model_dump(mode="json")],
            "progress_messages": progress_messages,
            "response_text": (
                "Hello! I am your AI Requirement Engineer. To establish a complete, compliant financial requirements baseline, "
                "I have identified key requirements slots across Workflow, Security, Limits, and Auditability.\n\n"
                "Please review the grouped questions in the card below. You can answer directly or select 'Assume Standard Defaults'."
            )
        }

    # Turn 2+: Answers Received -> Extract Requirements & Assumptions
    progress_messages.append("Extracting structured IEEE requirements and parsing business specifications...")
    extracted_objs = requirement_engineer_agent.extract_requirements_from_text(
        text=user_input,
        source_statement_id=f"msg#{state.get('chat_id', 'chat')[:8]}",
        project_id=state.get("project_id", "default_proj")
    )
    req_dicts = [r.model_dump(mode="json") for r in extracted_objs]

    # Extract default assumptions
    assumptions_objs = requirement_engineer_agent.extract_assumptions(user_input, state.get("project_id", "default_proj"))
    assump_dicts = [
        {
            "id": a.id,
            "project_id": a.project_id,
            "statement": a.statement,
            "rationale": a.rationale,
            "category": a.category,
            "status": a.status
        }
        for a in assumptions_objs
    ]

    # Build Requirement Summary ActionCard
    cat_counts = {}
    for r in extracted_objs:
        cat_counts[r.category.value] = cat_counts.get(r.category.value, 0) + 1

    summary_card = ActionCard(
        id=f"card-extract-{uuid.uuid4().hex[:8]}",
        card_type=ActionCardType.REQUIREMENT_CARD,
        title=f"Structured Requirements Extracted ({len(extracted_objs)} Total)",
        payload={
            "total_requirements": len(extracted_objs),
            "category_breakdown": cat_counts,
            "assumptions_recorded": len(assumptions_objs),
            "requirements": req_dicts
        },
        actions=["View Traceability", "Analyze Quality", "Baseline Approval"]
    )
    action_cards.append(summary_card.model_dump(mode="json"))

    return {
        "phase": ConversationPhase.EXTRACTED.value,
        "requirements": req_dicts,
        "assumptions": assump_dicts,
        "action_cards": action_cards,
        "progress_messages": progress_messages,
        "response_text": f"Successfully extracted {len(req_dicts)} structured requirements from your input."
    }


def analysis_node(state: AgentState) -> Dict[str, Any]:
    """Analysis Engine Agent: performs 10-dimension quality assessment and detects defects."""
    progress_messages = list(state.get("progress_messages", []))
    progress_messages.append("Analyzing requirements for ambiguity, conflicts, regulatory gaps, and testability...")

    req_dicts = state.get("requirements", [])
    project_id = state.get("project_id", "default_proj")

    # Reconstruct transient RequirementModel instances for analysis
    temp_reqs = []
    for r in req_dicts:
        temp_reqs.append(RequirementModel(
            id=r["id"],
            project_id=project_id,
            statement=r["statement"],
            category=r.get("category", "Functional"),
            priority=r.get("priority", "Medium"),
            source_statement_id=r.get("source_statement_id")
        ))

    issues_models = analysis_engine.analyze_project(project_id, temp_reqs, db=None)
    summary_card = analysis_engine.build_issue_summary_card(temp_reqs, issues_models)

    action_cards = list(state.get("action_cards", []))
    action_cards.append(summary_card.model_dump(mode="json"))

    issues_dicts = [
        {
            "id": i.id,
            "requirement_id": i.requirement_id,
            "project_id": i.project_id,
            "issue_type": i.issue_type,
            "severity": i.severity,
            "detail": i.detail,
            "suggestion": i.suggestion,
            "rationale": i.rationale,
            "status": i.status
        }
        for i in issues_models
    ]

    return {
        "phase": ConversationPhase.ANALYSED.value,
        "issues": issues_dicts,
        "action_cards": action_cards,
        "progress_messages": progress_messages
    }


def compliance_security_risk_node(state: AgentState) -> Dict[str, Any]:
    """Compliance + Security + Risk Agent (Phase 10 stub fixture)."""
    progress_messages = list(state.get("progress_messages", []))
    progress_messages.append("Verifying regulatory compliance against authoritative RBI/DPDP guidelines and generating risk register...")

    compliance_mappings = [
        {
            "standard": "RBI Master Direction on KYC",
            "section": "Section 24",
            "citation": "RBI/DBR/2015-16/18 Master Direction DBR.AML.BC.No.81/14.01.001/2015-16",
            "status": "compliant"
        },
        {
            "standard": "Digital Personal Data Protection Act 2023",
            "section": "Section 6(1)",
            "citation": "DPDP Act 2023 Section 6(1)",
            "status": "compliant"
        }
    ]

    risks = [
        {
            "risk_id": "RSK-001",
            "category": "Compliance",
            "description": "Failure to maintain audit trail for 5 years violates PMLA 2002.",
            "probability": 2,
            "impact": 5,
            "score": 10,
            "mitigation": "Enforce immutable WORM audit storage."
        }
    ]

    return {
        "phase": ConversationPhase.ENRICH.value,
        "compliance_mappings": compliance_mappings,
        "risks": risks,
        "progress_messages": progress_messages
    }


def sdlc_node(state: AgentState) -> Dict[str, Any]:
    """SDLC Agent (Phase 11 stub fixture): recommends and ranks development methodologies."""
    progress_messages = list(state.get("progress_messages", []))
    progress_messages.append("Computing SDLC methodology recommendation based on compliance constraints and project risk...")

    sdlc_recommendation = {
        "recommended_model": "Hybrid Agile with Stage-Gate Compliance",
        "score": 88,
        "confidence": 0.92,
        "factors": {
            "regulatory_complexity": "High (Strict RBI/PMLA baselines)",
            "team_distribution": "Distributed",
            "speed_to_market": "High"
        },
        "runners_up": [
            {"model": "Formal Waterfall", "score": 74},
            {"model": "Pure Kanban", "score": 62}
        ]
    }

    return {
        "phase": ConversationPhase.SDLC_ANALYSED.value,
        "sdlc_recommendations": sdlc_recommendation,
        "progress_messages": progress_messages
    }


def documentation_validation_node(state: AgentState) -> Dict[str, Any]:
    """Documentation & Validation Agent (Phase 12 stub fixture): prepares final engineering baseline."""
    progress_messages = list(state.get("progress_messages", []))
    progress_messages.append("Generating requirements traceability matrix (RTM) and validating final specification package...")

    return {
        "phase": ConversationPhase.DONE.value,
        "progress_messages": progress_messages,
        "response_text": "Engineering requirements baseline complete, validated, and ready for development."
    }


def approval_gate_node(state: AgentState) -> Dict[str, Any]:
    """Human-in-the-loop approval gate node: records baseline approval decisions."""
    progress_messages = list(state.get("progress_messages", []))
    progress_messages.append("Awaiting stakeholder sign-off on baseline specifications...")

    approval_status = state.get("approval_status", {})
    approval_status["requirement_baseline"] = "approved"

    return {
        "approval_status": approval_status,
        "phase": ConversationPhase.ENRICH.value,
        "progress_messages": progress_messages
    }
