from fastapi import APIRouter, File, Form, UploadFile

from python_rag.services.document_service import (
    save_uploaded_document,
    get_document_detail,
)

router = APIRouter(prefix="/internal", tags=["documents"])


@router.post("/documents/upload")
def upload_document(
    file=File(...),
    user_id=Form(1),
):
    return save_uploaded_document(user_id=int(user_id), upload_file=file)


@router.get("/documents/{doc_id}")
def get_document(doc_id):
    return get_document_detail(int(doc_id))