"""L2-regularized logistic regression and the metrics a probe artifact stores.

Pure Python so the CPU smoke path does not need torch, numpy, or sklearn.
Feature rows are small (a mock residual) or a few thousand wide (a 3B
hidden state). Both fit in an ordinary training loop.
"""

import math


TPR_TARGET = 0.95


def train_logistic(
    rows: list[list[float]],
    labels: list[int],
    *,
    l2: float = 0.05,
    steps: int = 400,
    lr: float = 0.3,
) -> tuple[list[float], float]:
    """Return ``(weights, bias)`` for a probability of the positive class."""

    if not rows:
        raise ValueError("logistic regression needs at least one row")
    if len(rows) != len(labels):
        raise ValueError("logistic regression row and label counts differ")
    dim = len(rows[0])
    if any(len(row) != dim for row in rows):
        raise ValueError("logistic regression rows have different widths")
    weights = [0.0] * dim
    bias = 0.0
    count = float(len(rows))
    for _ in range(steps):
        grad_w = [0.0] * dim
        grad_b = 0.0
        for row, label in zip(rows, labels):
            score = bias
            for weight, value in zip(weights, row):
                score += weight * value
            error = _sigmoid(score) - float(label)
            for index, value in enumerate(row):
                grad_w[index] += error * value
            grad_b += error
        for index in range(dim):
            weights[index] -= lr * (grad_w[index] / count + l2 * weights[index])
        bias -= lr * (grad_b / count)
    return weights, bias


def standardize(
    rows: list[list[float]],
    mean: list[float] | None = None,
    std: list[float] | None = None,
) -> tuple[list[list[float]], list[float], list[float]]:
    """Z-score rows. Pass train moments to scale later splits the same way."""

    if not rows:
        raise ValueError("standardize needs at least one row")
    dim = len(rows[0])
    if mean is None or std is None:
        mean = []
        std = []
        count = float(len(rows))
        for index in range(dim):
            column = [row[index] for row in rows]
            mu = sum(column) / count
            variance = sum((value - mu) ** 2 for value in column) / count
            sigma = math.sqrt(variance)
            if sigma < 1e-8:
                sigma = 1.0
            mean.append(mu)
            std.append(sigma)
    scaled = [
        [(value - mean[index]) / std[index] for index, value in enumerate(row)]
        for row in rows
    ]
    return scaled, mean, std


def predict_proba(row: list[float], weights: list[float], bias: float) -> float:
    score = bias
    for weight, value in zip(weights, row):
        score += weight * value
    return _sigmoid(score)


def auroc(scores: list[float], labels: list[int]) -> float:
    """Mann-Whitney AUROC. Ties use the average rank. Empty classes return 0.5."""

    if len(scores) != len(labels) or not scores:
        return 0.5
    positives = sum(labels)
    negatives = len(labels) - positives
    if positives == 0 or negatives == 0:
        return 0.5
    order = sorted(range(len(scores)), key=lambda index: scores[index])
    rank_sum = 0.0
    cursor = 0
    while cursor < len(order):
        end = cursor
        while end < len(order) and scores[order[end]] == scores[order[cursor]]:
            end += 1
        average = (cursor + 1 + end) / 2.0
        for position in range(cursor, end):
            if labels[order[position]] == 1:
                rank_sum += average
        cursor = end
    return (rank_sum - positives * (positives + 1) / 2.0) / (positives * negatives)


def binary_counts(
    scores: list[float], labels: list[int], threshold: float
) -> tuple[int, int, int, int]:
    true_pos = false_pos = true_neg = false_neg = 0
    for score, label in zip(scores, labels):
        predicted = score >= threshold
        if predicted and label == 1:
            true_pos += 1
        elif predicted and label == 0:
            false_pos += 1
        elif label == 0:
            true_neg += 1
        else:
            false_neg += 1
    return true_pos, false_pos, true_neg, false_neg


def f1_score(true_pos: int, false_pos: int, false_neg: int) -> float:
    precision_den = true_pos + false_pos
    recall_den = true_pos + false_neg
    precision = true_pos / precision_den if precision_den else 0.0
    recall = true_pos / recall_den if recall_den else 0.0
    if precision + recall == 0.0:
        return 0.0
    return 2.0 * precision * recall / (precision + recall)


def threshold_at_tpr(
    scores: list[float],
    labels: list[int],
    target: float = TPR_TARGET,
) -> tuple[float, float, float]:
    """Highest threshold whose recall is at least ``target``.

    Returns ``(threshold, fpr, achieved_tpr)``. Walking from a strict
    threshold downward picks the operating point that still hits the
    target recall with the lowest false-positive rate. If the target is
    out of reach, the threshold that catches every positive is used.
    """

    positives = [score for score, label in zip(scores, labels) if label == 1]
    negatives = [score for score, label in zip(scores, labels) if label == 0]
    if not positives:
        return 1.0, 1.0, 0.0
    candidates = sorted(set(scores), reverse=True)
    fallback: tuple[float, float, float] | None = None
    for threshold in candidates:
        true_pos = sum(score >= threshold for score in positives)
        achieved = true_pos / len(positives)
        false_pos = sum(score >= threshold for score in negatives)
        fpr = false_pos / len(negatives) if negatives else 0.0
        fallback = (threshold, fpr, achieved)
        if achieved + 1e-12 >= target:
            return threshold, fpr, achieved
    assert fallback is not None
    return fallback


def metric_block(
    scores: list[float],
    labels: list[int],
    threshold: float,
    *,
    tpr_target: float = TPR_TARGET,
) -> dict:
    true_pos, false_pos, true_neg, false_neg = binary_counts(scores, labels, threshold)
    positives = true_pos + false_neg
    negatives = true_neg + false_pos
    achieved = true_pos / positives if positives else 0.0
    fpr = false_pos / negatives if negatives else 0.0
    return {
        "auroc": auroc(scores, labels),
        "f1": f1_score(true_pos, false_pos, false_neg),
        "fpr_at_tpr": fpr,
        "tpr": achieved,
        "tpr_target": tpr_target,
        "threshold": threshold,
        "positives": positives,
        "negatives": negatives,
    }


def _sigmoid(value: float) -> float:
    if value >= 0.0:
        exp = math.exp(-value)
        return 1.0 / (1.0 + exp)
    exp = math.exp(value)
    return exp / (1.0 + exp)
