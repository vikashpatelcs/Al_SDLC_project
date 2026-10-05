# ADR 007: Embedding Model Selection

- **Status**: Accepted
- **Date**: 2026-10-06

## Context
Embeddings must run locally on developer hardware without requiring dedicated GPU infrastructure.

## Decision
Select BAAI/bge-small-en-v1.5 (384 dimensions) for dense embeddings, with optional bge-reranker-base for two-stage retrieval.

## Consequences
High retrieval accuracy on benchmark financial corpora while running efficiently on CPU.
