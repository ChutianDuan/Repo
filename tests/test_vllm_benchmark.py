import importlib.util
from pathlib import Path
import sys

import pytest


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "vllm_benchmark.py"
SPEC = importlib.util.spec_from_file_location("vllm_benchmark", SCRIPT_PATH)
vllm_benchmark = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = vllm_benchmark
SPEC.loader.exec_module(vllm_benchmark)


class FakeResponse:
    def __init__(self, status_code=200, payload=None, text="", lines=None):
        self.status_code = status_code
        self._payload = payload
        self.text = text
        self._lines = list(lines or [])

    def json(self):
        return self._payload

    def iter_lines(self, decode_unicode=False):
        del decode_unicode
        return iter(self._lines)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False


def build_config(**overrides):
    values = {
        "endpoint": "http://127.0.0.1:9000/v1/chat/completions",
        "model": "test-model",
        "api_key": "",
        "mode": "both",
        "request_count": 2,
        "concurrency": 1,
        "prompt": "hello",
        "max_tokens": 16,
        "temperature": 0.0,
        "timeout_seconds": 5.0,
    }
    values.update(overrides)
    return vllm_benchmark.BenchmarkConfig(**values)


def test_percentile_uses_linear_interpolation():
    assert vllm_benchmark.percentile([], 95) is None
    assert vllm_benchmark.percentile([2.0], 95) == 2.0
    assert vllm_benchmark.percentile([1.0, 3.0], 50) == 2.0


def test_parse_sse_line_handles_delta_done_and_comments():
    payload, done = vllm_benchmark.parse_sse_line(
        'data: {"choices":[{"delta":{"content":"hi"}}]}'
    )
    assert done is False
    assert payload["choices"][0]["delta"]["content"] == "hi"
    assert vllm_benchmark.parse_sse_line("data: [DONE]") == (None, True)
    assert vllm_benchmark.parse_sse_line(": keep-alive") == (None, False)


def test_parser_rejects_non_positive_request_count():
    parser = vllm_benchmark.build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["--requests", "0"])


def test_resolve_config_requires_model():
    args = vllm_benchmark.build_parser().parse_args([])
    with pytest.raises(ValueError, match="model is required"):
        vllm_benchmark.resolve_config(args, environ={})


def test_resolve_config_uses_cli_then_environment():
    args = vllm_benchmark.build_parser().parse_args(
        ["--model", "cli-model", "--base-url", "http://model.test/v1"]
    )
    config = vllm_benchmark.resolve_config(
        args,
        environ={
            "LLM_MODEL": "env-model",
            "LLM_BASE_URL": "http://ignored.test/v1",
            "VLLM_API_KEY": "secret",
        },
    )
    assert config.model == "cli-model"
    assert config.endpoint == "http://model.test/v1/chat/completions"
    assert config.api_key == "secret"


@pytest.mark.parametrize(
    ("endpoint", "expected"),
    [
        ("http://localhost:9000/v1/chat/completions", True),
        ("http://127.0.0.1:9000/v1/chat/completions", True),
        ("http://[::1]:9000/v1/chat/completions", True),
        ("https://model.example/v1/chat/completions", False),
    ],
)
def test_loopback_endpoint_detection(endpoint, expected):
    assert vllm_benchmark._is_loopback_endpoint(endpoint) is expected


def test_nonstream_non_2xx_is_reported_without_raising(monkeypatch):
    monkeypatch.setattr(
        vllm_benchmark,
        "_post",
        lambda *args, **kwargs: FakeResponse(status_code=503, text="unavailable"),
    )
    result = vllm_benchmark.run_nonstream_request(build_config(), 0)
    assert result["success"] is False
    assert result["status_code"] == 503
    assert "HTTP 503" in result["error"]


def test_stream_collects_ttft_chars_and_optional_usage(monkeypatch):
    lines = [
        'data: {"choices":[{"delta":{"content":"hel"}}]}',
        'data: {"choices":[{"delta":{"content":"lo"}}]}',
        'data: {"choices":[],"usage":{"completion_tokens":2}}',
        "data: [DONE]",
    ]
    monkeypatch.setattr(
        vllm_benchmark,
        "_post",
        lambda *args, **kwargs: FakeResponse(lines=lines),
    )
    result = vllm_benchmark.run_stream_request(build_config(), 0)
    assert result["success"] is True
    assert result["ttft_seconds"] is not None
    assert result["response_chars"] == 5
    assert result["completion_tokens"] == 2


def test_stream_report_keeps_token_rate_empty_without_provider_usage():
    result = {
        "success": True,
        "e2e_seconds": 1.0,
        "ttft_seconds": 0.1,
        "response_chars": 12,
        "completion_tokens": None,
        "completion_tokens_per_second": None,
    }
    report = vllm_benchmark.build_phase_report("stream", [result], duration=1.0)
    assert report["completion_token_samples"] == 0
    assert report["completion_tokens_per_second"]["samples"] == 0


@pytest.mark.parametrize(
    ("successful_requests", "expected_exit_code"),
    [(1, 0), (0, 1)],
)
def test_main_exit_code_depends_on_any_success(
    monkeypatch,
    capsys,
    successful_requests,
    expected_exit_code,
):
    phase = {
        "mode": "stream",
        "total_requests": 2,
        "successful_requests": successful_requests,
        "failed_requests": 2 - successful_requests,
    }
    monkeypatch.setattr(vllm_benchmark, "run_phase", lambda config, mode: phase)
    exit_code = vllm_benchmark.main(
        ["--mode", "stream", "--model", "test-model", "--requests", "2"]
    )
    assert exit_code == expected_exit_code
    report = capsys.readouterr().out
    assert '"failed_requests"' in report
    assert "secret" not in report
