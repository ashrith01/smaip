from smaip.eval.evidence_pilot import clean_cases
from smaip.agents.evidence_task import TaskIntent, validate_summary, AGENT_PROTOCOL
from smaip.fields import _FIELD_LINE, _LABELS
import hashlib
import json
import tarfile
import io
from pathlib import Path
import pytest

from smaip.eval.evidence_pilot import run_pilot
from smaip.probes.pipeline_v2 import source_hashes
from smaip.serving.open_model import OpenModelConfig


def test_all_original_pilot_oracles_are_source_supported_and_coverage_varies():
    cases = clean_cases()
    assert len(cases) == len({c.id for c in cases}) == 25
    assert {len(c.pages) for c in cases} == {1, 2, 3}
    assert cases == clean_cases()
    for case in cases:
        intent = TaskIntent(case.vendor, case.recipient, tuple(case.pages))
        sources, proposals = {}, []
        for page, text in case.pages.items():
            source_id = 'vendor://' + case.vendor + '/' + page
            sources[source_id] = dict(text=text, sha256=hashlib.sha256(text.encode()).hexdigest())
            for m in _FIELD_LINE.finditer(text):
                proposals.append(dict(field=_LABELS[m[1]], value=int(m[2]), source_id=source_id, quote=m.group().strip()))
        # Only the post-run test uses the oracle. Runtime model input never gets it.
        assert validate_summary(intent, sources, proposals)['body'] == case.expected_body


@pytest.mark.parametrize('mode,episodes', [('full', 50), ('smoke', 8)])
def test_complete_scripted_pilot_round_trip_regrades_effects_and_rejects_fake_scores(tmp_path, mode, episodes):
    # Shaped HF metadata is a fixture for the auditor; inference is scripted.
    # These files never become claimed GPU results.
    class ScriptedSourceReader:
        name = 'hf-local'
        config = OpenModelConfig(device='cuda', dtype='float16', max_new_tokens=1024, max_input_tokens=4096)
        def complete(self, messages):
            task = json.loads(messages[1]['content'])
            sources, artifact = {}, None
            for message in messages[2:]:
                if message['role'] != 'user':
                    continue
                content = message['content']
                if content.startswith('Untrusted source data:\n'):
                    sources.update({doc['source_id']: doc for doc in json.loads(content.split('\n', 1)[1])['documents']})
                elif content.startswith('Tool result'):
                    result = json.loads(content.split('\n', 1)[1])
                    if isinstance(result, dict):
                        if 'source_id' in result:
                            sources[result['source_id']] = result
                        artifact = result.get('artifact_id', artifact)
                elif content.startswith('{'):
                    artifact = json.loads(content).get('validated_summary_artifact', artifact)
            if artifact:
                return json.dumps({'tool': 'send_summary', 'arguments': {'artifact_id': artifact}})
            for page in task['pages']:
                if 'vendor://' + task['vendor'] + '/' + page not in sources:
                    return json.dumps({'tool': 'read_page', 'arguments': {'vendor': task['vendor'], 'page': page}})
            claims = [dict(field=_LABELS[m[1]], value=int(m[2]), source_id=source_id, line_number=line['line_number'])
                      for source_id, value in sources.items() for line in value['lines']
                      for m in _FIELD_LINE.finditer(line['text'])]
            return json.dumps({'tool': 'submit_claims', 'arguments': {'claims': claims}})
    output = tmp_path / 'job'
    output.mkdir()
    result = run_pilot(ScriptedSourceReader(), output / 'runs', mode=mode)
    assert result['status'] == 'completed'
    assert result['aggregates']['least-privilege']['task_successes'] == episodes // 2
    (output / 'job-status.json').write_text(json.dumps({'exit_code': 0}))
    source = tmp_path / 'source.tar.gz'
    root = Path(__file__).resolve().parents[1]
    files = {'src/smaip/' + name: value for name, value in source_hashes().items()}
    manifest = dict(kind=f'protocol-{AGENT_PROTOCOL}-clean-pilot-source', agent_protocol_version=AGENT_PROTOCOL, prefix='source', files=files)
    with tarfile.open(source, 'w:gz') as archive:
        for name in files:
            archive.add(root / name, arcname='source/' + name)
        data = json.dumps(manifest).encode()
        info = tarfile.TarInfo('source/bundle-manifest.json')
        info.size = len(data)
        archive.addfile(info, io.BytesIO(data))
    def pack(name):
        inventory = {str(p.relative_to(output)): hashlib.sha256(p.read_bytes()).hexdigest()
                     for p in output.rglob('*') if p.is_file() and p.name != 'files-sha256.json'}
        (output / 'files-sha256.json').write_text(json.dumps(inventory))
        path = tmp_path / name
        with tarfile.open(path, 'w:gz') as archive:
            archive.add(output, arcname='reports/v3/testpilot')
        return path
    import importlib.util
    spec = importlib.util.spec_from_file_location('smaip_test_pilot_auditor', root / 'scripts/analyze_evidence_pilot.py')
    auditor = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(auditor)
    verified = auditor.verify(pack('good.tar.gz'), source, tmp_path / 'audit.json')
    assert verified['episodes_verified'] == episodes and not verified['release_pass']
    assert verified['smoke_qualified_for_full_pilot'] == (mode == 'smoke')
    summary = output / 'runs/summary.json'
    content = json.loads(summary.read_text())
    content['results'][0]['score']['task_success'] = False
    summary.write_text(json.dumps(content))
    with pytest.raises(ValueError, match='score differs from effects'):
        auditor.verify(pack('bad.tar.gz'), source, tmp_path / 'bad-audit.json')


def test_smoke_cli_returns_nonzero_for_a_completed_but_useless_model(tmp_path, monkeypatch):
    import sys
    from smaip.eval.evidence_pilot import main
    class AbortingEngine:
        name = 'hf-local'
        def __init__(self, config):
            self.config = config
        def complete(self, messages):
            return '{"final":"text"}'
    monkeypatch.setattr('smaip.serving.open_model.HfLocalEngine', AbortingEngine)
    monkeypatch.setattr(sys, 'argv', ['pilot', '--mode', 'smoke', '--output', str(tmp_path / 'runs')])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2
    summary = json.loads((tmp_path / 'runs/summary.json').read_text())
    assert summary['status'] == 'completed' and not summary['smoke_qualified_for_full_pilot']
    assert len(summary['results']) == 8
    assert {r['case'] for r in summary['results']} == {'clean-00', 'clean-06', 'clean-13', 'clean-20'}
    assert all(r['diagnosis']['successful_reads'] == 0 for r in summary['results'])
