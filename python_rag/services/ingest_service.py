import os

from python_rag.domain.constants.document_state import DocumentState
from python_rag.domain.constants.task_state import TaskState
from python_rag.domain.constants.error_code import NOT_FOUND_ERROR, INTERNAL_ERROR
from python_rag.domain.exceptions import AppException
from python_rag.domain.logger import logger
from python_rag.repos.document_repo import (
    get_document_by_id,
    update_document_status,
)
from python_rag.repos.chunk_repo import (
    delete_chunks_by_doc_id,
    bulk_insert_chunks,
)
from python_rag.repos.task_repo import update_task_record
from python_rag.utils.text_chunker import simple_chunk_text


def _emit_progress(celery_task_id, state, progress, meta, progress_callback=None, error=None):
    """
    同时更新：
    1. MySQL tasks 表
    2. Celery backend 状态（如果传入 callback）
    """
    update_task_record(
        celery_task_id=celery_task_id,
        state=state,
        progress=progress,
        meta=meta,
        error=error,
    )

    if progress_callback:
        try:
            progress_callback(state=state, meta=dict(meta or {}, progress=progress))
        except Exception:
            logger.exception("progress_callback failed")


def _read_text_file(path):
    if not os.path.exists(path):
        raise AppException(INTERNAL_ERROR, "document file does not exist")

    with open(path, "rb") as f:
        raw = f.read()

    if not raw:
        return ""

    encodings = [
        "utf-8",
        "utf-8-sig",
        "gb18030",
        "gbk",
    ]

    for enc in encodings:
        try:
            return raw.decode(enc)
        except Exception:
            pass

    return raw.decode("utf-8", errors="ignore")


def run_ingest_for_document(doc_id, celery_task_id, progress_callback=None):
    """
    真正的 ingest 逻辑：
    - 读文档
    - 切片
    - 写 chunks
    - 更新 document/task 状态
    """
    try:
        doc = get_document_by_id(doc_id)
        if not doc:
            raise AppException(NOT_FOUND_ERROR, "document not found")

        update_document_status(doc_id, DocumentState.INGESTING, None)
        _emit_progress(
            celery_task_id=celery_task_id,
            state=TaskState.STARTED,
            progress=5,
            meta={
                "stage": "document_marked_ingesting",
                "doc_id": doc_id,
                "filename": doc["filename"],
            },
            progress_callback=progress_callback,
        )

        text = _read_text_file(doc["storage_path"])
        if not text or not text.strip():
            raise AppException(INTERNAL_ERROR, "document text is empty")

        _emit_progress(
            celery_task_id=celery_task_id,
            state=TaskState.PROGRESS,
            progress=25,
            meta={
                "stage": "document_loaded",
                "doc_id": doc_id,
                "char_count": len(text),
            },
            progress_callback=progress_callback,
        )

        chunks = simple_chunk_text(
            text=text,
            chunk_size=800,
            overlap=100,
        )

        if not chunks:
            raise AppException(INTERNAL_ERROR, "chunk result is empty")

        _emit_progress(
            celery_task_id=celery_task_id,
            state=TaskState.PROGRESS,
            progress=55,
            meta={
                "stage": "document_chunked",
                "doc_id": doc_id,
                "chunk_count": len(chunks),
            },
            progress_callback=progress_callback,
        )

        delete_chunks_by_doc_id(doc_id)

        inserted = bulk_insert_chunks(doc_id, chunks)

        _emit_progress(
            celery_task_id=celery_task_id,
            state=TaskState.PROGRESS,
            progress=85,
            meta={
                "stage": "chunks_inserted",
                "doc_id": doc_id,
                "chunk_count": inserted,
            },
            progress_callback=progress_callback,
        )

        update_document_status(doc_id, DocumentState.READY, None)

        result = {
            "stage": "finished",
            "doc_id": doc_id,
            "filename": doc["filename"],
            "chunk_count": inserted,
            "document_status": DocumentState.READY,
        }

        _emit_progress(
            celery_task_id=celery_task_id,
            state=TaskState.SUCCESS,
            progress=100,
            meta=result,
            progress_callback=progress_callback,
        )

        return result

    except Exception as e:
        logger.exception("run_ingest_for_document failed")

        try:
            update_document_status(doc_id, DocumentState.FAILED, str(e))
        except Exception:
            logger.exception("update_document_status FAILED failed")

        try:
            _emit_progress(
                celery_task_id=celery_task_id,
                state=TaskState.FAILURE,
                progress=100,
                meta={
                    "stage": "failed",
                    "doc_id": doc_id,
                },
                error=str(e),
                progress_callback=progress_callback,
            )
        except Exception:
            logger.exception("update_task_record FAILURE failed")

        raise