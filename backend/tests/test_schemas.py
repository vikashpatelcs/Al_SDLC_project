"""
Unit tests for Pydantic v2 core schemas (Phase 1).
Validates contracts, serialization, validation rules, and sample JSON objects.
"""
import pytest
from datetime import datetime
from pydantic import ValidationError

from backend.app.schemas import (
    Requirement,
    RequirementCategory,
    RequirementStatus,
    Priority,
    AcceptanceCriteria,
    RequirementIssue,
    IssueType,
    IssueSeverity,
    IssueStatus,
    ApprovalRequest,
    ApprovalDecision,
    GateType,
    ApprovalAction,
    ActingRole,
    ApprovalStatus,
    RiskItem,
    RiskCategory,
    RiskSeverity,
    RiskStatus,
    SDLCRecommendation,
    SDLCFactor,
    SDLCModelType,
    SDLCPhaseWorkflow,
    ModelScoreRanking,
    AgentMessage,
    ActionCard,
    ActionCardType,
    MessageRole,
    AgentSender,
    SlotItem,
    InterviewTemplate,
    TopicGroup,
)


def test_requirement_valid_sample():
    """Verify that a canonical financial requirement instance validates cleanly."""
    ac = AcceptanceCriteria(
        id="AC-001",
        given="Customer has completed mobile OTP verification",
        when="Customer submits Aadhaar number and biometric / OTP consent",
        then="The system shall initiate offline XML verification with UIDAI within 3 seconds"
    )
    req = Requirement(
        id="FR-ONB-001",
        project_id="proj-123",
        statement="The system shall verify customer Aadhaar identity via UIDAI offline XML verification.",
        category=RequirementCategory.COMPLIANCE,
        sub_category="KYC Verification",
        priority=Priority.HIGH,
        version=1,
        status=RequirementStatus.DRAFT,
        source_statement_id="SRC-CHAT-MSG-003",
        business_justification="Mandated by RBI Master Direction on KYC (Section 16)",
        dependencies=["FR-ONB-000"],
        acceptance_criteria=[ac],
        evidence_ids=["CHUNK-RBI-KYC-SEC16"],
        kb_version="1.0.0",
        model_version="qwen2.5:3b"
    )

    data = req.model_dump()
    assert data["id"] == "FR-ONB-001"
    assert data["category"] == "Compliance"
    assert data["priority"] == "High"
    assert len(data["acceptance_criteria"]) == 1
    assert data["acceptance_criteria"][0]["id"] == "AC-001"
    assert data["kb_version"] == "1.0.0"

    # Verify JSON round-trip
    json_str = req.model_dump_json()
    req_restored = Requirement.model_validate_json(json_str)
    assert req_restored.id == req.id
    assert req_restored.statement == req.statement


def test_requirement_invalid_category_raises():
    """Verify that invalid requirement category is rejected."""
    with pytest.raises(ValidationError):
        Requirement(
            id="FR-001",
            statement="Test statement",
            category="NonExistentCategory",
            priority=Priority.LOW
        )


def test_issue_schema():
    """Verify requirement issue tracking schema."""
    issue = RequirementIssue(
        id="ISS-001",
        requirement_id="FR-ONB-001",
        issue_type=IssueType.AMBIGUITY,
        severity=IssueSeverity.HIGH,
        detail="Phrase 'instantly' is subjective and cannot be benchmarked.",
        suggestion="Replace 'instantly' with 'within 200 milliseconds under 95th percentile load'.",
        rationale="INCOSE requirement quality guidelines require verifiable quantitative metrics."
    )
    assert issue.issue_type == IssueType.AMBIGUITY
    assert issue.status == IssueStatus.OPEN


def test_approval_request_and_decision():
    """Verify 8 mandatory gates and 5 approval actions."""
    req = ApprovalRequest(
        id="APR-001",
        chat_id="chat-999",
        gate_type=GateType.BASELINE,
        subject_id="BASELINE-V1",
        title="Approve Requirement Baseline v1.0",
        description="Formal sign-off of initial 18 requirements.",
        required_role=ActingRole.PRODUCT_OWNER
    )
    assert req.gate_type == GateType.BASELINE
    assert req.status == ApprovalStatus.PENDING

    decision = ApprovalDecision(
        approval_id="APR-001",
        action=ApprovalAction.ACCEPT,
        acting_role=ActingRole.PRODUCT_OWNER,
        comment="Baseline reviewed and aligned with onboarding roadmap."
    )
    assert decision.action == ApprovalAction.ACCEPT
    assert decision.acting_role == ActingRole.PRODUCT_OWNER


