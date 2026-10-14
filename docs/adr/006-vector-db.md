# ADR 006: Vector Database for RAG Knowledge Base

- **Status**: Accepted
- **Date**: 2026-10-06

## Context
Grounding requirements in official regulatory circulars requires persistent, low-overhead semantic retrieval.

## Decision
Use ChromaDB in local persistent mode with two distinct collections: 'kb_authoritative' (official circulars) and 'uploads_untrusted' (user documents).

## Consequences
Completely embedded local vector index requiring no external server; strict separation prevents untrusted user files from contaminating official regulatory grounding.
