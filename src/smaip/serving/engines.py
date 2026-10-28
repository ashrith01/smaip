"""Completion engines.

mock is the default. The Hugging Face and vLLM engines are stubs: they return
a deterministic string and do not import or download weights.
"""

from smaip.errors import UnknownEngine


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


def engine_for_model(model: str) -> Engine:
    key = model.strip().lower()
    if key in {"mock", "smaip-mock"}:
        return MockEngine()
    if key in {"hf", "hf-stub", "huggingface"}:
        return HfStubEngine()
    if key in {"vllm", "vllm-stub"}:
        return VllmStubEngine()
    raise UnknownEngine(
        f"unknown engine for model {model!r}; Week 1 accepts mock, hf-stub, and vllm-stub"
    )