def test_risk_score_and_severity_calculation():
    """Verify 5x5 probability x impact risk score calculation and severity tiering."""
    # Critical risk: 4 * 4 = 16 (>= 16 -> CRITICAL)
    crit_risk = RiskItem(
        id="RSK-001",
        title="Unauthorized Aadhaar Data Exposure",
        category=RiskCategory.SECURITY,
        probability=4,
        impact=4,
        mitigation="Field-level Fernet AES encryption with hardware security module."
    )
    assert crit_risk.risk_score == 16
    assert crit_risk.severity == RiskSeverity.CRITICAL

    # High risk: 3 * 4 = 12 (10-15 -> HIGH)
    high_risk = RiskItem(
        id="RSK-002",
        title="UIDAI API Outage during Peak Onboarding",
        category=RiskCategory.AVAILABILITY,
        probability=3,
        impact=4,
        mitigation="Asynchronous fallback queue and retry backoff."
    )
    assert high_risk.risk_score == 12
    assert high_risk.severity == RiskSeverity.HIGH

    # Low risk: 1 * 2 = 2 (< 5 -> LOW)
    low_risk = RiskItem(
        id="RSK-003",
        title="Minor UI button translation mismatch",
        category=RiskCategory.BUSINESS,
        probability=1,
        impact=2,
        mitigation="Localization lint checks in CI."
    )
    assert low_risk.risk_score == 2
    assert low_risk.severity == RiskSeverity.LOW


def test_risk_out_of_bounds_raises():
    """Verify probability and impact must be between 1 and 5."""
    with pytest.raises(ValidationError):
        RiskItem(
            id="RSK-ERR",
            title="Invalid",
            category=RiskCategory.SECURITY,
            probability=6,
            impact=3,
            mitigation="None"
        )


def test_sdlc_recommendation_and_workflow():
    """Verify SDLC model scoring, factors, and 10-dimension workflow."""
    factor = SDLCFactor(
        name="regulatory_criticality",
        score=5,
        evidence_quote="System conducts live banking KYC subject to PMLA 2002 penalties."
    )
    ranking = ModelScoreRanking(
        model_type=SDLCModelType.AGILE_V_MODEL,
        score_percentage=94.5,
        rank=1,
        key_strengths=["Formal V-Model verification for regulatory KYC", "Agile iteration on UI"],
        tradeoffs=["Requires dual documentation track"]
    )
    workflow_phase = SDLCPhaseWorkflow(
        phase_name="Regulatory Architecture & Threat Modeling",
        activity="Map requirements to RBI and DPDP statutory articles",
        role="Security Architect & Compliance Officer",
        deliverable="Threat Model and Regulatory Compliance Matrix",
        security_activity="STRIDE Threat modeling on PII ingress endpoints",
        testing="Control design review",
        compliance_checkpoint="RBI IT Direction Section 4 review",
        human_approval="Gate 2: Security & Compliance Sign-off",
        entry_criteria="Baseline requirements approved",
        exit_criteria="Zero unmitigated critical threats",
        traceability_requirement="Link every security req to a threat ID"
    )

    rec = SDLCRecommendation(
        chat_id="chat-123",
        selected_model=SDLCModelType.AGILE_V_MODEL,
        rankings=[ranking],
        factor_evaluations={"regulatory_criticality": factor},
        explanation="Agile + V-Model Hybrid is recommended due to critical regulatory oversight.",
        workflow=[workflow_phase]
    )

    assert rec.selected_model == SDLCModelType.AGILE_V_MODEL
    assert len(rec.rankings) == 1
    assert rec.factor_evaluations["regulatory_criticality"].score == 5
    assert len(rec.workflow) == 1
    assert rec.workflow[0].phase_name == "Regulatory Architecture & Threat Modeling"


def test_agent_message_and_action_card():
    """Verify AgentMessage with embedded ActionCard."""
    card = ActionCard(
        id="CARD-001",
        card_type=ActionCardType.QUESTION_GROUP,
        title="Clarification Questions: Onboarding Limits & Auth",
        payload={
            "topic": "Security and Encryption",
            "questions": ["What is the maximum daily transaction limit?"]
        },
        actions=["Submit Answers", "Assume Safe Defaults"]
    )
    msg = AgentMessage(
        id="MSG-001",
        chat_id="chat-001",
        role=MessageRole.ASSISTANT,
        sender_agent=AgentSender.REQUIREMENT_ENGINEER,
        content="I have analyzed your request and prepared clarification questions.",
        action_cards=[card]
    )

    assert msg.role == MessageRole.ASSISTANT
    assert msg.sender_agent == AgentSender.REQUIREMENT_ENGINEER
    assert len(msg.action_cards) == 1
    assert msg.action_cards[0].card_type == ActionCardType.QUESTION_GROUP


def test_slot_and_interview_template():
    """Verify SlotItem and InterviewTemplate schemas."""
    slot = SlotItem(
        name="data.retention_period",
        topic=TopicGroup.DATA,
        question_text="What is the mandatory data retention duration for KYC records?",
        required=True
    )
    assert slot.filled is False
    assert slot.name == "data.retention_period"

    template = InterviewTemplate(
        role_name="Compliance Officer",
        description="Interview targeting statutory mandates and audit trails",
        priority_topics=[TopicGroup.COMPLIANCE, TopicGroup.DATA, TopicGroup.RISK],
        recommended_slots=["data.retention_period", "compliance.pmla_reporting"]
    )
    assert template.role_name == "Compliance Officer"
    assert TopicGroup.COMPLIANCE in template.priority_topics
