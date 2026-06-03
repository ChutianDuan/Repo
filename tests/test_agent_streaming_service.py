import asyncio

from python_rag.app.agent.streaming import agent_streaming_service


class FakeAgentOrchestrator:
    async def run(
        self,
        question,
        trace_id=None,
        session_id=None,
        user_message_id=None,
        event_sink=None,
    ):
        await event_sink(
            {
                "type": "agent_step",
                "run_id": 501,
                "step_id": 601,
                "step_index": 0,
                "status": "RUNNING",
            }
        )
        await event_sink(
            {
                "type": "tool_call",
                "run_id": 501,
                "step_id": 601,
                "tool_call_id": "call_1",
                "tool_name": "knowledge_search",
                "arguments": {"query": question},
                "status": "RUNNING",
            }
        )
        await event_sink(
            {
                "type": "tool_result",
                "run_id": 501,
                "step_id": 601,
                "tool_call_id": "call_1",
                "tool_name": "knowledge_search",
                "result": {"total": 1},
                "status": "SUCCESS",
            }
        )
        return {
            "run_id": 501,
            "answer": "Agent final answer.",
            "citations": [
                {
                    "doc_id": 7,
                    "chunk_id": 11,
                    "chunk_index": 0,
                    "score": 0.91,
                    "snippet": "架构说明",
                }
            ],
            "steps_used": 1,
        }


def test_stream_agent_chat_emits_agent_and_legacy_events(monkeypatch):
    created_messages = []
    saved_citations = []

    def fake_create_message(session_id, role, content, status="SUCCESS", meta=None):
        message_id = 700 + len(created_messages) + 1
        row = {
            "message_id": message_id,
            "session_id": session_id,
            "role": role,
            "content": content,
            "status": status,
            "meta": meta or {},
        }
        created_messages.append(row)
        return row

    monkeypatch.setattr(agent_streaming_service, "create_message", fake_create_message)
    monkeypatch.setattr(
        agent_streaming_service,
        "bulk_insert_citations",
        lambda message_id, hits: saved_citations.append(
            {"message_id": message_id, "hits": hits}
        ),
    )
    monkeypatch.setattr(
        agent_streaming_service,
        "AgentOrchestrator",
        FakeAgentOrchestrator,
    )

    async def collect_events():
        return [
            event
            async for event in agent_streaming_service.stream_agent_chat(
                session_id=1,
                message="hello",
            )
        ]

    raw_stream = "".join(asyncio.run(collect_events()))

    assert "event: agent_step" in raw_stream
    assert "event: tool_call" in raw_stream
    assert "event: tool_result" in raw_stream
    assert "event: final" in raw_stream
    assert '"type": "delta"' in raw_stream
    assert '"type": "done"' in raw_stream
    assert '"citation_count": 1' in raw_stream
    assert created_messages[0]["role"] == "user"
    assert created_messages[1]["role"] == "assistant"
    assert created_messages[1]["meta"]["agent_run_id"] == 501
    assert saved_citations == [
        {
            "message_id": 702,
            "hits": [
                {
                    "doc_id": 7,
                    "chunk_id": 11,
                    "chunk_index": 0,
                    "score": 0.91,
                    "snippet": "架构说明",
                }
            ],
        }
    ]
