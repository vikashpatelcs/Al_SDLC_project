"""
Analysis Engine Agent for Phase 8: Requirement Analysis + Issue Detection.
Implements all 10 Problem Statement §10 quality dimensions:
1. Ambiguity & Non-measurability
2. Conflict & Contradiction
3. Incompleteness & Missing Slots
4. Feasibility & Untestable Claims
5. Duplication & Overlap
6. Regulatory & Compliance Gaps
7. Weak Words
8. Missing Actor or Imperative
9. Undefined Acronyms
10. Missing Traceability Source

Provides suggestion generation with rationale, database persistence for RequirementIssueModel,
re-analysis loop on requirement updates, and ActionCard payloads per Master Plan A13.
"""
import os
import re
import uuid
import yaml
from typing import Any, Dict, List, Optional, Set, Tuple
from sqlalchemy.orm import Session

from backend.app.db.models import RequirementModel, RequirementIssueModel, Project
from backend.app.schemas.issue import IssueType, IssueSeverity, IssueStatus
from backend.app.schemas.message import ActionCard, ActionCardType
from backend.app.rag.retriever import HybridRetriever


RULES_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../rules"))


class AnalysisEngine:
    def __init__(self, rules_dir: Optional[str] = None):
        self.rules_dir = rules_dir or RULES_DIR
        self._load_rules()
        self.retriever: Optional[HybridRetriever] = None

    def _load_rules(self) -> None:
        """Load deterministic rule dictionaries and glossaries."""
        # Weak words
        ww_path = os.path.join(self.rules_dir, "weak_words.yaml")
        if os.path.exists(ww_path):
            with open(ww_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
                self.weak_words = data.get("weak_words", [])
        else:
            self.weak_words = []

        # Glossary
        glossary_path = os.path.join(self.rules_dir, "glossary.yaml")
        if os.path.exists(glossary_path):
            with open(glossary_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
                self.glossary = data.get("acronyms", {})
        else:
            self.glossary = {}

        # Quality rules
        qr_path = os.path.join(self.rules_dir, "quality_rules.yaml")
        if os.path.exists(qr_path):
            with open(qr_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
                self.quality_rules = {d["id"]: d for d in data.get("dimensions", [])}
        else:
            self.quality_rules = {}

        # Common known technical words to not flag as undefined acronyms
        self.standard_known_acronyms: Set[str] = {
            "AI", "ID", "IT", "XML", "OTP", "API", "JSON", "URL", "HTTP", "HTTPS", "REST", "SQL",
            "SHA", "AES", "TLS", "PDF", "CSV", "DOCX", "EML", "RFC", "IEEE", "UI", "UX", "DB", "INR"
        }

    def _get_retriever(self) -> Optional[HybridRetriever]:
        """Lazy loader for HybridRetriever to cross-reference regulations."""
        if self.retriever is None:
            try:
                self.retriever = HybridRetriever(collection_name="financial_kb_authoritative")
            except Exception:
                self.retriever = None
        return self.retriever

    # ---------------------------------------------------------
    # 10 Core Quality Detectors
    # ---------------------------------------------------------

    def detect_weak_words(self, statement: str) -> List[Dict[str, Any]]:
        """Detector 7: Scan for weak, subjective, or conversational terms."""
        issues = []
        lowered = statement.lower()

        for entry in self.weak_words:
            word = entry["word"].lower()
            pattern = r'\b' + re.escape(word) + r'\b'
            if re.search(pattern, lowered):
                issues.append({
                    "issue_type": entry.get("category", IssueType.WEAK_WORD.value),
                    "severity": entry.get("severity", IssueSeverity.MEDIUM.value),
                    "detail": f"Contains weak word or phrase '{word}'",
                    "suggestion": f"Replace '{word}' with measurable criteria such as '{entry.get('suggestion_template', '')}'",
                    "rationale": entry.get("reason", "Vague term degrades verifiable testing and implementation accuracy.")
                })
        return issues

    def detect_ambiguity(self, statement: str) -> List[Dict[str, Any]]:
        """Detector 1: Identify unquantified adjectives and non-measurable speed/capacity descriptors."""
        issues = []
        lowered = statement.lower()

        ambiguity_triggers = [
            (r'\b(as soon as possible|at the earliest|fast|quick|quickly|rapidly)\b',
             "Unquantified response SLA.",
             "Define specific response SLA threshold in milliseconds or seconds (e.g. <= 2.5 seconds under 95th percentile load)."),
            (r'\b(seamless|seamlessly|user-friendly|intuitive)\b',
             "Subjective user experience descriptor lacking verifiable acceptance criteria.",
             "Specify concrete workflow constraints (e.g. requiring no manual re-entry of data, completion in <= 3 steps)."),
            (r'\b(approximately|about|roughly)\b',
             "Imprecise numerical expectation without error tolerance margin.",
             "Specify exact value and tolerance bounds (e.g. +/- 2%).")
        ]

        for pattern, rationale, suggestion in ambiguity_triggers:
            match = re.search(pattern, lowered)
            if match:
                matched_phrase = match.group(0)
                issues.append({
                    "issue_type": IssueType.AMBIGUITY.value,
                    "severity": IssueSeverity.MEDIUM.value,
                    "detail": f"Vague phrase '{matched_phrase}' detected.",
                    "suggestion": suggestion,
                    "rationale": rationale
                })
        return issues

    def detect_incompleteness(self, statement: str) -> List[Dict[str, Any]]:
        """Detector 3: Identify missing operational parameters, open-ended truncations, or unhandled conditions."""
        issues = []
        lowered = statement.lower()

        # Open-ended truncation
        if re.search(r'\b(etc\.?|and so on|and so forth)\b', lowered):
            issues.append({
                "issue_type": IssueType.INCOMPLETENESS.value,
                "severity": IssueSeverity.HIGH.value,
                "detail": "Open-ended truncation ('etc.') leaves requirement scope undefined.",
                "suggestion": "Explicitly enumerate all permissible parameters or cases instead of using truncation.",
                "rationale": "Truncation prevents complete test boundary enumeration."
            })

        # Underspecified conditionals
        if re.search(r'\b(as appropriate|if necessary|where applicable)\b', lowered):
            issues.append({
                "issue_type": IssueType.INCOMPLETENESS.value,
                "severity": IssueSeverity.HIGH.value,
                "detail": "Underspecified condition without deterministic predicate.",
                "suggestion": "Specify the exact boolean condition or trigger criteria that activates this behavior.",
                "rationale": "Ambiguous branching leaves business logic implementation undefined."
            })

        # Financial transaction missing limits
        is_transaction = any(k in lowered for k in ["transfer", "payment", "disbursement", "withdrawal", "p2p"])
        has_limit = any(k in lowered for k in ["limit", "threshold", "cap", "inr", "rs", "maximum", "amount"])
        if is_transaction and not has_limit:
            issues.append({
                "issue_type": IssueType.INCOMPLETENESS.value,
                "severity": IssueSeverity.MEDIUM.value,
                "detail": "Financial transaction requirement lacks explicit velocity or value limit specification.",
                "suggestion": "Define per-transaction cap and daily cumulative maximum limit.",
                "rationale": "Statutory risk guidelines mandate bounded transaction amounts to prevent fraud."
            })

        return issues

    def detect_untestable_and_infeasible(self, statement: str) -> List[Dict[str, Any]]:
        """Detector 4: Flag absolute or theoretically unprovable assertions."""
        issues = []
        lowered = statement.lower()

        unverifiable = [
            ("bug-free", "Absolute perfection cannot be proven mathematically or empirically in software.",
             "Replace with 'shall pass 100% of integration test suites with zero critical or blocker defects'."),
            ("zero latency", "Zero latency is physically impossible in network and database architectures.",
             "Specify SLA latency bound (e.g. 'with 99th percentile round-trip time under 50ms')."),
            ("unhackable", "Absolute security is an invalid architectural claim.",
             "Specify cryptographic posture and penetration testing passing criteria."),
            ("infinitely scalable", "Infinite scalability is commercially and technically unachievable.",
             "Specify target throughput limit (e.g. 'horizontally scalable to support 5,000 transactions per second')."),
            ("100% secure", "Absolute security assertion is unverifiable.",
             "Specify compliance with RBI Cyber Security Framework and AES-256/TLS 1.3 standards.")
        ]

        for phrase, rationale, suggestion in unverifiable:
            if phrase in lowered:
                issues.append({
                    "issue_type": IssueType.UNTESTABLE.value,
                    "severity": IssueSeverity.HIGH.value,
                    "detail": f"Untestable assertion '{phrase}' detected.",
                    "suggestion": suggestion,
                    "rationale": rationale
                })
        return issues

    def detect_missing_actor_and_imperative(self, statement: str) -> List[Dict[str, Any]]:
        """Detector 8: Enforce IEEE-830 modal imperative ('shall') and defined actor."""
        issues = []
        lowered = statement.lower()

        # Check imperative
        has_shall = "shall" in lowered or "must" in lowered
        if not has_shall:
            issues.append({
                "issue_type": IssueType.AMBIGUITY.value,
                "severity": IssueSeverity.MEDIUM.value,
                "detail": "Statement lacks mandatory IEEE-830 imperative modal ('shall' or 'must').",
                "suggestion": f"Rephrase statement using active imperative: 'The system shall {statement.strip()}'.",
                "rationale": "IEEE-830 standard requires explicit modals ('shall') to distinguish binding requirements from aspirational goals."
            })

        # Check actor
        actors = ["system", "application", "service", "user", "admin", "agent", "platform", "component"]
        has_actor = any(re.search(r'\b' + a + r'\b', lowered) for a in actors)
        if not has_actor:
            issues.append({
                "issue_type": IssueType.INCOMPLETENESS.value,
                "severity": IssueSeverity.MEDIUM.value,
                "detail": "Requirement lacks an explicit subject actor (e.g. 'The system', 'The user').",
                "suggestion": "Explicitly identify the responsible component: 'The system shall...'",
                "rationale": "Without a designated actor, system boundary ownership and responsibility cannot be assigned."
            })

        return issues

    def detect_undefined_acronyms(self, statement: str) -> List[Dict[str, Any]]:
        """Detector 9: Flag uppercase acronyms (>= 2 chars) not in glossary."""
        issues = []
        # Find uppercase words with 2 or more letters
        words = re.findall(r'\b[A-Z]{2,}(?:-[A-Z]{2,})?\b', statement)

        for w in set(words):
            if w not in self.glossary and w not in self.standard_known_acronyms:
                issues.append({
                    "issue_type": IssueType.WEAK_WORD.value,
                    "severity": IssueSeverity.LOW.value,
                    "detail": f"Undefined acronym '{w}' detected.",
                    "suggestion": f"Define '{w}' upon first occurrence or expand to full name.",
                    "rationale": f"Acronym '{w}' is not catalogued in the canonical financial glossary."
                })
        return issues

    def detect_missing_source(self, requirement: RequirementModel) -> List[Dict[str, Any]]:
        """Detector 10: Identify requirements lacking provenance source links."""
        issues = []
        if not requirement.source_statement_id or requirement.source_statement_id.strip() == "":
            issues.append({
                "issue_type": IssueType.MISSING_SOURCE.value,
                "severity": IssueSeverity.HIGH.value,
                "detail": f"Requirement {requirement.id} has no source_statement_id traceability link.",
                "suggestion": "Link requirement to originating message ID or uploaded document chunk ID.",
                "rationale": "Auditability requires end-to-end traceability from stakeholder utterance to requirement."
            })
        return issues

    def detect_regulatory_gaps(self, statement: str) -> List[Dict[str, Any]]:
        """Detector 6: Detect statutory and regulatory violations."""
        issues = []
        lowered = statement.lower()

        qr_reg = self.quality_rules.get("regulatory_gap", {})
        violations = qr_reg.get("violations", [])

        for v in violations:
            pattern = v["pattern"]
            if re.search(pattern, lowered):
                issues.append({
                    "issue_type": IssueType.REGULATORY_GAP.value,
                    "severity": IssueSeverity.CRITICAL.value,
                    "detail": f"Regulatory violation: {v['violation']}",
                    "suggestion": v["suggestion"],
                    "rationale": f"Statutory mandate under {v['citation']}."
                })

        # Specific hard checks on statutory financial rules
        if "cvv" in lowered and ("store" in lowered or "save" in lowered or "retain" in lowered):
            if not any(i["detail"].startswith("Regulatory violation") for i in issues):
                issues.append({
                    "issue_type": IssueType.REGULATORY_GAP.value,
                    "severity": IssueSeverity.CRITICAL.value,
                    "detail": "Storing sensitive CVV card security data post-authorization.",
                    "suggestion": "The system shall never store CVV/CVV2 numbers post-authorization per RBI Card Directions.",
                    "rationale": "RBI Master Direction on Credit/Debit Card Issuance Section 17.2 strictly prohibits persisting CVV."
                })

        if "aadhaar" in lowered and ("verify" in lowered or "xml" in lowered) and ("consent" not in lowered and "otp" not in lowered):
            issues.append({
                "issue_type": IssueType.REGULATORY_GAP.value,
                "severity": IssueSeverity.HIGH.value,
                "detail": "Aadhaar verification without explicit user consent mechanism.",
                "suggestion": "The system shall obtain explicit customer consent prior to UIDAI Aadhaar verification.",
                "rationale": "UIDAI Regulations and DPDP Act 2023 require informed consent before identity token processing."
            })

        return issues

    # ---------------------------------------------------------
    # Pairwise Project-Level Detectors
    # ---------------------------------------------------------

    def detect_conflicts(self, requirements: List[RequirementModel]) -> List[Dict[str, Any]]:
        """Detector 2: Detect opposing directives between requirement pairs in the project."""
        issues = []
        qr_conf = self.quality_rules.get("conflict", {})
        antagonistic_pairs = qr_conf.get("antagonistic_patterns", [])

        # Check explicit antagonistic pairs
        for i in range(len(requirements)):
            req_a = requirements[i]
            stmt_a = req_a.statement.lower()

            for j in range(i + 1, len(requirements)):
                req_b = requirements[j]
                stmt_b = req_b.statement.lower()

                for rule in antagonistic_pairs:
                    p1, p2 = rule["pair"][0].lower(), rule["pair"][1].lower()
                    if (p1 in stmt_a and p2 in stmt_b) or (p2 in stmt_a and p1 in stmt_b):
                        issues.append({
                            "requirement_id": req_a.id,
                            "conflicting_requirement_id": req_b.id,
                            "issue_type": IssueType.CONFLICT.value,
                            "severity": IssueSeverity.CRITICAL.value,
                            "detail": f"Conflict detected with {req_b.id}: {rule['description']}",
                            "suggestion": f"Reconcile conflict between {req_a.id} ('{rule['pair'][0]}') and {req_b.id} ('{rule['pair'][1]}').",
                            "rationale": rule["rationale"]
                        })
                        issues.append({
                            "requirement_id": req_b.id,
                            "conflicting_requirement_id": req_a.id,
                            "issue_type": IssueType.CONFLICT.value,
                            "severity": IssueSeverity.CRITICAL.value,
                            "detail": f"Conflict detected with {req_a.id}: {rule['description']}",
                            "suggestion": f"Reconcile conflict between {req_b.id} and {req_a.id}.",
                            "rationale": rule["rationale"]
                        })

        return issues

    def detect_duplicates(self, requirements: List[RequirementModel]) -> List[Dict[str, Any]]:
        """Detector 5: Compute pairwise token overlap to flag duplicate requirements (>= 0.85 similarity)."""
        issues = []
        threshold = 0.85

        def get_tokens(text: str) -> Set[str]:
            stopwords = {"the", "system", "shall", "and", "or", "to", "of", "in", "for", "with", "a", "an", "is"}
            words = set(re.findall(r'\b\w+\b', text.lower()))
            return words - stopwords

        for i in range(len(requirements)):
            req_a = requirements[i]
            tokens_a = get_tokens(req_a.statement)
            if not tokens_a:
                continue

            for j in range(i + 1, len(requirements)):
                req_b = requirements[j]
                tokens_b = get_tokens(req_b.statement)
                if not tokens_b:
                    continue

                intersection = len(tokens_a & tokens_b)
                union = len(tokens_a | tokens_b)
                similarity = intersection / union if union > 0 else 0.0

                if similarity >= threshold:
                    issues.append({
                        "requirement_id": req_b.id,
                        "duplicate_of_id": req_a.id,
                        "issue_type": IssueType.DUPLICATE.value,
                        "severity": IssueSeverity.MEDIUM.value,
                        "detail": f"Requirement is a duplicate of {req_a.id} with similarity {similarity:.2f}.",
                        "suggestion": f"Consolidate {req_b.id} into {req_a.id} to eliminate redundancy.",
                        "rationale": f"High lexical overlap indicates duplicate specification of the same capability."
                    })

        return issues

    # ---------------------------------------------------------
    # Comprehensive Project Analysis & Re-analysis
    # ---------------------------------------------------------

    def analyze_requirement(self, requirement: RequirementModel) -> List[Dict[str, Any]]:
        """Run all single-requirement detectors on an individual requirement."""
        stmt = requirement.statement
        all_issues = []

        all_issues.extend(self.detect_ambiguity(stmt))
        all_issues.extend(self.detect_weak_words(stmt))
        all_issues.extend(self.detect_incompleteness(stmt))
        all_issues.extend(self.detect_untestable_and_infeasible(stmt))
        all_issues.extend(self.detect_missing_actor_and_imperative(stmt))
        all_issues.extend(self.detect_undefined_acronyms(stmt))
        all_issues.extend(self.detect_regulatory_gaps(stmt))
        all_issues.extend(self.detect_missing_source(requirement))

        for iss in all_issues:
            iss["requirement_id"] = requirement.id

        return all_issues

    def analyze_project(
        self,
        project_id: str,
        requirements: List[RequirementModel],
        db: Optional[Session] = None
    ) -> List[RequirementIssueModel]:
        """Run full 10-dimension analysis across all project requirements and persist to DB."""
        raw_issues: List[Dict[str, Any]] = []

        # 1. Single requirement checks
        for r in requirements:
            raw_issues.extend(self.analyze_requirement(r))

        # 2. Pairwise project checks
        raw_issues.extend(self.detect_conflicts(requirements))
        raw_issues.extend(self.detect_duplicates(requirements))

        persisted_issues: List[RequirementIssueModel] = []
        seq = 1

        for raw in raw_issues:
            issue_id = f"ISS-{project_id[:6].upper()}-{seq:03d}"
            seq += 1

            model = RequirementIssueModel(
                id=issue_id,
                requirement_id=raw.get("requirement_id"),
                project_id=project_id,
                issue_type=raw["issue_type"],
                severity=raw.get("severity", IssueSeverity.MEDIUM.value),
                detail=raw["detail"],
                suggestion=raw["suggestion"],
                rationale=raw["rationale"],
                status=IssueStatus.OPEN.value
            )
            persisted_issues.append(model)
            if db:
                db.add(model)

        if db:
            try:
                db.flush()
            except Exception:
                pass

        return persisted_issues

    def reanalyze_requirement(
        self,
        requirement: RequirementModel,
        new_statement: str,
        db: Session
    ) -> Tuple[RequirementModel, int, List[RequirementIssueModel]]:
        """
        Re-analysis loop: update requirement statement, re-run checks,
        resolve fixed issues, and register new issues if any.
        Returns: (updated_requirement, resolved_count, remaining_open_issues)
        """
        requirement.statement = new_statement
        requirement.version += 1

        # Retrieve existing open issues
        existing_issues = db.query(RequirementIssueModel).filter(
            RequirementIssueModel.requirement_id == requirement.id,
            RequirementIssueModel.status == IssueStatus.OPEN.value
        ).all()

        # Run fresh analysis on new statement
        new_raw_issues = self.analyze_requirement(requirement)

        # Check existing issues against new raw findings: if an issue type is cleared, resolve it
        new_issue_types = {raw["issue_type"] for raw in new_raw_issues}
        resolved_count = 0

        for old_issue in existing_issues:
            if old_issue.issue_type not in new_issue_types:
                old_issue.status = IssueStatus.RESOLVED.value
                resolved_count += 1

        # Add any newly introduced issues
        existing_types = {i.issue_type for i in existing_issues if i.status == IssueStatus.OPEN.value}
        remaining_issues = [i for i in existing_issues if i.status == IssueStatus.OPEN.value]

        existing_count = db.query(RequirementIssueModel).filter(
            RequirementIssueModel.project_id == requirement.project_id
        ).count()
        seq = existing_count + 1
        for raw in new_raw_issues:
            if raw["issue_type"] not in existing_types:
                new_id = f"ISS-{requirement.project_id[:6].upper()}-{seq:03d}"
                while db.query(RequirementIssueModel).filter(RequirementIssueModel.id == new_id).first():
                    seq += 1
                    new_id = f"ISS-{requirement.project_id[:6].upper()}-{seq:03d}"
                seq += 1
                new_issue_model = RequirementIssueModel(
                    id=new_id,
                    requirement_id=requirement.id,
                    project_id=requirement.project_id,
                    issue_type=raw["issue_type"],
                    severity=raw.get("severity", IssueSeverity.MEDIUM.value),
                    detail=raw["detail"],
                    suggestion=raw["suggestion"],
                    rationale=raw["rationale"],
                    status=IssueStatus.OPEN.value
                )
                db.add(new_issue_model)
                remaining_issues.append(new_issue_model)

        db.flush()
        return requirement, resolved_count, remaining_issues

    # ---------------------------------------------------------
    # ActionCard Generation
    # ---------------------------------------------------------

    def build_issue_summary_card(
        self,
        requirements: List[RequirementModel],
        issues: List[RequirementIssueModel]
    ) -> ActionCard:
        """Construct the Master Plan Phase 8 'Requirements found: N / Complete X / ...' ActionCard."""
        total_reqs = len(requirements)
        open_issues = [i for i in issues if i.status == IssueStatus.OPEN.value]

        # Requirement IDs that have at least one open issue
        flawed_req_ids = {i.requirement_id for i in open_issues if i.requirement_id}
        complete_count = max(0, total_reqs - len(flawed_req_ids))

        ambiguous_count = len([i for i in open_issues if i.issue_type in [IssueType.AMBIGUITY.value, IssueType.NON_MEASURABLE.value, IssueType.WEAK_WORD.value]])
        conflicting_count = len([i for i in open_issues if i.issue_type == IssueType.CONFLICT.value])
        regulatory_count = len([i for i in open_issues if i.issue_type == IssueType.REGULATORY_GAP.value])
        untestable_count = len([i for i in open_issues if i.issue_type in [IssueType.UNTESTABLE.value, IssueType.FEASIBILITY.value]])
        incomplete_count = len([i for i in open_issues if i.issue_type == IssueType.INCOMPLETENESS.value])
        duplicate_count = len([i for i in open_issues if i.issue_type == IssueType.DUPLICATE.value])

        payload = {
            "total_requirements": total_reqs,
            "complete_count": complete_count,
            "ambiguous_count": ambiguous_count,
            "conflicting_count": conflicting_count,
            "regulatory_gap_count": regulatory_count,
            "untestable_count": untestable_count,
            "incomplete_count": incomplete_count,
            "duplicate_count": duplicate_count,
            "total_open_issues": len(open_issues),
            "summary_text": f"Requirements found: {total_reqs} | Complete: {complete_count} | Ambiguous: {ambiguous_count} | Conflicting: {conflicting_count} | Regulatory gaps: {regulatory_count}",
            "issues": [
                {
                    "id": i.id,
                    "requirement_id": i.requirement_id,
                    "issue_type": i.issue_type,
                    "severity": i.severity,
                    "detail": i.detail,
                    "suggestion": i.suggestion,
                    "rationale": i.rationale,
                    "status": i.status
                }
                for i in open_issues
            ]
        }

        return ActionCard(
            id=f"card-issues-{uuid.uuid4().hex[:8]}",
            card_type=ActionCardType.ISSUE_SUMMARY,
            title=f"Requirement Analysis Summary ({len(open_issues)} Issues Identified)",
            payload=payload,
            actions=["Review Issues", "Accept Suggestions", "Re-analyse All"]
        )


analysis_engine = AnalysisEngine()
