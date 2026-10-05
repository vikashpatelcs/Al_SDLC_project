# AI Requirement Engineer — Antigravity Master Plan

Agentic-AI LLM system for requirement gathering, analysis and SDLC identification in the financial sector.
Source of truth: `Problem_Statement.docx` (20 numbered sections) + your Master Project Prompt.

> **How to use this file**
> 1. Put it in `docs/MASTER_PLAN.md` of your repo and tell Antigravity to treat it as read-only context.
> 2. Do Phase 0 first (it installs the guardrails). Then run **one phase at a time**, pasting that phase's *Antigravity prompt*.
> 3. A phase is finished only when the agent reports `Checkpoint: PASS` and **you** tick the checklist.

---

## PART A — DECISIONS, GAPS, ARCHITECTURE

### A1. Decisions I made (change any before Phase 0)

| Topic | Decision | Why |
|---|---|---|
| Representative use case | **Digital customer onboarding + KYC (inside a digital-banking app)**; loan processing is the 2nd case | Problem statement says start with one (loan processing *or* onboarding). Onboarding has a compact, well-defined RBI/PMLA/DPDP corpus, and also covers your "open account / transfer / fraud alert" scenario |
| Frontend | React + Vite + TypeScript + Tailwind, SSE streaming | Simple, ChatGPT-like, easy for an agent to generate |
| Backend | Python 3.11, FastAPI, SQLAlchemy 2, Alembic, Pydantic v2 | Same language as ML/RAG code |
| Orchestration | **LangGraph** (state graph, checkpointing, interrupts for human approval) | Approval gates map directly to graph interrupts |
| Relational DB | SQLite (prototype) → PostgreSQL (Phase 17); keep SQLAlchemy portable | Zero setup now, production path later |
| Vector DB | ChromaDB (persistent, local) | No server needed; swap for pgvector/Qdrant later |
| Embeddings | `BAAI/bge-small-en-v1.5` (CPU-friendly); optional reranker `bge-reranker-base` | Runs on laptop without GPU |
| Base LLM | **Qwen2.5-7B-Instruct** (fallback **Qwen2.5-3B-Instruct**) | Good JSON/instruction following, QLoRA fits a free Colab T4 |
| Fine-tuning | QLoRA with Unsloth + TRL on Colab; export LoRA adapter + GGUF | Laptop has no NVIDIA GPU |
| Local inference | **Ollama** (GGUF Q4_K_M), OpenAI-compatible endpoint | CPU-capable; OpenAI-compatible local API |
| LLM policy | **Offline, open-weights models only. No hosted/paid LLM API anywhere** (app, dataset generation, evaluation, judging). Gateway rejects non-local base URLs | Meets the offline requirement; keeps financial data on your machine. If the 7B is too slow on your CPU, use the 3B. Base vs fine-tuned comparison uses the same model family |
| Rule engines | YAML rule files + Python evaluators (quality, compliance, SDLC) | Problem statement requires *rule-based* compliance validation and deterministic SDLC logic |
| PII masking | Microsoft Presidio + custom India recognisers (Aadhaar, PAN, IFSC, account no., mobile, UPI ID) | Sensitive data must be masked **before** any LLM call |
| PDF | Jinja2 → HTML → WeasyPrint (fallback: ReportLab if WeasyPrint is painful on Windows) | Templated, versionable |
| Login | **None.** Anonymous session token (HttpOnly cookie) isolates chats; later replaced by OIDC user id | Meets "no login" yet supports isolation + future RBAC/MFA |

### A2. Problem-statement coverage matrix (PS = Problem_Statement.docx section)

| PS § | Requirement | Component | Phase |
|---|---|---|---|
| Intro | Agentic multi-agent LLM system, hallucination/explainability/bias/injection/access/regulatory change/interoperability/human oversight | Whole system; see A8, A9 | all |
| 1 | System scope + expected outputs | Scope doc, artefact generators | 1, 14 |
| 2 | Stakeholders + **role-specific interview templates** | `agents/templates/interviews/*.yaml` | 6 |
| 3 | Structured + unstructured inputs; classify/mask sensitive data | Upload parsers, masking pipeline | 3, 6 |
| 4 | Multi-agent architecture + orchestrator | 6 agents + LangGraph | 9 |
| 5 | Versioned financial knowledge base | KB registry + ingestion | 7 |
| 6 | RAG: classify → retrieve → evidence → generate → cite → confidence → escalate | `rag/` + citation verifier | 7, 10 |
| 7 | Adaptive interviews | Slot-coverage question generator | 6 |
| 8 | Standard requirement structure | `schemas/requirement.py` | 6 |
| 9 | Multi-label classification (13 classes) | Classifier (fine-tuned) | 6 |
| 10 | Quality analysis (10 checks) + return to clarification | `analysis` agent + rules | 8 |
| 11 | Compliance + security analysis; no final legal determination | Compliance/Security/Risk agent | 10 |
| 12 | Artefacts (SRS, stories, use cases, process workflows, data/interface reqs, risk register, compliance matrix, RTM, assumptions, open issues) | Documentation agent | 14 |
| 13–14 | SDLC factors + hybrid engine (rules + MCDA + LLM explanation), ranked output | `sdlc_engine.py` | 11 |
| 15 | Project-specific SDLC workflow | SDLC agent | 11 |
| 16 | Human-in-the-loop (8 mandatory approvals) | Approval gates | 12 |
| 17 | Platform security (RBAC, MFA, encryption, masking, filters, allowlist, injection, isolation, audit, retention, versioning) | `core/security/` | 3, 7, 13, 17 |
| 18 | Prototype stack, start with one use case | Whole plan | 2–17 |
| 19 | Evaluation metrics incl. P/R/F1, time saved, SDLC accuracy vs experts | `ml/eval/` | 15 |
| 20 | Gradual deployment: advisory mode, monitoring, re-evaluation, audit of everything | Deployment | 17 |

### A3. Gaps in your Master Prompt (now fixed in this plan)

1. **Role-specific interview templates** (PS §2) — not in your prompt. Added: the user may say "I'm the compliance officer"; the agent switches template. Default role = Product Owner/BA.
2. **Document inputs** (PS §3: transcripts, emails, policies, API specs, incident reports) — added as a paperclip upload in the chat box (still ChatGPT-like), parsed in Phase 6.
3. **Mask before LLM** (PS §3, §17) — added as a mandatory pipeline step (Phase 3).
4. **Rule-based compliance validation** (Intro, §11) — YAML rules, not LLM-only.
5. **Bias, explainability** (Intro) — "Explain" action on every AI output + bias checks in eval (A9).
6. **Regulatory change handling** — KB versioning + "affected mappings" report (Phase 7/10).
7. **Multi-role SDLC sign-off** (PS §14: PM, architect, security, compliance) — approval records carry an *acting role*; the prototype lets one person sign in each role, logged as such.
8. **MFA/IAM** (PS §17) vs "no login" — conflict resolved: designed-in hook (Phase 13/17), not implemented in the prototype.
9. **Transaction limits, exceptional conditions** (PS §7) — added to the question bank.
10. **Process workflows, data requirements, interface requirements** (PS §12) — added to artefacts.
11. **Time-saved vs manual** (PS §19) — manual baseline timing added to evaluation.
12. **Persistence is needed from Phase 2**, not Phase 13 — chat history can't work without it. Phase 13 *hardens* it (see A12).

