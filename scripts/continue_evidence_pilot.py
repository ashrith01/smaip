#!/usr/bin/env python3
"""Complete missing r3 episodes without retrying any completed success/failure.

This launcher lives outside src/. It verifies and reuses the original r3 package
bytes, cases, model configuration, scorer and budgets. It records its own source
inside summary.continuation. Parent archives and outputs are never overwritten.
"""
import argparse
from dataclasses import asdict
import hashlib
from importlib import metadata
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tarfile
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from analyze_evidence_pilot import verify
from smaip.agents.evidence_task import TaskIntent, run_evidence_task
from smaip.eval.contract import EvalConfig
from smaip.eval.evidence_pilot import pilot_cases
from smaip.eval.open_agent_dev import CaseLibrary, score_case
from smaip.probes.pipeline_v2 import MODEL, REVISION, source_hashes
from smaip.serving.open_model import HfLocalEngine, OpenModelConfig

R3_SHA256 = 'a675c268fb24b243e8ee117017715f2dfd941005ba2761b237ac9d5bbb547ffe'
PARENT_SHA256 = 'd7566b93bd1615abf18dece38a56dc3aa3bc7b935979456c8f1adf793ed50fbb'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, data):
    path.write_text(json.dumps(data, indent=2, allow_nan=False) + '\n')


def aggregates(results):
    out = {}
    for topology in ('single-agent', 'least-privilege'):
        scores = [r['score']['task_success'] for r in results if r['topology'] == topology]
        out[topology] = {'completed': len(scores), 'task_successes': sum(scores),
                         'utility': sum(scores) / len(scores) if scores else None}
    return out


