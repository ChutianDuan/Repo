import os

from python_rag.config import INGEST_CHUNK_OVERLAP, INGEST_CHUNK_SIZE
from python_rag.modules.documents.schemas import DocumentState
from python_rag.core.error_codes import TaskState,ERR_CELERY_ERROR
from python_rag.core.errors import AppError
from python_rag.core.logger import logger
from python_rag.modules.documents.repo import (
    get_document_by_id,
    update_document_status,
    delete_chunks_by_doc_id,
    bulk_insert_chunks,
    list_chunks_by_doc_id,
    upsert_document_index,
)

from python_rag.modules.tasks.repo import update_task_record
from python_rag.infra.storage import resolve_storage_path
from python_rag.modules.ingest.embedding_service import (
    embed_documents,
    get_embedding_model_name,
)
from python_rag.modules.ingest.chunking_service import (
    extract_text_from_document,
    validate_supported_document_filename,
)
from python_rag.modules.retrieval.faiss_service import build_doc_faiss_index
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


def run_ingest_for_document(doc_id, celery_task_id, progress_callback=None):
    """
    Day 2 ingest 逻辑：
    - 读文档
    - 切片
    - 重建 chunks
    - 生成 embeddings
    - 构建 FAISS 索引
    - 写 document_indexes
    - 更新 document/task 状态
    """
    try:
        embedding_model_name = get_embedding_model_name()
        doc = get_document_by_id(doc_id)
        if not doc:
            raise AppError(ERR_CELERY_ERROR, "document not found")

        update_document_status(doc_id, DocumentState.INGESTING, None)
        validate_supported_document_filename(doc.get("filename") or "")
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

        text = extract_text_from_document(
            path=resolve_storage_path(doc["storage_path"]),
            filename=doc.get("filename") or "",
        )
        if not text or not text.strip():
            raise AppError(ERR_CELERY_ERROR, "document text is empty")

        _emit_progress(
            celery_task_id=celery_task_id,
            state=TaskState.PROGRESS,
            progress=20,
            meta={
                "stage": "document_loaded",
                "doc_id": doc_id,
                "filename": doc["filename"],
                "char_count": len(text),
            },
            progress_callback=progress_callback,
        )

        chunks = simple_chunk_text(
            text=text,
            chunk_size=INGEST_CHUNK_SIZE,
            overlap=INGEST_CHUNK_OVERLAP,
        )
        if not chunks:
            raise AppError(ERR_CELERY_ERROR, "chunk result is empty")

        _emit_progress(
            celery_task_id=celery_task_id,
            state=TaskState.PROGRESS,
            progress=40,
            meta={
                "stage": "document_chunked",
                "doc_id": doc_id,
                "filename": doc["filename"],
                "chunk_count": len(chunks),
                "chunk_size": INGEST_CHUNK_SIZE,
                "chunk_overlap": INGEST_CHUNK_OVERLAP,
            },
            progress_callback=progress_callback,
        )

        # 先删旧 chunks，再重建
        delete_chunks_by_doc_id(doc_id)
        inserted = bulk_insert_chunks(doc_id, chunks)

        if inserted <= 0:
            raise AppError(ERR_CELERY_ERROR, "bulk_insert_chunks inserted 0 rows")

        _emit_progress(
            celery_task_id=celery_task_id,
            state=TaskState.PROGRESS,
            progress=60,
            meta={
                "stage": "chunks_inserted",
                "doc_id": doc_id,
                "filename": doc["filename"],
                "chunk_count": inserted,
            },
            progress_callback=progress_callback,
        )

        # 一定重新从 DB 读取，拿真实 chunk_id
        chunk_rows = list_chunks_by_doc_id(doc_id)
        if not chunk_rows:
            raise AppError(ERR_CELERY_ERROR, "no chunks found after insert")

        texts = [row.get("content", row.get("text", "")) for row in chunk_rows]
        _emit_progress(
            celery_task_id=celery_task_id,
            state=TaskState.PROGRESS,
            progress=75,
            meta={
                "stage": "embedding_chunks",
                "doc_id": doc_id,
                "filename": doc["filename"],
                "chunk_count": len(chunk_rows),
                "embedding_model": embedding_model_name,
            },
            progress_callback=progress_callback,
        )

        vectors = embed_documents(texts)
        if vectors is None or len(vectors) != len(chunk_rows):
            raise AppError(ERR_CELERY_ERROR, "embedding result count mismatch")

        _emit_progress(
            celery_task_id=celery_task_id,
            state=TaskState.PROGRESS,
            progress=90,
            meta={
                "stage": "building_faiss_index",
                "doc_id": doc_id,
                "filename": doc["filename"],
                "chunk_count": len(chunk_rows),
                "embedding_model": embedding_model_name,
            },
            progress_callback=progress_callback,
        )

        index_meta = build_doc_faiss_index(
            doc_id=doc_id,
            chunk_rows=chunk_rows,
            vectors=vectors,
        )

        upsert_document_index(
            doc_id=doc_id,
            index_type=index_meta["index_type"],
            embedding_model=embedding_model_name,
            dimension=index_meta["dimension"],
            index_path=index_meta["index_path"],
            mapping_path=index_meta["mapping_path"],
            chunk_count=index_meta["chunk_count"],
            status="READY",
        )

        update_document_status(doc_id, DocumentState.READY, None)

        result = {
            "stage": "finished",
            "doc_id": doc_id,
            "filename": doc["filename"],
            "chunk_count": len(chunk_rows),
            "document_status": DocumentState.READY,
            "index_status": "READY",
            "embedding_model": embedding_model_name,
            "index_type": index_meta["index_type"],
            "dimension": index_meta["dimension"],
            "index_path": index_meta["index_path"],
            "mapping_path": index_meta["mapping_path"],
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
                    "error": str(e),
                },
                error=str(e),
                progress_callback=progress_callback,
            )
        except Exception:
            logger.exception("update_task_record FAILURE failed")

        raise
