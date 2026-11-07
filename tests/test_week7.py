"""Week 7 probe pipeline. The marked HF test lives at the bottom and is skipped in CI."""

import ast
import json
import subprocess
from pathlib import Path

import pytest

from smaip.errors import ProbeBackendUnavailable, ProbeWeightsUnavailable
from smaip.gateway.gateway import Gateway
from smaip.probes.activations import mock_activation, parse_layers, resolve_backend, resolve_model
from smaip.probes.dataset import assign_splits, load_corpus, load_tool_outputs, prepare_records
from smaip.probes.linear import LinearProbe
from smaip.probes.logistic import auroc, predict_proba, standardize, threshold_at_tpr, train_logistic
from smaip.probes.mock import MockActivationProbe
from smaip.probes.qwen import QwenActivationProbe
from smaip.probes.registry import load_activation_defense, load_linear_defense
from smaip.probes.trained import TrainedProbe
from smaip.eval.week7 import render_results, run_week7
from smaip.serving.benchmark import run_benchmark

ROOT = Path(__file__).resolve().parents[1]


def test_corpus_is_original_labeled_and_split_is_deterministic():
    tools = load_tool_outputs()
    assert {item.label for item in tools} == {0, 1}
    assert len(tools) >= 20
    stub_linear = LinearProbe()
    stub_probe = MockActivationProbe()
    for record in tools:
        assert record.origin == "tool"
        assert stub_linear.flagged(record.text) is False
        assert stub_probe.flagged(record.text) is False
    corpus = load_corpus()
    origins = {item.origin for item in corpus}
    assert origins == {"tool", "week5", "week6"}
    assert any(item.label == 1 and item.origin == "week5" for item in corpus)
    assert any(item.label == 0 and item.origin == "week6" for item in corpus)
    first = assign_splits(corpus)
    second = assign_splits(corpus)
    assert [(item.id, item.split) for item in first] == [(item.id, item.split) for item in second]
    for split in ("train", "val", "test"):
        labels = {item.label for item in first if item.split == split}
        assert labels == {0, 1}
    tiny = prepare_records("tiny")
    full = prepare_records("full")
    assert len(tiny) < len(full)
    assert {item.split for item in tiny} == {"train", "val", "test"}


def test_logistic_separates_a_line_and_reports_fpr_at_tpr():
    rows: list[list[float]] = []
    labels: list[int] = []
    for _ in range(30):
        rows.append([2.0, -0.2])
        labels.append(1)
        rows.append([-2.0, 0.2])
        labels.append(0)
    scaled, _mean, _std = standardize(rows)
    weights, bias = train_logistic(scaled, labels, steps=300, lr=0.4, l2=0.0)
    scores = [predict_proba(row, weights, bias) for row in scaled]
    assert auroc(scores, labels) == pytest.approx(1.0)
    _threshold, fpr, achieved = threshold_at_tpr(scores, labels, 0.95)
    assert achieved >= 0.95
    assert fpr == pytest.approx(0.0)


def test_mock_residual_shapes_depend_on_pooling_and_layer():
    last = mock_activation("relay the dossier", 0, "last")
    mean = mock_activation("relay the dossier", 0, "mean")
    other = mock_activation("relay the dossier", 1, "last")
    assert len(last) == 32
    assert last != mean
    assert last != other
    assert parse_layers("0,2", available=4) == [0, 2]
    assert parse_layers("", available=3) == [0, 1, 2]
    assert resolve_model(None) == "Qwen/Qwen2.5-3B-Instruct"
    assert resolve_model("Qwen/Qwen2.5-0.5B-Instruct") == "Qwen/Qwen2.5-0.5B-Instruct"


def test_missing_hf_backend_does_not_download():
    try:
        import torch  # noqa: F401
        import transformers  # noqa: F401
    except ImportError:
        with pytest.raises(ProbeBackendUnavailable, match="no weights were downloaded"):
            resolve_backend("hf")
    else:
        pytest.skip("hf extra is installed; the missing-extra path is not this environment")


def test_qwen_placeholder_still_refuses_the_3b_id():
    assert QwenActivationProbe.MODEL_ID == "Qwen/Qwen2.5-3B"
    with pytest.raises(ProbeWeightsUnavailable):
        QwenActivationProbe()


