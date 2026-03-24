from python_rag.domain.constants.document_state import DocumentState
from python_rag.domain.constants.task_state import TaskState
from python_rag.domain.constants.error_code import NOT_FOUND_ERROR, INTERNAL_ERROR
from python_rag.domain.exceptions import AppException
from python_rag.domain.logger import logger
from python_rag.repos.chunk_repo import delete_chunks_by_doc_id, bulk_insert_chunks
from python_rag.repos.document_repo import get_document_by_id, update_document_status
from python_rag.repos.task_repo import update_task_record
from python_rag.utils.text_chunker import simple_chunk_text


def _read_text_from_document(path):
    with open(path, "rb") as f:
        raw = f.read()

    try:
        return raw.decode("utf-8")
    except Exception:
        return raw.decode("utf-8", errors="ignore")


def run_ingest_for_document(doc_id, celery_task_id):
    try:
        doc = get_document_by_id(doc_id)
        if not doc:
            raise AppException(NOT_FOUND_ERROR, "document not found")

        update_document_status(doc_id, DocumentState.INGESTING, None)
        update_task_record(
            celery_task_id=celery_task_id,
            state=TaskState.STARTED,
            progress=5,
            meta={"stage": "document_status_updated", "doc_id": doc_id},
        )

        text = _read_text_from_document(doc["storage_path"])
        if not text.strip():
            raise AppException(INTERNAL_ERROR, "document text is empty")

        update_task_record(
            celery_task_id=celery_task_id,
            state=TaskState.PROGRESS,
            progress=30,
            meta={"stage": "document_loaded", "doc_id": doc_id},
        )

        chunks = simple_chunk_text(text, chunk_size=800, overlap=100)

        update_task_record(
            celery_task_id=celery_task_id,
            state=TaskState.PROGRESS,
            progress=60,
            meta={"stage": "chunked", "doc_id": doc_id, "chunk_count": len(chunks)},
        )

        delete_chunks_by_doc_id(doc_id)
        inserted = bulk_insert_chunks(doc_id, chunks)

        update_document_status(doc_id, DocumentState.READY, None)
        update_task_record(
            celery_task_id=celery_task_id,
            state=TaskState.SUCCESS,
            progress=100,
            meta={
                "stage": "finished",
                "doc_id": doc_id,
                "chunk_count": inserted,
            },
        )

        return {
            "doc_id": doc_id,
            "chunk_count": inserted,
        }
    except Exception as e:
        logger.exception("run_ingest_for_document failed")
        update_document_status(doc_id, DocumentState.FAILED, str(e))
        update_task_record(
            celery_task_id=celery_task_id,
            state=TaskState.FAILURE,
            progress=100,
            error=str(e),
            meta={"stage": "failed", "doc_id": doc_id},
        )
        raise