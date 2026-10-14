# ADR 011: Pre-LLM PII Masking Pipeline

- **Status**: Accepted
- **Date**: 2026-10-06

## Context
Sensitive identifiers (Aadhaar, PAN, account numbers, IFSC, mobile numbers) must be masked before text reaches any LLM or audit log.

## Decision
Deploy Microsoft Presidio integrated with custom Indian financial pattern recognizers. Masked tokens (<PAN_1>) map to a per-session isolated vault.

## Consequences
Zero data leakage risk into model context windows or persistent logs; clean reversibility when generating official customer documents.
