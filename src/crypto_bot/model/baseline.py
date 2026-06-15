from __future__ import annotations

from collections.abc import Sequence
from typing import Any


def train_trend_logreg(
    X_train: Sequence[Sequence[float]],
    y_train: Sequence[int],
    X_test: Sequence[Sequence[float]],
    y_test: Sequence[int],
    *,
    max_iter: int = 200,
) -> dict[str, Any]:
    """Fit a simple multinomial logistic trend classifier; requires scikit-learn."""
    try:
        from sklearn.linear_model import LogisticRegression
        from sklearn.metrics import accuracy_score
    except ImportError as e:
        msg = "Install optional dependency: pip install 'crypto-bot[model]'"
        raise RuntimeError(msg) from e

    clf = LogisticRegression(max_iter=max_iter)
    clf.fit(X_train, y_train)
    pred_tr = clf.predict(X_train)
    pred_te = clf.predict(X_test)
    return {
        "model": clf,
        "train_accuracy": float(accuracy_score(y_train, pred_tr)),
        "test_accuracy": float(accuracy_score(y_test, pred_te)),
        "classes": [int(c) for c in clf.classes_],
        "pred_train": [int(p) for p in pred_tr],
        "pred_test": [int(p) for p in pred_te],
    }


def time_series_split(
    X: Sequence[Sequence[float]],
    y: Sequence[int],
    *,
    train_frac: float = 0.7,
) -> tuple[list[list[float]], list[list[float]], list[int], list[int]]:
    """Chronological split (first *train_frac* for training, rest for test)."""
    if not X or len(X) != len(y):
        msg = "X and y must be non-empty and equal length"
        raise ValueError(msg)
    if not (0.0 < train_frac < 1.0):
        msg = "train_frac must be between 0 and 1"
        raise ValueError(msg)
    n = len(X)
    cut = max(1, min(n - 1, int(n * train_frac)))
    x_tr = [list(row) for row in X[:cut]]
    x_te = [list(row) for row in X[cut:]]
    y_tr = list(y[:cut])
    y_te = list(y[cut:])
    return x_tr, x_te, y_tr, y_te
