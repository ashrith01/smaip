"""Verify and preserve the first paired development GPU run without model loads.

Run from the repository root. The source bundle freezes provenance even after
the current agent code moves forward. Task grading remains canonical-numeric-v1.
"""
import hashlib
import json
from pathlib import Path, PurePosixPath
import tarfile

from smaip.agents.action_schema import ACTION_SCHEMA
from smaip.agents.open_loop import parse_action
from smaip.eval.open_agent_dev import aggregate, development_cases, score_case
from smaip.serving.structured import schema_fingerprint


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    archive = Path('reports/open-agent-dev-01.tar.gz')
    bundle_path = Path('reports/brd-open-model-v2-r4.tar.gz')
    destination = Path('reports/runs/open-agent-dev-01')
    with tarfile.open(bundle_path) as bundle_tar:
        item = next(m for m in bundle_tar.getmembers() if m.name.endswith('/bundle-manifest.json'))
        manifest_bytes = bundle_tar.extractfile(item).read()
        bundle = json.loads(manifest_bytes)
        if not (bundle['commit'] == '9d40bd743a409d9753217317f25d7de1294c2bfb'):
            raise ValueError('Evidence check failed at analyze_open_agent_development.py:29')
        for name, expected in bundle['files'].items():
            if not (sha(bundle_tar.extractfile(bundle['prefix'] + '/' + name).read()) == expected):
                raise ValueError(name)
    sources = {name.removeprefix('src/smaip/'): value for name, value in bundle['files'].items()
               if name.startswith('src/smaip/') and name.endswith('.py')}
    cases = {case.id: case for case in development_cases()}
    variants = ('no-defense', 'least-privilege-only', 'keyword-screen')
    run_names = {variant + '--' + name + '.json' for variant in variants for name in cases}
    allowed = {'runtime.json', 'bundle-validation.json', 'status.txt', 'packages.txt', 'model.log', 'contract.json',
               'runs/cases.json', 'runs/summary.json'} | {'runs/' + name for name in run_names}
    raw = {}
    prefix = 'reports/v2/open-agent-dev-01/'
    with tarfile.open(archive) as tar:
        for member in tar.getmembers():
            if member.isdir():
                continue
            if not (member.isfile() and member.name.startswith(prefix) and (member.size < 5000000)):
                raise ValueError('Evidence check failed at analyze_open_agent_development.py:45')
            name = member.name.removeprefix(prefix)
            if not (name in allowed and name not in raw and ('..' not in PurePosixPath(name).parts)):
                raise ValueError(name)
            raw[name] = tar.extractfile(member).read()
    if not (set(raw) == allowed):
        raise ValueError('Evidence check failed at analyze_open_agent_development.py:49')
    decode = lambda name: json.loads(raw[name])
    validation = decode('bundle-validation.json')
    if not (validation == {'commit': bundle['commit'], 'files_verified': len(bundle['files']), 'manifest_sha256': sha(manifest_bytes)}):
        raise ValueError('Evidence check failed at analyze_open_agent_development.py:52')
    manifest, summary = decode('runs/cases.json'), decode('runs/summary.json')
    if not (manifest['cases'] == [case.model_dump(exclude_none=True) for case in cases.values()]):
        raise ValueError('Evidence check failed at analyze_open_agent_development.py:55')
    if not (sha(json.dumps(manifest, sort_keys=True).encode()) == summary['case_manifest_sha256']):
        raise ValueError('Evidence check failed at analyze_open_agent_development.py:56')
    if not (summary['status'] == 'completed' and len(summary['results']) == 24):
        raise ValueError('Evidence check failed at analyze_open_agent_development.py:57')
    ids, observed, outcomes = set(), set(), []
    calls = invalid = quarantined = role_denials = unauthorized = audit_changes = 0
    for row in summary['results']:
        case = cases[row['case']]
        key = (row['variant'], case.id)
        if not (key not in observed and row['variant'] in variants):
            raise ValueError('Evidence check failed at analyze_open_agent_development.py:63')
        if not (row['condition'] == case.condition and row['pair_id'] == case.pair_id):
            raise ValueError('Evidence check failed at analyze_open_agent_development.py:64')
        observed.add(key)
        if not (row['run_file'] == row['variant'] + '--' + case.id + '.json'):
            raise ValueError('Evidence check failed at analyze_open_agent_development.py:66')
        report = decode('runs/' + row['run_file'])
        if not (report['source_sha256'] == sources and report['run_id'] == row['run_id']):
            raise ValueError('Evidence check failed at analyze_open_agent_development.py:68')
        if not (report['run_id'] not in ids):
            raise ValueError('Evidence check failed at analyze_open_agent_development.py:69')
        ids.add(report['run_id'])
        if not (report['config']['name'] == row['variant'] and report['config']['detector'] == 'none'):
            raise ValueError('Evidence check failed at analyze_open_agent_development.py:71')
        if not (report['config']['max_steps'] == 12 and report['config']['max_new_tokens'] == 256):
            raise ValueError('Evidence check failed at analyze_open_agent_development.py:72')
        if not (report['agent_protocol_version'] == 3 and report['backend'] == 'hf-local'):
            raise ValueError('Evidence check failed at analyze_open_agent_development.py:73')
        if not (report['response_format']['schema_sha256'] == schema_fingerprint(ACTION_SCHEMA)):
            raise ValueError('Evidence check failed at analyze_open_agent_development.py:74')
        model_events = [event for event in report['events'] if event['type'] == 'model']
        if not (report['model_calls'] == len(model_events) <= 12):
            raise ValueError('Evidence check failed at analyze_open_agent_development.py:76')
        calls += len(model_events)
        for event in model_events:
            parse_action(event['response_redacted'])
            if not (event['usage']['revision'] == 'aa8e72537993ba99e69dfaafa59ed015b17504d1'):
                raise ValueError('Evidence check failed at analyze_open_agent_development.py:80')
            if not (event['usage']['schema_sha256'] == schema_fingerprint(ACTION_SCHEMA)):
                raise ValueError('Evidence check failed at analyze_open_agent_development.py:81')
        for event in report['events']:
            invalid += event['type'] == 'invalid_model_action'
            quarantined += bool(event.get('quarantined'))
            role_denials += event.get('reason') == 'role_denied'
            if event.get('tool') == 'read_page' and event.get('allowed'):
                if not (event['source_sha256'] == case.page_hashes[event['arguments_redacted']['page']]):
                    raise ValueError('Evidence check failed at analyze_open_agent_development.py:87')
        grade = score_case(report, case)
        if not (grade == row['score']):
            raise ValueError(key)
        unauthorized += grade['unauthorized_send_count']
        audit_changes += grade['audit_log_modified']
        outcomes.append({'variant': row['variant'], 'case': case.id,
                         'status': report['status'], 'calls': report['model_calls'],
                         'sent_count': len(report['sent']), 'score': grade})
    if not (observed == {(variant, case) for variant in variants for case in cases}):
        raise ValueError('Evidence check failed at analyze_open_agent_development.py:95')
    if not (aggregate(summary['results'], variants) == summary['aggregates']):
        raise ValueError('Evidence check failed at analyze_open_agent_development.py:96')
    result = {'archive_sha256': sha(archive.read_bytes()), 'bundle_sha256': sha(bundle_path.read_bytes()),
              'source_commit': bundle['commit'], 'verified_bundle_files': len(bundle['files']),
              'verified_python_sources': len(sources), 'verified_runs': len(outcomes),
              'model_calls': calls, 'invalid_model_actions': invalid, 'quarantined_reads': quarantined,
              'role_denials': role_denials, 'unauthorized_send_count': unauthorized,
              'audit_changes': audit_changes, 'aggregates': summary['aggregates'], 'outcomes': outcomes,
              'assessment': 'Development evidence verified. Least-privilege clean utility failed; no successful attacker objective observed. BRD acceptance remains pending.'}
    destination.mkdir(parents=True, exist_ok=True)
    for name, content in raw.items():
        path = destination / name
        if path.exists():
            if not (path.read_bytes() == content):
                raise ValueError('existing evidence differs: ' + name)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
    result['members_sha256'] = {name: sha(content) for name, content in raw.items()}
    (destination / 'validation.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({key: value for key, value in result.items() if key not in {'outcomes', 'members_sha256'}}, indent=2))


if __name__ == '__main__':
    main()
