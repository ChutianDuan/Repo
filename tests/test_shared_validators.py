import pytest
from pydantic import ValidationError

from python_rag.modules.chat.common import build_citations_from_hits
from python_rag.modules.chat.schemas import SubmitChatJobRequest
from python_rag.modules.retrieval.schemas import SearchRequest


def test_doc_ids_are_normalized_consistently_across_requests():
    chat_request = SubmitChatJobRequest(
        session_id=1,
        user_message_id=2,
        doc_ids=[3, "3", 4],
    )
    search_request = SearchRequest(
        query="hello",
        doc_ids=[3, "3", 4],
    )

    assert chat_request.doc_ids == [3, 4]
    assert search_request.doc_ids == [3, 4]


def test_doc_ids_reject_non_positive_values():
    with pytest.raises(ValidationError):
        SubmitChatJobRequest(
            session_id=1,
            user_message_id=2,
            doc_ids=[0],
        )


def test_citation_builder_preserves_snippets_and_scores():
    citations = build_citations_from_hits(
        [
            {
                "doc_id": 7,
                "chunk_id": 9,
                "chunk_index": 1,
                "score": 0.2,
                "rerank_score": 0.8,
                "content": "important context",
            }
        ]
    )

    assert citations == [
        {
            "rank": 1,
            "doc_id": 7,
            "chunk_id": 9,
            "chunk_index": 1,
            "score": 0.8,
            "faiss_score": None,
            "bm25_score": None,
            "rrf_score": None,
            "rerank_score": 0.8,
            "faiss_rank": None,
            "bm25_rank": None,
            "rrf_rank": None,
            "original_rank": None,
            "content": "important context",
            "snippet": "important context",
        }
    ]
