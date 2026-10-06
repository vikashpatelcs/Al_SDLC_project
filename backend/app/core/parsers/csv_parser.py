"""
Parser for CSV requirements spreadsheets.
"""
import csv
import os
from typing import List
from backend.app.core.parsers.chunk import DocumentChunk


def parse_csv_file(file_path: str, max_rows_per_chunk: int = 10) -> List[DocumentChunk]:
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    filename = os.path.basename(file_path)
    chunks: List[DocumentChunk] = []

    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.reader(f)
        rows = list(reader)

    if not rows:
        return []

    header = rows[0]
    data_rows = rows[1:]

    chunk_index = 1
    for i in range(0, len(data_rows), max_rows_per_chunk):
        batch = data_rows[i:i + max_rows_per_chunk]
        text_lines = [f"Table: {filename} (Columns: {', '.join(header)})"]
        for row_idx, r in enumerate(batch, start=i + 1):
            row_items = [f"{header[idx] if idx < len(header) else f'Col{idx}'}: {val}" for idx, val in enumerate(r)]
            text_lines.append(f"Row {row_idx}: " + "; ".join(row_items))

        chunks.append(DocumentChunk(
            chunk_id=f"{filename}#rows-{i + 1}-to-{min(i + max_rows_per_chunk, len(data_rows))}",
            source_file=filename,
            text="\n".join(text_lines),
            page_or_section=f"Rows {i + 1}-{min(i + max_rows_per_chunk, len(data_rows))}"
        ))
        chunk_index += 1

    return chunks
