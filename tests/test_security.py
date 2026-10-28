"""Week 2 API hygiene: auth, limits, request ids, and redacted logs."""

import json
import logging

from fastapi.testclient import TestClient

from smaip.privacy.redact import EMAIL_TOKEN, PHONE_TOKEN
from smaip.serving.app import create_app
from smaip.serving.engines import Engine
from smaip.serving.ratelimit import RateLimiter
from smaip.serving.settings import ServingSettings


class CountingEngine(Engine):
    name = "mock"

    def __init__(self) -> None:
        self.calls = 0

    def complete(self, messages: list[dict]) -> str:
        self.calls += 1
        return "counted:" + messages[-1]["content"]


def _body(content: str = "hello", **extra) -> dict:
    payload = {
        "model": "smaip-mock",
        "messages": [{"role": "user", "content": content}],
    }
    payload.update(extra)
    return payload


def _secured(**overrides) -> ServingSettings:
    values = {
        "api_keys": ("test-key", "other-key"),
        "require_api_key": True,
        "rate_limit_per_minute": 60,
    }
    values.update(overrides)
    return ServingSettings(**values)


def _client(settings: ServingSettings | None = None, engine: Engine | None = None) -> TestClient:
    return TestClient(create_app(engine=engine, settings=settings))


def test_health_and_metrics_stay_open_when_inference_requires_a_key():
    client = _client(_secured())
    assert client.get("/health").status_code == 200
    assert client.get("/metrics").status_code == 200
    denied = client.post("/v1/chat/completions", json=_body())
    assert denied.status_code == 401
    assert denied.json()["detail"]["type"] == "auth_error"
    assert "test-key" not in denied.text


def test_bearer_and_x_api_key_both_authorize():
    client = _client(_secured())
    bearer = client.post(
        "/v1/chat/completions",
        json=_body("hello"),
        headers={"Authorization": "Bearer test-key"},
    )
    header = client.post(
        "/v1/chat/completions",
        json=_body("hello"),
        headers={"X-API-Key": "other-key"},
    )
    assert bearer.status_code == 200
    assert header.status_code == 200
    assert bearer.json()["smaip"] == {"cache": "miss", "engine": "mock"}
    assert header.json()["smaip"]["cache"] == "hit"


def test_wrong_key_is_401_and_counts_an_auth_failure():
    client = _client(_secured())
    response = client.post(
        "/v1/chat/completions",
        json=_body(),
        headers={"Authorization": "bearer not-the-key"},
    )
    assert response.status_code == 401
    metrics = client.get("/metrics").json()
    assert metrics["auth_failures"] == 1
    assert metrics["requests_total"] == 0
    prom = client.get("/metrics?format=prom").text
    assert "smaip_auth_failures_total 1" in prom
    assert "smaip_rate_limited_total 0" in prom
    assert "smaip_payload_rejected_total 0" in prom


def test_rate_limit_is_per_key_and_does_not_call_the_engine():
    engine = CountingEngine()
    client = _client(
        _secured(rate_limit_per_minute=1),
        engine=engine,
    )
    headers_a = {"Authorization": "Bearer test-key"}
    headers_b = {"X-API-Key": "other-key"}
    assert client.post("/v1/chat/completions", json=_body("a"), headers=headers_a).status_code == 200
    limited = client.post("/v1/chat/completions", json=_body("a"), headers=headers_a)
    assert limited.status_code == 429
    assert limited.json()["detail"]["type"] == "rate_limit"
    assert limited.headers["retry-after"] == "60"
    assert client.post("/v1/chat/completions", json=_body("b"), headers=headers_b).status_code == 200
    assert engine.calls == 2
    metrics = client.get("/metrics").json()
    assert metrics["rate_limited"] == 1
    assert metrics["requests_total"] == 2


def test_rate_limiter_expires_the_window_without_sleeping():
    limiter = RateLimiter(2, window_seconds=60)
    assert limiter.allow("a", now=0)
    assert limiter.allow("a", now=1)
    assert limiter.allow("a", now=2) is False
    assert limiter.allow("b", now=2) is True
    assert limiter.allow("a", now=61) is True


def test_zero_limit_disables_throttling():
    client = _client(_secured(rate_limit_per_minute=0))
    headers = {"Authorization": "Bearer test-key"}
    for _ in range(3):
        response = client.post("/v1/chat/completions", json=_body("n"), headers=headers)
        assert response.status_code == 200


def test_body_and_message_limits():
    client = _client(
        ServingSettings(max_body_bytes=80, max_message_chars=8000, max_messages=2)
    )
    too_big = client.post(
        "/v1/chat/completions",
        content=b'{"model":"smaip-mock","messages":[{"role":"user","content":"' + b"A" * 200 + b'"}]}',
        headers={"content-type": "application/json"},
    )
    assert too_big.status_code == 413
    assert too_big.json()["detail"]["type"] == "request_too_large"

    long_text = client.post("/v1/chat/completions", json=_body("x" * 50))
    # 50 chars is under the char cap but the JSON body is over 80 bytes.
    assert long_text.status_code == 413

    chars = _client(ServingSettings(max_message_chars=4, max_messages=1))
    over_chars = chars.post(
        "/v1/chat/completions",
        json=_body("hello ada@example.com"),
    )
    assert over_chars.status_code == 400
    assert over_chars.json()["detail"]["type"] == "invalid_request"
    audit = json.dumps(chars.app.state.request_audit.entries)
    assert "ada@example.com" not in audit
    assert EMAIL_TOKEN in audit

    too_many = chars.post(
        "/v1/chat/completions",
        json={
            "model": "smaip-mock",
            "messages": [
                {"role": "user", "content": "one"},
                {"role": "user", "content": "two"},
            ],
        },
    )
    assert too_many.status_code == 400
    metrics = chars.get("/metrics").json()
    assert metrics["payload_rejected"] >= 2


