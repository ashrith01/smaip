"""Trained logistic probes over residual-stream activations.

``kind="linear"`` is the last-token probe (the LP-only defense).
``kind="activation"`` is the mean-pooled probe (the probe-only defense).
Both score a text by running the same backend that collected its training
vectors, then applying the saved weights. The Week 1 phrase stubs stay in
place when these files are absent.
"""

import json
from pathlib import Path

from smaip.probes.activations import embed_text
from smaip.probes.logistic import predict_proba, standardize


class TrainedProbe:
    def __init__(self, payload: dict) -> None:
        self.kind = str(payload["kind"])
        self.model_id = str(payload["model_id"])
        self.backend = str(payload["backend"])
        self.device = str(payload.get("device") or "cpu")
        self.pooling = str(payload["pooling"])
        self.layer = int(payload["layer"])
        self.threshold = float(payload["threshold"])
        self.dim = int(payload["dim"])
        self.mean = [float(value) for value in payload["mean"]]
        self.std = [float(value) for value in payload["std"]]
        self.weights = [float(value) for value in payload["weights"]]
        self.bias = float(payload["bias"])
        self.metrics = payload.get("metrics") or {}
        self.layer_sweep = list(payload.get("layer_sweep") or [])
        self.tpr_target = float(payload.get("tpr_target") or 0.95)
        self._cache: dict[str, float] = {}

    @classmethod
    def load(cls, path: Path) -> "TrainedProbe":
        payload = json.loads(path.read_text(encoding="utf-8"))
        return cls(payload)

    def score(self, text: str) -> float:
        cached = self._cache.get(text)
        if cached is not None:
            return cached
        vector = embed_text(
            text,
            model_id=self.model_id,
            layer=self.layer,
            pooling=self.pooling,
            backend=self.backend,
            device=self.device,
        )
        scaled, _mean, _std = standardize([vector], self.mean, self.std)
        probability = predict_proba(scaled[0], self.weights, self.bias)
        self._cache[text] = probability
        return probability

    def flagged(self, text: str) -> bool:
        return self.score(text) >= self.threshold
