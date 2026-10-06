"""
Unit and Integration Tests for Phase 15: Evaluation Harness & Benchmark Metrics.
Validates metric mathematical calculations, toy data edge cases, gold case schema integrity,
expert SDLC labels, and benchmark report generation per Master Plan §A14.
"""
import os
import json
import glob
import pytest

from ml.eval.metrics import (
    calculate_prf1,
    calculate_seeded_defect_metrics,
    calculate_control_coverage,
    calculate_citation_metrics,
    calculate_sdlc_agreement,
    calculate_traceability_coverage,
    calculate_summary_statistics,
    calculate_time_saved,
    token_overlap_similarity
)
from ml.eval.report import generate_markdown_report


CASES_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../ml/eval/cases"))
GOLD_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../ml/eval/gold"))
RESULTS_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../ml/eval/evaluation_results.json"))
REPORT_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../docs/EVALUATION_REPORT.md"))


def test_token_overlap_similarity():
    """Verify Jaccard token overlap similarity."""
    assert token_overlap_similarity("verify aadhaar identity", "verify aadhaar identity") == 1.0
    assert token_overlap_similarity("verify aadhaar identity", "completely different string") == 0.0
    assert token_overlap_similarity("", "") == 1.0
    assert token_overlap_similarity("verify aadhaar", "") == 0.0

    # Partial overlap
    sim = token_overlap_similarity("verify customer aadhaar identity", "verify customer pan card")
    assert 0.0 < sim < 1.0


def test_prf1_metrics_toy_data():
    """Tests P/R/F1 on toy edge cases: perfect match, disjoint, and empty."""
    # Perfect match
    res_perf = calculate_prf1(
        ["The system shall verify identity.", "The system shall encrypt data."],
        ["The system shall verify identity.", "The system shall encrypt data."]
    )
    assert res_perf["precision"] == 1.0
    assert res_perf["recall"] == 1.0
    assert res_perf["f1"] == 1.0

    # Completely disjoint
    res_disjoint = calculate_prf1(
        ["The system shall process payments."],
        ["The system shall verify loan eligibility."]
    )
    assert res_disjoint["precision"] == 0.0
    assert res_disjoint["recall"] == 0.0
    assert res_disjoint["f1"] == 0.0

    # Empty sets
    res_empty = calculate_prf1([], [])
    assert res_empty["precision"] == 1.0
    assert res_empty["recall"] == 1.0
    assert res_empty["f1"] == 1.0

    res_half_empty = calculate_prf1(["Some requirement."], [])
    assert res_half_empty["precision"] == 0.0
    assert res_half_empty["recall"] == 0.0


def test_seeded_defect_metrics():
    """Tests ambiguity and conflict detection recall against ground-truth seeded defect list."""
    seeded = [
        {"type": "ambiguity", "text": "respond instantly without delay"},
        {"type": "conflict", "text": "store raw cvv vs mask cvv"}
    ]
    detected = [
        {"detail": "Flagged non-measurable weak word: respond instantly without delay", "suggestion": "Specify <= 500ms SLA", "issue_type": "ambiguity"},
        {"detail": "Conflict between store raw cvv and statutory masking rules", "suggestion": "Do not store CVV", "issue_type": "conflict"}
    ]
    metrics = calculate_seeded_defect_metrics(detected, seeded)
    assert metrics["recall"] == 1.0
    assert metrics["precision"] == 1.0
    assert metrics["f1"] == 1.0
    assert metrics["detected"] == 2

    # Partial detection
    metrics_partial = calculate_seeded_defect_metrics([detected[0]], seeded)
    assert metrics_partial["recall"] == 0.5
    assert metrics_partial["detected"] == 1


def test_control_coverage_and_citation_metrics():
    """Tests statutory control coverage, citation precision, and hallucination rate calculation."""
    gold_controls = ["CMP-KYC-001", "CMP-PII-CONSENT-002", "SEC-CRYPTO-003"]
    extracted_controls = ["CMP-KYC-001", "CMP-PII-CONSENT-002"]

    cov = calculate_control_coverage(extracted_controls, gold_controls)
    assert cov == round(2 / 3, 4)

    # Citation metrics
    citations = [
        {"id": "RBI-MD-KYC-S16", "citation_verified": True},
        {"id": "PMLA-S12", "citation_verified": True},
        {"id": "FABRICATED-REG-99", "citation_verified": False}
    ]
    cit_metrics = calculate_citation_metrics(citations, ["RBI-MD-KYC-S16", "PMLA-S12"], total_claims=10)
    assert cit_metrics["citation_correctness"] == round(2 / 3, 4)
    # 1 unsupported out of 10 claims = 10%
    assert cit_metrics["hallucination_rate"] == 10.0


