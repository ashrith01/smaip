"""Completion engines.

mock is the default. The Hugging Face and vLLM engines named ``hf-stub`` and
``vllm-stub`` are stubs: they return a deterministic string and do not import
or download weights.

``SMAIP_HF_CPU=1`` opts into a separate CPU backend for one small model.
That backend lives in another module and is imported only when the flag is
on. ``smaip-mock`` stays the mock engine either way. CI leaves the flag unset.
"""

import os

from smaip.errors import HfCpuDisabled, UnknownEngine

HF_CPU_MODEL_ID = "Qwen/Qwen2.5-0.5B-Instruct"
_HF_CPU_KEYS = frozenset({"hf-cpu", HF_CPU_MODEL_ID.lower()})
_CACHED: tuple[bool, "Engine"] | None = None


class Engine:
    name = "mock"

    def complete(self, messages: list[dict]) -> str:
        raise NotImplementedError


def _last_content(messages: list[dict]) -> str:
    for message in reversed(messages):
        content = message.get("content", "")
        if isinstance(content, str) and content:
            return content
    return ""


class MockEngine(Engine):
    name = "mock"

    def complete(self, messages: list[dict]) -> str:
        return "mock:" + _last_content(messages)


class HfStubEngine(Engine):
    name = "hf"

    def complete(self, messages: list[dict]) -> str:
        prompt = _last_content(messages)
        return (
            "[hf-stub] backend=huggingface weights=not-loaded "
            f"download=refused prompt_chars={len(prompt)}"
        )


class VllmStubEngine(Engine):
    name = "vllm"

    def complete(self, messages: list[dict]) -> str:
        prompt = _last_content(messages)
        return (
            "[vllm-stub] backend=vllm weights=not-loaded "
            f"download=refused prompt_chars={len(prompt)}"
        )


def hf_cpu_requested() -> bool:
    return os.environ.get("SMAIP_HF_CPU", "").strip().lower() in {"1", "true", "yes"}


def default_engine() -> Engine:
    """Mock engine, unless ``SMAIP_HF_CPU`` selects the optional CPU backend."""

    global _CACHED
    flag = hf_cpu_requested()
    if _CACHED is not None and _CACHED[0] == flag:
        return _CACHED[1]
    if not flag:
        engine: Engine = MockEngine()
    else:
        from smaip.serving.hf_cpu import HfCpuEngine

        engine = HfCpuEngine()
    _CACHED = (flag, engine)
    return engine


def engine_for_model(model: str) -> Engine:
    key = model.strip().lower()
    if key in {"mock", "smaip-mock"}:
        return MockEngine()
    if key in {"hf", "hf-stub", "huggingface"}:
        return HfStubEngine()
    if key in {"vllm", "vllm-stub"}:
        return VllmStubEngine()
    if key in {"hf-local", "vllm-local"}:
        from smaip.serving.open_model import configured_engine

        return configured_engine(key)
    if key in _HF_CPU_KEYS:
        if not hf_cpu_requested():
            raise HfCpuDisabled(
                "HF CPU backend is off. Set SMAIP_HF_CPU=1 to load "
                f"{HF_CPU_MODEL_ID} on CPU. No weights were downloaded."
            )
        from smaip.serving.hf_cpu import HfCpuEngine

        return HfCpuEngine()
    raise UnknownEngine(
        f"unknown engine for model {model!r}; Week 1 accepts mock, hf-stub, and vllm-stub"
    )
