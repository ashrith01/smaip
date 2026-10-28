"""Keyword hook for obvious indirect-prompt-injection markers.

The patterns are fixed and local. They are a Week 1 detector, not a claim
that keyword search is a sufficient defense.
"""


class KeywordHook:
    PATTERNS: tuple[str, ...] = (
        "ignore previous instructions",
        "attacker@evil.example",
        "audit.log",
        "exfiltrate",
    )

    def hits(self, text: str) -> list[str]:
        lowered = text.lower()
        return [pattern for pattern in self.PATTERNS if pattern in lowered]

    def flagged(self, text: str) -> bool:
        return bool(self.hits(text))