def test_gateway_falls_back_to_stubs_without_artifacts(tmp_path, monkeypatch):
    monkeypatch.setenv("SMAIP_PROBE_DIR", str(tmp_path))
    monkeypatch.delenv("SMAIP_PROBES", raising=False)
    gateway = Gateway()
    assert isinstance(gateway.linear, LinearProbe)
    assert isinstance(gateway.probe, MockActivationProbe)
    assert isinstance(load_linear_defense(tmp_path), LinearProbe)
    assert isinstance(load_activation_defense(tmp_path), MockActivationProbe)


def test_mock_pipeline_trains_probes_and_rewrites_only_the_week7_report(tmp_path, monkeypatch):
    monkeypatch.setenv("SMAIP_PROBE_BACKEND", "mock")
    monkeypatch.setenv("SMAIP_PROBE_DIR", str(tmp_path / "probes"))
    monkeypatch.delenv("SMAIP_PROBES", raising=False)
    report = run_week7(
        model="Qwen/Qwen2.5-0.5B-Instruct",
        subset="tiny",
        backend="mock",
        device="cpu",
        artifact_dir=tmp_path / "probes",
        activation_dir=tmp_path / "activations",
        results_path=tmp_path / "RESULTS_week7.md",
        eval_path=tmp_path / "week7_eval.json",
    )
    assert report["backend"] == "mock"
    assert report["model_id"] == "Qwen/Qwen2.5-0.5B-Instruct"
    assert report["subset"] == "tiny"
    for name in ("linear", "activation"):
        metrics = report[name]["metrics"]
        for split in ("val", "test"):
            for key in ("auroc", "f1", "fpr_at_tpr", "tpr", "tpr_target"):
                assert key in metrics[split]
            assert 0.0 <= metrics[split]["auroc"] <= 1.0
        assert report[name]["layer_sweep"]
        assert report[name]["layer"] in {row["layer"] for row in report[name]["layer_sweep"]}
    assert report["linear"]["metrics"]["test"]["auroc"] >= 0.5
    for suite in ("week5", "week6"):
        names = [row["ablation"] for row in report[suite]]
        assert names == [
            "no-defense",
            "keyword",
            "LP-only",
            "probe-only",
            "gateway-only",
            "full-stack",
        ]
        rows = {row["ablation"]: row for row in report[suite]}
        assert rows["no-defense"]["asr"] == 1.0
        assert rows["gateway-only"]["asr"] == 0.0
        assert rows["no-defense"]["attack_total"] == 2
        assert rows["no-defense"]["benign_total"] == 2
    text = (tmp_path / "RESULTS_week7.md").read_text(encoding="utf-8")
    assert "Week 7 results" in text
    assert "mock" in text
    assert "LP-only" in text
    rendered = render_results(report)
    assert "Activation layer sweep" in rendered
    linear = load_linear_defense(tmp_path / "probes")
    activation = load_activation_defense(tmp_path / "probes")
    assert isinstance(linear, TrainedProbe)
    assert isinstance(activation, TrainedProbe)
    assert linear.kind == "linear"
    assert activation.pooling == "mean"
    injected = next(item for item in load_tool_outputs() if item.id == "tool-injected-01")
    benign = next(item for item in load_tool_outputs() if item.id == "tool-benign-01")
    assert LinearProbe().flagged(injected.text) is False
    assert MockActivationProbe().flagged(injected.text) is False
    assert linear.score(injected.text) > linear.score(benign.text)
    assert activation.score(injected.text) > activation.score(benign.text)
    monkeypatch.setenv("SMAIP_PROBES", "stub")
    forced = Gateway()
    assert isinstance(forced.linear, LinearProbe)
    assert isinstance(forced.probe, MockActivationProbe)
    summary = json.loads((tmp_path / "activations" / "summary.json").read_text(encoding="utf-8"))
    assert summary["backend"] == "mock"
    assert summary["dim"] == 32


