"""Optional CPU backend. The marked test is skipped unless SMAIP_RUN_HF=1."""

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from smaip.errors import HfCpuDisabled
from smaip.serving.app import create_app
from smaip.serving.engines import HF_CPU_MODEL_ID, MockEngine, default_engine, engine_for_model


def test_default_engine_stays_on_the_mock(monkeypatch):
    monkeypatch.delenv("SMAIP_HF_CPU", raising=False)
    monkeypatch.delenv("SMAIP_RUN_HF", raising=False)
    assert isinstance(default_engine(), MockEngine)
    assert isinstance(engine_for_model("smaip-mock"), MockEngine)
    assert HF_CPU_MODEL_ID == "Qwen/Qwen2.5-0.5B-Instruct"


def test_hf_cpu_model_is_rejected_without_the_flag_and_does_not_import_weights(monkeypatch):
    monkeypatch.delenv("SMAIP_HF_CPU", raising=False)
    sys.modules.pop("smaip.serving.hf_cpu", None)
    with pytest.raises(HfCpuDisabled, match="No weights were downloaded"):
        engine_for_model("hf-cpu")
    with pytest.raises(HfCpuDisabled, match="Qwen/Qwen2.5-0.5B-Instruct"):
        engine_for_model(HF_CPU_MODEL_ID)
    assert "smaip.serving.hf_cpu" not in sys.modules
    assert "torch" not in sys.modules
    assert "transformers" not in sys.modules


def test_named_mock_stays_mock_when_the_flag_is_on(monkeypatch):
    monkeypatch.setenv("SMAIP_HF_CPU", "1")
    assert isinstance(engine_for_model("smaip-mock"), MockEngine)


def test_chat_rejects_the_cpu_model_without_downloading(monkeypatch):
    monkeypatch.delenv("SMAIP_HF_CPU", raising=False)
    client = TestClient(create_app())
    response = client.post(
        "/v1/chat/completions",
        json={"model": "hf-cpu", "messages": [{"role": "user", "content": "hello"}]},
    )
    assert response.status_code == 400
    assert "No weights were downloaded" in response.text
    assert "torch" not in sys.modules


def test_cpu_backend_source_forces_cpu_and_is_not_imported_by_engines():
    source = Path(engine_for_model.__code__.co_filename).read_text(encoding="utf-8")
    assert "import torch" not in source
    assert "transformers" not in source
    from smaip.serving import hf_cpu

    text = Path(hf_cpu.__file__).read_text(encoding="utf-8")
    assert HF_CPU_MODEL_ID in text
    assert 'model.to("cpu")' in text
    assert 'device_map="auto"' not in text
    assert "import torch" in text
    assert "from transformers import AutoModelForCausalLM, AutoTokenizer" in text


@pytest.mark.hf
def test_qwen_05b_completes_on_cpu(monkeypatch):
    monkeypatch.setenv("SMAIP_HF_CPU", "1")
    try:
        import torch
        from smaip.serving.hf_cpu import HfCpuEngine
    except ImportError as exc:
        pytest.fail(f'Install the hf extra before SMAIP_RUN_HF=1 (`pip install -e ".[hf]"`): {exc}')
    engine = HfCpuEngine()
    assert engine.model is None
    text = engine.complete([{"role": "user", "content": "Reply with the single word pong."}])
    assert isinstance(text, str) and text.strip()
    assert engine.model is not None
    assert next(engine.model.parameters()).device.type == "cpu"
    assert torch.device("cpu").type == "cpu"
