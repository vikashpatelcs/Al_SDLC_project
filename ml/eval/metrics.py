"""
Mathematical Evaluation Metrics Engine for Phase 15 per Master Plan §A14.
Implements P/R/F1, seeded defect recall, statutory control coverage,
citation correctness, hallucination rate, SDLC expert agreement, and bootstrap statistics.
"""
import math
import random
from typing import List, Dict, Any, Tuple, Optional


def tokenize(text: str) -> set:
    """Normalize and tokenize text into lowercase word tokens."""
    cleaned = "".join(c.lower() if c.isalnum() else " " for c in text)
    return set(cleaned.split())


def token_overlap_similarity(s1: str, s2: str) -> float:
    """Calculates Jaccard token overlap between two requirement strings."""
    t1 = tokenize(s1)
    t2 = tokenize(s2)
    if not t1 and not t2:
        return 1.0
    if not t1 or not t2:
        return 0.0
    intersection = len(t1.intersection(t2))
    union = len(t1.union(t2))
    return intersection / union if union > 0 else 0.0


def calculate_prf1(
    predicted_statements: List[str],
    gold_statements: List[str],
    similarity_threshold: float = 0.5
) -> Dict[str, float]:
    """
    Computes Precision, Recall, and F1 score for requirement statements
    using token-overlap semantic alignment.
    """
    if not predicted_statements and not gold_statements:
        return {"precision": 1.0, "recall": 1.0, "f1": 1.0}
    if not predicted_statements or not gold_statements:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0}

    matched_gold = set()
    matched_pred = set()

    for p_idx, pred in enumerate(predicted_statements):
        best_sim = 0.0
        best_g_idx = -1
        for g_idx, gold in enumerate(gold_statements):
            if g_idx in matched_gold:
                continue
            sim = token_overlap_similarity(pred, gold)
            if sim > best_sim:
                best_sim = sim
                best_g_idx = g_idx

        if best_sim >= similarity_threshold and best_g_idx != -1:
            matched_gold.add(best_g_idx)
            matched_pred.add(p_idx)

    tp = len(matched_pred)
    precision = tp / len(predicted_statements) if predicted_statements else 0.0
    recall = tp / len(gold_statements) if gold_statements else 0.0
    f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4)
    }


def calculate_seeded_defect_metrics(
    detected_issues: List[Dict[str, Any]],
    seeded_defects: List[Dict[str, Any]]
) -> Dict[str, float]:
    """
    Calculates ambiguity, conflict, and defect recall against seeded ground truths.
    """
    if not seeded_defects:
        return {"recall": 1.0, "precision": 1.0, "f1": 1.0}

    detected_texts = [
        (i.get("detail", "") + " " + i.get("suggestion", "") + " " + i.get("issue_type", "")).lower()
        for i in detected_issues
    ]

    detected_count = 0
    for defect in seeded_defects:
        target_snippet = defect.get("text", "").lower()
        defect_type = defect.get("type", "").lower()

        # Check if any detected issue matches the defect text or type
        is_found = any(
            (target_snippet in dt or defect_type in dt or any(w in dt for w in target_snippet.split() if len(w) > 4))
            for dt in detected_texts
        )
        if is_found:
            detected_count += 1

    recall = detected_count / len(seeded_defects)
    precision = detected_count / len(detected_issues) if detected_issues else 0.0
    f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

    return {
        "recall": round(recall, 4),
        "precision": round(precision, 4),
        "f1": round(f1, 4),
        "detected": detected_count,
        "total_seeded": len(seeded_defects)
    }


def calculate_control_coverage(
    extracted_controls: List[str],
    gold_controls: List[str]
) -> float:
    """Calculates ratio of gold statutory controls covered."""
    if not gold_controls:
        return 1.0
    if not extracted_controls:
        return 0.0

    ext_normalized = {c.strip().upper() for c in extracted_controls if c}
    gold_normalized = {c.strip().upper() for c in gold_controls if c}

    # Match by exact ID or partial token match
    covered = 0
    for gc in gold_normalized:
        if gc in ext_normalized or any(gc in ec or ec in gc for ec in ext_normalized):
            covered += 1

    coverage = covered / len(gold_normalized)
    return round(coverage, 4)


def calculate_citation_metrics(
    citations: List[Dict[str, Any]],
    verified_citations: List[str],
    total_claims: int
) -> Dict[str, float]:
    """
    Computes citation correctness (% supported) and hallucination rate per 100 claims.
    """
    if not citations:
        correctness = 1.0
        hallucination_rate = 0.0
    else:
        verified_set = {v.strip().upper() for v in verified_citations}
        supported_count = sum(
            1 for c in citations
            if c.get("citation_verified", False) or c.get("id", "").strip().upper() in verified_set
        )
        correctness = supported_count / len(citations)
        unsupported = len(citations) - supported_count
        hallucination_rate = (unsupported / max(total_claims, 1)) * 100.0

    return {
        "citation_correctness": round(correctness, 4),
        "hallucination_rate": round(hallucination_rate, 2)
    }


