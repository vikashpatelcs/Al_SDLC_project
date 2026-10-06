"""
Parser for EML email threads and interview transcripts.
"""
import email
from email import policy
import os
from typing import List
from backend.app.core.parsers.chunk import DocumentChunk


def parse_eml_file(file_path: str) -> List[DocumentChunk]:
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    filename = os.path.basename(file_path)
    with open(file_path, "rb") as f:
        msg = email.message_from_binary_file(f, policy=policy.default)

    subject = msg.get("Subject", "(No Subject)")
    sender = msg.get("From", "(Unknown Sender)")
    recipient = msg.get("To", "(Unknown Recipient)")
    date = msg.get("Date", "")

    header_summary = f"Email Thread: {subject}\nFrom: {sender}\nTo: {recipient}\nDate: {date}\n"

    body_text = ""
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            cdispo = str(part.get("Content-Disposition"))
            if ctype == "text/plain" and "attachment" not in cdispo:
                body_text += part.get_content() + "\n"
    else:
        body_text = msg.get_content()

    full_text = header_summary + "\n" + (body_text or "").strip()

    return [
        DocumentChunk(
            chunk_id=f"{filename}#body",
            source_file=filename,
            text=full_text.strip(),
            page_or_section="Email Body"
        )
    ]
