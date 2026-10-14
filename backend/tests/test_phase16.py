"""
Phase 16 Integration & Hardening Test Suite per Master Plan §12 (Phase 16) and §33.
Features:
  1. Full §33 digital banking customer onboarding & KYC walkthrough run 3x consecutively.
  2. Latency profiling across all 6 pipeline stages.
  3. Resilience & error handling: model offline, empty KB, malicious upload rejection, tenant isolation.
  4. Cryptographic tamper-evident audit hash chain verification.
"""
import os
import json
import time
import uuid
import hashlib
import pytest
from pypdf import PdfReader
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.testclient import TestClient

from backend.app.main import app
from backend.app.config import settings
from backend.app.db.session import Base, get_db
from backend.app.db.models import (
    Chat,
    Project,
    Stakeholder,
    RequirementModel,
    RequirementVersion,
    Assumption,
    RequirementIssueModel,
    ComplianceMappingModel,
    RiskModel,
    SDLCRecommendationModel,
    ApprovalModel,
    TraceabilityModel,
    GeneratedDocumentModel,
    AuditLogModel,
)
from backend.app.schemas.message import ActionCardType
from backend.app.schemas.approval import GateType, ApprovalAction, ActingRole, ApprovalStatus
from backend.app.agents.requirement_engineer import requirement_engineer_agent
from backend.app.agents.analysis import analysis_engine
from backend.app.agents.compliance_security_risk import compliance_security_risk_agent
from backend.app.agents.sdlc import sdlc_agent
from backend.app.agents.documentation import DocumentationAgent
from backend.app.graph.gates import approval_gate_manager, SDLC_MANDATORY_ROLES
from backend.app.core.audit import record_audit_event, AuditEventType, verify_audit_chain
from backend.app.core.llm_gateway import llm_gateway, ModelServiceUnavailableError
from backend.app.rag.retriever import hybrid_retriever


