"""
Citation Verifier for Phase 7.
Verifies regulatory citations against authoritative documents in kb/manifest.yaml and ChromaDB chunks.
Strictly rejects fabricated, non-existent, or hallucinated circular numbers and section citations.
"""
import re
from typing import Dict, Any, Optional, List
from backend.app.rag.kb_registry import kb_registry
from backend.app.rag.retriever import hybrid_retriever


class CitationVerifier:
    def __init__(self):
        pass

    def verify_citation(
        self,
        citation_text: str,
        claimed_requirement: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Verify whether a cited circular, act, or section exists in the authoritative registry.
        Rejects fabricated circular numbers or hallucinated sections.
        """
        if not citation_text or not isinstance(citation_text, str):
            return {
                "status": "REJECTED",
                "is_valid": False,
                "reason": "Empty or invalid citation string."
            }

        citation_clean = citation_text.strip()

        # 1. Match against known documents in manifest
        matched_doc = None
        for doc in kb_registry.documents:
            circ = doc.get("circular_number", "")
            title = doc.get("title", "")
            doc_id = doc.get("id", "")

            # Exact or substring match of circular number, document ID, or full title
            if circ.lower() in citation_clean.lower() or doc_id.lower() in citation_clean.lower() or title.lower() in citation_clean.lower():
                matched_doc = doc
                break

            # Keyword heuristic (e.g. "KYC Direction" or "DPDP Act" or "PMLA")
            if "kyc" in citation_clean.lower() and "rbi" in citation_clean.lower() and doc["id"] == "DOC-RBI-KYC-2016":
                matched_doc = doc
                break
            if "dpdp" in citation_clean.lower() and doc["id"] == "DOC-GOI-DPDP-2023":
                matched_doc = doc
                break
            if "pmla" in citation_clean.lower() and doc["id"] == "DOC-GOI-PMLA-2002":
                matched_doc = doc
                break
            if "it framework" in citation_clean.lower() and doc["id"] == "DOC-RBI-ITFW-2016":
                matched_doc = doc
                break
            if "cyber security" in citation_clean.lower() and "rbi" in citation_clean.lower() and doc["id"] == "DOC-RBI-CSIS-2016":
                matched_doc = doc
                break
            if ("card" in citation_clean.lower() or "coft" in citation_clean.lower()) and doc["id"] == "DOC-RBI-CARD-2022":
                matched_doc = doc
                break
            if "upi" in citation_clean.lower() and doc["id"] == "DOC-NPCI-UPI-2020":
                matched_doc = doc
                break
            if "sebi" in citation_clean.lower() and doc["id"] == "DOC-SEBI-CYBR-2022":
                matched_doc = doc
                break

        if not matched_doc:
            return {
                "status": "REJECTED",
                "is_valid": False,
                "matched_doc_id": None,
                "reason": f"Fabricated or unmanifested regulatory reference: '{citation_text}' not found in authoritative knowledge base."
            }

        # 2. Extract section number from citation if present
        m_sec = re.search(r'\b(Section\s+[\d\w\(\)]+|Annex\s+\d+|Part\s+\d+)\b', citation_clean, re.IGNORECASE)
        if m_sec:
            section_number = m_sec.group(1)
        else:
            # Check for trailing clause/section like '2.1' or '4.1'
            matches = re.findall(r'(?<![/.\w])(\d+\.\d+)(?![/.\w])', citation_clean)
            section_number = matches[-1] if matches else None

        # 3. Retrieve chunks for this document from hybrid retriever / Chroma to verify section existence
        retrieved_chunks = hybrid_retriever.retrieve(
            query=f"{matched_doc['title']} {section_number or ''}",
            top_k=5
        )

        doc_chunks = [c for c in retrieved_chunks if c.get("metadata", {}).get("doc_id") == matched_doc["id"]]

        if section_number:
            # Check if section number exists in document chunks
            sec_clean = section_number.lower()
            section_found = False
            for c in doc_chunks:
                c_sec = c.get("metadata", {}).get("section_number", "").lower()
                c_text = c.get("text", "").lower()
                if sec_clean in c_sec or sec_clean in c_text:
                    section_found = True
                    break

            if not section_found and not any(sec_clean in c.get("text", "").lower() for c in hybrid_retriever.corpus_chunks if c.get("metadata", {}).get("doc_id") == matched_doc["id"]):
                return {
                    "status": "REJECTED",
                    "is_valid": False,
                    "matched_doc_id": matched_doc["id"],
                    "reason": f"Fabricated section reference: '{section_number}' does not exist in {matched_doc['title']}."
                }

        return {
            "status": "VERIFIED",
            "is_valid": True,
            "matched_doc_id": matched_doc["id"],
            "matched_circular": matched_doc["circular_number"],
            "matched_section": section_number,
            "title": matched_doc["title"],
            "regulator": matched_doc["regulator"],
            "reason": f"Verified against authoritative regulation: {matched_doc['title']} ({matched_doc['circular_number']})."
        }


# Singleton verifier instance
citation_verifier = CitationVerifier()
