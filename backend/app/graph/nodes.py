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
from backend.app.agents.compliance_security_risk import compliance_security_risk_agent
from backend.app.agents.sdlc import sdlc_agent
from backend.app.agents.documentation import DocumentationAgent
from backend.app.db.models import RequirementModel

documentation_agent = DocumentationAgent()


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
    """Compliance + Security + Risk Agent: executes RAG grounding, citation validation, and 5x5 risk scoring."""
    progress_messages = list(state.get("progress_messages", []))
    progress_messages.append("Verifying regulatory compliance against authoritative RBI/DPDP guidelines and generating risk register...")

    reqs = state.get("requirements", [])
    project_id = state.get("project_id", "default_proj")

    result = compliance_security_risk_agent.analyze_compliance_and_risk(
        requirements=reqs,
        project_id=project_id
    )

    action_cards = list(state.get("action_cards", []))
    action_cards.extend(result.get("action_cards", []))

    return {
        "phase": ConversationPhase.ENRICH.value,
        "compliance_mappings": result.get("compliance_mappings", []),
        "risks": result.get("risks", []),
        "action_cards": action_cards,
        "progress_messages": progress_messages
    }


def sdlc_node(state: AgentState) -> Dict[str, Any]:
    """SDLC Agent: recommends and ranks development methodologies via deterministic MCDA."""
    progress_messages = list(state.get("progress_messages", []))
    progress_messages.append("Computing SDLC methodology recommendation based on compliance constraints and project risk...")

    reqs = state.get("requirements", [])
    project_id = state.get("project_id", "default_proj")
    chat_id = state.get("chat_id")

    rec = sdlc_agent.recommend_sdlc(
        requirements=reqs,
        project_id=project_id,
        chat_id=chat_id
    )

    card = sdlc_agent.build_sdlc_ranking_card(rec)
    action_cards = list(state.get("action_cards", []))
    action_cards.append(card.model_dump(mode="json"))

    return {
        "phase": ConversationPhase.SDLC_ANALYSED.value,
        "sdlc_recommendations": rec.model_dump(mode="json"),
        "action_cards": action_cards,
        "progress_messages": progress_messages
    }


def documentation_validation_node(state: AgentState) -> Dict[str, Any]:
    """Documentation & Validation Agent (Phase 14): synthesizes artefacts, builds RTM, compiles SRS PDF."""
    progress_messages = list(state.get("progress_messages", []))
    progress_messages.append("Validating specification package, building RTM, and compiling IEEE 29148 SRS...")

    chat_id = state.get("chat_id", str(uuid.uuid4()))
    project_id = state.get("project_id", "default_proj")
    requirements = state.get("requirements", [])
    compliance_mappings = state.get("compliance_mappings", [])
    risks = state.get("risks", [])
    sdlc_recommendation = state.get("sdlc_recommendations", {})
    issues = state.get("issues", [])
    approval_status = dict(state.get("approval_status", {}))
    is_approved = approval_status.get("requirement_baseline") == "approved"

    project_data = {
        "id": project_id,
        "title": "Digital Customer Onboarding & KYC",
        "version": 1
    }

    # Synthesize artefacts and compile SRS PDF (DB session is None in node since nodes do not write to DB)
    result = documentation_agent.compile_srs(
        db=None,
        chat_id=chat_id,
        project_data=project_data,
        requirements=requirements,
        compliance_mappings=compliance_mappings,
        risks=risks,
        sdlc_recommendation=sdlc_recommendation,
        issues=issues,
        is_approved=is_approved
    )

    action_cards = list(state.get("action_cards", []))
    action_cards.append(result["action_card"].model_dump(mode="json"))

    pdf_meta = result["pdf_meta"]
    progress_messages.append(
        f"IEEE 29148 SRS compiled. RTM coverage: {int(result['coverage_score'] * 100)}%."
    )

    return {
        "phase": ConversationPhase.DONE.value,
        "action_cards": action_cards,
        "progress_messages": progress_messages,
        "response_text": (
            f"Requirements engineering cycle complete! {len(result['active_requirements'])} specifications validated "
            f"with {int(result['coverage_score'] * 100)}% RTM coverage.\n\n"
            f"Your IEEE 29148 Software Requirements Specification (SRS) has been compiled. "
            f"Download and inspect the package via the card below."
        )
    }


def approval_gate_node(state: AgentState) -> Dict[str, Any]:
    """Human-in-the-loop approval gate node: manages approval decisions, halts, and rejection loops."""
    progress_messages = list(state.get("progress_messages", []))
    approval_status = dict(state.get("approval_status", {}))
    action_cards = list(state.get("action_cards", []))

    current_decision = approval_status.get("requirement_baseline")

    # Halt pipeline only if explicit human approval is required (auto_approve is False) and not yet decided
    if approval_status.get("auto_approve") is False and current_decision not in ("approved", "rejected"):
        progress_messages.append("Halting pipeline: Awaiting mandatory human stakeholder approval on requirement baseline...")
        approval_card = ActionCard(
            id=f"card-apr-{uuid.uuid4().hex[:8]}",
            card_type=ActionCardType.APPROVAL_REQUEST,
            title="Mandatory Baseline Approval Gate (PS §16)",
            payload={
                "gate_type": "baseline",
                "required_role": "product_owner",
                "summary": "Review extracted requirements baseline and statutory compliance mappings before enrichment.",
                "total_requirements": len(state.get("requirements", []))
            },
            actions=["Accept", "Reject", "Edit", "Regenerate", "Explain"]
        )
        action_cards.append(approval_card.model_dump(mode="json"))
        return {
            "approval_status": approval_status,
            "action_cards": action_cards,
            "progress_messages": progress_messages,
            "response_text": "Execution paused at Human Approval Gate: Please review and sign off on the baseline specifications to proceed."
        }

    # Otherwise mark approved (if not rejected)
    if current_decision != "rejected":
        approval_status["requirement_baseline"] = "approved"
        progress_messages.append("Requirement baseline signed off/approved.")

    return {
        "approval_status": approval_status,
        "phase": ConversationPhase.ENRICH.value if approval_status.get("requirement_baseline") == "approved" else ConversationPhase.ANALYSED.value,
        "progress_messages": progress_messages
    }
