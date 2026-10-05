# ADR 005: Relational Database Strategy

- **Status**: Accepted
- **Date**: 2026-10-06

## Context
Development requires zero-friction local setup, while production requires robust multi-user concurrency and enterprise persistence.

## Decision
Use SQLite with foreign key enforcement and WAL mode for local prototyping, maintaining SQLAlchemy models portable to PostgreSQL in Phase 17.

## Consequences
Instant local setup without external database daemon dependencies; straightforward containerization path for production.
