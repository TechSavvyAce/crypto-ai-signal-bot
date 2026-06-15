from __future__ import annotations

from collections import Counter
from collections.abc import Sequence


def class_counts(y: Sequence[int]) -> dict[int, int]:
    return dict(Counter(y))


def majority_baseline_accuracy(y_eval: Sequence[int], y_train: Sequence[int]) -> float:
    """Accuracy if we always predict the most common class in *y_train* on *y_eval*."""
    if not y_eval or not y_train:
        return float("nan")
    maj = Counter(y_train).most_common(1)[0][0]
    return sum(1 for v in y_eval if v == maj) / len(y_eval)


def accuracy(y_true: Sequence[int], y_pred: Sequence[int]) -> float:
    if not y_true or len(y_true) != len(y_pred):
        return float("nan")
    return sum(1 for a, b in zip(y_true, y_pred) if a == b) / len(y_true)
