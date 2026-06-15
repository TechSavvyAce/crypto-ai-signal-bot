from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class TrendClassifierArtifact:
    """Loaded baseline trend model + feature column order."""

    classifier: Any
    feature_columns: tuple[str, ...]
    meta: dict[str, Any]

    def predict_row(self, row: dict[str, Any]) -> int:
        x = [float(row[c]) for c in self.feature_columns]
        pred = self.classifier.predict([x])[0]
        return int(pred)


def save_trend_artifact(
    directory: Path,
    classifier: Any,
    feature_columns: tuple[str, ...],
    meta: dict[str, Any],
) -> None:
    """Persist sklearn classifier + ``meta.json`` (feature column order and training metadata)."""
    try:
        import joblib
    except ImportError as e:
        msg = "joblib is required (install scikit-learn / crypto-bot[model])"
        raise RuntimeError(msg) from e

    directory.mkdir(parents=True, exist_ok=True)
    joblib.dump(classifier, directory / "classifier.joblib")
    payload = {**meta, "feature_columns": list(feature_columns)}
    (directory / "meta.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


def load_trend_artifact(directory: Path) -> TrendClassifierArtifact:
    try:
        import joblib
    except ImportError as e:
        msg = "joblib is required (install scikit-learn / crypto-bot[model])"
        raise RuntimeError(msg) from e

    clf_path = directory / "classifier.joblib"
    meta_path = directory / "meta.json"
    if not clf_path.is_file() or not meta_path.is_file():
        msg = f"Missing classifier.joblib or meta.json under {directory}"
        raise FileNotFoundError(msg)
    classifier = joblib.load(clf_path)
    data = json.loads(meta_path.read_text(encoding="utf-8"))
    cols_raw = data.pop("feature_columns", [])
    if not isinstance(cols_raw, list) or not cols_raw:
        msg = "meta.json must contain non-empty feature_columns"
        raise ValueError(msg)
    return TrendClassifierArtifact(
        classifier=classifier,
        feature_columns=tuple(str(c) for c in cols_raw),
        meta=data,
    )
