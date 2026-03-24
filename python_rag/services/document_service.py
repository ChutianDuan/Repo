from python_rag.domain.constants.document_state import DocumentState
from python_rag.domain.constants.error_code import DB_ERROR, INTERNAL_ERROR, NOT_FOUND_ERROR
from python_rag.domain.exceptions import AppException
from python_rag.domain.logger import logger
from python_rag.infra.storage import build_upload_path, save_bytes_to_path
from python_rag.repos.document_repo import (
    create_document_record,
    get_document_by_id,
)
from python_rag.utils.hash_utils import sha256_bytes


def save_uploaded_document(user_id, upload_file):
    try:
        content = upload_file.file.read()
        if not content:
            raise AppException(INTERNAL_ERROR, "empty upload file")

        file_path = build_upload_path(upload_file.filename)
        save_bytes_to_path(content, file_path)

        doc_id = create_document_record(
            user_id=user_id,
            filename=upload_file.filename,
            mime=upload_file.content_type or "application/octet-stream",
            sha256=sha256_bytes(content),
            size_bytes=len(content),
            storage_path=file_path,
            status=DocumentState.UPLOADED,
        )

        return {
            "doc_id": doc_id,
            "filename": upload_file.filename,
            "status": DocumentState.UPLOADED,
        }
    except AppException:
        raise
    except Exception as e:
        logger.exception("save_uploaded_document failed")
        raise AppException(DB_ERROR, "save_uploaded_document failed: {0}".format(e))


def get_document_detail(doc_id):
    try:
        row = get_document_by_id(doc_id)
        if not row:
            raise AppException(NOT_FOUND_ERROR, "document not found")

        return {
            "doc_id": row["id"],
            "filename": row["filename"],
            "mime": row["mime"],
            "size_bytes": row["size_bytes"],
            "status": row["status"],
            "storage_path": row["storage_path"],
        }
    except AppException:
        raise
    except Exception as e:
        logger.exception("get_document_detail failed")
        raise AppException(DB_ERROR, "get_document_detail failed: {0}".format(e))