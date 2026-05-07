from fastapi import APIRouter, File, Form, Query, UploadFile

from python_rag.modules.documents.service import (
    save_uploaded_document,
    get_document_detail,
    list_document_items,
)

router = APIRouter(prefix="/internal", tags=["documents"])


@router.post("/documents/upload")
def upload_document(
    file: UploadFile = File(...),
    user_id: int = Form(1),
):
    return save_uploaded_document(user_id=user_id, upload_file=file)


@router.get("/documents")
def list_documents(
    user_id: int | None = Query(default=None, gt=0),
    status: str | None = Query(default=None, max_length=32),
    limit: int = Query(default=100, ge=1, le=1000),
):
    return list_document_items(user_id=user_id, status=status, limit=limit)


@router.get("/documents/{doc_id}")
def get_document(doc_id: int):
    return get_document_detail(doc_id)
