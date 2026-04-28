import os
import time

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
from python_rag.modules.monitor.request_metrics import (
    estimate_embedding_cost_usd,
    is_timeout_error,
    record_request_metric,
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
    started_at = time.perf_counter()
    text_extract_ms = None
    chunking_ms = None
    chunk_insert_ms = None
    embedding_ms = None
    index_ms = None
    embedding_tokens = None

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

        text_started_at = time.perf_counter()
        text = extract_text_from_document(
            path=resolve_storage_path(doc["storage_path"]),
            filename=doc.get("filename") or "",
        )
        text_extract_ms = int((time.perf_counter() - text_started_at) * 1000)
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

        chunking_started_at = time.perf_counter()
        chunks = simple_chunk_text(
            text=text,
            chunk_size=INGEST_CHUNK_SIZE,
            overlap=INGEST_CHUNK_OVERLAP,
        )
        chunking_ms = int((time.perf_counter() - chunking_started_at) * 1000)
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
        insert_started_at = time.perf_counter()
        delete_chunks_by_doc_id(doc_id)
        inserted = bulk_insert_chunks(doc_id, chunks)
        chunk_insert_ms = int((time.perf_counter() - insert_started_at) * 1000)

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
        chunk_rows = list_chunks_by_doc_id(doc_id, limit=None)
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

        embedding_started_at = time.perf_counter()
        vectors = embed_documents(texts)
        embedding_ms = int((time.perf_counter() - embedding_started_at) * 1000)
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

        index_started_at = time.perf_counter()
        index_meta = build_doc_faiss_index(
            doc_id=doc_id,
            chunk_rows=chunk_rows,
            vectors=vectors,
        )
        index_ms = int((time.perf_counter() - index_started_at) * 1000)

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

        embedding_tokens = sum(int(row.get("tokens_est") or 0) for row in chunk_rows)
        ready_latency_ms = None
        if doc.get("created_at"):
            ready_latency_ms = int(
                max(0, (time.time() - doc["created_at"].timestamp()) * 1000),
            )
        total_ingest_ms = int((time.perf_counter() - started_at) * 1000)
        cost_usd = estimate_embedding_cost_usd(embedding_tokens)

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
            "ingest_ready_ms": ready_latency_ms,
            "ingest_runtime_ms": total_ingest_ms,
            "embedding_tokens": embedding_tokens,
            "cost_usd": cost_usd,
            "timings_ms": {
                "text_extract_ms": text_extract_ms,
                "chunking_ms": chunking_ms,
                "chunk_insert_ms": chunk_insert_ms,
                "embedding_ms": embedding_ms,
                "index_ms": index_ms,
            },
        }

        record_request_metric(
            request_type="ingest",
            status="success",
            channel="celery",
            doc_id=doc_id,
            celery_task_id=celery_task_id,
            e2e_latency_ms=total_ingest_ms,
            ready_latency_ms=ready_latency_ms,
            embedding_tokens=embedding_tokens,
            cost_usd=cost_usd,
            answer_source="embedding",
            extra={
                **result["timings_ms"],
                "chunk_count": len(chunk_rows),
                "char_count": len(text),
                "document_size_bytes": int(doc.get("size_bytes") or 0),
            },
        )

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
        total_ingest_ms = int((time.perf_counter() - started_at) * 1000)

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

        record_request_metric(
            request_type="ingest",
            status="error",
            channel="celery",
            doc_id=doc_id,
            celery_task_id=celery_task_id,
            e2e_latency_ms=total_ingest_ms,
            embedding_tokens=embedding_tokens,
            cost_usd=estimate_embedding_cost_usd(embedding_tokens),
            timed_out=is_timeout_error(e),
            error_message=str(e),
            extra={
                "text_extract_ms": text_extract_ms,
                "chunking_ms": chunking_ms,
                "chunk_insert_ms": chunk_insert_ms,
                "embedding_ms": embedding_ms,
                "index_ms": index_ms,
            },
        )

        raise
