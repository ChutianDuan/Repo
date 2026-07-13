#!/usr/bin/env python3
"""Benchmark an OpenAI-compatible chat-completions endpoint directly."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import statistics
import sys
import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Iterable, Iterator, Mapping, Optional, Sequence
from urllib.parse import urlparse

try:
    import requests
except ImportError:  # pragma: no cover - exercised by the CLI guard
    requests = None


DEFAULT_BASE_URL = "http://127.0.0.1:9000/v1"
DEFAULT_PROMPT = "请简要介绍 Transformer、Self-Attention、KV Cache 和 MoE。"


@dataclass(frozen=True)
class BenchmarkConfig:
    endpoint: str
    model: str
    api_key: str
    mode: str
    request_count: int
    concurrency: int
    prompt: str
    max_tokens: int
    temperature: float
    timeout_seconds: float


def percentile(values: Sequence[float], percent: int) -> Optional[float]:
    if not values:
        return None
    ordered = sorted(float(value) for value in values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * (percent / 100.0)
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def metric_summary(values: Iterable[float]) -> dict[str, Any]:
    samples = [float(value) for value in values]
    if not samples:
        return {
            "samples": 0,
            "min": None,
            "avg": None,
            "p50": None,
            "p95": None,
            "p99": None,
            "max": None,
        }
    return {
        "samples": len(samples),
        "min": min(samples),
        "avg": statistics.fmean(samples),
        "p50": percentile(samples, 50),
        "p95": percentile(samples, 95),
        "p99": percentile(samples, 99),
        "max": max(samples),
    }


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be greater than zero")
    return parsed


def positive_float(value: str) -> float:
    parsed = float(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be greater than zero")
    return parsed


def non_negative_float(value: str) -> float:
    parsed = float(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("value must be zero or greater")
    return parsed


def chat_completions_endpoint(base_url: str) -> str:
    normalized = str(base_url or "").strip().rstrip("/")
    if not normalized:
        normalized = DEFAULT_BASE_URL
    if normalized.endswith("/chat/completions"):
        return normalized
    return f"{normalized}/chat/completions"


def parse_sse_line(line: str | bytes) -> tuple[Optional[dict[str, Any]], bool]:
    if isinstance(line, bytes):
        line = line.decode("utf-8")
    normalized = line.strip()
    if not normalized or normalized.startswith(":") or not normalized.startswith("data:"):
        return None, False
    payload_text = normalized[5:].strip()
    if payload_text == "[DONE]":
        return None, True
    payload = json.loads(payload_text)
    if not isinstance(payload, dict):
        raise ValueError("SSE data must be a JSON object")
    return payload, False


def _content_delta(payload: Mapping[str, Any]) -> str:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    first = choices[0]
    if not isinstance(first, Mapping):
        return ""
    delta = first.get("delta")
    if not isinstance(delta, Mapping):
        return ""
    content = delta.get("content")
    return content if isinstance(content, str) else ""


def _completion_content(payload: Mapping[str, Any]) -> str:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    first = choices[0]
    if not isinstance(first, Mapping):
        return ""
    message = first.get("message")
    if not isinstance(message, Mapping):
        return ""
    content = message.get("content")
    return content if isinstance(content, str) else ""


def _completion_tokens(payload: Mapping[str, Any]) -> Optional[int]:
    usage = payload.get("usage")
    if not isinstance(usage, Mapping):
        return None
    value = usage.get("completion_tokens")
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)) and value >= 0:
        return int(value)
    return None


def _headers(api_key: str) -> dict[str, str]:
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


def _payload(config: BenchmarkConfig, stream: bool) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": config.model,
        "messages": [{"role": "user", "content": config.prompt}],
        "max_tokens": config.max_tokens,
        "temperature": config.temperature,
        "stream": stream,
    }
    if stream:
        payload["stream_options"] = {"include_usage": True}
    return payload


def _is_loopback_endpoint(endpoint: str) -> bool:
    hostname = (urlparse(endpoint).hostname or "").lower()
    return hostname in {"localhost", "127.0.0.1", "::1"}


@contextmanager
def _post(endpoint: str, **kwargs: Any) -> Iterator[Any]:
    with requests.Session() as session:
        if _is_loopback_endpoint(endpoint):
            session.trust_env = False
        with session.post(endpoint, **kwargs) as response:
            yield response


def _failure_result(
    mode: str,
    request_index: int,
    started_at: float,
    error: str,
    status_code: Optional[int] = None,
) -> dict[str, Any]:
    return {
        "mode": mode,
        "request_index": request_index,
        "success": False,
        "status_code": status_code,
        "error": str(error)[:500],
        "e2e_seconds": max(0.0, time.perf_counter() - started_at),
        "ttft_seconds": None,
        "response_chars": 0,
        "completion_tokens": None,
        "completion_tokens_per_second": None,
    }


def run_nonstream_request(config: BenchmarkConfig, request_index: int) -> dict[str, Any]:
    started_at = time.perf_counter()
    try:
        with _post(
            config.endpoint,
            headers=_headers(config.api_key),
            json=_payload(config, stream=False),
            timeout=config.timeout_seconds,
        ) as response:
            if response.status_code < 200 or response.status_code >= 300:
                return _failure_result(
                    "nonstream",
                    request_index,
                    started_at,
                    f"HTTP {response.status_code}: {response.text[:300]}",
                    response.status_code,
                )
            payload = response.json()
            if not isinstance(payload, dict):
                raise ValueError("response JSON must be an object")
            content = _completion_content(payload)
            if not content:
                raise ValueError("response did not contain assistant content")
            return {
                "mode": "nonstream",
                "request_index": request_index,
                "success": True,
                "status_code": response.status_code,
                "error": None,
                "e2e_seconds": max(0.0, time.perf_counter() - started_at),
                "ttft_seconds": None,
                "response_chars": len(content),
                "completion_tokens": _completion_tokens(payload),
                "completion_tokens_per_second": None,
            }
    except Exception as exc:
        return _failure_result("nonstream", request_index, started_at, str(exc))


def run_stream_request(config: BenchmarkConfig, request_index: int) -> dict[str, Any]:
    started_at = time.perf_counter()
    first_content_at: Optional[float] = None
    response_chars = 0
    completion_tokens: Optional[int] = None
    try:
        with _post(
            config.endpoint,
            headers={**_headers(config.api_key), "Accept": "text/event-stream"},
            json=_payload(config, stream=True),
            timeout=config.timeout_seconds,
            stream=True,
        ) as response:
            if response.status_code < 200 or response.status_code >= 300:
                return _failure_result(
                    "stream",
                    request_index,
                    started_at,
                    f"HTTP {response.status_code}: {response.text[:300]}",
                    response.status_code,
                )
            for line in response.iter_lines(decode_unicode=True):
                payload, done = parse_sse_line(line)
                if done:
                    break
                if payload is None:
                    continue
                token_count = _completion_tokens(payload)
                if token_count is not None:
                    completion_tokens = token_count
                delta = _content_delta(payload)
                if not delta:
                    continue
                if first_content_at is None:
                    first_content_at = time.perf_counter()
                response_chars += len(delta)

        if first_content_at is None or response_chars == 0:
            raise ValueError("stream did not contain a content delta")

        finished_at = time.perf_counter()
        decode_seconds = max(0.0, finished_at - first_content_at)
        token_rate = None
        if completion_tokens is not None and decode_seconds > 0:
            token_rate = completion_tokens / decode_seconds
        return {
            "mode": "stream",
            "request_index": request_index,
            "success": True,
            "status_code": response.status_code,
            "error": None,
            "e2e_seconds": max(0.0, finished_at - started_at),
            "ttft_seconds": max(0.0, first_content_at - started_at),
            "response_chars": response_chars,
            "completion_tokens": completion_tokens,
            "completion_tokens_per_second": token_rate,
        }
    except Exception as exc:
        return _failure_result("stream", request_index, started_at, str(exc))


def build_phase_report(mode: str, results: Sequence[Mapping[str, Any]], duration: float) -> dict[str, Any]:
    successful = [result for result in results if result.get("success")]
    failed = [result for result in results if not result.get("success")]
    ttft_values = [
        float(result["ttft_seconds"])
        for result in successful
        if result.get("ttft_seconds") is not None
    ]
    token_rates = [
        float(result["completion_tokens_per_second"])
        for result in successful
        if result.get("completion_tokens_per_second") is not None
    ]
    return {
        "mode": mode,
        "total_requests": len(results),
        "successful_requests": len(successful),
        "failed_requests": len(failed),
        "success_rate": (len(successful) / len(results)) if results else 0.0,
        "duration_seconds": duration,
        "requests_per_second": (len(results) / duration) if duration > 0 else None,
        "e2e_seconds": metric_summary(
            float(result["e2e_seconds"])
            for result in successful
            if result.get("e2e_seconds") is not None
        ),
        "ttft_seconds": metric_summary(ttft_values) if mode == "stream" else None,
        "response_chars": metric_summary(
            float(result["response_chars"])
            for result in successful
            if result.get("response_chars") is not None
        ),
        "completion_tokens_per_second": (
            metric_summary(token_rates) if mode == "stream" else None
        ),
        "completion_token_samples": sum(
            1 for result in successful if result.get("completion_tokens") is not None
        ),
        "errors": [str(result.get("error") or "unknown error") for result in failed[:10]],
    }


def run_phase(config: BenchmarkConfig, mode: str) -> dict[str, Any]:
    runner = run_stream_request if mode == "stream" else run_nonstream_request
    started_at = time.perf_counter()
    max_workers = min(config.concurrency, config.request_count)
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(runner, config, index)
            for index in range(config.request_count)
        ]
        results = [future.result() for future in futures]
    duration = max(0.0, time.perf_counter() - started_at)
    return build_phase_report(mode, results, duration)


def resolve_config(
    args: argparse.Namespace,
    environ: Optional[Mapping[str, str]] = None,
) -> BenchmarkConfig:
    env = environ if environ is not None else os.environ
    model = str(
        args.model
        or env.get("VLLM_SERVED_MODEL_NAME")
        or env.get("LLM_MODEL")
        or ""
    ).strip()
    if not model:
        raise ValueError(
            "model is required; use --model or set VLLM_SERVED_MODEL_NAME/LLM_MODEL"
        )
    base_url = str(args.base_url or env.get("LLM_BASE_URL") or DEFAULT_BASE_URL)
    api_key = str(env.get("VLLM_API_KEY") or env.get("LLM_API_KEY") or "")
    return BenchmarkConfig(
        endpoint=chat_completions_endpoint(base_url),
        model=model,
        api_key=api_key,
        mode=args.mode,
        request_count=args.request_count,
        concurrency=args.concurrency,
        prompt=args.prompt,
        max_tokens=args.max_tokens,
        temperature=args.temperature,
        timeout_seconds=args.timeout_seconds,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Benchmark a raw OpenAI-compatible vLLM endpoint without the RAG stack."
    )
    parser.add_argument("--mode", choices=("stream", "nonstream", "both"), default="both")
    parser.add_argument("--requests", dest="request_count", type=positive_int, default=20)
    parser.add_argument("--concurrency", type=positive_int, default=5)
    parser.add_argument("--model")
    parser.add_argument("--base-url")
    parser.add_argument("--prompt", default=DEFAULT_PROMPT)
    parser.add_argument("--max-tokens", type=positive_int, default=256)
    parser.add_argument("--temperature", type=non_negative_float, default=0.7)
    parser.add_argument("--timeout-seconds", type=positive_float, default=300.0)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if requests is None:
        parser.error(
            "requests is not installed; install python_rag/requirements.txt in the active environment"
        )
    try:
        config = resolve_config(args)
    except ValueError as exc:
        parser.error(str(exc))

    modes = ("nonstream", "stream") if config.mode == "both" else (config.mode,)
    phases = [run_phase(config, mode) for mode in modes]
    total_requests = sum(int(phase["total_requests"]) for phase in phases)
    successful_requests = sum(int(phase["successful_requests"]) for phase in phases)
    failed_requests = total_requests - successful_requests
    report = {
        "config": {
            "endpoint": config.endpoint,
            "model": config.model,
            "mode": config.mode,
            "requests_per_mode": config.request_count,
            "concurrency": config.concurrency,
            "max_tokens": config.max_tokens,
            "temperature": config.temperature,
            "timeout_seconds": config.timeout_seconds,
            "api_key_configured": bool(config.api_key),
        },
        "summary": {
            "total_requests": total_requests,
            "successful_requests": successful_requests,
            "failed_requests": failed_requests,
            "success_rate": (
                successful_requests / total_requests if total_requests else 0.0
            ),
        },
        "phases": phases,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if successful_requests > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
