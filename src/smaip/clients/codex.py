"""External coding-model client.

Week 1 refuses the network. Tests and local runs never need an API key.
"""

from smaip.errors import NetworkRefused


class CodexClient:
    """Stub client. Every method that would talk to a hosted Codex API raises."""

    def complete(self, prompt: str, **kwargs: object) -> str:
        del prompt, kwargs
        raise NetworkRefused(
            "Codex client stub refuses network access. Use the mock engine."
        )

    def chat(self, messages: list[dict], **kwargs: object) -> str:
        del messages, kwargs
        raise NetworkRefused(
            "Codex client stub refuses network access. Use the mock engine."
        )

    def request(self, method: str, url: str, **kwargs: object) -> str:
        del method, url, kwargs
        raise NetworkRefused(
            "Codex client stub refuses network access. Use the mock engine."
        )
