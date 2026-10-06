"""
Parser for PDF requirements specifications and interview transcripts.
"""
import os
from typing import List
from pypdf import PdfReader
from backend.app.core.parsers.chunk import DocumentChunk


def parse_pdf_file(file_path: str) -> List[DocumentChunk]:
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    filename = os.path.basename(file_path)
    reader = PdfReader(file_path)
    chunks: List[DocumentChunk] = []

    for page_idx, page in enumerate(reader.pages, start=1):
        page_text = page.extract_text() or ""
        cleaned = page_text.strip()
        if cleaned:
            chunks.append(DocumentChunk(
                chunk_id=f"{filename}#page-{page_idx}",
                source_file=filename,
                text=cleaned,
                page_or_section=f"Page {page_idx}"
            ))

    return chunks
