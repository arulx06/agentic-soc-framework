"""Consistent binary evaluation helpers.

Predictions are represented as integers (1=attack, 0=benign) everywhere.
Metrics functions refuse to return meaningful accuracy for empty splits
(they raise ValueError) so callers cannot silently print misleading numbers.
"""

from __future__ import annotations


def prediction_to_label(probability: float, threshold: float = 0.5) -> int:
    return 1 if float(probability) >= threshold else 0


def prediction_to_string(label_int: int) -> str:
    return "attack" if int(label_int) == 1 else "benign"


def binary_metrics(y_true: list[int], y_pred: list[int]) -> dict | None:
    """Return accuracy/precision/recall/F1 or None when the split is empty."""
    if len(y_true) != len(y_pred):
        raise ValueError("length mismatch")
    if len(y_true) == 0:
        return None
    tp = sum(1 for t, p in zip(y_true, y_pred) if t == 1 and p == 1)
    fp = sum(1 for t, p in zip(y_true, y_pred) if t == 0 and p == 1)
    fn = sum(1 for t, p in zip(y_true, y_pred) if t == 1 and p == 0)
    tn = sum(1 for t, p in zip(y_true, y_pred) if t == 0 and p == 0)
    accuracy = (tp + tn) / len(y_true)
    precision = tp / (tp + fp) if (tp + fp) else None
    recall = tp / (tp + fn) if (tp + fn) else None
    f1 = (
        2 * precision * recall / (precision + recall)
        if precision is not None and recall is not None and (precision + recall)
        else None
    )
    return {
        "support": len(y_true),
        "positives": sum(y_true),
        "accuracy": round(accuracy, 6),
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }
