"""Validate saved Week 7 evidence without loading Qwen or changing any probes.

Run from the repo root: PYTHONPATH=src .venv/bin/python scripts/analyze_week7_rescore.py
The record-level metrics below use an independent pairwise AUROC calculation.
"""
import hashlib
import json
import math
from pathlib import Path
import shutil
import tarfile

from smaip.probes.dataset import prepare_records
from evidence_snapshot import assert_sources


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def metrics(rows, kind, threshold):
    positive = [row[kind] for row in rows if row['label'] == 1]
    negative = [row[kind] for row in rows if row['label'] == 0]
    tp = sum(value >= threshold for value in positive)
    fp = sum(value >= threshold for value in negative)
    tn, fn = len(negative) - fp, len(positive) - tp
    auc = sum((a > b) + 0.5 * (a == b) for a in positive for b in negative) / (len(positive) * len(negative))
    return {'tp': tp, 'fp': fp, 'tn': tn, 'fn': fn, 'auroc': auc,
            'f1': 2 * tp / (2 * tp + fp + fn) if tp else 0.0,
            'recall': tp / len(positive), 'fpr_at_validation_threshold': fp / len(negative),
            'threshold': threshold}


def main():
    archive = Path('reports/week7-rescore-results.tar.gz')
    result = json.loads(Path('reports/week7_rescore.json').read_text())
    with tarfile.open(archive) as tar:
        expected = {'reports/RESULTS_week7_rescore.md', 'reports/week7_rescore.json'}
        assert {m.name for m in tar.getmembers()} == expected
        for name in expected:
            member = tar.getmember(name)
            assert member.isfile() and member.size < 2_000_000
            assert tar.extractfile(member).read() == Path(name).read_bytes(), name
    assert (result['model_id'], result['backend'], result['device'], result['subset']) == ('Qwen/Qwen2.5-3B-Instruct', 'hf', 'cuda', 'full')
    for name, digest in result['probe_sha256'].items():
        assert sha(Path('artifacts/probes') / name) == digest, name
    original_manifest = json.loads(Path('reports/runs/week7-gpu-original/manifest.json').read_text())
    for name, entry in original_manifest['files'].items():
        assert sha(name) == entry['sha256'], name
    source_root = Path('src/smaip')
    current_sources = {str(p.relative_to(source_root)): sha(p) for p in source_root.rglob('*.py')}
    source_snapshot = assert_sources(result['source_sha256'])
    records = {record.id: record for record in prepare_records('full')}
    rows = result['document_scores']
    assert len(rows) == len(records) == len({row['id'] for row in rows}) == 57
    for row in rows:
        record = records[row['id']]
        assert (row['label'], row['split']) == (record.label, record.split)
        assert row['text_sha256'] == hashlib.sha256(record.text.encode()).hexdigest()
        assert all(math.isfinite(row[kind]) and 0 <= row[kind] <= 1 for kind in ('linear', 'activation'))
    computed = {}
    discrepancies = []
    for kind in ('linear', 'activation'):
        payload = json.loads((Path('artifacts/probes') / (kind + '.json')).read_text())
        for name in ('weights', 'mean', 'std'):
            assert len(payload[name]) == payload['dim'] == 2048
            assert all(math.isfinite(x) for x in payload[name])
        assert all(x > 0 for x in payload['std'])
        public = result[kind]
        for name in ('threshold', 'layer', 'pooling', 'metrics', 'layer_sweep', 'n_train', 'n_val', 'n_test'):
            assert public[name] == payload[name], (kind, name)
        anchor = round(max(x['layer'] for x in payload['layer_sweep']) * 2 / 3)
        chosen = min(payload['layer_sweep'], key=lambda x: (-x['val_auroc'], x['val_fpr_at_tpr'], abs(x['layer'] - anchor), x['layer']))
        assert chosen['layer'] == payload['layer']
        computed[kind] = {}
        for split in ('train', 'val', 'test'):
            block = metrics([row for row in rows if row['split'] == split], kind, payload['threshold'])
            computed[kind][split] = block
            if split != 'train':
                original = payload['metrics'][split]
                for new, old in (('auroc', 'auroc'), ('f1', 'f1'), ('recall', 'tpr'), ('fpr_at_validation_threshold', 'fpr_at_tpr')):
                    if not math.isclose(block[new], original[old], abs_tol=1e-12):
                        discrepancies.append({'probe': kind, 'split': split, 'metric': new, 'stored_training_metric': original[old], 'recomputed_rescore_metric': block[new]})
    comparisons = []
    original_eval = json.loads(Path('reports/week7_eval.json').read_text())
    for suite in ('week5', 'week6'):
        baseline = {row['ablation']: row for row in original_eval[suite]}
        tasks = json.loads((source_root / 'eval' / 'suites' / (suite + '.json')).read_text())['tasks']
        expected_ids = {task['id'] for task in tasks}
        expected_kinds = {task['id']: task['kind'] for task in tasks}
        for row in result[suite]:
            assert len(row['scenarios']) == len(expected_ids)
            assert {s['id'] for s in row['scenarios']} == expected_ids
            assert all(s['kind'] == expected_kinds[s['id']] for s in row['scenarios'])
            benign = [s for s in row['scenarios'] if s['kind'] == 'benign']
            attacks = [s for s in row['scenarios'] if s['kind'] == 'attack']
            counts = {'benign_total': len(benign), 'benign_ok': sum(s['legitimate_ok'] for s in benign), 'fp_hits': sum(s['false_positive'] for s in benign), 'attack_total': len(attacks), 'attack_hits': sum(s['attack_succeeded'] for s in attacks)}
            assert all(row[key] == value for key, value in counts.items())
            assert row['utility'] == counts['benign_ok'] / counts['benign_total']
            assert row['asr'] == counts['attack_hits'] / counts['attack_total']
            assert row['fpr'] == counts['fp_hits'] / counts['benign_total']
            comparisons.append({'suite': suite, 'ablation': row['ablation'],
                                'before_utility': baseline[row['ablation']]['utility'], 'after_utility': row['utility'],
                                'before_fpr': baseline[row['ablation']]['fpr'], 'after_fpr': row['fpr'],
                                'asr': row['asr'], 'counts': counts,
                                'suite_elapsed_ms': row['latency_ms'], 'mean_episode_ms': row['latency_ms'] / len(row['scenarios'])})
    report = {'assessment': 'Integration recovery verified with remaining scientific and calibration caveats',
              'archive_sha256': sha(archive), 'probe_sha256': result['probe_sha256'],
              'source_snapshot': source_snapshot, 'verified_source_files': len(result['source_sha256']), 'verified_documents': len(rows), 'verified_ablation_rows': len(comparisons),
              'runtime': result['runtime'], 'recomputed_record_metrics': computed,
              'stored_metric_discrepancies': discrepancies, 'episode_comparisons': comparisons}
    Path('reports/week7_rescore_validation.json').write_text(json.dumps(report, indent=2) + '\n')
    snapshot = Path('reports/runs/week7-gpu-rescore')
    snapshot.mkdir(parents=True, exist_ok=True)
    for name in ('RESULTS_week7_rescore.md', 'week7_rescore.json'):
        source = Path('reports') / name
        target = snapshot / name
        if target.exists():
            assert target.read_bytes() == source.read_bytes()
        else:
            shutil.copyfile(source, target)
    manifest = {'archive_sha256': sha(archive), 'files': {name: sha(snapshot / name) for name in ('RESULTS_week7_rescore.md', 'week7_rescore.json')}}
    (snapshot / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'verified_sources': len(result['source_sha256']), 'source_snapshot': source_snapshot, 'verified_documents': len(rows), 'verified_ablations': len(comparisons), 'metric_discrepancies': discrepancies}, indent=2))


if __name__ == '__main__':
    main()
