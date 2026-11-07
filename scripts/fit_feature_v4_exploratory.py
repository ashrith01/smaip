#!/usr/bin/env python3
"""Exploratory linear-probe fit on unreviewed V4 features.

NVIDIA groups determine feature selection by three-fold out-of-fold scores.
LLMail is scored once with the selected feature as a source-transfer
diagnostic. No operating threshold, deployment probe, calibration or final
accuracy claim is produced.
"""

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sys
import tarfile
import time

os.environ['OPENBLAS_NUM_THREADS'] = '1'
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
COLLECTION_SHA256 = 'eb745c1b9615a69067850e6969a18122bd2f701d3e1e5eacbd8f7ba81f46dbd4'
CANDIDATE_SHA256 = '842b73014b1fc071cf9a61f1daccdd144be899ebf427970b7c8ea3bc539aec9e'
PROTOCOL_FINGERPRINT = 'ddb4e1c05d9f25100331ea78eec8cc36c47cef4866f57417e2f30607272df463'
NVIDIA = 'nvidia/Nemotron-RL-Agentic-Indirect-Prompt-Injection-v1'
LLMAIL = 'microsoft/llmail-inject-challenge'
LAYERS = (6, 18, 30)
POOLS = ('content_last', 'content_mean', 'assistant_boundary')
SEED = 'smaip-v4-exploratory-01-group-cv-source-transfer'
L2 = 0.05


def sha(value):
    return hashlib.sha256(value).hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sigmoid(logits):
    return 1.0 / (1.0 + np.exp(-np.clip(logits, -50.0, 50.0)))


def objective(z, y, weights, bias, l2):
    logits = z @ weights + bias
    return float(np.mean(np.logaddexp(0.0, logits) - y * logits) +
                 0.5 * l2 * np.dot(weights, weights))


def fit_logistic(train_x, train_y, *, l2=L2, max_steps=300):
    """Deterministic full-batch logistic fit with train-only z-score/line search."""
    x = np.asarray(train_x, dtype=np.float64)
    y = np.asarray(train_y, dtype=np.float64)
    require(x.ndim == 2 and x.shape[0] == y.size and x.shape[0] > 0 and
            set(np.unique(y)).issubset({0.0, 1.0}) and len(np.unique(y)) == 2,
            'fitting requires both labels and consistent vectors')
    mean = x.mean(axis=0)
    std = x.std(axis=0)
    std[std < 1e-8] = 1.0
    z = (x - mean) / std
    weights = np.zeros(x.shape[1], dtype=np.float64)
    bias = 0.0
    loss = objective(z, y, weights, bias, l2)
    trace = [{'step': 0, 'objective': loss}]
    steps_run = 0
    for step in range(1, max_steps + 1):
        errors = sigmoid(z @ weights + bias) - y
        grad_w = z.T @ errors / len(y) + l2 * weights
        grad_b = float(errors.mean())
        grad_norm_sq = float(np.dot(grad_w, grad_w) + grad_b * grad_b)
        if grad_norm_sq < 1e-10:
            break
        step_size = 1.0
        accepted = False
        for _ in range(24):
            next_w = weights - step_size * grad_w
            next_b = bias - step_size * grad_b
            next_loss = objective(z, y, next_w, next_b, l2)
            if next_loss <= loss - 1e-4 * step_size * grad_norm_sq:
                accepted = True
                break
            step_size *= 0.5
        if not accepted:
            break
        weights, bias, loss = next_w, next_b, next_loss
        steps_run = step
        if step in (1, 10, 50, 100, 200, 300):
            trace.append({'step': step, 'objective': loss, 'gradient_norm': math.sqrt(grad_norm_sq),
                          'step_size': step_size})
    require(np.all(np.isfinite(weights)) and math.isfinite(bias) and math.isfinite(loss),
            'nonfinite fitted model')
    return {'mean': mean, 'std': std, 'weights': weights, 'bias': bias,
            'steps_run': steps_run, 'objective': loss, 'trace': trace,
            'weights_l2_norm': float(np.linalg.norm(weights))}


