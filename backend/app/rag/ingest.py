"""
Ingestion Pipeline for Authoritative Regulatory Knowledge Base (Phase 7).
Enforces:
1. Manifest allowlist verification (untrusted uploads CANNOT enter authoritative collection).
2. Section-aware chunking with hierarchy preservation.
3. ChromaDB storage in collection 'financial_kb_authoritative'.
4. Synchronization of KnowledgeBaseVersion in SQLite.
"""
import os
import sys
from typing import List, Dict, Any, Optional

# Ensure project root in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

import chromadb
from chromadb.config import Settings
from sqlalchemy.orm import Session

from backend.app.rag.kb_registry import kb_registry
from backend.app.rag.chunker import section_chunker, SectionChunk
from backend.app.db.session import SessionLocal


CHROMA_PERSIST_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../../../storage/chroma")
)
AUTHORITATIVE_COLLECTION = "financial_kb_authoritative"


class SecurityError(Exception):
    """Raised when an unmanifested document attempts to enter the authoritative KB."""
    pass


class KBIngestionPipeline:
    def __init__(self, persist_dir: str = CHROMA_PERSIST_DIR):
        self.persist_dir = persist_dir
        os.makedirs(self.persist_dir, exist_ok=True)
        self.client = chromadb.PersistentClient(
            path=self.persist_dir,
            settings=Settings(anonymized_telemetry=False)
        )
        self.collection = self.client.get_or_create_collection(
            name=AUTHORITATIVE_COLLECTION,
            metadata={"description": "Authoritative Indian Financial Regulations and Circulars"}
        )

    def ingest_single_document(self, file_path_or_id: str, project_root: Optional[str] = None) -> List[SectionChunk]:
        """
        Ingest a single document into the authoritative collection with strict allowlist check.
        Rejects any document not listed in kb/manifest.yaml.
        """
        # 1. Enforce allowlist check (Checkpoint 5)
        if not kb_registry.is_allowlisted(file_path_or_id):
            raise SecurityError(
                f"Security Violation: '{file_path_or_id}' is not in kb/manifest.yaml. "
                "Uploaded documents cannot enter the authoritative collection."
            )

        # 2. Retrieve document metadata
        doc_meta = None
        for d in kb_registry.documents:
            if d["id"] == file_path_or_id or os.path.basename(d["file_path"]) == os.path.basename(file_path_or_id):
                doc_meta = d
                break

        if not doc_meta:
            raise SecurityError(f"Document metadata not found in manifest for '{file_path_or_id}'")

        if project_root is None:
            project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))

        abs_file_path = os.path.join(project_root, doc_meta["file_path"])
        if not os.path.exists(abs_file_path):
            raise FileNotFoundError(f"Authoritative document file missing: {abs_file_path}")

        with open(abs_file_path, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()

        # 3. Section-aware chunking
        chunks = section_chunker.chunk_document(text, doc_meta)
        if not chunks:
            return []

        # 4. Upsert into Chroma
        ids = [c.chunk_id for c in chunks]
        documents = [c.text for c in chunks]
        metadatas = [
            {
                "doc_id": c.doc_id,
                "title": c.title,
                "regulator": c.regulator,
                "circular_number": c.circular_number,
                "section_number": c.section_number,
                "heading_path": c.heading_path,
                "content_hash": c.content_hash
            }
            for c in chunks
        ]

        self.collection.upsert(
            ids=ids,
            documents=documents,
            metadatas=metadatas
        )

        return chunks

    def ingest_full_knowledge_base(self, db_session: Optional[Session] = None) -> Dict[str, Any]:
        """
        Ingest all 8 documents from kb/manifest.yaml and record version in SQLite.
        """
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
        total_chunks = 0
        ingested_docs = 0

        for doc_meta in kb_registry.documents:
            chunks = self.ingest_single_document(doc_meta["id"], project_root)
            total_chunks += len(chunks)
            ingested_docs += 1

        # Record version in SQLite
        should_close_db = False
        if db_session is None:
            db_session = SessionLocal()
            should_close_db = True

        try:
            kb_version = kb_registry.record_version(
                db=db_session,
                version_tag="v2026.10",
                total_chunks=total_chunks
            )
            version_id = kb_version.id
        finally:
            if should_close_db:
                db_session.close()

        return {
            "documents_ingested": ingested_docs,
            "total_chunks": total_chunks,
            "collection_name": AUTHORITATIVE_COLLECTION,
            "version_id": version_id
        }


# Singleton pipeline instance
kb_ingestion_pipeline = KBIngestionPipeline()


if __name__ == "__main__":
    print("Running authoritative KB ingestion ...")
    res = kb_ingestion_pipeline.ingest_full_knowledge_base()
    print(f"Ingested {res['documents_ingested']} documents with {res['total_chunks']} chunks. Version recorded.")