### A4. Architecture

```
USER ─► React chat UI (sidebar + chat + inline action cards + upload)
          │  REST + SSE
          ▼
   FastAPI ── Session middleware (anon token → chat ownership)
          │
          ▼
   LangGraph Workflow (state persisted per chat)
   ┌───────────────────────────────────────────────────────────────┐
   │ 1 Coordinator ──► routes, state, approval gates, audit hooks  │
   │ 2 Requirement Engineer   (questions, extraction, stories, AC) │
   │ 3 Requirement Analysis   (classify, quality, conflicts, dups) │
   │ 4 Compliance+Security+Risk (RAG, rules, controls, risk reg.)  │
   │ 5 SDLC Agent             (factors → engine → workflow)        │
   │ 6 Documentation+Validation (SRS, RTM, PDF, final validation)  │
   └───────┬───────────────┬──────────────────┬────────────────────┘
           ▼               ▼                  ▼
     LLM Gateway     RAG (Chroma +       Rule engines (YAML)
     (Ollama/FT      BM25, citation      quality · compliance · SDLC
      model)          verifier)
           │               │                  │
           └───────┬───────┴──────────────────┘
                   ▼
   Security layer: masking · injection guard · output validator · audit chain
                   ▼
   SQLite/Postgres (structured)   Chroma (vectors)   Files (uploads, PDFs)
```

**Mapping the 13 agents of the problem statement to 6** (so nothing is lost):

| My agent | Absorbs PS agents |
|---|---|
| Coordinator | Coordinator, Human-approval agent (approval gate nodes) |
| Requirement Engineer | Stakeholder interaction, Requirement extraction, Clarification |
| Requirement Analysis | Classification, Conflict-detection |
| Compliance+Security+Risk | Compliance, Security & privacy, Risk-analysis |
| SDLC | SDLC selection |
| Documentation+Validation | Documentation, Validation |

Deterministic things (masking, rule checks, SDLC scoring, PDF rendering) are **services, not agents**.

### A5. Conversation state machine (what the Coordinator drives)

```
INTAKE → QUESTIONS_SENT → ANSWERS_RECEIVED → EXTRACTED → ANALYSED
  → ISSUE_REVIEW ⟲ (suggest → user Accept/Edit/Reject/Regenerate → re-analyse)
  → ⛔ APPROVAL: requirement baseline
  → ENRICH (security, privacy, risk, compliance+RAG)
  → ⛔ APPROVAL: high-risk security reqs & regulatory interpretations
  → ARTEFACTS (SRS, stories, use cases, AC, RTM, registers)
  → SDLC_ANALYSED → ⛔ APPROVAL: SDLC (challenge → re-score loop)
  → ⛔ APPROVAL: final package → PDF_GENERATED → DONE (or CHANGE_REQUEST → new baseline version)
```
Every transition is written to `audit_logs` and `agent_executions`.

### A6. Question bank design (smart interview)
- 10 topic groups: Business, Users/Roles, Workflow, Data, Security, Compliance, Performance, Integration, Risk, Constraints (+ transaction limits, exceptions, audit/reporting).
- Each topic has **slots** (e.g. `data.retention_period`). First message → one grouped question set generated for slots the idea doesn't already answer. User answers freely in one message.
- Extraction fills slots; unfilled/vague slots become **targeted follow-ups only**. Vague = rule-flagged (weak words) or LLM-flagged.
- Stop condition: required slots filled (or user says "assume defaults" → assumptions recorded in the Assumptions register).

### A7. Structured requirement model
Exactly your JSON + `version`, `source_statement_id` (link to original user sentence/uploaded chunk), `evidence_ids[]`, `issues[]`, `kb_version`, `model_version`. IDs follow `FR-ONB-001`, `SR-ONB-002`, `NFR-PERF-001` (domain code from the project).

### A8. RAG + regulation strategy
**Corpus layers (in `kb/`)**
1. Regulations (India, onboarding/KYC first): RBI KYC Master Direction; PMLA 2002 + Rules; DPDP Act 2023 (+ Rules as published); IT Act 2000; RBI direction(s) on IT governance/risk/controls and on digital payment security & authentication; RBI Digital Lending directions (for the loan case). Later: SEBI, IRDAI, PFRDA circulars per use case.
2. Standards (summaries you may legally store): ISO/IEC 27001 control themes, NIST CSF, OWASP ASVS, PCI DSS themes (only what you can lawfully include — store *your own summaries* + link where licensing prevents copying).
3. RE guidelines: ISO/IEC/IEEE 29148 structure, INCOSE rules, user-story/use-case templates, SRS template.
4. SDLC selection guide: your rule table from PS §14 + literature notes.
5. Glossary + financial processes (KYC, CKYC, V-CIP, STR, CDD, EDD…).
6. Approved past projects (your own sample SRSs).

**Acquisition rules:** download only from official regulator sites (rbi.org.in, sebi.gov.in, irdai.gov.in, pfrda.org.in, indiacode.nic.in). **Verify at ingestion time that you hold the latest amended version** — regulations change; I do not assert any specific current text. Store in `kb/raw/<regulator>/` with a `kb/manifest.yaml` entry.

**Metadata per chunk:** `document_id, title, regulator, jurisdiction, domain, document_type, effective_date, version, supersedes, applicability, section, source, official_url, kb_version, content_hash, allowlisted`.

**Pipeline:** query classification (regulatory / security / RE-guideline / SDLC / glossary) → metadata-filtered hybrid retrieval (dense + BM25) → optional rerank → evidence pack (≤ 6 chunks) → LLM answer **must cite chunk IDs** → **citation verifier** (ID was retrieved + quoted text found in chunk) → **confidence** = weighted(retrieval score, rerank score, citation verified, rule-agreement) → below threshold or unverified ⇒ label **"Unsupported — needs compliance review"**. The agent never states a regulatory obligation without a verified citation.

**Regulation change:** new document version ⇒ new `kb_version`; old chunks kept but marked `superseded`; a "Regulatory impact" job lists compliance mappings whose cited chunk was superseded.

### A9. AI-system security design (PS Intro + §17)

