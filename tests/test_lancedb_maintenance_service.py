import sys
import types

from python_rag.app.core.error_codes import TaskState
from python_rag.app.modules.retrieval import lancedb_service


def test_submit_lancedb_document_rebuild_records_and_queues_task(monkeypatch):
    calls = []

    class FakeTask:
        @staticmethod
        def apply_async(kwargs, task_id):
            calls.append({"kwargs": kwargs, "task_id": task_id})

    fake_index_tasks = types.ModuleType("python_rag.app.tasks.index_tasks")
    fake_index_tasks.build_embedding_task = FakeTask
    monkeypatch.setitem(sys.modules, "python_rag.app.tasks.index_tasks", fake_index_tasks)

    monkeypatch.setattr(
        lancedb_service,
        "get_document_by_id",
        lambda doc_id: {"id": doc_id, "filename": "note.md"},
    )
    monkeypatch.setattr(
        lancedb_service,
        "get_document_chunk_stats",
        lambda doc_id: {"chunk_count": 3},
    )
    monkeypatch.setattr(lancedb_service, "create_task_record", lambda **kwargs: 11)
    monkeypatch.setattr(lancedb_service, "create_vector_index_job", lambda **kwargs: 22)

    result = lancedb_service.submit_lancedb_document_rebuild(doc_id=7)

    assert result["db_task_id"] == 11
    assert result["vector_job_id"] == 22
    assert result["state"] == TaskState.PENDING
    assert result["doc_id"] == 7
    assert result["chunk_count"] == 3
    assert calls == [{"kwargs": {"doc_id": 7}, "task_id": result["task_id"]}]
