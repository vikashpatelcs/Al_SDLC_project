"""
Scenario-level dataset splitter for Phase 4.
Splits examples by scenario_id with zero leakage.
Routes held-out subdomains (insurance, regulatory_reporting) strictly to test.jsonl.
"""
import json
import os
import random
from collections import defaultdict
from typing import Dict, List, Any, Set

HELD_OUT_SUBDOMAINS = {"insurance", "regulatory_reporting"}


def split_dataset(
    input_file: str,
    output_dir: str,
    train_ratio: float = 0.80,
    val_ratio: float = 0.10,
    random_seed: int = 42
) -> Dict[str, Any]:
    print(f"Reading dataset from {input_file} ...")
    
    # Group examples by scenario_id
    scenario_to_examples: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    scenario_to_subdomain: Dict[str, str] = {}

    with open(input_file, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            ex = json.loads(line)
            sc_id = ex["scenario_id"]
            scenario_to_examples[sc_id].append(ex)
            scenario_to_subdomain[sc_id] = ex["subdomain"]

    total_scenarios = len(scenario_to_examples)
    total_examples = sum(len(exs) for exs in scenario_to_examples.values())
    print(f"Total scenarios: {total_scenarios}, Total examples: {total_examples}")

    held_out_scenarios: List[str] = []
    standard_scenarios: List[str] = []

    for sc_id, sub in scenario_to_subdomain.items():
        if sub in HELD_OUT_SUBDOMAINS:
            held_out_scenarios.append(sc_id)
        else:
            standard_scenarios.append(sc_id)

    # Deterministic shuffle of standard scenarios
    rng = random.Random(random_seed)
    rng.shuffle(standard_scenarios)

    n_std = len(standard_scenarios)
    n_train = int(n_std * train_ratio)
    n_val = int(n_std * val_ratio)
    # Remaining standard scenarios go to test along with all held-out scenarios
    train_scenarios = set(standard_scenarios[:n_train])
    val_scenarios = set(standard_scenarios[n_train:n_train + n_val])
    test_scenarios = set(standard_scenarios[n_train + n_val:] + held_out_scenarios)

    # Verification of zero scenario overlap
    assert len(train_scenarios.intersection(val_scenarios)) == 0, "Scenario leak: train and val overlap"
    assert len(train_scenarios.intersection(test_scenarios)) == 0, "Scenario leak: train and test overlap"
    assert len(val_scenarios.intersection(test_scenarios)) == 0, "Scenario leak: val and test overlap"

    # Verify held-out subdomains are strictly in test
    for sc_id in train_scenarios:
        assert scenario_to_subdomain[sc_id] not in HELD_OUT_SUBDOMAINS, f"Held-out domain leaked into train: {sc_id}"
    for sc_id in val_scenarios:
        assert scenario_to_subdomain[sc_id] not in HELD_OUT_SUBDOMAINS, f"Held-out domain leaked into val: {sc_id}"

    splits = {
        "train": [ex for sc in train_scenarios for ex in scenario_to_examples[sc]],
        "val": [ex for sc in val_scenarios for ex in scenario_to_examples[sc]],
        "test": [ex for sc in test_scenarios for ex in scenario_to_examples[sc]],
    }

    os.makedirs(output_dir, exist_ok=True)
    summary = {}

    for split_name, examples in splits.items():
        out_path = os.path.join(output_dir, f"{split_name}.jsonl")
        with open(out_path, "w", encoding="utf-8") as f:
            for ex in examples:
                f.write(json.dumps(ex) + "\n")
        
        split_scenarios = set(ex["scenario_id"] for ex in examples)
        split_subdomains = set(ex["subdomain"] for ex in examples)
        summary[split_name] = {
            "count": len(examples),
            "scenarios": len(split_scenarios),
            "subdomains": sorted(list(split_subdomains)),
        }
        print(f"Split '{split_name}': {len(examples)} examples across {len(split_scenarios)} scenarios ({len(split_subdomains)} subdomains).")

    print("Scenario-level split complete with 0 leakage.")
    return summary


if __name__ == "__main__":
    base_dir = os.path.dirname(__file__)
    inp = os.path.join(base_dir, "data", "deduped.jsonl")
    out = os.path.join(base_dir, "data")
    split_dataset(inp, out)
