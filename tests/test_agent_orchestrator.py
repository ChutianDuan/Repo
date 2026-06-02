import asyncio
import json

from python_rag.app.agent import orchestrator
from python_rag.app.tools.base import BaseTool
from python_rag.app.tools.registry import ToolRegistry


class FakeKnowledgeSearchTool(BaseTool):
    name = "knowledge_search"
    description = "Search test knowledge."
    input_schema = {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "top_k": {"type": "integer"},
        },
        "required": ["query"],
        "additionalProperties": False,
    }
    timeout_ms = 1000
    permission_level = "readonly"

    def __init__(self):
        self.calls = []
        super().__init__()

    async def run(self, arguments: dict) -> dict:
        self.calls.append(arguments)
        return {
            "results": [
                {
                    "chunk_id": 1,
                    "chunk_index": 0,
                    "doc_id": 7,
                    "document_id": 7,
                    "title": "architecture.md",
                    "content": "项目架构包含 C++ Gateway、FastAPI Internal Service、Celery Worker 和知识库检索。",
                    "score": 0.91,
                }
            ],
            "total": 1,
        }


class EmptyKnowledgeSearchTool(FakeKnowledgeSearchTool):
    async def run(self, arguments: dict) -> dict:
        self.calls.append(arguments)
        return {
            "results": [],
            "total": 0,
        }


class TimeoutKnowledgeSearchTool(FakeKnowledgeSearchTool):
    async def run(self, arguments: dict) -> dict:
        self.calls.append(arguments)
        return {
            "results": [],
            "total": 0,
            "error": "knowledge_search timeout",
        }


class FakeTraceRecorder:
    def __init__(self):
        self.runs = []
        self.finished_runs = []
        self.failed_runs = []
        self.steps = []
        self.finished_steps = []
        self.tool_calls = []
        self.finished_tool_calls = []
        self.failed_tool_calls = []

    def create_run(self, **kwargs):
        self.runs.append(kwargs)
        return 101

    def finish_run(self, **kwargs):
        self.finished_runs.append(kwargs)

    def fail_run(self, **kwargs):
        self.failed_runs.append(kwargs)

    def create_step(self, **kwargs):
        self.steps.append(kwargs)
        return 200 + len(self.steps)

    def finish_step(self, **kwargs):
        self.finished_steps.append(kwargs)

    def create_tool_call(self, **kwargs):
        self.tool_calls.append(kwargs)
        return 300 + len(self.tool_calls)

    def finish_tool_call(self, **kwargs):
        self.finished_tool_calls.append(kwargs)

    def fail_tool_call(self, **kwargs):
        self.failed_tool_calls.append(kwargs)


def _patch_trace(monkeypatch, recorder):
    monkeypatch.setattr(orchestrator.trace_service, "create_run", recorder.create_run)
    monkeypatch.setattr(orchestrator.trace_service, "finish_run", recorder.finish_run)
    monkeypatch.setattr(orchestrator.trace_service, "fail_run", recorder.fail_run)
    monkeypatch.setattr(orchestrator.trace_service, "create_step", recorder.create_step)
    monkeypatch.setattr(orchestrator.trace_service, "finish_step", recorder.finish_step)
    monkeypatch.setattr(
        orchestrator.trace_service,
        "create_tool_call",
        recorder.create_tool_call,
    )
    monkeypatch.setattr(
        orchestrator.trace_service,
        "finish_tool_call",
        recorder.finish_tool_call,
    )
    monkeypatch.setattr(
        orchestrator.trace_service,
        "fail_tool_call",
        recorder.fail_tool_call,
    )


def _tool_call(arguments):
    return {
        "id": "call_knowledge_1",
        "type": "function",
        "function": {
            "name": "knowledge_search",
            "arguments": json.dumps(arguments, ensure_ascii=False),
        },
    }


