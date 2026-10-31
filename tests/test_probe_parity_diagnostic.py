"""The manual GPU diagnostic must detect small decision flips and preserve probes."""
import hashlib
import importlib.util
from pathlib import Path

import pytest

from smaip.eval.week7 import run_week7

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/gpu/probe_parity.py'
spec = importlib.util.spec_from_file_location('probe_parity_diagnostic', SCRIPT)
parity = importlib.util.module_from_spec(spec)
spec.loader.exec_module(parity)


def test_small_score_delta_cannot_hide_threshold_flip():
    reference = {'page': {'linear': 0.49, 'activation': 0.2796}}
    candidate = {'page': {'linear': 0.49, 'activation': 0.2798}}
    result = parity.compare(reference, candidate, {'linear': 0.5, 'activation': 0.2797}, 0.001)
    assert result['activation']['score_tolerance_exceeded'] == []
    assert result['activation']['decision_flips'][0]['id'] == 'page'
    assert result['linear']['decision_flips'] == []


def test_comparison_rejects_missing_record():
    with pytest.raises(AssertionError, match='record sets'):
        parity.compare({'a': {'linear': 0.1, 'activation': 0.1}}, {}, {'linear': 0.5, 'activation': 0.5}, 0.001)


def test_mock_diagnostic_runs_all_conditions_without_refitting_or_overwriting(tmp_path, monkeypatch):
    probes = tmp_path / 'probes'
    run_week7(subset='tiny', backend='mock', device='cpu', artifact_dir=probes,
              activation_dir=tmp_path / 'activations', results_path=tmp_path / 'train.md',
              eval_path=tmp_path / 'train.json')
    before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in probes.glob('*.json')}
    output = tmp_path / 'parity'
    report = parity.diagnose(artifacts=probes, output=output, backend='mock', device='cpu', subset='tiny')
    assert report['status'] == 'parity_screen_passed'
    assert len(report['conditions']) == 6
    assert all(len(condition['scores']) == 20 for condition in report['conditions'].values())
    assert report['metadata']['backend'] == 'mock'
    assert 'no Qwen or GPU' in report['metadata']['note']
    assert before == {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in probes.glob('*.json')}
    assert (output / 'vectors.jsonl.gz').is_file()
    assert (output / 'parity.json').is_file()
    assert (output / 'RESULTS.md').is_file()
    with pytest.raises(FileExistsError):
        parity.diagnose(artifacts=probes, output=output, backend='mock', device='cpu', subset='tiny')


def test_mock_diagnostic_cannot_label_real_hf_weights_as_a_mock_result(tmp_path):
    import json
    for kind in ('linear', 'activation'):
        (tmp_path / (kind + '.json')).write_text(json.dumps({'backend': 'hf', 'model_id': 'real', 'device': 'cuda'}))
    with pytest.raises(AssertionError, match='backend'):
        parity.diagnose(artifacts=tmp_path, output=tmp_path / 'output', backend='mock')
    assert not (tmp_path / 'output').exists()
