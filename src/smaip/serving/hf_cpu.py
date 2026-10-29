"""Optional CPU backend for one small open model.

This module is imported only after ``SMAIP_HF_CPU`` is set. Importing
``smaip.serving.engines`` does not import it, and constructing the engine
does not download weights. Weights load on the first ``complete`` call.

The model is ``Qwen/Qwen2.5-0.5B-Instruct``. Generation is forced onto CPU.
CI does not set the flag and does not install this extra.
"""

import os

from smaip.errors import HfCpuDisabled
from smaip.serving.engines import HF_CPU_MODEL_ID, Engine


def _flag_on() -> bool:
    return os.environ.get("SMAIP_HF_CPU", "").strip().lower() in {"1", "true", "yes"}


class HfCpuEngine(Engine):
    name = "hf-cpu"
    MODEL_ID = HF_CPU_MODEL_ID

    def __init__(self) -> None:
        if not _flag_on():
            raise HfCpuDisabled(
                "HF CPU backend is off. Set SMAIP_HF_CPU=1 to load "
                f"{self.MODEL_ID} on CPU. No weights were downloaded."
            )
        self.model = None
        self.tokenizer = None

    def complete(self, messages: list[dict]) -> str:
        self._load()
        assert self.model is not None
        assert self.tokenizer is not None
        import torch

        chat = [
            {
                "role": str(message.get("role") or "user"),
                "content": str(message.get("content") or ""),
            }
            for message in messages
            if isinstance(message, dict)
        ]
        if not chat:
            chat = [{"role": "user", "content": ""}]
        try:
            prompt = self.tokenizer.apply_chat_template(
                chat,
                tokenize=False,
                add_generation_prompt=True,
            )
        except (ValueError, TypeError):
            prompt = chat[-1]["content"]
        inputs = self.tokenizer(prompt, return_tensors="pt")
        inputs = {key: value.to("cpu") for key, value in inputs.items()}
        with torch.no_grad():
            output = self.model.generate(
                **inputs,
                max_new_tokens=64,
                do_sample=False,
                pad_token_id=self.tokenizer.eos_token_id,
            )
        new_tokens = output[0, inputs["input_ids"].shape[-1] :]
        return self.tokenizer.decode(new_tokens, skip_special_tokens=True)

    def _load(self) -> None:
        if self.model is not None:
            return
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        tokenizer = AutoTokenizer.from_pretrained(self.MODEL_ID)
        if tokenizer.pad_token_id is None:
            tokenizer.pad_token = tokenizer.eos_token
        model = AutoModelForCausalLM.from_pretrained(
            self.MODEL_ID,
            torch_dtype=torch.float32,
            device_map=None,
            low_cpu_mem_usage=True,
        )
        model.to("cpu")
        model.eval()
        self.tokenizer = tokenizer
        self.model = model