def test_sdlc_agreement_metrics():
    """Tests Top-1 and Top-2 concordance against expert panel votes."""
    expert_labels = {
        "consensus_top": "Agile + DevSecOps Hybrid",
        "consensus_second": "V-Model",
        "expert_votes": {
            "EXP-01": {"top": "Agile + DevSecOps Hybrid", "second": "V-Model"},
            "EXP-02": {"top": "Agile + DevSecOps Hybrid", "second": "DevSecOps"},
            "EXP-03": {"top": "V-Model", "second": "Agile + DevSecOps Hybrid"}
        }
    }
    agree = calculate_sdlc_agreement("Agile + DevSecOps Hybrid", "V-Model", expert_labels)
    # EXP-01 and EXP-02 top match -> 2/3 top-1 agreement
    assert agree["top1_agreement"] == round(2 / 3, 4)
    # EXP-01 top match, EXP-02 top match, EXP-03 second match -> 3/3 top-2 agreement
    assert agree["top2_agreement"] == 1.0


def test_summary_statistics_calculation():
    """Tests sample mean, standard deviation, and bootstrap intervals."""
    values = [10.0, 12.0, 14.0]
    stats = calculate_summary_statistics(values, bootstrap_samples=500, random_seed=42)
    assert stats["mean"] == 12.0
    assert stats["sd"] == 2.0  # sqrt(((10-12)^2 + 0 + (14-12)^2) / 2) = sqrt(8/2) = 2.0
    assert 10.0 <= stats["ci_lower"] <= 12.0
    assert 12.0 <= stats["ci_upper"] <= 14.0


def test_time_saved_calculation():
    """Tests person-hours and percentage reduction."""
    res = calculate_time_saved(manual_hours=40.0, system_hours=2.0)
    assert res["hours_saved"] == 38.0
    assert res["percentage_saved"] == 95.0


def test_all_6_gold_cases_schema_validity():
    """Validates that all 6 case files in ml/eval/cases have required attributes."""
    case_files = sorted(glob.glob(os.path.join(CASES_DIR, "*.json")))
    assert len(case_files) == 6, f"Expected exactly 6 gold cases, found {len(case_files)}"

    required_keys = [
        "case_id", "domain", "title", "narrative",
        "seeded_defects", "gold_requirements", "gold_controls",
        "gold_sdlc_factors", "expert_sdlc_labels"
    ]

    for cf in case_files:
        with open(cf, "r", encoding="utf-8") as f:
            data = json.load(f)

        for k in required_keys:
            assert k in data, f"Key '{k}' missing from {os.path.basename(cf)}"

        assert len(data["seeded_defects"]) >= 1
        assert len(data["gold_requirements"]) >= 3
        assert len(data["gold_controls"]) >= 3
        assert len(data["gold_sdlc_factors"]) == 13
        assert len(data["expert_sdlc_labels"]) >= 3


def test_expert_sdlc_labels_file_integrity():
    """Verifies that ml/eval/gold/expert_sdlc_labels.json indexes all 6 cases and 3 experts."""
    expert_file = os.path.join(GOLD_DIR, "expert_sdlc_labels.json")
    assert os.path.exists(expert_file)

    with open(expert_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert "experts" in data
    assert len(data["experts"]) == 3
    assert "cases" in data
    assert len(data["cases"]) == 6


def test_evaluation_results_and_report_files():
    """Verifies that evaluation_results.json and EVALUATION_REPORT.md are generated and complete."""
    assert os.path.exists(RESULTS_FILE), "evaluation_results.json not found"

    with open(RESULTS_FILE, "r", encoding="utf-8") as f:
        res = json.load(f)

    assert res["cases_evaluated"] == 6
    assert len(res["seeds"]) == 3
    assert "S0_Manual" in res["summary"]
    assert "S4_FullAgentic" in res["summary"]

    # Generate or verify report
    report_text = generate_markdown_report()
    assert os.path.exists(REPORT_FILE)
    assert "# Empirical Evaluation & Ablation Benchmark Report" in report_text
    assert "S0 (Manual BA)" in report_text
    assert "S4 (Full Multi-Agent)" in report_text
    assert "Ablation Study Insights" in report_text
    assert "Honest Error Analysis" in report_text