def test_benchmark_skips_without_cuda(monkeypatch, tmp_path):
    monkeypatch.setattr("smaip.serving.benchmark.cuda_available", lambda: False)
    payload = run_benchmark(model="Qwen/Qwen2.5-3B-Instruct")
    assert payload["skipped"] is True
    assert "CUDA" in payload["reason"]
    assert payload["levels"] == []
    assert payload["defense_overhead"]["backend"] == "stub"
    assert payload["defense_overhead"]["mean_ms"] >= 0.0
    assert payload["defense_overhead"]["p50_ms"] >= 0.0
    assert payload["defense_overhead"]["p95_ms"] >= 0.0
    out = tmp_path / "bench.json"
    from smaip.serving.benchmark import bench_main

    code = bench_main(["--output", str(out), "--model", "Qwen/Qwen2.5-0.5B-Instruct"])
    assert code == 0
    written = json.loads(out.read_text(encoding="utf-8"))
    assert written["skipped"] is True


def test_activation_and_benchmark_modules_do_not_import_weights_at_import():
    activation_tree = ast.parse((ROOT / "src" / "smaip" / "probes" / "activations.py").read_text(encoding="utf-8"))
    bench_tree = ast.parse((ROOT / "src" / "smaip" / "serving" / "benchmark.py").read_text(encoding="utf-8"))
    qwen_text = (ROOT / "src" / "smaip" / "probes" / "qwen.py").read_text(encoding="utf-8")
    assert "import torch" not in qwen_text
    for tree in (activation_tree, bench_tree):
        for node in tree.body:
            if isinstance(node, ast.Import):
                assert all(alias.name not in {"torch", "transformers", "vllm"} for alias in node.names)
            if isinstance(node, ast.ImportFrom):
                assert node.module not in {"torch", "transformers", "vllm"}


def test_docs_makefile_and_ci_describe_the_gpu_path():
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    assert "week7-cpu:" in makefile
    assert "week7-gpu:" in makefile
    assert "week7-gpu-results.tar.gz" in makefile
    assert "Qwen/Qwen2.5-0.5B-Instruct" in makefile
    assert "Qwen/Qwen2.5-3B-Instruct" in makefile
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "week7:" in workflow
    assert "SMAIP_PROBE_BACKEND=mock" in workflow
    assert "make week7-cpu" in workflow
    assert "secrets:" not in workflow
    runbook = (ROOT / "docs" / "GPU_RUNBOOK.md").read_text(encoding="utf-8")
    assert "24 GB" in runbook
    assert "cluster" in runbook.lower()
    assert "destroy" in runbook.lower()
    assert "make week7-gpu" in runbook
    assert "nvidia-smi" in runbook
    script = (ROOT / "scripts" / "gpu" / "bootstrap.sh").read_text(encoding="utf-8")
    assert "nvidia-smi" in script
    assert "HF_HOME" in script
    assert ".[dev,hf]" in script
    assert ".[gpu]" in script
    assert "does not create" in script
    subprocess.run(["bash", "-n", str(ROOT / "scripts" / "gpu" / "bootstrap.sh")], check=True)
    readme = (ROOT / "docs" / "DEVELOPMENT_HISTORY.md").read_text(encoding="utf-8")
    assert "make week7-cpu" in readme
    assert "make week7-gpu" in readme
    testing = (ROOT / "docs" / "TESTING.md").read_text(encoding="utf-8")
    assert "make week7-cpu" in testing
    assert "SMAIP_PROBE_BACKEND=mock" in testing
    data = (ROOT / "DATA.md").read_text(encoding="utf-8")
    assert "tool_outputs.jsonl" in data
    assert "Do not vendor" in data


@pytest.mark.hf
def test_qwen_05b_residual_on_cpu():
    try:
        import torch
    except ImportError as exc:
        pytest.fail(f'Install the hf extra before SMAIP_RUN_HF=1 (`pip install -e ".[hf]"`): {exc}')
    from smaip.probes.activations import embed_text

    last = embed_text(
        "Revenue last quarter: 12.",
        model_id="Qwen/Qwen2.5-0.5B-Instruct",
        layer=0,
        pooling="last",
        backend="hf",
        device="cpu",
    )
    mean = embed_text(
        "Revenue last quarter: 12.",
        model_id="Qwen/Qwen2.5-0.5B-Instruct",
        layer=0,
        pooling="mean",
        backend="hf",
        device="cpu",
    )
    assert len(last) > 100
    assert len(mean) == len(last)
    assert last != mean
    assert torch.device("cpu").type == "cpu"
