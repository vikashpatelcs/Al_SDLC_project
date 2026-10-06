"""
Unit and Integration Tests for Phase 10: Compliance + Security + Privacy + Risk Agent.
Verifies authoritative citation verification, escalation of unsupported claims, deterministic
rule gap detection, 5x5 risk scoring math, legal advisory disclaimer, and Coordinator DB persistence.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.db.session import Base
from backend.app.db.models import (
    Chat,
    Project,
    RequirementModel,
    ComplianceMappingModel,
    RiskModel,
    AgentExecutionModel,
)
from backend.app.agents.compliance_security_risk import (
    compliance_security_risk_agent,
    LEGAL_ADVISORY_DISCLAIMER,
)
from backend.app.agents.coordinator import CoordinatorAgent
from backend.app.graph.checkpointer import SqliteCheckpointer
from backend.app.schemas.message import ActionCardType
from backend.app.schemas.risk import RiskItem, RiskCategory, RiskSeverity


@pytest.fixture
def db_session(tmp_path):
    """Isolated in-memory/temp SQLite database for Phase 10 testing."""
    db_file = tmp_path / "test_phase10.db"
    engine = create_engine(f"sqlite:///{db_file}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_mappings_carry_verified_citations():
    """Verify that requirements matched against authoritative KB carry verified statutory citations."""
    sample_reqs = [
        {
            "id": "REQ-ONB-001",
            "statement": "The system shall perform customer biometric Aadhaar verification and PAN validation for digital KYC onboarding.",
            "category": "Regulatory"
        }
    ]

    result = compliance_security_risk_agent.analyze_compliance_and_risk(
        requirements=sample_reqs,
        project_id="proj-test-10"
    )

    mappings = result["compliance_mappings"]
    assert len(mappings) > 0

    verified_mappings = [m for m in mappings if m["citation_verified"] and m["compliance_status"] == "compliant"]
    assert len(verified_mappings) > 0

    first_verified = verified_mappings[0]
    assert first_verified["citation_doc_id"] in ["DOC-RBI-KYC-2016", "DOC-GOI-DPDP-2023", "DOC-GOI-PMLA-2002"]
    assert first_verified["escalation_flag"] is False
    assert first_verified["compliance_status"] == "compliant"


def test_unsupported_citation_escalated():
    """Verify that fabricated or ungrounded regulatory claims are escalated and flagged needs_review."""
    fake_citation = "RBI Master Direction NonExistentCircular/2099/FAKE Section 99"

    escalated = compliance_security_risk_agent.verify_and_escalate_mapping(
        citation_text=fake_citation,
        project_id="proj-fake",
        requirement_id="REQ-FAKE-001",
        claimed_regulation="Imaginary Circular 2099"
    )

    assert escalated["citation_verified"] is False
    assert escalated["escalation_flag"] is True
    assert escalated["compliance_status"] == "needs_review"
    assert "requires compliance review" in escalated["escalation_reason"]


def test_rule_based_compliance_gaps_detected():
    """Verify deterministic compliance rules trigger gaps when mandatory conditions (consent/retention) are omitted."""
    # Storing personal data indefinitely without consent or retention limit
    bad_req = [
        {
            "id": "REQ-BAD-001",
            "statement": "The application shall store customer Aadhaar, PAN, and personal data in an unencrypted table without retention limits.",
            "category": "Data-management"
        }
    ]

    result = compliance_security_risk_agent.analyze_compliance_and_risk(
        requirements=bad_req,
        project_id="proj-gap-test"
    )

    gaps = [m for m in result["compliance_mappings"] if m["compliance_status"] == "gap"]
    assert len(gaps) >= 1

    gap_titles = [g["regulation_name"] for g in gaps]
    assert any("Digital Personal Data Protection" in title for title in gap_titles)

    gap_record = gaps[0]
    assert gap_record["escalation_flag"] is True
    assert gap_record["gap_description"] is not None


def test_cvv_storage_prohibition_rule_fires():
    """Verify prohibited card credentials storage rule triggers an explicit compliance gap and critical risk."""
    card_req = [
        {
            "id": "REQ-CRD-001",
            "statement": "The checkout system shall persist customer credit card numbers and save CVV post-authorization for fast one-click checkout.",
            "category": "Security"
        }
    ]

    result = compliance_security_risk_agent.analyze_compliance_and_risk(
        requirements=card_req,
        project_id="proj-cvv-test"
    )

    gaps = [m for m in result["compliance_mappings"] if m["compliance_status"] == "gap"]
    assert any("Credit Card" in g["regulation_name"] for g in gaps)

    # Risk item generated for the prohibited pattern
    risks = result["risks"]
    assert any("CVV" in r["title"] or "Card" in r["title"] for r in risks)
    cvv_risk = next(r for r in risks if "CVV" in r["title"] or "Card" in r["title"])
    assert cvv_risk["impact"] == 5
    assert cvv_risk["risk_score"] >= 10


def test_risk_register_fields_and_5x5_scoring():
    """Verify 5x5 Risk Register calculations and schema conformance."""
    sample_reqs = [
        {
            "id": "REQ-TXN-001",
            "statement": "The system shall execute real-time fund transfers without two-factor step-up authentication.",
            "category": "Functional"
        }
    ]

    result = compliance_security_risk_agent.analyze_compliance_and_risk(
        requirements=sample_reqs,
        project_id="proj-risk-math"
    )

    risks = result["risks"]
    assert len(risks) > 0

    for r in risks:
        # Check required fields
        assert "id" in r
        assert "category" in r
        assert "probability" in r
        assert "impact" in r
        assert "risk_score" in r
        assert "severity" in r
        assert "mitigation" in r
        assert "owner" in r
        assert "status" in r

        # Check 5x5 math
        p = r["probability"]
        i = r["impact"]
        score = r["risk_score"]
        assert 1 <= p <= 5
        assert 1 <= i <= 5
        assert score == p * i
        assert 1 <= score <= 25

        # Check severity classification consistency
        sev = r["severity"]
        if score >= 16:
            assert sev == RiskSeverity.CRITICAL.value
        elif score >= 10:
            assert sev == RiskSeverity.HIGH.value
        elif score >= 5:
            assert sev == RiskSeverity.MEDIUM.value
        else:
            assert sev == RiskSeverity.LOW.value


def test_disclaimer_present_in_output():
    """Verify that the mandatory legal advisory disclaimer is included in outputs and action cards."""
    result = compliance_security_risk_agent.analyze_compliance_and_risk(
        requirements=[{"id": "REQ-001", "statement": "User login with password.", "category": "Functional"}],
        project_id="proj-disc"
    )

    # In top-level agent result
    assert "not constitute a final legal determination" in result["disclaimer"]

    # In action cards
    cards = result["action_cards"]
    assert len(cards) == 2

    comp_card = next(c for c in cards if c["card_type"] == ActionCardType.COMPLIANCE_CARD.value)
    risk_card = next(c for c in cards if c["card_type"] == ActionCardType.RISK_CARD.value)

    assert "not constitute a final legal determination" in comp_card["payload"]["disclaimer"]
    assert "not constitute a final legal determination" in risk_card["payload"]["disclaimer"]


def test_gold_control_coverage():
    """Evaluate compliance and risk coverage on gold onboarding scenario."""
    gold_reqs = [
        {
            "id": "REQ-GLD-001",
            "statement": "The system shall perform UIDAI Aadhaar verification with explicit customer consent.",
            "category": "Regulatory"
        },
        {
            "id": "REQ-GLD-002",
            "statement": "The system shall encrypt customer records using AES-256 and store keys in HSM.",
            "category": "Security"
        },
        {
            "id": "REQ-GLD-003",
            "statement": "The system shall maintain an immutable audit log for 5 years per PMLA regulations.",
            "category": "Auditability"
        }
    ]

    result = compliance_security_risk_agent.analyze_compliance_and_risk(
        requirements=gold_reqs,
        project_id="proj-gold-coverage"
    )

    mappings = result["compliance_mappings"]
    verified = [m for m in mappings if m["citation_verified"]]
    assert len(verified) >= 3

    covered_regulations = {m["regulation_name"] for m in verified}
    assert any("KYC" in r or "Data Protection" in r or "Money-Laundering" in r for r in covered_regulations)


def test_coordinator_persists_compliance_and_risks(db_session, tmp_path):
    """Verify coordinator writes compliance mappings and risk items to DB tables during workflow execution."""
    # Seed Chat and Project in SQLite
    chat = Chat(id="chat-phase10-e2e", owner_token_hash="tok123", title="Phase 10 E2E")
    db_session.add(chat)
    db_session.commit()

    project = Project(id="proj-phase10-e2e", chat_id=chat.id, title="E2E Project", domain="digital_onboarding")
    db_session.add(project)
    db_session.commit()

    checkpointer = SqliteCheckpointer(db_path=str(tmp_path / "coordinator_p10.db"))
    coordinator = CoordinatorAgent(checkpointer=checkpointer)

    # Turn 1: Concept intake -> Question groups
    res_turn1 = coordinator.run_workflow(
        db=db_session,
        chat=chat,
        user_text="We need to build a digital KYC onboarding system.",
        auto_approve=True
    )
    assert len(res_turn1["action_cards"]) >= 1

    # Turn 2: Answers -> Extracts requirements, runs analysis, and enriches with compliance + risk
    user_answers = (
        "We require customer UIDAI Aadhaar verification, PAN check, AES-256 encryption, "
        "and statutory 5-year audit trail storage. Assume standard defaults."
    )
    result = coordinator.run_workflow(
        db=db_session,
        chat=chat,
        user_text=user_answers,
        auto_approve=True
    )

    # Verify coordinator returned compliance mappings and risks
    assert len(result["compliance_mappings"]) > 0
    assert len(result["risks"]) > 0

    # Verify rows in database
    db_mappings = db_session.query(ComplianceMappingModel).filter(
        ComplianceMappingModel.project_id == project.id
    ).all()
    assert len(db_mappings) > 0

    db_risks = db_session.query(RiskModel).filter(
        RiskModel.project_id == project.id
    ).all()
    assert len(db_risks) > 0

    # Verify foreign keys
    for m in db_mappings:
        assert m.project_id == project.id
        assert m.requirement_id is not None
    for r in db_risks:
        assert r.project_id == project.id
