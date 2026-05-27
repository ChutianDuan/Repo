from pathlib import Path

import pytest

from python_rag.core.errors import AppError
from python_rag.modules.documents import service as document_service


def test_delete_document_removes_db_records_and_index_files(monkeypatch, tmp_path):
    upload_path = tmp_path / "note.md"
    index_path = tmp_path / "doc_7.faiss"
    mapping_path = tmp_path / "doc_7_mapping.json"
    for path in (upload_path, index_path, mapping_path):
        path.write_text("content", encoding="utf-8")

    calls = []
    monkeypatch.setattr(
        document_service,
        "get_document_by_id",
        lambda doc_id: {"id": doc_id, "storage_path": str(upload_path)},
    )
    monkeypatch.setattr(
        document_service,
        "get_document_index_by_doc_id",
        lambda doc_id: {"index_path": str(index_path), "mapping_path": str(mapping_path)},
    )

    def fake_delete(doc_id):
        calls.append(doc_id)
        return {
            "deleted_documents": 1,
            "deleted_indexes": 1,
            "deleted_chunks": 3,
            "deleted_citations": 2,
        }

    monkeypatch.setattr(document_service, "delete_document_by_id", fake_delete)

    result = document_service.delete_document(7)

    assert calls == [7]
    assert result["deleted"] is True
    assert result["deleted_chunks"] == 3
    assert not upload_path.exists()
    assert not index_path.exists()
    assert not mapping_path.exists()


def test_delete_document_missing_raises_not_found(monkeypatch):
    monkeypatch.setattr(document_service, "get_document_by_id", lambda doc_id: None)

    with pytest.raises(AppError) as exc:
        document_service.delete_document(404)

    assert exc.value.http_status == 404
