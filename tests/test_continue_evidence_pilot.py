"""Synthetic CPU fixtures verify continuation integrity, not GPU quality."""
import hashlib
import io
import json
from pathlib import Path
import sys
import tarfile

import pytest

from smaip.eval.evidence_pilot import run_pilot
from smaip.fields import _FIELD_LINE, _LABELS
from smaip.probes.pipeline_v2 import source_hashes
from smaip.serving.open_model import OpenModelConfig

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from continue_evidence_pilot import continue_pilot, aggregates
from analyze_evidence_pilot import verify


class SourceReader:
    name = 'hf-local'
    config = OpenModelConfig(device='cuda', dtype='float16', max_new_tokens=1024, max_input_tokens=4096)

    def __init__(self, *, abort_first=False, fail=False):
        self.abort_first, self.fail, self.seen = abort_first, fail, set()

    def complete(self, messages):
        task = json.loads(messages[1]['content'])
        self.seen.add(task['vendor'])
        if self.fail:
            raise RuntimeError('synthetic interruption')
        if self.abort_first and task['vendor'] == 'pilot_vendor_00' and 'the single-agent ' in messages[0]['content']:
            return '{"final":"cannot continue"}'
        artifact = task['workflow_state']['validated_artifact']
        sources = {}
        for message in messages[2:]:
            text = message['content']
            if message['role'] != 'user':
                continue
            if text.startswith('Untrusted source data:\n'):
                sources.update({d['source_id']: d for d in json.loads(text.split('\n', 1)[1])['documents']})
            elif text.startswith('Tool result'):
                data = json.loads(text.split('\n', 1)[1])
                if isinstance(data, dict) and 'source_id' in data:
                    sources[data['source_id']] = data
        if artifact:
            return json.dumps({'tool': 'send_summary', 'arguments': {'artifact_id': artifact}})
        if task['workflow_state']['remaining_pages']:
            return json.dumps({'tool': 'read_page', 'arguments': {'vendor': task['vendor'],
                              'page': task['workflow_state']['remaining_pages'][0]}})
        claims = [dict(field=_LABELS[m[1]], value=int(m[2]), source_id=source_id, line_number=line['line_number'])
                  for source_id, doc in sources.items() for line in doc['lines'] for m in _FIELD_LINE.finditer(line['text'])]
        return json.dumps({'tool': 'submit_claims', 'arguments': {'claims': claims}})


def pack(output, destination):
    inventory = {str(p.relative_to(output)): hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in output.rglob('*') if p.is_file() and p.name != 'files-sha256.json'}
    (output / 'files-sha256.json').write_text(json.dumps(inventory))
    with tarfile.open(destination, 'w:gz') as archive:
        archive.add(output, arcname='reports/v3/parent')


@pytest.fixture
def partial_parent(tmp_path):
    output = tmp_path / 'parent'
    output.mkdir()
    summary = run_pilot(SourceReader(abort_first=True), output / 'runs')
    for row in summary['results'][40:]:
        (output / 'runs' / row['run_file']).unlink()
    summary['results'] = summary['results'][:40]
    summary.update(status='running', aggregates=aggregates(summary['results']))
    (output / 'runs/summary.json').write_text(json.dumps(summary))
    (output / 'job-status.json').write_text(json.dumps({'exit_code': 124}))
    source = tmp_path / 'source.tar.gz'
    files = {'src/smaip/' + n: h for n, h in source_hashes().items()}
    manifest = dict(kind='protocol-7-clean-pilot-source', agent_protocol_version=7, prefix='source', files=files)
    with tarfile.open(source, 'w:gz') as archive:
        for name in files:
            archive.add(ROOT / name, arcname='source/' + name)
        data = json.dumps(manifest).encode()
        info = tarfile.TarInfo('source/bundle-manifest.json')
        info.size = len(data)
        archive.addfile(info, io.BytesIO(data))
    prior = tmp_path / 'parent.tar.gz'
    pack(output, prior)
    return output, prior, source


def test_continuation_preserves_all_40_including_failure_and_runs_only_missing_10(tmp_path, partial_parent):
    parent, prior, source = partial_parent
    before = {p.name: p.read_bytes() for p in (parent / 'runs').glob('*.json') if '--clean-' in p.name}
    parent_bytes = prior.read_bytes()
    engine = SourceReader()
    output = tmp_path / 'continued'
    plan = continue_pilot(prior, source, output, source_root=ROOT, engine=engine, plan_only=True)
    assert len(plan['missing_episodes']) == 10 and plan['preserved_failures'] == 1
    assert not engine.seen and not output.exists()
    result = continue_pilot(prior, source, output, source_root=ROOT, engine=engine)
    assert engine.seen == {f'pilot_vendor_{n:02d}' for n in range(20, 25)}
    assert len(result['results']) == 50 and result['status'] == 'completed'
    assert result['aggregates']['single-agent']['task_successes'] == 24
    assert result['aggregates']['least-privilege']['task_successes'] == 25
    assert result['continuation']['preserved_failures'] == 1
    for name, raw in before.items():
        assert (output / 'runs' / name).read_bytes() == raw
    assert prior.read_bytes() == parent_bytes
    checked = verify(output.with_name(output.name + '.tar.gz'), source, tmp_path / 'final-audit.json')
    assert checked['episodes_verified'] == 50 and checked['status'] == 'completed'
    with pytest.raises(ValueError, match='fresh'):
        continue_pilot(prior, source, output, source_root=ROOT, engine=engine)


def test_continuation_rejects_forged_parent_scores_before_any_new_model_call(tmp_path, partial_parent):
    parent, _, source = partial_parent
    path = parent / 'runs/summary.json'
    summary = json.loads(path.read_text())
    summary['results'][0]['score']['task_success'] = True
    path.write_text(json.dumps(summary))
    forged = tmp_path / 'forged.tar.gz'
    pack(parent, forged)
    engine = SourceReader()
    with pytest.raises(ValueError, match='score differs from effects'):
        continue_pilot(forged, source, tmp_path / 'bad', source_root=ROOT, engine=engine)
    assert not engine.seen and not (tmp_path / 'bad').exists()


def test_interrupted_continuation_archives_original_failed_and_successful_records(tmp_path, partial_parent):
    _, prior, source = partial_parent
    output = tmp_path / 'interrupted'
    with pytest.raises(RuntimeError, match='synthetic interruption'):
        continue_pilot(prior, source, output, source_root=ROOT, engine=SourceReader(fail=True))
    checked = verify(output.with_name(output.name + '.tar.gz'), source, tmp_path / 'partial-audit.json')
    assert checked['status'] == 'incomplete' and checked['episodes_verified'] == 40
    assert checked['aggregates']['single-agent']['task_successes'] == 19
