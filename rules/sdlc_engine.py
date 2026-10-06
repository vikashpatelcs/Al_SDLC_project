"""
Deterministic SDLC Recommendation Engine (MCDA) per Problem Statement §13-§14 and Master Plan Phase 11.
Strict Rule: Pure mathematical calculation; no LLM computes or modifies scores.
Calculates weighted compatibility scores and normalized percentages across all 7 methodologies.
"""
import os
import yaml
from typing import Dict, List, Any, Optional

from backend.app.schemas.sdlc import SDLCModelType, ModelScoreRanking


class SDLCEngine:
    def __init__(self, config_path: Optional[str] = None):
        if not config_path:
            base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
            config_path = os.path.join(base_dir, "rules", "sdlc_rules.yaml")
        
        self.config_path = config_path
        self.rules = self._load_rules()
        self.model_profiles = self.rules.get("model_fit_profiles", {})
        self.factor_weights = self.rules.get("factor_weights", {})

    def _load_rules(self) -> Dict[str, Any]:
        if os.path.exists(self.config_path):
            with open(self.config_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        return {}

    def compute_rankings(self, factor_scores: Dict[str, int]) -> List[ModelScoreRanking]:
        """
        Computes deterministic multi-criteria compatibility scores for all 7 methodologies.
        Returns sorted List[ModelScoreRanking] (rank 1 to 7).
        """
        raw_scores: Dict[str, float] = {}
        strengths_map: Dict[str, List[str]] = {}
        tradeoffs_map: Dict[str, List[str]] = {}

        for model_name, ideal_profile in self.model_profiles.items():
            total_weight = 0.0
            weighted_similarity = 0.0
            model_strengths = []
            model_tradeoffs = []

            for factor, weight in self.factor_weights.items():
                actual_val = factor_scores.get(factor, 3)
                target_val = ideal_profile.get(factor, 3)

                # Distance on 1-5 scale (max difference is 4)
                diff = abs(target_val - actual_val)
                sim = 1.0 - (diff / 4.0)

                weighted_similarity += weight * sim
                total_weight += weight

                if diff == 0:
                    model_strengths.append(f"Ideal alignment on {factor.replace('_', ' ')} (score {actual_val}/5)")
                elif diff >= 3:
                    model_tradeoffs.append(f"Significant divergence on {factor.replace('_', ' ')} (target {target_val} vs actual {actual_val})")

            base_score = (weighted_similarity / total_weight) if total_weight > 0 else 0.5

            # Apply domain-specific financial hard rules / adjustments
            adjusted_score = base_score

            reg_crit = factor_scores.get("regulatory_criticality", 3)
            sec_risk = factor_scores.get("security_risk", 3)
            req_stab = factor_scores.get("requirement_stability", 3)
            freq_chg = factor_scores.get("frequency_of_expected_changes", 3)
            cont_del = factor_scores.get("need_for_continuous_delivery", 3)
            leg_dep = factor_scores.get("legacy_system_dependence", 3)

            # Rule 1: High regulatory criticality and high security risk penalize pure Agile
            if model_name == "Agile" and reg_crit >= 4 and sec_risk >= 4:
                adjusted_score -= 0.18
                model_tradeoffs.append("Pure Agile lacks mandatory stage-gate regulatory compliance controls.")

            # Rule 2: Highly volatile requirements with frequent changes strongly penalize pure Waterfall
            if model_name == "Waterfall" and req_stab <= 2 and freq_chg >= 4:
                adjusted_score -= 0.25
                model_tradeoffs.append("Waterfall cannot accommodate rapid scope changes without severe rework.")

            # Rule 3: Heavy legacy dependence and high failure consequences favor V-Model
            if model_name == "V-Model" and leg_dep >= 4 and req_stab >= 4:
                adjusted_score += 0.08
                model_strengths.append("V-Model provides rigorous verification required for legacy core banking.")

            # Rule 4: High continuous delivery combined with critical security favors DevSecOps hybrids
            if model_name == "Agile + DevSecOps Hybrid" and cont_del >= 4 and sec_risk >= 4:
                adjusted_score += 0.08
                model_strengths.append("Automated security gates support both rapid delivery and statutory auditability.")

            raw_scores[model_name] = max(0.05, min(1.0, adjusted_score))
            strengths_map[model_name] = model_strengths[:3]
            tradeoffs_map[model_name] = model_tradeoffs[:3]

        # Normalization: Map top raw score to ~88-92% and scale proportionally
        max_raw = max(raw_scores.values()) if raw_scores else 1.0
        normalized_percentages: Dict[str, float] = {}

        for m, s in raw_scores.items():
            pct = round((s / max_raw) * 88.0, 1) if max_raw > 0 else 50.0
            # Ensure within [10.0, 95.0]
            normalized_percentages[m] = max(10.0, min(95.0, pct))

        # Sort models descending by score, deterministic tie-breaker by model name
        sorted_models = sorted(
            normalized_percentages.keys(),
            key=lambda m: (-normalized_percentages[m], m)
        )

        rankings: List[ModelScoreRanking] = []
        for rank_idx, m_name in enumerate(sorted_models, start=1):
            rankings.append(ModelScoreRanking(
                model_type=SDLCModelType(m_name),
                score_percentage=normalized_percentages[m_name],
                rank=rank_idx,
                key_strengths=strengths_map.get(m_name, []),
                tradeoffs=tradeoffs_map.get(m_name, [])
            ))

        return rankings


# Singleton engine instance
sdlc_engine = SDLCEngine()