@pytest.fixture
def db_session():
    """Isolated in-memory SQLite database with static pool for Phase 16 testing."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    c = TestClient(app, cookies={settings.SESSION_COOKIE_NAME: "test_phase16_cookie_xyz"})
    yield c
    app.dependency_overrides.clear()


def execute_section33_walkthrough(db: sessionmaker, run_index: int):
    """
    Executes the complete §33 User Journey end-to-end:
      Concept Prompt -> Question Cards -> Answers -> Extraction -> Quality Checks ->
      Compliance/Risk -> Approval Gate -> SDLC Recommendation -> Challenge -> 4-Role Signoff ->
      Validation -> 23-Section PDF Export -> Audit Hash Chain Verification.
    """
    chat_id = f"chat-sec33-run-{run_index}-{uuid.uuid4().hex[:6]}"
    project_id = f"proj-sec33-run-{run_index}-{uuid.uuid4().hex[:6]}"

    chat = Chat(id=chat_id, owner_token_hash="owner_sec33_hash", title=f"§33 Digital Banking Onboarding Run {run_index}")
    project = Project(id=project_id, chat_id=chat_id, title=f"Digital Banking KYC Onboarding Run {run_index}", domain="banking")
    db.add_all([chat, project])
    db.commit()

    record_audit_event(
        db=db,
        event=AuditEventType.SESSION_START.value,
        actor="Stakeholder",
        payload={"chat_id": chat_id, "project_id": project_id, "run": run_index},
        chat_id=chat_id,
    )

    # Stage 1: Stakeholder Prompt & Grouped Question Generation (Intake)
    initial_prompt = "We want a digital banking customer onboarding and KYC verification workflow."
    question_card = requirement_engineer_agent.generate_grouped_questions(initial_prompt)
    assert question_card.card_type == ActionCardType.QUESTION_GROUP
    assert "groups" in question_card.payload
    assert len(question_card.payload["groups"]) >= 1

    record_audit_event(
        db=db,
        event=AuditEventType.INTAKE.value,
        actor="RequirementEngineerAgent",
        payload={"prompt": initial_prompt, "groups_generated": len(question_card.payload["groups"])},
        chat_id=chat_id,
    )

    # Stage 2: Stakeholder Comprehensive Specification Answer & Requirement Extraction
    stakeholder_answer = (
        "The system shall verify customer identity using UIDAI Aadhaar offline XML verification with explicit OTP consent. "
        "The system shall validate customer PAN validity against NSDL database prior to account activation. "
        "The system shall provide an agent-assisted Video-based Customer Identification Process (V-CIP) when biometric checks fail. "
        "The system shall complete UIDAI XML identity verification within 3 seconds under 95th percentile load. "
        "The system shall enforce daily transaction limits and step-up authentication. "
        "The system shall encrypt all customer KYC documents and biometric tokens at rest using AES-256 field-level encryption. "
        "The system shall retain all customer identification records and V-CIP recordings for at least five years from date of account closure in accordance with PMLA 2002."
    )

    extracted_reqs = requirement_engineer_agent.extract_requirements_from_text(
        text=stakeholder_answer,
        source_statement_id=f"msg#{chat_id[:8]}",
        project_id=project_id,
        domain_prefix="ONB"
    )
    assert len(extracted_reqs) >= 5

    # Persist extracted requirements & initial versions
    for req in extracted_reqs:
        rm = RequirementModel(
            id=req.id,
            project_id=project_id,
            statement=req.statement,
            category=req.category.value,
            priority=req.priority.value,
            version=1,
            status="draft",
            source_statement_id=req.source_statement_id,
            business_justification=req.business_justification,
        )
        rv = RequirementVersion(
            id=str(uuid.uuid4()),
            requirement_id=req.id,
            version=1,
            statement=req.statement,
            category=req.category.value,
            priority=req.priority.value,
            status="draft",
            changed_by="RequirementEngineerAgent",
            change_reason="Initial extraction",
        )
        db.add_all([rm, rv])
    db.commit()

    record_audit_event(
        db=db,
        event=AuditEventType.EXTRACTION.value,
        actor="RequirementEngineerAgent",
        payload={"total_extracted": len(extracted_reqs)},
        chat_id=chat_id,
    )

    # Stage 3: Quality Analysis Engine (Completeness, Ambiguity, Conflicts)
    db_reqs = db.query(RequirementModel).filter(RequirementModel.project_id == project_id).all()
    analysis_issues = analysis_engine.analyze_project(
        project_id=project_id,
        requirements=db_reqs,
        db=db
    )
    assert isinstance(analysis_issues, list)

    record_audit_event(
        db=db,
        event=AuditEventType.ANALYSIS.value,
        actor="RequirementAnalysisAgent",
        payload={"issues_found": len(analysis_issues)},
        chat_id=chat_id,
    )

    # Stage 4: Compliance, Security, Privacy, and Risk Analysis
    compliance_result = compliance_security_risk_agent.analyze_compliance_and_risk(
        requirements=extracted_reqs,
        project_id=project_id,
    )
    assert len(compliance_result["compliance_mappings"]) > 0
    assert len(compliance_result["risks"]) > 0
    assert "disclaimer" in compliance_result

    for m in compliance_result["compliance_mappings"]:
        db.add(ComplianceMappingModel(
            id=m["id"],
            requirement_id=m["requirement_id"],
            project_id=project_id,
            regulation_name=m["regulation_name"],
            section_reference=m["section_reference"],
            citation_quote=m.get("citation_quote") or "Mandatory statutory regulatory standard clause.",
            citation_doc_id=m.get("citation_doc_id") or "DOC-REG",
            citation_verified=m.get("citation_verified", True),
            compliance_status=m.get("compliance_status", "compliant"),
            control_required=m.get("control_required") or "Implement mandatory statutory controls.",
            confidence_score=m.get("confidence_score", 1.0),
        ))
    for r in compliance_result["risks"]:
        prob = int(r.get("probability", 3))
        imp = int(r.get("impact", 4))
        score = r.get("risk_score") or (prob * imp)
        sev = r.get("severity") or ("critical" if score >= 20 else "high" if score >= 12 else "medium" if score >= 6 else "low")
        db.add(RiskModel(
            id=r["id"],
            project_id=project_id,
            requirement_id=r.get("requirement_id"),
            title=r["title"],
            category=r["category"],
            probability=prob,
            impact=imp,
            risk_score=score,
            severity=sev,
            mitigation=r["mitigation"],
            owner=r.get("owner", "Compliance & Risk Team"),
            status=r.get("status", "identified"),
        ))
    db.commit()

    record_audit_event(
        db=db,
        event=AuditEventType.COMPLIANCE_MAPPING.value,
        actor="ComplianceSecurityRiskAgent",
        payload={"mappings": len(compliance_result["compliance_mappings"]), "risks": len(compliance_result["risks"])},
        chat_id=chat_id,
    )

    # Stage 5: Human Baseline Approval Gate
    gate = approval_gate_manager.create_approval_request(
        db=db,
        chat_id=chat_id,
        project_id=project_id,
        gate_type=GateType.BASELINE.value,
        subject_id=project_id,
        title="Stakeholder Baseline Approval for Digital Onboarding Requirements",
        description="Review and sign-off of initial onboarding baseline",
        required_role=ActingRole.PRODUCT_OWNER.value,
        evidence_data={"total_requirements": len(extracted_reqs)},
    )
    assert gate.status == ApprovalStatus.PENDING.value

    # Reviewer accepts baseline
    approval_resp = approval_gate_manager.process_decision(
        db=db,
        approval_id=gate.id,
        action=ApprovalAction.ACCEPT.value,
        acting_role=ActingRole.PRODUCT_OWNER.value,
        comment="Approved standard KYC onboarding requirements baseline.",
    )
    assert approval_resp["status"] == ApprovalStatus.APPROVED.value

    # Update requirements to approved
    db.query(RequirementModel).filter(RequirementModel.project_id == project_id).update({"status": "approved"})
    db.commit()

    record_audit_event(
        db=db,
        event=AuditEventType.APPROVAL_DECISION.value,
        actor="ProductOwner",
        payload={"gate": GateType.BASELINE.value, "status": ApprovalStatus.APPROVED.value},
        chat_id=chat_id,
    )

    # Stage 6: SDLC Recommendation & Challenge Loop
    sdlc_res = sdlc_agent.recommend_sdlc(
        requirements=extracted_reqs,
        project_id=project_id,
        chat_id=chat_id,
    )
    assert sdlc_res.selected_model is not None
    assert len(sdlc_res.rankings) > 0

    # Challenge SDLC: adjust regulatory oversight to maximum
    challenge_res = sdlc_agent.recommend_sdlc(
        requirements=extracted_reqs,
        project_id=project_id,
        chat_id=chat_id,
        factor_overrides={"regulatory_criticality": 5, "requirement_stability": 4},
    )
    assert len(challenge_res.rankings) > 0
    top_model_name = challenge_res.selected_model.value

    # Persist SDLC recommendation
    db_sdlc = SDLCRecommendationModel(
        id=f"SDLC-{uuid.uuid4().hex[:8]}",
        project_id=project_id,
        chat_id=chat_id,
        selected_model=top_model_name,
        rankings_json=json.dumps([r.model_dump(mode="json") for r in challenge_res.rankings]),
        factors_json=json.dumps({k: v.model_dump(mode="json") for k, v in challenge_res.factor_evaluations.items()}),
        explanation=challenge_res.explanation,
        workflow_json=json.dumps([w.model_dump(mode="json") for w in challenge_res.workflow]),
        is_approved=False
    )
    db.add(db_sdlc)
    db.commit()

    # 4-role multi-stakeholder sign-off
    sdlc_gate = approval_gate_manager.create_approval_request(
        db=db,
        chat_id=chat_id,
        project_id=project_id,
        gate_type=GateType.SDLC_SELECTION.value,
        subject_id=db_sdlc.id,
        title="SDLC Model Selection Sign-off",
        description="Multi-role sign-off for tailored SDLC methodology",
        required_role=ActingRole.PRODUCT_OWNER.value,
        evidence_data={"model": top_model_name},
    )
    for role in SDLC_MANDATORY_ROLES:
        approval_gate_manager.process_decision(
            db=db,
            approval_id=sdlc_gate.id,
            action=ApprovalAction.ACCEPT.value,
            acting_role=role,
            comment=f"Sign-off by {role} for regulated banking delivery.",
        )
    db.refresh(sdlc_gate)
    assert sdlc_gate.status == ApprovalStatus.APPROVED.value

    record_audit_event(
        db=db,
        event=AuditEventType.SDLC_RECOMMENDED.value,
        actor="SDLCAgent",
        payload={"top_model": top_model_name, "signed_off": True},
        chat_id=chat_id,
    )

    # Stage 7: Documentation Agent, 100% Traceability & 23-Section PDF Compilation
    doc_agent = DocumentationAgent()
    req_dicts = [
        {
            "id": r.id,
            "statement": r.statement,
            "category": r.category.value,
            "priority": r.priority.value,
            "source_statement_id": r.source_statement_id,
            "status": "approved",
            "acceptance_criteria": [
                {"given": ac.given, "when": ac.when, "then": ac.then}
                for ac in (r.acceptance_criteria or [])
            ]
        }
        for r in extracted_reqs
    ]
    project_data = {"id": project_id, "title": "Digital Banking KYC Onboarding", "version": 1}
    doc_result = doc_agent.compile_srs(
        db=db,
        chat_id=chat_id,
        project_data=project_data,
        requirements=req_dicts,
        compliance_mappings=compliance_result["compliance_mappings"],
        risks=compliance_result["risks"],
        sdlc_recommendation={"selected_model": top_model_name, "explanation": challenge_res.explanation},
        is_approved=True
    )
    assert doc_result["pdf_meta"]["is_approved"] is True
    pdf_path = doc_result["pdf_meta"]["file_path"]
    sha256 = doc_result["pdf_meta"]["sha256"]
    assert os.path.exists(pdf_path)

    # Verify PDF structure with 23 ISO/IEC/IEEE sections
    reader = PdfReader(pdf_path)
    assert len(reader.pages) >= 2
    full_pdf_text = " ".join([page.extract_text() or "" for page in reader.pages])

    required_sections = [
        "1. Document Control", "2. Executive Summary", "3. Purpose", "4. Scope",
        "5. Definitions, Acronyms", "6. References, Statutory", "7. Product Perspective",
        "8. Product Functions Overview", "9. User Classes", "10. Operating Environment",
        "11. Design, Implementation", "12. Assumptions", "13. External Interface",
        "14. System Functional Requirements Catalog", "15. User Stories", "16. Use Case",
        "17. Process Workflows", "18. Data Requirements", "19. Non-Functional Quality",
        "20. Statutory & Regulatory Compliance Matrix", "21. Threat & Risk Register",
        "22. Tailored SDLC Methodology", "23. Requirements Traceability Matrix"
    ]
    for sec in required_sections:
        assert sec in full_pdf_text, f"Section missing from generated PDF: '{sec}'"

    record_audit_event(
        db=db,
        event=AuditEventType.DOCUMENT_GENERATED.value,
        actor="DocumentationAgent",
        payload={"file_path": pdf_path, "sha256": sha256},
        chat_id=chat_id,
    )

    # Stage 8: Verify Complete Tamper-Evident Audit Chain Integrity
    is_valid, err, tampered_id = verify_audit_chain(db=db, chat_id=None)
    assert is_valid is True
    assert err is None
    assert tampered_id is None

    return {
        "chat_id": chat_id,
        "project_id": project_id,
        "num_requirements": len(extracted_reqs),
        "pdf_path": pdf_path,
        "sha256": sha256,
    }


def test_e2e_section33_walkthrough_run_1(db_session):
    """E2E Run 1 of 3: Digital banking customer onboarding walkthrough."""
    res = execute_section33_walkthrough(db_session, run_index=1)
    assert res["num_requirements"] >= 5
    assert os.path.exists(res["pdf_path"])


def test_e2e_section33_walkthrough_run_2(db_session):
    """E2E Run 2 of 3: Consecutive repeat run verifying deterministic stability."""
    res = execute_section33_walkthrough(db_session, run_index=2)
    assert res["num_requirements"] >= 5
    assert os.path.exists(res["pdf_path"])


def test_e2e_section33_walkthrough_run_3(db_session):
    """E2E Run 3 of 3: Third consecutive green run per Master Plan checkpoint."""
    res = execute_section33_walkthrough(db_session, run_index=3)
    assert res["num_requirements"] >= 5
    assert os.path.exists(res["pdf_path"])


def test_resilience_model_offline_fallback(monkeypatch, db_session):
    """Verifies system degrades gracefully to deterministic extractor when LLM is offline."""
    def offline_llm(*args, **kwargs):
        raise ModelServiceUnavailableError("Local Ollama connection refused on 127.0.0.1:11434")

    monkeypatch.setattr(llm_gateway, "complete_prompt", offline_llm)

    test_text = (
        "The system shall verify customer identity using UIDAI Aadhaar offline XML verification. "
        "The system shall validate customer PAN validity against NSDL database."
    )
    reqs = requirement_engineer_agent.extract_requirements_from_text(
        text=test_text,
        source_statement_id="msg#offline_test",
        project_id="proj-offline"
    )
    assert len(reqs) >= 2
    assert any("Aadhaar" in r.statement for r in reqs)


def test_resilience_empty_kb_graceful_handling(monkeypatch):
    """Verifies compliance & risk engine operates cleanly with empty retrieval results."""
    def empty_retrieve(*args, **kwargs):
        return []

    monkeypatch.setattr(hybrid_retriever, "retrieve", empty_retrieve)

    sample_reqs = [
        RequirementModel(
            id="REQ-TEST-001",
            project_id="proj-empty-kb",
            statement="The system shall store customer PAN and Aadhaar records in plain text.",
            category="Compliance",
            priority="High"
        )
    ]
    res = compliance_security_risk_agent.analyze_compliance_and_risk(
        requirements=sample_reqs,
        project_id="proj-empty-kb"
    )
    assert "compliance_mappings" in res
    assert "risks" in res
    # Deterministic rule engine catches the gap and generates risks even without RAG chunks
    assert len(res["compliance_mappings"]) > 0
    assert len(res["risks"]) > 0


def test_resilience_malicious_upload_rejected(client, db_session):
    """Verifies that executable and script uploads are rejected with HTTP 400."""
    chat = Chat(id="chat-upload-test", owner_token_hash=hashlib.sha256(b"test_phase16_cookie_xyz").hexdigest(), title="Upload Test")
    db_session.add(chat)
    db_session.commit()

    # 1. Malicious executable
    res = client.post(
        f"/api/chats/{chat.id}/upload",
        files={"file": ("ransomware.exe", b"MZ\x90\x00malicious_binary", "application/x-msdownload")},
    )
    assert res.status_code == 400
    assert "Disallowed file extension" in res.json()["detail"]

    # 2. Malicious bash script
    res = client.post(
        f"/api/chats/{chat.id}/upload",
        files={"file": ("exploit.sh", b"#!/bin/bash\nrm -rf /", "application/x-sh")},
    )
    assert res.status_code == 400
    assert "Disallowed file extension" in res.json()["detail"]

    # 3. Valid documentation file (.txt)
    res = client.post(
        f"/api/chats/{chat.id}/upload",
        files={"file": ("policy.txt", b"Standard digital onboarding policy text", "text/plain")},
    )
    assert res.status_code == 200
    assert res.json()["filename"] == "policy.txt"


def test_tenant_isolation_chat_access(client, db_session):
    """Verifies that an unauthorized tenant receives 404 when accessing another user's chat."""
    other_owner_hash = hashlib.sha256(b"foreign_tenant_cookie_999").hexdigest()
    foreign_chat = Chat(id="foreign-chat-001", owner_token_hash=other_owner_hash, title="Foreign Bank Chat")
    db_session.add(foreign_chat)
    db_session.commit()

    # Attempt to read foreign chat using current client session cookie
    res = client.get(f"/api/chats/{foreign_chat.id}")
    assert res.status_code == 404

    # Attempt to post message into foreign chat
    res = client.post(f"/api/chats/{foreign_chat.id}/messages", json={"content": "Attempted breach"})
    assert res.status_code == 404


