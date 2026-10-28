"""Codex client stub."""

import socket

import pytest

from smaip.clients import CodexClient
from smaip.errors import NetworkRefused


def test_codex_complete_refuses_network(monkeypatch):
    calls = []

    def record(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("socket opened")

    monkeypatch.setattr(socket, "create_connection", record)
    with pytest.raises(NetworkRefused, match="network"):
        CodexClient().complete("write a function")
    assert calls == []


def test_codex_chat_and_request_refuse_network():
    client = CodexClient()
    with pytest.raises(NetworkRefused):
        client.chat([{"role": "user", "content": "hi"}])
    with pytest.raises(NetworkRefused):
        client.request("POST", "https://api.openai.com/v1/responses")