def test_schema_rejects_bad_role_temperature_and_stream():
    client = _client(ServingSettings())
    bad_role = client.post(
        "/v1/chat/completions",
        json={
            "model": "smaip-mock",
            "messages": [{"role": "nope", "content": "write ada@example.com"}],
        },
    )
    assert bad_role.status_code == 422
    assert "ada@example.com" not in bad_role.text
    leaked = client.post(
        "/v1/chat/completions",
        json={
            "model": "smaip-mock",
            "messages": [{"role": "user", "content": {"email": "ada@example.com"}}],
        },
    )
    assert leaked.status_code == 422
    assert "ada@example.com" not in leaked.text
    assert EMAIL_TOKEN in leaked.text

    assert client.post("/v1/chat/completions", json=_body("hi", temperature=3)).status_code == 422
    assert client.post("/v1/chat/completions", json=_body("hi", temperature=-0.1)).status_code == 422
    assert client.post("/v1/chat/completions", json=_body("hi", temperature=2)).status_code == 200
    streamed = client.post("/v1/chat/completions", json=_body("hi", stream=True))
    assert streamed.status_code == 400
    assert streamed.json()["detail"]["type"] == "unsupported"
    empty = client.post(
        "/v1/chat/completions",
        json={"model": "smaip-mock", "messages": [{"role": "user", "content": ""}]},
    )
    assert empty.status_code == 422


def test_request_id_is_echoed_or_generated():
    client = _client(ServingSettings())
    echoed = client.get("/health", headers={"X-Request-ID": "req-123.abc"})
    assert echoed.headers["x-request-id"] == "req-123.abc"
    generated = client.get("/health", headers={"X-Request-ID": "bad id"})
    assert generated.headers["x-request-id"] != "bad id"
    assert generated.headers["x-request-id"].isalnum()
    chat = client.post(
        "/v1/chat/completions",
        json=_body("hello"),
        headers={"X-Request-ID": "chat-1"},
    )
    assert chat.headers["x-request-id"] == "chat-1"
    assert chat.json()["smaip"] == {"cache": "miss", "engine": "mock"}
    matched = [
        entry
        for entry in client.app.state.request_audit.entries
        if entry.get("request_id") == "chat-1" and entry.get("event") == "chat.completion"
    ]
    assert matched
    assert matched[0]["engine"] == "mock"


def test_redacted_echo_and_access_log_hide_contact_details(caplog):
    caplog.set_level(logging.INFO, logger="smaip.access")
    client = _client(_secured())
    content = "reach ada@example.com or 415-555-0199"
    response = client.post(
        "/v1/chat/completions",
        json=_body(content, redact_echo=True),
        headers={"Authorization": "Bearer test-key", "X-Request-ID": "pii-1"},
    )
    assert response.status_code == 200
    echo = response.json()["smaip"]["redacted_echo"]
    assert echo == [{"role": "user", "content": f"reach {EMAIL_TOKEN} or {PHONE_TOKEN}"}]
    # The mock engine still completes from the original prompt.
    assert "ada@example.com" in response.json()["choices"][0]["message"]["content"]
    audit = json.dumps(client.app.state.request_audit.entries)
    assert "ada@example.com" not in audit
    assert "415-555-0199" not in audit
    assert "test-key" not in audit
    assert EMAIL_TOKEN in audit
    assert "pii-1" in audit
    assert "ada@example.com" not in caplog.text
    assert "test-key" not in caplog.text
    assert EMAIL_TOKEN in caplog.text


def test_settings_load_from_the_environment(monkeypatch):
    monkeypatch.setenv("SMAIP_API_KEYS", "alpha, beta")
    monkeypatch.setenv("SMAIP_RATE_LIMIT_PER_MINUTE", "4")
    monkeypatch.setenv("SMAIP_MAX_MESSAGE_CHARS", "12")
    loaded = ServingSettings.load()
    assert loaded.api_keys == ("alpha", "beta")
    assert loaded.require_api_key is True
    assert loaded.rate_limit_per_minute == 4
    assert loaded.max_message_chars == 12

    monkeypatch.setenv("SMAIP_REQUIRE_API_KEY", "false")
    opened = ServingSettings.load()
    assert opened.require_api_key is False
    monkeypatch.delenv("SMAIP_REQUIRE_API_KEY")

    client = TestClient(create_app())
    denied = client.post("/v1/chat/completions", json=_body("hello"))
    assert denied.status_code == 401
    allowed = client.post(
        "/v1/chat/completions",
        json=_body("hello"),
        headers={"X-API-Key": "beta"},
    )
    assert allowed.status_code == 200


def test_hf_stub_still_refuses_downloads_behind_auth():
    client = _client(_secured())
    response = client.post(
        "/v1/chat/completions",
        json=_body("hello", model="hf-stub"),
        headers={"Authorization": "Bearer test-key"},
    )
    assert response.status_code == 200
    text = response.json()["choices"][0]["message"]["content"]
    assert "download=refused" in text
    assert response.json()["smaip"]["engine"] == "hf"


def test_anonymous_bucket_when_auth_is_off():
    client = _client(ServingSettings(require_api_key=False, rate_limit_per_minute=1))
    assert client.post("/v1/chat/completions", json=_body("one")).status_code == 200
    assert client.post("/v1/chat/completions", json=_body("two")).status_code == 429
