import json

from python_rag.app.modules.llm import service as llm_service


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


def _chat_payload(content, finish_reason="length", usage=None, model="test-model"):
    return {
        "model": model,
        "choices": [
            {
                "message": {"content": content},
                "finish_reason": finish_reason,
            }
        ],
        "usage": usage,
    }


def _enable_llm(monkeypatch, max_rounds):
    monkeypatch.setattr(llm_service, "LLM_ENABLE", True)
    monkeypatch.setattr(llm_service, "LLM_PROVIDER", "openai_compatible")
    monkeypatch.setattr(llm_service, "LLM_BASE_URL", "http://llm.test/v1")
    monkeypatch.setattr(llm_service, "LLM_MODEL", "test-model")
    monkeypatch.setattr(llm_service, "LLM_MAX_GENERATION_ROUNDS", max_rounds)


def test_build_payload_uses_configured_generation_options(monkeypatch):
    monkeypatch.setattr(llm_service, "LLM_MODEL", "mimo-v2.5-pro")
    monkeypatch.setattr(llm_service, "LLM_MAX_TOKENS", 1024)
    monkeypatch.setattr(llm_service, "LLM_TOKEN_LIMIT_FIELD", "max_completion_tokens")
    monkeypatch.setattr(llm_service, "LLM_TEMPERATURE", 1.0)
    monkeypatch.setattr(llm_service, "LLM_TOP_P", 0.95)
    monkeypatch.setattr(llm_service, "LLM_FREQUENCY_PENALTY", 0.0)
    monkeypatch.setattr(llm_service, "LLM_PRESENCE_PENALTY", 0.0)

    payload = llm_service._build_payload(
        [{"role": "user", "content": "please introduce yourself"}],
        stream=False,
    )

    assert payload["model"] == "mimo-v2.5-pro"
    assert payload["max_completion_tokens"] == 1024
    assert "max_tokens" not in payload
    assert payload["temperature"] == 1.0
    assert payload["top_p"] == 0.95
    assert payload["frequency_penalty"] == 0.0
    assert payload["presence_penalty"] == 0.0


def test_generate_from_messages_loops_until_model_done_marker(monkeypatch):
    _enable_llm(monkeypatch, max_rounds=3)
    calls = []
    responses = [
        _chat_payload(
            "第一段",
            finish_reason="length",
            usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        ),
        _chat_payload(
            "第二段\n[[LLM_DONE]]",
            finish_reason="stop",
            usage={"prompt_tokens": 8, "completion_tokens": 4, "total_tokens": 12},
        ),
    ]

    def fake_post(url, headers=None, json=None, timeout=None, **kwargs):
        calls.append({"url": url, "payload": json, "timeout": timeout})
        return _FakeResponse(responses.pop(0))

    monkeypatch.setattr(llm_service.http_client, "post", fake_post)

    result = llm_service.generate_from_messages([
        {"role": "system", "content": "系统提示"},
        {"role": "user", "content": "问题"},
    ])

    assert result["answer"] == "第一段\n第二段"
    assert result["usage"] == {
        "prompt_tokens": 18,
        "completion_tokens": 9,
        "total_tokens": 27,
    }
    assert result["rounds"] == 2
    assert result["max_rounds"] == 3
    assert result["stopped_by_model"] is True
    assert result["stop_reason"] == "done_marker"
    assert len(calls) == 2
    assert "[[LLM_DONE]]" in calls[0]["payload"]["messages"][0]["content"]
    assert calls[1]["payload"]["messages"][-2] == {"role": "assistant", "content": "第一段"}


def test_generate_from_messages_stops_at_max_rounds(monkeypatch):
    _enable_llm(monkeypatch, max_rounds=2)
    calls = []
    responses = [
        _chat_payload("第一段", finish_reason="length"),
        _chat_payload("第二段", finish_reason="length"),
    ]

    def fake_post(url, headers=None, json=None, timeout=None, **kwargs):
        calls.append(json)
        return _FakeResponse(responses.pop(0))

    monkeypatch.setattr(llm_service.http_client, "post", fake_post)

    result = llm_service.generate_from_messages([
        {"role": "user", "content": "问题"},
    ])

    assert result["answer"] == "第一段\n第二段"
    assert result["rounds"] == 2
    assert result["max_rounds"] == 2
    assert result["stopped_by_model"] is False
    assert result["stop_reason"] == "max_rounds"
    assert len(calls) == 2

def _stream_delta(content=None, finish_reason=None, usage=None, model="test-model"):
    delta = {}
    if content is not None:
        delta["content"] = content
    return {
        "model": model,
        "choices": [
            {
                "delta": delta,
                "finish_reason": finish_reason,
            }
        ],
        "usage": usage,
    }


def test_stream_from_messages_loops_and_filters_done_marker(monkeypatch):
    _enable_llm(monkeypatch, max_rounds=3)
    calls = []
    responses = [
        _FakeStreamResponse([
            _stream_delta("第一段"),
            _stream_delta(finish_reason="length"),
            "[DONE]",
        ]),
        _FakeStreamResponse([
            _stream_delta("第二段\n[[LLM"),
            _stream_delta("_DONE]]", finish_reason="stop"),
            "[DONE]",
        ]),
    ]

    def fake_post(url, headers=None, json=None, timeout=None, stream=False, **kwargs):
        calls.append({"payload": json, "stream": stream})
        return responses.pop(0)

    monkeypatch.setattr(llm_service.http_client, "post", fake_post)

    events = list(llm_service.stream_from_messages([
        {"role": "user", "content": "问题"},
    ]))

    deltas = [event["delta"] for event in events if event["type"] == "delta"]
    done = events[-1]

    assert "[[LLM_DONE]]" not in "".join(deltas)
    assert done["type"] == "done"
    assert done["answer"] == "第一段第二段"
    assert done["rounds"] == 2
    assert done["max_rounds"] == 3
    assert done["stopped_by_model"] is True
    assert done["stop_reason"] == "done_marker"
    assert len(calls) == 2
    assert all(call["stream"] is True for call in calls)
