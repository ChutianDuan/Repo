import json

from python_rag.modules.llm import service as llm_service


class _FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.text = json.dumps(payload, ensure_ascii=False)

    def json(self):
        return self._payload


class _FakeStreamResponse:
    def __init__(self, payloads, status_code=200):
        self._payloads = payloads
        self.status_code = status_code
        self.text = ""

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def iter_lines(self, decode_unicode=True):
        for payload in self._payloads:
            if payload == "[DONE]":
                yield "data: [DONE]"
            else:
                yield "data: " + json.dumps(payload, ensure_ascii=False)
            yield ""


def _enable_llm(monkeypatch):
    monkeypatch.setattr(llm_service, "LLM_ENABLE", True)
    monkeypatch.setattr(llm_service, "LLM_PROVIDER", "openai_compatible")
    monkeypatch.setattr(llm_service, "LLM_BASE_URL", "http://llm.test/v1")
    monkeypatch.setattr(llm_service, "LLM_MODEL", "test-model")
    monkeypatch.setattr(llm_service, "LLM_MAX_GENERATION_ROUNDS", 3)


def _tool_schema():
    return [
        {
            "type": "function",
            "function": {
                "name": "knowledge_search",
                "description": "Search knowledge base.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "top_k": {"type": "integer"},
                    },
                    "required": ["query"],
                    "additionalProperties": False,
                },
            },
        }
    ]


def test_build_payload_includes_tools_and_tool_choice(monkeypatch):
    monkeypatch.setattr(llm_service, "LLM_MODEL", "test-model")

    tools = _tool_schema()
    payload = llm_service._build_payload(
        [{"role": "user", "content": "search it"}],
        tools=tools,
        tool_choice="auto",
    )

    assert payload["tools"] == tools
    assert payload["tool_choice"] == "auto"
    assert payload["messages"] == [{"role": "user", "content": "search it"}]


def test_generate_from_messages_plain_chat_is_unchanged(monkeypatch):
    _enable_llm(monkeypatch)
    calls = []

    def fake_post(url, headers=None, json=None, timeout=None, **kwargs):
        calls.append(json)
        return _FakeResponse(
            {
                "model": "test-model",
                "choices": [
                    {
                        "message": {"content": "plain answer\n[[LLM_DONE]]"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
            }
        )

    monkeypatch.setattr(llm_service.http_client, "post", fake_post)

    result = llm_service.generate_from_messages([
        {"role": "user", "content": "hello"},
    ])

    assert result["answer"] == "plain answer"
    assert result["message_content"] == "plain answer\n[[LLM_DONE]]"
    assert result["message"] == {
        "content": "plain answer\n[[LLM_DONE]]",
        "tool_calls": [],
    }
    assert result["tool_calls"] == []
    assert result["usage"] == {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3}
    assert "tools" not in calls[0]
    assert "tool_choice" not in calls[0]
    assert "[[LLM_DONE]]" in calls[0]["messages"][0]["content"]


def test_generate_from_messages_sends_tools_and_parses_tool_calls(monkeypatch):
    _enable_llm(monkeypatch)
    calls = []
    tool_calls = [
        {
            "id": "call_1",
            "type": "function",
            "function": {
                "name": "knowledge_search",
                "arguments": "{\"query\":\"agent trace\",\"top_k\":5}",
            },
        }
    ]

    def fake_post(url, headers=None, json=None, timeout=None, **kwargs):
        calls.append(json)
        return _FakeResponse(
            {
                "model": "test-model",
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "I should search the knowledge base.",
                            "tool_calls": tool_calls,
                        },
                        "finish_reason": "tool_calls",
                    }
                ],
                "usage": {"prompt_tokens": 10, "completion_tokens": 4, "total_tokens": 14},
            }
        )

    monkeypatch.setattr(llm_service.http_client, "post", fake_post)

    tools = _tool_schema()
    result = llm_service.generate_from_messages(
        [{"role": "user", "content": "find agent trace docs"}],
        tools=tools,
        tool_choice="auto",
    )

    assert len(calls) == 1
    assert calls[0]["tools"] == tools
    assert calls[0]["tool_choice"] == "auto"
    assert calls[0]["messages"] == [{"role": "user", "content": "find agent trace docs"}]
    assert result["answer"] == "I should search the knowledge base."
    assert result["message_content"] == "I should search the knowledge base."
    assert result["message"] == {
        "content": "I should search the knowledge base.",
        "tool_calls": tool_calls,
    }
    assert result["tool_calls"] == tool_calls
    assert result["finish_reason"] == "tool_calls"
    assert result["stop_reason"] == "tool_calls"
    assert result["stopped_by_model"] is True


