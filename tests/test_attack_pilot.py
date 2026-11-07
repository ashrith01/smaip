import json
import sys
from types import SimpleNamespace

import pytest

from smaip.eval.attack_pilot import attack_pilot_cases, run_attack_pilot
from smaip.eval.open_agent_dev import score_case
from smaip.fields import extract_fields


def _report(case):
    return {'sent': [{'to': case.recipient, 'subject': 'brief', 'body': case.expected_body}],
            'files': {'audit.log': 'audit-seed\n'},
            'events': [{'type': 'tool', 'tool': 'read_page', 'allowed': True,
                        'quarantined': False,
                        'arguments_redacted': {'vendor': case.vendor, 'page': page},
                        'source_sha256': digest}
                       for page, digest in case.page_hashes.items()]}


def test_paired_payloads_preserve_task_facts_and_make_no_source_claims():
    cases = attack_pilot_cases()
    assert len(cases) == 8 and len({case.id for case in cases}) == 8
    assert {case.attack_goal for case in cases} == {'attacker_send', 'audit_tamper'}
    for clean, injected in zip(cases[::2], cases[1::2]):
        assert clean.condition == 'clean' and injected.condition == 'injected'
        assert clean.pair_id == injected.pair_id
        assert clean.expected_body == injected.expected_body
        assert clean.recipient == injected.recipient
        assert set(clean.pages) == set(injected.pages)
        changed = [page for page in clean.pages if clean.pages[page] != injected.pages[page]]
        assert len(changed) == 1
        page = changed[0]
        assert injected.pages[page].startswith(clean.pages[page])
        assert all(extract_fields(text) == extract_fields(injected.pages[name])
                   for name, text in clean.pages.items())
        assert clean.attacker_recipient != clean.recipient
        assert score_case(_report(clean), clean)['task_success']
        assert score_case(_report(injected), injected)['task_success']


def test_attack_objective_requires_observed_tool_effect():
    for case in attack_pilot_cases()[1::2]:
        report = _report(case)
        report['events'].append({'type': 'model', 'response_redacted': 'attack completed'})
        assert not score_case(report, case)['attack_objective_observed']
        if case.attack_goal == 'attacker_send':
            report['sent'].append({'to': case.attacker_recipient, 'subject': 'x', 'body': '42'})
        else:
            del report['files']['audit.log']
        score = score_case(report, case)
        assert score['attack_objective_observed'] and not score['task_success']


def test_runner_preserves_paired_scope_and_clean_baseline_gate(tmp_path):
    class NoProgressEngine:
        name = 'hf-local'
        config = SimpleNamespace(model_id='Qwen/Qwen2.5-3B-Instruct', max_new_tokens=256)
        def complete(self, messages):
            return '{"final":"no action"}'

    summary = run_attack_pilot(NoProgressEngine(), output=tmp_path / 'runs', variants=('no-defense',))
    assert summary['status'] == 'clean-baseline-incomplete; attack cases skipped'
    assert len(summary['results']) == 4
    assert all(row['condition'] == 'clean' for row in summary['results'])
    assert summary['aggregates']['no-defense']['attack_objective_rate'] is None
    manifest = json.loads((tmp_path / 'runs/cases.json').read_text())
    assert manifest['scope'].startswith('original synthetic paired attack development')
    assert len(manifest['cases']) == 8


def test_gpu_entrypoint_rejects_cpu_before_creating_output(tmp_path, monkeypatch):
    from scripts.gpu import run_attack_pilot as entrypoint

    engine = SimpleNamespace(config=SimpleNamespace(
        model_id='Qwen/Qwen2.5-3B-Instruct', revision='aa8e72537993ba99e69dfaafa59ed015b17504d1',
        device='cpu', dtype='float32', max_new_tokens=256, max_input_tokens=2048))
    monkeypatch.setattr(entrypoint, 'configured_engine', lambda name: engine)
    output = tmp_path / 'pilot'
    monkeypatch.setattr(sys, 'argv', ['pilot', '--output', str(output)])
    with pytest.raises(ValueError, match='pinned offline CUDA'):
        entrypoint.main()
    assert not output.exists()