def predict(x, model):
    z = (np.asarray(x, dtype=np.float64) - model['mean']) / model['std']
    return sigmoid(z @ model['weights'] + model['bias'])


def auroc(scores, labels):
    labels = np.asarray(labels, dtype=np.int8)
    scores = np.asarray(scores, dtype=np.float64)
    positives, negatives = int(labels.sum()), int(len(labels) - labels.sum())
    require(positives > 0 and negatives > 0, 'AUROC requires both classes')
    order = np.argsort(scores, kind='stable')
    sorted_scores, sorted_labels = scores[order], labels[order]
    rank_sum = 0.0
    cursor = 0
    while cursor < len(scores):
        end = cursor + 1
        while end < len(scores) and sorted_scores[end] == sorted_scores[cursor]:
            end += 1
        rank_sum += float(sorted_labels[cursor:end].sum()) * (cursor + 1 + end) / 2.0
        cursor = end
    return (rank_sum - positives * (positives + 1) / 2.0) / (positives * negatives)


def empirical_low_fpr(scores, labels):
    """Post-hoc ranking diagnostic; the returned cutoff is never deployed."""
    scores = np.asarray(scores, dtype=np.float64)
    labels = np.asarray(labels, dtype=np.int8)
    negative = scores[labels == 0]
    positive = scores[labels == 1]
    allowed = int(math.floor(0.01 * len(negative)))
    require(allowed < len(negative) and len(positive) > 0 and
            np.all(np.isfinite(scores)), 'insufficient ranking observations')
    # Among feasible score cutoffs, maximize true positives and then minimize
    # false positives. The earlier exploratory r1 diagnostic always chose the
    # cutoff just above the (allowed+1)th negative and could report four/two
    # avoidable false positives even under perfect class separation.
    tp, fp = 0, 0
    for cutoff in np.unique(positive):
        candidate_fp = int(np.count_nonzero(negative >= cutoff))
        if candidate_fp > allowed:
            continue
        candidate_tp = int(np.count_nonzero(positive >= cutoff))
        if candidate_tp > tp or (candidate_tp == tp and candidate_fp < fp):
            tp, fp = candidate_tp, candidate_fp
    return {'allowed_false_positives': allowed, 'observed_false_positives': fp,
            'positives_above_post_hoc_cutoff': tp, 'attack_count': len(positive),
            'benign_count': len(negative), 'descriptive_tpr': tp / len(positive),
            'descriptive_fpr': fp / len(negative)}


class Groups:
    def __init__(self, count):
        self.parent = list(range(count))

    def root(self, index):
        while self.parent[index] != index:
            self.parent[index] = self.parent[self.parent[index]]
            index = self.parent[index]
        return index

    def union(self, a, b):
        a, b = self.root(a), self.root(b)
        if a != b:
            self.parent[b] = a


def make_folds(records):
    """Keep context, pair, author, exact text and near duplicates connected."""
    from smaip.probes.external_v2 import shingles, similar
    require(all(r['source_origin'] == NVIDIA and not r['previously_observed'] for r in records),
            'NVIDIA fitting rows differ from unused-context queue')
    groups = Groups(len(records))
    for field in ('source_context_id', 'pair_id', 'template_id', 'author_id', 'generation_batch'):
        seen = {}
        for index, row in enumerate(records):
            value = row[field]
            if value is None:
                continue
            key = (row['source_origin'], value)
            if key in seen:
                groups.union(index, seen[key])
            else:
                seen[key] = index
    seen = {}
    for index, row in enumerate(records):
        normalized = re.sub(r'\s+', ' ', row['untrusted_text'].casefold()).strip()
        if normalized in seen:
            groups.union(index, seen[normalized])
        else:
            seen[normalized] = index
    tokens = [shingles(r['untrusted_text']) for r in records]
    for index, current in enumerate(tokens):
        for previous in range(index):
            if groups.root(index) != groups.root(previous) and similar(current, tokens[previous]):
                groups.union(index, previous)
    components = defaultdict(list)
    for index in range(len(records)):
        components[groups.root(index)].append(index)
    strata = {0: [], 1: []}
    for component in components.values():
        positive = int(any(records[i]['label'] == 1 for i in component))
        strata[positive].append(component)
    folds = np.full(len(records), -1, dtype=np.int8)
    component_manifest = []
    for stratum in (0, 1):
        ordered = sorted(strata[stratum], key=lambda component:
            sha((SEED + '|' + '|'.join(sorted(records[i]['id'] for i in component))).encode()))
        for index, component in enumerate(ordered):
            fold = index % 3
            for row_index in component:
                folds[row_index] = fold
            component_manifest.append({'fold': fold, 'ids': sorted(records[i]['id'] for i in component),
                                       'labels': dict(Counter(records[i]['label'] for i in component))})
    require(np.all(folds >= 0), 'unassigned fitting row')
    for fold in range(3):
        labels = [records[i]['label'] for i in range(len(records)) if folds[i] == fold]
        require(0 < sum(labels) < len(labels), 'fold lacks a class')
    # Keep the second source genuinely separate; identical and near-duplicate
    # cross-source documents are checked by the caller before fitting.
    return folds, component_manifest