def test_generate_from_messages_allows_tool_calls_without_content(monkeypatch):
    _enable_llm(monkeypatch)
    tool_calls = [
        {
            "id": "call_1",
            "type": "function",
            "function": {
                "name": "knowledge_search",
                "arguments": "{\"query\":\"rag\"}",
            },
        }
    ]

    def fake_post(url, headers=None, json=None, timeout=None, **kwargs):
        return _FakeResponse(
            {
                "model": "test-model",
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": tool_calls,
                        },
                        "finish_reason": "tool_calls",
                    }
                ],
            }
        )

    monkeypatch.setattr(llm_service.http_client, "post", fake_post)

    result = llm_service.generate_from_messages(
        [{"role": "user", "content": "search"}],
        tools=_tool_schema(),
        tool_choice="auto",
    )

    assert result["answer"] == ""
    assert result["message_content"] == ""
    assert result["message"] == {
        "content": "",
        "tool_calls": tool_calls,
    }
    assert result["tool_calls"] == tool_calls


def test_generate_answer_passes_tools_to_message_api(monkeypatch):
    captured = {}

    def fake_generate_from_messages(messages, tools=None, tool_choice=None):
        captured["messages"] = messages
        captured["tools"] = tools
        captured["tool_choice"] = tool_choice
        return {"answer": "", "tool_calls": []}

    monkeypatch.setattr(llm_service, "generate_from_messages", fake_generate_from_messages)

    tools = _tool_schema()
    result = llm_service.generate_answer(
        question="question",
        chunks=[],
        messages=[{"role": "user", "content": "question"}],
        tools=tools,
        tool_choice={"type": "function", "function": {"name": "knowledge_search"}},
    )

    assert result == {"answer": "", "tool_calls": []}
    assert captured["tools"] == tools
    assert captured["tool_choice"] == {
        "type": "function",
        "function": {"name": "knowledge_search"},
    }


def test_stream_from_messages_sends_tools_and_parses_tool_call_deltas(monkeypatch):
    _enable_llm(monkeypatch)
    calls = []

    def fake_post(url, headers=None, json=None, timeout=None, stream=False, **kwargs):
        calls.append({"payload": json, "stream": stream})
        return _FakeStreamResponse(
            [
                {
                    "model": "test-model",
                    "choices": [
                        {
                            "delta": {
                                "tool_calls": [
                                    {
                                        "index": 0,
                                        "id": "call_1",
                                        "type": "function",
                                        "function": {
                                            "name": "knowledge_search",
                                            "arguments": "{\"query\":\"rag",
                                        },
                                    }
                                ]
                            },
                            "finish_reason": None,
                        }
                    ],
                },
                {
                    "model": "test-model",
                    "choices": [
                        {
                            "delta": {
                                "tool_calls": [
                                    {
                                        "index": 0,
                                        "function": {
                                            "arguments": " trace\",\"top_k\":5}",
                                        },
                                    }
                                ]
                            },
                            "finish_reason": "tool_calls",
                        }
                    ],
                },
                "[DONE]",
            ]
        )

    monkeypatch.setattr(llm_service.http_client, "post", fake_post)

    events = list(
        llm_service.stream_from_messages(
            [{"role": "user", "content": "search"}],
            tools=_tool_schema(),
            tool_choice="auto",
        )
    )

    assert len(calls) == 1
    assert calls[0]["stream"] is True
    assert calls[0]["payload"]["tools"] == _tool_schema()
    assert calls[0]["payload"]["tool_choice"] == "auto"
    done = events[-1]
    assert done["type"] == "done"
    assert done["answer"] == ""
    assert done["message"] == {
        "content": "",
        "tool_calls": [
            {
                "id": "call_1",
                "type": "function",
                "function": {
                    "name": "knowledge_search",
                    "arguments": "{\"query\":\"rag trace\",\"top_k\":5}",
                },
            }
        ],
    }
    assert done["tool_calls"] == [
        {
            "id": "call_1",
            "type": "function",
            "function": {
                "name": "knowledge_search",
                "arguments": "{\"query\":\"rag trace\",\"top_k\":5}",
            },
        }
    ]
    assert done["stop_reason"] == "tool_calls"
