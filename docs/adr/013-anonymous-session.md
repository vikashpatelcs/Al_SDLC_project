# ADR 013: Anonymous Session and State Isolation

- **Status**: Accepted
- **Date**: 2026-10-06

## Context
System specification mandates no login/registration screens, yet must prevent cross-user chat leakage and prepare for future enterprise IAM.

## Decision
Issue cryptographically secure anonymous session tokens via HttpOnly cookies. Store only SHA-256 token hashes in the database and enforce owner filtering on all queries.

## Consequences
Clean user isolation with zero login friction; architectural interface seamlessly maps to OIDC/OAuth2 bearer tokens in Phase 17.
