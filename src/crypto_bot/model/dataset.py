from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from crypto_bot.features.engine import FeatureTable
from crypto_bot.market_data.types import Bar
from crypto_bot.model.labels import LabelTable


@dataclass(frozen=True)
class SupervisedTable:
    """Aligned feature + label rows with explicit column names for X and y."""

    feature_columns: tuple[str, ...]
    label_columns: tuple[str, ...]
    rows: list[dict[str, Any]]


def default_feature_columns(feature_table: FeatureTable) -> tuple[str, ...]:
    return tuple(c for c in feature_table.columns if c not in ("open_time", "symbol"))


def join_features_labels(
    bars: Sequence[Bar],
    feature_table: FeatureTable,
    label_table: LabelTable,
) -> SupervisedTable:
    """Merge feature and label rows by bar index (must match *bars* length)."""
    n = len(bars)
    if len(feature_table.rows) != n or len(label_table.rows) != n:
        msg = "feature_table, label_table, and bars must have the same length"
        raise ValueError(msg)

    fx_cols = default_feature_columns(feature_table)
    lb_cols = tuple(label_table.columns)
    rows: list[dict[str, Any]] = []
    for i in range(n):
        merged = {**feature_table.rows[i], **{c: label_table.rows[i][c] for c in lb_cols}}
        rows.append(merged)

    return SupervisedTable(feature_columns=fx_cols, label_columns=lb_cols, rows=rows)


def build_xy_trend(
    supervised: SupervisedTable,
    *,
    trend_column: str,
) -> tuple[list[list[float]], list[int]]:
    """Drop rows with NaN in features or label; return X as float matrix and y as int class."""
    if trend_column not in supervised.label_columns:
        msg = f"trend_column {trend_column!r} not in label columns"
        raise ValueError(msg)

    X: list[list[float]] = []
    y: list[int] = []
    for row in supervised.rows:
        try:
            yi = int(row[trend_column])
        except (TypeError, ValueError):
            continue
        if yi not in (-1, 0, 1):
            continue
        xvec: list[float] = []
        bad = False
        for c in supervised.feature_columns:
            v = row.get(c)
            if not isinstance(v, (int, float)) or math.isnan(float(v)):
                bad = True
                break
            xvec.append(float(v))
        if bad:
            continue
        X.append(xvec)
        y.append(yi)
    return X, y
