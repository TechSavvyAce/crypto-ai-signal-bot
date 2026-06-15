from __future__ import annotations

from crypto_bot.model.metrics import class_counts, majority_baseline_accuracy


def test_majority_baseline() -> None:
    y_tr = [1, 1, 1, -1]
    y_te = [1, 1, -1, -1]
    # majority in train is 1 → predicts 1 always → 50% on test
    assert majority_baseline_accuracy(y_te, y_tr) == 0.5


def test_class_counts() -> None:
    assert class_counts([1, 1, -1]) == {1: 2, -1: 1}
