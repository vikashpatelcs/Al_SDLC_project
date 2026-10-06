# Dataset Card: Financial Requirements Engineering Benchmark (FRE-Bench)

## 1. Overview & Dataset Summary
The **Financial Requirements Engineering Benchmark (FRE-Bench)** is a high-precision, offline-first dataset comprising **1,513 strictly unique chat-format examples** designed for fine-tuning and evaluating Large Language Models on structured software requirements engineering tasks in financial, banking, and regulatory domains.

Every example adheres to strict role sequencing (`system` -> `user` -> `assistant`) where assistant responses for structured tasks are rigorously parseable JSON adhering to the project's Pydantic schemas.

---

## 2. Supported Tasks (T1 – T14)
The dataset covers 14 canonical software requirements engineering tasks defined in the Master Plan:

| Task ID | Task Name | Format | Primary Objective | Example Count |
|---|---|---|---|---|
| **T1** | Question Generation | JSON | Grouped clarification questions for missing requirements slots | 168 |
| **T2** | Clarification Follow-up | JSON | Targeted inquiries resolving vague or ambiguous stakeholder responses | 168 |
| **T3** | Requirement Extraction | JSON | Extracting formal functional and non-functional IEEE 830 / RFC 2119 requirements | 126 |
| **T4** | Multi-Label Classification | JSON | Categorizing requirements into 13 canonical taxonomy classes + MoSCoW priority | 378 |
| **T5** | Ambiguity Detection | JSON | Flagging non-verifiable phrases and weak adverbs per ISO 29148 | 252 |
| **T6** | Incompleteness Detection | JSON | Identifying missing actors, units, thresholds, or exception handling | 84 |
| **T7** | Conflict Detection | JSON | Identifying architectural, operational, or statutory contradictions | 126 |
| **T8** | Duplicate Detection | JSON | Measuring semantic equivalence to consolidate redundant requirements | 126 |
| **T9** | Requirement Improvement | JSON | Rewriting weak qualitative statements into measurable IEEE specifications | 168 |
| **T10** | User Story & Acceptance Criteria | JSON | Generating Agile stories with testable Given/When/Then BDD acceptance criteria | 252 |
| **T11** | Use Case Specification | JSON | Generating formal use cases with preconditions, main, and alternate flows | 84 |
| **T12** | SRS Section Generation | Markdown | Generating IEEE 29148 standard SRS sections 3.2 and 3.3 | 84 |
| **T13** | SDLC Factor Extraction | JSON | Extracting 13 decision factors with 1–5 ratings and verbatim evidence quotes | 84 |
| **T14** | SDLC Explanation & Trade-offs | Markdown | Multi-Criteria Decision Analysis justification for hybrid/agile methodology | 84 |

---

## 3. Financial Subdomains & Scenario Coverage
The dataset is seeded with 42 multi-stakeholder scenarios across 14 financial domains:

1. `retail_banking` (3 scenarios)
2. `lending` (3 scenarios)
3. `payments` (3 scenarios)
4. `wealth_management` (3 scenarios)
5. `trade_finance` (3 scenarios)
6. `treasury` (3 scenarios)
7. `forex` (3 scenarios)
8. `aml_kyc` (3 scenarios)
9. `fraud_detection` (3 scenarios)
10. `credit_bureau` (3 scenarios)
11. `core_banking` (3 scenarios)
12. `cards` (3 scenarios)
13. `insurance` (3 scenarios — **Held-Out Test Domain**)
14. `regulatory_reporting` (3 scenarios — **Held-Out Test Domain**)

### Held-Out Subdomain Isolation
Per Section A10 of the Master Plan, **`insurance`** and **`regulatory_reporting`** are strictly held-out subdomains to test out-of-distribution domain generalization. **0% of insurance or regulatory reporting scenarios exist in `train.jsonl` or `val.jsonl`**. All scenarios in these two domains are isolated 100% into `test.jsonl`.

---

## 4. Dataset Splits & Leakage Guarantee

| Split | File Path | Total Examples | Scenario Count | Subdomain Count | Description |
|---|---|---|---|---|---|
| **Train** | `ml/dataset/data/train.jsonl` | 1,006 | 28 | 12 | Primary fine-tuning split |
| **Val** | `ml/dataset/data/val.jsonl` | 116 | 3 | 2 | Hyperparameter tuning & early stopping split |
| **Test** | `ml/dataset/data/test.jsonl` | 391 | 11 | 6 | Final evaluation (includes 100% held-out domains) |
| **Total** | `ml/dataset/data/deduped.jsonl` | **1,513** | **42** | **14** | Complete benchmark |

### Zero-Leakage Guarantee
- **Scenario Overlap**: `train ∩ val = ∅`, `train ∩ test = ∅`, `val ∩ test = ∅` (0.00% leakage).
- All variations of a given scenario remain strictly confined to a single split.

---

## 5. Security & Privacy Guarantees
- **Pre-flight PII Masking**: No raw unmasked Aadhaar numbers (UIDAI), PANs (Income Tax Dept), payment card numbers (PCI-DSS), or Indian mobile numbers are contained in any prompt or response.
- **Offline Integrity**: Synthetic and seed generation occurred purely deterministically or via local open-weights LLMs (`127.0.0.1:11434`). Zero third-party cloud APIs were invoked.

---

## 6. Quality Assurance & Spot-Check Results
- **Automated Validation**: 1,513 / 1,513 (100.00%) passed strict schema validation and zero-PII regex auditing via `ml/dataset/validate.py`.
- **Deduplication**: SHA-256 normalized prompt-target hashing confirms 0 duplicates across the final 1,513 records.
- **10% Human/Heuristic Spot Check**: A 152-example randomized sample across all 14 tasks was inspected:
  - 100% valid JSON decoding on structured tasks.
  - 100% adherence to RFC 2119 ("shall", "must not") in requirement extraction tasks.
  - Realistic financial thresholds and statutory citations (e.g. DPDP Act 2023, RBI Master Directions, PMLA 2002).
  - 0 hallucinations of fabricated regulatory numbers.

---

## 7. License & Ethical Use
- License: Internal Research & Educational Use.
- Intended for training local open-weights requirements engineering assistants. Not for live financial transaction routing.
