import json
import time
from typing import Any, Dict, Generator, List, Optional

import requests

from python_rag.config import (
    LLM_API_KEY,
    LLM_MODEL,
    LLM_TEMPERATURE,
    LLM_MAX_TOKENS,
    LLM_ENABLE,
    LLM_PROVIDER,
    LLM_BASE_URL,
    LLM_TIMEOUT_SECONDS,
)


class LLMServiceError(Exception):
    pass


def _build_headers() -> Dict[str, str]:
    headers = {
        "Content-Type": "application/json",
    }
    if LLM_API_KEY:
        headers["Authorization"] = "Bearer %s" % LLM_API_KEY
    return headers


def _build_payload(messages: List[Dict[str, str]], stream: bool = False) -> Dict[str, Any]:
    return {
        "model": LLM_MODEL,
        "messages": messages,
        "temperature": LLM_TEMPERATURE,
        "max_tokens": LLM_MAX_TOKENS,
        "stream": stream,
    }


def _normalize_content_parts(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        text_parts = []
        for item in value:
            if isinstance(item, dict):
                if item.get("type") in ("text", "output_text") and item.get("text"):
                    text_parts.append(str(item["text"]))
                elif item.get("type") == "input_text" and item.get("text"):
                    text_parts.append(str(item["text"]))
            elif item is not None:
                text_parts.append(str(item))
        return "".join(text_parts)
    return str(value)


def _extract_answer(resp_json: Dict[str, Any]) -> Dict[str, Any]:
    choices = resp_json.get("choices") or []
    if not choices:
        raise LLMServiceError("llm response missing choices")

    first = choices[0] or {}
    message = first.get("message") or {}
    answer = message.get("content")

    # 兼容部分 OpenAI-compatible 服务
    if answer is None:
        answer = first.get("text")

    if answer is None:
        raise LLMServiceError("llm response missing answer content")

    answer = _normalize_content_parts(answer).strip()
    if not answer:
        raise LLMServiceError("llm response answer is empty")

    return {
        "answer": answer,
        "model": resp_json.get("model") or LLM_MODEL,
        "usage": resp_json.get("usage"),
        "finish_reason": first.get("finish_reason"),
    }


def _flush_sse_event_lines(event_lines: List[str]) -> Optional[str]:
    if not event_lines:
        return None

    data_lines = []
    for line in event_lines:
        if line.startswith("data:"):
            data_lines.append(line[5:].lstrip())

    if not data_lines:
        return None
    return "\n".join(data_lines)


def _iter_sse_data(response: requests.Response) -> Generator[str, None, None]:
    event_lines: List[str] = []

    for raw_line in response.iter_lines(decode_unicode=True):
        if raw_line is None:
            continue

        line = raw_line.rstrip("\r")
        if line == "":
            payload = _flush_sse_event_lines(event_lines)
            event_lines = []
            if payload is not None:
                yield payload
            continue

        if line.startswith(":"):
            continue

        event_lines.append(line)

    payload = _flush_sse_event_lines(event_lines)
    if payload is not None:
        yield payload


def _extract_stream_delta(chunk_json: Dict[str, Any]) -> str:
    choices = chunk_json.get("choices") or []
    if not choices:
        return ""

    first = choices[0] or {}
    delta = first.get("delta")
    if isinstance(delta, dict):
        if delta.get("content") is not None:
            return _normalize_content_parts(delta.get("content"))
        if delta.get("reasoning_content") is not None:
            return _normalize_content_parts(delta.get("reasoning_content"))

    if first.get("text") is not None:
        return _normalize_content_parts(first.get("text"))

    message = first.get("message")
    if isinstance(message, dict) and message.get("content") is not None:
        return _normalize_content_parts(message.get("content"))

    return ""


def generate_from_messages(messages: List[Dict[str, str]]) -> Dict[str, Any]:
    if not LLM_ENABLE:
        raise LLMServiceError("LLM service is disabled by config")

    if LLM_PROVIDER != "openai_compatible":
        raise LLMServiceError("unsupported LLM provider: %s" % LLM_PROVIDER)

    if not LLM_BASE_URL:
        raise LLMServiceError("LLM_BASE_URL is not configured")

    if not LLM_MODEL:
        raise LLMServiceError("LLM_MODEL is not configured")

    url = LLM_BASE_URL + "/chat/completions"
    headers = _build_headers()
    payload = _build_payload(messages, stream=False)

    start_ts = time.time()

    try:
        response = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=LLM_TIMEOUT_SECONDS,
        )
    except requests.Timeout as e:
        raise LLMServiceError("llm request timed out: %s" % str(e))
    except requests.RequestException as e:
        raise LLMServiceError("llm request failed: %s" % str(e))

    if response.status_code >= 400:
        text = response.text[:1000]
        raise LLMServiceError(
            "llm http error status=%s body=%s" % (response.status_code, text)
        )

    try:
        resp_json = response.json()
    except ValueError:
        raise LLMServiceError("llm response is not valid json: %s" % response.text[:1000])

    result = _extract_answer(resp_json)
    result["latency_ms"] = int((time.time() - start_ts) * 1000)
    return result


