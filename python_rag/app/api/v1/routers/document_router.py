from fastapi import APIRouter, File, Form, Query, UploadFile

from python_rag.app.modules.documents.service import (
    delete_document,
    save_uploaded_document,
    get_document_detail,
    list_document_items,
)
from python_rag.app.shared.common import api_response
from python_rag.app.shared.schemas import ApiResponse

router = APIRouter(prefix="/internal", tags=["documents"])


@router.post("/documents/upload", response_model=ApiResponse)
def upload_document(
    file: UploadFile = File(...),
    user_id: int = Form(1),
):
    return api_response(save_uploaded_document(user_id=user_id, upload_file=file))


@router.get("/documents", response_model=ApiResponse)
def list_documents(
    user_id: int | None = Query(default=None, gt=0),
    status: str | None = Query(default=None, max_length=32),
    limit: int = Query(default=100, ge=1, le=1000),
):
    return api_response(list_document_items(user_id=user_id, status=status, limit=limit))


@router.get("/documents/{doc_id}", response_model=ApiResponse)
def get_document(doc_id: int):
    return api_response(get_document_detail(doc_id))


@router.delete("/documents/{doc_id}", response_model=ApiResponse)
def remove_document(doc_id: int):
    return api_response(delete_document(doc_id))