| Threat | Control |
|---|---|
| Prompt injection (user text, uploads, retrieved docs) | Untrusted content wrapped in delimiters and labelled *data*; system prompt states instruction hierarchy; regex+classifier scan of uploads/chunks; agents have **no side-effect tools** (only the Coordinator writes to DB) |
| Sensitive-data leakage | Presidio+India recognisers mask before LLM; placeholders (`<PAN_1>`) kept in a per-chat vault, never sent to LLM; logs store masked text |
| Unauthorised access | Anonymous session token (hashed in DB) checked on every query; `owner_token` filter at repository layer; RBAC tables ready for later |
| Unsafe agent actions | Per-agent permission matrix in `core/permissions.py` (read/write scopes); least data in each prompt |
| Retrieval poisoning / untrusted docs | Allowlisted sources only; ingestion requires manifest entry + hash; user uploads go to a **separate, non-authoritative** collection |
| Incorrect regulatory claims | Citation verifier + confidence + escalation + "not a legal determination" disclaimer |
| Output risk | Pydantic schema validation, repair-retry (max 2), unsafe-content filter |
| Bias | Eval set includes stakeholder-diverse and demographic-neutral prompts; check that requirements don't add discriminatory criteria (e.g. loan eligibility by religion/gender) → flagged by a rule |
| Tamper-evidence | `audit_logs` hash chain (each row stores `prev_hash`) |
| Encryption | HTTPS in deployment; field-level Fernet for message/requirement text at rest (key from env); disk encryption on host |

### A10. Fine-tuning dataset strategy (teaches *skills*, not regulations)

**Tasks (JSONL, chat format, always output strict JSON where structured):**
`T1 question_generation` · `T2 clarification_followup` · `T3 requirement_extraction` · `T4 classification (multi-label)` · `T5 ambiguity_detection` · `T6 incompleteness_detection` · `T7 conflict_detection` · `T8 duplicate_detection` · `T9 requirement_improvement` · `T10 user_story_ac` · `T11 use_case` · `T12 srs_section` · `T13 sdlc_factor_extraction` · `T14 sdlc_explanation`.

**Size target:** 4,000–6,000 examples (start with ~1,500 to test the pipeline).
**Sources:** (a) synthetic generation with a **local open-weights teacher** (e.g. Qwen2.5-7B/14B-Instruct via Ollama, or on the Colab GPU during your Colab session; no hosted APIs) from seed scenarios you write — across ≥ 12 financial subdomains; (b) public RE datasets for labelled signal (PROMISE/PROMISE_exp NFR, PURE requirements documents — check licences); (c) hand-written gold examples (≥ 150) by you.
**Quality controls:** schema validation → dedupe (embedding similarity) → rule check (no real PII, no invented regulation numbers inside *regulatory* fields — those must come from RAG at runtime) → local-LLM-judge filter → **human review of a random 10 %**.
**Split:** by **scenario**, not by row (prevents leakage). Hold out **entire subdomains** (insurance, regulatory reporting) as the test set to measure generalisation. Ratio ≈ 80/10/10 plus the held-out subdomains.
**Rule:** the fine-tuning set must contain *behaviour* ("flag 'instantly' as non-measurable and propose a measurable rewrite"), never regulatory facts.

### A11. Colab fine-tuning recipe (Phase 5 detail)

| Item | Primary | Fallback (if OOM / slow) |
|---|---|---|
| GPU | Colab T4 16 GB (free) | same |
| Model | Qwen2.5-7B-Instruct, 4-bit | Qwen2.5-3B-Instruct |
| Method | QLoRA (nf4, double-quant, bf16/fp16 as supported) | same |
| LoRA | r=16, alpha=32, dropout=0.05, all attn+MLP proj | r=8, alpha=16, attn only |
| Max seq len | 4096 | 2048 |
| Batch | per-device 2, grad-accum 8 | per-device 1, accum 16 |
| LR / sched | 2e-4, cosine, warmup 3 % | 1e-4 |
| Epochs | 2–3 (early stop on val loss) | 2 |
| Optimizer | paged_adamw_8bit | same |
| Loss masking | train on assistant tokens only | same |
| Checkpointing | to Google Drive every 100 steps (sessions disconnect) | same |

**Export:** save LoRA adapter → (optional) merge to 16-bit → convert to **GGUF Q4_K_M** → download → `ollama create req-engineer-ft -f Modelfile`.
**Evaluate on Colab** (GPU is faster than your laptop) with `ml/colab/eval.ipynb` over the same test set for base vs FT. **Training finishing proves nothing** — success is the metrics delta (JSON-validity, extraction F1, classification macro-F1, ambiguity F1, conflict F1, improvement quality) on held-out data.

### A12. Database design

**Relational (SQLAlchemy):** `chats(id, owner_token_hash, title, created_at, updated_at, state, deleted_at)` · `messages(id, chat_id, role, content_masked, created_at, meta)` · `projects(id, chat_id, name, domain, jurisdiction, summary)` · `stakeholders` · `requirements` · `requirement_versions` · `requirement_issues(type, severity, detail, suggestion, status)` · `approvals(id, chat_id, subject_type, subject_id, action, acting_role, comment, created_at)` · `risks` · `compliance_mappings(requirement_id, chunk_id, regulation, control, confidence, status, kb_version)` · `sdlc_recommendations(model, score, factors_json, explanation, selected)` · `traceability(source_statement_id, requirement_id, regulation_chunk, control, acceptance_criteria_id, risk_id)` · `generated_documents(id, chat_id, type, version, path, sha256, status)` · `agent_executions(id, chat_id, agent, input_ref, output_ref, model_version, kb_version, prompt_version, latency_ms)` · `audit_logs(id, chat_id, event, actor, payload, prev_hash, hash)` · `model_versions` · `knowledge_base_versions` · `uploaded_files`.
**Vector DB (Chroma):** `kb_authoritative` (official docs, standards, guidelines) and `uploads_untrusted` (per-chat user uploads). Embeddings + chunk metadata only.
**File storage (`storage/`):** raw uploads, `kb/raw` source PDFs, generated PDFs/DOCX, evaluation outputs. DB holds paths + SHA-256.

### A13. UI/UX plan (keep it tiny)
- Layout exactly as your sketch: left sidebar (+ New Chat, search, grouped Today/Yesterday, rename/delete on hover), main chat, bottom input with paperclip + Send.
- Rendered markdown, streaming tokens, copy button.
- **Inline cards inside the chat** (not new pages): *Question groups*, *Issue summary* (counts), *Suggested requirement* with **Accept / Edit / Reject / Regenerate / Explain**, *Approval request*, *SDLC ranking* (bars) with "Challenge this", *Download PDF*.
- Subtle status line (e.g. "Analysing compliance…") — no dashboards, no settings screens, no login.

### A14. Evaluation plan (Phase 15 detail)

