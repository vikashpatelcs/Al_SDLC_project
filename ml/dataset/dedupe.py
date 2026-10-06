"""
Deduplication utility for Phase 4 dataset.
Removes exact and near duplicate examples based on SHA-256 normalized content hash.
"""
import hashlib
import json
import os
import sys
from typing import Dict, Any, List


def compute_example_hash(example: Dict[str, Any]) -> str:
    messages = example.get("messages", [])
    text_parts = [m.get("role", "") + ":" + m.get("content", "").strip() for m in messages]
    normalized = "\n".join(text_parts).lower()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def deduplicate_dataset(input_file: str, output_file: str) -> int:
    print(f"Deduplicating {input_file} ...")
    seen_hashes = set()
    unique_examples = []
    duplicate_count = 0

    with open(input_file, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            ex = json.loads(line)
            h = compute_example_hash(ex)
            if h in seen_hashes:
                duplicate_count += 1
            else:
                seen_hashes.add(h)
                unique_examples.append(ex)

    with open(output_file, "w", encoding="utf-8") as f:
        for ex in unique_examples:
            f.write(json.dumps(ex) + "\n")

    print(f"Original: {len(unique_examples) + duplicate_count}, Deduplicated: {len(unique_examples)}, Removed: {duplicate_count}")
    return len(unique_examples)


if __name__ == "__main__":
    inp = os.path.join(os.path.dirname(__file__), "data", "all_generated.jsonl")
    out = os.path.join(os.path.dirname(__file__), "data", "deduped.jsonl")
    deduplicate_dataset(inp, out)
