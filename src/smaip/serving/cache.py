"""Exact-prompt cache.

The key is the engine name plus the message transcript, role and content,
character for character. Sampling parameters are not part of the prompt.
"""

from threading import Lock


class ExactPromptCache:
    def __init__(self, max_entries: int = 1024) -> None:
        self.max_entries = max_entries
        self._store: dict[str, str] = {}
        self._order: list[str] = []
        self.hits = 0
        self.misses = 0
        self._lock = Lock()

    @staticmethod
    def prompt_key(engine: str, messages: list[dict]) -> str:
        parts: list[str] = []
        for message in messages:
            role = str(message.get("role", ""))
            content = message.get("content", "")
            if not isinstance(content, str):
                raise ValueError("prompt content must be a string")
            parts.append(role + "\x1f" + content)
        return engine + "\x1e" + "\x1e".join(parts)

    def get(self, key: str) -> str | None:
        with self._lock:
            if key not in self._store:
                self.misses += 1
                return None
            self.hits += 1
            return self._store[key]

    def put(self, key: str, value: str) -> None:
        with self._lock:
            if key in self._store:
                self._store[key] = value
                return
            self._store[key] = value
            self._order.append(key)
            while len(self._order) > self.max_entries:
                oldest = self._order.pop(0)
                self._store.pop(oldest, None)
