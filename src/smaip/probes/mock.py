"""Default activation probe. No weights, no downloads."""


class MockActivationProbe:
    """Scores a fixed set of injection markers that the keyword and linear probes ignore."""

    MARKERS: tuple[str, ...] = (
        "[[sys]]",
        "override safety",
        "begin_payload",
        "do not tell the user",
    )
    THRESHOLD = 0.25

    def score(self, text: str) -> float:
        lowered = text.lower()
        hits = sum(1 for marker in self.MARKERS if marker in lowered)
        return hits / len(self.MARKERS)

    def flagged(self, text: str) -> bool:
        return self.score(text) >= self.THRESHOLD