def calculate_sdlc_agreement(
    predicted_top_model: str,
    predicted_second_model: Optional[str],
    expert_labels: Dict[str, Any]
) -> Dict[str, float]:
    """
    Computes Top-1 and Top-2 agreement against >= 3 expert votes and consensus.
    """
    consensus_top = expert_labels.get("consensus_top", "")
    consensus_second = expert_labels.get("consensus_second", "")
    expert_votes = expert_labels.get("expert_votes", {})

    top1_matches = 0
    top2_matches = 0
    total_experts = len(expert_votes) if expert_votes else 3

    if expert_votes:
        for exp_id, vote in expert_votes.items():
            exp_top = vote.get("top", "")
            exp_sec = vote.get("second", "")

            if predicted_top_model.lower() == exp_top.lower():
                top1_matches += 1
                top2_matches += 1
            elif (
                predicted_top_model.lower() == exp_sec.lower() or
                (predicted_second_model and predicted_second_model.lower() == exp_top.lower())
            ):
                top2_matches += 1
    else:
        # Fallback to consensus comparison
        if predicted_top_model.lower() == consensus_top.lower():
            top1_matches = 3
            top2_matches = 3
        elif (
            predicted_top_model.lower() == consensus_second.lower() or
            (predicted_second_model and predicted_second_model.lower() == consensus_top.lower())
        ):
            top2_matches = 3

    top1_agree = top1_matches / total_experts if total_experts > 0 else 0.0
    top2_agree = top2_matches / total_experts if total_experts > 0 else 0.0

    return {
        "top1_agreement": round(top1_agree, 4),
        "top2_agreement": round(top2_agree, 4)
    }


def calculate_traceability_coverage(
    rtm_rows: List[Dict[str, Any]],
    requirements: List[Dict[str, Any]]
) -> float:
    """Calculates percentage of requirements with complete bi-directional links."""
    if not requirements:
        return 1.0
    if not rtm_rows:
        return 0.0

    covered_ids = {
        r.get("requirement_id")
        for r in rtm_rows
        if r.get("source_statement_id") and r.get("acceptance_criteria_id")
    }
    req_ids = {r.get("id") for r in requirements if r.get("id")}
    intersection = covered_ids.intersection(req_ids)
    coverage = len(intersection) / len(req_ids) if req_ids else 1.0
    return round(coverage, 4)


def calculate_summary_statistics(
    values: List[float],
    bootstrap_samples: int = 1000,
    random_seed: int = 42
) -> Dict[str, float]:
    """
    Computes sample mean, sample standard deviation, and paired bootstrap 95% CI.
    """
    if not values:
        return {"mean": 0.0, "sd": 0.0, "ci_lower": 0.0, "ci_upper": 0.0}

    n = len(values)
    mean_val = sum(values) / n

    if n > 1:
        variance = sum((x - mean_val) ** 2 for x in values) / (n - 1)
        sd_val = math.sqrt(variance)
    else:
        sd_val = 0.0

    # Bootstrap 95% Confidence Interval
    rng = random.Random(random_seed)
    bootstrap_means = []
    for _ in range(bootstrap_samples):
        sample = [rng.choice(values) for _ in range(n)]
        bootstrap_means.append(sum(sample) / n)

    bootstrap_means.sort()
    low_idx = int(0.025 * bootstrap_samples)
    high_idx = int(0.975 * bootstrap_samples)
    ci_lower = bootstrap_means[low_idx]
    ci_upper = bootstrap_means[high_idx]

    return {
        "mean": round(mean_val, 4),
        "sd": round(sd_val, 4),
        "ci_lower": round(ci_lower, 4),
        "ci_upper": round(ci_upper, 4)
    }


def calculate_time_saved(
    manual_hours: float,
    system_hours: float
) -> Dict[str, float]:
    """Calculates time reduction in engineering person-hours and percentage."""
    saved_hours = max(0.0, manual_hours - system_hours)
    percent_saved = (saved_hours / manual_hours * 100.0) if manual_hours > 0 else 0.0
    return {
        "manual_hours": round(manual_hours, 2),
        "system_hours": round(system_hours, 2),
        "hours_saved": round(saved_hours, 2),
        "percentage_saved": round(percent_saved, 2)
    }
