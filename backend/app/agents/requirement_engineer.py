"""
Requirement Engineer Agent (Phase 6).
Handles:
1. Slot-based grouped question generation (Master Plan A6 / PS §2).
2. Requirement extraction from chat text and uploaded documents with RFC 2119 'shall' normalization.
3. Multi-label classification across the 13 PS canonical categories.
4. Deterministic ID generation and source_statement_id traceability.
5. Assumptions register extraction.
6. DB persistence for Project, Stakeholder, RequirementModel, and Assumption.
"""
import json
import os
import re
import uuid
import yaml
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Tuple

from sqlalchemy.orm import Session

from backend.app.db.models import (
    Project, Stakeholder, RequirementModel, RequirementVersion, Assumption, Message, Chat
)
from backend.app.schemas import (
    Requirement, RequirementCategory, Priority, RequirementStatus, AcceptanceCriteria,
    ActionCard, ActionCardType
)
from backend.app.core.llm_gateway import llm_gateway
from backend.app.core.security.output_validator import StructuredOutputHelper
from backend.app.core.parsers.chunk import DocumentChunk


SLOTS_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../rules/slots.yaml"))
TEMPLATES_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "templates/interviews"))


class RequirementEngineerAgent:
    def __init__(self):
        self.slots_def = self._load_slots()
        self.interview_templates = self._load_templates()

    def _load_slots(self) -> Dict[str, Any]:
        if os.path.exists(SLOTS_PATH):
            with open(SLOTS_PATH, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                return data.get("slots", {})
        return {}

    def _load_templates(self) -> Dict[str, Any]:
        templates = {}
        if os.path.exists(TEMPLATES_DIR):
            for fname in os.listdir(TEMPLATES_DIR):
                if fname.endswith(".yaml"):
                    role = fname.replace(".yaml", "")
                    with open(os.path.join(TEMPLATES_DIR, fname), "r", encoding="utf-8") as f:
                        templates[role] = yaml.safe_load(f)
        return templates

    def generate_grouped_questions(self, idea_text: str, domain: str = "general_finance") -> ActionCard:
        """
        Analyze the stakeholder's initial concept and return grouped clarification questions.
        Groups questions by domain slots with concrete examples and selectable options (one-step answering).
        """
        groups = []
        lowered = idea_text.lower()

        slot_options_map = {
            "identity_and_kyc": [
                "Aadhaar XML + OTP", "Video KYC (V-CIP)", "CKYC Registry Sync", "PAN NSDL Validation"
            ],
            "transaction_limits": [
                "₹50,000 Step-Up 2FA", "Daily Cap ₹2,00,000", "3-Retry Backoff Policy", "Real-Time Fraud Ceilings"
            ],
            "security_and_privacy": [
                "AES-256 Storage Encryption", "TLS 1.3 in Transit", "Granular DPDP Consent Tokens", "Field-Level PII Masking"
            ],
            "audit_and_compliance": [
                "8-Year Tamper-Evident Log", "PMLA 2002 5-Year Storage", "Daily EOD Reconciliation", "Real-Time Suspicious Alerts"
            ],
            "resilience_and_sla": [
                "3-Second P99 Response SLA", "99.95% High Availability", "Multi-AZ Disaster Recovery", "500 Peak TPS"
            ]
        }

        slot_examples_map = {
            "identity_and_kyc": "e.g., UIDAI Aadhaar offline XML verification with OTP and agent-assisted Video KYC fallback",
            "transaction_limits": "e.g., ₹50,000 step-up threshold with ₹2,00,000 daily cumulative velocity cap",
            "security_and_privacy": "e.g., AES-256 field-level encryption for customer PII and TLS 1.3 in transit",
            "audit_and_compliance": "e.g., Immutable WORM audit trails retained for 8 years under RBI guidelines",
            "resilience_and_sla": "e.g., Sub-3-second P99 latency and 99.95% uptime with automated retries"
        }

        for slot_key, slot_info in self.slots_def.items():
            topic = slot_info.get("topic", slot_key.replace("_", " ").title())
            qs = slot_info.get("questions", [])
            group_questions = []

            for q in qs:
                prompt_text = q.get("prompt", "")
                group_questions.append(prompt_text)

            if group_questions:
                groups.append({
                    "slot_key": slot_key,
                    "topic": topic,
                    "questions": group_questions,
                    "options": slot_options_map.get(slot_key, ["Standard Baseline", "Automated Fallback"]),
                    "example": slot_examples_map.get(slot_key, "e.g. Standard compliance baseline")
                })

        if not groups:
            groups = [
                {
                    "slot_key": "transaction_limits",
                    "topic": "Limits, Velocity, and Exceptions",
                    "questions": [
                        "What are the per-transaction ceilings and step-up authentication thresholds?",
                        "What automated compensation or retry flows handle external partner timeouts?"
                    ],
                    "options": ["₹50,000 Step-Up 2FA", "Daily Cap ₹2,00,000", "3-Retry Backoff"],
                    "example": "e.g. ₹50,000 step-up authentication threshold"
                },
                {
                    "slot_key": "resilience_and_sla",
                    "topic": "Resilience, Latency, and SLAs",
                    "questions": [
                        "What are the target P99 response time (SLA) and peak TPS throughput?",
                        "What are the required RPO (data loss) and RTO (recovery time) parameters?"
                    ],
                    "options": ["3-Second P99 SLA", "99.95% Uptime", "500 TPS"],
                    "example": "e.g. P99 response time < 3 seconds"
                }
            ]

        card = ActionCard(
            id=f"card-qgroup-{uuid.uuid4().hex[:8]}",
            card_type=ActionCardType.QUESTION_GROUP,
            title="Project Clarification & Architecture Slots",
            payload={
                "instruction": "Please clarify your project parameters. You can select pre-configured options below or submit answers in one go.",
                "groups": groups
            },
            actions=["Assume Standard Defaults", "Adopt Selected Options", "Submit Answers"]
        )
        return card

    def extract_requirements_from_text(
        self,
        text: str,
        source_statement_id: Optional[str] = None,
        project_id: str = "default_proj",
        domain_prefix: str = "REQ"
    ) -> List[Requirement]:
        """
        Extract structured requirements adhering to RFC 2119 / IEEE 'shall' keywords.
        Ensures 100% of requirements have source_statement_id and valid categories.
        """
        effective_source_id = source_statement_id or f"msg#{uuid.uuid4().hex[:6]}"
        extracted: List[Requirement] = []
        seq = 1

        # Check for local LLM extraction attempt
        llm_extracted = self._extract_via_llm(text, effective_source_id, project_id, domain_prefix)
        if llm_extracted and len(llm_extracted) >= 3:
            return llm_extracted

        # Rule-based + deterministic heuristic extractor (hybrid guarantee)
        clean_text = text.strip()
        sentences = re.split(r'(?<=[.!?\n])\s+', clean_text)
        
        # Financial domain patterns
        patterns = [
            (
                r'(verify|verifying|authenticate|identity|onboard)\s+.*?(aadhaar|kyc|pan|v-cip|customer)',
                RequirementCategory.COMPLIANCE,
                "The system shall verify customer identity using UIDAI Aadhaar offline XML verification with explicit OTP consent.",
                Priority.HIGH,
                "Statutory requirement under RBI KYC Direction Section 16"
            ),
            (
                r'(pan|nsdl|income\s*tax|tax\s*id)',
                RequirementCategory.COMPLIANCE,
                "The system shall validate customer PAN validity against the NSDL database prior to account activation.",
                Priority.HIGH,
                "Statutory compliance under CBDT and RBI regulations"
            ),
            (
                r'(video|v-cip|biometric|agent-assisted|face)',
                RequirementCategory.FUNCTIONAL,
                "The system shall provide an agent-assisted Video-based Customer Identification Process (V-CIP) when biometric checks fail or high-risk thresholds apply.",
                Priority.HIGH,
                "Mandated fallback under RBI Master Direction on Digital KYC"
            ),
            (
                r'(encrypt|aes-256|hsm|field-level|cryptographic|security)',
                RequirementCategory.SECURITY,
                "The system shall encrypt all customer KYC documents and biometric tokens at rest using AES-256 field-level encryption.",
                Priority.HIGH,
                "Data protection standard under RBI Cyber Security Framework and DPDP Act"
            ),
            (
                r'(latency|throughput|seconds|load|tps|sla|response|performance)',
                RequirementCategory.PERFORMANCE,
                "The system shall complete UIDAI XML identity verification within 3 seconds under 95th percentile load.",
                Priority.MEDIUM,
                "Operational SLA to ensure seamless customer onboarding conversion"
            ),
            (
                r'(retain|retention|statutory\s*period|pmla|years|storage|archive)',
                RequirementCategory.DATA,
                "The system shall retain all customer identification records and V-CIP recordings for at least five years from date of account closure in accordance with PMLA 2002.",
                Priority.HIGH,
                "Statutory requirement under Section 12 of PMLA 2002 and RBI KYC Master Direction"
            ),
            (
                r'(limit|ceiling|threshold|step-up|daily|velocity)',
                RequirementCategory.OPERATIONAL,
                "The system shall enforce daily transaction limits and trigger two-factor step-up verification for transactions exceeding configured thresholds.",
                Priority.HIGH,
                "Fraud risk mitigation and operational control"
            ),
            (
                r'(retry|backoff|timeout|exception|failover|resilience)',
                RequirementCategory.AVAILABILITY,
                "The system shall execute automated retries with exponential backoff up to 3 attempts when external partner APIs time out.",
                Priority.MEDIUM,
                "High-availability and resilience requirement"
            ),
            (
                r'(audit|tamper-evident|ledger|worm|log|immutable)',
                RequirementCategory.AUDITABILITY,
                "The system shall maintain an immutable, tamper-evident audit trail for all transaction events.",
                Priority.HIGH,
                "Statutory auditability under RBI IT governance circular"
            ),
            (
                r'(upi|npci|payment|settlement|vpa|transfer|wallet)',
                RequirementCategory.FUNCTIONAL,
                "The system shall execute real-time UPI transaction routing and settlement through NPCI integration rails.",
                Priority.HIGH,
                "Core payment functionality"
            ),
            (
                r'(credit|loan|cibil|experian|bureau|underwriting|disbursement)',
                RequirementCategory.FUNCTIONAL,
                "The system shall pull and evaluate customer credit bureau reports from authorized agencies prior to loan origination.",
                Priority.HIGH,
                "Credit assessment underwriting policy"
            )
        ]

        matched_statements = set()
        proj_tag = project_id.replace("-", "")[:6].upper() if project_id else "GEN"

        # Check explicit "shall/must" sentences in input first
        for s in sentences:
            s_clean = s.strip()
            if not s_clean:
                continue

            # If user already wrote a requirement statement ("The system shall..." or "shall...")
            if re.search(r'\b(shall|must|needs to|required to)\b', s_clean, re.IGNORECASE) and len(s_clean) > 20:
                stmt = s_clean
                if not stmt.lower().startswith("the system shall"):
                    stmt = f"The system shall {stmt[0].lower() + stmt[1:]}"
                if not stmt.endswith("."):
                    stmt = f"{stmt}."
                if stmt not in matched_statements:
                    matched_statements.add(stmt)
                    req_id = f"REQ-{domain_prefix}-{proj_tag}-{seq:03d}"
                    seq += 1
                    extracted.append(Requirement(
                        id=req_id,
                        project_id=project_id,
                        statement=stmt,
                        category=RequirementCategory.FUNCTIONAL,
                        priority=Priority.HIGH,
                        version=1,
                        status=RequirementStatus.DRAFT,
                        source_statement_id=effective_source_id,
                        business_justification="Derived directly from stakeholder plan",
                        acceptance_criteria=[
                            AcceptanceCriteria(
                                id=f"AC-{seq:03d}-01",
                                given="System services are operational and authenticated",
                                when="Processing event is triggered",
                                then=stmt
                            )
                        ]
                    ))

            # Pattern matching against domain rules
            for pat, cat, stmt, pri, just in patterns:
                if re.search(pat, s_clean, re.IGNORECASE) and stmt not in matched_statements:
                    matched_statements.add(stmt)
                    req_id = f"REQ-{domain_prefix}-{proj_tag}-{seq:03d}"
                    seq += 1
                    ac = [
                        AcceptanceCriteria(
                            id=f"AC-{seq:03d}-01",
                            given="Preconditions and authorized caller identity are established",
                            when="The processing event is triggered",
                            then=stmt
                        )
                    ]
                    extracted.append(Requirement(
                        id=req_id,
                        project_id=project_id,
                        statement=stmt,
                        category=cat,
                        priority=pri,
                        version=1,
                        status=RequirementStatus.DRAFT,
                        source_statement_id=effective_source_id,
                        business_justification=just,
                        acceptance_criteria=ac
                    ))

        # Guarantee at least baseline specifications if input had any general intent
        if not extracted:
            default_stmts = [
                (RequirementCategory.COMPLIANCE, "The system shall verify customer identity using UIDAI Aadhaar offline XML verification with explicit OTP consent.", Priority.HIGH, "Statutory compliance under RBI KYC direction"),
                (RequirementCategory.COMPLIANCE, "The system shall validate customer PAN validity against the NSDL database prior to activation.", Priority.HIGH, "Statutory compliance under CBDT and RBI"),
                (RequirementCategory.SECURITY, "The system shall encrypt all customer KYC documents at rest using AES-256 field-level encryption.", Priority.HIGH, "RBI Cyber Security Framework"),
                (RequirementCategory.DATA, "The system shall retain all audit logs and customer records for five years in accordance with PMLA 2002.", Priority.HIGH, "Statutory requirement under PMLA 2002 §12"),
                (RequirementCategory.OPERATIONAL, "The system shall enforce transaction limits and trigger step-up multi-factor authentication for high-risk operations.", Priority.HIGH, "Operational risk controls"),
                (RequirementCategory.PERFORMANCE, "The system shall complete verification and transaction routing within 3 seconds under peak load.", Priority.MEDIUM, "Performance SLA")
            ]
            for cat, stmt, pri, just in default_stmts:
                req_id = f"REQ-{domain_prefix}-{proj_tag}-{seq:03d}"
                seq += 1
                extracted.append(Requirement(
                    id=req_id,
                    project_id=project_id,
                    statement=stmt,
                    category=cat,
                    priority=pri,
                    version=1,
                    status=RequirementStatus.DRAFT,
                    source_statement_id=effective_source_id,
                    business_justification=just,
                    acceptance_criteria=[
                        AcceptanceCriteria(
                            id=f"AC-{seq:03d}-01",
                            given="Operational state",
                            when="Action triggered",
                            then=stmt
                        )
                    ]
                ))
        return extracted

    def _extract_via_llm(
        self,
        text: str,
        source_statement_id: str,
        project_id: str,
        domain_prefix: str
    ) -> List[Requirement]:
        """Attempt extraction via local Ollama LLM if available."""
        prompt = (
            "You are an expert Financial Requirements Engineer. "
            "Extract formal software requirements from the following text. "
            "Output a JSON list of objects with fields: id, statement, category, priority, business_justification. "
            "Every statement must start with 'The system shall'.\n\n"
            f"Input Text:\n{text}\n\nJSON output:"
        )
        try:
            resp = llm_gateway.generate(
                prompt=prompt,
                system_prompt="You are a strict JSON generator. Output valid JSON only.",
                temperature=0.0
            )
            raw = resp.get("response", "").strip()
            # Extract JSON block
            match = re.search(r'\[.*\]', raw, re.DOTALL)
            if match:
                data = json.loads(match.group(0))
                reqs = []
                for idx, item in enumerate(data, 1):
                    stmt = item.get("statement", "")
                    if not stmt.lower().startswith("the system shall"):
                        stmt = f"The system shall {stmt}"
                    cat_val = item.get("category", "Functional")
                    try:
                        cat = RequirementCategory(cat_val)
                    except ValueError:
                        cat = RequirementCategory.FUNCTIONAL
                    
                    pri_val = item.get("priority", "Medium")
                    try:
                        pri = Priority(pri_val)
                    except ValueError:
                        pri = Priority.MEDIUM

                    reqs.append(Requirement(
                        id=f"REQ-{domain_prefix}-{idx:03d}",
                        project_id=project_id,
                        statement=stmt,
                        category=cat,
                        priority=pri,
                        version=1,
                        status=RequirementStatus.DRAFT,
                        source_statement_id=source_statement_id,
                        business_justification=item.get("business_justification", "Extracted from stakeholder specification"),
                        acceptance_criteria=[
                            AcceptanceCriteria(
                                id=f"AC-{idx:03d}-01",
                                given="System is operating normally",
                                when="Trigger condition occurs",
                                then=stmt
                            )
                        ]
                    ))
                return reqs
        except Exception:
            pass
        return []

    def extract_assumptions(self, text: str, project_id: str) -> List[Assumption]:
        """Extract explicit and default assumptions into Assumption models."""
        assumptions = []
        lowered = text.lower()

        if "assume standard defaults" in lowered or "assume defaults" in lowered or "default" in lowered:
            assumptions.append(Assumption(
                id=str(uuid.uuid4()),
                project_id=project_id,
                statement="Standard digital KYC using CKYC registry with Aadhaar OTP fallback is assumed.",
                rationale="Stakeholder requested default standard parameters during intake.",
                category="Compliance",
                status="unverified"
            ))
            assumptions.append(Assumption(
                id=str(uuid.uuid4()),
                project_id=project_id,
                statement="Transactions exceeding 50,000 INR require two-factor step-up authentication.",
                rationale="Baseline financial fraud risk standard.",
                category="Operational",
                status="unverified"
            ))
            assumptions.append(Assumption(
                id=str(uuid.uuid4()),
                project_id=project_id,
                statement="Data at rest is protected via AES-256-GCM and API traffic uses TLS 1.3.",
                rationale="Statutory baseline under RBI Cyber Security Framework.",
                category="Security",
                status="unverified"
            ))

        return assumptions

    def process_chat_message(
        self,
        db: Session,
        chat: Chat,
        user_message: Message,
        uploaded_chunks: Optional[List[DocumentChunk]] = None
    ) -> Dict[str, Any]:
        """
        Main orchestration entry point for a chat turn.
        Returns response text and action cards to append.
        """
        # 1. Ensure Project exists for this chat
        project = db.query(Project).filter(Project.chat_id == chat.id).first()
        if not project:
            project = Project(
                id=str(uuid.uuid4()),
                chat_id=chat.id,
                title=chat.title,
                domain="general_finance",
                description=user_message.content_masked
            )
            db.add(project)
            db.flush()

        msg_content = user_message.content_masked.strip()
        all_chunks = uploaded_chunks or []

        # 2. Determine state: If chat has only 1 user message and no files, it is INTAKE -> provide grouped questions
        user_msg_count = db.query(Message).filter(
            Message.chat_id == chat.id,
            Message.role == "user"
        ).count()

        if user_msg_count <= 1 and not all_chunks:
            # First turn: Return grouped questions
            card = self.generate_grouped_questions(msg_content, project.domain)
            resp_text = (
                "Hello! I am your AI Requirement Engineer. To establish a complete, compliant financial requirements baseline, "
                "I have identified key requirements slots across Workflow, Security, Limits, and Auditability.\n\n"
                "Please review the grouped questions in the card below. You can answer directly or select 'Assume Standard Defaults'."
            )
            chat.state = "INTERVIEW_IN_PROGRESS"
            db.commit()
            return {
                "text": resp_text,
                "action_cards": [card.model_dump(mode="json")]
            }

        # 3. Subsequent turn: Extract requirements from answers and/or documents
        domain_prefix = "REQ"
        combined_text = msg_content
        if all_chunks:
            chunk_texts = [f"[{c.chunk_id}]\n{c.text}" for c in all_chunks]
            combined_text += "\n\n" + "\n\n".join(chunk_texts)
            domain_prefix = "DOC"

        source_id = user_message.id if not all_chunks else all_chunks[0].chunk_id
        extracted_reqs = self.extract_requirements_from_text(
            text=combined_text,
            source_statement_id=source_id,
            project_id=project.id,
            domain_prefix=domain_prefix
        )

        # 4. Extract assumptions
        assumptions = self.extract_assumptions(combined_text, project.id)
        for a in assumptions:
            db.add(a)

        # 5. Persist extracted requirements in DB
        persisted_reqs = []
        for req in extracted_reqs:
            # Check for existing requirement with same statement in project
            existing = db.query(RequirementModel).filter(
                RequirementModel.project_id == project.id,
                RequirementModel.statement == req.statement
            ).first()
            if not existing:
                final_id = req.id
                while db.query(RequirementModel).filter(RequirementModel.id == final_id).first():
                    final_id = f"{req.id}-{uuid.uuid4().hex[:4].upper()}"
                req.id = final_id

                model = RequirementModel(
                    id=final_id,
                    project_id=project.id,
                    statement=req.statement,
                    category=req.category.value,
                    priority=req.priority.value,
                    version=1,
                    status=req.status.value,
                    source_statement_id=req.source_statement_id,
                    business_justification=req.business_justification,
                    dependencies_json=json.dumps(req.dependencies),
                    acceptance_criteria_json=json.dumps([ac.model_dump(mode="json") for ac in req.acceptance_criteria])
                )
                db.add(model)
                db.flush()

                # Add initial version snapshot
                ver = RequirementVersion(
                    id=str(uuid.uuid4()),
                    requirement_id=model.id,
                    version=1,
                    statement=model.statement,
                    category=model.category,
                    priority=model.priority,
                    status=model.status,
                    changed_by="RequirementEngineerAgent",
                    change_reason="Initial automated extraction"
                )
                db.add(ver)
                persisted_reqs.append(req)

        db.commit()

        # 6. Build summary ActionCard
        cat_counts = {}
        for r in extracted_reqs:
            cat_counts[r.category.value] = cat_counts.get(r.category.value, 0) + 1

        summary_card = ActionCard(
            id=f"card-extract-{uuid.uuid4().hex[:8]}",
            card_type=ActionCardType.REQUIREMENT_CARD,
            title=f"Structured Requirements Extracted ({len(extracted_reqs)} Total)",
            payload={
                "total_requirements": len(extracted_reqs),
                "category_breakdown": cat_counts,
                "assumptions_recorded": len(assumptions),
                "requirements": [r.model_dump(mode="json") for r in extracted_reqs]
            },
            actions=["View Traceability", "Analyze Quality", "Baseline Approval"]
        )

        resp_text = (
            f"Successfully extracted **{len(extracted_reqs)} structured requirements** adhering to RFC 2119 / IEEE standards.\n\n"
            f"- **Breakdown**: {', '.join(f'{k}: {v}' for k, v in cat_counts.items())}\n"
            f"- **Assumptions**: {len(assumptions)} statutory and operational defaults recorded in the Assumptions Register.\n"
            f"- **Provenance**: All requirements linked to source statement `{source_id}`."
        )

        chat.state = "REQUIREMENTS_EXTRACTED"
        db.commit()

        return {
            "text": resp_text,
            "action_cards": [summary_card.model_dump(mode="json")]
        }


# Singleton instance
requirement_engineer_agent = RequirementEngineerAgent()
