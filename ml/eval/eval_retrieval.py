"""
Retrieval Benchmark Evaluator for Phase 7.
Evaluates HybridRetriever on 30 hand-written queries from ml/eval/retrieval_queries.yaml.
Calculates Recall@5 and Mean Reciprocal Rank (MRR).
"""
import os
import sys
import yaml
from typing import Dict, Any

# Ensure project root in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from backend.app.rag.retriever import hybrid_retriever


QUERIES_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "retrieval_queries.yaml"))


def evaluate_retrieval(top_k: int = 5) -> Dict[str, Any]:
    with open(QUERIES_PATH, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    queries = data.get("queries", [])
    total = len(queries)
    hits_at_k = 0
    reciprocal_ranks = []

    print(f"Evaluating {total} queries with top_k={top_k} ...")

    details = []
    for q in queries:
        qid = q["id"]
        qtext = q["query"]
        expected_doc = q["expected_doc_id"]
        expected_sec = q.get("expected_section")

        results = hybrid_retriever.retrieve(query=qtext, top_k=top_k)
        retrieved_doc_ids = [r.get("metadata", {}).get("doc_id") for r in results]

        # A hit occurs if expected_doc_id appears in top_k results
        hit = (expected_doc in retrieved_doc_ids)
        rank = -1
        if hit:
            hits_at_k += 1
            rank = retrieved_doc_ids.index(expected_doc) + 1
            reciprocal_ranks.append(1.0 / rank)
        else:
            reciprocal_ranks.append(0.0)

        details.append({
            "id": qid,
            "expected_doc": expected_doc,
            "hit": hit,
            "rank": rank,
            "top_retrieved": retrieved_doc_ids[:3]
        })

    recall_at_k = hits_at_k / max(total, 1)
    mrr = sum(reciprocal_ranks) / max(total, 1)

    print(f"\n--- Benchmark Results ---")
    print(f"Total Queries: {total}")
    print(f"Hits @ {top_k}: {hits_at_k}/{total}")
    print(f"Recall @ {top_k}: {recall_at_k:.4f} ({recall_at_k * 100:.2f}%)")
    print(f"MRR: {mrr:.4f}")

    return {
        "total": total,
        "hits_at_k": hits_at_k,
        "recall_at_k": recall_at_k,
        "mrr": mrr,
        "details": details
    }


if __name__ == "__main__":
    evaluate_retrieval(top_k=5)
