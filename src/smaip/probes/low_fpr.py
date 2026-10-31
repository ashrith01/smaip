"""Calibration-only low-FPR thresholds, with explicit held-out operating points.

Never pass final-test labels into calibrate(). Scores at the selected threshold
are positive (>=); nextafter permits a strict boundary above tied negatives.
"""
import math
from smaip.probes.logistic import auroc, binary_counts, f1_score


def _validate(scores, labels):
    if len(scores) != len(labels) or not scores or set(labels) != {0, 1}:
        raise ValueError('scores need both labels and matching nonempty lengths')
    if any(not math.isfinite(x) or not 0 <= x <= 1 for x in scores):
        raise ValueError('scores must be finite probabilities')


def operating_point(scores, labels, threshold):
    _validate(scores, labels)
    if not math.isfinite(threshold):
        raise ValueError('threshold must be finite')
    tp, fp, tn, fn = binary_counts(scores, labels, threshold)
    return {'auroc': auroc(scores, labels), 'tp': tp, 'fp': fp, 'tn': tn, 'fn': fn,
            'tpr': tp / (tp + fn), 'fpr': fp / (fp + tn),
            'f1': f1_score(tp, fp, fn), 'threshold': threshold,
            'negatives': fp + tn, 'positives': tp + fn}


def calibrate(scores, labels, *, max_fpr=0.01):
    """Maximize calibration recall subject to the empirical FPR budget.

    Ties prefer lower FPR and then the strictest threshold. This returns a
    frozen operating point, not a population-FPR guarantee.
    """
    _validate(scores, labels)
    if not 0 <= max_fpr < 1:
        raise ValueError('max_fpr must be in [0, 1)')
    candidates = set(scores) | {math.nextafter(x, math.inf) for x in scores}
    feasible = [operating_point(scores, labels, threshold) for threshold in candidates]
    feasible = [row for row in feasible if row['fpr'] <= max_fpr + 1e-12]
    chosen = min(feasible, key=lambda row: (-row['tpr'], row['fpr'], -row['threshold']))
    n = chosen['negatives']
    return {**chosen, 'selection_split': 'calibration', 'fpr_budget': max_fpr,
            'fpr_resolution': 1 / n,
            'zero_fp_one_sided_95_upper': 1 - 0.05 ** (1 / n) if chosen['fp'] == 0 else None,
            'low_fpr_evidence_sufficient': chosen['fp'] == 0 and 1 - 0.05 ** (1 / n) <= max_fpr,
            'note': 'Sufficiency field uses a zero-event independent Bernoulli bound; group independence must be checked separately.'}


def evaluate_frozen(scores, labels, calibration):
    return {**operating_point(scores, labels, calibration['threshold']),
            'threshold_source': 'independent-calibration',
            'calibration_fpr_budget': calibration['fpr_budget']}
