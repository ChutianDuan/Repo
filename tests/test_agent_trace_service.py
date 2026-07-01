from python_rag.app.agent.trace import trace_service
from python_rag.app.agent.schemas import (
    AgentRunStatus,
    AgentStepStatus,
    AgentToolCallStatus,
)


def test_create_run_uses_running_status(monkeypatch):
    calls = []

    def fake_create_agent_run(**kwargs):
        calls.append(kwargs)
        return 101

    monkeypatch.setattr(trace_service.models, "create_agent_run", fake_create_agent_run)

    run_id = trace_service.create_run(
        agent_name="rag-agent",
        trace_id="trace-1",
        model="glm-test",
        input_data={"question": "hello"},
        meta={"source": "unit-test"},
    )

    assert run_id == 101
    assert calls == [
        {
            "agent_name": "rag-agent",
            "trace_id": "trace-1",
            "agent_version": None,
            "model": "glm-test",
            "status": AgentRunStatus.RUNNING,
            "session_id": None,
            "user_message_id": None,
            "input_data": {"question": "hello"},
            "meta": {"source": "unit-test"},
        }
    ]


def test_create_step_can_write_multiple_steps(monkeypatch):
    created_steps = []

    def fake_get_next_agent_step_index(run_id):
        return len(created_steps)

    def fake_create_agent_step(**kwargs):
        created_steps.append(kwargs)
        return 200 + len(created_steps)

    monkeypatch.setattr(
        trace_service.models,
        "get_next_agent_step_index",
        fake_get_next_agent_step_index,
    )
    monkeypatch.setattr(trace_service.models, "create_agent_step", fake_create_agent_step)

    first_step_id = trace_service.create_step(run_id=7, name="plan")
    second_step_id = trace_service.create_step(run_id=7, name="act")

    assert first_step_id == 201
    assert second_step_id == 202
    assert [step["step_index"] for step in created_steps] == [0, 1]
    assert [step["status"] for step in created_steps] == [
        AgentStepStatus.RUNNING,
        AgentStepStatus.RUNNING,
    ]


def test_finish_run_and_fail_run_record_terminal_status(monkeypatch):
    updates = []
    monkeypatch.setattr(
        trace_service.models,
        "update_agent_run",
        lambda **kwargs: updates.append(kwargs),
    )

    trace_service.finish_run(
        run_id=1,
        output_data={"answer": "done"},
        prompt_tokens=3,
        completion_tokens=4,
    )
    trace_service.fail_run(run_id=2, error_message="tool timeout")

    assert updates[0]["status"] == AgentRunStatus.SUCCESS
    assert updates[0]["total_tokens"] == 7
    assert updates[0]["error_message"] is None
    assert updates[0]["finished"] is True
    assert updates[1]["status"] == AgentRunStatus.FAILED
    assert updates[1]["error_message"] == "tool timeout"
    assert updates[1]["finished"] is True


def test_finish_step_records_success(monkeypatch):
    updates = []
    monkeypatch.setattr(
        trace_service.models,
        "update_agent_step",
        lambda **kwargs: updates.append(kwargs),
    )

    trace_service.finish_step(
        step_id=12,
        decision="use retrieval",
        output_data={"next": "tool"},
        latency_ms=25,
    )

    assert updates == [
        {
            "step_id": 12,
            "status": AgentStepStatus.SUCCESS,
            "reasoning_summary": trace_service.models._UNSET,
            "decision": "use retrieval",
            "output_data": {"next": "tool"},
            "prompt_tokens": None,
            "completion_tokens": None,
            "total_tokens": None,
            "latency_ms": 25,
            "error_message": None,
            "finished": True,
        }
    ]


def test_tool_call_create_finish_and_fail(monkeypatch):
    created = []
    updates = []
    monkeypatch.setattr(
        trace_service.models,
        "create_agent_tool_call",
        lambda **kwargs: created.append(kwargs) or 301,
    )
    monkeypatch.setattr(
        trace_service.models,
        "update_agent_tool_call",
        lambda **kwargs: updates.append(kwargs),
    )

    tool_call_id = trace_service.create_tool_call(
        run_id=7,
        step_id=12,
        tool_name="retrieval.search",
        arguments={"query": "hello"},
    )
    trace_service.finish_tool_call(
        tool_call_id=tool_call_id,
        result={"hits": 2},
        latency_ms=80,
    )
    trace_service.fail_tool_call(
        tool_call_id=302,
        error_message="permission denied",
    )

    assert tool_call_id == 301
    assert created[0]["status"] == AgentToolCallStatus.RUNNING
    assert created[0]["arguments"] == {"query": "hello"}
    assert updates[0]["status"] == AgentToolCallStatus.SUCCESS
    assert updates[0]["result"] == {"hits": 2}
    assert updates[0]["result_preview"] == '{"hits": 2}'
    assert updates[0]["finished"] is True
    assert updates[1]["status"] == AgentToolCallStatus.FAILED
    assert updates[1]["result"] is trace_service.models._UNSET
    assert updates[1]["error_message"] == "permission denied"
    assert updates[1]["finished"] is True


def test_build_tool_result_preview_unwraps_standard_knowledge_result():
    result = {
        "ok": True,
        "error": None,
        "data": {
            "results": [],
            "total": 3,
            "retrieval": {
                "provider": "lancedb",
                "dense_top_k": 50,
                "rerank_top_k": 5,
                "candidate_count": 12,
                "vector_search_latency_ms": 7,
                "rerank_latency_ms": 11,
                "retrieval_latency_ms": 25,
            },
        },
    }

    assert trace_service.build_tool_result_preview("knowledge_search", result) == (
        "total=3; provider=lancedb; dense_top_k=50; rerank_top_k=5; "
        "candidates=12; vector_ms=7; rerank_ms=11; retrieval_ms=25"
    )
