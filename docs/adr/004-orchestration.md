# ADR 004: Multi-Agent Workflow Orchestration

- **Status**: Accepted
- **Date**: 2026-10-06

## Context
The system coordinates 6 specialized agents with cyclical review loops and mandatory human approval gates.

## Decision
Use LangGraph state graph with persistent checkpointing and state-machine interrupt nodes for human approvals.

## Consequences
Explicit state transitions, ability to halt pipeline at approval gates without losing context, resume after crash, and strict single-writer DB access via the Coordinator.
