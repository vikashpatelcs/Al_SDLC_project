"""
Field-level encryption at rest for sensitive requirements and messages
per Problem Statement §17 and Master Plan Phase 13.
Uses AES-128-CBC / HMAC-SHA256 via cryptography.fernet with keys derived from SESSION_SECRET.
"""
import base64
import hashlib
from typing import Optional
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy.types import TypeDecorator, Text

from backend.app.config import settings


def _get_fernet() -> Fernet:
    """Derive a deterministic 32-byte URL-safe base64 key from configuration secret."""
    secret = getattr(settings, "ENCRYPTION_KEY", None) or settings.SESSION_SECRET
    key_bytes = hashlib.sha256(secret.encode("utf-8")).digest()
    fernet_key = base64.urlsafe_b64encode(key_bytes)
    return Fernet(fernet_key)


def encrypt_text(plaintext: Optional[str]) -> Optional[str]:
    """Encrypt plaintext string using Fernet."""
    if plaintext is None:
        return None
    if not isinstance(plaintext, str):
        plaintext = str(plaintext)
    f = _get_fernet()
    token = f.encrypt(plaintext.encode("utf-8"))
    return token.decode("utf-8")


def decrypt_text(ciphertext: Optional[str]) -> Optional[str]:
    """
    Decrypt Fernet ciphertext string.
    Gracefully returns original string if not encrypted (legacy data compatibility).
    """
    if ciphertext is None:
        return None
    if not isinstance(ciphertext, str):
        ciphertext = str(ciphertext)

    f = _get_fernet()
    try:
        decrypted = f.decrypt(ciphertext.encode("utf-8"))
        return decrypted.decode("utf-8")
    except (InvalidToken, ValueError, Exception):
        # Fallback for unencrypted legacy rows or test strings
        return ciphertext


class EncryptedText(TypeDecorator):
    """
    SQLAlchemy TypeDecorator providing transparent field-level encryption at rest.
    Stored on disk/DB as Fernet ciphertext (gAAAAA...), transparently decrypted in memory.
    """
    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None:
            return encrypt_text(value)
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            return decrypt_text(value)
        return value
