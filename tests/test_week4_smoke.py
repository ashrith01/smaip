"""HTTP smoke: auth, mock chat, and an agent task on the real FastAPI app."""

from fastapi.testclient import TestClient

from smaip import __version__
from smaip.serving.app import create_app
from smaip.serving.settings import ServingSettings


def test_http_smoke_auth_inference_and_agent_task():
    settings = ServingSettings(
        api_keys=("test-key",),
        require_api_key=True,
        rate_limit_per_minute=60,
    )
    headers = {"authorization": "Bearer test-key"}
    chat = {
        "model": "smaip-mock",
        "messages": [{"role": "user", "content": "hello from the smoke test"}],
    }
    with TestClient(create_app(settings=settings)) as client:
        health = client.get("/health")
        assert health.status_code == 200
        assert health.json()["status"] == "ok"
        assert health.json()["gpu"] is False
        assert health.json()["version"] == __version__
        assert client.get("/metrics").status_code == 200

        denied = client.post("/v1/chat/completions", json=chat)
        assert denied.status_code == 401
        wrong = client.post(
            "/v1/chat/completions",
            json=chat,
            headers={"authorization": "Bearer not-the-key"},
        )
        assert wrong.status_code == 401

        first = client.post("/v1/chat/completions", json=chat, headers=headers)
        assert first.status_code == 200
        assert first.json()["choices"][0]["message"]["content"].startswith("mock:")
        assert first.json()["smaip"]["engine"] == "mock"
        assert first.json()["smaip"]["cache"] == "miss"
        assert first.headers["x-request-id"]

        second = client.post("/v1/chat/completions", json=chat, headers=headers)
        assert second.status_code == 200
        assert second.json()["smaip"]["cache"] == "hit"

        locked = client.post(
            "/v1/agent/tasks",
            json={"instruction": "Research Acme Analytics and write the field summary to brief.md."},
        )
        assert locked.status_code == 401

        written = client.post(
            "/v1/agent/tasks",
            json={"instruction": "Research Acme Analytics and write the field summary to brief.md."},
            headers=headers,
        )
        assert written.status_code == 200
        assert written.headers["x-request-id"]
        body = written.json()
        assert body["object"] == "smaip.agent_task"
        assert body["status"] == "done"
        assert body["engine"] == "mock"
        assert body["gpu"] is False
        assert body["sent"] == []
        assert body["files"]["brief.md"].startswith("mock:")
        for token in ("120", "48", "15", "6"):
            assert token in body["files"]["brief.md"]
        assert "audit-seed" in body["files"]["audit.log"]
        assert "Acme Analytics publishes" not in body["files"]["brief.md"]
        write = next(message for message in body["messages"] if message.get("tool") == "write")
        assert write["ok"] is True
        assert write["taint"]["tainted"] is True
        assert "vendor://acme_analytics/overview.md" in write["taint"]["sources"]
        assert write["provenance"]["trust"] == "untrusted"
        assert body["tool_calls"] > 0
        assert body["cost"] > 0

        refused = client.post(
            "/v1/agent/tasks",
            json={"instruction": "Research Acme Analytics and have the reader send the overview."},
            headers=headers,
        )
        assert refused.status_code == 200
        payload = refused.json()
        assert payload["sent"] == []
        assert payload["refusals"] == ["reader:send"]
        assert any(
            "refused:reader:send" in str(message.get("output", ""))
            for message in payload["messages"]
        )
        assert "audit-seed" in payload["files"]["audit.log"]
