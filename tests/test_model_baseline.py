from __future__ import annotations

import pytest

from crypto_bot.model.baseline import time_series_split, train_trend_logreg


def test_time_series_split() -> None:
    X = [[1.0], [2.0], [3.0], [4.0], [5.0]]
    y = [0, 1, 0, 1, 0]
    x_tr, x_te, y_tr, y_te = time_series_split(X, y, train_frac=0.6)
    assert len(x_tr) == 3 and len(x_te) == 2


def test_train_trend_logreg_smoke() -> None:
    pytest.importorskip("sklearn")
    X = [[0.0, 0.0], [1.0, 0.0], [0.0, 1.0], [1.0, 1.0], [2.0, 0.0], [0.0, 2.0]]
    y = [-1, 0, 1, -1, 0, 1]
    x_tr, x_te, y_tr, y_te = time_series_split(X, y, train_frac=0.66)
    out = train_trend_logreg(x_tr, y_tr, x_te, y_te)
    assert "train_accuracy" in out
    assert "pred_test" in out and len(out["pred_test"]) == len(y_te)
    assert 0.0 <= out["test_accuracy"] <= 1.0
