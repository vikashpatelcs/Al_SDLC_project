"""
Tests for Phase 14: SRS / PDF / Artefacts Generator per PS §12 and Master Plan §12.
Verifies all 23 standard sections in generated PDF, approved-only filtering,
DRAFT watermarking, 100% RTM coverage, pre-generation validation, and REST export.
"""
import os
import uuid
import hashlib
import pytest
from pypdf import PdfReader
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.main import app
from backend.app.db.models import (
    Base,
    Chat,
    Project,
    RequirementModel,
    ComplianceMappingModel,
    RiskModel,
    SDLCRecommendationModel,
    ApprovalModel,
    TraceabilityModel,
    GeneratedDocumentModel
)
from backend.app.db.session import get_db
from backend.app.docs_gen.validation import SpecificationValidator
from backend.app.docs_gen.traceability import TraceabilityEngine
from backend.app.agents.documentation import DocumentationAgent
from backend.app.graph.nodes import documentation_validation_node
from backend.app.graph.state import ConversationPhase
from backend.app.config import settings


from sqlalchemy.pool import StaticPool

# In-memory SQLite for Phase 14 tests
TEST_DB_URL = "sqlite:///:memory:"
engine = create_engine(
    TEST_DB_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    test_client = TestClient(app)
    yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def sample_spec_data():
    project_data = {
        "id": "PROJ-KYC-001",
        "title": "Digital Banking KYC & Customer Onboarding",
        "version": 1
    }
    requirements = [
        {
            "id": "FR-ONB-001",
            "statement": "The system shall capture and redact customer identity documents with OCR.",
            "category": "Functional",
            "priority": "High",
            "source_statement_id": "SRC-UTT-001",
            "status": "baseline_approved",
            "acceptance_criteria": [
                {"id": "AC-ONB-001", "given": "A customer uploads Aadhaar", "when": "OCR parses the image", "then": "First 8 digits are masked"}
            ]
        },
        {
            "id": "SR-SEC-002",
            "statement": "The system shall encrypt customer identity identifiers at rest using AES-256.",
            "category": "Security",
            "priority": "High",
            "source_statement_id": "SRC-UTT-002",
            "status": "baseline_approved",
            "evidence_ids": ["RBI-ITG-SEC-004"],
            "acceptance_criteria": [
                {"id": "AC-SEC-002", "given": "Customer data is written", "when": "Stored in database", "then": "Raw plaintext is never persisted"}
            ]
        },
        {
            "id": "CR-CMP-003",
            "statement": "The system shall obtain explicit customer consent before fetching e-KYC records.",
            "category": "Compliance",
            "priority": "High",
            "source_statement_id": "SRC-UTT-003",
            "status": "baseline_approved",
            "evidence_ids": ["DPDP-2023-SEC-006"],
            "acceptance_criteria": [
                {"id": "AC-CMP-003", "given": "Customer reaches e-KYC step", "when": "Prompt displayed", "then": "Affirmative consent recorded"}
            ]
        }
    ]
    compliance_mappings = [
        {
            "requirement_id": "CR-CMP-003",
            "regulation_name": "DPDP Act 2023",
            "section_reference": "Section 6(1)",
            "control_required": "Obtain freely given specific consent",
            "citation_verified": True
        },
        {
            "requirement_id": "SR-SEC-002",
            "regulation_name": "RBI IT Governance 2023",
            "section_reference": "Clause 8.2",
            "control_required": "Cryptographic protection of data at rest",
            "citation_verified": True
        }
    ]
    risks = [
        {
            "id": "RSK-001",
            "requirement_id": "SR-SEC-002",
            "category": "security",
            "severity": "high",
            "risk_score": 15,
            "mitigation": "Field-level Fernet token encryption."
        }
    ]
    sdlc_rec = {
        "selected_model": "Agile-DevSecOps Hybrid",
        "explanation": "High regulatory criticality requires continuous verification gates."
    }
    return {
        "project_data": project_data,
        "requirements": requirements,
        "compliance_mappings": compliance_mappings,
        "risks": risks,
        "sdlc_rec": sdlc_rec
    }


def test_srs_pdf_has_all_23_sections(sample_spec_data, tmp_path):
    """PS §12 & Master Plan §12: SRS PDF renders all 23 standard sections."""
    agent = DocumentationAgent()
    out_dir = str(tmp_path / "docs")

    res = agent.compile_srs(
        db=None,
        chat_id="test_chat_23",
        project_data=sample_spec_data["project_data"],
        requirements=sample_spec_data["requirements"],
        compliance_mappings=sample_spec_data["compliance_mappings"],
        risks=sample_spec_data["risks"],
        sdlc_recommendation=sample_spec_data["sdlc_rec"],
        is_approved=True,
        output_dir=out_dir
    )

    pdf_path = res["pdf_meta"]["file_path"]
    assert os.path.exists(pdf_path)

    # Read rendered PDF pages using pypdf
    reader = PdfReader(pdf_path)
    full_text = " ".join([page.extract_text() or "" for page in reader.pages])

    # Assert presence of all 23 standard sections
    expected_sections = [
        "1. Document Control",
        "2. Executive Summary",
        "3. Purpose",
        "4. Scope",
        "5. Definitions, Acronyms",
        "6. References, Statutory",
        "7. Product Perspective",
        "8. Product Functions Overview",
        "9. User Classes",
        "10. Operating Environment",
        "11. Design, Implementation",
        "12. Assumptions",
        "13. External Interface",
        "14. System Functional Requirements Catalog",
        "15. User Stories",
        "16. Use Case",
        "17. Process Workflows",
        "18. Data Requirements",
        "19. Non-Functional Quality",
        "20. Statutory & Regulatory Compliance Matrix",
        "21. Threat & Risk Register",
        "22. Tailored SDLC Methodology",
        "23. Requirements Traceability Matrix"
    ]

    for sec in expected_sections:
        assert sec in full_text, f"Section missing from generated PDF: '{sec}'"


def test_unapproved_requirements_excluded_from_approved_srs(sample_spec_data, tmp_path):
    """Approved baseline documents must omit rejected or unapproved draft requirements."""
    agent = DocumentationAgent()
    out_dir = str(tmp_path / "docs")

    reqs_with_unapproved = list(sample_spec_data["requirements"])
    reqs_with_unapproved.append({
        "id": "FR-REJ-999",
        "statement": "The system shall store raw unmasked CVV codes permanently.",
        "category": "Functional",
        "priority": "Low",
        "source_statement_id": "SRC-UNAPPROVED",
        "status": "rejected"  # Excluded!
    })

    res = agent.compile_srs(
        db=None,
        chat_id="test_chat_filter",
        project_data=sample_spec_data["project_data"],
        requirements=reqs_with_unapproved,
        compliance_mappings=sample_spec_data["compliance_mappings"],
        risks=sample_spec_data["risks"],
        is_approved=True,
        output_dir=out_dir
    )

    pdf_path = res["pdf_meta"]["file_path"]
    reader = PdfReader(pdf_path)
    full_text = " ".join([page.extract_text() or "" for page in reader.pages])

    # Approved requirements are present
    assert "FR-ONB-001" in full_text
    assert "SR-SEC-002" in full_text

    # Rejected requirement must be omitted
    assert "FR-REJ-999" not in full_text
    assert "store raw unmasked CVV codes permanently" not in full_text


def test_draft_watermark_when_not_approved(sample_spec_data, tmp_path):
    """Unapproved or in-progress baseline compiles with DRAFT status & watermark."""
    agent = DocumentationAgent()
    out_dir = str(tmp_path / "docs")

    res = agent.compile_srs(
        db=None,
        chat_id="test_chat_draft",
        project_data=sample_spec_data["project_data"],
        requirements=sample_spec_data["requirements"],
        is_approved=False,
        output_dir=out_dir
    )

    pdf_path = res["pdf_meta"]["file_path"]
    assert res["pdf_meta"]["is_approved"] is False

    reader = PdfReader(pdf_path)
    full_text = " ".join([page.extract_text() or "" for page in reader.pages])
    assert "DRAFT" in full_text


def test_traceability_matrix_100_percent_coverage(sample_spec_data, db_session):
    """Verifies 100% RTM coverage and database persistence."""
    agent = DocumentationAgent()
    proj_id = sample_spec_data["project_data"]["id"]

    # First add requirement models to DB session
    for r in sample_spec_data["requirements"]:
        db_session.add(RequirementModel(
            id=r["id"],
            project_id=proj_id,
            statement=r["statement"],
            category=r["category"],
            source_statement_id=r["source_statement_id"]
        ))
    db_session.commit()

    rtm_rows = agent.traceability_engine.build_matrix(
        requirements=sample_spec_data["requirements"],
        compliance_mappings=sample_spec_data["compliance_mappings"],
        risks=sample_spec_data["risks"]
    )
    coverage = agent.traceability_engine.calculate_coverage(rtm_rows, sample_spec_data["requirements"])
    assert coverage == 1.0

    # Persist to database
    persisted_count = agent.traceability_engine.persist_traceability(db_session, proj_id, rtm_rows)
    assert persisted_count >= 3

    # Verify rows in DB
    db_rows = db_session.query(TraceabilityModel).filter(TraceabilityModel.project_id == proj_id).all()
    assert len(db_rows) == persisted_count
    for row in db_rows:
        assert row.source_statement_id is not None
        assert row.requirement_id is not None
        assert row.acceptance_criteria_id is not None


def test_validation_engine_flags_missing_evidence():
    """SpecificationValidator checks completeness and flags missing evidence for regulatory specs."""
    incomplete_reqs = [
        {
            "id": "CR-001",
            "statement": "Short",  # too short
            "category": "Compliance",
            "source_statement_id": None,  # missing link
            "evidence_ids": [],  # missing evidence
            "acceptance_criteria": []
        }
    ]
    val = SpecificationValidator.validate(incomplete_reqs)
    assert not val.is_valid
    assert len(val.errors) > 0
    assert any("statement" in e.lower() for e in val.errors)
    assert any("evidence" in w.lower() for w in val.warnings)


def test_generated_document_persistence_and_sha256(sample_spec_data, tmp_path, db_session):
    """Generated document records file_path, version, and authentic SHA-256."""
    agent = DocumentationAgent()
    out_dir = str(tmp_path / "docs")

    res = agent.compile_srs(
        db=db_session,
        chat_id="test_chat_sha",
        project_data=sample_spec_data["project_data"],
        requirements=sample_spec_data["requirements"],
        output_dir=out_dir
    )

    pdf_meta = res["pdf_meta"]
    pdf_path = pdf_meta["file_path"]

    # Compute actual SHA-256
    with open(pdf_path, "rb") as f:
        computed_sha = hashlib.sha256(f.read()).hexdigest()

    assert pdf_meta["sha256"] == computed_sha


def test_export_endpoint_returns_binary_pdf(client, db_session, sample_spec_data, tmp_path):
    """GET /chats/{chat_id}/documents/export returns 200 with application/pdf and verified SHA header."""
    chat_id = str(uuid.uuid4())
    token = "anon_doc_tester"
    owner_hash = hashlib.sha256(token.encode()).hexdigest()

    # Create chat and project
    chat = Chat(id=chat_id, owner_token_hash=owner_hash, title="Onboarding Project", state="DONE")
    project = Project(id=str(uuid.uuid4()), chat_id=chat_id, title="Onboarding Project")
    db_session.add(chat)
    db_session.add(project)

    for r in sample_spec_data["requirements"]:
        db_session.add(RequirementModel(
            id=r["id"],
            project_id=project.id,
            statement=r["statement"],
            category=r["category"],
            source_statement_id=r["source_statement_id"],
            status="baseline_approved"
        ))
    db_session.commit()

    client.cookies.set(settings.SESSION_COOKIE_NAME, token)

    # Call export endpoint
    resp = client.get(f"/api/chats/{chat_id}/documents/export")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert "X-Document-SHA256" in resp.headers

    # Validate binary PDF magic header
    pdf_bytes = resp.content
    assert pdf_bytes.startswith(b"%PDF-")


def test_graph_documentation_validation_node_generates_srs(sample_spec_data):
    """Graph documentation node synthesizes SRS, updates phase to DONE, and emits ActionCard."""
    state = {
        "chat_id": "test_graph_chat",
        "project_id": "test_graph_proj",
        "phase": ConversationPhase.SDLC_ANALYSED.value,
        "requirements": sample_spec_data["requirements"],
        "compliance_mappings": sample_spec_data["compliance_mappings"],
        "risks": sample_spec_data["risks"],
        "sdlc_recommendations": sample_spec_data["sdlc_rec"],
        "approval_status": {"requirement_baseline": "approved"}
    }

    result = documentation_validation_node(state)
    assert result["phase"] == ConversationPhase.DONE.value
    assert len(result["action_cards"]) > 0

    doc_card = result["action_cards"][-1]
    assert doc_card["card_type"] in ("download_pdf", "document_export")
    assert doc_card["payload"]["is_approved"] is True
    assert doc_card["payload"]["sha256"] is not None
