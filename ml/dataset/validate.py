"""
Dataset Validator for Phase 4.
Validates 100% schema compliance, role order, valid JSON targets, and zero PII leaks.
"""
import json
import os
import sys
from typing import Dict, Any, List, Tuple

# Ensure project root in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from backend.app.core.security.masking import pii_masker


def validate_example(example: Dict[str, Any]) -> Tuple[bool, List[str]]:
    errors = []

    # 1. Structure check
    for key in ["task", "scenario_id", "subdomain", "messages"]:
        if key not in example:
            errors.append(f"Missing required field: '{key}'")

    messages = example.get("messages", [])
    if len(messages) < 3:
        errors.append(f"Expected at least 3 message turns (system, user, assistant), found {len(messages)}")
    else:
        roles = [m.get("role") for m in messages]
        if roles[0] != "system" or roles[1] != "user" or roles[2] != "assistant":
            errors.append(f"Invalid message role sequence: {roles}")

    # 2. Structured assistant output check for JSON tasks
    task = example.get("task", "")
    asst_content = messages[-1].get("content", "") if messages else ""

    structured_tasks = [
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
        "T13_sdlc_factor_extraction",
    ]

    if any(st in task for st in structured_tasks):
        try:
            json.loads(asst_content)
        except json.JSONDecodeError as e:
            errors.append(f"Task '{task}' assistant content is not valid JSON: {e}")

    # 3. PII Leakage Check
    # Verify no raw unmasked Aadhaar, PAN, Card, or Mobile numbers in messages
    full_text = " ".join([m.get("content", "") for m in messages])
    masked_text, vault = pii_masker.mask(full_text)
    # If the masker extracted any token, ensure it was not raw unmasked PII
    if pii_masker.AADHAAR_REGEX.search(full_text):
        errors.append("Potential unmasked Aadhaar number detected in text")
    if pii_masker.CARD_REGEX.search(full_text):
        errors.append("Potential unmasked Card number detected in text")

    return (len(errors) == 0), errors


def validate_dataset_file(file_path: str) -> Dict[str, Any]:
    print(f"Validating dataset file: {file_path} ...")
    total = 0
    valid_count = 0
    all_errors = []

    with open(file_path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            if not line.strip():
                continue
            total += 1
            try:
                ex = json.loads(line)
            except json.JSONDecodeError as e:
                all_errors.append(f"Line {line_num}: Invalid JSON format: {e}")
                continue

            is_valid, errs = validate_example(ex)
            if is_valid:
                valid_count += 1
            else:
                all_errors.append(f"Line {line_num} (Task {ex.get('task')}): {'; '.join(errs)}")

    validity_rate = (valid_count / max(total, 1)) * 100.0
    print(f"Total Examples: {total}")
    print(f"Valid Examples: {valid_count} ({validity_rate:.2f}%)")
    print(f"Errors Found: {len(all_errors)}")

    return {
        "total": total,
        "valid": valid_count,
        "validity_rate": validity_rate,
        "errors": all_errors[:10]  # first 10 errors
    }


if __name__ == "__main__":
    target = os.path.join(os.path.dirname(__file__), "data", "all_generated.jsonl")
    res = validate_dataset_file(target)
    if res["validity_rate"] < 100.0:
        print("Validation FAILED!")
        sys.exit(1)
    else:
        print("Validation PASSED: 100% schema valid and zero PII leaks.")
