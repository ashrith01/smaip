#!/usr/bin/env python3
"""Reaggregate archived GPU development evidence through the stricter gate.

Preserves every original artifact. Outputs an explicitly incomplete three-arm
development report, never fabricates the four unmeasured arms.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from smaip.eval.acceptance import assess
from smaip.eval.evidence import bound_evidence


def verify(root, output):
    root, output = Path(root).resolve(), Path(output)
    if output.exists():
        raise ValueError('preserve previous audit; choose fresh output')
    agent = root / 'open-agent-dev-02/runs'
    probe = root / 'probe-development-01'
    summary = json.loads((agent / 'summary.json').read_text())
    evaluation = json.loads((probe / 'evaluation/evaluation.json').read_text())
    artifacts = {}
    def bind(path):
        name = str(path.relative_to(root))
        artifacts[name] = {'path': name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
        return name
    cases = bind(agent / 'cases.json')
    runs = [{'variant': r['variant'], 'case': r['case'], 'artifact': bind(agent / r['run_file'])} for r in summary['results']]
    collection = bind(probe / 'collection/collection.json')
    meta = json.loads((probe / 'collection/collection.json').read_text())
    for name in meta['files_sha256']:
        bind(probe / 'collection' / name)
    rows = []
    for name, values in summary['aggregates'].items():
        # Quarantine is rechecked from actual clean episode events below.
        clean = [r for r in summary['results'] if r['variant'] == name and r['condition'] == 'clean']
        fp = sum(any(e.get('quarantined') for e in json.loads((agent / r['run_file']).read_text())['events']) for r in clean)
        rows.append({'name': name, 'utility': values['clean_task_success_rate'], 'asr': values['attack_objective_rate'], 'fpr': fp / len(clean)})
    reports = {}
    for filename in ('linear.json', 'activation.json'):
        m = evaluation['metrics'][filename]
        report = {'schema_version': 2, 'kind': 'brd-evidence', 'backend': 'hf-local',
            'model_id': meta['feature_protocol']['model_id'], 'run_id': 'archived-development-reaggregation-' + filename,
            'rows': rows,
            'probe': {'test_auroc': m['auroc'], 'test_tpr': m['tpr'], 'test_fpr': m['fpr'],
                'test_tp': m['tp'], 'test_fp': m['fp'], 'test_positives': m['positives'], 'test_negatives': m['negatives'],
                'calibration_negatives': 6, 'threshold_source': m['threshold_source'], 'fpr_budget': m['calibration_fpr_budget']},
            'evidence_bundle': {'artifacts': artifacts, 'agents': {'cases': cases, 'runs': runs},
                'probe': {'collection': collection, 'model': bind(probe / 'probes' / filename)}}}
        # Copy inventory so subsequent model bindings cannot mutate a report.
        report = json.loads(json.dumps(report))
        verified = bound_evidence(report, root)
        disposition = assess(report, evidence_root=root)
        if not disposition['checks'].get('artifact_consistency_verified'):
            raise ValueError('gate did not verify archived artifact consistency')
        if disposition['passed']:
            raise ValueError('development run must not certify release')
        reports[filename] = {'report': report, 'verified': verified, 'disposition': disposition}
    output.mkdir(parents=True)
    for filename, item in reports.items():
        (output / (filename.removesuffix('.json') + '-bound.json')).write_text(json.dumps(item, indent=2) + '\n')
    print(json.dumps({k: {'status': v['disposition']['status'], 'verified': v['verified']} for k, v in reports.items()}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', default='reports/runs')
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    verify(args.root, args.output)
