#!/usr/bin/env python3
"""Fixed-feature V4 sensitivity to R031 quarantine and exact deduplication.

Uses only saved vectors and source-provided development labels. The selected
feature and objective are inherited from the already observed exploratory fit.
"""

from collections import Counter
import hashlib
import json
import os
from pathlib import Path

import fit_feature_v4_exploratory as fit


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / '.local-data/feature-v4-solo-audit-01/candidate-manifest.jsonl'
MANIFEST_SHA = '8952a310a6e47663c15416909dbe20a9385939429c4410afafb396dd6785b7ae'
PREVIOUS = ROOT / '.local-data/exploratory-fit-v4-02'
OUTPUT = ROOT / '.local-data/feature-v4-solo-sensitivity-01'
FEATURE = 'content_mean/18'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def jsonl(path):
    return [json.loads(line) for line in path.read_bytes().splitlines() if line.strip()]


def write_private(path, value):
    contents = (json.dumps(value, indent=2, allow_nan=False) + '\n').encode()
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'wb') as file:
        file.write(contents)
        file.flush()
        os.fsync(file.fileno())
    return fit.sha(contents)


def describe(scores, labels):
    scores = fit.np.asarray(scores, dtype=fit.np.float64)
    labels = fit.np.asarray(labels, dtype=fit.np.int8)
    require(len(scores) and len(fit.np.unique(labels)) == 2 and fit.np.all(fit.np.isfinite(scores)),
            'invalid scores for both-label ranking')
    attack = scores[labels == 1]
    benign = scores[labels == 0]
    return {'rows': len(scores), 'attack': len(attack), 'benign': len(benign),
            'auroc': fit.auroc(scores, labels),
            'minimum_attack_score': float(attack.min()),
            'maximum_benign_score': float(benign.max()),
            'separation_gap': float(attack.min() - benign.max())}


