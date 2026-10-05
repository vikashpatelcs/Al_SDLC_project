# ADR 003: Backend Architecture and Framework

- **Status**: Accepted
- **Date**: 2026-10-06

## Context
The backend must coordinate AI agents, execute deterministic rule checks, serve REST/SSE endpoints, and manage persistence in Python.

## Decision
Adopt Python 3.11+, FastAPI for the web layer, SQLAlchemy 2.0 (async/sync) for ORM, Alembic for schema migrations, and Pydantic v2 for data contracts.

## Consequences
Maintains unified Python ecosystem across ML, RAG, and API services; guarantees high throughput and rigorous schema validation.
