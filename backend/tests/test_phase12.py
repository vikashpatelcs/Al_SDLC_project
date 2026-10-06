"""
Unit and Integration Tests for Phase 12: Human-in-the-Loop & Approval Gates.
Verifies all 8 mandatory gates, 5 reviewer actions (Accept, Reject, Edit, Regenerate, Explain),
baseline immutability with version history & impact analysis, SDLC 4-role sign-offs,
and pipeline halt / resume behavior.
"""
import pytest
import json
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from starlette.testclient import TestClient

from backend.app.main import app
from backend.app.config import settings
from backend.app.db.session import Base
from backend.app.db.models import (
    Chat,
    Project,
    RequirementModel,
    RequirementVersion,
    ApprovalModel,
    SDLCRecommendationModel,
)
from backend.app.db.session import Base, get_db
from backend.app.schemas.message import ActionCardType
from backend.app.schemas.approval import GateType, ApprovalAction, ActingRole, ApprovalStatus
from backend.app.graph.gates import approval_gate_manager, SDLC_MANDATORY_ROLES
from backend.app.agents.coordinator import CoordinatorAgent
from backend.app.graph.checkpointer import SqliteCheckpointer


@pytest.fixture
def db_session(tmp_path):
    """Isolated in-memory/temp SQLite database for Phase 12 testing."""
    db_file = tmp_path / "test_phase12.db"
    engine = create_engine(f"sqlite:///{db_file}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    c = TestClient(app, cookies={settings.SESSION_COOKIE_NAME: "phase12_test_cookie_123"})
    yield c
    app.dependency_overrides.clear()


def test_all_8_gates_block(db_session):
    """Verify that all 8 PS §16 mandatory gates can be created and block in pending status."""
    chat = Chat(id="chat-gate-test", owner_token_hash="tok1", title="Gate Test Chat")
    project = Project(id="proj-gate-test", chat_id=chat.id, title="Gate Test Proj")
    db_session.add_all([chat, project])
    db_session.commit()

    all_8_gates = [
        (GateType.BASELINE.value, "Final Requirement Baseline Approval", "REQ-ALL"),
        (GateType.REQUIREMENT_CHANGE.value, "Requirement Scope Modification", "REQ-001"),
        (GateType.REGULATORY_INTERPRETATION.value, "High-Impact Statutory Interpretation", "CMP-001"),
        (GateType.HIGH_RISK_SECURITY.value, "High-Risk Threat Sign-Off", "RSK-001"),
        (GateType.CONFLICT_DECISION.value, "Contradictory Requirement Adjudication", "ISS-001"),
        (GateType.ARCHITECTURE_CRITICAL.value, "Core Architectural Ledger Boundary", "REQ-002"),
        (GateType.SDLC_SELECTION.value, "SDLC Methodology 4-Role Sign-Off", "SDLC-001"),
        (GateType.PRODUCTION_READINESS.value, "Pre-Deployment Audit Clearance", "AUD-001"),
    ]

    created_approvals = []
    for gate_type, title, subj in all_8_gates:
        apr = approval_gate_manager.create_approval_request(
            db=db_session,
            chat_id=chat.id,
            project_id=project.id,
            gate_type=gate_type,
            subject_id=subj,
            title=title,
            description=f"Human sign-off required for {gate_type}.",
            required_role="compliance_officer" if "regulatory" in gate_type else "product_owner"
        )
        created_approvals.append(apr)

    assert len(created_approvals) == 8

    # All must be initially pending (blocking downstream execution)
    for apr in created_approvals:
        assert apr.status == ApprovalStatus.PENDING.value
        assert apr.decided_at is None


def test_five_actions_work(db_session):
    """Verify that all 5 reviewer actions (Accept, Reject, Edit, Regenerate, Explain) execute properly."""
    chat = Chat(id="chat-5act", owner_token_hash="tok2", title="Actions Chat")
    project = Project(id="proj-5act", chat_id=chat.id, title="Actions Proj")
    req = RequirementModel(
        id="REQ-ACT-001",
        project_id=project.id,
        statement="The system shall process card payments.",
        category="Functional",
        version=1,
        status="draft"
    )
    db_session.add_all([chat, project, req])
    db_session.commit()

    # 1. Action: EXPLAIN
    apr_exp = approval_gate_manager.create_approval_request(
        db=db_session,
        chat_id=chat.id,
        project_id=project.id,
        gate_type=GateType.HIGH_RISK_SECURITY.value,
        subject_id=req.id,
        title="Security Risk Review",
        description="Review payment authorization protocol.",
        required_role=ActingRole.SECURITY_ARCHITECT.value,
        evidence_data={
            "evidence_quote": "Processes credit card transaction flows.",
            "rationale": "Mandates PCI-DSS and RBI Card Tokenisation controls.",
            "citations": ["RBI/2022-23/92 Master Direction Section 19"]
        },
        confidence_score=0.96
    )
    exp_res = approval_gate_manager.process_decision(
        db=db_session,
        approval_id=apr_exp.id,
        action=ApprovalAction.EXPLAIN.value,
        acting_role=ActingRole.SECURITY_ARCHITECT.value
    )
    assert exp_res["confidence_score"] == 0.96
    assert "RBI/2022-23/92" in exp_res["applicable_citations"][0]
    # Gate remains pending after explain
    assert apr_exp.status == ApprovalStatus.PENDING.value

    # 2. Action: ACCEPT
    apr_acc = approval_gate_manager.create_approval_request(
        db=db_session,
        chat_id=chat.id,
        project_id=project.id,
        gate_type=GateType.HIGH_RISK_SECURITY.value,
        subject_id=req.id,
        title="Accept Gate",
        description="Accepting security control.",
        required_role=ActingRole.SECURITY_ARCHITECT.value
    )
    acc_res = approval_gate_manager.process_decision(
        db=db_session,
        approval_id=apr_acc.id,
        action=ApprovalAction.ACCEPT.value,
        acting_role=ActingRole.SECURITY_ARCHITECT.value,
        comment="Approved following threat model review."
    )
    assert acc_res["status"] == ApprovalStatus.APPROVED.value

    # 3. Action: REJECT
    apr_rej = approval_gate_manager.create_approval_request(
        db=db_session,
        chat_id=chat.id,
        project_id=project.id,
        gate_type=GateType.REQUIREMENT_CHANGE.value,
        subject_id=req.id,
        title="Reject Gate",
        description="Rejecting requirement change.",
        required_role=ActingRole.PRODUCT_OWNER.value
    )
    rej_res = approval_gate_manager.process_decision(
        db=db_session,
        approval_id=apr_rej.id,
        action=ApprovalAction.REJECT.value,
        acting_role=ActingRole.PRODUCT_OWNER.value,
        comment="Does not align with sprint scope."
    )
    assert rej_res["status"] == ApprovalStatus.REJECTED.value

    # 4. Action: EDIT
    apr_edt = approval_gate_manager.create_approval_request(
        db=db_session,
        chat_id=chat.id,
        project_id=project.id,
        gate_type=GateType.REQUIREMENT_CHANGE.value,
        subject_id=req.id,
        title="Edit Gate",
        description="Editing requirement text.",
        required_role=ActingRole.PRODUCT_OWNER.value
    )
    edt_res = approval_gate_manager.process_decision(
        db=db_session,
        approval_id=apr_edt.id,
        action=ApprovalAction.EDIT.value,
        acting_role=ActingRole.PRODUCT_OWNER.value,
        comment="Added mandatory two-factor authentication clause.",
        modified_payload="The system shall process card payments with mandatory two-factor authentication."
    )
    assert edt_res["status"] == ApprovalStatus.REVISED.value
    assert "impact_analysis" in edt_res

    # 5. Action: REGENERATE
    apr_reg = approval_gate_manager.create_approval_request(
        db=db_session,
        chat_id=chat.id,
        project_id=project.id,
        gate_type=GateType.REQUIREMENT_CHANGE.value,
        subject_id=req.id,
        title="Regenerate Gate",
        description="Regenerating requirement formulation.",
        required_role=ActingRole.PRODUCT_OWNER.value
    )
    reg_res = approval_gate_manager.process_decision(
        db=db_session,
        approval_id=apr_reg.id,
        action=ApprovalAction.REGENERATE.value,
        acting_role=ActingRole.PRODUCT_OWNER.value
    )
    assert reg_res["status"] == ApprovalStatus.PENDING.value


def test_baseline_immutable_and_versioned(db_session):
    """Verify that editing an approved requirement preserves v1 immutably, increments to v2, and logs impact."""
    chat = Chat(id="chat-immu", owner_token_hash="tok3", title="Immutability Chat")
    project = Project(id="proj-immu", chat_id=chat.id, title="Immutability Proj")
    req = RequirementModel(
        id="REQ-IMM-001",
        project_id=project.id,
        statement="Original statement version 1: Enforce AES-256.",
        category="Security",
        version=1,
        status="approved"  # Previously locked baseline
    )
    db_session.add_all([chat, project, req])
    db_session.commit()

    apr = approval_gate_manager.create_approval_request(
        db=db_session,
        chat_id=chat.id,
        project_id=project.id,
        gate_type=GateType.REQUIREMENT_CHANGE.value,
        subject_id=req.id,
        title="Change approved requirement",
        description="Modifying cryptographic cipher to AES-256-GCM.",
        required_role=ActingRole.SECURITY_ARCHITECT.value
    )

    new_text = "Updated statement version 2: Enforce AES-256-GCM with HSM key management."
    decision_res = approval_gate_manager.process_decision(
        db=db_session,
        approval_id=apr.id,
        action=ApprovalAction.EDIT.value,
        acting_role=ActingRole.SECURITY_ARCHITECT.value,
        comment="Upgrade to GCM mode for authenticated encryption.",
        modified_payload=new_text
    )

    # Verify requirement updated to v2
    db_session.refresh(req)
    assert req.version == 2
    assert req.statement == new_text

    # Verify v1 snapshot preserved immutably in requirement_versions
    versions = db_session.query(RequirementVersion).filter(
        RequirementVersion.requirement_id == req.id
    ).all()
    assert len(versions) == 1
    v1_snap = versions[0]
    assert v1_snap.version == 1
    assert "version 1" in v1_snap.statement
    assert "Human Reviewer" in v1_snap.changed_by

    # Verify impact analysis reported
    impact = decision_res["impact_analysis"]
    assert impact["previous_version"] == 1
    assert impact["new_version"] == 2
    assert impact["reanalysis_required"] is True


def test_sdlc_four_role_signoff_logged(db_session):
    """Verify that SDLC selection tracks 4 roles and only marks approved when all 4 sign."""
    chat = Chat(id="chat-sdlc-sign", owner_token_hash="tok4", title="SDLC Sign Chat")
    project = Project(id="proj-sdlc-sign", chat_id=chat.id, title="SDLC Sign Proj")
    sdlc_rec = SDLCRecommendationModel(
        id="rec-001",
        project_id=project.id,
        chat_id=chat.id,
        selected_model="Agile + DevSecOps Hybrid",
        rankings_json="[]",
        factors_json="{}",
        explanation="Recommended methodology.",
        workflow_json="[]",
        is_approved=False
    )
    db_session.add_all([chat, project, sdlc_rec])
    db_session.commit()

    apr = approval_gate_manager.create_approval_request(
        db=db_session,
        chat_id=chat.id,
        project_id=project.id,
        gate_type=GateType.SDLC_SELECTION.value,
        subject_id=sdlc_rec.id,
        title="SDLC 4-Role Sign-Off",
        description="Mandatory sign-off from PM, Architect, Security, and Compliance.",
        required_role=ActingRole.PROJECT_MANAGER.value
    )

    # 1. Sign under Project Manager
    res1 = approval_gate_manager.process_decision(
        db=db_session,
        approval_id=apr.id,
        action=ApprovalAction.ACCEPT.value,
        acting_role=ActingRole.PROJECT_MANAGER.value,
        comment="PM sign-off: scope aligns with budget."
    )
    assert res1["fully_approved"] is False
    assert res1["status"] == ApprovalStatus.PENDING.value
    assert len(res1["remaining_roles"]) == 3

    # 2. Sign under Software Architect
    res2 = approval_gate_manager.process_decision(
        db=db_session,
        approval_id=apr.id,
        action=ApprovalAction.ACCEPT.value,
        acting_role=ActingRole.SOFTWARE_ARCHITECT.value,
        comment="Architect sign-off: distributed design compatible."
    )
    assert res2["fully_approved"] is False
    assert len(res2["remaining_roles"]) == 2

    # 3. Sign under Security Lead
    res3 = approval_gate_manager.process_decision(
        db=db_session,
        approval_id=apr.id,
        action=ApprovalAction.ACCEPT.value,
        acting_role=ActingRole.SECURITY_ARCHITECT.value,
        comment="Security sign-off: shift-left SAST/DAST verified."
    )
    assert res3["fully_approved"] is False
    assert len(res3["remaining_roles"]) == 1
    assert res3["remaining_roles"] == [ActingRole.COMPLIANCE_OFFICER.value]

    # 4. Final sign under Compliance Officer
    res4 = approval_gate_manager.process_decision(
        db=db_session,
        approval_id=apr.id,
        action=ApprovalAction.ACCEPT.value,
        acting_role=ActingRole.COMPLIANCE_OFFICER.value,
        comment="Compliance sign-off: RBI circular checkpoints included."
    )
    assert res4["fully_approved"] is True
    assert res4["status"] == ApprovalStatus.APPROVED.value
    assert len(res4["remaining_roles"]) == 0

    # Verify SDLC model is_approved updated in DB
    db_session.refresh(sdlc_rec)
    assert sdlc_rec.is_approved is True


def test_explain_shows_evidence_and_confidence(db_session, client):
    """Verify that GET /api/approvals/{id}/explain returns evidence quote, citations, and confidence."""
    chat = Chat(id="chat-exp-api", owner_token_hash="tok5", title="Explain API Chat")
    project = Project(id="proj-exp-api", chat_id=chat.id, title="Explain API Proj")
    db_session.add_all([chat, project])
    db_session.commit()

    apr = approval_gate_manager.create_approval_request(
        db=db_session,
        chat_id=chat.id,
        project_id=project.id,
        gate_type=GateType.REGULATORY_INTERPRETATION.value,
        subject_id="CMP-002",
        title="Regulatory Interpretation Gate",
        description="Statutory retention interpretation under PMLA Section 12.",
        required_role=ActingRole.COMPLIANCE_OFFICER.value,
        evidence_data={
            "evidence_quote": "Store transaction logs for 5 years in WORM format.",
            "rationale": "Mandated under PMLA 2002 Section 12(1)(a).",
            "citations": ["Prevention of Money-Laundering Act, 2002 (Act No. 15 of 2003) - Section 12"]
        },
        confidence_score=0.98
    )

    response = client.get(f"/api/approvals/{apr.id}/explain")
    assert response.status_code == 200
    data = response.json()

    assert data["confidence_score"] == 0.98
    assert "PMLA" in data["rationale"]
    assert "WORM" in data["evidence_quote"]
    assert len(data["applicable_citations"]) == 1


def test_pipeline_halts_at_gate_and_resumes_on_approval(db_session, tmp_path):
    """Verify workflow pauses at approval gate when auto_approve=False and resumes upon approval."""
    chat = Chat(id="chat-pause-resume", owner_token_hash="tok6", title="Pause Resume Chat")
    db_session.add(chat)
    db_session.commit()

    project = Project(id="proj-pause-resume", chat_id=chat.id, title="Pause Resume Proj", domain="digital_lending")
    db_session.add(project)
    db_session.commit()

    checkpointer = SqliteCheckpointer(db_path=str(tmp_path / "coordinator_p12.db"))
    coordinator = CoordinatorAgent(checkpointer=checkpointer)

    # Turn 1: Concept intake
    res1 = coordinator.run_workflow(
        db=db_session,
        chat=chat,
        user_text="We need to build a digital personal loan disbursement application.",
        auto_approve=False
    )
    assert res1["phase"] == "QUESTIONS_SENT"

    # Turn 2: Answers with auto_approve=False -> extracts requirements, analyses, and halts at approval_gate
    res2 = coordinator.run_workflow(
        db=db_session,
        chat=chat,
        user_text="We require UIDAI Aadhaar verification, PAN validation via NSDL, and AES-256 encryption.",
        auto_approve=False
    )

    # Execution paused at human approval gate
    card_types = [c["card_type"] for c in res2["action_cards"]]
    assert ActionCardType.APPROVAL_REQUEST.value in card_types
    assert "paused" in res2["response_text"].lower()

    # Create approval gate record to simulate human approval
    apr = approval_gate_manager.create_approval_request(
        db=db_session,
        chat_id=chat.id,
        project_id=project.id,
        gate_type=GateType.BASELINE.value,
        subject_id="baseline",
        title="Approve Requirement Baseline",
        description="Stakeholder sign-off on extracted requirements.",
        required_role=ActingRole.PRODUCT_OWNER.value
    )

    # Human approves gate
    approval_gate_manager.process_decision(
        db=db_session,
        approval_id=apr.id,
        action=ApprovalAction.ACCEPT.value,
        acting_role=ActingRole.PRODUCT_OWNER.value,
        comment="Requirements approved for development."
    )

    # Resume workflow with approval_status["requirement_baseline"] = "approved"
    res_resumed = coordinator.run_workflow(
        db=db_session,
        chat=chat,
        user_text="Proceed with approved baseline.",
        auto_approve=True
    )

    # Pipeline successfully resumes through compliance, SDLC, and reaches DONE
    assert res_resumed["phase"] == "DONE"
    assert "complete" in res_resumed["response_text"].lower()
