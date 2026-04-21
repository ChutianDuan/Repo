import time
from typing import Any, Dict, List

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


def _build_payload(messages: List[Dict[str, str]]) -> Dict[str, Any]:
    return {
        "model": LLM_MODEL,
        "messages": messages,
        "temperature": LLM_TEMPERATURE,
        "max_tokens": LLM_MAX_TOKENS,
        "stream": False,
    }


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

    # 极少数兼容服务可能返回 content=list
    if isinstance(answer, list):
        text_parts = []
        for item in answer:
            if isinstance(item, dict):
                if item.get("type") == "text" and item.get("text"):
                    text_parts.append(str(item["text"]))
            elif item is not None:
                text_parts.append(str(item))
        answer = "\n".join(text_parts)

    answer = str(answer).strip()
    if not answer:
        raise LLMServiceError("llm response answer is empty")

    return {
        "answer": answer,
        "model": resp_json.get("model") or LLM_MODEL,
        "usage": resp_json.get("usage"),
        "finish_reason": first.get("finish_reason"),
    }


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
    payload = _build_payload(messages)

    start_ts = time.time()

    try:
        response = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=LLM_TIMEOUT_SECONDS,
        )
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
