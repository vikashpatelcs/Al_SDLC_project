# ADR 008: Local LLM Engine and Base Model

- **Status**: Accepted
- **Date**: 2026-10-06

## Context
System must operate entirely locally with open-weights models supporting structured JSON outputs.

## Decision
Select Qwen2.5-7B-Instruct (fallback Qwen2.5-3B-Instruct) executed via local Ollama with OpenAI-compatible HTTP endpoints.

## Consequences
Superior reasoning and instruction-following for JSON schema generation; compatible with QLoRA fine-tuning on consumer/free Colab GPUs.
