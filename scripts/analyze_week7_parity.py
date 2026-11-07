"""Independently verify returned parity vectors, tokens, metadata and scores.

Run from repo root: PYTHONPATH=src .venv/bin/python scripts/analyze_week7_parity.py
No model loads, calibration, or probe writes occur.
"""
import gzip
import hashlib
import json
import math
from pathlib import Path

from smaip.probes.dataset import prepare_records
from evidence_snapshot import assert_sources


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def compare(reference, candidate, thresholds, tolerance):
    assert set(reference) == set(candidate)
    result = {kind: {'max_abs_score_delta': 0.0, 'score_tolerance_exceeded': [], 'decision_flips': []} for kind in thresholds}
    for record_id in sorted(reference):
        for kind, threshold in thresholds.items():
            a, b = reference[record_id][kind], candidate[record_id][kind]
            assert math.isfinite(a) and math.isfinite(b) and 0 <= a <= 1 and 0 <= b <= 1
            delta = abs(a - b)
            result[kind]['max_abs_score_delta'] = max(result[kind]['max_abs_score_delta'], delta)
            if delta > tolerance:
                result[kind]['score_tolerance_exceeded'].append(record_id)
            if (a >= threshold) != (b >= threshold):
                result[kind]['decision_flips'].append({'id': record_id, 'reference': a, 'candidate': b, 'threshold': threshold})
    return result


