"""Layer sweep for one logistic probe.

Each layer is fit on the train split only. The chosen layer is the best
validation AUROC, then the lower false-positive rate at the target recall,
then the layer closest to two thirds of the way through the network (ties
in that distance take the earlier layer). The threshold is frozen on the
validation split before the test metrics are computed.
"""

from smaip.probes.logistic import (
    TPR_TARGET,
    metric_block,
    predict_proba,
    standardize,
    threshold_at_tpr,
    train_logistic,
)


def sweep_probe(
    rows: list[dict],
    *,
    kind: str,
    pooling: str,
    model_id: str,
    backend: str,
    device: str,
    tpr_target: float = TPR_TARGET,
) -> dict:
    layers = _layers(rows)
    if not layers:
        raise ValueError("activation rows do not name any layers")
    train_rows = [row for row in rows if row["split"] == "train"]
    val_rows = [row for row in rows if row["split"] == "val"]
    test_rows = [row for row in rows if row["split"] == "test"]
    if not train_rows or not val_rows or not test_rows:
        raise ValueError("the probe sweep needs train, val, and test rows")
    sweep: list[dict] = []
    fitted: dict[int, dict] = {}
    for layer in layers:
        train_x, train_y = _matrix(train_rows, layer, pooling)
        val_x, val_y = _matrix(val_rows, layer, pooling)
        scaled_train, mean, std = standardize(train_x)
        weights, bias = train_logistic(scaled_train, train_y)
        scaled_val, _, _ = standardize(val_x, mean, std)
        val_scores = [_dot(row, weights, bias) for row in scaled_val]
        threshold, _fpr, _tpr = threshold_at_tpr(val_scores, val_y, tpr_target)
        block = metric_block(val_scores, val_y, threshold, tpr_target=tpr_target)
        entry = {
            "layer": layer,
            "val_auroc": block["auroc"],
            "val_f1": block["f1"],
            "val_fpr_at_tpr": block["fpr_at_tpr"],
            "val_tpr": block["tpr"],
        }
        sweep.append(entry)
        fitted[layer] = {
            "weights": weights,
            "bias": bias,
            "mean": mean,
            "std": std,
            "threshold": threshold,
            "val_scores": val_scores,
            "val_labels": val_y,
        }
    depth = max(item["layer"] for item in sweep) + 1
    anchor = int(round((depth - 1) * 2 / 3))
    chosen = min(
        sweep,
        key=lambda item: (
            -item["val_auroc"],
            item["val_fpr_at_tpr"],
            abs(item["layer"] - anchor),
            item["layer"],
        ),
    )
    layer = int(chosen["layer"])
    fit = fitted[layer]
    test_x, test_y = _matrix(test_rows, layer, pooling)
    scaled_test, _, _ = standardize(test_x, fit["mean"], fit["std"])
    test_scores = [_dot(row, fit["weights"], fit["bias"]) for row in scaled_test]
    threshold = float(fit["threshold"])
    val_metrics = metric_block(
        fit["val_scores"], fit["val_labels"], threshold, tpr_target=tpr_target
    )
    test_metrics = metric_block(test_scores, test_y, threshold, tpr_target=tpr_target)
    dim = len(fit["weights"])
    return {
        "format": 1,
        "kind": kind,
        "model_id": model_id,
        "backend": backend,
        "device": device,
        "pooling": pooling,
        "layer": layer,
        "threshold": threshold,
        "tpr_target": tpr_target,
        "dim": dim,
        "mean": fit["mean"],
        "std": fit["std"],
        "weights": fit["weights"],
        "bias": fit["bias"],
        "metrics": {"val": val_metrics, "test": test_metrics},
        "layer_sweep": sweep,
        "n_train": len(train_rows),
        "n_val": len(val_rows),
        "n_test": len(test_rows),
        "layer_indexing": "residual stream after the transformer block (hidden_states[layer + 1])",
    }


def _layers(rows: list[dict]) -> list[int]:
    names = rows[0]["layers"]["last"].keys()
    return sorted(int(name) for name in names)


def _matrix(rows: list[dict], layer: int, pooling: str) -> tuple[list[list[float]], list[int]]:
    key = str(layer)
    features = [list(row["layers"][pooling][key]) for row in rows]
    labels = [int(row["label"]) for row in rows]
    return features, labels


def _dot(row: list[float], weights: list[float], bias: float) -> float:
    return predict_proba(row, weights, bias)