def continue_pilot(prior, bundle, output, *, source_root=ROOT, engine=None, plan_only=False):
    prior, bundle, output, source_root = map(Path, (prior, bundle, output, source_root))
    archive_path = output.with_name(output.name + '.tar.gz')
    if output.exists() or archive_path.exists() or archive_path.with_name(archive_path.name + '.partial').exists():
        raise ValueError('fresh continuation output required; preserve previous results')
    parent_hash = digest(prior)
    # The original auditor verifies every completed case and score before carry.
    with tempfile.TemporaryDirectory(prefix='smaip-continuation-check-') as temp:
        checked = verify(prior, bundle, Path(temp) / 'parent-audit.json')
    if checked['pilot_mode'] != 'full' or checked['status'] != 'incomplete' or not 0 < checked['episodes_verified'] < 50:
        raise ValueError('only an incomplete full pilot can be continued')
    with tarfile.open(bundle) as source:
        member = next(m for m in source.getmembers() if m.name.endswith('/bundle-manifest.json'))
        manifest = json.load(source.extractfile(member))
    if manifest['agent_protocol_version'] != 7:
        raise ValueError('continuation requires frozen protocol 7')
    for name, expected in manifest['files'].items():
        relative = Path(name)
        path = (source_root / relative).resolve()
        if relative.is_absolute() or '..' in relative.parts or not path.is_relative_to(source_root.resolve()) or digest(path) != expected:
            raise ValueError('frozen source tree differs: ' + name)
    expected_sources = {n.removeprefix('src/smaip/'): h for n, h in manifest['files'].items()
                        if n.startswith('src/smaip/') and n.endswith('.py')}
    if source_hashes() != expected_sources:
        raise ValueError('imported runtime differs from original r3 source')
    with tarfile.open(prior) as source:
        summaries = [m for m in source.getmembers() if m.name.endswith('/runs/summary.json')]
        prefix = summaries[0].name.removesuffix('runs/summary.json')
        summary = json.load(source.extractfile(prefix + 'runs/summary.json'))
        case_bytes = source.extractfile(prefix + 'runs/cases.json').read()
        carried = {r['run_file']: source.extractfile(prefix + 'runs/' + r['run_file']).read()
                   for r in summary['results']}
    if digest(prior) != parent_hash:
        raise ValueError('parent archive changed during verification')
    config = OpenModelConfig(model_id=MODEL, revision=REVISION, device='cuda', dtype='float16',
                             max_new_tokens=1024, max_input_tokens=4096)
    if json.loads(case_bytes)['model_config'] != asdict(config):
        raise ValueError('parent model configuration differs')
    seen = {(r['topology'], r['case']) for r in summary['results']}
    missing = [(case, topology) for case in pilot_cases('full') for topology in ('single-agent', 'least-privilege')
               if (topology, case.id) not in seen]
    if len(missing) + len(seen) != 50:
        raise ValueError('case accounting differs')
    if plan_only:
        return {'kind': 'verified-r3-continuation-plan', 'preserved_episodes': len(seen),
            'preserved_failures': sum(not r['score']['task_success'] for r in summary['results']),
            'missing_episodes': [{'case': case.id, 'topology': topology} for case, topology in missing],
            'parent_archive_sha256': parent_hash, 'source_bundle_sha256': digest(bundle),
            'new_model_calls': 0, 'maximum_new_model_calls': len(missing) * 12,
            'maximum_new_generated_tokens': len(missing) * 12 * 1024}
    # Construct no GPU model until all parent/source checks have passed.
    if engine is None:
        import torch
        if not torch.cuda.is_available():
            raise ValueError('CUDA required; no CPU/mock fallback')
        engine = HfLocalEngine(config)
    if engine.name != 'hf-local' or asdict(engine.config) != asdict(config):
        raise ValueError('continuation model/budgets differ')
    output.mkdir(parents=True)
    runs = output / 'runs'
    runs.mkdir()
    (runs / 'cases.json').write_bytes(case_bytes)
    for name, data in carried.items():
        (runs / name).write_bytes(data)
    preserved = len(summary['results'])
    launcher = Path(__file__).read_text()
    summary.update(status='running', continuation={
        'parent_archive_sha256': parent_hash, 'source_bundle_sha256': digest(bundle),
        'preserved_episodes': preserved, 'planned_new_episodes': len(missing),
        'preserved_failures': sum(not r['score']['task_success'] for r in summary['results']),
        'source_state': 'Original r3 src and all manifest members verified byte-for-byte; launcher added outside src',
        'launcher_sha256': hashlib.sha256(launcher.encode()).hexdigest(), 'launcher_source': launcher,
        'timing_scope': 'Separate execution segment; not one uninterrupted serving/performance run',
        'unflushed_parent_work': 'Any in-flight episode lost at timeout is unobserved; no parent model-call/cost total is inferred'})
    def save():
        summary['aggregates'] = aggregates(summary['results'])
        write(runs / 'summary.json', summary)
    save()
    log = (output / 'model.log').open('w')
    def announce(message):
        print(message, flush=True)
        log.write(message + '\n')
        log.flush()
    code, started = 1, time.monotonic()
    try:
        announce(f'Preserved {preserved} completed episodes including failures; running {len(missing)} missing episodes only.')
        if engine.__class__ is HfLocalEngine:
            info = subprocess.run(['nvidia-smi'], text=True, capture_output=True, check=True)
            (output / 'gpu.txt').write_text(info.stdout)
            (output / 'packages.txt').write_text('\n'.join(sorted(
                f'{d.metadata["Name"]}=={d.version}' for d in metadata.distributions() if d.metadata.get('Name'))) + '\n')
        for case, topology in missing:
            if time.monotonic() - started >= 1800:
                raise TimeoutError('continuation reached 1800-second budget')
            evaluation = EvalConfig('task-intent-evidence-' + topology, topology=topology,
                                   backend='hf-local', model_id=MODEL, max_steps=12, max_new_tokens=1024)
            intent = TaskIntent(case.vendor, case.recipient, tuple(case.pages), review_required=False)
            run = run_evidence_task(intent, library=CaseLibrary(case), engine=engine, config=evaluation)
            filename = topology + '--' + case.id + '.json'
            path = runs / filename
            write(path, run)
            reads = [e for e in run['events'] if e['type'] == 'tool' and e.get('tool') == 'read_page' and e.get('allowed')]
            score = score_case(run, case)
            summary['results'].append({'case': case.id, 'topology': topology, 'run_file': filename,
                'run_sha256': digest(path), 'score': score,
                'diagnosis': {'status': run['status'], 'failure_reason': run['failure_reason'],
                    'successful_reads': len(reads), 'unique_pages_read': len({e['arguments_redacted']['page'] for e in reads}),
                    'model_calls': run['model_calls'], 'validated_artifact': run['summary_artifact'] is not None}})
            save()
            announce(f'{len(summary["results"])}/50 {topology} {case.id}: {score["task_success"]} '
                     f'calls={run["model_calls"]} reason={run["failure_reason"]}')
        summary.update(status='completed', smoke_qualified_for_full_pilot=False)
        code = 0
    except BaseException as exc:
        summary['status'] = 'failed; preserve partial continuation'
        summary['continuation']['error'] = type(exc).__name__ + ': ' + str(exc)
        raise
    finally:
        save()
        log.close()
        write(output / 'job-status.json', {'exit_code': code, 'status': 'completed' if code == 0 else 'failed-or-interrupted',
                                         'training_performed': False, 'sandbox_only': True})
        inventory = {str(p.relative_to(output)): digest(p) for p in sorted(output.rglob('*'))
                     if p.is_file() and p.name != 'files-sha256.json'}
        write(output / 'files-sha256.json', inventory)
        partial_archive = archive_path.with_name(archive_path.name + '.partial')
        with tarfile.open(partial_archive, 'w:gz') as archive:
            archive.add(output, arcname='reports/v3/' + output.name)
        partial_archive.rename(archive_path)
        print('Evidence saved to ' + str(archive_path), flush=True)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prior', default='reports/v3/evidence-clean-03-full.tar.gz')
    parser.add_argument('--bundle', default=str(ROOT.parent / (ROOT.name + '.tar.gz')))
    parser.add_argument('--output', default='reports/v3/evidence-clean-03-completed')
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    if digest(args.bundle) != R3_SHA256 or digest(args.prior) != PARENT_SHA256:
        raise ValueError('expected the audited r3 source and exact 40-episode parent archive')
    if Path(args.output).resolve().parent != (ROOT / 'reports/v3').resolve():
        raise ValueError('output must be a fresh direct child of reports/v3')
    os.environ['HF_HUB_OFFLINE'] = os.environ['TRANSFORMERS_OFFLINE'] = '1'
    os.environ.setdefault('CUDA_VISIBLE_DEVICES', '0')
    def terminate(_signal, _frame):
        raise TimeoutError('external continuation deadline reached')
    signal.signal(signal.SIGTERM, terminate)
    result = continue_pilot(args.prior, args.bundle, args.output, plan_only=args.check_only)
    if args.check_only:
        print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
