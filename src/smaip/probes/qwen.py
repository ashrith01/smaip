"""Real activation probe placeholder.

Constructing this class is the error. Week 1 never downloads Qwen weights.
"""

from smaip.errors import ProbeWeightsUnavailable


class QwenActivationProbe:
    MODEL_ID = "Qwen/Qwen2.5-3B"

    def __init__(self) -> None:
        raise ProbeWeightsUnavailable(
            "QwenActivationProbe refuses to load "
            f"{self.MODEL_ID}. Week 1 does not download model weights. "
            "Use MockActivationProbe."
        )

    def score(self, text: str) -> float:
        raise ProbeWeightsUnavailable(
            f"QwenActivationProbe refuses to score with {self.MODEL_ID}."
        )
