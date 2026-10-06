"""
Unit and Integration Tests for Phase 7: RAG + Financial Knowledge Base.
Verifies:
1. Manifest integrity and SHA-256 validation (>= 8 official documents).
2. Section-aware chunking preserving hierarchy and heading paths.
3. Authoritative ingestion and KnowledgeBaseVersion recording in SQLite.
4. Strict security isolation (uploads CANNOT enter authoritative collection).
5. Hybrid retrieval recall@5 >= 0.80 on 30 evaluation queries.
6. Citation verifier accepting valid citations and strictly rejecting fabricated ones.
"""
import os
import pytest
from sqlalchemy.orm import Session

from backend.app.db.session import SessionLocal
from backend.app.db.models import KnowledgeBaseVersion
from backend.app.rag.kb_registry import kb_registry
from backend.app.rag.chunker import section_chunker
from backend.app.rag.ingest import kb_ingestion_pipeline, SecurityError, AUTHORITATIVE_COLLECTION
from backend.app.rag.retriever import hybrid_retriever
from backend.app.rag.verifier import citation_verifier
from ml.eval.eval_retrieval import evaluate_retrieval


@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_manifest_integrity_and_hashes():
    """Verify >= 8 official documents in manifest and all SHA-256 hashes match files on disk."""
    assert len(kb_registry.documents) >= 8, f"Expected >= 8 documents, found {len(kb_registry.documents)}"

    integrity_results = kb_registry.verify_integrity()
    assert len(integrity_results) >= 8
    for doc_id, is_valid in integrity_results.items():
        assert is_valid is True, f"SHA-256 mismatch or missing file for {doc_id}"


def test_section_aware_chunking():
    """Verify chunks preserve legal hierarchy breadcrumbs (heading_path) and section numbers."""
    doc = kb_registry.get_document("DOC-RBI-KYC-2016")
    assert doc is not None

    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
    file_path = os.path.join(project_root, doc["file_path"])
    with open(file_path, "r", encoding="utf-8") as f:
        text = f.read()

    chunks = section_chunker.chunk_document(text, doc)
    assert len(chunks) >= 4

    # Verify heading paths contain chapter and section breadcrumbs
    paths = [c.heading_path for c in chunks]
    assert any("CHAPTER III" in p and "Section 16" in p for p in paths)
    assert any("CHAPTER III" in p and "Section 18" in p for p in paths)

    # Verify contextualized text prepends regulator and circular number
    assert all("Reserve Bank of India" in c.text for c in chunks)
    assert all(doc["circular_number"] in c.text for c in chunks)


def test_authoritative_ingest_and_version_recording(db_session):
    """Verify full KB ingest populates Chroma collection and logs version in SQLite."""
    res = kb_ingestion_pipeline.ingest_full_knowledge_base(db_session=db_session)
    assert res["documents_ingested"] >= 8
    assert res["total_chunks"] >= 30
    assert res["collection_name"] == AUTHORITATIVE_COLLECTION

    # Check SQLite record
    kb_ver = db_session.query(KnowledgeBaseVersion).filter(
        KnowledgeBaseVersion.collection_name == AUTHORITATIVE_COLLECTION
    ).first()
    assert kb_ver is not None
    assert kb_ver.documents_count >= 8
    assert kb_ver.total_chunks == res["total_chunks"]
    assert kb_ver.manifest_hash == kb_registry.compute_manifest_hash()


def test_authoritative_collection_isolation():
    """CRITICAL SECURITY TEST: Ensure unmanifested user uploads CANNOT enter authoritative collection."""
    fake_upload_path = "storage/uploads/user_uploaded_statement.txt"

    # Attempting to ingest unmanifested file must raise SecurityError
    with pytest.raises(SecurityError) as exc_info:
        kb_ingestion_pipeline.ingest_single_document(fake_upload_path)

    assert "Security Violation" in str(exc_info.value)
    assert "Uploaded documents cannot enter the authoritative collection" in str(exc_info.value)


def test_hybrid_retrieval_recall_at_5():
    """Verify Recall@5 >= 0.80 across the 30 benchmark queries."""
    results = evaluate_retrieval(top_k=5)
    assert results["total"] == 30
    assert results["recall_at_k"] >= 0.80, f"Recall@5 {results['recall_at_k']:.2f} < 0.80"
    assert results["mrr"] >= 0.80


def test_citation_verifier_valid_citations():
    """Verify authentic citations return status == 'VERIFIED'."""
    valid_citations = [
        "RBI Master Direction - Know Your Customer (KYC) Direction, 2016 Section 16",
        "Digital Personal Data Protection Act, 2023 Section 6",
        "Prevention of Money-Laundering Act, 2002 Section 12",
        "RBI/2015-16/418 DBS.CO/CSITE/BC.11/33.01.001/2015-16 2.1",
        "NPCI/UPI/OC-87/2020-21 4.1",
        "RBI/2022-23/92 Master Direction DOR.AUT.REC.No.27/24.01.041/2022-23 Section 10",
    ]

    for cit in valid_citations:
        res = citation_verifier.verify_citation(cit)
        assert res["status"] == "VERIFIED", f"Expected VERIFIED for '{cit}', got: {res}"
        assert res["is_valid"] is True
        assert res["matched_doc_id"] is not None


def test_citation_verifier_rejects_fake_citations():
    """CRITICAL TEST: Verify fabricated or hallucinated citations are strictly REJECTED."""
    fake_citations = [
        "RBI Circular RBI/2099/NONEXISTENT-999 regarding instant settlement",
        "Section 9999 of the Prevention of Money Laundering Act, 2002",
        "Digital Personal Data Protection Act, 2023 Section 888",
        "European Union General Data Protection Regulation Article 17",  # Non-allowlisted foreign regulation
        "Fabricated Banking Directive 2025/999",
    ]

    for fake in fake_citations:
        res = citation_verifier.verify_citation(fake)
        assert res["status"] == "REJECTED", f"Expected REJECTED for fabricated citation '{fake}', got: {res}"
        assert res["is_valid"] is False
        assert "Fabricated" in res["reason"] or "not found" in res["reason"]
