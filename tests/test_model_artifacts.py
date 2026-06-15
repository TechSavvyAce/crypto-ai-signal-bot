from __future__ import annotations

from pathlib import Path

import pytest

from crypto_bot.model.artifacts import load_trend_artifact, save_trend_artifact


def test_save_load_trend_roundtrip(tmp_path: Path) -> None:
    pytest.importorskip("sklearn")
    from sklearn.linear_model import LogisticRegression

    clf = LogisticRegression(max_iter=100)
    clf.fit([[0.0, 1.0], [1.0, 0.0], [2.0, 1.0]], [-1, 0, 1])
    cols = ("a", "b")
    meta = {"note": "test", "feature_schema_version": "1.0.0"}
    d = tmp_path / "m"
    save_trend_artifact(d, clf, cols, meta)
    art = load_trend_artifact(d)
    assert art.feature_columns == cols
    assert art.meta["note"] == "test"
    assert art.predict_row({"a": 0.0, "b": 1.0}) in (-1, 0, 1)
