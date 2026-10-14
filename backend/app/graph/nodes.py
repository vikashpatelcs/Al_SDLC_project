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
                "Hello! I am your AI Requirement Engineer for Financial Systems.\n\n"
                "To generate your official 23-Section ISO/IEC/IEEE 29148 Software Requirements Specification (SRS) PDF, "
                "our multi-agent system runs a rigorous compliance and engineering pipeline:\n"
                "1. **Stakeholder Elicitation:** Gathers business, technical, and regulatory slots.\n"
                "2. **Structured Extraction:** Synthesizes IEEE functional and non-functional requirements.\n"
                "3. **Regulatory Verification:** Maps statutory rules (RBI Master Directions, PMLA 2002, DPDP Act 2023).\n"
                "4. **SDLC Optimization:** Recommends the optimal delivery methodology (Agile/DevSecOps).\n"
                "5. **PDF Compilation:** Delivers the complete SRS document package with download link in this chat.\n\n"
                "💡 **How to proceed:**\n"
                "• **Instant Full Run:** Click **'Assume Standard Defaults'** below to use our verified Digital Banking & KYC baseline.\n"
                "• **Custom System:** Reply with your specific banking requirements (or answer the questions in the card below)."
            )
        }

    # Turn 2+: Answers Received -> Extract Requirements & Assumptions
    progress_messages.append("Extracting structured IEEE requirements and parsing business specifications...")
    
    uploaded_chunks = state.get("uploaded_chunks", [])
    uploaded_text = " ".join([c.get("content", "") for c in uploaded_chunks if isinstance(c, dict) and c.get("content")])
    
    # Expand default action selections into full statutory digital banking requirements
    user_text = user_input.strip()
    if any(phrase in user_text.lower() for phrase in [
        "assume standard defaults", "standard defaults", "default baseline", "assume defaults", "default kyc", "onboarding baseline"
    ]):
        effective_text = (
            "The system shall verify customer identity using UIDAI Aadhaar offline XML verification. "
            "The system shall validate customer PAN validity against NSDL database prior to activation. "
            "The system shall encrypt all customer KYC documents at rest using AES-256 field-level encryption. "
            "The system shall retain all audit logs and customer records for five years in accordance with PMLA 2002. "
            "The system shall perform biometric liveness detection and facial matching during video KYC onboarding. "
            "The system shall enforce role-based access control and multi-factor authentication for banking back-office personnel."
        )
    else:
        effective_text = f"{user_text}\n{uploaded_text}".strip()

    extracted_objs = requirement_engineer_agent.extract_requirements_from_text(
        text=effective_text,
        source_statement_id=f"msg#{state.get('chat_id', 'chat')[:8]}",
        project_id=state.get("project_id", "default_proj")
    )
    req_dicts = [r.model_dump(mode="json") for r in extracted_objs]

    # Extract default assumptions
    assumptions_objs = requirement_engineer_agent.extract_assumptions(effective_text, state.get("project_id", "default_proj"))
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
        "response_text": f"Successfully extracted and baselined {len(req_dicts)} structured requirements from your plan."
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

    sdlc_expl = sdlc_recommendation.get("explanation", "")
    selected_model_name = sdlc_recommendation.get("selected_model", "Agile + DevSecOps Hybrid")
    
    cat_summary = {}
    for r in result['active_requirements']:
        cat = r.get("category", "Functional") if isinstance(r, dict) else getattr(r, "category", "Functional")
        cat_summary[cat] = cat_summary.get(cat, 0) + 1
    cat_line = ", ".join([f"{k}: {v}" for k, v in cat_summary.items()]) if cat_summary else "Functional & Compliance"

    full_response = (
        f"### ✅ Requirements Engineered & Baselined (Processing Complete)\n\n"
        f"Successfully synthesized **{len(result['active_requirements'])} structured specifications** ({cat_line}) "
        f"with **{int(result['coverage_score'] * 100)}% RTM Traceability Coverage**.\n\n"
        f"---\n"
        f"{sdlc_expl}\n\n"
        f"---\n"
        f"💡 **Interactive Change Options:**\n"
        f"• **Switch SDLC:** Reply e.g. *'change sdlc to waterfall'*, *'switch to agile'*, or click any alternative in the SDLC card below.\n"
        f"• **Edit Specifications:** Reply e.g. *'change requirement REQ-001 to...'*, or *'add requirement: daily limit ₹50,000'*.\n"
        f"• **Download Package:** Your official 23-Section IEEE 29148 SRS PDF is ready via the card below."
    )

    return {
        "phase": ConversationPhase.DONE.value,
        "action_cards": action_cards,
        "progress_messages": progress_messages,
        "response_text": full_response
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
