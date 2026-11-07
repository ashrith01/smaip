"""Residual-stream activations for probe training.

The real backend is a Hugging Face causal LM. The default id is
``Qwen/Qwen2.5-3B-Instruct``. ``SMAIP_PROBE_MODEL`` or ``--model`` overrides
it. The CPU path uses ``Qwen/Qwen2.5-0.5B-Instruct``. Weights load on the
first forward, not at import.

``mock`` is a deterministic stand-in used when CI must not download a model.
It is a hashed bag of tokens, not a hidden state. Reports name the backend
so a mock AUROC is not read as a Qwen result.

Layer indexes are transformer blocks. The vector is the residual stream
after that block (``hidden_states[layer + 1]``). The linear probe pools the
last non-padding token. The activation probe mean-pools every non-padding
token. One forward returns both.
"""

import hashlib
import os
from functools import lru_cache
from typing import Any

from smaip.errors import ProbeBackendUnavailable


DEFAULT_MODEL = "Qwen/Qwen2.5-3B-Instruct"
CPU_MODEL = "Qwen/Qwen2.5-0.5B-Instruct"
MOCK_DIM = 32
MOCK_LAYERS = (0, 1, 2, 3)
_HF: dict[tuple[str, str, str], tuple[Any, Any]] = {}


def resolve_model(explicit: str | None = None) -> str:
    if explicit and explicit.strip():
        return explicit.strip()
    env = os.environ.get("SMAIP_PROBE_MODEL", "").strip()
    if env:
        return env
    return DEFAULT_MODEL


def resolve_backend(explicit: str | None = None) -> str:
    choice = (explicit or os.environ.get("SMAIP_PROBE_BACKEND") or "auto").strip().lower()
    if choice == "mock":
        return "mock"
    if choice == "hf":
        _require_hf()
        return "hf"
    if choice == "auto":
        if _hf_importable():
            return "hf"
        raise ProbeBackendUnavailable(
            "No Hugging Face backend is installed, so activations were not collected "
            "and no weights were downloaded. Install it with "
            '`python3 -m pip install -e ".[hf]"` or set SMAIP_PROBE_BACKEND=mock '
            "for the CPU smoke path."
        )
    raise ProbeBackendUnavailable(f"unknown probe backend {choice!r}")


def resolve_device(explicit: str | None, backend: str) -> str:
    if backend == "mock":
        return "cpu"
    choice = (explicit or os.environ.get("SMAIP_PROBE_DEVICE") or "auto").strip().lower()
    if choice in {"", "auto"}:
        return "cuda" if cuda_available() else "cpu"
    if choice == "cpu":
        return "cpu"
    if choice == "cuda":
        if not cuda_available():
            raise ProbeBackendUnavailable(
                "CUDA was requested but torch.cuda.is_available() is false. "
                "No model weights were downloaded."
            )
        return "cuda"
    raise ProbeBackendUnavailable(f"unknown probe device {choice!r}")


def parse_layers(explicit: str | None, *, available: int | None = None) -> list[int] | None:
    """Parse a comma-separated layer list.

    ``None`` means every block once the model (or the mock) has reported
    how many blocks it has. An empty string is that default.
    """

    raw = explicit
    if raw is None:
        raw = os.environ.get("SMAIP_PROBE_LAYERS", "")
    raw = raw.strip().lower()
    if raw in {"", "all"}:
        if available is None:
            return None
        return list(range(available))
    layers: list[int] = []
    for piece in raw.split(","):
        piece = piece.strip()
        if not piece:
            continue
        try:
            layer = int(piece)
        except ValueError as exc:
            raise ProbeBackendUnavailable(f"bad probe layer {piece!r}") from exc
        if layer < 0 or (available is not None and layer >= available):
            raise ProbeBackendUnavailable(
                f"probe layer {layer} is outside 0..{None if available is None else available - 1}"
            )
        layers.append(layer)
    if not layers:
        raise ProbeBackendUnavailable("probe layer list is empty")
    return layers


def cuda_available() -> bool:
    try:
        import torch
    except ImportError:
        return False
    return bool(torch.cuda.is_available())


def mock_activation(text: str, layer: int, pooling: str, dim: int = MOCK_DIM) -> list[float]:
    """Hashed token features. Last-token and mean pooling disagree on purpose."""

    if pooling not in {"last", "mean"}:
        raise ValueError(f"unknown pooling {pooling!r}")
    tokens = text.lower().split() or [""]
    chosen = tokens[-1:] if pooling == "last" else tokens
    vector = [0.0] * dim
    for token in chosen:
        digest = hashlib.sha256(f"{layer}:{token}".encode()).digest()
        index = digest[0] % dim
        sign = 1.0 if digest[1] % 2 == 0 else -1.0
        vector[index] += sign
    if pooling == "mean":
        scale = float(len(chosen))
        vector = [value / scale for value in vector]
    return vector


