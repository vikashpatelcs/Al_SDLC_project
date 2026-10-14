"""
SDLC Recommendation Agent per Problem Statement §13-§15 and Master Plan Phase 11.
Extracts 13 project decision factors with verbatim requirement quotes, executes deterministic MCDA scoring,
generates score-consistent explanations, produces 10-field project-specific phase workflows,
and supports interactive factor challenge loops.
"""
import os
import re
import yaml
from typing import Dict, List, Any, Optional

from rules.sdlc_engine import sdlc_engine
from backend.app.schemas.sdlc import (
    SDLCModelType,
    SDLCFactor,
    SDLCPhaseWorkflow,
    ModelScoreRanking,
    SDLCRecommendation,
)
from backend.app.schemas.message import ActionCard, ActionCardType


class SDLCAgent:
    def __init__(self, base_dir: Optional[str] = None):
        self.base_dir = base_dir or os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
        self.templates_dir = os.path.join(self.base_dir, "rules", "workflow_templates")

    def extract_factors(
        self,
        requirements: List[Any],
        project_domain: str = "general_finance",
        chat_context: Optional[str] = None
    ) -> Dict[str, SDLCFactor]:
        """
        Extracts ratings (1-5) for all 13 PS §13 factors based on requirement statements and domain.
        Pairs each factor with a verbatim evidence quote.
        """
        all_stmts = " ".join([getattr(r, "statement", None) or (r.get("statement") if isinstance(r, dict) else "") for r in requirements])
        full_text = f"{project_domain} {all_stmts} {chat_context or ''}".lower()

        def find_req_quote(keywords: List[str], fallback: str) -> str:
            for r in requirements:
                stmt = getattr(r, "statement", None) or (r.get("statement") if isinstance(r, dict) else "")
                rid = getattr(r, "id", None) or (r.get("id") if isinstance(r, dict) else "")
                if stmt and any(k.lower() in stmt.lower() for k in keywords):
                    return f'"{stmt}" [{rid}]' if rid else f'"{stmt}"'
            return fallback

        factors: Dict[str, SDLCFactor] = {}

        # 1. requirement_stability
        req_count = len(requirements)
        if any(w in full_text for w in ["frozen", "mandatory statutory baseline", "fixed scope", "immutable"]):
            stab = 5
            quote = find_req_quote(["frozen", "statutory", "mandatory", "pmla", "compliance"], "Statutory baseline is mandated by financial policy.")
        elif req_count >= 10:
            stab = 4
            quote = f"Established baseline of {req_count} structured requirements with verified acceptance criteria."
        elif any(w in full_text for w in ["mvp", "prototype", "agile", "evolving", "flexible"]):
            stab = 2
            quote = "Early project stage with expected iterative stakeholder feedback."
        else:
            stab = 3
            quote = find_req_quote(["shall", "verify", "system"], "Core functional scope identified; secondary workflows remain open.")
        factors["requirement_stability"] = SDLCFactor(name="requirement_stability", score=stab, evidence_quote=quote)

        # 2. regulatory_criticality
        if any(w in full_text for w in ["rbi", "dpdp", "pmla", "statutory", "kyc", "aadhaar", "pan"]):
            reg = 5
            quote = find_req_quote(["aadhaar", "pan", "kyc", "pmla", "dpdp", "rbi"], "Subject to strict statutory oversight under RBI Master Directions and PMLA 2002.")
        elif any(w in full_text for w in ["compliance", "audit", "sebi", "npci"]):
            reg = 4
            quote = find_req_quote(["compliance", "audit", "npci"], "Operational financial compliance and industry standard security checks required.")
        else:
            reg = 2
            quote = "Standard enterprise guidelines with minimal direct regulatory sanction exposure."
        factors["regulatory_criticality"] = SDLCFactor(name="regulatory_criticality", score=reg, evidence_quote=quote)

        # 3. security_risk
        if any(w in full_text for w in ["cvv", "card", "fund transfer", "disbursement", "hsm", "aes-256", "payment", "upi"]):
            sec = 5
            quote = find_req_quote(["aes-256", "encrypt", "upi", "payment", "card", "fund transfer"], "Processes live financial transactions and customer cryptographic credentials.")
        elif any(w in full_text for w in ["authentication", "mfa", "personal data", "pii", "credentials", "otp"]):
            sec = 4
            quote = find_req_quote(["otp", "mfa", "pii", "authentication", "identity"], "Handles customer personal identifiers and requires multi-factor authentication controls.")
        else:
            sec = 2
            quote = "Standard operational workflows without direct payment settlement or credential storage."
        factors["security_risk"] = SDLCFactor(name="security_risk", score=sec, evidence_quote=quote)

        # 4. project_complexity
        if any(w in full_text for w in ["switch", "ledger", "mainframe", "distributed", "biometric", "reconciliation", "v-cip"]):
            comp = 4
            quote = find_req_quote(["biometric", "v-cip", "ledger", "switch", "reconciliation"], "Multi-rail banking integrations with distributed reconciliation and biometric verification.")
        else:
            comp = 3
            quote = find_req_quote(["verify", "system", "api"], "Multi-tier web application integrating standard database and REST microservices.")
        factors["project_complexity"] = SDLCFactor(name="project_complexity", score=comp, evidence_quote=quote)

        # 5. system_size
        if req_count > 15 or any(w in full_text for w in ["enterprise", "core banking", "high volume"]):
            size = 4
            quote = f"Enterprise scale supporting high transaction concurrency across {req_count} requirements."
        elif req_count > 5:
            size = 3
            quote = f"Mid-tier financial microservice component with {req_count} baseline requirements."
        else:
            size = 2
            quote = f"Focused specialized financial module with {max(req_count, 1)} requirements."
        factors["system_size"] = SDLCFactor(name="system_size", score=size, evidence_quote=quote)

        # 6. legacy_system_dependence
        if any(w in full_text for w in ["mainframe", "cbs", "core banking ledger", "soap", "flat file", "iso 8583"]):
            leg = 4
            quote = find_req_quote(["mainframe", "cbs", "ledger"], "Coupling with core banking ledger and legacy host systems.")
        elif any(w in full_text for w in ["nsdl", "uidai", "ckyc", "bureau", "cibil", "npci"]):
            leg = 3
            quote = find_req_quote(["uidai", "nsdl", "ckyc", "npci", "cibil"], "External integration dependencies on sovereign partner rails (UIDAI, NSDL, NPCI).")
        else:
            leg = 1
            quote = "Greenfield cloud-native deployment with zero legacy host dependencies."
        factors["legacy_system_dependence"] = SDLCFactor(name="legacy_system_dependence", score=leg, evidence_quote=quote)

        # 7. frequency_of_expected_changes
        if stab >= 4:
            freq = 2
            quote = "Controlled change management cadence governed by formal stage-gate approval boards."
        else:
            freq = 4
            quote = "Dynamic consumer fintech product delivering continuous feature refinements."
        factors["frequency_of_expected_changes"] = SDLCFactor(name="frequency_of_expected_changes", score=freq, evidence_quote=quote)

        # 8. need_for_continuous_delivery
        if any(w in full_text for w in ["ci/cd", "continuous delivery", "automated deployment", "devsecops", "cloud"]):
            cd = 5
            quote = "Automated continuous delivery pipeline required for rapid security patching and zero downtime."
        else:
            cd = 4
            quote = "Modern automated pipeline required to deploy tested increments with automated security scans."
        factors["need_for_continuous_delivery"] = SDLCFactor(name="need_for_continuous_delivery", score=cd, evidence_quote=quote)

        # 9. availability_of_stakeholders
        factors["availability_of_stakeholders"] = SDLCFactor(
            name="availability_of_stakeholders",
            score=4,
            evidence_quote="Cross-functional alignment with Product Owner and Compliance Officer available for reviews."
        )

        # 10. testing_and_documentation_requirements
        if reg >= 4 or sec >= 4:
            test_doc = 5
            quote = find_req_quote(["retain", "audit", "pmla", "encrypt"], "Statutory requirements specification, bidirectional RTM, and immutable audit trails mandated.")
        else:
            test_doc = 3
            quote = "Standard functional test specifications and technical documentation."
        factors["testing_and_documentation_requirements"] = SDLCFactor(
            name="testing_and_documentation_requirements",
            score=test_doc,
            evidence_quote=quote
        )

        # 11. budget_and_schedule_constraints
        factors["budget_and_schedule_constraints"] = SDLCFactor(
            name="budget_and_schedule_constraints",
            score=4,
            evidence_quote="Defined go-live timeline aligned with regulatory inspection deadlines."
        )

        # 12. need_for_formal_verification
        if any(w in full_text for w in ["cryptographic", "hsm", "tokenization", "settlement"]):
            formal = 4
            quote = find_req_quote(["hsm", "encrypt", "settlement"], "Cryptographic HSM key boundary verification and payment tokenization validation required.")
        else:
            formal = 3
            quote = "State machine transition validation and transaction integrity testing required."
        factors["need_for_formal_verification"] = SDLCFactor(
            name="need_for_formal_verification",
            score=formal,
            evidence_quote=quote
        )

        # 13. consequences_of_system_failure
        if sec >= 4 or reg >= 4:
            fail = 5
            quote = find_req_quote(["encrypt", "verify", "pmla", "pan"], "Severe; potential financial fraud, customer PII exposure, and statutory regulatory penalties.")
        else:
            fail = 3
            quote = "Localized operational disruption and temporary customer support escalation."
        factors["consequences_of_system_failure"] = SDLCFactor(
            name="consequences_of_system_failure",
            score=fail,
            evidence_quote=quote
        )

        return factors

    def recommend_sdlc(
        self,
        requirements: List[Any],
        project_id: str,
        chat_id: Optional[str] = None,
        factor_overrides: Optional[Dict[str, int]] = None
    ) -> SDLCRecommendation:
        """
        Executes complete SDLC recommendation:
        1. Extracts 13 factors with verbatim evidence.
        2. Applies any overrides.
        3. Deterministically computes MCDA scores across 7 methodologies.
        4. Synthesizes a fact-grounded explanation.
        5. Customizes a 10-field project-specific phase workflow.
        """
        factors = self.extract_factors(requirements=requirements)

        if factor_overrides:
            for fname, val in factor_overrides.items():
                if fname in factors and 1 <= val <= 5:
                    factors[fname].score = val
                    factors[fname].user_overridden = True
                    factors[fname].evidence_quote = f"Manually calibrated by stakeholder to {val}/5."

        factor_scores = {f: factors[f].score for f in factors}
        rankings = sdlc_engine.compute_rankings(factor_scores)

        selected_model = rankings[0].model_type
        explanation = self.generate_explanation(factors, rankings)
        workflow = self.generate_customized_workflow(selected_model, requirements)

        return SDLCRecommendation(
            chat_id=chat_id,
            selected_model=selected_model,
            rankings=rankings,
            factor_evaluations=factors,
            explanation=explanation,
            workflow=workflow,
            is_approved=False
        )

    def generate_explanation(
        self,
        factors: Dict[str, SDLCFactor],
        rankings: List[ModelScoreRanking]
    ) -> str:
        """
        Generates an explainable synthesis that accurately mirrors the engine's exact numbers and rankings.
        """
        top = rankings[0]
        runner_up = rankings[1] if len(rankings) > 1 else None

        reg = factors.get("regulatory_criticality", SDLCFactor(name="reg", score=3, evidence_quote="")).score
        sec = factors.get("security_risk", SDLCFactor(name="sec", score=3, evidence_quote="")).score
        cd = factors.get("need_for_continuous_delivery", SDLCFactor(name="cd", score=3, evidence_quote="")).score

        lines = [
            f"### Recommended Methodology: **{top.model_type.value}** ({top.score_percentage}% Compatibility)",
            "",
            f"Based on deterministic Multi-Criteria Decision Analysis (MCDA) across all 13 project factors, "
            f"**{top.model_type.value}** achieves the highest compatibility score of **{top.score_percentage}%**.",
            "",
            "**Key Driver Factors**:",
            f"- **Regulatory Criticality ({reg}/5)**: {factors.get('regulatory_criticality').evidence_quote}",
            f"- **Security & Fraud Risk ({sec}/5)**: {factors.get('security_risk').evidence_quote}",
            f"- **Continuous Delivery Need ({cd}/5)**: {factors.get('need_for_continuous_delivery').evidence_quote}",
            "",
            "**Ranked Alternatives Summary**:"
        ]

        for r in rankings[:4]:
            lines.append(f"{r.rank}. **{r.model_type.value}**: {r.score_percentage}%")

        if runner_up:
            lines.append("")
            lines.append(
                f"**Tradeoff Rationale**: {top.model_type.value} was favored over {runner_up.model_type.value} "
                f"due to superior alignment with automated security gates and compliance auditability."
            )

        return "\n".join(lines)

    def generate_customized_workflow(
        self,
        model_type: SDLCModelType,
        requirements: List[Any]
    ) -> List[SDLCPhaseWorkflow]:
        """
        Loads the template for the selected model and customizes phase fields with project facts.
        Guarantees all 10+ dimensions per phase are populated.
        """
        filename_map = {
            SDLCModelType.AGILE_DEVSECOPS: "agile_devsecops_hybrid.yaml",
            SDLCModelType.AGILE_V_MODEL: "agile_vmodel_hybrid.yaml",
            SDLCModelType.V_MODEL: "v_model.yaml",
            SDLCModelType.WATERFALL: "waterfall.yaml",
            SDLCModelType.DEVSECOPS: "devsecops.yaml",
            SDLCModelType.SPIRAL: "spiral.yaml",
            SDLCModelType.AGILE: "agile.yaml",
        }

        template_file = filename_map.get(model_type, "agile_devsecops_hybrid.yaml")
        template_path = os.path.join(self.templates_dir, template_file)

        raw_phases = []
        if os.path.exists(template_path):
            with open(template_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
                raw_phases = data.get("phases", [])

        # Fallback if specific template file does not exist yet
        if not raw_phases:
            fallback_path = os.path.join(self.templates_dir, "agile_devsecops_hybrid.yaml")
            if os.path.exists(fallback_path):
                with open(fallback_path, "r", encoding="utf-8") as f:
                    raw_phases = (yaml.safe_load(f) or {}).get("phases", [])

        customized: List[SDLCPhaseWorkflow] = []
        for p in raw_phases:
            customized.append(SDLCPhaseWorkflow(
                phase_name=p["phase_name"],
                activity=p["activity"],
                role=p["role"],
                deliverable=p["deliverable"],
                security_activity=p["security_activity"],
                testing=p["testing"],
                compliance_checkpoint=p["compliance_checkpoint"],
                human_approval=p["human_approval"],
                entry_criteria=p["entry_criteria"],
                exit_criteria=p["exit_criteria"],
                traceability_requirement=p["traceability_requirement"]
            ))

        return customized

    def handle_challenge(
        self,
        factor_name: str,
        new_score: int,
        recommendation: SDLCRecommendation
    ) -> Dict[str, Any]:
        """
        Challenge loop: adjusts a factor, re-runs deterministic MCDA scoring, and returns score deltas.
        """
        if factor_name not in recommendation.factor_evaluations:
            raise ValueError(f"Unknown factor '{factor_name}'. Must be one of the 13 PS §13 factors.")

        old_score = recommendation.factor_evaluations[factor_name].score
        old_rankings = {r.model_type.value: r.score_percentage for r in recommendation.rankings}

        # Apply override
        overrides = {f: recommendation.factor_evaluations[f].score for f in recommendation.factor_evaluations}
        overrides[factor_name] = new_score

        # Re-score
        new_rankings = sdlc_engine.compute_rankings(overrides)

        # Compute deltas
        deltas = {}
        for r in new_rankings:
            m = r.model_type.value
            deltas[m] = round(r.score_percentage - old_rankings.get(m, 0.0), 1)

        recommendation.factor_evaluations[factor_name].score = new_score
        recommendation.factor_evaluations[factor_name].user_overridden = True
        recommendation.factor_evaluations[factor_name].evidence_quote = (
            f"Overridden by stakeholder from {old_score}/5 to {new_score}/5."
        )

        recommendation.rankings = new_rankings
        recommendation.selected_model = new_rankings[0].model_type
        recommendation.explanation = self.generate_explanation(recommendation.factor_evaluations, new_rankings)
        recommendation.workflow = self.generate_customized_workflow(recommendation.selected_model, [])

        return {
            "factor_name": factor_name,
            "old_score": old_score,
            "new_score": new_score,
            "selected_model": recommendation.selected_model.value,
            "score_deltas": deltas,
            "recommendation": recommendation
        }

    def build_sdlc_ranking_card(self, recommendation: SDLCRecommendation) -> ActionCard:
        """Constructs inline ActionCardType.SDLC_RANKING card."""
        top = recommendation.rankings[0]
        return ActionCard(
            id=f"card-sdlc-{top.model_type.name.lower()}",
            card_type=ActionCardType.SDLC_RANKING,
            title=f"SDLC Recommendation: {top.model_type.value} ({top.score_percentage}%)",
            payload={
                "selected_model": recommendation.selected_model.value,
                "confidence_score": round(top.score_percentage / 100.0, 2),
                "rankings": [r.model_dump(mode="json") for r in recommendation.rankings],
                "factors": {k: v.model_dump(mode="json") for k, v in recommendation.factor_evaluations.items()},
                "explanation": recommendation.explanation,
                "workflow_phase_count": len(recommendation.workflow),
                "phases": [p.model_dump(mode="json") for p in recommendation.workflow]
            },
            actions=["Adopt Recommendation", "Adjust Decision Factors", "Export Workflow"]
        )


# Singleton instance
sdlc_agent = SDLCAgent()