**Case studies:** onboarding/KYC, loan processing, payments (used in development) + digital banking, fraud detection, insurance, regulatory reporting (insurance & reg-reporting held out from training).
**Gold data:** for each case, an input narrative with **seeded defects** (ambiguities, a conflict, a duplicate, missing security info) and a gold requirement list + gold labels, written/validated by you (+ ideally 1–2 peers).
**Systems compared:** S0 manual BA · S1 base LLM · S2 fine-tuned · S3 fine-tuned + RAG · S4 full multi-agent. Temperature 0, 3 runs each, report mean ± sd; paired bootstrap for significance.

| Metric | How |
|---|---|
| Extraction P/R/F1 | Match to gold reqs by embedding sim ≥ 0.8 + manual spot check |
| Completeness | % of gold slots/requirements covered |
| Correctness / consistency | Rubric (0–2) by humans on a sample; conflict recall |
| Ambiguity & conflict detection | P/R/F1 vs seeded defects |
| Regulatory control coverage | % of gold controls found |
| Citation correctness | % citations that exist and support the claim |
| Hallucination rate | unsupported regulatory/factual claims per 100 claims |
| SDLC accuracy | agreement (top-1, top-2) with ≥ 3 expert labels (teachers/industry contacts) |
| Traceability coverage | % reqs with full chain source→req→control→test |
| Human correction rate | % AI outputs edited/rejected in scripted sessions |
| Time | wall-clock per stage vs manual (time 2–3 peers doing S0) |
| Satisfaction | 5-pt Likert survey, ≥ 5 evaluators |

---

## PART B — PHASES (each with checkpoint + Antigravity prompt)

**Repo layout (created in Phase 0):**
```
req-engineer/
  AGENTS.md  .agent/rules/  .agent/workflows/
  docs/ (MASTER_PLAN.md, PROBLEM_STATEMENT.md, ARCHITECTURE.md, phase_reports/)
  frontend/            # Vite + React + TS + Tailwind
  backend/app/{api,core,db,schemas,agents,graph,rag,rules,docs_gen}  backend/tests
  ml/{dataset,colab,eval}
  kb/{raw,processed,manifest.yaml}
  storage/{uploads,generated}
```

**Order notes (deviations from your list, with reasons):**
- Basic persistence moves into **Phase 2** (chat history needs it); Phase 13 hardens it.
- PII masking moves into **Phase 3** (nothing may reach an LLM unmasked).
- **Phases 4–5 (dataset/fine-tuning) run in parallel with 6–7**; Colab training takes days of waiting. The fine-tuned model is plugged in at the end of Phase 5; pipeline phases work against the base model meanwhile.
- All 17 phases kept; Phase 0 added for guardrails. Rough solo effort: ~14–18 weeks (days shown per phase).

---

### PHASE 0 — Workspace & guardrails (0.5 d)
**Objective:** Make Antigravity unable to skip checkpoints.
**Tasks:** create repo skeleton; write `AGENTS.md` / `.agent/rules/` (content in Part C); create workflow `/phase-report`; convert Problem_Statement.docx → `docs/PROBLEM_STATEMENT.md`; commit master plan; git init + `.gitignore` (models, data, `.env`, `kb/raw`, `storage`).
**Files:** `AGENTS.md`, `.agent/rules/*.md`, `.agent/workflows/phase-report.md`, `Makefile`, `.env.example`, `docs/*`.
**Tech:** git, Python 3.11, Node 20.
**Testing:** `make check` runs (even if empty).
**Common errors:** rules folder name differs by Antigravity version → open *Customizations* in the app and use the folder it shows.
**CHECKPOINT:** [ ] skeleton exists [ ] rules visible in Antigravity [ ] agent can print the report template [ ] you set terminal policy to *request review* and use **Planning mode**
```
PHASE 0. Inspect the workspace and docs/MASTER_PLAN.md (read-only).
Create the repo skeleton from "Repo layout", AGENTS.md and .agent/rules from Part C of the plan,
.agent/workflows/phase-report.md, Makefile (targets: setup, check, test, lint), .env.example,
.gitignore, docs/PROBLEM_STATEMENT.md (convert the attached docx faithfully).
DO NOT write application code. DO NOT install heavy ML packages.
Tests: `make check` exits 0. Acceptance: tree matches the plan; report in the mandatory format.
```

### PHASE 1 — Problem understanding + architecture (2–3 d)
**Objective:** Freeze contracts before coding.
**Tasks:** write `ARCHITECTURE.md` + ADRs (the A1 decisions); OpenAPI draft; Mermaid ERD + state machine; **Pydantic/JSON schemas** for Requirement, Issue, Approval, Risk, SDLCRecommendation, AgentMessage; agent I/O contracts; question-bank slot list; interview-template list; PS coverage table verified against Part A2.
**Files:** `docs/ARCHITECTURE.md`, `docs/adr/*.md`, `docs/openapi_draft.yaml`, `backend/app/schemas/*.py` (types only).
**DB changes:** none (design only). **Model/Dataset:** none.
**Testing:** schemas import; sample JSON validates.
**Common errors:** over-designing → keep to what A1–A14 say.
**CHECKPOINT:** [ ] every PS § mapped to a component [ ] schemas validate sample requirement [ ] you approved ADRs [ ] agent permission matrix drafted
```
PHASE 1. Inspect docs/MASTER_PLAN.md and docs/PROBLEM_STATEMENT.md.
Create ARCHITECTURE.md, ADRs, openapi_draft.yaml, Mermaid ERD + state machine, and Pydantic v2 schemas
in backend/app/schemas (Requirement incl. all PS §8 fields + version/evidence_ids/kb_version/model_version).
Add tests/test_schemas.py. DO NOT create endpoints, DB, UI. Acceptance: pytest passes; a coverage table
lists each PS section → component → phase with no gaps.
```