def main():
    snapshot = Path('reports/runs/week7-gpu-parity')
    manifest = json.loads((snapshot / 'manifest.json').read_text())
    assert sha('reports/week7-parity-results.tar.gz') == manifest['archive_sha256']
    for name, digest in manifest['files'].items():
        assert sha(snapshot / name) == digest
    r = json.loads((snapshot / 'parity.json').read_text())
    m = r['metadata']
    assert (m['backend'], m['model_id'], m['device'], m['subset'], m['repeats']) == ('hf', 'Qwen/Qwen2.5-3B-Instruct', 'cuda', 'full', 2)
    assert sha('scripts/gpu/probe_parity.py') == m['script_sha256']
    root = Path('src/smaip')
    source_snapshot = assert_sources(m['source_sha256'])
    assert sha('reports/week7_rescore.json') == m['prior_rescore_sha256']
    records = {record.id: record for record in prepare_records('full')}
    assert len(records) == len(m['records']) == len({x['id'] for x in m['records']}) == 57
    for row in m['records']:
        record = records[row['id']]
        assert (row['label'], row['split'], row['text_sha256']) == (record.label, record.split, hashlib.sha256(record.text.encode()).hexdigest())
    payloads = {}
    for kind, digest in m['probe_sha256'].items():
        path = Path('artifacts/probes') / (kind + '.json')
        assert sha(path) == digest
        payloads[kind] = json.loads(path.read_text())
        assert payloads[kind]['threshold'] == m['thresholds'][kind]
    expected_conditions = {f'{mode}_repeat{repeat}' for mode in ('serving', 'batch1', 'batch4') for repeat in (1, 2)}
    assert set(r['conditions']) == expected_conditions
    reference = r['conditions']['serving_repeat1']['scores']
    for name, condition in r['conditions'].items():
        assert set(condition['scores']) == set(records)
        assert compare(reference, condition['scores'], m['thresholds'], m['score_tolerance']) == r['comparisons_to_serving_repeat1'][name]
        for kind in payloads:
            for split in ('train', 'val', 'test'):
                rows = [key for key in records if records[key].split == split]
                positive = [condition['scores'][key][kind] for key in rows if records[key].label == 1]
                negative = [condition['scores'][key][kind] for key in rows if records[key].label == 0]
                tp = sum(x >= m['thresholds'][kind] for x in positive)
                fp = sum(x >= m['thresholds'][kind] for x in negative)
                fn = len(positive) - tp
                f1 = 2 * tp / (2 * tp + fp + fn) if tp else 0.0
                auc = sum((a > b) + 0.5 * (a == b) for a in positive for b in negative) / (len(positive) * len(negative))
                block = r['split_metrics'][name][kind][split]
                for value, expected in ((auc, block['auroc']), (f1, block['f1']), (tp / len(positive), block['tpr']), (fp / len(negative), block['fpr_at_tpr'])):
                    assert math.isclose(value, expected, abs_tol=1e-12)
    prior = json.loads(Path('reports/week7_rescore.json').read_text())
    prior_scores = {row['id']: {kind: row[kind] for kind in payloads} for row in prior['document_scores']}
    assert compare(prior_scores, reference, m['thresholds'], m['score_tolerance']) == r['comparison_of_serving_to_prior_rescore']
    tokens = json.loads((snapshot / 'tokens.json').read_text())
    mismatches = []
    for key in records:
        for mode in ('batch1', 'batch4'):
            row = tokens[mode][key]
            assert len(row['input_ids']) == len(row['attention_mask'])
            assert all(x in (0, 1) for x in row['attention_mask'])
            assert [token for token, keep in zip(row['input_ids'], row['attention_mask']) if keep] == row['nonpadding_input_ids']
        a, b = tokens['batch1'][key], tokens['batch4'][key]
        if (a['nonpadding_input_ids'], a['rendered_sha256']) != (b['nonpadding_input_ids'], b['rendered_sha256']):
            mismatches.append(key)
    assert mismatches == m['token_mismatches']
    vectors = {}
    max_score_error = 0.0
    with gzip.open(snapshot / 'vectors.jsonl.gz', 'rt') as handle:
        for line in handle:
            row = json.loads(line)
            key = (row['condition'], row['id'])
            assert key not in vectors
            assert row['condition'] in expected_conditions and row['id'] in records
            vectors[key] = row['vectors']
            assert set(row['vectors']) == set(payloads)
            for kind, vector in row['vectors'].items():
                payload = payloads[kind]
                assert len(vector) == len(payload['weights']) == len(payload['mean']) == len(payload['std']) == 2048
                assert all(math.isfinite(x) for x in vector)
                z = payload['bias']
                for x, weight, mean, std in zip(vector, payload['weights'], payload['mean'], payload['std']):
                    z += weight * ((x - mean) / std)
                probability = 1 / (1 + math.exp(-z)) if z >= 0 else math.exp(z) / (1 + math.exp(z))
                error = abs(probability - r['conditions'][row['condition']]['scores'][row['id']][kind])
                max_score_error = max(max_score_error, error)
                assert error < 1e-12
    assert len(vectors) == len(expected_conditions) * len(records) == 342
    deltas = {}
    for name in expected_conditions:
        deltas[name] = {}
        for kind in payloads:
            deltas[name][kind] = max(abs(a - b) for key in records
                                     for a, b in zip(vectors[('serving_repeat1', key)][kind], vectors[(name, key)][kind]))
    assert deltas == r['max_abs_vector_deltas']
    repeat_equal = {mode: all(vectors[(f'{mode}_repeat1', key)] == vectors[(f'{mode}_repeat2', key)] for key in records)
                    for mode in ('serving', 'batch1', 'batch4')}
    summary = {'assessment': 'Reproducible batch-size-dependent feature difference; original threshold crossing reproduced',
               'archive_sha256': manifest['archive_sha256'], 'source_snapshot': source_snapshot, 'verified_source_files': len(m['source_sha256']),
               'verified_documents': len(records), 'verified_conditions': len(expected_conditions),
               'verified_vector_rows': len(vectors), 'verified_scores': len(vectors) * 2,
               'maximum_recomputed_score_error': max_score_error, 'exact_vector_repeat_matches': repeat_equal,
               'token_mismatches': mismatches,
               'truncated_records': {mode: sum(row['was_truncated'] for row in rows.values()) for mode, rows in tokens.items()},
               'comparisons_to_serving_repeat1': r['comparisons_to_serving_repeat1'],
               'prior_rescore_comparison': r['comparison_of_serving_to_prior_rescore'],
               'snapshot': m['snapshot'], 'runtime': m['runtime'], 'gpu': m['gpu'],
               'thresholds_unchanged': m['thresholds']}
    (snapshot / 'validation.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps({key: summary[key] for key in ('assessment', 'verified_vector_rows', 'verified_scores', 'maximum_recomputed_score_error', 'exact_vector_repeat_matches', 'token_mismatches', 'truncated_records')}, indent=2))


if __name__ == '__main__':
    main()
