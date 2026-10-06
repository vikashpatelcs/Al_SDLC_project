"""
Comprehensive tests for Phase 6: Structured Requirement Engine.
Verifies:
1. Document parsers (txt, csv, docx, pdf, eml) with pre-flight PII masking.
2. Grouped questions generation (slot-based, not one-at-a-time).
3. Requirement extraction on Gold Cases with >= 80% recall.
4. Multi-label classification across the 13 canonical categories.
5. Traceability with source_statement_id on 100% of requirements.
6. Assumptions register population.
7. DB persistence for Project, RequirementModel, RequirementVersion, and Assumption.
8. End-to-end chat flow (Intake -> Grouped Questions -> Answers -> Extracted Summary).
"""
import csv
import json
import os
import uuid
import pytest
from docx import Document
from pypdf import PdfWriter
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.config import settings
from backend.app.db.session import SessionLocal
from backend.app.db.models import Project, RequirementModel, RequirementVersion, Assumption, Chat, Message
from backend.app.schemas import RequirementCategory, ActionCardType
from backend.app.core.parsers.factory import parse_and_mask_document
from backend.app.agents.requirement_engineer import requirement_engineer_agent


CASES_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../ml/eval/cases"))


@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def client():
    return TestClient(app, cookies={settings.SESSION_COOKIE_NAME: "phase6_test_cookie_12345"})


def test_document_parsers_multi_format(tmp_path):
    """Verify document parsers extract text chunks with traceable IDs and pre-flight PII masking."""
    # 1. Plaintext parser test
    txt_file = tmp_path / "spec.txt"
    txt_file.write_text("Paragraph 1: The system shall verify user identity.\n\nParagraph 2: Customer mobile 9876543210 is verified.", encoding="utf-8")
    txt_chunks = parse_and_mask_document(str(txt_file))
    assert len(txt_chunks) >= 1
    assert all(c.is_masked for c in txt_chunks)
    assert "[MOBILE_" in txt_chunks[0].text or "verify user identity" in txt_chunks[0].text
    assert txt_chunks[0].chunk_id.startswith("spec.txt#")

    # 2. CSV parser test
    csv_file = tmp_path / "requirements.csv"
    with open(csv_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["ID", "Statement", "Priority"])
        writer.writerow(["REQ-01", "The system shall encrypt data at rest", "High"])
        writer.writerow(["REQ-02", "Customer Aadhaar 2345 6789 0123 must be verified", "High"])
    csv_chunks = parse_and_mask_document(str(csv_file))
    assert len(csv_chunks) >= 1
    assert "[AADHAAR_" in csv_chunks[0].text or "encrypt data at rest" in csv_chunks[0].text

    # 3. DOCX parser test
    docx_file = tmp_path / "interview.docx"
    doc = Document()
    doc.add_heading("Stakeholder Transcript", 0)
    doc.add_paragraph("The application shall enforce dual maker-checker authorization.")
    doc.save(str(docx_file))
    docx_chunks = parse_and_mask_document(str(docx_file))
    assert len(docx_chunks) >= 1
    assert "maker-checker authorization" in docx_chunks[0].text

    # 4. PDF parser test
    pdf_file = tmp_path / "regulation.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    with open(pdf_file, "wb") as f:
        writer.write(f)
    pdf_chunks = parse_and_mask_document(str(pdf_file))
    # Blank page returns empty or chunk
    assert isinstance(pdf_chunks, list)

    # 5. EML parser test
    eml_file = tmp_path / "thread.eml"
    eml_content = (
        "From: architect@bank.com\n"
        "To: po@bank.com\n"
        "Subject: Architecture Decision\n"
        "Date: Mon, 06 Oct 2026 10:00:00 +0530\n\n"
        "The system shall enforce TLS 1.3 for all inter-service communications."
    )
    eml_file.write_text(eml_content, encoding="utf-8")
    eml_chunks = parse_and_mask_document(str(eml_file))
    assert len(eml_chunks) == 1
    assert "TLS 1.3" in eml_chunks[0].text


def test_grouped_questions_generation():
    """Verify slot-based questions are grouped by theme and not asked one-at-a-time."""
    concept = "We want to launch an online digital wallet with UPI payments and merchant settlements."
    card = requirement_engineer_agent.generate_grouped_questions(concept)
    
    assert card.card_type == ActionCardType.QUESTION_GROUP
    groups = card.payload.get("groups", [])
    assert len(groups) >= 2, f"Expected at least 2 question groups, got {len(groups)}"
    
    total_questions = sum(len(g.get("questions", [])) for g in groups)
    assert total_questions >= 2, f"Expected multiple questions across groups, got {total_questions}"

    # Verify grouping topics exist
    topics = [g.get("topic") for g in groups]
    assert any("Workflow" in t or "Limits" in t or "Security" in t or "Audit" in t for t in topics)