def embed_text(
    text: str,
    *,
    model_id: str,
    layer: int,
    pooling: str,
    backend: str,
    device: str,
    dtype_name: str | None = None,
) -> list[float]:
    if backend == "mock":
        return mock_activation(text, layer, pooling)
    if backend != "hf":
        raise ProbeBackendUnavailable(f"unknown probe backend {backend!r}")
    if pooling not in {"last", "mean"}:
        raise ValueError(f"unknown pooling {pooling!r}")
    pools = _compute_pools(text, model_id, device, dtype_name or _dtype_name_for(device), _max_length())
    try:
        return list(pools[pooling][layer])
    except KeyError as exc:
        raise ProbeBackendUnavailable(f"probe layer {layer} is outside this model") from exc


@lru_cache(maxsize=64)
def _compute_pools(text: str, model_id: str, device: str, dtype_name: str, max_length: int) -> dict:
    """Share one forward between both probes; bound retained per-text vectors."""
    _require_hf()
    import torch

    model, tokenizer = _load_hf(model_id, device, dtype_name)
    rendered = _render(tokenizer, text)
    encoded = tokenizer(
        rendered,
        return_tensors="pt",
        truncation=True,
        max_length=max_length,
    )
    encoded = {key: value.to(device) for key, value in encoded.items()}
    with torch.no_grad():
        output = model(**encoded, output_hidden_states=True, use_cache=False)
    return {
        pooling: {
            layer: _pool_hidden(output.hidden_states, encoded["attention_mask"], layer, pooling)
            for layer in range(len(output.hidden_states) - 1)
        }
        for pooling in ("last", "mean")
    }


def clear_pool_cache() -> None:
    _compute_pools.cache_clear()


def preload_backend(model_id: str, backend: str, device: str, dtype_name: str) -> None:
    if backend == "hf":
        _load_hf(model_id, device, dtype_name)
    elif backend != "mock":
        raise ProbeBackendUnavailable(f"unknown probe backend {backend!r}")


def release_cached_model() -> None:
    _HF.clear()
    clear_pool_cache()
    import gc

    gc.collect()
    try:
        import torch
    except ImportError:
        return
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


def _dtype_name_for(device: str) -> str:
    return "float16" if device == "cuda" else "float32"


def collect(
    records: list,
    *,
    model_id: str,
    backend: str,
    device: str,
    layers: list[int],
) -> list[dict]:
    """One row per record: both poolings at every requested layer."""

    if backend == "mock":
        rows = []
        for record in records:
            rows.append(_package(record, layers, backend="mock"))
        return rows
    _require_hf()
    import torch

    model, tokenizer = _load_hf(model_id, device)
    hidden_count = _residual_blocks(model)
    for layer in layers:
        if layer < 0 or layer >= hidden_count:
            raise ProbeBackendUnavailable(
                f"probe layer {layer} is outside 0..{hidden_count - 1} for {model_id}"
            )
    batch_size = _batch_size()
    rows: list[dict] = []
    for start in range(0, len(records), batch_size):
        chunk = records[start : start + batch_size]
        rendered = [_render(tokenizer, record.text) for record in chunk]
        encoded = tokenizer(
            rendered,
            return_tensors="pt",
            truncation=True,
            padding=True,
            max_length=_max_length(),
        )
        encoded = {key: value.to(device) for key, value in encoded.items()}
        with torch.no_grad():
            output = model(**encoded, output_hidden_states=True, use_cache=False)
        mask = encoded["attention_mask"]
        for row_index, record in enumerate(chunk):
            pooled: dict[str, dict[str, list[float]]] = {"last": {}, "mean": {}}
            for layer in layers:
                hidden = output.hidden_states[layer + 1][row_index]
                row_mask = mask[row_index]
                pooled["last"][str(layer)] = _masked_last(hidden, row_mask)
                pooled["mean"][str(layer)] = _masked_mean(hidden, row_mask)
            rows.append(
                {
                    "id": record.id,
                    "label": record.label,
                    "split": record.split,
                    "origin": record.origin,
                    "layers": pooled,
                }
            )
    return rows


