"""
Anonymous session management and owner token hashing.
Guarantees multi-tenant isolation without requiring login or registration.
"""
import hashlib
import secrets
from typing import Optional
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from backend.app.config import settings


def hash_token(token: str) -> str:
    """Compute deterministic SHA-256 hash of a session token."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class SessionMiddleware(BaseHTTPMiddleware):
    """
    Middleware ensuring every client possesses an anonymous session cookie.
    Extracts or creates a cryptographically secure token, hashes it,
    and sets request.state.owner_token_hash for downstream route handlers.
    """
    async def dispatch(self, request: Request, call_next):
        token = request.cookies.get(settings.SESSION_COOKIE_NAME)
        is_new_session = False

        if not token:
            token = secrets.token_urlsafe(32)
            is_new_session = True

        request.state.session_token = token
        request.state.owner_token_hash = hash_token(token)

        response: Response = await call_next(request)

        if is_new_session:
            response.set_cookie(
                key=settings.SESSION_COOKIE_NAME,
                value=token,
                max_age=settings.SESSION_COOKIE_MAX_AGE,
                httponly=True,
                samesite="lax",
                path="/",
            )

        return response


def get_current_owner_hash(request: Request) -> str:
    """FastAPI dependency to retrieve the current request's owner token hash."""
    if hasattr(request.state, "owner_token_hash"):
        return request.state.owner_token_hash
    # Fallback if accessed outside middleware
    token = request.cookies.get(settings.SESSION_COOKIE_NAME, "anonymous-default")
    return hash_token(token)
