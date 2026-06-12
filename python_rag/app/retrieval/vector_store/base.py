from dataclasses import dataclass
from typing import Any, Iterable, List, Optional, Protocol


@dataclass
class VectorRecord:
    chunk_id: int
    document_id: int
    chunk_index: int
    title: str
    content_hash: str
    status: str
    vector: List[float]


@dataclass
class VectorSearchHit:
    chunk_id: int
    document_id: int
    chunk_index: int
    title: str
    content_hash: str
    status: str
    score: float
    distance: Optional[float] = None
    rank: Optional[int] = None


class VectorStore(Protocol):
    def upsert(self, records: List[VectorRecord]) -> dict:
        ...

    def search(
        self,
        query_vector: Any,
        top_k: int,
        document_ids: Optional[Iterable[int]] = None,
    ) -> List[VectorSearchHit]:
        ...

    def delete_document(self, document_id: int) -> int:
        ...
