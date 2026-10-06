"""
Tamper-Evident Audit Hash Chain per Problem Statement §17 and Master Plan Phase 13.
Every audit log record contains a cryptographic SHA-256 hash linking to the previous row.
Includes full chain integrity verification with pinpoint tamper detection.
"""
import json
import hashlib
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, Any, Optional, Tuple, List
from sqlalchemy.orm import Session


GENESIS_HASH = "0" * 64


class AuditEventType(str, Enum):
    INTAKE = "intake"
    EXTRACTION = "extraction"
    ANALYSIS = "analysis"
    COMPLIANCE_MAPPING = "compliance_mapping"
    RISK_SCORED = "risk_scored"
    SDLC_RECOMMENDED = "sdlc_recommended"
    APPROVAL_DECISION = "approval_decision"
    REQUIREMENT_VERSIONED = "requirement_versioned"
    DOCUMENT_GENERATED = "document_generated"
    EXPORT = "export"
    TAMPER_DETECTED = "tamper_detected"
    SESSION_START = "session_start"


def canonical_json(data: Any) -> str:
    """Format payload into a deterministic, sorted, whitespace-compact JSON string."""
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def compute_audit_hash(
    prev_hash: str,
    timestamp_iso: str,
    event: str,
    actor: str,
    chat_id: Optional[str],
    canonical_payload: str
) -> str:
    """Compute deterministic SHA-256 hash of an audit chain block."""
    raw = f"{prev_hash}|{timestamp_iso}|{event}|{actor}|{chat_id or ''}|{canonical_payload}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def record_audit_event(
    db: Session,
    event: str,
    actor: str,
    payload: Dict[str, Any],
    chat_id: Optional[str] = None
):
    """
    Append an immutable event to the tamper-evident audit chain.
    Authoritatively links to the latest row's hash.
    """
    from backend.app.db.models import AuditLogModel

    # 1. Fetch latest audit record to establish previous hash
    last_record = (
        db.query(AuditLogModel)
        .order_by(AuditLogModel.created_at.desc(), AuditLogModel.id.desc())
        .first()
    )
    prev_hash = last_record.hash if last_record else GENESIS_HASH

    # 2. Prepare timestamp and payload
    now_dt = datetime.now(timezone.utc)
    timestamp_iso = now_dt.isoformat()
    payload_str = canonical_json(payload)

    # 3. Calculate cryptographic hash
    entry_hash = compute_audit_hash(
        prev_hash=prev_hash,
        timestamp_iso=timestamp_iso,
        event=event,
        actor=actor,
        chat_id=chat_id,
        canonical_payload=payload_str
    )

    # 4. Persist to database
    audit_entry = AuditLogModel(
        chat_id=chat_id,
        event=event,
        actor=actor,
        payload_json=payload_str,
        prev_hash=prev_hash,
        hash=entry_hash,
        created_at=now_dt
    )
    db.add(audit_entry)
    db.commit()
    db.refresh(audit_entry)
    return audit_entry


def verify_audit_chain(
    db: Session,
    chat_id: Optional[str] = None
) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Verifies cryptographic integrity of the audit log chain.
    Returns:
        (is_valid: bool, error_detail: Optional[str], tampered_id: Optional[str])
    """
    from backend.app.db.models import AuditLogModel

    query = db.query(AuditLogModel)
    if chat_id:
        query = query.filter(AuditLogModel.chat_id == chat_id)
    records: List[AuditLogModel] = query.order_by(AuditLogModel.created_at.asc(), AuditLogModel.id.asc()).all()

    if not records:
        return True, None, None

    expected_prev = GENESIS_HASH

    for idx, rec in enumerate(records):
        # 1. Verify prev_hash matches prior block (if global chain verification)
        if not chat_id and rec.prev_hash != expected_prev:
            return (
                False,
                f"Broken chain at index {idx} (ID {rec.id}): prev_hash '{rec.prev_hash}' does not match expected '{expected_prev}'.",
                rec.id
            )

        # 2. Verify row hash integrity
        timestamp_iso = rec.created_at.replace(tzinfo=timezone.utc).isoformat() if rec.created_at.tzinfo is None else rec.created_at.isoformat()
        computed_hash = compute_audit_hash(
            prev_hash=rec.prev_hash,
            timestamp_iso=timestamp_iso,
            event=rec.event,
            actor=rec.actor,
            chat_id=rec.chat_id,
            canonical_payload=rec.payload_json
        )

        if computed_hash != rec.hash:
            return (
                False,
                f"Tampered row at index {idx} (ID {rec.id}): stored hash '{rec.hash}' does not match computed hash '{computed_hash}'.",
                rec.id
            )

        expected_prev = rec.hash

    return True, None, None