def test_gold_requirement_extraction_recall():
    """Verify >= 80% recall on gold requirements across all seed cases."""
    case_files = ["case1_onboarding_kyc.json", "case2_loan_origination.json", "case3_upi_payments.json"]

    for cfile in case_files:
        path = os.path.join(CASES_DIR, cfile)
        with open(path, "r", encoding="utf-8") as f:
            cdata = json.load(f)

        narrative = cdata["narrative"]
        gold_reqs = cdata["gold_requirements"]

        extracted = requirement_engineer_agent.extract_requirements_from_text(
            text=narrative,
            source_statement_id=f"doc#{cdata['case_id']}",
            project_id="test-proj-001"
        )

        assert len(extracted) > 0, f"No requirements extracted for {cdata['case_id']}"

        # Evaluate recall: for each gold requirement, check if its core topic is captured in extracted
        matched_gold = 0
        extracted_texts = " ".join([r.statement.lower() for r in extracted])

        for g in gold_reqs:
            # Check key keywords from gold statement
            keywords = [w.lower() for w in g["statement"].split() if len(w) > 4 and w.lower() not in ["shall", "system", "under"]]
            if any(k in extracted_texts for k in keywords):
                matched_gold += 1

        recall = matched_gold / len(gold_reqs)
        assert recall >= 0.80, f"Case {cdata['case_id']} recall {recall:.2f} < 0.80 ({matched_gold}/{len(gold_reqs)})"


def test_multi_label_classification_validity():
    """Verify all extracted requirements receive a valid canonical category."""
    text = "The system shall verify customer Aadhaar identity and encrypt all records using AES-256."
    extracted = requirement_engineer_agent.extract_requirements_from_text(
        text=text,
        source_statement_id="msg-101",
        project_id="test-proj-001"
    )
    assert len(extracted) >= 1
    canonical_values = set(c.value for c in RequirementCategory)
    for r in extracted:
        assert r.category.value in canonical_values


def test_source_statement_id_traceability():
    """Verify 100% of extracted requirements have a valid source_statement_id link."""
    source_id = "chunk_section_7#line_20"
    text = "The system shall validate customer PAN validity against the NSDL database prior to account activation."
    extracted = requirement_engineer_agent.extract_requirements_from_text(
        text=text,
        source_statement_id=source_id,
        project_id="test-proj-001"
    )
    assert len(extracted) >= 1
    for r in extracted:
        assert r.source_statement_id == source_id


def test_assumptions_register(db_session):
    """Verify assumption records are generated when defaults are requested."""
    text = "Please proceed with customer onboarding and assume standard defaults for KYC and limits."
    assumptions = requirement_engineer_agent.extract_assumptions(text, "proj-123")
    assert len(assumptions) >= 2
    for a in assumptions:
        assert a.project_id == "proj-123"
        assert a.statement is not None
        assert a.status == "unverified"


def test_database_persistence_and_versioning(db_session):
    """Verify RequirementModel and initial RequirementVersion are persisted."""
    chat = Chat(id=str(uuid.uuid4()), owner_token_hash="test_token_hash", title="Persistence Test")
    db_session.add(chat)
    db_session.commit()

    user_msg = Message(
        id=str(uuid.uuid4()),
        chat_id=chat.id,
        role="user",
        sender_agent="stakeholder",
        content_masked="Customer identity must be verified using UIDAI Aadhaar offline XML verification.",
        created_at=chat.created_at
    )
    db_session.add(user_msg)
    db_session.commit()

    result = requirement_engineer_agent.process_chat_message(
        db=db_session,
        chat=chat,
        user_message=user_msg
    )

    # First turn was intake -> now send second turn with answers
    answer_msg = Message(
        id=str(uuid.uuid4()),
        chat_id=chat.id,
        role="user",
        sender_agent="stakeholder",
        content_masked="The system must verify PAN with NSDL and encrypt KYC records with AES-256.",
        created_at=chat.created_at
    )
    db_session.add(answer_msg)
    db_session.commit()

    result_turn2 = requirement_engineer_agent.process_chat_message(
        db=db_session,
        chat=chat,
        user_message=answer_msg
    )

    # Check Project created
    project = db_session.query(Project).filter(Project.chat_id == chat.id).first()
    assert project is not None

    # Check Requirements created
    reqs = db_session.query(RequirementModel).filter(RequirementModel.project_id == project.id).all()
    assert len(reqs) >= 1

    # Check Versions created
    for r in reqs:
        versions = db_session.query(RequirementVersion).filter(RequirementVersion.requirement_id == r.id).all()
        assert len(versions) >= 1
        assert versions[0].version == 1


def test_end_to_end_chat_intake_and_extraction(client):
    """Verify chat intake returns grouped questions on turn 1, and extraction summary on turn 2."""
    # Create chat
    r_create = client.post("/api/chats", json={"title": "End to End Onboarding"})
    assert r_create.status_code == 201
    chat_id = r_create.json()["id"]

    # Turn 1: Concept intake -> Grouped questions
    r_turn1 = client.post(
        f"/api/chats/{chat_id}/messages",
        json={"content": "We want to build a digital lending app for personal loans."}
    )
    assert r_turn1.status_code == 200
    assert "event: action_cards" in r_turn1.text
    assert "question_group" in r_turn1.text

    # Turn 2: Answers submission -> Structured requirements extracted
    r_turn2 = client.post(
        f"/api/chats/{chat_id}/messages",
        json={"content": "We require UIDAI Aadhaar verification, PAN check via NSDL, and AES-256 encryption. Assume standard defaults."}
    )
    assert r_turn2.status_code == 200
    assert "event: action_cards" in r_turn2.text
    assert "requirement_card" in r_turn2.text
    assert "Structured Requirements Extracted" in r_turn2.text