def stream_from_messages(messages: List[Dict[str, str]]) -> Generator[Dict[str, Any], None, None]:
    if not LLM_ENABLE:
        raise LLMServiceError("LLM service is disabled by config")

    if LLM_PROVIDER != "openai_compatible":
        raise LLMServiceError("unsupported LLM provider: %s" % LLM_PROVIDER)

    if not LLM_BASE_URL:
        raise LLMServiceError("LLM_BASE_URL is not configured")

    if not LLM_MODEL:
        raise LLMServiceError("LLM_MODEL is not configured")

    url = LLM_BASE_URL + "/chat/completions"
    headers = _build_headers()
    payload = _build_payload(messages, stream=True)

    start_ts = time.time()
    first_delta_ts = None
    answer_parts: List[str] = []
    usage = None
    finish_reason = None
    model = LLM_MODEL

    try:
        with requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=(10, LLM_TIMEOUT_SECONDS),
            stream=True,
        ) as response:
            if response.status_code >= 400:
                text = response.text[:1000]
                raise LLMServiceError(
                    "llm http error status=%s body=%s" % (response.status_code, text)
                )

            for payload_text in _iter_sse_data(response):
                if payload_text == "[DONE]":
                    break

                try:
                    chunk_json = json.loads(payload_text)
                except ValueError:
                    raise LLMServiceError(
                        "llm stream chunk is not valid json: %s" % payload_text[:500]
                    )

                if chunk_json.get("model"):
                    model = chunk_json["model"]
                if chunk_json.get("usage") is not None:
                    usage = chunk_json.get("usage")

                choices = chunk_json.get("choices") or []
                if choices:
                    finish_reason = choices[0].get("finish_reason") or finish_reason

                delta_text = _extract_stream_delta(chunk_json)
                if not delta_text:
                    continue

                if first_delta_ts is None:
                    first_delta_ts = time.time()

                answer_parts.append(delta_text)
                yield {
                    "type": "delta",
                    "delta": delta_text,
                    "model": model,
                }
    except requests.Timeout as e:
        raise LLMServiceError("llm request timed out: %s" % str(e))
    except requests.RequestException as e:
        raise LLMServiceError("llm request failed: %s" % str(e))

    answer = "".join(answer_parts).strip()
    if not answer:
        raise LLMServiceError("llm stream produced empty answer")

    yield {
        "type": "done",
        "answer": answer,
        "model": model,
        "usage": usage,
        "finish_reason": finish_reason,
        "latency_ms": int((time.time() - start_ts) * 1000),
        "ttft_ms": int((first_delta_ts - start_ts) * 1000) if first_delta_ts else None,
    }


def generate_answer(
    question: str,
    chunks: List[Dict[str, Any]],
    messages: List[Dict[str, str]],
) -> Dict[str, Any]:
    """
    question/chunks 暂时保留在签名里，后续可用于埋点、重试策略、provider routing。
    当前真实调用只依赖 messages。
    """
    _ = question
    _ = chunks
    return generate_from_messages(messages)


def stream_answer(
    question: str,
    chunks: List[Dict[str, Any]],
    messages: List[Dict[str, str]],
) -> Generator[Dict[str, Any], None, None]:
    _ = question
    _ = chunks
    yield from stream_from_messages(messages)
