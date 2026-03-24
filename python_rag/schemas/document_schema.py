from pydantic import BaseModel


class UploadDocumentResponse(BaseModel):
    doc_id: int
    filename: str
    status: str


class DocumentDetailResponse(BaseModel):
    doc_id: int
    filename: str
    mime: str
    size_bytes: int
    status: str
    storage_path: str