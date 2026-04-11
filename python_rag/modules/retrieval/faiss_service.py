import json
from pathlib import Path
from typing import List, Dict

import faiss
import numpy as np


INDEX_DIR = Path("./data/indexes")
INDEX_DIR.mkdir(parents=True, exist_ok=True)


def build_doc_faiss_index(
    doc_id: int,
    chunk_rows: List[Dict],
    vectors: np.ndarray,
):
    if vectors.ndim != 2 or len(chunk_rows) != vectors.shape[0]:
        raise ValueError("chunk count and vector count mismatch")

    dim = vectors.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(vectors)

    index_path = INDEX_DIR / f"doc_{doc_id}.faiss"
    mapping_path = INDEX_DIR / f"doc_{doc_id}_mapping.json"

    faiss.write_index(index, str(index_path))

    mapping = []
    for row_idx, chunk in enumerate(chunk_rows):
        content = chunk.get("content", chunk.get("text", ""))

        mapping.append(
            {
                "row_id": row_idx,
                "chunk_id": chunk["id"],
                "doc_id": chunk["doc_id"],
                "chunk_index": chunk["chunk_index"],
                "content": content,
            }
        )

    with open(mapping_path, "w", encoding="utf-8") as f:
        json.dump(mapping, f, ensure_ascii=False, indent=2)

    return {
        "index_type": "faiss_flat_ip",
        "dimension": dim,
        "index_path": str(index_path),
        "mapping_path": str(mapping_path),
        "chunk_count": len(chunk_rows),
    }


def search_doc_faiss_index(index_path: str, mapping_path: str, query_vector: np.ndarray, top_k: int = 3):
    index = faiss.read_index(index_path)

    with open(mapping_path, "r", encoding="utf-8") as f:
        mapping = json.load(f)

    query = np.asarray([query_vector], dtype="float32")
    scores, indices = index.search(query, top_k)

    results = []
    for score, idx in zip(scores[0], indices[0]):
        if idx < 0 or idx >= len(mapping):
            continue
        item = mapping[idx]
        results.append(
            {
                "doc_id": item["doc_id"],
                "chunk_id": item["chunk_id"],
                "chunk_index": item["chunk_index"],
                "score": float(score),
                "content": item["content"],
            }
        )
    return results