def load_data():
    collection_path = ROOT / '.local-data/returned/feature-v4-collection-01.tar.gz'
    candidate_path = ROOT / '.local-data/corpus-review-01/prepared/candidates.jsonl'
    audit_path = ROOT / '.local-data/returned/feature-v4-collection-01.audit.json'
    require(sha(collection_path.read_bytes()) == COLLECTION_SHA256 and
            sha(candidate_path.read_bytes()) == CANDIDATE_SHA256,
            'feature collection or candidate source differs')
    audit = json.loads(audit_path.read_text())
    require(audit['status'] == 'verified' and audit['returned_archive_sha256'] == COLLECTION_SHA256 and
            audit['candidate_reviewed'] is False and audit['training_performed'] is False,
            'feature evidence audit differs')
    candidates = [json.loads(line) for line in candidate_path.read_text().splitlines() if line.strip()]
    candidates = {r['id']: r for r in candidates if r['label_scope'] == 'task-document'}
    require(len(candidates) == 1012, 'task candidate count differs')
    with tarfile.open(collection_path, 'r:gz') as archive:
        root = 'feature-collection-01/'
        summary = json.load(archive.extractfile(root + 'summary.json'))
        metadata = [json.loads(line) for line in archive.extractfile(root + 'rows.jsonl').read().splitlines()]
        data = archive.extractfile(root + 'vectors.f32').read()
    require(summary['status'] == 'completed' and summary['protocol_fingerprint'] == PROTOCOL_FINGERPRINT and
            summary['completed_count'] == 1012 and len(metadata) == 1012 and
            len(data) == 1012 * 9 * 2048 * 4, 'incomplete V4 feature matrix')
    matrix = np.frombuffer(data, dtype='<f4').reshape(1012, 3, 3, 2048)
    require(np.all(np.isfinite(matrix)), 'nonfinite saved vectors')
    records = []
    for position, row in enumerate(metadata):
        candidate = candidates[row['id']]
        require(row['protocol_fingerprint'] == PROTOCOL_FINGERPRINT and
                row['task_sha256'] == sha(candidate['trusted_task'].encode()) and
                row['text_sha256'] == sha(candidate['untrusted_text'].encode()) and
                row['offset_bytes'] == position * 9 * 2048 * 4 and
                row['source_origin'] == candidate['source_origin'], 'feature/candidate identity differs')
        records.append(candidate)
    require({r['source_origin'] for r in records} == {NVIDIA, LLMAIL}, 'unexpected source stream')
    return matrix, records, summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / '.local-data/exploratory-fit-v4-02')
    args = parser.parse_args()
    output = args.output.resolve()
    require(output.is_relative_to((ROOT / '.local-data').resolve()) and not output.exists(),
            'choose a fresh ignored .local-data output')
    started = time.monotonic()
    matrix, records, collection = load_data()
    nv_indices = [i for i, row in enumerate(records) if row['source_origin'] == NVIDIA]
    ll_indices = [i for i, row in enumerate(records) if row['source_origin'] == LLMAIL]
    nv_records = [records[i] for i in nv_indices]
    ll_records = [records[i] for i in ll_indices]
    folds, components = make_folds(nv_records)
    # Check even the held source for close duplicates of fitting texts.
    from smaip.probes.external_v2 import shingles, similar
    nv_shingles = [shingles(r['untrusted_text']) for r in nv_records]
    ll_shingles = [shingles(r['untrusted_text']) for r in ll_records]
    require(not any(similar(a, b) for a in nv_shingles for b in ll_shingles),
            'cross-source near-duplicate content would contaminate transfer diagnostic')
    y_nv = np.array([r['label'] for r in nv_records], dtype=np.int8)
    y_ll = np.array([r['label'] for r in ll_records], dtype=np.int8)
    require((len(nv_records), int(y_nv.sum()), len(ll_records), int(y_ll.sum())) == (681, 228, 331, 128),
            'source label counts differ')
    output.mkdir(parents=True)
    write_json(output / 'split.json', {'kind': 'three-fold-grouped-NVIDIA-development',
        'seed': SEED, 'source': NVIDIA, 'components': components,
        'fold_counts': {str(fold): dict(Counter(int(y_nv[i]) for i in range(len(y_nv)) if folds[i] == fold))
                        for fold in range(3)},
        'held_source': LLMAIL,
        'reviewed': False, 'independent_final_test': False})
    feature_results, predictions = [], []
    for layer_index, layer in enumerate(LAYERS):
        for pool_index, pool in enumerate(POOLS):
            feature = f'{pool}/{layer}'
            x_nv = matrix[nv_indices, layer_index, pool_index, :]
            scores = np.full(len(nv_indices), np.nan, dtype=np.float64)
            fit_diagnostics = []
            for fold in range(3):
                train = folds != fold
                select = folds == fold
                model = fit_logistic(x_nv[train], y_nv[train])
                scores[select] = predict(x_nv[select], model)
                fit_diagnostics.append({'fold': fold, 'training_rows': int(train.sum()),
                    'scored_rows': int(select.sum()), 'steps_run': model['steps_run'],
                    'objective': model['objective'], 'weights_l2_norm': model['weights_l2_norm'],
                    'trace': model['trace']})
            require(np.all(np.isfinite(scores)), 'missing out-of-fold score')
            metric = {'feature': feature, 'nvidia_oof_auroc': auroc(scores, y_nv),
                      'nvidia_oof_post_hoc_low_fpr': empirical_low_fpr(scores, y_nv),
                      'fits': fit_diagnostics}
            feature_results.append(metric)
            predictions.extend({'id': row['id'], 'source': NVIDIA, 'fold': int(folds[i]),
                                'feature': feature, 'label': int(y_nv[i]), 'score': float(scores[i])}
                               for i, row in enumerate(nv_records))
            print(feature, 'OOF AUROC', round(metric['nvidia_oof_auroc'], 4),
                  'descriptive low-FPR TPR', round(metric['nvidia_oof_post_hoc_low_fpr']['descriptive_tpr'], 4),
                  flush=True)
    chosen = max(feature_results, key=lambda r: (r['nvidia_oof_post_hoc_low_fpr']['descriptive_tpr'],
                                                  r['nvidia_oof_auroc'], -LAYERS.index(int(r['feature'].split('/')[1])),
                                                  -POOLS.index(r['feature'].split('/')[0])))
    pool_name, layer_name = chosen['feature'].split('/')
    li, pi = LAYERS.index(int(layer_name)), POOLS.index(pool_name)
    final_model = fit_logistic(matrix[nv_indices, li, pi, :], y_nv)
    ll_scores = predict(matrix[ll_indices, li, pi, :], final_model)
    require(np.all(np.isfinite(ll_scores)), 'nonfinite held-source score')
    ll_metric = {'auroc': auroc(ll_scores, y_ll),
                 'post_hoc_low_fpr': empirical_low_fpr(ll_scores, y_ll),
                 'attack_count': int(y_ll.sum()), 'benign_count': int(len(y_ll) - y_ll.sum())}
    predictions.extend({'id': row['id'], 'source': LLMAIL, 'fold': None,
                        'feature': chosen['feature'], 'label': int(y_ll[i]), 'score': float(ll_scores[i])}
                       for i, row in enumerate(ll_records))
    model_payload = {'kind': 'exploratory-linear-v4-not-for-serving', 'feature': chosen['feature'],
        'protocol_fingerprint': PROTOCOL_FINGERPRINT, 'source_collection_sha256': COLLECTION_SHA256,
        'fit_script_sha256': sha(Path(__file__).read_bytes()),
        'training_source': NVIDIA, 'training_ids': [r['id'] for r in nv_records],
        'L2': L2, 'optimizer': 'full-batch logistic loss plus L2 with Armijo backtracking',
        'mean': final_model['mean'].tolist(), 'std': final_model['std'].tolist(),
        'weights': final_model['weights'].tolist(), 'bias': final_model['bias'],
        'steps_run': final_model['steps_run'], 'objective': final_model['objective'],
        'threshold': None, 'serving_enabled': False, 'human_reviewed': False,
        'independent_final_test': False}
    write_json(output / 'exploratory-model.json', model_payload)
    (output / 'predictions.jsonl').write_text(''.join(json.dumps(r, allow_nan=False) + '\n' for r in predictions))
    summary = {'status': 'completed', 'kind': 'feature-v4-exploratory-source-transfer',
        'scope': 'unreviewed development only', 'feature_collection_sha256': COLLECTION_SHA256,
        'candidate_source_sha256': CANDIDATE_SHA256, 'protocol_fingerprint': PROTOCOL_FINGERPRINT,
        'fit_script_sha256': sha(Path(__file__).read_bytes()),
        'nvidia_rows': len(nv_records), 'nvidia_attack_rows': int(y_nv.sum()),
        'nvidia_group_components': len(components), 'llmail_rows': len(ll_records),
        'llmail_attack_rows': int(y_ll.sum()), 'selected_feature': chosen['feature'],
        'selection_rule': 'maximize pooled grouped-OOF post-hoc TPR at <=1% empirical FPR, minimizing FP among equal-TP cutoffs; tie-break AUROC and fixed layer/pool order',
        'selection_metric': {k: v for k, v in chosen.items() if k != 'fits'},
        'llmail_source_transfer': ll_metric,
        'feature_comparison': [{k: v for k, v in r.items() if k != 'fits'} for r in feature_results],
        'final_fit': {'steps_run': final_model['steps_run'], 'objective': final_model['objective'],
                      'weights_l2_norm': final_model['weights_l2_norm']},
        'runtime': {'python': os.sys.version, 'numpy': np.__version__,
                    'openblas_threads': os.environ['OPENBLAS_NUM_THREADS'],
                    'elapsed_seconds': time.monotonic() - started},
        'training_performed': True, 'base_model_finetuned': False,
        'human_label_review': False, 'threshold_selected': False,
        'independent_final_test': False, 'release_eligible': False,
        'limitations': ['Upstream/synthetic labels have not been human-adjudicated.',
                        'Only NVIDIA was used for fitting and feature selection.',
                        'LLMail is a single source with 128 connected attack rows from two scenarios/five teams.',
                        'Reported <=1% FPR points are post-hoc empirical rankings, not calibrated operating points.',
                        'Feature choice consumes development labels; no independent final-test claim.']}
    write_json(output / 'summary.json', summary)
    write_json(output / 'files-sha256.json', {p.name: sha(p.read_bytes()) for p in sorted(output.iterdir())
                                            if p.is_file() and p.name != 'files-sha256.json'})
    print(json.dumps({'selected_feature': chosen['feature'], 'nvidia_oof_auroc': chosen['nvidia_oof_auroc'],
                      'nvidia_oof_descriptive_tpr': chosen['nvidia_oof_post_hoc_low_fpr']['descriptive_tpr'],
                      'llmail_auroc': ll_metric['auroc'],
                      'llmail_descriptive_tpr': ll_metric['post_hoc_low_fpr']['descriptive_tpr'],
                      'output': str(output)}, indent=2))


if __name__ == '__main__':
    main()
