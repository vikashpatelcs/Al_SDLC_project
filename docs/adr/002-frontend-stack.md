# ADR 002: Frontend Technology Stack

- **Status**: Accepted
- **Date**: 2026-10-06

## Context
The system requires a responsive, ChatGPT-like conversation interface with inline action cards, file uploads, and streaming.

## Decision
Use React 18 with Vite, TypeScript, and Tailwind CSS. Implement Server-Sent Events (SSE) for token streaming and action card delivery.

## Consequences
Ensures clean component isolation, type safety, fast local development, and seamless inline rendering of approval gates and SDLC charts without heavy UI overhead.
