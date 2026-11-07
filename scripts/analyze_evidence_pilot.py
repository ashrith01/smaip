#!/usr/bin/env python3
"""Verify returned sandbox pilot hashes and regrade effects without a model."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import sys
import tarfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from smaip.eval.evidence_pilot import clean_cases, pilot_cases
from smaip.eval.open_agent_dev import score_case
from smaip.probes.pipeline_v2 import MODEL, REVISION


def verify(archive, bundle, output):
    output = Path(output)
    if output.exists():
        raise ValueError('choose a fresh audit output')
    with tarfile.open(bundle) as source:
        manifests = [m for m in source.getmembers() if m.name.endswith('/bundle-manifest.json')]
        if len(manifests) != 1:
            raise ValueError('source manifest absent or duplicated')
        manifest = json.load(source.extractfile(manifests[0]))
        protocol = manifest.get('agent_protocol_version', 5)
        if protocol not in (5, 6, 7) or manifest['kind'] != f'protocol-{protocol}-clean-pilot-source':
            raise ValueError('wrong source bundle')
        for name, expected in manifest['files'].items():
            raw = source.extractfile(manifest['prefix'] + '/' + name).read()
            if hashlib.sha256(raw).hexdigest() != expected:
                raise ValueError('source bundle member differs')
    cases = {c.id: c for c in clean_cases()}
    topologies = ('single-agent', 'least-privilege')
    allowed = {'gpu.txt', 'packages.txt', 'model.log', 'job-status.json', 'files-sha256.json', 'runs/cases.json', 'runs/summary.json'}
    allowed |= {f'runs/{t}--{case}.json' for t in topologies for case in cases}
    raw, total, prefix = {}, 0, None
    with tarfile.open(archive) as returned:
        for member in returned.getmembers():
            if member.isdir():
                continue
            path = PurePosixPath(member.name)
            if not member.isfile() or path.is_absolute() or '..' in path.parts or len(path.parts) < 4:
                raise ValueError('unsafe archive member')
            current_prefix = '/'.join(path.parts[:3])
            if path.parts[:2] != ('reports', 'v3') or prefix not in (None, current_prefix):
                raise ValueError('unexpected output root')
            prefix = current_prefix
            name = '/'.join(path.parts[3:])
            total += member.size
            if name not in allowed or name in raw or member.size > 20_000_000 or total > 100_000_000:
                raise ValueError('unexpected, duplicate or oversized evidence member')
            raw[name] = returned.extractfile(member).read()
    inventory = json.loads(raw['files-sha256.json'])
    if set(inventory) != set(raw) - {'files-sha256.json'} or any(hashlib.sha256(raw[n]).hexdigest() != h for n, h in inventory.items()):
        raise ValueError('returned file inventory differs')
    case_manifest = json.loads(raw['runs/cases.json'])
    mode = case_manifest.get('pilot_mode', 'full')
    cases = {c.id: c for c in pilot_cases(mode)}
    episodes = len(cases) * 2
    if case_manifest['cases'] != [c.model_dump(exclude_none=True) for c in cases.values()]:
        raise ValueError('pilot task content differs')
    expected_sources = {n.removeprefix('src/smaip/'): h for n, h in manifest['files'].items() if n.startswith('src/smaip/') and n.endswith('.py')}
    if case_manifest['source_sha256'] != expected_sources or case_manifest['agent_protocol_version'] != protocol or case_manifest['episodes'] != episodes:
        raise ValueError('pilot source/protocol differs')
    summary = json.loads(raw['runs/summary.json'])
    if summary['case_manifest_sha256'] != hashlib.sha256(raw['runs/cases.json']).hexdigest():
        raise ValueError('case manifest binding differs')
    results, seen, identities = [], set(), set()
    for entry in summary['results']:
        key = (entry['topology'], entry['case'])
        expected_name = f'{key[0]}--{key[1]}.json'
        if key in seen or key[0] not in topologies or key[1] not in cases or entry['run_file'] != expected_name:
            raise ValueError('episode identity differs')
        seen.add(key)
        data = raw['runs/' + expected_name]
        run = json.loads(data)
        if hashlib.sha256(data).hexdigest() != entry['run_sha256'] or run['source_sha256'] != expected_sources:
            raise ValueError('episode hash/source differs')
        if run['run_id'] in identities:
            raise ValueError('duplicate run identity')
        identities.add(run['run_id'])
        if (run['backend'], run['agent_protocol_version'], run['runtime_policy'], run['generation_config']['model_id'],
            run['generation_config']['revision'], run['generation_config']['device'], run['generation_config']['dtype']) != (
                'hf-local', protocol, f'task-intent-evidence-v{protocol - 4}', MODEL, REVISION, 'cuda', 'float16'):
            raise ValueError('episode model/protocol differs')
        if run['config']['topology'] != key[0] or run['config']['max_steps'] != 12 or run['config']['max_new_tokens'] != 1024:
            raise ValueError('episode topology/budget differs')
        if run['config']['keyword'] or run['config']['gateway'] or run['config']['detector'] != 'none' or run['generation_config']['max_input_tokens'] != 4096 or run['generation_config']['max_new_tokens'] != 1024:
            raise ValueError('episode policy/generation budget differs')
        if run['model_calls'] != sum(e['type'] == 'model' for e in run['events']) or not 0 <= run['model_calls'] <= 12:
            raise ValueError('episode call accounting differs')
        score = score_case(run, cases[key[1]])
        if score != entry['score']:
            raise ValueError('submitted task score differs from effects')
        if protocol >= 7:
            reads = [e for e in run['events'] if e['type'] == 'tool' and e.get('tool') == 'read_page' and e.get('allowed')]
            actual_diagnosis = {'status': run['status'], 'failure_reason': run['failure_reason'],
                'successful_reads': len(reads), 'unique_pages_read': len({e['arguments_redacted']['page'] for e in reads}),
                'model_calls': run['model_calls'], 'validated_artifact': run['summary_artifact'] is not None}
            if entry.get('diagnosis') != actual_diagnosis:
                raise ValueError('submitted diagnosis differs from effects')
        results.append({**entry, 'score': score})
    expected_files = {'runs/' + r['run_file'] for r in results}
    if {n for n in raw if n.startswith('runs/') and n not in ('runs/cases.json', 'runs/summary.json')} != expected_files:
        raise ValueError('unreported episode artifacts')
    aggregates = {}
    for topology in topologies:
        scores = [r['score']['task_success'] for r in results if r['topology'] == topology]
        aggregates[topology] = {'completed': len(scores), 'task_successes': sum(scores), 'utility': sum(scores) / len(scores) if scores else None}
    if aggregates != summary['aggregates']:
        raise ValueError('submitted aggregate differs')
    status = json.loads(raw['job-status.json'])
    qualified = mode == 'smoke' and len(seen) == episodes and all(r['score']['task_success'] for r in results)
    if protocol >= 6 and summary.get('smoke_qualified_for_full_pilot', False) != qualified:
        raise ValueError('smoke quality disposition differs from effects')
    completed = len(seen) == episodes and summary['status'] == 'completed' and status['exit_code'] in (0, 2)
    result = {'kind': f'verified-protocol-{protocol}-clean-pilot', 'status': 'completed' if completed else 'incomplete',
        'pilot_mode': mode, 'smoke_qualified_for_full_pilot': qualified,
        'source_bundle_sha256': hashlib.sha256(Path(bundle).read_bytes()).hexdigest(),
        'archive_sha256': hashlib.sha256(Path(archive).read_bytes()).hexdigest(),
        'aggregates': aggregates, 'episodes_verified': len(results), 'release_pass': False,
        'scope': 'Artifact consistency and clean synthetic sandbox utility; no security evaluation, independent label attestation or five-point noninferiority claim'}
    with output.open('x') as stream:
        stream.write(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', required=True)
    parser.add_argument('--bundle', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    verify(args.archive, args.bundle, args.output)
