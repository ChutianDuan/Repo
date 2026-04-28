import os

from python_rag.config import MAX_DOCUMENT_SIZE_BYTES
from python_rag.modules.documents.schemas import DocumentState
from python_rag.core.error_codes import (
    ERR_DB_ERROR,
    ERR_DOCUMENT_NOT_FOUND,
    ERR_INVALID_REQUEST,
)
from python_rag.core.errors import AppError
from python_rag.core.logger import logger
from python_rag.infra.storage import build_upload_path, save_bytes_to_path
from python_rag.modules.documents.repo import (
    create_document_record,
    get_document_by_id,
)
from python_rag.modules.ingest.chunking_service import validate_supported_document_filename
from python_rag.utils.hash_utils import sha256_bytes


def save_uploaded_document(user_id, upload_file):
    file_path = None
    try:
        validate_supported_document_filename(upload_file.filename or "")

        content = upload_file.file.read()
        if not content:
            raise AppError(ERR_INVALID_REQUEST, "empty upload file")
        if len(content) > MAX_DOCUMENT_SIZE_BYTES:
            raise AppError(
                ERR_INVALID_REQUEST,
                "upload file is too large; max supported size is {0} bytes".format(
                    MAX_DOCUMENT_SIZE_BYTES,
                ),
            )

        file_path = build_upload_path(upload_file.filename)
        save_bytes_to_path(content, file_path)

        try:
            doc_id = create_document_record(
                user_id=user_id,
                filename=upload_file.filename,
                mime=upload_file.content_type or "application/octet-stream",
                sha256=sha256_bytes(content),
                size_bytes=len(content),
                storage_path=file_path,
                status=DocumentState.UPLOADED,
            )
        except Exception:
            if file_path and os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except Exception:
                    logger.exception("failed to cleanup uploaded file after document insert failure")
            raise

        return {
            "doc_id": doc_id,
            "filename": upload_file.filename,
            "status": DocumentState.UPLOADED,
        }
    except AppError:
        raise
    except Exception as e:
        logger.exception("save_uploaded_document failed")
        raise AppError(ERR_DB_ERROR, "save_uploaded_document failed: {0}".format(e))


def get_document_detail(doc_id):
    try:
        row = get_document_by_id(doc_id)
        if not row:
            raise AppError(ERR_DOCUMENT_NOT_FOUND, "document not found", http_status=404)

        return {
            "doc_id": row["id"],
            "user_id": row["user_id"],
            "filename": row["filename"],
            "mime": row["mime"],
            "size_bytes": row["size_bytes"],
            "status": row["status"],
            "storage_path": row["storage_path"],
            "error_message": row["error_message"],
            "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            "updated_at": row.get("updated_at").isoformat() if row.get("updated_at") else None,
        }
    except AppError:
        raise
    except Exception as e:
        logger.exception("get_document_detail failed")
        raise AppError(ERR_DB_ERROR, "get_document_detail failed: {0}".format(e))
