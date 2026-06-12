from pathlib import Path

import pytest

from python_rag.app.core.errors import AppError
from python_rag.app.modules.retrieval import lancedb_service
from python_rag.app.retrieval.vector_store.lancedb_store import LanceDBVectorStore


class FakeLanceDBStore:
    def __init__(self, refs=None):
        self.refs = refs or []
        self.deleted_chunk_ids = []

    def capacity(self, document_sample_limit=20):
        return {
            "index_type": "lancedb",
            "uri": "/tmp/lancedb",
            "table_name": "chunk_vectors",
            "table_exists": True,
            "vector_count": len(self.refs),
            "row_count": len(self.refs),
            "document_count": 1,
            "dimension": 2,
            "status_counts": {"indexed": len(self.refs)},
            "top_documents": [{"doc_id": 7, "vector_count": len(self.refs)}],
            "disk_bytes": 12,
            "path_exists": True,
        }

    def list_vector_refs(self, document_ids=None, limit=None):
        refs = list(self.refs)
        if document_ids:
            allowed = {int(item) for item in document_ids}
            refs = [ref for ref in refs if int(ref["document_id"]) in allowed]
        if limit is not None:
            refs = refs[: int(limit)]
        return refs

    def delete_chunk_ids(self, chunk_ids):
        self.deleted_chunk_ids.extend(int(item) for item in chunk_ids)
        return len(self.deleted_chunk_ids)


def test_lancedb_index_status_reports_missing_and_orphan_vectors(monkeypatch):
    store = FakeLanceDBStore(
        refs=[
            {
                "chunk_id": 10,
                "document_id": 7,
                "chunk_index": 0,
                "status": "indexed",
            },
            {
                "chunk_id": 99,
                "document_id": 7,
                "chunk_index": 8,
                "status": "indexed",
            },
        ]
    )
    monkeypatch.setattr(lancedb_service, "_lancedb_store", lambda: store)
    monkeypatch.setattr(
        lancedb_service,
        "get_document_by_id",
        lambda doc_id: {
            "id": doc_id,
            "user_id": 1,
            "filename": "note.md",
            "status": "uploaded",
            "index_status": "indexed",
            "error_message": None,
            "created_at": None,
            "updated_at": None,
        },
    )
    monkeypatch.setattr(
        lancedb_service,
        "get_document_chunk_stats",
        lambda doc_id: {
            "chunk_count": 2,
            "embedding_status_counts": {"embedded": 2},
            "vector_index_status_counts": {"indexed": 2},
        },
    )
    monkeypatch.setattr(
        lancedb_service,
        "list_chunk_refs_by_doc_id",
        lambda doc_id: [{"id": 10, "doc_id": doc_id}, {"id": 11, "doc_id": doc_id}],
    )
    monkeypatch.setattr(lancedb_service, "get_document_index_by_doc_id", lambda doc_id: None)
    monkeypatch.setattr(lancedb_service, "get_latest_vector_index_job", lambda doc_id: None)

    result = lancedb_service.get_lancedb_index_status(doc_id=7)

    assert result["status"] == "degraded"
    assert result["healthy"] is False
    assert set(result["health"]["reasons"]) == {"missing_vectors", "orphan_vectors"}
    assert result["consistency"]["missing_chunk_ids"] == [11]
    assert result["consistency"]["orphan_chunk_ids"] == [99]
    assert result["lancedb"]["vector_count"] == 2


def test_cleanup_lancedb_orphan_vectors_deletes_only_orphans(monkeypatch):
    store = FakeLanceDBStore(
        refs=[
            {"chunk_id": 1, "document_id": 10, "chunk_index": 0, "status": "indexed"},
            {"chunk_id": 2, "document_id": 20, "chunk_index": 0, "status": "indexed"},
            {"chunk_id": 3, "document_id": 30, "chunk_index": 0, "status": "indexed"},
        ]
    )
    monkeypatch.setattr(lancedb_service, "_lancedb_store", lambda: store)
    monkeypatch.setattr(
        lancedb_service,
        "list_existing_chunk_refs",
        lambda chunk_ids: {1: 10, 2: 99},
    )

    dry_run = lancedb_service.cleanup_lancedb_orphan_vectors(dry_run=True, limit=10)
    assert dry_run["orphan_chunk_ids"] == [2, 3]
    assert dry_run["deleted_count"] == 0
    assert store.deleted_chunk_ids == []

    result = lancedb_service.cleanup_lancedb_orphan_vectors(dry_run=False, limit=10)
    assert result["orphan_count"] == 2
    assert result["deleted_count"] == 2
    assert store.deleted_chunk_ids == [2, 3]
    assert {item["reason"] for item in result["orphans"]} == {
        "document_mismatch",
        "chunk_missing",
    }


def test_lancedb_backup_and_restore_requires_overwrite_for_existing_path(tmp_path):
    source = tmp_path / "lancedb"
    source.mkdir()
    current_file = source / "current.txt"
    current_file.write_text("current", encoding="utf-8")

    store = LanceDBVectorStore(uri=str(source), table_name="chunk_vectors")
    backup = store.backup(backup_dir=str(tmp_path / "backups"), label="manual")
    backup_path = Path(backup["backup_path"])
    assert backup_path.exists()
    assert (backup_path / "current.txt").read_text(encoding="utf-8") == "current"

    current_file.write_text("changed", encoding="utf-8")
    with pytest.raises(AppError) as exc:
        store.restore(str(backup_path), overwrite=False)
    assert exc.value.http_status == 409

    restored = store.restore(str(backup_path), overwrite=True)
    assert current_file.read_text(encoding="utf-8") == "current"
    assert restored["overwritten"] is True
    assert Path(restored["pre_restore_backup_path"]).exists()
