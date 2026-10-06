"""
Section-Aware Chunker for Regulatory Documents.
Preserves legal hierarchy breadcrumbs (heading_path) and section numbers
so that chunks retain full regulatory context.
"""
import hashlib
import re
from typing import List, Dict, Any


class SectionChunk:
    def __init__(
        self,
        chunk_id: str,
        doc_id: str,
        title: str,
        regulator: str,
        circular_number: str,
        section_number: str,
        heading_path: str,
        text: str
    ):
        self.chunk_id = chunk_id
        self.doc_id = doc_id
        self.title = title
        self.regulator = regulator
        self.circular_number = circular_number
        self.section_number = section_number
        self.heading_path = heading_path
        self.text = text
        self.content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "doc_id": self.doc_id,
            "title": self.title,
            "regulator": self.regulator,
            "circular_number": self.circular_number,
            "section_number": self.section_number,
            "heading_path": self.heading_path,
            "text": self.text,
            "content_hash": self.content_hash
        }


class SectionAwareChunker:
    # Regex patterns for chapters, sections, annexes
    CHAPTER_PATTERN = re.compile(r'^(CHAPTER\s+[IVXLCDM\d]+|ANNEX\s+\d+|SECTION\s+[IVXLCDM]+)(?::\s*(.*))?$', re.IGNORECASE)
    SECTION_PATTERN = re.compile(r'^(Section\s+[\d\w\(\)]+|[\d\.]+\s+[A-Z][\w\s]+)(?::\s*(.*))?$', re.IGNORECASE)

    def chunk_document(self, text: str, doc_metadata: Dict[str, Any]) -> List[SectionChunk]:
        doc_id = doc_metadata.get("id", "DOC-UNKNOWN")
        doc_title = doc_metadata.get("title", "")
        regulator = doc_metadata.get("regulator", "")
        circ_num = doc_metadata.get("circular_number", "")

        lines = text.splitlines()
        chunks: List[SectionChunk] = []

        current_chapter = ""
        current_section = ""
        current_heading_path = ""
        current_lines: List[str] = []
        chunk_counter = 1

        def flush_chunk():
            nonlocal chunk_counter, current_lines
            if not current_lines:
                return
            chunk_body = "\n".join(current_lines).strip()
            if not chunk_body:
                return

            sec_clean = current_section if current_section else f"Part {chunk_counter}"
            # Extract section number like "Section 16" or "1.1"
            sec_num_match = re.search(r'(Section\s+[\d\w]+|\b\d+\.\d+\b)', sec_clean, re.IGNORECASE)
            sec_num = sec_num_match.group(0) if sec_num_match else sec_clean

            h_path = current_heading_path if current_heading_path else doc_title

            # Prepend breadcrumbs context to text so retriever has full semantic context
            contextualized_text = f"[{regulator}] {doc_title}\nCircular: {circ_num}\nPath: {h_path}\n\n{chunk_body}"

            chunk_id = f"{doc_id}#sec-{chunk_counter:03d}"
            chunks.append(SectionChunk(
                chunk_id=chunk_id,
                doc_id=doc_id,
                title=doc_title,
                regulator=regulator,
                circular_number=circ_num,
                section_number=sec_num,
                heading_path=h_path,
                text=contextualized_text
            ))
            chunk_counter += 1
            current_lines = []

        for line in lines:
            line_str = line.strip()
            if not line_str:
                if current_lines:
                    current_lines.append("")
                continue

            # Check chapter match
            chap_match = self.CHAPTER_PATTERN.match(line_str)
            if chap_match:
                flush_chunk()
                current_chapter = line_str
                current_section = ""
                current_heading_path = current_chapter
                continue

            # Check section match
            sec_match = self.SECTION_PATTERN.match(line_str)
            if sec_match:
                flush_chunk()
                current_section = line_str
                if current_chapter:
                    current_heading_path = f"{current_chapter} > {current_section}"
                else:
                    current_heading_path = current_section
                current_lines.append(line_str)
                continue

            current_lines.append(line_str)

        flush_chunk()
        return chunks


# Singleton chunker instance
section_chunker = SectionAwareChunker()
