"""
Document Parser Factory.
Dispatches uploaded files to appropriate parsers, enforces pre-flight PII masking,
and flags prompt injection attempts before requirement extraction.
"""
import os
from typing import List, Optional

from backend.app.core.parsers.chunk import DocumentChunk
from backend.app.core.parsers.text_parser import parse_text_file
from backend.app.core.parsers.csv_parser import parse_csv_file
from backend.app.core.parsers.docx_parser import parse_docx_file
from backend.app.core.parsers.pdf_parser import parse_pdf_file
from backend.app.core.parsers.eml_parser import parse_eml_file
from backend.app.core.security.masking import pii_masker
from backend.app.core.security.injection import injection_scanner


def parse_and_mask_document(file_path: str, mime_type: Optional[str] = None) -> List[DocumentChunk]:
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Uploaded file does not exist: {file_path}")

    ext = os.path.splitext(file_path)[1].lower()

    if ext in [".txt", ".md"]:
        raw_chunks = parse_text_file(file_path)
    elif ext == ".csv":
        raw_chunks = parse_csv_file(file_path)
    elif ext == ".docx":
        raw_chunks = parse_docx_file(file_path)
    elif ext == ".pdf":
        raw_chunks = parse_pdf_file(file_path)
    elif ext in [".eml", ".msg"]:
        raw_chunks = parse_eml_file(file_path)
    else:
        # Fallback to plain text read
        raw_chunks = parse_text_file(file_path)

    # Pre-flight PII masking and prompt injection scanning on all chunks
    safe_chunks: List[DocumentChunk] = []
    for chunk in raw_chunks:
        # 1. Injection scan
        is_flagged, matches = injection_scanner.scan(chunk.text)
        cleaned_text = chunk.text
        if is_flagged:
            # Prepend security warning to avoid injection hijacking extraction
            cleaned_text = f"[UNTRUSTED CONTENT FILTERED: {', '.join(matches)}]\n" + cleaned_text

        # 2. PII masking
        masked_text, _ = pii_masker.mask(cleaned_text)

        safe_chunks.append(DocumentChunk(
            chunk_id=chunk.chunk_id,
            source_file=chunk.source_file,
            text=masked_text,
            page_or_section=chunk.page_or_section,
            is_masked=True
        ))

    return safe_chunks
