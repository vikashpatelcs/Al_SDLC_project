"""
Knowledge Base Registry for Phase 7.
Enforces allowlist verification from kb/manifest.yaml, checks SHA-256 integrity,
handles supersede logic, and synchronizes KnowledgeBaseVersion with SQLite.
"""
import hashlib
import os
import uuid
from typing import Dict, List, Optional, Any
import yaml
from sqlalchemy.orm import Session

from backend.app.db.models import KnowledgeBaseVersion


DEFAULT_MANIFEST_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../../../kb/manifest.yaml")
)


class KBRegistry:
    def __init__(self, manifest_path: str = DEFAULT_MANIFEST_PATH):
        self.manifest_path = manifest_path
        self.manifest_data = self._load_manifest()
        self.documents: List[Dict[str, Any]] = self.manifest_data.get("documents", [])
        self._doc_by_id: Dict[str, Dict[str, Any]] = {d["id"]: d for d in self.documents}
        self._doc_by_path: Dict[str, Dict[str, Any]] = {
            os.path.normpath(d["file_path"]): d for d in self.documents
        }

    def _load_manifest(self) -> Dict[str, Any]:
        if not os.path.exists(self.manifest_path):
            raise FileNotFoundError(f"Knowledge base manifest not found: {self.manifest_path}")
        with open(self.manifest_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    def reload(self):
        self.manifest_data = self._load_manifest()
        self.documents = self.manifest_data.get("documents", [])
        self._doc_by_id = {d["id"]: d for d in self.documents}
        self._doc_by_path = {os.path.normpath(d["file_path"]): d for d in self.documents}

    def get_document(self, doc_id: str) -> Optional[Dict[str, Any]]:
        return self._doc_by_id.get(doc_id)

    def get_document_by_circular(self, circular_query: str) -> Optional[Dict[str, Any]]:
        """Match document by circular number or partial citation."""
        query_norm = circular_query.lower().strip()
        for doc in self.documents:
            circ = doc.get("circular_number", "").lower()
            title = doc.get("title", "").lower()
            if query_norm in circ or circ in query_norm or query_norm in title:
                return doc
        return None

    def is_allowlisted(self, file_path_or_id: str) -> bool:
        """Verify whether a file path or document ID is registered in the authoritative manifest."""
        if file_path_or_id in self._doc_by_id:
            return True
        norm = os.path.normpath(file_path_or_id)
        # Check relative or basename matches
        for stored_path in self._doc_by_path:
            if norm.endswith(stored_path) or stored_path.endswith(norm) or os.path.basename(norm) == os.path.basename(stored_path):
                return True
        return False

    def verify_integrity(self, base_dir: Optional[str] = None) -> Dict[str, bool]:
        """Verify that all manifest documents exist and match their recorded SHA-256 hash."""
        results = {}
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
        
        for doc in self.documents:
            rel_path = doc["file_path"]
            abs_path = os.path.join(project_root, rel_path)
            if not os.path.exists(abs_path):
                results[doc["id"]] = False
                continue

            with open(abs_path, "rb") as f:
                computed_hash = hashlib.sha256(f.read()).hexdigest()
            results[doc["id"]] = (computed_hash == doc["sha256"])

        return results

    def compute_manifest_hash(self) -> str:
        """Compute SHA-256 hash of manifest file content."""
        with open(self.manifest_path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()

    def record_version(
        self,
        db: Session,
        version_tag: str = "v2026.10",
        total_chunks: int = 0
    ) -> KnowledgeBaseVersion:
        """Record or update knowledge base version entry in SQLite database."""
        from backend.app.db.session import engine, Base
        Base.metadata.create_all(bind=engine)

        manifest_hash = self.compute_manifest_hash()
        
        # Check if already recorded
        existing = db.query(KnowledgeBaseVersion).filter(
            KnowledgeBaseVersion.manifest_hash == manifest_hash
        ).first()

        if existing:
            existing.total_chunks = total_chunks
            db.commit()
            return existing

        kb_version = KnowledgeBaseVersion(
            id=str(uuid.uuid4()),
            version_tag=version_tag,
            manifest_hash=manifest_hash,
            documents_count=len(self.documents),
            total_chunks=total_chunks,
            collection_name="financial_kb_authoritative"
        )
        db.add(kb_version)
        db.commit()
        return kb_version


# Singleton instance
kb_registry = KBRegistry()
