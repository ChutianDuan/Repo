from pydantic import BaseModel, Field


class DocumentState(object):
    UPLOADED = "uploaded"
    PARSING = "parsing"
    PARSED = "parsed"
    INDEXING = "indexing"
    INDEXED = "indexed"
    FAILED = "failed"
    READY = INDEXED


class DocumentIndexStatus(object):
    NOT_INDEXED = "not_indexed"
    PARSING = "parsing"
    PARSED = "parsed"
    INDEXING = "indexing"
    INDEXED = "indexed"
    FAILED = "failed"


class ChunkEmbeddingStatus(object):
    PENDING = "pending"
    EMBEDDED = "embedded"
    FAILED = "failed"


class ChunkVectorIndexStatus(object):
    PENDING = "pending"
    INDEXED = "indexed"
    FAILED = "failed"


class CreateWebDocumentRequest(BaseModel):
    url: str = Field(..., min_length=1, max_length=2048)
    user_id: int = Field(default=1, gt=0)
