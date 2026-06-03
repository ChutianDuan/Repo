import json
import math
import re
from collections import Counter
from typing import Any, Dict, List, Optional, Sequence

from python_rag.app.core.config import BM25_B, BM25_K1


_TOKEN_PATTERN = re.compile(r"[a-z0-9]+|[\u4e00-\u9fff]+", re.IGNORECASE)
_CJK_PATTERN = re.compile(r"^[\u4e00-\u9fff]+$")


def tokenize_for_bm25(text: str) -> List[str]:
    terms: List[str] = []
    for raw_term in _TOKEN_PATTERN.findall((text or "").lower()):
        if _CJK_PATTERN.match(raw_term):
            terms.extend(raw_term)
            terms.extend(
                raw_term[index : index + 2]
                for index in range(max(0, len(raw_term) - 1))
            )
            continue

        terms.append(raw_term)
    return terms


def _load_mapping(mapping_path: str) -> List[Dict[str, Any]]:
    with open(mapping_path, "r", encoding="utf-8") as f:
        mapping = json.load(f)
    if not isinstance(mapping, list):
        return []
    return [item for item in mapping if isinstance(item, dict)]


def _score_bm25(
    tokenized_docs: Sequence[List[str]],
    query_tokens: Sequence[str],
    *,
    k1: float,
    b: float,
) -> List[float]:
    doc_count = len(tokenized_docs)
    if doc_count <= 0 or not query_tokens:
        return []

    doc_lengths = [len(tokens) for tokens in tokenized_docs]
    avg_doc_len = sum(doc_lengths) / doc_count if doc_count else 0.0
    if avg_doc_len <= 0:
        avg_doc_len = 1.0

    term_frequencies = [Counter(tokens) for tokens in tokenized_docs]
    doc_frequencies: Counter[str] = Counter()
    for frequencies in term_frequencies:
        doc_frequencies.update(frequencies.keys())

    scores = [0.0 for _ in tokenized_docs]
    query_frequencies = Counter(query_tokens)

    for term, query_frequency in query_frequencies.items():
        doc_frequency = doc_frequencies.get(term, 0)
        if doc_frequency <= 0:
            continue

        idf = math.log(1.0 + (doc_count - doc_frequency + 0.5) / (doc_frequency + 0.5))
        for doc_index, frequencies in enumerate(term_frequencies):
            term_frequency = frequencies.get(term, 0)
            if term_frequency <= 0:
                continue

            denominator = term_frequency + k1 * (
                1.0 - b + b * doc_lengths[doc_index] / avg_doc_len
            )
            if denominator <= 0:
                continue

            scores[doc_index] += (
                idf
                * (term_frequency * (k1 + 1.0) / denominator)
                * query_frequency
            )

    return scores


def search_doc_bm25_index(
    mapping_path: str,
    query: str,
    top_k: int = 3,
    *,
    k1: Optional[float] = None,
    b: Optional[float] = None,
) -> List[Dict[str, Any]]:
    if top_k <= 0:
        return []

    mapping = _load_mapping(mapping_path)
    if not mapping:
        return []

    query_tokens = tokenize_for_bm25(query)
    if not query_tokens:
        return []

    tokenized_docs = [
        tokenize_for_bm25(item.get("content") or item.get("text") or "")
        for item in mapping
    ]
    scores = _score_bm25(
        tokenized_docs,
        query_tokens,
        k1=BM25_K1 if k1 is None else k1,
        b=BM25_B if b is None else b,
    )

    ranked = sorted(
        (
            (score, index)
            for index, score in enumerate(scores)
            if score > 0 and index < len(mapping)
        ),
        key=lambda item: item[0],
        reverse=True,
    )

    results = []
    for rank, (score, index) in enumerate(ranked[:top_k], start=1):
        item = mapping[index]
        content = item.get("content") or item.get("text") or ""
        bm25_score = float(score)
        results.append(
            {
                "doc_id": item["doc_id"],
                "chunk_id": item["chunk_id"],
                "chunk_index": item["chunk_index"],
                "score": bm25_score,
                "bm25_score": bm25_score,
                "bm25_rank": rank,
                "content": content,
            }
        )
    return results
