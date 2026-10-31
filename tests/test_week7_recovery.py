"""Recovery regressions: document boundaries, artifact reuse, and cache isolation."""
import hashlib
import json
from pathlib import Path

import pytest

from smaip.agents.graph import run_task
from smaip.eval.week5 import _follow_call, _trace_score, load_tasks, week5_root
from smaip.eval.week7 import rescore_week7, run_week7
from smaip.gateway.enforcement import presets
from smaip.gateway.gateway import Gateway
from smaip.probes.trained import TrainedProbe
from smaip.vendors import VendorLibrary


class DocumentProbe:
    matches_training_documents = True

    def __init__(self):
        self.seen = []

    def flagged(self, text):
        self.seen.append(text)
        # Simulate a benign page, but an out-of-distribution digest false positive.
        return "mock:" in text or "malicious-source" in text


def test_generated_digest_is_not_sent_to_document_probe():
    probe = DocumentProbe()
    result = run_task(
        "Research Acme Analytics and email the digest to owner@example.com",
        enforcement=presets()["LP-only"],
        fields={"vendor": "acme_analytics", "recipient": "owner@example.com"},
        linear=probe,
    )
    assert result.gateway.workspace.sent
    assert probe.seen
    assert all("mock:" not in text and "owner@example.com" not in text for text in probe.seen)


def test_original_malicious_document_still_blocks_mutation():
    probe = DocumentProbe()
    gateway = Gateway(linear=probe)
    decision = gateway.execute(
        role="actor", tool="send",
        arguments={"to": "evil@example.com", "body": "apparently harmless"},
        untrusted_text="malicious-source",
        enforcement=presets()["LP-only"],
    )
    assert not decision.allowed
    assert decision.reason == "linear_probe_hook"
    assert not gateway.workspace.sent
    assert probe.seen == ["malicious-source"]


def test_multi_page_followup_preserves_individual_document_boundaries():
    library = VendorLibrary(week5_root())
    task = next(item for item in load_tasks() if item["id"] == "ferry-hop")
    arguments, text, documents = _follow_call(task, library)
    assert len(documents) == 2
    assert text == "\n".join(documents)
    probe = DocumentProbe()
    gateway = Gateway(linear=probe)
    gateway.execute(
        role="actor", tool=task["follow"]["tool"], arguments=arguments,
        untrusted_text=text, untrusted_documents=documents,
        enforcement=presets()["LP-only"],
    )
    assert probe.seen == documents


def test_rescore_reuses_artifacts_without_training_or_threshold_changes(tmp_path, monkeypatch):
    directory = tmp_path / "probes"
    run_week7(
        subset="tiny", backend="mock", device="cpu", artifact_dir=directory,
        activation_dir=tmp_path / "activations", results_path=tmp_path / "training.md",
        eval_path=tmp_path / "training.json",
    )
    paths = list(directory.glob("*.json"))
    before = {p.name: p.read_bytes() for p in paths}
    def forbidden(*args, **kwargs):
        raise AssertionError("rescore must not collect activations or train")
    monkeypatch.setattr("smaip.eval.week7.collect", forbidden)
    monkeypatch.setattr("smaip.eval.week7.sweep_probe", forbidden)
    report = rescore_week7(
        artifact_dir=directory, subset="tiny", results_path=tmp_path / "rescore.md",
        output_path=tmp_path / "rescore.json",
    )
    assert {p.name: p.read_bytes() for p in paths} == before
    assert report["probe_sha256"] == {name: hashlib.sha256(data).hexdigest() for name, data in before.items()}
    for kind in ("linear", "activation"):
        assert report[kind]["threshold"] == json.loads(before[kind + ".json"])["threshold"]
    assert report["week5"][0]["attack_total"] == 2
    assert "not unseen-attack" in report["note"]
    with pytest.raises(ValueError, match="subset"):
        rescore_week7(artifact_dir=directory, subset="typo", results_path=tmp_path / "bad.md", output_path=tmp_path / "bad.json")


def test_missing_probe_files_do_not_trigger_a_training_run(tmp_path):
    with pytest.raises(FileNotFoundError, match="does not train"):
        rescore_week7(artifact_dir=tmp_path)


def test_trace_logging_does_not_compute_uncached_trained_scores():
    class Probe:
        matches_training_documents = True
        def cached_score(self, text):
            return 0.25 if text == "seen" else None
        def score(self, text):
            raise AssertionError("diagnostic model forward outside the timer")
    assert _trace_score(Probe(), "joined unseen", ["seen", "unseen"]) == 0.25
    assert _trace_score(Probe(), "unseen", ["unseen"]) is None


def test_score_precision_tracks_training_and_cache_tracks_feature_config(monkeypatch):
    payload = {
        "kind": "linear", "model_id": "test", "backend": "mock", "device": "cuda",
        "pooling": "last", "layer": 0, "threshold": 0.5, "dim": 1,
        "mean": [0.0], "std": [1.0], "weights": [1.0], "bias": 0.0,
    }
    probe = TrainedProbe(payload)
    calls = []
    def embed(text, **kwargs):
        calls.append(kwargs)
        return [1.0]
    monkeypatch.setattr("smaip.probes.trained.embed_text", embed)
    monkeypatch.setenv("SMAIP_PROBE_DEVICE", "cpu")
    assert probe.embedding_dtype() == "float16"
    first = probe.score("page")
    assert probe.score("page") == first
    assert len(calls) == 1
    monkeypatch.setenv("SMAIP_PROBE_MAX_LENGTH", "256")
    probe.score("page")
    assert len(calls) == 2
    assert calls[0]["dtype_name"] == "float16"
    assert calls[0]["device"] == "cpu"
    probe.clear_score_cache()
    assert probe.cached_score("page") is None
