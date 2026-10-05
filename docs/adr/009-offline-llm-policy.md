# ADR 009: Offline LLM Policy and Gateway Guardrails

- **Status**: Accepted
- **Date**: 2026-10-06

## Context
Financial privacy mandates that no financial statements, prompts, or user uploads leave the local host.

## Decision
Enforce a strict offline-only policy. The LLM Gateway validates and rejects any base URL that resolves to non-local addresses or hosted cloud APIs.

## Consequences
Guarantees regulatory compliance regarding data sovereignty and privacy; zero ongoing API costs.