def test_agent_orchestrator_calls_knowledge_search_and_returns_final_answer(monkeypatch):
    recorder = FakeTraceRecorder()
    _patch_trace(monkeypatch, recorder)
    knowledge_tool = FakeKnowledgeSearchTool()
    registry = ToolRegistry([knowledge_tool])
    llm_calls = []

    def fake_generate_from_messages(messages, tools=None, tool_choice=None):
        llm_calls.append(
            {
                "messages": messages,
                "tools": tools,
                "tool_choice": tool_choice,
            }
        )
        if len(llm_calls) == 1:
            return {
                "answer": "I need to search.",
                "message": {
                    "content": "I need to search.",
                    "tool_calls": [_tool_call({"query": "系统架构", "top_k": 5})],
                },
                "tool_calls": [_tool_call({"query": "系统架构", "top_k": 5})],
                "usage": {"prompt_tokens": 10, "completion_tokens": 3, "total_tokens": 13},
                "latency_ms": 11,
            }
        assert any(message["role"] == "tool" for message in messages)
        tool_message = [message for message in messages if message["role"] == "tool"][0]
        assert "项目架构包含" in tool_message["content"]
        return {
            "answer": "项目架构包含 C++ Gateway、FastAPI、Celery 和知识库检索。",
            "message": {
                "content": "项目架构包含 C++ Gateway、FastAPI、Celery 和知识库检索。",
                "tool_calls": [],
            },
            "tool_calls": [],
            "usage": {"prompt_tokens": 12, "completion_tokens": 8, "total_tokens": 20},
            "latency_ms": 12,
        }

    monkeypatch.setattr(
        orchestrator.llm_service,
        "generate_from_messages",
        fake_generate_from_messages,
    )

    events = []

    result = asyncio.run(
        orchestrator.AgentOrchestrator(
            registry=registry,
            max_steps=3,
        ).run("根据项目文档总结系统架构", event_sink=events.append)
    )

    assert result["run_id"] == 101
    assert result["answer"] == "项目架构包含 C++ Gateway、FastAPI、Celery 和知识库检索。"
    assert result["citations"] == [
        {
            "rank": 1,
            "doc_id": 7,
            "chunk_id": 1,
            "chunk_index": 0,
            "score": 0.91,
            "snippet": "项目架构包含 C++ Gateway、FastAPI Internal Service、Celery Worker 和知识库检索。",
            "content": "项目架构包含 C++ Gateway、FastAPI Internal Service、Celery Worker 和知识库检索。",
            "title": "architecture.md",
        }
    ]
    assert result["steps_used"] == 2
    assert knowledge_tool.calls == [{"query": "系统架构", "top_k": 5}]
    assert len(llm_calls) == 2
    assert llm_calls[0]["tool_choice"] == "auto"
    assert llm_calls[1]["tools"] is None
    assert llm_calls[1]["tool_choice"] is None
    assert [tool["function"]["name"] for tool in llm_calls[0]["tools"]] == [
        "knowledge_search",
    ]

    assert len(recorder.runs) == 1
    assert recorder.runs[0]["input_data"] == {"question": "根据项目文档总结系统架构"}
    assert len(recorder.steps) == 2
    assert len(recorder.finished_steps) == 2
    assert recorder.finished_steps[0]["decision"] == "tool_call"
    assert recorder.finished_steps[1]["decision"] == "final_answer"
    assert len(recorder.tool_calls) == 1
    assert recorder.tool_calls[0]["tool_name"] == "knowledge_search"
    assert recorder.tool_calls[0]["tool_call_id"] == "call_knowledge_1"
    assert len(recorder.finished_tool_calls) == 1
    assert recorder.finished_runs[0]["run_id"] == 101
    assert recorder.finished_runs[0]["output_data"]["answer"] == result["answer"]
    assert recorder.finished_runs[0]["output_data"]["citations"] == result["citations"]
    assert recorder.failed_runs == []

    event_types = [event["type"] for event in events]
    assert "agent_step" in event_types
    assert "tool_call" in event_types
    assert "tool_result" in event_types


def test_agent_orchestrator_answers_greeting_without_tool(monkeypatch):
    recorder = FakeTraceRecorder()
    _patch_trace(monkeypatch, recorder)
    knowledge_tool = FakeKnowledgeSearchTool()
    registry = ToolRegistry([knowledge_tool])
    llm_calls = []

    def fake_generate_from_messages(messages, tools=None, tool_choice=None):
        llm_calls.append({"messages": messages, "tools": tools, "tool_choice": tool_choice})
        return {
            "answer": "你好，我可以帮你基于项目文档回答问题。",
            "message": {
                "content": "你好，我可以帮你基于项目文档回答问题。",
                "tool_calls": [],
            },
            "tool_calls": [],
            "usage": {"prompt_tokens": 7, "completion_tokens": 8, "total_tokens": 15},
            "latency_ms": 9,
        }

    monkeypatch.setattr(
        orchestrator.llm_service,
        "generate_from_messages",
        fake_generate_from_messages,
    )

    events = []
    result = asyncio.run(
        orchestrator.AgentOrchestrator(registry=registry, max_steps=3).run(
            "你好",
            event_sink=events.append,
        )
    )

    assert result["answer"] == "你好，我可以帮你基于项目文档回答问题。"
    assert result["steps_used"] == 1
    assert knowledge_tool.calls == []
    assert recorder.tool_calls == []
    assert recorder.finished_steps[0]["decision"] == "final_answer"
    assert recorder.finished_runs[0]["output_data"]["observations"] == []
    assert [event["type"] for event in events].count("tool_call") == 0
    assert llm_calls[0]["tool_choice"] == "auto"


