from typing import Optional

from fastapi import APIRouter, Path, Query

from python_rag.app.modules.retrieval.lancedb_service import (
    backup_lancedb_index,
    cleanup_lancedb_orphan_vectors,
    get_lancedb_capacity,
    get_lancedb_index_status,
    restore_lancedb_index,
    submit_lancedb_document_rebuild,
)
from python_rag.app.retrieval.hybrid_service import search_in_documents
from python_rag.app.modules.retrieval.schemas import (
    CleanupLanceDBOrphansRequest,
    LanceDBBackupRequest,
    LanceDBRestoreRequest,
    SearchRequest,
    SearchResponse,
)
from python_rag.app.shared.common import api_response
from python_rag.app.shared.schemas import ApiResponse

router = APIRouter(prefix="/internal", tags=["retrieval"])


@router.post("/search", response_model=SearchResponse)
def internal_search(req: SearchRequest):
    result = search_in_documents(
        doc_id=req.doc_id,
        doc_ids=req.doc_ids,
        user_id=req.user_id,
        query=req.query,
        top_k=req.top_k,
        relevant_chunk_ids=req.relevant_chunk_ids,
        relevant_chunk_indexes=req.relevant_chunk_indexes,
    )
    return api_response(result)


@router.get("/lancedb/status", response_model=ApiResponse)
def query_lancedb_status(doc_id: Optional[int] = Query(None, gt=0)):
    return api_response(get_lancedb_index_status(doc_id=doc_id))


@router.get("/lancedb/capacity", response_model=ApiResponse)
def query_lancedb_capacity(
    document_sample_limit: int = Query(20, ge=1, le=1000),
):
    return api_response(
        get_lancedb_capacity(document_sample_limit=document_sample_limit)
    )


@router.post("/lancedb/documents/{doc_id}/rebuild", response_model=ApiResponse)
def rebuild_lancedb_document_index(doc_id: int = Path(..., gt=0)):
    return api_response(submit_lancedb_document_rebuild(doc_id=doc_id))


@router.post("/lancedb/orphans/cleanup", response_model=ApiResponse)
def cleanup_lancedb_orphans(req: CleanupLanceDBOrphansRequest):
    return api_response(
        cleanup_lancedb_orphan_vectors(dry_run=req.dry_run, limit=req.limit)
    )


@router.post("/lancedb/backup", response_model=ApiResponse)
def backup_lancedb(req: LanceDBBackupRequest):
    return api_response(
        backup_lancedb_index(backup_dir=req.backup_dir, label=req.label)
    )


@router.post("/lancedb/restore", response_model=ApiResponse)
def restore_lancedb(req: LanceDBRestoreRequest):
    return api_response(
        restore_lancedb_index(
            backup_path=req.backup_path,
            overwrite=req.overwrite,
        )
    )
