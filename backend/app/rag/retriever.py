"""
Hybrid Retriever for Financial Regulatory Knowledge Base (Phase 7).
Combines:
1. Dense vector semantic search via ChromaDB.
2. Sparse keyword BM25 search via rank_bm25.
3. Reciprocal Rank Fusion (RRF) for merged ranking.
"""
import os
from typing import List, Dict, Any, Optional
from collections import defaultdict
import chromadb
from chromadb.config import Settings
from rank_bm25 import BM25Okapi

from backend.app.rag.ingest import CHROMA_PERSIST_DIR, AUTHORITATIVE_COLLECTION


class HybridRetriever:
    def __init__(self, persist_dir: str = CHROMA_PERSIST_DIR):
        self.persist_dir = persist_dir
        self.client = chromadb.PersistentClient(
            path=self.persist_dir,
            settings=Settings(anonymized_telemetry=False)
        )
        self.collection = self.client.get_or_create_collection(name=AUTHORITATIVE_COLLECTION)
        self.bm25_index: Optional[BM25Okapi] = None
        self.corpus_chunks: List[Dict[str, Any]] = []
        self._build_bm25_index()

    def _build_bm25_index(self):
        """Load all chunks from Chroma to build BM25 sparse keyword index."""
        results = self.collection.get(include=["documents", "metadatas"])
        docs = results.get("documents", [])
        metas = results.get("metadatas", [])
        ids = results.get("ids", [])

        self.corpus_chunks = []
        tokenized_corpus = []

        for idx, text in enumerate(docs):
            chunk_data = {
                "id": ids[idx],
                "text": text,
                "metadata": metas[idx] if idx < len(metas) else {}
            }
            self.corpus_chunks.append(chunk_data)
            # Simple whitespace and punctuation tokenization
            tokens = text.lower().replace("\n", " ").split()
            tokenized_corpus.append(tokens)

        if tokenized_corpus:
            self.bm25_index = BM25Okapi(tokenized_corpus)

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        regulator_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Execute hybrid retrieval combining dense vector search and BM25 sparse search with RRF.
        """
        if not self.corpus_chunks:
            self._build_bm25_index()

        if not self.corpus_chunks:
            return []

        # 1. Dense Chroma Query
        dense_where = None
        if regulator_filter:
            dense_where = {"regulator": regulator_filter}

        query_texts = [query]
        dense_results = self.collection.query(
            query_texts=query_texts,
            n_results=min(top_k * 3, len(self.corpus_chunks)),
            where=dense_where,
            include=["documents", "metadatas", "distances"]
        )

        dense_ranks: Dict[str, int] = {}
        dense_items: Dict[str, Dict[str, Any]] = {}

        if dense_results and dense_results.get("ids"):
            matched_ids = dense_results["ids"][0]
            matched_docs = dense_results["documents"][0]
            matched_metas = dense_results["metadatas"][0]
            for r_idx, chunk_id in enumerate(matched_ids, start=1):
                dense_ranks[chunk_id] = r_idx
                dense_items[chunk_id] = {
                    "id": chunk_id,
                    "text": matched_docs[r_idx - 1],
                    "metadata": matched_metas[r_idx - 1]
                }

        # 2. Sparse BM25 Query
        sparse_ranks: Dict[str, int] = {}
        if self.bm25_index:
            tokens = query.lower().split()
            bm25_scores = self.bm25_index.get_scores(tokens)
            sorted_indices = sorted(range(len(bm25_scores)), key=lambda i: bm25_scores[i], reverse=True)

            current_rank = 1
            for idx in sorted_indices[:top_k * 3]:
                chunk = self.corpus_chunks[idx]
                chunk_id = chunk["id"]
                if regulator_filter and chunk.get("metadata", {}).get("regulator") != regulator_filter:
                    continue
                sparse_ranks[chunk_id] = current_rank
                dense_items[chunk_id] = chunk
                current_rank += 1

        # 3. Reciprocal Rank Fusion (RRF)
        # RRF_score = 1 / (60 + rank_dense) + 1 / (60 + rank_sparse)
        rrf_scores: Dict[str, float] = defaultdict(float)
        k_const = 60.0

        for chunk_id, rank in dense_ranks.items():
            rrf_scores[chunk_id] += 1.0 / (k_const + rank)

        for chunk_id, rank in sparse_ranks.items():
            rrf_scores[chunk_id] += 1.0 / (k_const + rank)

        # Sort by RRF score descending
        sorted_ids = sorted(rrf_scores.keys(), key=lambda cid: rrf_scores[cid], reverse=True)

        results = []
        for cid in sorted_ids[:top_k]:
            item = dense_items[cid]
            results.append({
                "chunk_id": item["id"],
                "text": item["text"],
                "metadata": item["metadata"],
                "rrf_score": round(rrf_scores[cid], 5)
            })

        return results


# Singleton retriever instance
hybrid_retriever = HybridRetriever()
