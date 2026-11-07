#!/usr/bin/env python3
"""Save and verify a development-only V4 linear probe from archived features.

Qwen stays frozen. The fit uses source labels from cleaned NVIDIA rows; LLMail
is an already observed source-transfer diagnostic, not an independent test.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path

import fit_feature_v4_exploratory as fit


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / '.local-data/feature-v4-solo-audit-01/candidate-manifest.jsonl'
MANIFEST_SHA = '8952a310a6e47663c15416909dbe20a9385939429c4410afafb396dd6785b7ae'
SENSITIVITY = ROOT / '.local-data/feature-v4-solo-sensitivity-01/summary.json'
SENSITIVITY_SHA = '60aa46bdaf0161f63679fa554aeb37d0c238bec5d3c3cb816c89f7b1bf49073d'
OUTPUT = ROOT / '.local-data/feature-v4-solo-probe-01'
FEATURE = 'content_mean/18'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read_jsonl(path):
    return [json.loads(line) for line in path.read_bytes().splitlines() if line.strip()]


def write_private(path, raw):
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'wb') as file:
        file.write(raw)
        file.flush()
        os.fsync(file.fileno())


def json_bytes(value):
    return (json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n').encode()


def load_inputs():
    require(sha(MANIFEST.read_bytes()) == MANIFEST_SHA, 'cleaned manifest differs')
    require(sha(SENSITIVITY.read_bytes()) == SENSITIVITY_SHA, 'fixed-feature sensitivity differs')
    sensitivity = json.loads(SENSITIVITY.read_text())
    require(sensitivity['fixed_feature'] == FEATURE and sensitivity['selection_repeated'] is False and
            sensitivity['threshold_selected'] is False and sensitivity['serving_enabled'] is False,
            'sensitivity policy differs')
    manifest = read_jsonl(MANIFEST)
    selected = {row['candidate_id']: row for row in manifest
                if row['status'] == 'source_label_development_only'}
    require(len(manifest) == 1012 and len(selected) == 968 and
            [row['candidate_id'] for row in manifest if row['status'] == 'quarantined'] == ['nvidia-12-clean'],
            'cleaned selection differs')
    matrix, records, _ = fit.load_data()
    nv = [i for i, row in enumerate(records) if row['id'] in selected and row['source_origin'] == fit.NVIDIA]
    ll = [i for i, row in enumerate(records) if row['id'] in selected and row['source_origin'] == fit.LLMAIL]
    require(len(nv) == 680 and len(ll) == 288 and
            {records[i]['id'] for i in nv + ll} == set(selected), 'feature/manifest membership differs')
    for i in nv + ll:
        row, entry = records[i], selected[records[i]['id']]
        require(row['label'] == entry['source_label'] and row['source_origin'] == entry['source_origin'],
                'candidate label or source differs')
    return matrix, records, nv, ll, sensitivity


def score_from_saved(model, x):
    mean = fit.np.asarray(model['mean'], dtype=fit.np.float64)
    std = fit.np.asarray(model['std'], dtype=fit.np.float64)
    weights = fit.np.asarray(model['weights'], dtype=fit.np.float64)
    require(mean.shape == std.shape == weights.shape == (2048,) and
            fit.np.all(fit.np.isfinite(mean)) and fit.np.all(fit.np.isfinite(std)) and
            fit.np.all(fit.np.isfinite(weights)) and fit.np.all(std > 0),
            'saved model dimensions or values differ')
    logits = ((fit.np.asarray(x, dtype=fit.np.float64) - mean) / std) @ weights + model['bias']
    return 1.0 / (1.0 + fit.np.exp(-fit.np.clip(logits, -50.0, 50.0)))


def train():
    require(not OUTPUT.exists(), 'preserve probe 01; version any retraining')
    matrix, records, nv, ll, sensitivity = load_inputs()
    li, pi = fit.LAYERS.index(18), fit.POOLS.index('content_mean')
    x_nv, x_ll = matrix[nv, li, pi, :], matrix[ll, li, pi, :]
    y_nv = fit.np.asarray([records[i]['label'] for i in nv], dtype=fit.np.int8)
    y_ll = fit.np.asarray([records[i]['label'] for i in ll], dtype=fit.np.int8)
    require((int(y_nv.sum()), int(y_ll.sum())) == (228, 128), 'training labels differ')
    trained = fit.fit_logistic(x_nv, y_nv)
    model = {
        'kind': 'feature-v4-solo-source-label-probe-01',
        'scope': 'development only; not a validated injection detector',
        'base_model': fit.MODEL if hasattr(fit, 'MODEL') else 'Qwen/Qwen2.5-3B-Instruct',
        'base_model_finetuned': False,
        'feature': FEATURE, 'feature_protocol_fingerprint': fit.PROTOCOL_FINGERPRINT,
        'feature_collection_sha256': fit.COLLECTION_SHA256,
        'candidate_source_sha256': fit.CANDIDATE_SHA256,
        'cleaned_manifest_sha256': MANIFEST_SHA,
        'fixed_feature_sensitivity_sha256': SENSITIVITY_SHA,
        'training_source': fit.NVIDIA,
        'training_ids': [records[i]['id'] for i in nv],
        'held_source': fit.LLMAIL,
        'held_source_ids': [records[i]['id'] for i in ll],
        'label_status': 'source-provided; not accepted human truth',
        'optimizer': 'train-only z-score, full-batch logistic loss plus L2 with Armijo backtracking',
        'L2': fit.L2,
        'mean': trained['mean'].tolist(), 'std': trained['std'].tolist(),
        'weights': trained['weights'].tolist(), 'bias': trained['bias'],
        'threshold': None, 'serving_enabled': False,
        'human_label_review_complete': False, 'independent_final_test': False,
    }
    nv_scores, ll_scores = score_from_saved(model, x_nv), score_from_saved(model, x_ll)
    require(fit.np.max(fit.np.abs(nv_scores - fit.predict(x_nv, trained))) < 1e-12 and
            fit.np.max(fit.np.abs(ll_scores - fit.predict(x_ll, trained))) < 1e-12,
            'saved-model scoring differs from live fit')
    held_auroc = fit.auroc(ll_scores, y_ll)
    require(abs(held_auroc - sensitivity['llmail_source_transfer_cleaned']['auroc']) < 1e-12 and
            abs(float(ll_scores[y_ll == 1].min() - ll_scores[y_ll == 0].max()) -
                sensitivity['llmail_source_transfer_cleaned']['separation_gap']) < 1e-12,
            'retrained transfer result differs from archived sensitivity')
    predictions = [
        {'candidate_id': records[i]['id'], 'source_origin': records[i]['source_origin'],
         'source_label': records[i]['label'], 'score': float(score),
         'score_role': role}
        for group, scores, role in ((nv, nv_scores, 'training-in-sample'),
                                    (ll, ll_scores, 'observed-source-transfer'))
        for i, score in zip(group, scores)
    ]
    require(len(predictions) == len({row['candidate_id'] for row in predictions}) == 968,
            'prediction identities differ')
    summary = {
        'kind': 'feature-v4-solo-probe-fit-01', 'status': 'completed',
        'scope': model['scope'], 'model_training_source': fit.NVIDIA,
        'training_rows': len(nv), 'training_attacks': int(y_nv.sum()),
        'observed_transfer_source': fit.LLMAIL,
        'transfer_rows': len(ll), 'transfer_attacks': int(y_ll.sum()),
        'training_fit_steps': trained['steps_run'], 'training_objective': trained['objective'],
        'training_weights_l2_norm': trained['weights_l2_norm'],
        'nvidia_grouped_oof_auroc_from_prior_sensitivity': sensitivity['nvidia_oof_cleaned']['auroc'],
        'llmail_observed_source_transfer_auroc': held_auroc,
        'llmail_observed_source_transfer_gap': float(ll_scores[y_ll == 1].min() - ll_scores[y_ll == 0].max()),
        'threshold_selected': False, 'serving_enabled': False,
        'human_labels_used_for_fitting': False, 'independent_final_test': False,
        'limitations': [
            'The fixed feature and both source datasets were observed before this fit.',
            'Source labels are not accepted human truth; the 128 LLMail attack rows share lineage.',
            'Training scores are in-sample; transfer scores are already observed development evidence.',
            'New raw documents still require the pinned Qwen feature extractor; this JSON alone cannot read text.',
            'No operating threshold or real-agent defense behavior is established.',
        ],
    }
    OUTPUT.mkdir(mode=0o700, parents=True)
    model_raw = json_bytes(model)
    prediction_raw = ''.join(json.dumps(row, allow_nan=False) + '\n' for row in predictions).encode()
    summary['model_sha256'] = sha(model_raw)
    summary['predictions_sha256'] = sha(prediction_raw)
    summary['training_script_sha256'] = sha(Path(__file__).read_bytes())
    write_private(OUTPUT / 'model.json', model_raw)
    write_private(OUTPUT / 'predictions.jsonl', prediction_raw)
    write_private(OUTPUT / 'summary.json', json_bytes(summary))
    verify()
    print(json.dumps({'model': str(OUTPUT / 'model.json'), 'model_sha256': summary['model_sha256'],
                      'training_rows': len(nv), 'transfer_rows': len(ll),
                      'transfer_auroc': held_auroc,
                      'threshold': None, 'serving_enabled': False}, indent=2))


def verify():
    require(OUTPUT.is_dir(), 'trained output directory missing')
    summary = json.loads((OUTPUT / 'summary.json').read_text())
    model_raw = (OUTPUT / 'model.json').read_bytes()
    prediction_raw = (OUTPUT / 'predictions.jsonl').read_bytes()
    require(sha(model_raw) == summary['model_sha256'] and
            sha(prediction_raw) == summary['predictions_sha256'] and
            summary['training_script_sha256'] == sha(Path(__file__).read_bytes()),
            'trained artifact hash differs')
    model = json.loads(model_raw)
    require(model['feature'] == FEATURE and model['feature_protocol_fingerprint'] == fit.PROTOCOL_FINGERPRINT and
            model['threshold'] is None and model['serving_enabled'] is False and
            model['base_model_finetuned'] is False and
            model['cleaned_manifest_sha256'] == MANIFEST_SHA,
            'trained artifact policy differs')
    matrix, records, nv, ll, _ = load_inputs()
    li, pi = fit.LAYERS.index(18), fit.POOLS.index('content_mean')
    expected = {}
    for group, role in ((nv, 'training-in-sample'), (ll, 'observed-source-transfer')):
        scores = score_from_saved(model, matrix[group, li, pi, :])
        for i, score in zip(group, scores):
            expected[records[i]['id']] = (records[i], float(score), role)
    predictions = read_jsonl(OUTPUT / 'predictions.jsonl')
    require(len(predictions) == len(expected) == 968 and
            {row['candidate_id'] for row in predictions} == set(expected) and
            model['training_ids'] == [records[i]['id'] for i in nv] and
            model['held_source_ids'] == [records[i]['id'] for i in ll],
            'saved prediction identities differ')
    max_error = 0.0
    for row in predictions:
        candidate, expected_score, role = expected[row['candidate_id']]
        require(row['source_origin'] == candidate['source_origin'] and
                row['source_label'] == candidate['label'] and row['score_role'] == role,
                'saved prediction provenance differs')
        max_error = max(max_error, abs(row['score'] - expected_score))
    require(max_error < 1e-12, 'saved predictions do not reproduce')
    return {'verified_predictions': len(predictions), 'max_abs_score_error': max_error,
            'model_sha256': summary['model_sha256'], 'threshold_selected': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify-only', action='store_true')
    args = parser.parse_args()
    if args.verify_only:
        print(json.dumps(verify(), indent=2))
    else:
        train()
