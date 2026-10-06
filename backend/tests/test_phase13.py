"""
Unit and Integration Tests for Phase 13: Database Hardening, Field-Level Encryption,
Tamper-Evident Audit Chain, and Auth Hooks.
"""
import uuid
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from backend.app.db.session import Base
from backend.app.db.models import (
    Chat,
    Project,
    Message,
    RequirementModel,
    RequirementVersion,
    TraceabilityModel,
    GeneratedDocumentModel,
    AuditLogModel,
    ModelVersionModel,
    AgentExecutionModel,
    purge_expired_chats
)
from backend.app.core.audit import record_audit_event, verify_audit_chain, AuditEventType, GENESIS_HASH
from backend.app.core.crypto import encrypt_text, decrypt_text
from backend.app.core.auth_hook import get_current_principal, Principal
from backend.app.config import settings
from backend.app.agents.coordinator import CoordinatorAgent
from backend.app.graph.checkpointer import SqliteCheckpointer


@pytest.fixture
def db_session(tmp_path):
    """Isolated in-memory/temp SQLite database for Phase 13 testing."""
    db_file = tmp_path / "test_phase13.db"
    engine = create_engine(f"sqlite:///{db_file}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    try:
        yield session, engine
    finally:
        session.close()


def test_audit_chain_records_and_verifies_cleanly(db_session):
    """Verify that multiple audit records create a mathematically valid SHA-256 chain."""
    session, _ = db_session
    chat_id = "chat-audit-001"

    # Record multiple events
    e1 = record_audit_event(
        db=session,
        event=AuditEventType.INTAKE.value,
        actor="coordinator",
        payload={"action": "start_session", "scope": "onboarding"},
        chat_id=chat_id
    )
    assert e1.prev_hash == GENESIS_HASH

    e2 = record_audit_event(
        db=session,
        event=AuditEventType.EXTRACTION.value,
        actor="requirement_engineer",
        payload={"extracted": ["REQ-001", "REQ-002"]},
        chat_id=chat_id
    )
    assert e2.prev_hash == e1.hash

    e3 = record_audit_event(
        db=session,
        event=AuditEventType.APPROVAL_DECISION.value,
        actor="product_owner",
        payload={"decision": "accepted", "gate": "baseline"},
        chat_id=chat_id
    )
    assert e3.prev_hash == e2.hash

    # Verify global chain
    is_valid, err, tampered_id = verify_audit_chain(session)
    assert is_valid is True
    assert err is None
    assert tampered_id is None

    # Verify per-chat chain
    is_valid_chat, _, _ = verify_audit_chain(session, chat_id=chat_id)
    assert is_valid_chat is True


def test_audit_chain_detects_tamper(db_session):
    """Verify that any modification to an existing audit log entry is detected and pinpointed."""
    session, engine = db_session
    chat_id = "chat-tamper-002"

    e1 = record_audit_event(session, AuditEventType.INTAKE.value, "user", {"msg": "hello"}, chat_id)
    e2 = record_audit_event(session, AuditEventType.EXTRACTION.value, "agent", {"reqs": 2}, chat_id)
    e3 = record_audit_event(session, AuditEventType.SDLC_RECOMMENDED.value, "sdlc_agent", {"model": "Agile"}, chat_id)

    # Intentionally tamper with middle row directly via raw SQL
    with engine.connect() as conn:
        conn.execute(
            text("UPDATE audit_logs SET payload_json = :malicious WHERE id = :target_id"),
            {"malicious": '{"reqs":999,"forged":true}', "target_id": e2.id}
        )
        conn.commit()

    # Expire session cache
    session.expire_all()

    # Verify chain detects tamper and pinpoints row e2
    is_valid, err_msg, tampered_id = verify_audit_chain(session)
    assert is_valid is False
    assert tampered_id == e2.id
    assert "Tampered row" in err_msg


def test_field_level_encryption_at_rest(db_session):
    """Verify sensitive text is encrypted at rest in raw DB while transparent in ORM."""
    session, engine = db_session

    chat = Chat(id="chat-crypto-01", owner_token_hash="tok1", title="Crypto Chat")
    session.add(chat)
    session.commit()

    secret_message = "Confidential customer Aadhaar 1234-5678-9012 and salary statements."
    secret_statement = "The system shall encrypt customer PAN records with AES-256."

    msg = Message(
        id="msg-crypto-01",
        chat_id=chat.id,
        role="user",
        content_masked=secret_message
    )
    project = Project(id="proj-crypto-01", chat_id=chat.id, title="Crypto Proj")
    req = RequirementModel(
        id="REQ-CRYPTO-01",
        project_id=project.id,
        statement=secret_statement,
        category="Security"
    )
    session.add_all([project, msg, req])
    session.commit()

    # 1. ORM level: transparent decryption
    session.expire_all()
    loaded_msg = session.query(Message).filter(Message.id == msg.id).first()
    loaded_req = session.query(RequirementModel).filter(RequirementModel.id == req.id).first()
    assert loaded_msg.content_masked == secret_message
    assert loaded_req.statement == secret_statement

    # 2. Raw SQLite level: verify plaintext is NOT present in storage
    with engine.connect() as conn:
        raw_msg_row = conn.execute(text("SELECT content_masked FROM messages WHERE id = 'msg-crypto-01'")).fetchone()
        raw_req_row = conn.execute(text("SELECT statement FROM requirements WHERE id = 'REQ-CRYPTO-01'")).fetchone()

        raw_msg_text = raw_msg_row[0]
        raw_req_text = raw_req_row[0]

        # Plaintext secrets must NOT be in raw database
        assert secret_message not in raw_msg_text
        assert secret_statement not in raw_req_text
        assert "Aadhaar" not in raw_msg_text
        assert "AES-256" not in raw_req_text

        # Ciphertext format verification (Fernet tokens start with gAAAAA)
        assert raw_msg_text.startswith("gAAAAA")
        assert raw_req_text.startswith("gAAAAA")


def test_soft_delete_and_retention_purge(db_session):
    """Verify soft-delete filtering and retention purging of expired records."""
    session, _ = db_session
    now = datetime.now(timezone.utc)

    # 1. Active chat
    c_active = Chat(id="chat-active", owner_token_hash="tok1", title="Active", deleted_at=None)

    # 2. Recently soft-deleted chat (within 30-day retention window)
    c_recent_del = Chat(
        id="chat-recent-del",
        owner_token_hash="tok1",
        title="Recent Deleted",
        deleted_at=now - timedelta(days=5)
    )

    # 3. Expired soft-deleted chat (older than 30-day retention window)
    c_expired_del = Chat(
        id="chat-expired-del",
        owner_token_hash="tok1",
        title="Expired Deleted",
        deleted_at=now - timedelta(days=45)
    )

    session.add_all([c_active, c_recent_del, c_expired_del])
    session.commit()

    # Verify standard active query excludes soft-deleted
    active_chats = session.query(Chat).filter(Chat.deleted_at.is_(None)).all()
    assert len(active_chats) == 1
    assert active_chats[0].id == "chat-active"

    # Purge with 30-day retention
    purged_count = purge_expired_chats(session, retention_days=30)
    assert purged_count == 1

    # Verify expired chat was physically purged, but recent deleted remains
    assert session.query(Chat).filter(Chat.id == "chat-expired-del").first() is None
    assert session.query(Chat).filter(Chat.id == "chat-recent-del").first() is not None
    assert session.query(Chat).filter(Chat.id == "chat-active").first() is not None


def test_auth_hook_resolves_principal():
    """Verify get_current_principal resolves session tokens and guest fallbacks."""
    # 1. Authenticated session request
    req_auth = MagicMock()
    req_auth.cookies = {settings.SESSION_COOKIE_NAME: "test_token_secret_xyz"}
    req_auth.headers = {}

    p_auth = get_current_principal(req_auth)
    assert p_auth.is_authenticated is True
    assert p_auth.auth_type == "anonymous_session"
    assert p_auth.role == "requirements_engineer"
    assert p_auth.id.startswith("user-")

    # 2. Bearer header fallback
    req_hdr = MagicMock()
    req_hdr.cookies = {}
    req_hdr.headers = {"Authorization": "Bearer header_token_secret_123"}

    p_hdr = get_current_principal(req_hdr)
    assert p_hdr.is_authenticated is True
    assert p_hdr.auth_type == "anonymous_session"

    # 3. Unauthenticated guest
    req_guest = MagicMock()
    req_guest.cookies = {}
    req_guest.headers = {}

    p_guest = get_current_principal(req_guest)
    assert p_guest.is_authenticated is False
    assert p_guest.role == "guest"


def test_traceability_and_generated_documents_models(db_session):
    """Verify persistence of TraceabilityModel, GeneratedDocumentModel, and ModelVersionModel."""
    session, _ = db_session
    chat = Chat(id="chat-models-01", owner_token_hash="tok3", title="Models Chat")
    project = Project(id="proj-models-01", chat_id=chat.id, title="Models Project")
    req = RequirementModel(id="REQ-MOD-01", project_id=project.id, statement="Req statement", category="Functional")
    session.add_all([chat, project, req])
    session.commit()

    # Traceability link
    tr = TraceabilityModel(
        project_id=project.id,
        source_statement_id="msg#10",
        requirement_id=req.id,
        regulation_chunk="RBI-KYC-Sec16",
        control="SEC-CTRL-01",
        acceptance_criteria_id="AC-001",
        risk_id="RSK-001"
    )

    # Generated document record
    doc = GeneratedDocumentModel(
        chat_id=chat.id,
        project_id=project.id,
        doc_type="srs",
        version=1,
        file_path="/storage/generated/srs_v1.pdf",
        sha256="abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
        status="generated"
    )

    # Model version registry
    mv = ModelVersionModel(
        id="qwen2.5:7b-instruct",
        name="Qwen 2.5 7B Instruct",
        base_model="Qwen2.5-7B-Instruct",
        parameters="7B",
        context_len=4096,
        is_active=True
    )

    session.add_all([tr, doc, mv])
    session.commit()

    # Verify retrieval
    loaded_tr = session.query(TraceabilityModel).filter(TraceabilityModel.requirement_id == req.id).first()
    assert loaded_tr.regulation_chunk == "RBI-KYC-Sec16"
    assert loaded_tr.control == "SEC-CTRL-01"

    loaded_doc = session.query(GeneratedDocumentModel).filter(GeneratedDocumentModel.chat_id == chat.id).first()
    assert loaded_doc.doc_type == "srs"
    assert loaded_doc.sha256.startswith("abcdef")

    loaded_mv = session.query(ModelVersionModel).filter(ModelVersionModel.id == "qwen2.5:7b-instruct").first()
    assert loaded_mv.parameters == "7B"
    assert loaded_mv.is_active is True


def test_coordinator_creates_audit_trail(db_session, tmp_path):
    """Verify that CoordinatorAgent workflow turns automatically append to the audit log chain."""
    session, _ = db_session
    chat = Chat(id="chat-coord-audit", owner_token_hash="tok_coord", title="Coord Audit Chat")
    session.add(chat)
    session.commit()

    checkpointer = SqliteCheckpointer(db_path=str(tmp_path / "coord_audit_cp.db"))
    coordinator = CoordinatorAgent(checkpointer=checkpointer)

    # Run Turn 1: Concept intake
    res1 = coordinator.run_workflow(
        db=session,
        chat=chat,
        user_text="Digital lending app for micro loans.",
        auto_approve=True
    )

    # Audit records must exist
    audit_records = session.query(AuditLogModel).filter(AuditLogModel.chat_id == chat.id).all()
    assert len(audit_records) >= 1
    assert audit_records[0].event == AuditEventType.INTAKE.value

    # Verify audit chain integrity
    is_valid, err, _ = verify_audit_chain(session, chat_id=chat.id)
    assert is_valid is True
    assert err is None
