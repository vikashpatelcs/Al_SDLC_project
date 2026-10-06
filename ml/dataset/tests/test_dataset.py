"""
Unit and integration tests for Phase 4 Dataset (FRE-Bench).
Validates dataset size, deduplication, JSON validity, zero PII, zero leakage, and held-out domain isolation.
"""
import json
import os
import sys
import pytest
from typing import Set, Dict, List

# Ensure project root in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data"))
DEDUPED_PATH = os.path.join(DATA_DIR, "deduped.jsonl")
TRAIN_PATH = os.path.join(DATA_DIR, "train.jsonl")
VAL_PATH = os.path.join(DATA_DIR, "val.jsonl")
TEST_PATH = os.path.join(DATA_DIR, "test.jsonl")


def load_jsonl(path: str) -> List[Dict]:
    assert os.path.exists(path), f"File not found: {path}"
    records = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))
    return records


def test_dataset_size_and_structure():
    """Verify dataset meets the >= 1,500 scale requirement and has correct chat structure."""
    records = load_jsonl(DEDUPED_PATH)
    assert len(records) >= 1500, f"Expected at least 1500 examples, got {len(records)}"

    for idx, ex in enumerate(records):
        assert "task" in ex, f"Record {idx} missing 'task'"
        assert "scenario_id" in ex, f"Record {idx} missing 'scenario_id'"
        assert "subdomain" in ex, f"Record {idx} missing 'subdomain'"
        assert "messages" in ex, f"Record {idx} missing 'messages'"
        msgs = ex["messages"]
        assert len(msgs) >= 3, f"Record {idx} has < 3 message turns"
        assert msgs[0]["role"] == "system"
        assert msgs[1]["role"] == "user"
        assert msgs[2]["role"] == "assistant"
        assert msgs[2]["content"].strip() != ""


def test_task_coverage_t1_to_t14():
    """Verify all 14 canonical requirements engineering tasks are represented."""
    records = load_jsonl(DEDUPED_PATH)
    tasks = set(ex["task"] for ex in records)
    expected_prefixes = [
        "T1_question_generation",
        "T2_clarification_followup",
        "T3_requirement_extraction",
        "T4_classification",
        "T5_ambiguity_detection",
        "T6_incompleteness_detection",
        "T7_conflict_detection",
        "T8_duplicate_detection",
        "T9_requirement_improvement",
        "T10_user_story_ac",
        "T11_use_case",
        "T12_srs_section",
        "T13_sdlc_factor_extraction",
        "T14_sdlc_explanation",
    ]
    for prefix in expected_prefixes:
        assert any(t.startswith(prefix) for t in tasks), f"Missing task prefix: {prefix}"


def test_structured_tasks_json_validity():
    """Verify 100% parseable JSON for all structured assistant outputs."""
    records = load_jsonl(DEDUPED_PATH)
    structured_prefixes = [
        "T1_", "T2_", "T3_", "T4_", "T5_", "T6_", "T7_", "T8_", "T9_", "T10_", "T11_", "T13_"
    ]
    for idx, ex in enumerate(records):
        task = ex["task"]
        if any(task.startswith(p) for p in structured_prefixes):
            asst_text = ex["messages"][2]["content"]
            try:
                parsed = json.loads(asst_text)
                assert parsed is not None
            except json.JSONDecodeError as e:
                pytest.fail(f"Record {idx} (Task {task}) assistant content is not valid JSON: {e}")


def test_zero_raw_pii_leakage():
    """Verify zero unmasked Aadhaar or payment card numbers in all records."""
    from backend.app.core.security.masking import pii_masker

    records = load_jsonl(DEDUPED_PATH)
    for idx, ex in enumerate(records):
        full_text = " ".join([m["content"] for m in ex["messages"]])
        assert not pii_masker.AADHAAR_REGEX.search(full_text), f"Record {idx} leaked unmasked Aadhaar number"
        assert not pii_masker.CARD_REGEX.search(full_text), f"Record {idx} leaked unmasked Card number"


def test_zero_scenario_leakage_across_splits():
    """Verify strict zero scenario leakage across train, val, and test splits."""
    train_recs = load_jsonl(TRAIN_PATH)
    val_recs = load_jsonl(VAL_PATH)
    test_recs = load_jsonl(TEST_PATH)

    train_scenarios = set(ex["scenario_id"] for ex in train_recs)
    val_scenarios = set(ex["scenario_id"] for ex in val_recs)
    test_scenarios = set(ex["scenario_id"] for ex in test_recs)

    assert len(train_scenarios) > 0
    assert len(val_scenarios) > 0
    assert len(test_scenarios) > 0

    assert train_scenarios.intersection(val_scenarios) == set(), "Leak: train and val share scenarios"
    assert train_scenarios.intersection(test_scenarios) == set(), "Leak: train and test share scenarios"
    assert val_scenarios.intersection(test_scenarios) == set(), "Leak: val and test share scenarios"

    # Total sum of examples matches deduped file
    total_split_examples = len(train_recs) + len(val_recs) + len(test_recs)
    deduped_recs = load_jsonl(DEDUPED_PATH)
    assert total_split_examples == len(deduped_recs), f"Count mismatch: splits total {total_split_examples} != {len(deduped_recs)}"


def test_held_out_subdomains_isolated_to_test():
    """Verify held-out subdomains (insurance, regulatory_reporting) are absent from train/val and present in test."""
    train_recs = load_jsonl(TRAIN_PATH)
    val_recs = load_jsonl(VAL_PATH)
    test_recs = load_jsonl(TEST_PATH)

    train_subdomains = set(ex["subdomain"] for ex in train_recs)
    val_subdomains = set(ex["subdomain"] for ex in val_recs)
    test_subdomains = set(ex["subdomain"] for ex in test_recs)

    held_out = {"insurance", "regulatory_reporting"}

    for h in held_out:
        assert h not in train_subdomains, f"Held-out domain '{h}' leaked into train.jsonl"
        assert h not in val_subdomains, f"Held-out domain '{h}' leaked into val.jsonl"
        assert h in test_subdomains, f"Held-out domain '{h}' missing from test.jsonl"