def test_latency_profiling_per_stage(db_session):
    """Profiles latency of all 6 multi-agent stages and asserts responsive performance."""
    chat_id = "chat-latency-profile"
    project_id = "proj-latency-profile"
    chat = Chat(id=chat_id, owner_token_hash="tok", title="Latency Chat")
    project = Project(id=project_id, chat_id=chat_id, title="Latency Proj", domain="banking")
    db_session.add_all([chat, project])
    db_session.commit()

    sample_text = (
        "The system shall verify customer identity using UIDAI Aadhaar offline XML verification. "
        "The system shall validate customer PAN validity against NSDL database prior to activation. "
        "The system shall encrypt all customer KYC documents at rest using AES-256 field-level encryption. "
        "The system shall retain all records for five years in accordance with PMLA 2002."
    )

    timings = {}

    # Stage 1: Grouped Question Generation
    t0 = time.time()
    requirement_engineer_agent.generate_grouped_questions(sample_text)
    timings["Stage 1: Question Generation"] = (time.time() - t0) * 1000

    # Stage 2: Requirement Extraction
    t0 = time.time()
    reqs = requirement_engineer_agent.extract_requirements_from_text(
        sample_text, source_statement_id="msg#lat", project_id=project_id
    )
    timings["Stage 2: Extraction"] = (time.time() - t0) * 1000

    for r in reqs:
        db_session.add(RequirementModel(
            id=r.id, project_id=project_id, statement=r.statement,
            category=r.category.value, priority=r.priority.value, version=1, status="approved"
        ))
    db_session.commit()

    # Stage 3: Quality Analysis
    t0 = time.time()
    db_reqs = db_session.query(RequirementModel).filter(RequirementModel.project_id == project_id).all()
    analysis_engine.analyze_project(project_id=project_id, requirements=db_reqs, db=db_session)
    timings["Stage 3: Quality Analysis"] = (time.time() - t0) * 1000

    # Stage 4: Compliance & Risk Mapping
    t0 = time.time()
    comp_res = compliance_security_risk_agent.analyze_compliance_and_risk(reqs, project_id=project_id)
    timings["Stage 4: Compliance & Risk"] = (time.time() - t0) * 1000

    for m in comp_res["compliance_mappings"]:
        db_session.add(ComplianceMappingModel(
            id=m["id"],
            requirement_id=m["requirement_id"],
            project_id=project_id,
            regulation_name=m["regulation_name"],
            section_reference=m["section_reference"],
            citation_quote=m.get("citation_quote") or "Mandatory statutory regulatory standard clause.",
            citation_doc_id=m.get("citation_doc_id") or "DOC-REG",
            citation_verified=True,
            compliance_status="compliant",
            control_required=m.get("control_required") or "Implement mandatory statutory controls.",
            confidence_score=m.get("confidence_score", 1.0),
        ))
    for r in comp_res["risks"]:
        prob = int(r.get("probability", 3))
        imp = int(r.get("impact", 4))
        score = r.get("risk_score") or (prob * imp)
        sev = r.get("severity") or ("critical" if score >= 20 else "high" if score >= 12 else "medium" if score >= 6 else "low")
        db_session.add(RiskModel(
            id=r["id"], project_id=project_id, title=r["title"],
            category=r["category"], probability=prob, impact=imp,
            risk_score=score, severity=sev,
            mitigation=r["mitigation"], owner=r.get("owner", "Compliance & Risk Team"), status=r.get("status", "identified")
        ))
    db_session.commit()

    # Stage 5: SDLC Engine Recommendation
    t0 = time.time()
    sdlc_agent.recommend_sdlc(requirements=reqs, project_id=project_id, chat_id=chat_id)
    timings["Stage 5: SDLC Recommendation"] = (time.time() - t0) * 1000

    # Stage 6: 23-Section PDF Compilation
    doc_agent = DocumentationAgent()
    t0 = time.time()
    req_dicts = [
        {"id": r.id, "statement": r.statement, "category": r.category.value, "priority": r.priority.value, "status": "approved"}
        for r in reqs
    ]
    doc_res = doc_agent.compile_srs(
        db=db_session,
        chat_id=chat_id,
        project_data={"id": project_id, "title": "Latency Proj", "version": 1},
        requirements=req_dicts,
        compliance_mappings=comp_res["compliance_mappings"],
        risks=comp_res["risks"],
        is_approved=True
    )
    timings["Stage 6: PDF SRS Generation"] = (time.time() - t0) * 1000

    print(f"\n[LATENCY PROFILING RESULTS]")
    for stage, ms in timings.items():
        print(f"  {stage}: {ms:.1f} ms")

    # Profiling assertions (all responsive on standard developer hardware with local offline LLM)
    assert timings["Stage 1: Question Generation"] < 5000.0   # < 5s
    assert timings["Stage 2: Extraction"] < 45000.0           # < 45s (CPU LLM inference)
    assert timings["Stage 3: Quality Analysis"] < 5000.0      # < 5s
    assert timings["Stage 4: Compliance & Risk"] < 15000.0    # < 15s (RAG retrieval + risk mapping)
    assert timings["Stage 5: SDLC Recommendation"] < 5000.0   # < 5s
    assert timings["Stage 6: PDF SRS Generation"] < 15000.0   # < 15s
    assert os.path.exists(doc_res["pdf_meta"]["file_path"])


def test_audit_hash_chain_tamper_detection(db_session):
    """Verifies that any manual manipulation of an audit record is immediately detected."""
    chat_id = "chat-tamper-test"
    record_audit_event(db_session, AuditEventType.SESSION_START.value, "User", {"action": "start"}, chat_id)
    record_audit_event(db_session, AuditEventType.EXTRACTION.value, "REAgent", {"count": 3}, chat_id)
    record_audit_event(db_session, AuditEventType.APPROVAL_DECISION.value, "PO", {"status": "approved"}, chat_id)

    # Initial chain is cryptographically intact
    valid, _, _ = verify_audit_chain(db_session, chat_id=chat_id)
    assert valid is True

    # Tamper with the middle audit record payload
    records = db_session.query(AuditLogModel).filter(AuditLogModel.chat_id == chat_id).order_by(AuditLogModel.created_at.asc()).all()
    records[1].payload_json = '{"count": 9999, "illicit_edit": true}'
    db_session.commit()

    # Verification must fail and identify the tampered record
    valid, err_msg, tampered_id = verify_audit_chain(db_session, chat_id=chat_id)
    assert valid is False
    assert tampered_id == records[1].id
    assert "Tampered row" in err_msg