def model_layer_count(model_id: str, backend: str, device: str) -> int:
    if backend == "mock":
        return len(MOCK_LAYERS)
    _require_hf()
    model, _tokenizer = _load_hf(model_id, device)
    return _residual_blocks(model)


def _package(record, layers: list[int], *, backend: str) -> dict:
    pooled: dict[str, dict[str, list[float]]] = {"last": {}, "mean": {}}
    for layer in layers:
        if backend == "mock":
            pooled["last"][str(layer)] = mock_activation(record.text, layer, "last")
            pooled["mean"][str(layer)] = mock_activation(record.text, layer, "mean")
        else:
            raise ProbeBackendUnavailable(backend)
    return {
        "id": record.id,
        "label": record.label,
        "split": record.split,
        "origin": record.origin,
        "layers": pooled,
    }


def _pool_hidden(hidden_states, mask, layer: int, pooling: str) -> list[float]:
    if layer + 1 >= len(hidden_states):
        raise ProbeBackendUnavailable(
            f"probe layer {layer} is outside this model (blocks={len(hidden_states) - 1})"
        )
    hidden = hidden_states[layer + 1][0]
    if pooling == "last":
        return _masked_last(hidden, mask[0])
    if pooling == "mean":
        return _masked_mean(hidden, mask[0])
    raise ValueError(f"unknown pooling {pooling!r}")


def _masked_last(hidden, mask) -> list[float]:
    import torch

    positions = torch.nonzero(mask, as_tuple=False)
    index = int(positions[-1]) if len(positions) else 0
    vector = hidden[index].detach().float().cpu()
    return [float(value) for value in vector.tolist()]


def _masked_mean(hidden, mask) -> list[float]:
    import torch

    weights = mask.to(hidden.dtype).unsqueeze(-1)
    total = weights.sum().clamp_min(1.0)
    vector = (hidden * weights).sum(dim=0) / total
    vector = vector.detach().float().cpu()
    return [float(value) for value in vector.tolist()]


def _residual_blocks(model) -> int:
    config = model.config
    for name in ("num_hidden_layers", "n_layer"):
        value = getattr(config, name, None)
        if isinstance(value, int) and value > 0:
            return value
    raise ProbeBackendUnavailable("the model config does not name a layer count")


def _load_hf(model_id: str, device: str, dtype_name: str | None = None):
    chosen = dtype_name or _dtype_name_for(device)
    key = (model_id, device, chosen)
    cached = _HF.get(key)
    if cached is not None:
        return cached
    _require_hf()
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(model_id)
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    if chosen not in {"float16", "float32"}:
        raise ProbeBackendUnavailable(f"unknown probe dtype {chosen!r}")
    dtype = getattr(torch, chosen)
    model = _from_pretrained(
        AutoModelForCausalLM,
        model_id,
        dtype,
        low_cpu_mem_usage=True,
    )
    model.to(device)
    model.eval()
    _HF[key] = (model, tokenizer)
    return model, tokenizer


def _from_pretrained(cls, model_id: str, dtype, **kwargs):
    """Prefer ``dtype``; fall back to ``torch_dtype`` on older transformers."""

    try:
        return cls.from_pretrained(model_id, dtype=dtype, **kwargs)
    except TypeError:
        return cls.from_pretrained(model_id, torch_dtype=dtype, **kwargs)


def _render(tokenizer, text: str) -> str:
    messages = [{"role": "user", "content": text}]
    try:
        return tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=False,
        )
    except (ValueError, TypeError):
        return text


def _require_hf() -> None:
    if not _hf_importable():
        raise ProbeBackendUnavailable(
            "The Hugging Face extra is not installed, so no weights were downloaded. "
            'Install it with `python3 -m pip install -e ".[hf]"`.'
        )


def _hf_importable() -> bool:
    try:
        import torch  # noqa: F401
        import transformers  # noqa: F401
    except ImportError:
        return False
    return True


def _max_length() -> int:
    raw = os.environ.get("SMAIP_PROBE_MAX_LENGTH", "512").strip()
    try:
        value = int(raw)
    except ValueError as exc:
        raise ProbeBackendUnavailable("SMAIP_PROBE_MAX_LENGTH must be an integer") from exc
    if value < 8:
        raise ProbeBackendUnavailable("SMAIP_PROBE_MAX_LENGTH is too small")
    return value


def _batch_size() -> int:
    raw = os.environ.get("SMAIP_PROBE_BATCH", "4").strip()
    try:
        value = int(raw)
    except ValueError as exc:
        raise ProbeBackendUnavailable("SMAIP_PROBE_BATCH must be an integer") from exc
    return max(1, value)
