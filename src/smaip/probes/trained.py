"""Trained logistic probes over residual-stream activations.

``kind="linear"`` is the last-token probe (the LP-only defense).
``kind="activation"`` is the mean-pooled probe (the probe-only defense).
Both score a text by running the same backend that collected its training
vectors, then applying the saved weights. The Week 1 phrase stubs stay in
place when these files are absent.
"""

import json
import os
from collections import OrderedDict
from pathlib import Path

from smaip.probes.activations import _max_length, embed_text, preload_backend, resolve_device
from smaip.probes.logistic import predict_proba, standardize


class TrainedProbe:
    # The fit used individual document bodies, not generated digest arguments.
    matches_training_documents = True

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
        self._cache: OrderedDict[tuple, float] = OrderedDict()

    def score_device(self) -> str:
        return resolve_device(os.environ.get("SMAIP_PROBE_DEVICE") or "auto", self.backend)

    def embedding_dtype(self) -> str:
        # Preserve collection precision when moving a saved probe across devices.
        return "float16" if self.device == "cuda" else "float32"

    def preload(self) -> None:
        preload_backend(self.model_id, self.backend, self.score_device(), self.embedding_dtype())

    def clear_score_cache(self) -> None:
        self._cache.clear()

    def cached_score(self, text: str) -> float | None:
        return self._cache.get(self._cache_key(text))

    def _cache_key(self, text: str) -> tuple:
        return (self.score_device(), self.embedding_dtype(), _max_length(), text)

    @classmethod
    def load(cls, path: Path) -> "TrainedProbe":
        payload = json.loads(path.read_text(encoding="utf-8"))
        return cls(payload)

    def score(self, text: str) -> float:
        key = self._cache_key(text)
        cached = self._cache.get(key)
        if cached is not None:
            self._cache.move_to_end(key)
            return cached
        vector = embed_text(
            text,
            model_id=self.model_id,
            layer=self.layer,
            pooling=self.pooling,
            backend=self.backend,
            device=key[0],
            dtype_name=key[1],
        )
        scaled, _mean, _std = standardize([vector], self.mean, self.std)
        probability = predict_proba(scaled[0], self.weights, self.bias)
        self._cache[key] = probability
        if len(self._cache) > 256:
            self._cache.popitem(last=False)
        return probability

    def flagged(self, text: str) -> bool:
        return self.score(text) >= self.threshold
