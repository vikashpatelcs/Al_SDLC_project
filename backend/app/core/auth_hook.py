"""
Authentication & Authorization Hook per Problem Statement §17 and Master Plan Phase 13.
Provides a pluggable get_current_principal hook that resolves anonymous session tokens today,
and seamlessly supports enterprise OIDC/JWT tokens in future phases without breaking changes.
"""
from dataclasses import dataclass
from typing import Optional
from fastapi import Request

from backend.app.config import settings
from backend.app.core.session import hash_token


@dataclass
class Principal:
    """Represents the authenticated or anonymous acting subject."""
    id: str
    role: str
    auth_type: str
    token_hash: str
    is_authenticated: bool = True


def get_current_principal(request: Request) -> Principal:
    """
    FastAPI dependency hook resolving the current principal.
    Extracts anonymous session token from cookie (or header fallback).
    """
    token = request.cookies.get(settings.SESSION_COOKIE_NAME)
    if not token:
        # Fallback to Authorization header if present
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1]

    if token:
        thash = hash_token(token)
        return Principal(
            id=f"user-{thash[:12]}",
            role="requirements_engineer",
            auth_type="anonymous_session",
            token_hash=thash,
            is_authenticated=True
        )

    # Ephemeral guest
    return Principal(
        id="anonymous-guest",
        role="guest",
        auth_type="none",
        token_hash="guest_unauthenticated",
        is_authenticated=False
    )
