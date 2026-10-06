"""
Parser for plaintext and markdown documents (.txt, .md).
"""
import os
from typing import List
from backend.app.core.parsers.chunk import DocumentChunk


def parse_text_file(file_path: str, max_chunk_chars: int = 1500) -> List[DocumentChunk]:
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    filename = os.path.basename(file_path)
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()

    # Split by double newlines into logical paragraphs
    paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
    chunks: List[DocumentChunk] = []
    
    current_text = []
    current_len = 0
    chunk_index = 1

    for p in paragraphs:
        if current_len + len(p) > max_chunk_chars and current_text:
            chunk_str = "\n\n".join(current_text)
            chunks.append(DocumentChunk(
                chunk_id=f"{filename}#chunk-{chunk_index}",
                source_file=filename,
                text=chunk_str,
                page_or_section=f"Paragraph block {chunk_index}"
            ))
            chunk_index += 1
            current_text = [p]
            current_len = len(p)
        else:
            current_text.append(p)
            current_len += len(p)

    if current_text:
        chunk_str = "\n\n".join(current_text)
        chunks.append(DocumentChunk(
            chunk_id=f"{filename}#chunk-{chunk_index}",
            source_file=filename,
            text=chunk_str,
            page_or_section=f"Paragraph block {chunk_index}"
        ))

    return chunks
