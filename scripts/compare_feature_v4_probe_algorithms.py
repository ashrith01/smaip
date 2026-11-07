#!/usr/bin/env python3
"""Development-only algorithm comparison on pinned, saved V4 vectors.

The existing feature and both datasets have been observed. These results cannot
select a serving probe, threshold, or independent final-test performance.
"""

from collections import defaultdict
import argparse
import json
import os

import fit_feature_v4_exploratory as fit
import train_feature_v4_solo_probe as solo


OUTPUT = solo.ROOT / '.local-data/feature-v4-algorithm-compare-01'


def paired_fit(x, rows):
    """Learn the attack direction from matched attack-minus-clean differences."""
    by_pair = defaultdict(dict)
    for index, row in enumerate(rows):
        by_pair[row['pair_id']][row['label']] = index
    differences = [x[pair[1]] - x[pair[0]] for pair in by_pair.values()
                   if 0 in pair and 1 in pair]
    fit.require(len(differences) >= 100, 'too few complete training pairs')
    delta = fit.np.asarray(differences, dtype=fit.np.float64)
    train_x = fit.np.concatenate((delta, -delta))
    train_y = fit.np.concatenate((fit.np.ones(len(delta)), fit.np.zeros(len(delta))))
    model = fit.fit_logistic(train_x, train_y)
    return model, len(delta)


def paired_score(x, model):
    # The paired objective has symmetric inputs. Use its learned direction on
    # absolute examples; ranking is invariant to any constant offset.
    return (fit.np.asarray(x, dtype=fit.np.float64) / model['std']) @ model['weights']


def describe(scores, y, rows):
    pairs = defaultdict(dict)
    for score, row in zip(scores, rows):
        pairs[row['pair_id']][row['label']] = float(score)
    complete = [p for p in pairs.values() if 0 in p and 1 in p]
    return {'auroc': fit.auroc(scores, y),
            'paired_attack_above_clean': sum(p[1] > p[0] for p in complete),
            'complete_pairs': len(complete),
            'attack_min_minus_benign_max': float(scores[y == 1].min() - scores[y == 0].max())}


def main(verify_only=False):
    fit.require(OUTPUT.exists() if verify_only else not OUTPUT.exists(),
                'comparison output has unexpected presence; preserve version 01')
    matrix, records, nv, ll, sensitivity = solo.load_inputs()
    li, pi = fit.LAYERS.index(18), fit.POOLS.index('content_mean')
    x_nv, x_ll = matrix[nv, li, pi, :], matrix[ll, li, pi, :]
    r_nv, r_ll = [records[i] for i in nv], [records[i] for i in ll]
    y_nv = fit.np.asarray([r['label'] for r in r_nv], dtype=fit.np.int8)
    y_ll = fit.np.asarray([r['label'] for r in r_ll], dtype=fit.np.int8)
    folds, components = fit.make_folds(r_nv)
    methods = ('logistic_baseline', 'paired_difference')
    oof = {name: fit.np.full(len(nv), fit.np.nan) for name in methods}
    fold_pairs = []
    for fold in range(3):
        train, held = folds != fold, folds == fold
        base = fit.fit_logistic(x_nv[train], y_nv[train])
        pair, pair_count = paired_fit(x_nv[train], [r for r, keep in zip(r_nv, train) if keep])
        oof['logistic_baseline'][held] = fit.predict(x_nv[held], base)
        oof['paired_difference'][held] = paired_score(x_nv[held], pair)
        fold_pairs.append({'fold': fold, 'complete_training_pairs': pair_count,
                           'held_rows': int(held.sum())})
    fit.require(all(fit.np.all(fit.np.isfinite(scores)) for scores in oof.values()),
                'incomplete grouped predictions')
    base = fit.fit_logistic(x_nv, y_nv)
    pair, pair_count = paired_fit(x_nv, r_nv)
    transfer = {'logistic_baseline': fit.predict(x_ll, base),
                'paired_difference': paired_score(x_ll, pair)}
    fit.require(abs(fit.auroc(transfer['logistic_baseline'], y_ll) -
                    sensitivity['llmail_source_transfer_cleaned']['auroc']) < 1e-12,
                'baseline transfer reproduction differs')
    result = {
        'kind': 'feature-v4-algorithm-compare-01',
        'scope': 'exploratory, source-label development only',
        'feature': solo.FEATURE,
        'manifest_sha256': solo.MANIFEST_SHA,
        'collection_sha256': fit.COLLECTION_SHA256,
        'grouped_nvidia_components': len(components),
        'nvidia_rows': len(nv), 'llmail_rows': len(ll),
        'folds': fold_pairs, 'complete_final_training_pairs': pair_count,
        'algorithms': {
            name: {'nvidia_grouped_oof': describe(oof[name], y_nv, r_nv),
                   'llmail_observed_transfer': describe(transfer[name], y_ll, r_ll)}
            for name in methods
        },
        'threshold_selected': False, 'serving_enabled': False,
        'independent_final_test': False,
        'note': 'Comparing observed alternatives is diagnostic; no model is promoted from these scores.',
    }
    raw = solo.json_bytes(result)
    if verify_only:
        fit.require((OUTPUT / 'summary.json').read_bytes() == raw,
                    'saved algorithm comparison does not reproduce')
        print(json.dumps({'verified': True, 'summary_sha256': solo.sha(raw)}, indent=2))
    else:
        OUTPUT.mkdir(parents=True, mode=0o700)
        solo.write_private(OUTPUT / 'summary.json', raw)
        print(json.dumps(result, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify-only', action='store_true')
    main(parser.parse_args().verify_only)
