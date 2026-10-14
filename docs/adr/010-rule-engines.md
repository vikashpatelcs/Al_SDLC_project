# ADR 010: Deterministic Rule Engines for Compliance and Quality

- **Status**: Accepted
- **Date**: 2026-10-06

## Context
Regulatory compliance and SDLC scoring must be deterministic, transparent, and auditable—not left solely to probabilistic LLMs.

## Decision
Implement declarative YAML rule specifications paired with deterministic Python evaluators for quality checks, compliance control triggers, and SDLC MCDA scoring.

## Consequences
Transparent auditability, zero hallucinations in regulatory compliance logic, and deterministic reproduction of scoring outcomes.
