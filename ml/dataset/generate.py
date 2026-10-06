"""
Dataset Generator for Tasks T1 through T14.
Produces chat-format JSONL with strict valid JSON assistant responses for structured RE tasks.
Generates rich, distinct multi-persona and edge-case variations per scenario to exceed 1,500 unique examples.
"""
import json
import os
import sys
from typing import List, Dict, Any

# Ensure project root in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))


def generate_task_examples(scenario: Dict[str, Any]) -> List[Dict[str, Any]]:
    examples = []
    sc_id = scenario["scenario_id"]
    subdomain = scenario["subdomain"]
    title = scenario["title"]
    narrative = scenario["narrative"]
    reqs = scenario["sample_requirements"]
    vague_list = scenario.get("sample_vague_phrases", [])
    conflicts = scenario.get("sample_conflicts", {})
    sdlc = scenario.get("sdlc_profile", {})
    primary_actor = scenario.get("target_users", ["Financial User"])[0]

    # =========================================================================
    # T1: Question Generation (Multiple Perspectives)
    # =========================================================================
    # Perspective 1: Core Functional & Identity Slots
    asst_t1_func = {
        "groups": [
            {
                "topic": "Workflow and Identity",
                "questions": [
                    f"What is the exact end-to-end user journey for {title}?",
                    "What specific KYC or identity verification mechanisms (e.g. Aadhaar XML, CKYC, PAN API) are mandated?"
                ]
            },
            {
                "topic": "Limits and Thresholds",
                "questions": [
                    "What are the transaction value tiers and daily volume caps?",
                    "What error recovery paths handle upstream gateway timeouts?"
                ]
            }
        ]
    }
    examples.append({
        "task": "T1_question_generation",
        "scenario_id": sc_id,
        "subdomain": subdomain,
        "messages": [
            {"role": "system", "content": "You are an expert Financial Requirements Engineer. Analyze the input idea and generate targeted, grouped clarification questions for unfilled requirements slots."},
            {"role": "user", "content": f"Project Concept: {title}\nSummary: {narrative}\n\nPlease generate initial functional and workflow clarification questions."},
            {"role": "assistant", "content": json.dumps(asst_t1_func, indent=2)}
        ]
    })

    # Perspective 2: Security, Audit, and Compliance Slots
    asst_t1_sec = {
        "groups": [
            {
                "topic": "Security and Data Protection",
                "questions": [
                    "What cryptographic standards (e.g. AES-256-GCM, TLS 1.3) must be enforced for data at rest and in transit?",
                    "Are hardware security modules (HSM) required for key signing and tokenization?"
                ]
            },
            {
                "topic": "Auditability and Regulatory Mandates",
                "questions": [
                    f"Which specific guidelines under {scenario.get('regulatory_context', 'RBI regulations')} govern data retention and immutable audit logs?",
                    "What are the statutory reporting timelines for security incidents or suspicious transactions?"
                ]
            }
        ]
    }
    examples.append({
        "task": "T1_question_generation",
        "scenario_id": sc_id,
        "subdomain": subdomain,
        "messages": [
            {"role": "system", "content": "You are a Regulatory Compliance and Security Requirements Specialist. Identify missing regulatory, security, and auditability requirements."},
            {"role": "user", "content": f"Project: {title}\nIdentify mandatory compliance, data privacy, and security questions that need stakeholder clarification."},
            {"role": "assistant", "content": json.dumps(asst_t1_sec, indent=2)}
        ]
    })

    # Perspective 3: Architectural Scale & Performance Slots
    asst_t1_arch = {
        "groups": [
            {
                "topic": "Scalability and Throughput",
                "questions": [
                    "What is the projected peak transaction per second (TPS) target for year 1 and year 3?",
                    "What is the acceptable P99 API response latency SLA under peak load?"
                ]
            },
            {
                "topic": "High Availability and Disaster Recovery",
                "questions": [
                    "What are the target Recovery Point Objective (RPO) and Recovery Time Objective (RTO)?",
                    "Is active-active multi-region deployment required for zero downtime failover?"
                ]
            }
        ]
    }
    examples.append({
        "task": "T1_question_generation",
        "scenario_id": sc_id,
        "subdomain": subdomain,
        "messages": [
            {"role": "system", "content": "You are a Financial Systems Architect. Identify non-functional, scalability, and high-availability requirement gaps."},
            {"role": "user", "content": f"Concept: {title}\nWhat architectural and operational SLA questions must be clarified with the engineering team?"},
            {"role": "assistant", "content": json.dumps(asst_t1_arch, indent=2)}
        ]
    })

    # Perspective 4: Data Governance & Privacy Slots
    asst_t1_gov = {
        "groups": [
            {
                "topic": "Data Governance and Consent Management",
                "questions": [
                    "What explicit user consent artifacts and withdrawal workflows are required under DPDP Act?",
                    "How are Personally Identifiable Information (PII) elements tokenized before downstream analytics ingestion?"
                ]
            },
            {
                "topic": "Data Localization and Cross-border Boundaries",
                "questions": [
                    "Are all primary and disaster-recovery databases strictly hosted within Indian borders per RBI directives?",
                    "What data scrubbing procedures are applied to staging and non-production testing environments?"
                ]
            }
        ]
    }
    examples.append({
        "task": "T1_question_generation",
        "scenario_id": sc_id,
        "subdomain": subdomain,
        "messages": [
            {"role": "system", "content": "You are a Data Protection Officer and Privacy Engineer. Identify data governance, DPDP consent, and data localization requirement slots."},
            {"role": "user", "content": f"Project: {title}\nWhat data privacy, consent management, and localization questions must be addressed?"},
            {"role": "assistant", "content": json.dumps(asst_t1_gov, indent=2)}
        ]
    })

    # =========================================================================
    # T2: Clarification Follow-up
    # =========================================================================
    for idx, v in enumerate(vague_list):
        # Variation A: Standard ambiguity clarification
        asst_t2_a = {
            "issue_detected": "Non-measurable qualitative requirement",
            "clarification_question": f"Could you specify concrete quantitative metrics for '{v['vague']}'? For example, would '{v['improved']}' align with your SLA targets?"
        }
        examples.append({
            "task": "T2_clarification_followup",
            "scenario_id": sc_id,
            "subdomain": subdomain,
            "messages": [
                {"role": "system", "content": "You are a Requirements Engineer. Follow up on vague or incomplete stakeholder answers."},
                {"role": "user", "content": f"Stakeholder response: 'We want the system to {v['vague']}.'\nFollow-up question:"},
                {"role": "assistant", "content": json.dumps(asst_t2_a, indent=2)}
            ]
        })

        # Variation B: Bounding threshold inquiry
        asst_t2_b = {
            "issue_detected": "Missing boundary and error tolerance limits",
            "clarification_question": f"When stating '{v['vague']}', what is the upper-bound threshold and acceptable degradation mode during peak volumes or external outages?"
        }
        examples.append({
            "task": "T2_clarification_followup",
            "scenario_id": sc_id,
            "subdomain": subdomain,
            "messages": [
                {"role": "system", "content": "You are a Requirements Engineer investigating non-functional boundaries and failure thresholds."},
                {"role": "user", "content": f"The client stated: '{v['vague']}'. Ask for explicit failure bounds and threshold criteria."},
                {"role": "assistant", "content": json.dumps(asst_t2_b, indent=2)}
            ]
        })

    # =========================================================================
    # T3: Requirement Extraction (Strict RFC 2119 / IEEE 'shall')
    # =========================================================================
    # Positive extraction: functional requirements
    extracted_objs = []
    for r in reqs:
        extracted_objs.append({
            "id": r["id"],
            "statement": r["statement"],
            "category": r["category"],
            "priority": r["priority"],
            "status": "draft"
        })
    examples.append({
        "task": "T3_requirement_extraction",
        "scenario_id": sc_id,
        "subdomain": subdomain,
        "messages": [
            {"role": "system", "content": "You are an expert Requirements Engineer. Extract formal functional and non-functional requirements from the provided interview answers."},
            {"role": "user", "content": f"Context: {narrative}\nExtract structured requirements."},
            {"role": "assistant", "content": json.dumps(extracted_objs, indent=2)}
        ]
    })

    # Negative/Constraint extraction: statutory constraints
    constraints_objs = [
        {
            "id": f"REQ-{sc_id.replace('SCN-', '')}-SEC-01",
            "statement": f"The system shall never store unmasked financial credentials or authorization tokens in persistent application logs.",
            "category": "Security",
            "priority": "Must Have",
            "status": "draft"
        },
        {
            "id": f"REQ-{sc_id.replace('SCN-', '')}-CMP-01",
            "statement": f"The system shall retain all transactional audit records in append-only storage for a minimum of 8 years per statutory mandate.",
            "category": "Compliance",
            "priority": "Must Have",
            "status": "draft"
        }
    ]
    examples.append({
        "task": "T3_requirement_extraction",
        "scenario_id": sc_id,
        "subdomain": subdomain,
        "messages": [
            {"role": "system", "content": "You are a Financial Compliance Engineer. Extract non-functional regulatory constraints and negative invariants (what the system MUST NOT do)."},
            {"role": "user", "content": f"Project: {title}\nExtract statutory security and compliance negative constraints."},
            {"role": "assistant", "content": json.dumps(constraints_objs, indent=2)}
        ]
    })

    # Integration contract extraction
    api_objs = [
        {
            "id": f"REQ-{sc_id.replace('SCN-', '')}-INT-01",
            "statement": f"The external integration interface shall enforce HMAC-SHA256 request payload signatures and X-Idempotency-Key headers for all mutating endpoints.",
            "category": "Interface",
            "priority": "Must Have",
            "status": "draft"
        }
    ]
    examples.append({
        "task": "T3_requirement_extraction",
        "scenario_id": sc_id,
        "subdomain": subdomain,
        "messages": [
            {"role": "system", "content": "You are an Integration Architect. Extract API interface and cryptographic boundary requirements."},
            {"role": "user", "content": f"Project: {title}\nExtract integration and idempotency contract requirements."},
            {"role": "assistant", "content": json.dumps(api_objs, indent=2)}
        ]
    })

    # =========================================================================
    # T4: Multi-Label Classification (13 Canonical Categories + MoSCoW)
    # =========================================================================
    for r in reqs:
        # Primary category classification
        asst_t4_prim = {
            "id": r["id"],
            "primary_category": r["category"],
            "confidence": 0.95,
            "rationale": f"Classified as {r['category']} because the requirement explicitly defines operational capabilities for {subdomain.replace('_', ' ')}."
        }
        examples.append({
            "task": "T4_classification",
            "scenario_id": sc_id,
            "subdomain": subdomain,
            "messages": [
                {"role": "system", "content": "Classify the financial requirement across the 13 canonical categories: Business, Functional, Non-Functional, Technical, Security, Privacy, Compliance, Performance, Availability, Auditability, Operational, Interface, Data."},
                {"role": "user", "content": f"Requirement Statement:\n\"{r['statement']}\""},
                {"role": "assistant", "content": json.dumps(asst_t4_prim, indent=2)}
            ]
        })

        # Secondary / cross-cutting classification
        secondary_cat = "Compliance" if r["category"] in ["Security", "Privacy", "Data"] else "Security" if r["category"] == "Technical" else "Operational"
        asst_t4_sec = {
            "id": r["id"],
            "primary_category": r["category"],
            "secondary_categories": [secondary_cat],
            "is_cross_cutting": True,
            "rationale": f"While primarily {r['category']}, this requirement directly impacts {secondary_cat} due to regulatory verification controls."
        }
        examples.append({
            "task": "T4_classification",
            "scenario_id": sc_id,
            "subdomain": subdomain,
            "messages": [
                {"role": "system", "content": "Perform multi-label taxonomy classification on this financial requirement, identifying cross-cutting concerns."},
                {"role": "user", "content": f"Analyze cross-cutting categories for: \"{r['statement']}\""},
                {"role": "assistant", "content": json.dumps(asst_t4_sec, indent=2)}
            ]
        })

        # MoSCoW priority classification & justification
        asst_t4_moscow = {
            "id": r["id"],
            "priority": r["priority"],
            "moscow_tier": r["priority"],
            "penalty_risk": "High regulatory sanction or service disruption" if r["priority"] == "Must Have" else "Moderate operational inconvenience",
            "justification": f"Assigned {r['priority']} because failure to implement directly impairs core financial operations."
        }
        examples.append({
            "task": "T4_classification",
            "scenario_id": sc_id,
            "subdomain": subdomain,
            "messages": [
                {"role": "system", "content": "Evaluate requirement priority using the MoSCoW framework and regulatory penalty impact analysis."},
                {"role": "user", "content": f"Evaluate MoSCoW priority tier for: \"{r['statement']}\""},
                {"role": "assistant", "content": json.dumps(asst_t4_moscow, indent=2)}
            ]
        })

    # =========================================================================
    # T5: Ambiguity Detection (Weak Words / ISO 29148)
    # =========================================================================
    for v in vague_list:
        asst_t5_pos = {
            "has_ambiguity": True,
            "problematic_phrase": v["vague"],
            "defect_type": "non_measurable_quality",
            "suggestion": f"The system shall {v['improved']}."
        }
        examples.append({
            "task": "T5_ambiguity_detection",
            "scenario_id": sc_id,
            "subdomain": subdomain,
            "messages": [
                {"role": "system", "content": "Detect ambiguous, non-testable, or subjective wording in requirement statements."},
                {"role": "user", "content": f"Analyze statement for ambiguity: \"The system shall {v['vague']}.\""},
                {"role": "assistant", "content": json.dumps(asst_t5_pos, indent=2)}
            ]
        })

    # Weak word variation (adverbs: rapidly, seamlessly)
    examples.append({
        "task": "T5_ambiguity_detection",
        "scenario_id": sc_id,
        "subdomain": subdomain,
        "messages": [
            {"role": "system", "content": "Detect subjective adverbs and unverifiable superlatives in financial requirements per ISO 29148."},
            {"role": "user", "content": f"Analyze statement for ambiguity: \"The system shall seamlessly and rapidly handle transaction settlement for {title}.\""},
            {"role": "assistant", "content": json.dumps({
                "has_ambiguity": True,
                "problematic_phrase": "seamlessly and rapidly",
                "defect_type": "subjective_superlative",
                "suggestion": f"The system shall process transaction settlement within 500 milliseconds for 99.5% of requests during peak hours."
            }, indent=2)}
        ]
    })

    # Clean statement test for T5 (negative samples)
    for r in reqs:
        examples.append({
            "task": "T5_ambiguity_detection",
            "scenario_id": sc_id,
            "subdomain": subdomain,
            "messages": [
                {"role": "system", "content": "Detect ambiguous, non-testable, or subjective wording in requirement statements."},
                {"role": "user", "content": f"Analyze statement for ambiguity: \"{r['statement']}\""},
                {"role": "assistant", "content": json.dumps({"has_ambiguity": False, "problematic_phrase": None, "suggestion": None}, indent=2)}
            ]
        })

    # =========================================================================
    # T6: Incompleteness Detection
    # =========================================================================
    # Variation 1: Data storage incompleteness
    asst_t6_data = {
        "is_incomplete": True,
        "missing_elements": [
            "Missing specific data entity types and attributes",
            "Missing retention duration and lifecycle triggers",
            "Missing cryptographic encryption specifications",
            "Missing role-based access control list"
        ],
        "remediation": f"Specify explicit data schemas, statutory retention duration, and encryption algorithms for {title}."
    }
    examples.append({
        "task": "T6_incompleteness_detection",
        "scenario_id": sc_id,
        "subdomain": subdomain,
        "messages": [
            {"role": "system", "content": "Analyze requirement statements for missing actors, units, thresholds, or exception handling."},
            {"role": "user", "content": f"Check completeness: \"The application shall store data for {title}.\""},
            {"role": "assistant", "content": json.dumps(asst_t6_data, indent=2)}
        ]
    })

    # Variation 2: Third-party integration incompleteness
    asst_t6_integ = {
        "is_incomplete": True,
        "missing_elements": [
            "Missing HTTP connection and socket timeout values",
            "Missing circuit breaker error thresholds",
            "Missing retry policy (e.g. exponential backoff with jitter)",
            "Missing fallback response behaviour on service outage"
        ],
        "remediation": f"Define explicit connection timeout (e.g. 2000ms), max retries (e.g. 3), and fallback queueing when communicating with external partners."
    }
    examples.append({
        "task": "T6_incompleteness_detection",
        "scenario_id": sc_id,
        "subdomain": subdomain,
        "messages": [
            {"role": "system", "content": "Analyze requirement statements for missing operational, resilience, and exception handling specifications."},
            {"role": "user", "content": f"Check completeness: \"The system shall transmit transaction records to the external clearing house API for {title}.\""},
            {"role": "assistant", "content": json.dumps(asst_t6_integ, indent=2)}
        ]
    })

    # =========================================================================
    # T7: Conflict Detection
    # =========================================================================
    # Variation 1: Real conflicting pair (positive sample)
    if conflicts:
        asst_t7_pos = {
            "has_conflict": True,
            "conflict_type": "direct_operational_contradiction",
            "explanation": "Statement A and Statement B impose mutually exclusive operational workflows.",
            "recommended_resolution": "Enforce Statement B to comply with statutory and regulatory mandates."
        }
        examples.append({
            "task": "T7_conflict_detection",
            "scenario_id": sc_id,
            "subdomain": subdomain,
            "messages": [
                {"role": "system", "content": "Detect architectural, logical, or regulatory contradictions between pairs of requirement statements."},
                {"role": "user", "content": f"Statement A: \"{conflicts['statement_a']}\"\nStatement B: \"{conflicts['statement_b']}\"\n\nAre these statements in conflict?"},
                {"role": "assistant", "content": json.dumps(asst_t7_pos, indent=2)}
            ]
        })

    # Variation 2: Non-conflicting orthogonal pair (negative sample)
    if len(reqs) >= 2:
        asst_t7_neg = {
            "has_conflict": False,
            "conflict_type": None,
            "explanation": f"The statements address complementary operational aspects ({reqs[0]['category']} and {reqs[1]['category']}) and can be simultaneously satisfied.",
            "recommended_resolution": None
        }
        examples.append({
            "task": "T7_conflict_detection",
            "scenario_id": sc_id,
            "subdomain": subdomain,
            "messages": [
                {"role": "system", "content": "Detect architectural, logical, or regulatory contradictions between pairs of requirement statements."},
                {"role": "user", "content": f"Statement A: \"{reqs[0]['statement']}\"\nStatement B: \"{reqs[1]['statement']}\"\n\nAre these statements in conflict?"},
                {"role": "assistant", "content": json.dumps(asst_t7_neg, indent=2)}
            ]
        })

    # Variation 3: Regulatory latency vs audit conflict
    asst_t7_reg = {
        "has_conflict": True,
        "conflict_type": "performance_vs_audit_tradeoff",
        "explanation": f"Sub-millisecond direct settlement for {title} bypasses required cryptographic hardware signing and tamper-evident audit ledger writes.",
        "recommended_resolution": "Prioritize audit integrity and mandate asynchronous audit signing before finalizing transaction state."
    }
    examples.append({
        "task": "T7_conflict_detection",
        "scenario_id": sc_id,
        "subdomain": subdomain,
        "messages": [
            {"role": "system", "content": "Detect regulatory vs performance trade-off conflicts between requirement specifications."},
            {"role": "user", "content": f"Statement A: \"The system shall settle financial transfers for {title} under 50 milliseconds without blocking for external I/O.\"\nStatement B: \"The system shall write synchronous tamper-evident audit logs to immutable WORM storage for {title} before confirming any transfer.\"\n\nAre these statements in conflict?"},
            {"role": "assistant", "content": json.dumps(asst_t7_reg, indent=2)}
        ]
    })

    # =========================================================================
    # T8: Duplicate Detection
    # =========================================================================
    if len(reqs) >= 2:
        r1 = reqs[0]
        # Variation 1: Semantic duplicate (positive sample)
        dup_statement = r1["statement"].replace("The system shall", "The platform must").replace("via", "using")
        asst_t8_pos = {
            "is_duplicate": True,
            "similarity_score": 0.94,
            "recommendation": f"Consolidate into single canonical requirement {r1['id']}."
        }
        examples.append({
            "task": "T8_duplicate_detection",
            "scenario_id": sc_id,
            "subdomain": subdomain,
            "messages": [
                {"role": "system", "content": "Identify semantic and functional duplication between requirement statements."},
                {"role": "user", "content": f"Requirement 1: \"{r1['statement']}\"\nRequirement 2: \"{dup_statement}\"\nAre these requirements duplicates?"},
                {"role": "assistant", "content": json.dumps(asst_t8_pos, indent=2)}
            ]
        })

        # Variation 2: Distinct requirements (negative sample)
        r2 = reqs[1]
        asst_t8_neg = {
            "is_duplicate": False,
            "similarity_score": 0.18,
            "recommendation": "Maintain both distinct requirements in the specification."
        }
        examples.append({
            "task": "T8_duplicate_detection",
            "scenario_id": sc_id,
            "subdomain": subdomain,
            "messages": [
                {"role": "system", "content": "Identify semantic and functional duplication between requirement statements."},
                {"role": "user", "content": f"Requirement 1: \"{r1['statement']}\"\nRequirement 2: \"{r2['statement']}\"\nAre these requirements duplicates?"},
                {"role": "assistant", "content": json.dumps(asst_t8_neg, indent=2)}
            ]
        })

    if len(reqs) >= 3:
        r3 = reqs[2]
        dup_statement_3 = r3["statement"].replace("The system shall", "The application will mandate that it")
        asst_t8_third = {
            "is_duplicate": True,
            "similarity_score": 0.92,
            "recommendation": f"Consolidate into single canonical requirement {r3['id']}."
        }
        examples.append({
            "task": "T8_duplicate_detection",
            "scenario_id": sc_id,
            "subdomain": subdomain,
            "messages": [
                {"role": "system", "content": "Identify semantic and functional duplication between requirement statements."},
                {"role": "user", "content": f"Requirement 1: \"{r3['statement']}\"\nRequirement 2: \"{dup_statement_3}\"\nAre these requirements duplicates?"},
                {"role": "assistant", "content": json.dumps(asst_t8_third, indent=2)}
            ]
        })

    # =========================================================================
    # T9: Requirement Improvement (Measurable Rewrites)
    # =========================================================================
    for idx, v in enumerate(vague_list):
        asst_t9_a = {
            "original_statement": f"The system shall {v['vague']}.",
            "improved_statement": f"The system shall {v['improved']}.",
            "rationale": "Replaced non-testable qualitative description with verifiable quantitative threshold per INCOSE guidelines."
        }
        examples.append({
            "task": "T9_requirement_improvement",
            "scenario_id": sc_id,
            "subdomain": subdomain,
            "messages": [
                {"role": "system", "content": "Rewrite ambiguous or subjective software requirements into verifiable, measurable IEEE standard specifications with rationale."},
                {"role": "user", "content": f"Improve requirement: \"The system shall {v['vague']}.\""},
                {"role": "assistant", "content": json.dumps(asst_t9_a, indent=2)}
            ]
        })

        # Variation B: SLA and availability focus rewrite
        asst_t9_b = {
            "original_statement": f"The system shall ensure that it {v['vague']} for {title}.",
            "improved_statement": f"The system shall guarantee that it {v['improved']} with 99.99% availability and automated failover for {title}.",
            "rationale": f"Bound qualitative phrase '{v['vague']}' to quantifiable availability and performance criteria per INCOSE standard."
        }
        examples.append({
            "task": "T9_requirement_improvement",
            "scenario_id": sc_id,
            "subdomain": subdomain,
            "messages": [
                {"role": "system", "content": "Formulate strict quantitative Service Level Agreements (SLAs) for financial platform reliability requirements."},
                {"role": "user", "content": f"Rewrite into measurable SLA for {title}: \"The system shall ensure that it {v['vague']} for {title}.\""},
                {"role": "assistant", "content": json.dumps(asst_t9_b, indent=2)}
            ]
        })

    # =========================================================================
    # T10: User Story & Acceptance Criteria (Given/When/Then)
    # =========================================================================
    for r in reqs:
        # Standard workflow AC
        asst_t10_std = {
            "user_story": f"As a {primary_actor}, I want the system to execute verified operations so that {subdomain.replace('_', ' ')} compliance and business integrity are preserved.",
            "acceptance_criteria": [
                {
                    "scenario": "Standard successful execution",
                    "given": f"Preconditions for {r['id']} are satisfied and caller is authorized",
                    "when": "A valid transaction request is submitted",
                    "then": f"The system shall fulfill: {r['statement']}"
                },
                {
                    "scenario": "Input validation rejection",
                    "given": "Malformed payload or unauthenticated token is presented",
                    "when": "The processing request is initiated",
                    "then": "The system shall reject the request with HTTP 400/401 and write an immutable audit log"
                }
            ]
        }
        examples.append({
            "task": "T10_user_story_ac",
            "scenario_id": sc_id,
            "subdomain": subdomain,
            "messages": [
                {"role": "system", "content": "Generate Agile User Stories with testable Given/When/Then Acceptance Criteria from requirements."},
                {"role": "user", "content": f"Requirement: \"{r['statement']}\""},
                {"role": "assistant", "content": json.dumps(asst_t10_std, indent=2)}
            ]
        })

        # Resilience & Timeout AC
        asst_t10_res = {
            "user_story": f"As a System Reliability Engineer, I want the system to handle downstream service failures gracefully during {r['id']}.",
            "acceptance_criteria": [
                {
                    "scenario": "Downstream partner timeout",
                    "given": f"Execution of {r['id']} has initiated",
                    "when": "Downstream API fails to respond within 2500ms",
                    "then": "The system shall abort the request, roll back state changes, and queue a compensating event"
                },
                {
                    "scenario": "Idempotent retry submission",
                    "given": "A previous attempt timed out and a retry is issued with identical Idempotency-Key",
                    "when": "The request is re-evaluated",
                    "then": "The system shall return the cached terminal result without executing duplicate financial effects"
                }
            ]
        }
        examples.append({
            "task": "T10_user_story_ac",
            "scenario_id": sc_id,
            "subdomain": subdomain,
            "messages": [
                {"role": "system", "content": "Generate resilience, idempotency, and fault-tolerance BDD acceptance criteria for the requirement."},
                {"role": "user", "content": f"Generate exception and resilience acceptance criteria for: \"{r['statement']}\""},
                {"role": "assistant", "content": json.dumps(asst_t10_res, indent=2)}
            ]
        })

    # =========================================================================
    # T11: Use Case Generation
    # =========================================================================
    # Primary user flow
    asst_t11_user = {
        "use_case_id": f"UC-{sc_id.replace('SCN-', '')}-01",
        "title": f"Execute {title}",
        "primary_actor": primary_actor,
        "preconditions": f"User is authenticated and session possesses active {subdomain.replace('_', ' ')} permissions",
        "main_flow": [
            f"1. {primary_actor} navigates to {title} and submits parameters.",
            "2. System verifies schema, field limits, and business rules.",
            f"3. System fulfills requirement: {reqs[0]['statement']}",
            "4. System persists cryptographic audit record and displays confirmation."
        ],
        "alternate_flows": [
            "2a. Parameter validation fails: System displays error code and halts.",
            "3a. Authorization denied: System logs security exception and alerts compliance."
        ]
    }
    examples.append({
        "task": "T11_use_case",
        "scenario_id": sc_id,
        "subdomain": subdomain,
        "messages": [
            {"role": "system", "content": "Generate formal Use Case specifications from project requirements."},
            {"role": "user", "content": f"Project: {title}\nPrimary Requirement: {reqs[0]['statement']}"},
            {"role": "assistant", "content": json.dumps(asst_t11_user, indent=2)}
        ]
    })

    # Auditor / Operations reconciliation flow
    asst_t11_audit = {
        "use_case_id": f"UC-{sc_id.replace('SCN-', '')}-AUD-02",
        "title": f"Reconcile and Audit {title}",
        "primary_actor": "Compliance Auditor",
        "preconditions": "Auditor is authenticated with read-only audit ledger credentials",
        "main_flow": [
            f"1. Compliance Auditor queries transactional history for {title}.",
            "2. System retrieves immutable tamper-evident logs.",
            "3. System validates SHA-256 hash chains across all ledger entries.",
            "4. System renders verifiable audit export report."
        ],
        "alternate_flows": [
            "3a. Hash chain mismatch detected: System raises immediate P0 security alarm to CISO."
        ]
    }
    examples.append({
        "task": "T11_use_case",
        "scenario_id": sc_id,
        "subdomain": subdomain,
        "messages": [
            {"role": "system", "content": "Generate regulatory compliance and audit use case specifications."},
            {"role": "user", "content": f"Generate compliance audit use case for: {title}"},
            {"role": "assistant", "content": json.dumps(asst_t11_audit, indent=2)}
        ]
    })

    # =========================================================================
    # T12: SRS Section Generation (IEEE 29148)
    # =========================================================================
    # Section 3.2: Functional Requirements
    asst_t12_func = f"### 3.2 Functional Requirements — {title}\n\n"
    for idx, r in enumerate(reqs, 1):
        asst_t12_func += f"**3.2.{idx} [{r['id']}]**\n{r['statement']}\n- Priority: {r['priority']}\n- Category: {r['category']}\n\n"
    examples.append({
        "task": "T12_srs_section",
        "scenario_id": sc_id,
        "subdomain": subdomain,
        "messages": [
            {"role": "system", "content": "Format financial software specifications into standard IEEE 29148 / ISO 25010 SRS sections."},
            {"role": "user", "content": f"Generate Section 3.2 (Functional Requirements) for {title}."},
            {"role": "assistant", "content": asst_t12_func.strip()}
        ]
    })

    # Section 3.3: Non-Functional & Security Requirements
    asst_t12_sec = (
        f"### 3.3 Non-Functional & Security Requirements — {title}\n\n"
        f"**3.3.1 [NFR-{sc_id.replace('SCN-', '')}-01] Data Protection at Rest and in Transit**\n"
        f"The platform shall encrypt all data at rest using AES-256-GCM and all data in transit using TLS 1.3.\n"
        f"- Priority: Must Have\n- Category: Security\n\n"
        f"**3.3.2 [NFR-{sc_id.replace('SCN-', '')}-02] Statutory Audit Retention**\n"
        f"All event logs for {title} shall be stored in tamper-evident write-once-read-many (WORM) storage for 8 years.\n"
        f"- Priority: Must Have\n- Category: Compliance"
    )
    examples.append({
        "task": "T12_srs_section",
        "scenario_id": sc_id,
        "subdomain": subdomain,
        "messages": [
            {"role": "system", "content": "Format financial software specifications into standard IEEE 29148 / ISO 25010 SRS sections."},
            {"role": "user", "content": f"Generate Section 3.3 (Non-Functional and Security Requirements) for {title}."},
            {"role": "assistant", "content": asst_t12_sec}
        ]
    })

    # =========================================================================
    # T13: SDLC Factor Extraction (13 Decision Factors)
    # =========================================================================
    # High-impact regulatory & security factors
    asst_t13_reg = {
        "factors": {
            "regulatory_criticality": {
                "score": sdlc.get("regulatory_criticality", 5),
                "evidence_quote": f"Subject to {scenario.get('regulatory_context', 'financial regulations')}."
            },
            "security_exposure": {
                "score": sdlc.get("security_exposure", 5),
                "evidence_quote": "Handles financial PII and transactional ledgers requiring field-level encryption."
            },
            "requirement_stability": {
                "score": sdlc.get("requirement_stability", 4),
                "evidence_quote": "Core domain workflows governed by published regulatory circulars."
            }
        }
    }
    examples.append({
        "task": "T13_sdlc_factor_extraction",
        "scenario_id": sc_id,
        "subdomain": subdomain,
        "messages": [
            {"role": "system", "content": "Extract the 13 SDLC decision factors with 1-5 ratings and verbatim evidence quotes from project specifications."},
            {"role": "user", "content": f"Project Narrative: {narrative}\nExtract primary regulatory and security SDLC decision factors."},
            {"role": "assistant", "content": json.dumps(asst_t13_reg, indent=2)}
        ]
    })

    # Operational & team complexity factors
    asst_t13_ops = {
        "factors": {
            "complexity_and_scope": {
                "score": 4,
                "evidence_quote": f"Involves distributed financial integrations, multi-system reconciliation, and rigorous SLA compliance in {subdomain.replace('_', ' ')}."
            },
            "team_distribution": {
                "score": 3,
                "evidence_quote": "Multi-disciplinary engineering, QA, and compliance verification squads."
            },
            "fault_tolerance_criticality": {
                "score": 5,
                "evidence_quote": "Financial transactional failure carries severe regulatory penalties and business risk."
            }
        }
    }
    examples.append({
        "task": "T13_sdlc_factor_extraction",
        "scenario_id": sc_id,
        "subdomain": subdomain,
        "messages": [
            {"role": "system", "content": "Extract the 13 SDLC decision factors with 1-5 ratings and verbatim evidence quotes from project specifications."},
            {"role": "user", "content": f"Project Narrative: {narrative}\nExtract operational, team, and fault-tolerance SDLC decision factors."},
            {"role": "assistant", "content": json.dumps(asst_t13_ops, indent=2)}
        ]
    })

    # =========================================================================
    # T14: SDLC Explanation & Trade-offs
    # =========================================================================
    rec_model = sdlc.get("recommended_model", "Agile + V-Model Hybrid")
    # Positive recommendation explanation
    asst_t14_pos = (
        f"{rec_model} is recommended for {title} due to high regulatory criticality "
        f"({sdlc.get('regulatory_criticality', 5)}/5) and stringent audit requirements under {scenario.get('regulatory_context', 'regulations')}. "
        "The model pairs early iterative user-story prototyping for the user experience with formal V-Model verification gates "
        "(unit, integration, and regulatory acceptance testing) to ensure zero statutory compliance regressions prior to deployment."
    )
    examples.append({
        "task": "T14_sdlc_explanation",
        "scenario_id": sc_id,
        "subdomain": subdomain,
        "messages": [
            {"role": "system", "content": "Explain the recommended SDLC methodology using Multi-Criteria Decision Analysis factors and trade-off justifications."},
            {"role": "user", "content": f"Explain why {rec_model} is recommended for {title} based on regulatory criticality of {sdlc.get('regulatory_criticality', 5)}/5."},
            {"role": "assistant", "content": asst_t14_pos}
        ]
    })

    # Rejection explanation (trade-off against pure RAD or unchecked Agile)
    asst_t14_rej = (
        f"Pure Rapid Application Development (RAD) was evaluated and strictly rejected for {title}. "
        f"Given {subdomain.replace('_', ' ')} regulatory exposure and security criticality of {sdlc.get('security_exposure', 5)}/5, "
        "RAD's compressed documentation and lack of formal independent verification gates violate statutory auditability mandates. "
        "Skipping formal architecture reviews risks non-compliant data retention schemas and unacceptable regulatory fines."
    )
    examples.append({
        "task": "T14_sdlc_explanation",
        "scenario_id": sc_id,
        "subdomain": subdomain,
        "messages": [
            {"role": "system", "content": "Explain the recommended SDLC methodology using Multi-Criteria Decision Analysis factors and trade-off justifications."},
            {"role": "user", "content": f"Why is pure Rapid Application Development (RAD) inappropriate for {title} despite potential delivery speed advantages?"},
            {"role": "assistant", "content": asst_t14_rej}
        ]
    })

    return examples


def generate_full_dataset(scenarios_path: str, output_path: str) -> List[Dict[str, Any]]:
    with open(scenarios_path, "r", encoding="utf-8") as f:
        scenarios = json.load(f)

    all_examples = []
    for sc in scenarios:
        exs = generate_task_examples(sc)
        all_examples.extend(exs)

    with open(output_path, "w", encoding="utf-8") as f:
        for ex in all_examples:
            f.write(json.dumps(ex) + "\n")

    print(f"Generated {len(all_examples)} distinct dataset examples in {output_path}")
    return all_examples


if __name__ == "__main__":
    sc_file = os.path.join(os.path.dirname(__file__), "seeds", "scenarios.json")
    out_file = os.path.join(os.path.dirname(__file__), "data", "all_generated.jsonl")
    generate_full_dataset(sc_file, out_file)
