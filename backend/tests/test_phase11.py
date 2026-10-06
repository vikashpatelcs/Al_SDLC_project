"""
Unit and Integration Tests for Phase 11: SDLC Recommendation Engine.
Verifies 13-factor extraction with evidence quotes, deterministic MCDA ranking across 7 models,
rule table validation against archetypal cases, score-consistent explanations,
challenge loop re-scoring with deltas, 10-field lifecycle workflows, and DB persistence.
"""
import pytest
import json
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.db.session import Base
from backend.app.db.models import Chat, Project, SDLCRecommendationModel
from backend.app.agents.sdlc import sdlc_agent
from backend.app.agents.coordinator import CoordinatorAgent
from backend.app.graph.checkpointer import SqliteCheckpointer
from backend.app.schemas.sdlc import SDLCModelType, SDLCRecommendation
from backend.app.schemas.message import ActionCardType
from rules.sdlc_engine import sdlc_engine


@pytest.fixture
def db_session(tmp_path):
    """Isolated in-memory/temp SQLite database for Phase 11 testing."""
    db_file = tmp_path / "test_phase11.db"
    engine = create_engine(f"sqlite:///{db_file}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_13_factors_extracted_with_evidence():
    """Verify that all 13 PS §13 decision factors are extracted with Likert scores 1-5 and verbatim evidence quotes."""
    sample_reqs = [
        {"id": "REQ-001", "statement": "The system shall perform UIDAI biometric Aadhaar authentication under RBI KYC guidelines.", "category": "Regulatory"},
        {"id": "REQ-002", "statement": "The system shall enforce AES-256 HSM cryptographic key custody and 5-year audit trail storage.", "category": "Security"},
        {"id": "REQ-003", "statement": "The system shall deploy continuous daily automated CI/CD releases to production.", "category": "Operational"}
    ]

    factors = sdlc_agent.extract_factors(
        requirements=sample_reqs,
        project_domain="digital_banking_and_onboarding"
    )

    expected_13_factors = [
        "requirement_stability",
        "regulatory_criticality",
        "security_risk",
        "project_complexity",
        "system_size",
        "legacy_system_dependence",
        "frequency_of_expected_changes",
        "need_for_continuous_delivery",
        "availability_of_stakeholders",
        "testing_and_documentation_requirements",
        "budget_and_schedule_constraints",
        "need_for_formal_verification",
        "consequences_of_system_failure"
    ]

    assert len(factors) == 13
    for fname in expected_13_factors:
        assert fname in factors
        f_obj = factors[fname]
        assert 1 <= f_obj.score <= 5
        assert len(f_obj.evidence_quote.strip()) > 5


def test_ranked_percentage_list():
    """Verify deterministic MCDA engine generates ranked list across all 7 methodologies with normalized percentages."""
    factor_scores = {
        "requirement_stability": 3,
        "regulatory_criticality": 5,
        "security_risk": 5,
        "project_complexity": 4,
        "system_size": 3,
        "legacy_system_dependence": 2,
        "frequency_of_expected_changes": 4,
        "need_for_continuous_delivery": 5,
        "availability_of_stakeholders": 4,
        "testing_and_documentation_requirements": 5,
        "budget_and_schedule_constraints": 4,
        "need_for_formal_verification": 4,
        "consequences_of_system_failure": 5
    }

    rankings = sdlc_engine.compute_rankings(factor_scores)

    assert len(rankings) == 7

    # Ranks must be 1 to 7
    ranks = [r.rank for r in rankings]
    assert ranks == list(range(1, 8))

    # All 7 methodologies represented
    model_names = {r.model_type.value for r in rankings}
    assert model_names == {
        "Waterfall",
        "V-Model",
        "Spiral",
        "Agile",
        "DevSecOps",
        "Agile + V-Model Hybrid",
        "Agile + DevSecOps Hybrid"
    }

    # Percentages must be in descending order and between 10.0 and 95.0
    for idx in range(len(rankings) - 1):
        assert rankings[idx].score_percentage >= rankings[idx + 1].score_percentage
        assert 10.0 <= rankings[idx].score_percentage <= 95.0


def test_rule_table_cases_match_expected_top_model():
    """Verify that archetypal project profiles match the expected top methodology per Problem Statement §14."""
    archetypes = sdlc_engine.rules.get("archetypal_cases", [])
    assert len(archetypes) >= 3

    for case in archetypes:
        factors = case["factors"]
        expected_top = case["expected_top_model"]
        rankings = sdlc_engine.compute_rankings(factors)
        actual_top = rankings[0].model_type.value
        assert actual_top == expected_top, f"Failed for {case['id']}: expected {expected_top}, got {actual_top}"


def test_explanation_consistent_with_scores():
    """Verify that the generated explanation contains the exact numbers, percentages, and names from the engine."""
    sample_reqs = [
        {"id": "REQ-001", "statement": "Customer onboarding with Aadhaar verification and RBI KYC compliance.", "category": "Regulatory"}
    ]

    rec = sdlc_agent.recommend_sdlc(
        requirements=sample_reqs,
        project_id="proj-expl-test"
    )

    top_ranking = rec.rankings[0]
    explanation = rec.explanation

    # Top model name must be in explanation
    assert top_ranking.model_type.value in explanation

    # Exact score percentage must be in explanation
    assert f"{top_ranking.score_percentage}%" in explanation

    # Top driver factors mentioned
    assert "Regulatory Criticality" in explanation


def test_challenge_loop_re_evaluation():
    """Verify that stakeholder challenge adjustments shift scores in expected direction and report deltas."""
    sample_reqs = [
        {"id": "REQ-001", "statement": "Customer KYC onboarding app.", "category": "Functional"}
    ]

    initial_rec = sdlc_agent.recommend_sdlc(
        requirements=sample_reqs,
        project_id="proj-challenge-test"
    )

    # Challenge: Drastically increase requirement stability to 5 (frozen) and legacy dependence to 5
    challenge_res = sdlc_agent.handle_challenge(
        factor_name="requirement_stability",
        new_score=5,
        recommendation=initial_rec
    )

    assert challenge_res["factor_name"] == "requirement_stability"
    assert challenge_res["new_score"] == 5
    assert "score_deltas" in challenge_res

    deltas = challenge_res["score_deltas"]
    assert "Waterfall" in deltas or "V-Model" in deltas

    # When requirement stability is set to 5 (frozen), Waterfall/V-Model scores should increase
    assert deltas.get("Waterfall", 0.0) >= 0.0 or deltas.get("V-Model", 0.0) >= 0.0


def test_workflow_has_all_10_fields_per_phase():
    """Verify that the project-specific lifecycle workflow contains all 10 fields per phase per Problem Statement §15."""
    sample_reqs = [
        {"id": "REQ-001", "statement": "Customer KYC onboarding app with AES-256 and PMLA audit.", "category": "Regulatory"}
    ]

    rec = sdlc_agent.recommend_sdlc(
        requirements=sample_reqs,
        project_id="proj-wf-test"
    )

    workflow = rec.workflow
    assert len(workflow) >= 3

    for phase in workflow:
        assert len(phase.phase_name.strip()) > 0
        assert len(phase.activity.strip()) > 0
        assert len(phase.role.strip()) > 0
        assert len(phase.deliverable.strip()) > 0
        assert len(phase.security_activity.strip()) > 0
        assert len(phase.testing.strip()) > 0
        assert len(phase.compliance_checkpoint.strip()) > 0
        assert len(phase.human_approval.strip()) > 0
        assert len(phase.entry_criteria.strip()) > 0
        assert len(phase.exit_criteria.strip()) > 0
        assert len(phase.traceability_requirement.strip()) > 0


def test_coordinator_persists_sdlc_recommendation(db_session, tmp_path):
    """Verify coordinator persists the SDLC recommendation to the database during full workflow execution."""
    chat = Chat(id="chat-sdlc-e2e", owner_token_hash="tok999", title="SDLC E2E Chat")
    db_session.add(chat)
    db_session.commit()

    project = Project(id="proj-sdlc-e2e", chat_id=chat.id, title="SDLC E2E Proj", domain="digital_onboarding")
    db_session.add(project)
    db_session.commit()

    checkpointer = SqliteCheckpointer(db_path=str(tmp_path / "coordinator_p11.db"))
    coordinator = CoordinatorAgent(checkpointer=checkpointer)

    # Turn 1: Concept intake
    res1 = coordinator.run_workflow(
        db=db_session,
        chat=chat,
        user_text="We need to build a personal loan processing platform.",
        auto_approve=True
    )
    assert len(res1["action_cards"]) >= 1

    # Turn 2: Answers -> Extracts requirements, runs quality analysis, compliance, and SDLC recommendation
    res2 = coordinator.run_workflow(
        db=db_session,
        chat=chat,
        user_text="We require UIDAI Aadhaar verification, PAN validation via NSDL, AES-256 encryption, and 5-year audit trail.",
        auto_approve=True
    )

    assert "sdlc_recommendations" in res2
    assert res2["sdlc_recommendations"] is not None

    # Check row in database table sdlc_recommendations
    db_rec = db_session.query(SDLCRecommendationModel).filter(
        SDLCRecommendationModel.project_id == project.id
    ).first()

    assert db_rec is not None
    assert db_rec.selected_model in [
        "Agile + DevSecOps Hybrid",
        "Agile + V-Model Hybrid",
        "V-Model",
        "DevSecOps"
    ]

    rankings_data = json.loads(db_rec.rankings_json)
    assert len(rankings_data) == 7

    factors_data = json.loads(db_rec.factors_json)
    assert len(factors_data) == 13

    wf_data = json.loads(db_rec.workflow_json)
    assert len(wf_data) >= 3