def main():
    require(not OUTPUT.exists(), 'preserve sensitivity 01; version any rerun')
    require(fit.sha(MANIFEST.read_bytes()) == MANIFEST_SHA, 'solo audit manifest differs')
    previous_hashes = json.loads((PREVIOUS / 'files-sha256.json').read_text())
    for name in ('summary.json', 'predictions.jsonl', 'exploratory-model.json', 'split.json'):
        require(fit.sha((PREVIOUS / name).read_bytes()) == previous_hashes[name],
                f'previous exploratory fit file differs: {name}')
    previous_summary = json.loads((PREVIOUS / 'summary.json').read_text())
    previous_model = json.loads((PREVIOUS / 'exploratory-model.json').read_text())
    require(previous_summary['selected_feature'] == FEATURE and
            previous_model['feature'] == FEATURE and previous_model['threshold'] is None and
            previous_model['serving_enabled'] is False and
            previous_summary['feature_collection_sha256'] == fit.COLLECTION_SHA256,
            'previous fixed-feature identity differs')
    previous_scores = {row['id']: row['score'] for row in jsonl(PREVIOUS / 'predictions.jsonl')
                       if row['feature'] == FEATURE}
    require(len(previous_scores) == 1012, 'previous selected-feature predictions differ')

    manifest = jsonl(MANIFEST)
    require(len(manifest) == 1012 and len({row['candidate_id'] for row in manifest}) == 1012,
            'solo audit row count differs')
    selected = {row['candidate_id']: row for row in manifest
                if row['status'] == 'source_label_development_only'}
    require(len(selected) == 968 and sum(row['status'] == 'duplicate_reference' for row in manifest) == 43 and
            [row['candidate_id'] for row in manifest if row['status'] == 'quarantined'] == ['nvidia-12-clean'],
            'cleaned candidate decisions differ')
    matrix, records, collection = fit.load_data()
    indices = [i for i, row in enumerate(records) if row['id'] in selected]
    require(len(indices) == len(selected) and set(selected) == {records[i]['id'] for i in indices},
            'feature rows and selected candidate identities differ')
    for i in indices:
        row = records[i]
        entry = selected[row['id']]
        require(row['label'] == entry['source_label'] and row['source_origin'] == entry['source_origin'],
                'manifest/source label differs')
    nv_indices = [i for i in indices if records[i]['source_origin'] == fit.NVIDIA]
    ll_indices = [i for i in indices if records[i]['source_origin'] == fit.LLMAIL]
    require((len(nv_indices), len(ll_indices)) == (680, 288), 'cleaned source counts differ')
    nv_records = [records[i] for i in nv_indices]
    ll_records = [records[i] for i in ll_indices]
    folds, components = fit.make_folds(nv_records)
    y_nv = fit.np.array([row['label'] for row in nv_records], dtype=fit.np.int8)
    y_ll = fit.np.array([row['label'] for row in ll_records], dtype=fit.np.int8)
    require((int(y_nv.sum()), int(y_ll.sum())) == (228, 128), 'cleaned label counts differ')

    li, pi = fit.LAYERS.index(18), fit.POOLS.index('content_mean')
    x_nv = matrix[nv_indices, li, pi, :]
    x_ll = matrix[ll_indices, li, pi, :]
    oof = fit.np.full(len(nv_indices), fit.np.nan, dtype=fit.np.float64)
    fold_fits = []
    for fold in range(3):
        train, held = folds != fold, folds == fold
        model = fit.fit_logistic(x_nv[train], y_nv[train])
        oof[held] = fit.predict(x_nv[held], model)
        fold_fits.append({'fold': fold, 'train_rows': int(train.sum()),
                          'held_rows': int(held.sum()), 'steps_run': model['steps_run']})
    require(fit.np.all(fit.np.isfinite(oof)), 'missing grouped out-of-fold scores')
    final_model = fit.fit_logistic(x_nv, y_nv)
    transferred = fit.predict(x_ll, final_model)

    old_nv = fit.np.array([previous_scores[row['id']] for row in nv_records])
    old_ll = fit.np.array([previous_scores[row['id']] for row in ll_records])
    output = {'kind': 'feature-v4-solo-fixed-feature-sensitivity-01',
              'status': 'completed', 'scope': 'source-labeled development only',
              'candidate_source_sha256': fit.CANDIDATE_SHA256,
              'feature_collection_sha256': fit.COLLECTION_SHA256,
              'feature_protocol_fingerprint': fit.PROTOCOL_FINGERPRINT,
              'solo_manifest_sha256': MANIFEST_SHA,
              'prior_summary_sha256': previous_hashes['summary.json'],
              'prior_predictions_sha256': previous_hashes['predictions.jsonl'],
              'fixed_feature': FEATURE, 'selection_repeated': False,
              'L2': fit.L2, 'grouped_nvidia_components': len(components),
              'grouped_folds': fold_fits,
              'nvidia_oof_cleaned': describe(oof, y_nv),
              'nvidia_old_scores_on_cleaned_rows': describe(old_nv, y_nv),
              'llmail_source_transfer_cleaned': describe(transferred, y_ll),
              'llmail_old_scores_on_cleaned_rows': describe(old_ll, y_ll),
              'score_change': {
                  'nvidia_oof_max_abs': float(fit.np.max(fit.np.abs(oof - old_nv))),
                  'llmail_transfer_max_abs': float(fit.np.max(fit.np.abs(transferred - old_ll))),
              },
              'final_fit': {'training_rows': len(nv_records), 'steps_run': final_model['steps_run'],
                            'objective': final_model['objective'],
                            'weights_l2_norm': float(fit.np.linalg.norm(final_model['weights']))},
              'source_labels_used': True, 'human_labels_used_for_fitting': False,
              'threshold_selected': False, 'serving_enabled': False,
              'calibration_eligible': False, 'independent_final_test': False,
              'limitations': [
                  'The feature and source transfer were selected and observed before this sensitivity run.',
                  'The cleaned source labels have not been accepted as human-verified truth.',
                  'LLMail attacks share a connected lineage; rows are not independent examples.',
                  'No operating threshold, agent outcome, or final-test result is produced.',
              ]}
    OUTPUT.mkdir(mode=0o700, parents=True)
    summary_sha = write_private(OUTPUT / 'summary.json', output)
    print(json.dumps({'output': str(OUTPUT), 'summary_sha256': summary_sha,
                      'nvidia_auroc': output['nvidia_oof_cleaned']['auroc'],
                      'llmail_auroc': output['llmail_source_transfer_cleaned']['auroc'],
                      'nvidia_gap': output['nvidia_oof_cleaned']['separation_gap'],
                      'llmail_gap': output['llmail_source_transfer_cleaned']['separation_gap']}, indent=2))


if __name__ == '__main__':
    main()
