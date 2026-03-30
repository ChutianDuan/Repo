import sys

from python_rag.repos.document_index_repo import get_document_index_by_doc_id
from python_rag.services.embedding_service import embed_query
from python_rag.services.faiss_index_service import search_doc_faiss_index


def main():
    if len(sys.argv) < 3:
        print("usage: python scripts/test_doc_search.py <doc_id> <query>")
        sys.exit(1)

    doc_id = int(sys.argv[1])
    query = sys.argv[2]

    meta = get_document_index_by_doc_id(doc_id)
    if not meta:
        print("document index not found")
        sys.exit(1)

    qvec = embed_query(query)
    results = search_doc_faiss_index(
        index_path=meta["index_path"],
        mapping_path=meta["mapping_path"],
        query_vector=qvec,
        top_k=3,
    )

    for i, item in enumerate(results, 1):
        print("=" * 80)
        print(f"rank={i}")
        print(f"score={item['score']:.4f}")
        print(f"doc_id={item['doc_id']}, chunk_id={item['chunk_id']}, chunk_index={item['chunk_index']}")
        print(item["content"][:300])


if __name__ == "__main__":
    main()