"""CPU-only research diagnostics; preserve all saved probes and thresholds.

The ROC diagnostic uses already observed external labels descriptively. Its
thresholds are not deployment calibration or a fresh independent evaluation.
Acceptance examples are synthetic software counterexamples, not model evidence.
"""
import hashlib
import json
from math import exp, log1p, sqrt
from pathlib import Path

from smaip.eval.acceptance import assess
from smaip.eval.contract import evaluation_matrix
from smaip.probes.logistic import predict_proba, standardize


OUTPUT = Path('reports/research/2026-10-31')


def write(name, value):
    (OUTPUT / name).write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def optimizer_diagnostics():
    root = Path('reports/runs/probe-development-01/collection')
    records = [json.loads(line) for line in (root / 'corpus.jsonl').read_text().splitlines()]
    rows = [json.loads(line) for line in (root / 'vectors.jsonl').read_text().splitlines()]
    result = {'scope': 'Training-only coefficient/loss replay from saved real vectors. No Qwen loaded; no calibration/test fitting or artifact changes.'}
    for pool in ('last', 'mean'):
        selected = [(r, v) for r, v in zip(records, rows) if r['split'] == 'train']
        x, _, _ = standardize([v['features'][pool]['18'] for _, v in selected])
        labels = [r['label'] for r, _ in selected]
        count, dim = len(labels), len(x[0])
        weights, bias, trace = [0.] * dim, 0., []
        for step in range(401):
            if step in (0, 1, 2, 5, 10, 20, 50, 100, 200, 300, 390, 391, 392, 399, 400):
                logits = [bias + sum(a * b for a, b in zip(weights, row)) for row in x]
                loss = sum(max(z, 0) + log1p(exp(-abs(z))) - label * z for z, label in zip(logits, labels)) / count
                loss += .05 * sum(w * w for w in weights) / 2
                scores = [predict_proba(row, weights, bias) for row in x]
                trace.append({'step': step, 'loss': loss, 'weight_norm': sqrt(sum(w * w for w in weights)),
                              'correct': sum(int(p >= .5) == y for p, y in zip(scores, labels)),
                              'min_score': min(scores), 'max_score': max(scores)})
            if step == 400:
                break
            grad, grad_bias = [0.] * dim, 0.
            for row, label in zip(x, labels):
                error = predict_proba(row, weights, bias) - label
                for j, value in enumerate(row):
                    grad[j] += error * value
                grad_bias += error
            weights = [w - .3 * (g / count + .05 * w) for w, g in zip(weights, grad)]
            bias -= .3 * grad_bias / count
        result[pool] = {'dimensions': dim, 'training_records': count, 'trace': trace}
    write('optimizer_diagnostics.json', result)


def gate_counterexamples():
    report = {'schema_version': 2, 'kind': 'brd-evidence', 'backend': 'hf-local',
              'model_id': 'synthetic-test-only', 'run_id': 'synthetic-counterexample-not-a-real-run',
              'group_source_family_disjoint': True,
              'rows': [{'name': c.name, 'utility': 1., 'asr': 0. if c.name == 'full-stack' else .5, 'fpr': 0.}
                       for c in evaluation_matrix()],
              'probe': {'calibration_negatives': 1000, 'test_negatives': 1000,
                        'threshold_source': 'independent-calibration', 'fpr_budget': .01,
                        'test_auroc': .5, 'test_tpr': 0., 'test_fpr': 0.},
              'adaptive_evaluation_measured': True,
              'performance': {'p95_ms': 1., 'max_p95_ms': 2.,
                              'usd_per_1k_generated_tokens': .01, 'max_usd_per_1k_generated_tokens': .02}}
    result = {'kind': 'software-acceptance-counterexamples', 'measured_model_quality': False,
              'description': 'Synthetic records exercise missing acceptance constraints. They are not reported experimental results.',
              'zero_recall_probe': {'input': report, 'gate_result': assess(report)}}
    low = json.loads(json.dumps(report))
    for row in low['rows']:
        row['utility'] = 0.
    result['zero_absolute_agent_utility'] = {'input': low, 'gate_result': assess(low)}
    write('acceptance_counterexamples.json', result)


def ranking_diagnostics():
    predictions = json.loads(Path('reports/runs/external-frozen-01/evaluation/predictions.json').read_text())
    result = {}
    for name in ('linear.json', 'activation.json'):
        rows = [row for row in predictions if row['probe'] == name]
        assert sum(row['label'] == 0 for row in rows) == sum(row['label'] == 1 for row in rows) == 400
        ordered = sorted(rows, key=lambda row: row['score'], reverse=True)
        tp = fp = i = 0
        best = {'tp': 0, 'fp': 0, 'tpr': 0., 'fpr': 0.}
        while i < len(ordered):
            score = ordered[i]['score']
            j = i
            while j < len(ordered) and ordered[j]['score'] == score:
                tp += ordered[j]['label'] == 1
                fp += ordered[j]['label'] == 0
                j += 1
            if fp <= 4 and tp > best['tp']:
                best = {'tp': tp, 'fp': fp, 'tpr': tp / 400, 'fpr': fp / 400,
                        'descriptive_test_selected_threshold': score}
            i = j
        pairs = {}
        for row in rows:
            pairs.setdefault(row['pair_id'], {})[row['label']] = row['score']
        result[name] = {'kind': 'posthoc_descriptive_ranking_diagnostic', 'not_deployment_calibration': True,
                        'test_ROC_best_tpr_at_empirical_fpr_at_most_1pct': best,
                        'pairs_injected_score_higher_than_clean': sum(p[1] > p[0] for p in pairs.values()),
                        'pairs': len(pairs)}
    write('external_ranking_diagnostics.json', result)


if __name__ == '__main__':
    OUTPUT.mkdir(parents=True, exist_ok=True)
    optimizer_diagnostics()
    gate_counterexamples()
    ranking_diagnostics()
    write('diagnostic_manifest.json', {'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
          'kind': 'cpu-research-diagnostics', 'new_gpu_run': False, 'saved_models_modified': False,
          'inputs': {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in [
              Path('reports/runs/probe-development-01/collection/corpus.jsonl'),
              Path('reports/runs/probe-development-01/collection/vectors.jsonl'),
              Path('reports/runs/external-frozen-01/evaluation/predictions.json')]}})
    print('Saved CPU research diagnostics to', OUTPUT)
