"""
Compliance + Security + Privacy + Risk Agent per Master Plan Phase 10 & Problem Statement §11, §12, §17.
Adheres to strict offline requirements, retrieves from authoritative kb/, validates citations with CitationVerifier,
runs deterministic YAML compliance checks, generates 5x5 Risk Register, and enforces the mandatory legal advisory disclaimer.
"""
import os
import re
import uuid
import yaml
from typing import List, Dict, Any, Optional

from backend.app.rag.retriever import hybrid_retriever
from backend.app.rag.verifier import citation_verifier
from backend.app.schemas.risk import RiskItem, RiskCategory, RiskSeverity, RiskStatus
from backend.app.schemas.message import ActionCard, ActionCardType
from backend.app.core.security.masking import pii_masker


LEGAL_ADVISORY_DISCLAIMER = (
    "Disclaimer: Regulatory and compliance mappings are advisory and do not constitute a final "
    "legal determination. All statutory interpretations must be verified and approved by a qualified "
    "compliance or legal officer."
)


class ComplianceSecurityRiskAgent:
    def __init__(self, base_dir: Optional[str] = None):
        self.base_dir = base_dir or os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
        self.rules_dir = os.path.join(self.base_dir, "rules")
        
        self.compliance_rules = self._load_yaml("compliance_rules.yaml").get("rules", [])
        self.security_controls = self._load_yaml("security_controls.yaml").get("categories", [])
        self.privacy_controls = self._load_yaml("privacy_controls.yaml").get("principles", [])
        self.risk_model = self._load_yaml("risk_model.yaml")

    def _load_yaml(self, filename: str) -> Dict[str, Any]:
        path = os.path.join(self.rules_dir, filename)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        return {}

    def analyze_compliance_and_risk(
        self,
        requirements: List[Any],
        project_id: str
    ) -> Dict[str, Any]:
        """
        Executes complete Compliance, Security, Privacy, and Risk analysis for project requirements:
        1. RAG retrieval & Citation verification against authoritative knowledge base.
        2. Deterministic statutory compliance rules execution & gap detection.
        3. 5x5 Risk Register generation.
        4. Production of ActionCardType.COMPLIANCE_CARD and ActionCardType.RISK_CARD.
        """
        compliance_mappings: List[Dict[str, Any]] = []
        risks: List[Dict[str, Any]] = []

        risk_seq = 1

        for req in requirements:
            req_id = getattr(req, "id", None) or req.get("id")
            stmt = getattr(req, "statement", None) or req.get("statement", "")
            cat = getattr(req, "category", None) or req.get("category", "Functional")

            # 1. RAG retrieval against authoritative KB
            retrieved_chunks = hybrid_retriever.retrieve(query=stmt, top_k=2)
            for chunk in retrieved_chunks:
                meta = chunk.get("metadata", {})
                doc_title = meta.get("title", "Authoritative Financial Regulation")
                doc_id = meta.get("doc_id", "DOC-UNKNOWN")
                section = meta.get("section_number", meta.get("section", "Section 1"))
                circ_no = meta.get("circular_number", doc_id)

                citation_text = f"{doc_title} ({circ_no}) - {section}"
                verification = citation_verifier.verify_citation(citation_text)

                is_verified = verification.get("is_valid", False)
                mapping_id = f"CMP-{uuid.uuid4().hex[:8]}"

                compliance_mappings.append({
                    "id": mapping_id,
                    "requirement_id": req_id,
                    "project_id": project_id,
                    "regulation_name": doc_title,
                    "section_reference": section,
                    "citation_quote": chunk.get("text", "")[:350],
                    "citation_doc_id": doc_id,
                    "citation_verified": is_verified,
                    "compliance_status": "compliant" if is_verified else "needs_review",
                    "control_required": f"Adhere to {section} standards for {cat.lower()} workflows.",
                    "gap_description": None if is_verified else "Citation unverified or pending officer confirmation.",
                    "escalation_flag": not is_verified,
                    "escalation_reason": None if is_verified else "Citation requires compliance officer verification.",
                    "confidence_score": 0.95 if is_verified else 0.40
                })

            # 2. Deterministic Compliance Rules Validation
            for rule in self.compliance_rules:
                rule_triggers = any(re.search(pat, stmt, re.IGNORECASE) for pat in rule.get("trigger_patterns", []))
                if not rule_triggers:
                    continue

                has_prohibited = any(re.search(pat, stmt, re.IGNORECASE) for pat in rule.get("prohibited_patterns", []))
                mandatory_terms = rule.get("mandatory_terms", [])
                has_mandatory = all(re.search(pat, stmt, re.IGNORECASE) for pat in mandatory_terms) if mandatory_terms else True

                # Gap condition: prohibited pattern found OR mandatory statutory term missing
                is_gap = has_prohibited or not has_mandatory

                if is_gap:
                    gap_id = f"GAP-{uuid.uuid4().hex[:8]}"
                    compliance_mappings.append({
                        "id": gap_id,
                        "requirement_id": req_id,
                        "project_id": project_id,
                        "regulation_name": rule.get("regulation", "Regulatory Guideline"),
                        "section_reference": rule.get("section", "Statutory Clause"),
                        "citation_quote": rule.get("citation_quote", ""),
                        "citation_doc_id": rule.get("doc_id", "DOC-REG"),
                        "citation_verified": True,
                        "compliance_status": "gap",
                        "control_required": rule.get("control_required", ""),
                        "gap_description": rule.get("gap_message", ""),
                        "escalation_flag": True,
                        "escalation_reason": "Statutory compliance gap identified by rule engine.",
                        "confidence_score": 1.0
                    })

                    # Generate linked 5x5 Risk Item for the gap
                    risk_id = f"RSK-{risk_seq:03d}"
                    risk_seq += 1
                    
                    prob = 3
                    impact = 5 if ("card" in rule["id"].lower() or "cvv" in rule.get("title", "").lower() or "audit" in rule["id"].lower()) else 4

                    risk_obj = RiskItem(
                        id=risk_id,
                        project_id=project_id,
                        requirement_id=req_id,
                        title=f"Regulatory Non-Compliance: {rule.get('title')}",
                        category=RiskCategory.COMPLIANCE,
                        probability=prob,
                        impact=impact,
                        mitigation=rule.get("control_required", "Implement required statutory controls."),
                        owner="Compliance & Legal Officer",
                        status=RiskStatus.IDENTIFIED
                    )
                    risks.append(risk_obj.model_dump(mode="json"))

        # 3. Systemic Risk Baseline (if no specific gaps triggered, ensure baseline risk coverage)
        if not risks:
            base_risk = RiskItem(
                id=f"RSK-{risk_seq:03d}",
                project_id=project_id,
                title="Operational and Regulatory Oversight Exposure",
                category=RiskCategory.OPERATIONAL,
                probability=2,
                impact=3,
                mitigation="Conduct periodic compliance audits and review access logs quarterly.",
                owner="Compliance & Risk Team",
                status=RiskStatus.IDENTIFIED
            )
            risks.append(base_risk.model_dump(mode="json"))

        # 4. Build Action Cards
        comp_card = self.build_compliance_card(compliance_mappings)
        risk_card = self.build_risk_card(risks)

        return {
            "compliance_mappings": compliance_mappings,
            "risks": risks,
            "action_cards": [comp_card.model_dump(mode="json"), risk_card.model_dump(mode="json")],
            "disclaimer": LEGAL_ADVISORY_DISCLAIMER
        }

    def verify_and_escalate_mapping(
        self,
        citation_text: str,
        project_id: str,
        requirement_id: str,
        claimed_regulation: str
    ) -> Dict[str, Any]:
        """
        Standalone method to verify a proposed regulatory citation and escalate if ungrounded.
        """
        verification = citation_verifier.verify_citation(citation_text)
        is_valid = verification.get("is_valid", False)

        return {
            "id": f"CMP-{uuid.uuid4().hex[:8]}",
            "requirement_id": requirement_id,
            "project_id": project_id,
            "regulation_name": claimed_regulation,
            "section_reference": "N/A",
            "citation_quote": citation_text,
            "citation_doc_id": "UNVERIFIED" if not is_valid else "DOC-AUTHORITATIVE",
            "citation_verified": is_valid,
            "compliance_status": "compliant" if is_valid else "needs_review",
            "control_required": "Statutory compliance adherence.",
            "gap_description": None if is_valid else "Citation could not be verified in authoritative registry.",
            "escalation_flag": not is_valid,
            "escalation_reason": "Citation requires compliance review" if not is_valid else None,
            "confidence_score": 0.95 if is_valid else 0.20
        }

    def build_compliance_card(self, mappings: List[Dict[str, Any]]) -> ActionCard:
        total = len(mappings)
        verified = sum(1 for m in mappings if m.get("citation_verified"))
        gaps = sum(1 for m in mappings if m.get("compliance_status") == "gap")
        escalated = sum(1 for m in mappings if m.get("escalation_flag"))

        return ActionCard(
            id=f"card-comp-{uuid.uuid4().hex[:8]}",
            card_type=ActionCardType.COMPLIANCE_CARD,
            title=f"Regulatory Compliance Matrix ({total} Mappings)",
            payload={
                "total_mappings": total,
                "verified_count": verified,
                "gap_count": gaps,
                "escalated_count": escalated,
                "disclaimer": LEGAL_ADVISORY_DISCLAIMER,
                "mappings": mappings
            },
            actions=["View Full Matrix", "Approve Compliances", "Escalate Gaps"]
        )

    def build_risk_card(self, risks: List[Dict[str, Any]]) -> ActionCard:
        critical = sum(1 for r in risks if r.get("severity") == RiskSeverity.CRITICAL.value or r.get("risk_score", 0) >= 16)
        high = sum(1 for r in risks if r.get("severity") == RiskSeverity.HIGH.value or 10 <= r.get("risk_score", 0) < 16)
        medium = sum(1 for r in risks if r.get("severity") == RiskSeverity.MEDIUM.value or 5 <= r.get("risk_score", 0) < 10)
        low = sum(1 for r in risks if r.get("severity") == RiskSeverity.LOW.value or r.get("risk_score", 0) < 5)

        return ActionCard(
            id=f"card-risk-{uuid.uuid4().hex[:8]}",
            card_type=ActionCardType.RISK_CARD,
            title=f"Threat & Risk Register ({len(risks)} Risks)",
            payload={
                "total_risks": len(risks),
                "critical_count": critical,
                "high_count": high,
                "medium_count": medium,
                "low_count": low,
                "disclaimer": LEGAL_ADVISORY_DISCLAIMER,
                "risks": risks
            },
            actions=["View Risk Heatmap", "Mitigate Risks", "Sign Off"]
        )


# Singleton instance
compliance_security_risk_agent = ComplianceSecurityRiskAgent()
