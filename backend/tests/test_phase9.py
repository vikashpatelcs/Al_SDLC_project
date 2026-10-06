"""
Comprehensive unit and integration test suite for Phase 9: Multi-Agent Orchestration.
Verifies:
1. Per-agent permission matrix: non-coordinator agents cannot write to the database (Rule 7).
2. Full graph path executes to DONE with specialized agent stubs.
3. Restart & resume crash recovery from SQLite checkpointer.
4. Execution steps audit logging in agent_executions table.
5. Live SSE chat streaming emits real-time progress lines.
6. Human-in-the-loop approval gate interrupt and resume.
"""
import os
import uuid
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.config import settings
from backend.app.db.session import SessionLocal
from backend.app.db.models import Chat, Project, RequirementModel, AgentExecutionModel
from backend.app.core.permissions import assert_can_write_db, PermissionDeniedError
from backend.app.graph.state import ConversationPhase
from backend.app.graph.checkpointer import SqliteCheckpointer
from backend.app.graph.workflow import build_orchestration_graph
from backend.app.agents.coordinator import coordinator_agent


@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def client():
    return TestClient(app, cookies={settings.SESSION_COOKIE_NAME: "phase9_test_cookie_12345"})


def test_non_coordinator_cannot_write_db():
    """Verify Rule 7: Only the Coordinator may write to the database."""
    # Coordinator must pass
    assert_can_write_db("coordinator")

    # All other agents must raise PermissionDeniedError
    forbidden_agents = [
        "requirement_engineer",
        "analysis",
        "compliance_security_risk",
        "sdlc",
        "documentation_validation",
        "stakeholder",
        "unauthorized_service"
    ]
    for agent in forbidden_agents:
        with pytest.raises(PermissionDeniedError) as exc_info:
            assert_can_write_db(agent)
        assert "Rule 7 Violation" in str(exc_info.value)


def test_full_graph_execution_to_done(db_session):
    """Verify full graph path executes through all agent nodes to DONE."""
    chat = Chat(id=str(uuid.uuid4()), owner_token_hash="phase9_token", title="Orchestration Full Path Test")
    db_session.add(chat)
    db_session.commit()

    # Turn 1: Concept intake -> Questions sent
    res_turn1 = coordinator_agent.run_workflow(
        db=db_session,
        chat=chat,
        user_text="We need to build a digital wallet app for peer to peer payments."
    )
    assert res_turn1["phase"] == ConversationPhase.QUESTIONS_SENT.value
    assert len(res_turn1["action_cards"]) >= 1

    # Turn 2: Answers -> Extracts, Analyses, Enriches, Recommends SDLC, Completes to DONE
    res_turn2 = coordinator_agent.run_workflow(
        db=db_session,
        chat=chat,
        user_text="The system shall enforce UIDAI biometric verification and limit transactions to 100,000 INR."
    )
    assert res_turn2["phase"] == ConversationPhase.DONE.value
    assert len(res_turn2["requirements"]) >= 1
    assert any("card_type" in c for c in res_turn2["action_cards"])

    # Verify requirements persisted by Coordinator
    project = db_session.query(Project).filter(Project.chat_id == chat.id).first()
    assert project is not None
    reqs_in_db = db_session.query(RequirementModel).filter(RequirementModel.project_id == project.id).all()
    assert len(reqs_in_db) >= 1


def test_agent_executions_audit_logging(db_session):
    """Verify that every executed node writes a row to agent_executions table."""
    chat = Chat(id=str(uuid.uuid4()), owner_token_hash="phase9_token", title="Audit Logging Test")
    db_session.add(chat)
    db_session.commit()

    coordinator_agent.run_workflow(
        db=db_session,
        chat=chat,
        user_text="We want to build an automated lending underwriting engine."
    )

    logs = db_session.query(AgentExecutionModel).filter(AgentExecutionModel.chat_id == chat.id).all()
    assert len(logs) >= 1

    for log in logs:
        assert log.agent_name is not None
        assert log.phase is not None
        assert log.status == "success"
        assert log.duration_ms >= 0


def test_restart_and_resume_from_sqlite_checkpointer(tmp_path):
    """Verify state saved in SQLite checkpointer can be resumed mid-run after process restart."""
    cp_file = str(tmp_path / "test_checkpoints.db")
    cp1 = SqliteCheckpointer(db_path=cp_file)

    graph1 = build_orchestration_graph(checkpointer=cp1)
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    state_turn1 = {
        "chat_id": thread_id,
        "project_id": "test-proj",
        "phase": ConversationPhase.INTAKE.value,
        "user_input": "Digital account opening concept",
        "requirements": [],
        "issues": [],
        "assumptions": [],
        "compliance_mappings": [],
        "risks": [],
        "sdlc_recommendations": {},
        "approval_status": {},
        "action_cards": [],
        "progress_messages": [],
        "iteration_count": 0
    }

    # Execute step 1 on instance 1
    out1 = graph1.invoke(state_turn1, config)
    assert out1["phase"] == ConversationPhase.QUESTIONS_SENT.value

    # Simulate restart: create brand-new checkpointer instance on the same db file
    cp2 = SqliteCheckpointer(db_path=cp_file)
    restored_tuple = cp2.get_tuple(config)
    assert restored_tuple is not None
    assert restored_tuple.checkpoint["channel_values"]["phase"] == ConversationPhase.QUESTIONS_SENT.value

    # Resume graph execution on instance 2
    graph2 = build_orchestration_graph(checkpointer=cp2)
    state_turn2 = {
        "user_input": "The system shall verify PAN with NSDL and Aadhaar with OTP.",
        "requirements": []
    }
    out2 = graph2.invoke(state_turn2, config)
    assert out2["phase"] == ConversationPhase.DONE.value


def test_sse_streams_progress_lines(client):
    """Verify that SSE chat messaging streams real-time progress events."""
    r_create = client.post("/api/chats", json={"title": "Progress Streaming Test"})
    assert r_create.status_code == 201
    chat_id = r_create.json()["id"]

    r_msg = client.post(
        f"/api/chats/{chat_id}/messages",
        json={"content": "We need a digital personal loan disbursement application."}
    )
    assert r_msg.status_code == 200
    text = r_msg.text

    # Verify SSE progress events are present
    assert "event: progress" in text
    assert "data: {\"message\":" in text
    assert "event: token" in text
    assert "event: action_cards" in text
    assert "event: done" in text


def test_interrupt_and_human_approval_gate():
    """Verify human-in-the-loop approval gate interrupt and resumption."""
    graph = build_orchestration_graph(with_interrupts=True)
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    state = {
        "chat_id": thread_id,
        "project_id": "proj-approval",
        "phase": ConversationPhase.ANSWERS_RECEIVED.value,
        "user_input": "The system shall verify customer Aadhaar identity.",
        "requirements": [
            {
                "id": "REQ-001",
                "statement": "The system shall verify customer Aadhaar identity.",
                "category": "Compliance"
            }
        ],
        "approval_status": {},
        "action_cards": [],
        "progress_messages": []
    }

    # First run will interrupt right before approval_gate
    events = []
    for event in graph.stream(state, config):
        events.append(event)

    # Verify execution paused at approval_gate
    state_snap = graph.get_state(config)
    assert "approval_gate" in state_snap.next

    # Resume execution with human approval
    resume_events = []
    for event in graph.stream(None, config):
        resume_events.append(event)

    final_state = graph.get_state(config)
    assert final_state.values["phase"] == ConversationPhase.DONE.value