def test_agent_orchestrator_reports_insufficient_evidence_when_search_empty(monkeypatch):
    recorder = FakeTraceRecorder()
    _patch_trace(monkeypatch, recorder)
    knowledge_tool = EmptyKnowledgeSearchTool()
    registry = ToolRegistry([knowledge_tool])
    llm_calls = []

    def fake_generate_from_messages(messages, tools=None, tool_choice=None):
        llm_calls.append(messages)
        if len(llm_calls) == 1:
            return {
                "answer": "先检索知识库。",
                "message": {
                    "content": "先检索知识库。",
                    "tool_calls": [_tool_call({"query": "区块链支付模块", "top_k": 5})],
                },
                "tool_calls": [_tool_call({"query": "区块链支付模块", "top_k": 5})],
                "usage": {},
            }

        tool_message = [message for message in messages if message["role"] == "tool"][0]
        assert '"total": 0' in tool_message["content"]
        return {
            "answer": "当前知识库证据不足，无法确认文档里有区块链支付模块。",
            "message": {
                "content": "当前知识库证据不足，无法确认文档里有区块链支付模块。",
                "tool_calls": [],
            },
            "tool_calls": [],
            "usage": {},
        }

    monkeypatch.setattr(
        orchestrator.llm_service,
        "generate_from_messages",
        fake_generate_from_messages,
    )

    result = asyncio.run(
        orchestrator.AgentOrchestrator(registry=registry, max_steps=3).run(
            "文档里有没有区块链支付模块？"
        )
    )

    assert "证据不足" in result["answer"]
    assert knowledge_tool.calls == [{"query": "区块链支付模块", "top_k": 5}]
    assert recorder.finished_tool_calls[0]["result"] == {"results": [], "total": 0}
    assert recorder.failed_tool_calls == []
    assert recorder.finished_steps[0]["decision"] == "tool_call"
    assert recorder.finished_steps[1]["decision"] == "final_answer"


def test_agent_orchestrator_records_tool_error_result_as_failed_trace(monkeypatch):
    recorder = FakeTraceRecorder()
    _patch_trace(monkeypatch, recorder)
    knowledge_tool = TimeoutKnowledgeSearchTool()
    registry = ToolRegistry([knowledge_tool])
    llm_calls = []

    def fake_generate_from_messages(messages, tools=None, tool_choice=None):
        llm_calls.append(messages)
        if len(llm_calls) == 1:
            return {
                "answer": "",
                "message": {
                    "content": "",
                    "tool_calls": [_tool_call({"query": "系统架构", "top_k": 5})],
                },
                "tool_calls": [_tool_call({"query": "系统架构", "top_k": 5})],
                "usage": {},
            }

        tool_message = [message for message in messages if message["role"] == "tool"][0]
        assert "knowledge_search timeout" in tool_message["content"]
        return {
            "answer": "检索工具超时，已降级返回：当前无法可靠基于知识库总结系统架构。",
            "message": {
                "content": "检索工具超时，已降级返回：当前无法可靠基于知识库总结系统架构。",
                "tool_calls": [],
            },
            "tool_calls": [],
            "usage": {},
        }

    monkeypatch.setattr(
        orchestrator.llm_service,
        "generate_from_messages",
        fake_generate_from_messages,
    )

    events = []
    result = asyncio.run(
        orchestrator.AgentOrchestrator(registry=registry, max_steps=3).run(
            "根据项目文档总结系统架构",
            event_sink=events.append,
        )
    )

    assert "检索工具超时" in result["answer"]
    assert knowledge_tool.calls == [{"query": "系统架构", "top_k": 5}]
    assert recorder.finished_tool_calls == []
    assert len(recorder.failed_tool_calls) == 1
    assert recorder.failed_tool_calls[0]["error_message"] == "knowledge_search timeout"
    assert recorder.failed_tool_calls[0]["result"]["error"] == "knowledge_search timeout"
    failed_events = [
        event
        for event in events
        if event["type"] == "tool_result" and event["status"] == "FAILED"
    ]
    assert failed_events[0]["error_message"] == "knowledge_search timeout"
    assert recorder.finished_runs


def test_agent_orchestrator_records_tool_failure_and_continues(monkeypatch):
    recorder = FakeTraceRecorder()
    _patch_trace(monkeypatch, recorder)
    registry = ToolRegistry([FakeKnowledgeSearchTool()])
    llm_calls = []

    def fake_generate_from_messages(messages, tools=None, tool_choice=None):
        llm_calls.append(messages)
        if len(llm_calls) == 1:
            return {
                "answer": "",
                "message": {
                    "content": "",
                    "tool_calls": [_tool_call({"query": "x"})],
                },
                "tool_calls": [_tool_call({"query": "x"})],
                "usage": {},
            }
        tool_message = [message for message in messages if message["role"] == "tool"][0]
        assert "permission denied" in tool_message["content"]
        return {
            "answer": "I could not access the tool, so no answer is available.",
            "message": {
                "content": "I could not access the tool, so no answer is available.",
                "tool_calls": [],
            },
            "tool_calls": [],
            "usage": {},
        }

    monkeypatch.setattr(
        orchestrator.llm_service,
        "generate_from_messages",
        fake_generate_from_messages,
    )
    monkeypatch.setattr(
        orchestrator.AgentOrchestrator,
        "_get_readonly_tool",
        lambda self, name: (_ for _ in ()).throw(RuntimeError("permission denied")),
    )

    result = asyncio.run(
        orchestrator.AgentOrchestrator(
            registry=registry,
            max_steps=3,
        ).run("search something")
    )

    assert result["answer"] == "I could not access the tool, so no answer is available."
    assert len(recorder.failed_tool_calls) == 1
    assert recorder.failed_tool_calls[0]["error_message"] == "permission denied"
    assert recorder.finished_runs
