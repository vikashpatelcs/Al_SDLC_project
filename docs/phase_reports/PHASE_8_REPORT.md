# Phase Report: Phase 8 — Requirement Analysis + Issue Detection

```
Phase: Phase 8 — Requirement Analysis + Issue Detection
Implemented:
  1. Lexicons and Quality Rule Definitions:
     - rules/weak_words.yaml: Ambiguous, subjective, unquantified terms ("quickly", "seamlessly", "instantly", "user-friendly", "as appropriate", "if necessary", etc.) with parameterized rewrite templates.
     - rules/glossary.yaml: Canonical dictionary of financial, technical, and regulatory acronyms (KYC, AML, V-CIP, CKYC, UIDAI, NSDL, PAN, UPI, NPCI, PMLA, DPDP, KFS, APR, UTR, HSM, MFA, etc.).
     - rules/quality_rules.yaml: Deterministic criteria covering all 10 Problem Statement §10 quality dimensions.
  2. Database Persistence for Requirement Issues:
     - RequirementIssueModel in backend/app/db/models.py linked to requirements and projects.
     - Tracks issue_type, severity, detail, suggestion, rationale, and lifecycle status (open, resolved, dismissed).
  3. Analysis Engine Agent (backend/app/agents/analysis.py):
     - 10 multi-dimensional quality detectors:
       1. Ambiguity & Non-measurability (unquantified speed, throughput, or capacity)
       2. Pairwise Conflict & Contradiction (antagonistic directives: cloud unencrypted vs HSM encryption, retention mismatches)
       3. Incompleteness & Missing Slots (missing transaction velocity limits, missing error handling, truncation "etc.")
       4. Untestable & Infeasible Claims ("100% bug-free", "zero latency", "unhackable")
       5. Duplication & Overlap (pairwise token overlap >= 0.85)
       6. Regulatory Gap Analysis (CVV/PIN post-authorization storage, KYC retention < 5 years, processing personal data without explicit consent)
       7. Weak Words & Modals
       8. Missing Actor or IEEE-830 Imperative Modal ('shall'/'must')
       9. Undefined Acronyms (flags uppercase acronyms not catalogued in glossary)
       10. Missing Traceability Source (empty or missing source_statement_id)
     - Suggestion Generator: produces concrete, measurable rewrites and engineering/regulatory rationale for every issue.
     - Re-Analysis Loop: update requirement statement -> re-run detectors -> resolve cleared issues (status -> resolved).
     - ActionCard Generator: produces Master Plan A13 ISSUE_SUMMARY card with counts and inline suggestion cards.
  4. Live API & SSE Chat Streaming Integration (backend/app/api/chats.py):
     - Turn 2+: Extraction automatically triggers project analysis and emits ISSUE_SUMMARY ActionCard via SSE.
     - PATCH /api/chats/{chat_id}/requirements/{requirement_id}: updates requirement statement, re-analyzes, and returns resolved issue counts.
  5. Comprehensive Test Suite (backend/tests/test_phase8.py):
     - 7 unit and integration tests verifying all 10 dimensions, seeded defect recall >= 0.80, summary card counts, suggestion rationales, loop resolution, and PATCH API endpoint.

Files created:
  - rules/weak_words.yaml
  - rules/glossary.yaml
  - rules/quality_rules.yaml
  - backend/app/agents/analysis.py
  - backend/tests/test_phase8.py
  - docs/phase_reports/PHASE_8_REPORT.md

Files modified:
  - backend/app/db/models.py (added RequirementIssueModel, updated Project and RequirementModel relationships)
  - backend/app/api/chats.py (wired analysis engine into send_message, added PATCH re-analysis endpoint)

Tests:
  pytest backend/tests/ ml/dataset/tests/ -v

Passed: 48 (41 earlier tests + 7 new Phase 8 tests)
Failed: 0

Checkpoint: PASS
  [PASS] all 10 PS §10 checks implemented: Verified by test_all_10_quality_checks_implemented across all 10 quality dimensions.
  [PASS] seeded defect recall >= 0.8: Verified by test_seeded_defects_recall_on_gold_cases (100% recall on seeded ambiguities and conflicts across gold cases).
  [PASS] summary counts correct: Verified by test_issue_summary_card_counts (ISSUE_SUMMARY ActionCard payload counts match database rows exactly).
  [PASS] suggestion has rationale: Verified by test_suggestions_contain_measurable_rationale (100% of generated issues have non-empty suggestion and rationale).
  [PASS] loop (suggest -> edit -> re-analyse) works: Verified by test_reanalysis_loop_resolves_issues and test_patch_requirement_endpoint_reanalysis (updating statement marks previous issues as resolved).

Issues: None. All 48 tests passing with zero regressions.

Next phase: (propose only; do not start)
  Phase 9 — Multi-Agent Orchestration (LangGraph 6-agent workflow state machine, Coordinator agent, checkpointer, execution logging, permission matrix).
```