### PHASE 2 — Project setup + ChatGPT-like UI + minimal persistence (4–5 d)
**Objective:** A working chat shell with history, no AI yet.
**Tasks:** FastAPI app; `POST /chats`, `GET /chats`, `PATCH/DELETE /chats/{id}`, `GET /chats/{id}/messages`, `POST /chats/{id}/messages` (SSE stream of a **mock** assistant); anonymous session middleware; SQLite `chats`, `messages`, `uploaded_files`; React UI per A13 incl. search, rename, delete, markdown, paperclip upload (stores file only), inline **ActionCard** component (mock data).
**Files:** `backend/app/main.py, api/chats.py, core/session.py, db/models.py`; `frontend/src/{App.tsx, components/{Sidebar,ChatView,MessageInput,ActionCard}.tsx, api.ts}`.
**Tech:** FastAPI, SQLAlchemy, Alembic, React, Tailwind, react-markdown, EventSource/fetch-stream.
**Input → Output:** user text → streamed mock reply; chats persist across restarts.
**Testing:** pytest (CRUD, isolation: token A cannot read token B's chat); Vitest for components; Playwright smoke (new chat → send → reload → history intact).
**Common errors:** CORS/cookie `SameSite` on localhost → proxy via Vite; SSE buffering → disable proxy buffering; SQLite thread error → `check_same_thread=False` + session-per-request.
**CHECKPOINT:** [ ] backend & frontend start with `make dev` [ ] new/rename/delete/search chat work [ ] history survives restart [ ] two browsers can't see each other's chats [ ] no login/profile/dashboard anywhere
```
PHASE 2. Inspect docs/ARCHITECTURE.md and schemas. Create the FastAPI backend and React UI described in
Phase 2 of the plan. Assistant replies are a MOCK streamed string. Anonymous session = random token in an
HttpOnly cookie; store only its hash; every repository query filters by owner.
UI must look like a modern AI chat app: sidebar (+ New Chat, search, Today/Yesterday groups), centered chat,
bottom input with paperclip and Send. NO login, NO settings page, NO dashboards.
Tests: pytest (CRUD + isolation), vitest, one Playwright smoke test. Run all and paste results.
DO NOT change docs/ or schemas. DO NOT add LLM calls.
```

### PHASE 3 — LLM gateway + masking + baseline (3–4 d)
**Objective:** One safe way to call any model; first baseline numbers.
**Tasks:** `llm_gateway.py` (OpenAI-compatible client for local Ollama only; **refuses any non-local base URL**; timeouts, retries, token logging, `model_version`); `prompts/` with versioned prompt files; **structured-output helper** (Pydantic validate → repair retry ×2); **masking pipeline** (Presidio + India recognisers, reversible vault per chat) applied inside the gateway; injection scanner (basic patterns); start **gold set** (3 cases) and baseline runner.
**Files:** `core/llm_gateway.py, core/security/{masking.py,injection.py,output_validator.py}, prompts/*.md, ml/eval/cases/*.json, ml/eval/run_baseline.py`.
**Model changes:** pull base model into Ollama (`qwen2.5:7b-instruct` or 3B).
**Testing:** a non-local gateway URL is rejected; masking recall on a synthetic PII sample (target ≥ 0.95 on your recognisers); gateway never sends unmasked PAN/Aadhaar (test with a fake HTTP server capturing payloads); JSON-validity rate of base model.
**Common errors:** Presidio spaCy model missing → `python -m spacy download en_core_web_lg` (or `sm` for speed); Ollama slow on CPU → use the 3B model, lower `num_ctx`, keep prompts short.
**CHECKPOINT:** [ ] base model answers via gateway [ ] payload-capture test proves masking [ ] prompts versioned [ ] baseline_results.json created from 3 gold cases [ ] **you** reviewed the gold cases
```
PHASE 3. Inspect backend/app and docs. Create the LLM gateway, masking (Presidio + custom India recognisers:
Aadhaar, PAN, IFSC, account number, mobile, UPI), injection scanner, structured-output helper, versioned prompt
loader, and ml/eval baseline runner. Masking MUST run inside the gateway so no caller can bypass it.
Tests: payload-capture test, masking recall test, JSON repair test. Provide baseline_results.json.
DO NOT touch the frontend. DO NOT add any hosted-LLM client or API keys; the gateway must reject non-local URLs (add a test).
```

### PHASE 4 — Fine-tuning dataset (7–10 d, parallel track)
**Objective:** Dataset that teaches RE *behaviour* (A10).
**Tasks:** seed-scenario file (≥ 40 scenarios, ≥ 12 subdomains); generators per task T1–T14; validators; dedupe; split by scenario; dataset card; 150 hand-written gold examples (you).
**Files:** `ml/dataset/{seeds/,generate.py,validate.py,dedupe.py,split.py,DATASET_CARD.md,data/{train,val,test}.jsonl}`.
**Dataset changes:** this is the dataset.
**Testing:** 100 % schema-valid; zero PII hits; no scenario in two splits; manual review of 10 % sample (log result in card).
**Common errors:** teacher model invents regulation numbers → strip/regenerate; repetitive outputs → raise seed diversity; label imbalance → per-task quotas.
**CHECKPOINT:** [ ] ≥ 1,500 valid examples (target 4–6 k) [ ] splits leak-free [ ] held-out subdomains reserved [ ] 10 % human review done [ ] dataset card written
```
PHASE 4. Inspect ml/ and the A10 dataset strategy. Create generators, validators, dedupe, scenario-level splitter,
dataset card and tests under ml/dataset. Output chat-format JSONL with strict-JSON assistant targets.
Reserve insurance and regulatory-reporting as test-only subdomains. No regulatory facts in targets.
Tests: schema validity 100%, leakage test, PII test. DO NOT call any hosted/online LLM API; use only local Ollama or Colab-run open-weights models.
```

### PHASE 5 — Google Colab fine-tuning (3–4 d + waiting)
**Objective:** Fine-tuned adapter that beats baseline on held-out data.
**Tasks:** `finetune.ipynb` (Drive mount → install Unsloth/TRL → load 4-bit base → LoRA → SFT on assistant tokens → save checkpoints to Drive → eval on val); `eval.ipynb` (base vs FT on test); export adapter, merged model, GGUF Q4_K_M; `Modelfile`; local import to Ollama; compare in `run_eval.py`.
**Files:** `ml/colab/{finetune.ipynb,eval.ipynb,README.md}`, `ml/models/Modelfile`, `ml/eval/compare_base_ft.py`.
**Model changes:** register `req-engineer-ft:<version>` in `model_versions`.
**Testing:** training loss falls, val loss doesn't diverge; local inference returns valid JSON; **FT beats base** on JSON-validity, extraction F1, classification macro-F1, ambiguity F1, conflict F1 on test.
**Common errors:** CUDA OOM → fallback column of A11; session timeout → resume from Drive checkpoint; GGUF conversion fails → merge in 16-bit first, update llama.cpp; FT worse than base → data quality/overfit → fewer epochs, more diverse data.
**CHECKPOINT:** [ ] dataset loads [ ] GPU detected [ ] training runs [ ] val metrics logged [ ] adapter + GGUF downloaded [ ] local Ollama inference works [ ] **FT improves over baseline (numbers in report)** → only then Phase 6 integration swaps the model
```
PHASE 5. Create Colab notebooks and scripts per A11 (primary + fallback config cells). Notebooks must be
runnable top-to-bottom, checkpoint to Drive, and print a metrics table. Create Modelfile and
compare_base_ft.py. I will run Colab myself and give you the result files; you then run the local comparison.
DO NOT claim success from training completion; report metric deltas only. DO NOT modify backend/app.
```

### PHASE 6 — Structured requirement engine (4–5 d)
**Objective:** Idea → grouped questions → answers → structured requirements.
**Tasks:** requirement tables + versions; **slot-based question generator** (A6) with per-role interview templates (PS §2) and transaction-limit/exception questions; extraction from chat answers **and uploaded docs** (txt, pdf, docx, eml, csv parsers; masked first; stored in untrusted collection); multi-label classifier; ID generator; `source_statement_id` linking; "assume defaults" → Assumptions register.
**Files:** `agents/requirement_engineer.py`, `agents/templates/interviews/{product_owner,compliance_officer,security,risk,operations,auditor,architect,customer}.yaml`, `rules/slots.yaml`, `core/parsers/*.py`, `db` migrations.
**DB:** `projects, stakeholders, requirements, requirement_versions`. **Model:** use FT model if Phase 5 passed.
**Testing:** on gold cases: extraction F1 vs baseline; every requirement has source link; schema 100 % valid; questions are grouped, not one-at-a-time.
**Common errors:** over-extraction (non-requirements) → add "is this a requirement?" filter; ID collisions → DB sequence per project.
**CHECKPOINT:** [ ] grouped questions generated for the demo idea [ ] one big answer → ≥ 80 % of gold requirements extracted [ ] multi-label categories correct on gold [ ] uploaded transcript extracted [ ] source links present
```
PHASE 6. Inspect schemas, gateway, prompts, gold cases. Implement the requirement engine described in
Phase 6 + A6/A7. Uploaded files must be masked and scanned for injection before extraction.
Add migrations. Wire a minimal /chats/{id}/messages path: first message → question groups card;
next message → extraction summary. Tests with the gold cases; report F1.
DO NOT build analysis, RAG, or documents yet.
```

### PHASE 7 — RAG + financial knowledge base (6 d)
**Objective:** Versioned, allowlisted, citation-verified retrieval.
**Tasks:** `manifest.yaml` + ingest CLI (download is manual; ingest parses PDF/HTML, section-aware chunking, metadata A8, content hash); Chroma collections; hybrid retrieval; optional rerank; query classifier; **citation verifier**; KB versioning + supersede logic; allowlist enforcement; 30 hand-written retrieval test queries.
**Files:** `rag/{ingest.py,chunker.py,retriever.py,verifier.py,kb_registry.py}`, `kb/manifest.yaml`, `ml/eval/retrieval_queries.yaml`.
**DB:** `knowledge_base_versions`. **Dataset:** the KB (not training data).
**Testing:** recall@5 ≥ 0.8 on the 30 queries (target); verifier rejects fabricated citation; document not in manifest is refused; superseded chunk flagged.
**Common errors:** bad PDF text order → try `pymupdf`/`pdfplumber`; chunks lose section context → prepend heading path; scanned PDFs → OCR (flag as lower trust).
**CHECKPOINT:** [ ] ≥ 8 official documents ingested with full metadata [ ] retrieval target met [ ] fake citation rejected [ ] KB version recorded [ ] uploads can't enter authoritative collection
```
PHASE 7. Implement rag/ per A8. I will place official PDFs in kb/raw and list them in kb/manifest.yaml;
you write the ingest/chunk/retrieve/verify code. Never fetch documents from the internet yourself.
Add retrieval tests and a citation-verifier test with a fabricated citation. Report recall@5.
DO NOT hardcode regulatory text anywhere in code or prompts.
```

### PHASE 8 — Requirement analysis + issue detection (5 d)
**Objective:** PS §10 checks + the "Requirements found: 27 / Complete 19 / …" summary + suggestions.
**Tasks:** hybrid detectors — *rules* (weak-word list, missing unit/threshold, no actor, no "shall", undefined acronyms vs glossary, missing source) + *embeddings* (duplicates) + *candidate-pair + LLM adjudication* (conflicts: same entity/metric, opposing values) + LLM (feasibility, testability, incompleteness vs slots); **suggestion generator** with rationale; re-analysis loop after edits; summary card.
**Files:** `agents/analysis.py`, `rules/quality_rules.yaml`, `rules/weak_words.yaml`, `rules/glossary.yaml`.
**DB:** `requirement_issues`.
**Testing:** P/R/F1 on seeded defects in gold cases; "respond instantly" → flagged + measurable rewrite proposed; edit → re-analysis clears issue.
**Common errors:** false positives on weak words → context windows; conflict explosion O(n²) → pre-filter by entity overlap.
**CHECKPOINT:** [ ] all 10 PS §10 checks implemented [ ] seeded defect recall ≥ 0.8 [ ] summary counts correct [ ] suggestion has rationale [ ] loop (suggest→edit→re-analyse) works
```
PHASE 8. Implement analysis per Phase 8. Deterministic rules first; LLM only where rules can't decide.
Every issue stores type, severity, evidence and a suggested rewrite with rationale.
Add the summary message ("Requirements found: N; complete…; ambiguous…; conflicting…; missing security info…")
as an ActionCard payload. Tests against seeded-defect gold cases; report P/R/F1.
DO NOT implement approvals yet (use a stub that records the choice).
```

### PHASE 9 — Multi-agent orchestration (5 d)
**Objective:** Wrap everything in the 6-agent LangGraph workflow (A4/A5).
**Tasks:** `state.py` (typed graph state); nodes for 6 agents + deterministic service nodes; conditional edges from the state machine; **interrupt nodes** for approvals; DB-backed checkpointer (resume after restart); per-agent permission matrix; timeouts/retries; every node writes `agent_executions` + audit event; stream progress events to UI.
**Files:** `graph/{state.py,workflow.py,nodes.py}`, `agents/coordinator.py`, `core/permissions.py`.
**DB:** `agent_executions`.
**Testing:** graph runs the demo scenario with stubbed compliance/SDLC/doc nodes; killing the server mid-run and resuming continues from the same state; agent without permission cannot write.
**Common errors:** state bloat → store IDs, not full objects; infinite loops in suggest/re-analyse → max iterations + user escape.
**CHECKPOINT:** [ ] full graph path executes to DONE with stubs [ ] resume after restart [ ] permissions enforced [ ] each step logged [ ] UI shows progress line
```
PHASE 9. Inspect agents/, rag/, rules/. Implement the LangGraph workflow and Coordinator per A4/A5.
Only the Coordinator may write to the database; other agents return typed results.
Add persistence checkpointer, loop caps, permission matrix, execution logging. Replace the Phase 6/8 ad-hoc
message handling with the graph. Stub nodes for phases 10–14 return fixtures.
Tests: end-to-end stub run, restart-resume test, permission test. DO NOT remove earlier tests.
```

### PHASE 10 — Compliance + security + privacy + risk (6 d)
**Objective:** PS §11 and §12 (risk/compliance artefacts).
**Tasks:** requirement → RAG query → evidence → LLM mapping → citation verify → **YAML compliance rules** (e.g. PII stored ⇒ needs consent, retention, masking, access control; money movement ⇒ strong authentication, limits, audit log; onboarding ⇒ KYC/CDD mapping; eligibility criteria ⇒ non-discrimination check) → gap list; **security/privacy control checklist** (authN/authZ, encryption, access control, transaction security, audit logging, secure integrations, threats; data collection/sensitivity/masking/retention/access/sharing); **risk register** (business, technical, security, compliance, operational, availability, legacy; 5×5 probability×impact → level; mitigation, owner, status); **confidence score** and escalation labels; compliance-control matrix; "regulatory impact" report when KB version changes.
**Files:** `agents/compliance_security_risk.py`, `rules/{compliance_rules.yaml,security_controls.yaml,privacy_controls.yaml,risk_model.yaml}`.
**DB:** `compliance_mappings, risks`.
**Testing:** gold controls coverage; unsupported claim ⇒ flagged "needs compliance review", never asserted; every mapping has a verified citation or an escalation flag; rule fires on a requirement missing retention.
**Common errors:** LLM cites from memory → verifier blocks; too many generic risks → require link to a requirement or constraint.
**CHECKPOINT:** [ ] mappings carry verified citations [ ] unsupported → escalated [ ] rule-based gaps detected [ ] risk register has all fields [ ] disclaimer "not a legal determination" shown [ ] control coverage measured on gold
```
PHASE 10. Implement per Phase 10 + A8/A9. Compliance rules live in YAML and run deterministically AFTER
the LLM mapping to validate it. The agent must refuse to state a regulatory obligation without a
verified citation (use verifier from Phase 7). Generate risk register with the exact fields in the plan.
Tests: gold-control coverage, fabricated-citation rejection, rule-fires tests. DO NOT hardcode regulation text.
```

### PHASE 11 — SDLC recommendation engine (4 d)
**Objective:** PS §13–15 — ranked scores + project-specific workflow.
**Tasks:** SDLC agent extracts the 13 factors (1–5 + evidence quote; user can override via chat); `sdlc_rules.yaml` holds **per-model fit tables** and hard rules; engine = deterministic rules + weighted multi-criteria score → normalised % for Waterfall, V-Model, Spiral, Agile, DevSecOps, Agile+V, Agile+DevSecOps; LLM writes explanation using the factor/score table only; **challenge loop** (user changes a factor/argues → re-score, show delta); workflow generator producing, per phase: activity, role, deliverable, security activity, testing, compliance checkpoint, human approval, entry/exit criteria, traceability requirement — customised from project facts (e.g. threat modelling in design, SAST in implementation, transaction-integrity tests, compliance approval before deploy).
**Files:** `agents/sdlc.py`, `rules/sdlc_rules.yaml`, `rules/sdlc_engine.py`, `rules/workflow_templates/*.yaml`.
**DB:** `sdlc_recommendations`.
**Testing:** the PS §14 table cases return the expected top model (unit tests); explanation numbers match the engine; changing "requirement stability" shifts scores in the expected direction; ranking sums/normalisation sane.
**Common errors:** LLM-invented scores → forbid; engine must compute them. Ties → deterministic tie-breaker with note.
**CHECKPOINT:** [ ] 13 factors extracted with evidence [ ] ranked % list [ ] rule table tests pass [ ] explanation consistent with scores [ ] challenge → re-evaluation works [ ] workflow has all 10 fields per phase
```
PHASE 11. Implement the SDLC engine per Phase 11. Scores come ONLY from rules/sdlc_engine.py; the LLM
explains but never computes. Seed sdlc_rules.yaml with the problem statement's §14 table plus my
fit-table design (propose it in your plan artifact and wait for my review before coding the weights).
Tests: one unit test per row of the PS table, sensitivity test, workflow completeness test.
```

### PHASE 12 — Human approval + revision (4 d)
**Objective:** PS §16 — the 8 mandatory gates and change control.
**Tasks:** approval model + API; gate types: baseline, requirement change, regulatory interpretation, high-risk security req, conflict decision, architecture-critical req, SDLC selection, production readiness; actions **Accept / Reject / Edit / Regenerate / Explain** (Explain = rationale + evidence + confidence); acting-role field; approved baseline is **immutable** — change ⇒ new version + impact analysis (affected reqs, mappings, tests); SDLC needs 4 role sign-offs (PM, architect, security, compliance) recorded; nothing downstream runs while a gate is pending.
**Files:** `api/approvals.py`, `graph/gates.py`, `frontend/.../ApprovalCard.tsx`.
**DB:** `approvals`, requirement version status.
**Testing:** pipeline halts at each gate; reject → re-enters analysis; edited baseline creates v2 and keeps v1; PDF job refuses unapproved items.
**Common errors:** race between edit and re-analysis → version numbers + optimistic locking.
**CHECKPOINT:** [ ] all 8 gates block [ ] 5 actions work in UI [ ] baseline immutable + versioned [ ] SDLC 4-role sign-off logged [ ] Explain shows evidence
```
PHASE 12. Implement approvals and change control per Phase 12 using LangGraph interrupts.
Add ApprovalCard with Accept/Reject/Edit/Regenerate/Explain. Enforce immutability of approved baselines
(new version on change + impact report). Tests: each gate blocks, reject loop, versioning, optimistic locking.
DO NOT build PDF generation yet.
```

### PHASE 13 — Database hardening + chat history + audit (3 d)
**Objective:** Complete data model, tamper-evident audit, clean resume.
**Tasks:** remaining tables (`traceability, generated_documents, audit_logs, model_versions`…); Alembic migrations; audit **hash chain** + verify command; record all events listed in your §25; field-level encryption for message/requirement text; soft delete + retention policy setting; resume any chat at its exact workflow state; auth hook (`get_current_principal()` returns anon principal now; OIDC/MFA later); run test-suite also on PostgreSQL.
**Files:** `db/migrations/*`, `core/audit.py`, `core/crypto.py`, `core/auth_hook.py`, `backend/tests/test_audit_chain.py`.
**Testing:** tamper with one audit row → verify fails; encrypted columns unreadable in raw DB; resume mid-workflow works; Postgres run green.
**Common errors:** Alembic autogenerate misses SQLite constraints → batch mode; key rotation → store `key_id`.
**CHECKPOINT:** [ ] migrations from empty DB [ ] audit chain verifies and detects tamper [ ] all §25 events present [ ] encryption on [ ] resume works [ ] Postgres tests pass
```
PHASE 13. Complete DB per A12, add audit hash chain, field-level encryption, retention/soft delete, auth hook.
Do not change API shapes used by the frontend. Tests: tamper detection, encryption-at-rest, resume,
migration-from-scratch, Postgres compatibility (docker compose service allowed).
```

### PHASE 14 — SRS / PDF / artefacts (5 d)
**Objective:** PS §12 and your §22 — the final document.
**Tasks:** generators for user stories + AC (Given/When/Then), use cases, process workflows (Mermaid → image or table), data and interface requirements, assumptions & dependency register, open-issues list, **Requirements Traceability Matrix** (source statement → requirement → regulation chunk → control → acceptance criteria → risk), SRS in ISO/IEC/IEEE 29148 style with your 23 PDF sections; Jinja templates; only **approved** content in the final PDF, DRAFT watermark otherwise; version/approval block; sha256 recorded; download card in chat.
**Files:** `agents/documentation.py`, `docs_gen/{templates/*.html.j2,pdf.py,traceability.py,validation.py}`.
**DB:** `traceability`, `generated_documents`.
**Testing:** PDF renders with all 23 sections; unapproved requirement absent from final; traceability coverage 100 % for approved reqs; validation agent flags a requirement lacking evidence.
**Common errors:** WeasyPrint system libs on Windows → use WSL/Docker or switch to ReportLab; page-break of large tables → CSS `break-inside`.
**CHECKPOINT:** [ ] PDF generated from approved demo [ ] 23 sections present [ ] only approved items [ ] RTM complete [ ] sha256 + version stored [ ] opens correctly
```
PHASE 14. Implement artefacts and PDF per Phase 14. Validation step must verify completeness,
consistency and evidence before rendering. Final PDF includes only approved items; otherwise DRAFT.
Tests: section-presence test, approved-only test, traceability coverage test. Provide a sample PDF path.
```

### PHASE 15 — Evaluation (7 d)
**Objective:** Real evidence per A14 — not "it runs".
**Tasks:** finish 6 gold cases; scripted runners for S1–S4; metric code; manual-baseline timing sessions; expert SDLC labels; satisfaction survey; results tables + plots + error analysis; ablation conclusions (does FT help? does RAG help? do agents help?).
**Files:** `ml/eval/{cases/,gold/,run_eval.py,metrics.py,report.py}`, `docs/EVALUATION_REPORT.md`.
**Testing:** metric code unit-tested on toy data; runs reproducible (seed/config logged).
**Common errors:** judge-model bias → human spot checks; leakage → test cases never in training set.
**CHECKPOINT:** [ ] 4 system configs run on all cases [ ] all A14 metrics reported with sd [ ] SDLC compared to ≥ 3 experts [ ] failures analysed honestly [ ] report written
```
PHASE 15. Build the evaluation harness per A14 (S1 base, S2 FT, S3 FT+RAG, S4 full system) and produce
docs/EVALUATION_REPORT.md with tables. I supply gold files. Metrics code needs unit tests.
Never tune prompts on test cases. Report negative results as they are.
```

### PHASE 16 — Complete integration + hardening (4 d)
**Objective:** Your §33 scenario works end-to-end from the UI.
**Tasks:** Playwright test that walks the entire §33 flow (digital banking prompt → questions → one big answer → issues → accept/edit/reject → security/risk/compliance → approvals → SDLC challenge → PDF); latency profiling; UI polish; error states (model down, empty KB, upload rejected); prompt-injection red-team set (20 attacks) in tests.
**Testing:** E2E green 3× in a row; red-team: 0 successful leaks/unsafe actions.
**CHECKPOINT:** [ ] full scenario passes [ ] red-team passes [ ] graceful errors [ ] audit shows complete trail for the run [ ] no extra UI features crept in
```
PHASE 16. Write and run the E2E Playwright scenario from §33 and a 20-case injection red-team suite.
Fix bugs found WITHOUT adding features. Report latency per stage and any checkpoint regressions in earlier phases.
```

### PHASE 17 — Deployment + monitoring (4 d)
**Objective:** PS §20 — advisory-mode rollout.
**Tasks:** Docker Compose (frontend, backend, Postgres, Chroma volume, model server); `.env` profiles; healthchecks; structured logs; basic metrics (latency, error rate, escalation rate, human-correction rate); **advisory-mode banner/setting** ("outputs are advisory; human approval required"); backup/restore for DB + KB; model/KB version bump procedure + regression-eval command; runbook; documented OIDC+MFA integration plan.
**Model hosting note:** fully offline. Run Ollama on the laptop (or a machine on your own network) and point the gateway at it; no cloud LLM.
**Testing:** `docker compose up` from clean checkout; restore from backup; regression eval script runs.
**CHECKPOINT:** [ ] one-command start [ ] backups restore [ ] metrics visible in logs [ ] regression eval after a KB update [ ] runbook complete

```
PHASE 17. Containerise and add monitoring per Phase 17. No new product features.
Tests: clean-clone `docker compose up` smoke test, backup/restore test, regression-eval command.
```

---

## PART C — GUARDRAIL FILES FOR PHASE 0

**`AGENTS.md` / `.agent/rules/00-global.md`**
```
You are implementing the project in docs/MASTER_PLAN.md. docs/PROBLEM_STATEMENT.md is the source of truth.
1. Work on ONE phase only: the one named in the user's prompt.
2. Use Planning mode: produce an implementation plan and wait for approval before editing.
3. Before coding, list files you will create/modify. Never touch files marked "DO NOT change".
4. Run all tests (new + earlier phases). Paste real output; never claim a pass you didn't observe.
5. Evaluate the phase CHECKPOINT item by item. If ANY item fails: STOP, report FAIL, propose fixes.
   Never start the next phase on your own. Never weaken or delete a test to pass.
6. Product rules: no login/registration/profile/admin/dashboard UI; this is NOT a banking app.
7. Safety rules: nothing reaches an LLM unmasked; no regulatory claim without a verified citation;
   agents other than the Coordinator never write to the DB; no secrets in code; never invent
   regulation text — retrieve it from kb/.
8. Ask before: installing large packages, deleting files, network downloads.
9. OFFLINE LLM ONLY: never add or call any hosted/online LLM API. Only local Ollama / open-weights models.
```

**Mandatory report (`.agent/workflows/phase-report.md`)**
```
Phase:
Implemented:
Files created:
Files modified:
Tests:
Passed:
Failed:
Checkpoint: PASS / FAIL   (list each checkbox with PASS/FAIL + evidence)
Issues:
Next phase: (only propose; do not start)
```

**Final success criteria:** the §33 scenario passes in Phase 16; Phase 15 shows (honestly) whether fine-tuning, RAG and agents each improve results; every decision is recoverable from `audit_logs`.

**Your own tasks that Antigravity cannot do:** write/validate gold cases (Ph 3, 15), review dataset samples (Ph 4), run Colab (Ph 5), download official regulations (Ph 7), arrange expert SDLC labels + survey (Ph 15).
