"""API, engines, and the exact-prompt cache."""

import socket
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from smaip.serving.app import create_app
from smaip.serving.engines import Engine


class CountingEngine(Engine):
    name = "mock"

    def __init__(self) -> None:
        self.calls = 0

    def complete(self, messages: list[dict]) -> str:
        self.calls += 1
        return "counted:" + messages[-1]["content"]


def _body(content: str, model: str = "smaip-mock", temperature: float | None = None) -> dict:
    payload: dict = {
        "model": model,
        "messages": [{"role": "user", "content": content}],
    }
    if temperature is not None:
        payload["temperature"] = temperature
    return payload


def test_health_ok():
    client = TestClient(create_app())
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["engine_default"] == "mock"
    assert body["gpu"] is False


def test_metrics_start_at_zero():
    client = TestClient(create_app())
    body = client.get("/metrics").json()
    assert body["requests_total"] == 0
    assert body["cache_hits"] == 0
    assert body["cache_misses"] == 0
    assert body["cache_hit_rate"] == 0.0


def test_chat_mock_default_shape():
    client = TestClient(create_app())
    response = client.post("/v1/chat/completions", json=_body("hello"))
    assert response.status_code == 200
    body = response.json()
    assert body["object"] == "chat.completion"
    assert body["choices"][0]["message"]["content"] == "mock:hello"
    assert body["smaip"] == {"cache": "miss", "engine": "mock"}
    assert body["usage"]["total_tokens"] >= 1


def test_exact_cache_hit_and_metrics():
    client = TestClient(create_app())
    first = client.post("/v1/chat/completions", json=_body("hello")).json()
    second = client.post("/v1/chat/completions", json=_body("hello")).json()
    assert first["smaip"]["cache"] == "miss"
    assert second["smaip"]["cache"] == "hit"
    assert first["choices"][0]["message"]["content"] == second["choices"][0]["message"]["content"]
    metrics = client.get("/metrics").json()
    assert metrics["cache_hits"] == 1
    assert metrics["cache_misses"] == 1
    assert metrics["cache_hit_rate"] == 0.5
    assert metrics["requests_total"] == 2


def test_exact_cache_whitespace_is_a_miss():
    client = TestClient(create_app())
    client.post("/v1/chat/completions", json=_body("hello"))
    response = client.post("/v1/chat/completions", json=_body("hello "))
    assert response.json()["smaip"]["cache"] == "miss"
    assert response.json()["choices"][0]["message"]["content"] == "mock:hello "


def test_temperature_does_not_split_the_exact_prompt():
    client = TestClient(create_app())
    client.post("/v1/chat/completions", json=_body("hello", temperature=0.0))
    response = client.post("/v1/chat/completions", json=_body("hello", temperature=0.9))
    assert response.json()["smaip"]["cache"] == "hit"


def test_role_change_is_a_miss():
    client = TestClient(create_app())
    client.post("/v1/chat/completions", json=_body("hello"))
    response = client.post(
        "/v1/chat/completions",
        json={"model": "smaip-mock", "messages": [{"role": "system", "content": "hello"}]},
    )
    assert response.json()["smaip"]["cache"] == "miss"


def test_engine_is_not_called_on_a_hit():
    engine = CountingEngine()
    client = TestClient(create_app(engine=engine))
    client.post("/v1/chat/completions", json=_body("hello"))
    client.post("/v1/chat/completions", json=_body("hello"))
    assert engine.calls == 1


def test_hf_stub_refuses_download_in_the_body():
    client = TestClient(create_app())
    response = client.post("/v1/chat/completions", json=_body("hello", model="hf-stub"))
    text = response.json()["choices"][0]["message"]["content"]
    assert response.json()["smaip"]["engine"] == "hf"
    assert "hf-stub" in text
    assert "download=refused" in text


def test_vllm_stub_refuses_download_in_the_body():
    client = TestClient(create_app())
    response = client.post("/v1/chat/completions", json=_body("hello", model="vllm-stub"))
    text = response.json()["choices"][0]["message"]["content"]
    assert response.json()["smaip"]["engine"] == "vllm"
    assert "vllm-stub" in text
    assert "download=refused" in text


def test_stub_engines_do_not_open_sockets(monkeypatch):
    def boom(*args, **kwargs):
        raise AssertionError("socket opened")

    monkeypatch.setattr(socket, "create_connection", boom)
    client = TestClient(create_app())
    for model in ("hf-stub", "vllm-stub", "smaip-mock"):
        response = client.post("/v1/chat/completions", json=_body("hello", model=model))
        assert response.status_code == 200


def test_stub_sources_do_not_import_weight_libraries():
    source = Path(__import__("smaip.serving.engines", fromlist=["engines"]).__file__).read_text()
    for banned in (
        "transformers",
        "huggingface_hub",
        "import torch",
        "import vllm",
        "from vllm",
        "urllib.request",
        "import httpx",
        "import requests",
    ):
        assert banned not in source


def test_unknown_engine_is_400():
    client = TestClient(create_app())
    response = client.post(
        "/v1/chat/completions",
        json=_body("hello", model="Qwen/Qwen2.5-3B"),
    )
    assert response.status_code == 400
    assert "unknown" in response.text.lower()


def test_empty_messages_are_400():
    client = TestClient(create_app())
    response = client.post(
        "/v1/chat/completions",
        json={"model": "smaip-mock", "messages": []},
    )
    assert response.status_code == 400


def test_mock_and_hf_do_not_share_a_cache_entry():
    client = TestClient(create_app())
    client.post("/v1/chat/completions", json=_body("hello", model="smaip-mock"))
    response = client.post("/v1/chat/completions", json=_body("hello", model="hf-stub"))
    assert response.json()["smaip"]["cache"] == "miss"


def test_prometheus_metrics():
    client = TestClient(create_app())
    client.post("/v1/chat/completions", json=_body("hello"))
    response = client.get("/metrics?format=prom")
    assert response.status_code == 200
    assert "smaip_cache_hits" in response.text
    assert "smaip_cache_misses 1" in response.text
