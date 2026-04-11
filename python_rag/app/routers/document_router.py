from fastapi import APIRouter, File, Form, UploadFile

from python_rag.modules.documents.service import (
    save_uploaded_document,
    get_document_detail,
)

router = APIRouter(prefix="/internal", tags=["documents"])


@router.post("/documents/upload")
def upload_document(
    file: UploadFile = File(...),
    user_id: int = Form(1),
):
    return save_uploaded_document(user_id=user_id, upload_file=file)


@router.get("/documents/{doc_id}")
def get_document(doc_id: int):
    return get_document_detail(doc_id)
