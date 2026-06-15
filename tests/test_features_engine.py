from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

import pytest

from crypto_bot.features import FeatureConfig, compute_feature_table
from crypto_bot.market_data.types import Bar, Symbol


def _bar(t: datetime, close: float, sym: str = "BTC/USDT") -> Bar:
    return Bar(
        symbol=Symbol(sym),
        open_time=t,
        open=close,
        high=close * 1.001,
        low=close * 0.999,
        close=close,
        volume=1.0,
    )


def test_compute_features_empty() -> None:
    t = compute_feature_table([], FeatureConfig())
    assert t.rows == []


def test_compute_features_requires_sorted_time() -> None:
    base = datetime(2024, 1, 1, tzinfo=timezone.utc)
    bars = [
        _bar(base + timedelta(minutes=2), 102.0),
        _bar(base + timedelta(minutes=1), 101.0),
    ]
    with pytest.raises(ValueError, match="strictly increasing"):
        compute_feature_table(bars)


def test_ret_and_momentum_signs() -> None:
    base = datetime(2024, 1, 1, tzinfo=timezone.utc)
    prices = [100.0, 101.0, 102.0, 101.0]
    bars = [_bar(base + timedelta(minutes=i), p) for i, p in enumerate(prices)]
    cfg = FeatureConfig(vol_window=2, mom_horizon=2, rsi_period=2)
    t = compute_feature_table(bars, cfg)
    assert t.columns == cfg.column_names()
    assert t.schema_version
    r1 = t.rows[1]["ret_1"]
    assert r1 is not None and r1 > 0
    r3 = t.rows[3]["ret_1"]
    assert r3 is not None and r3 < 0
    mom2 = t.rows[2][cfg.column_names()[5]]
    assert mom2 is not None and mom2 > 0


def test_rsi_bounded() -> None:
    base = datetime(2024, 1, 1, tzinfo=timezone.utc)
    closes = [100 + i * 0.5 for i in range(40)]
    bars = [_bar(base + timedelta(minutes=i), c) for i, c in enumerate(closes)]
    cfg = FeatureConfig(vol_window=5, mom_horizon=3, rsi_period=14)
    t = compute_feature_table(bars, cfg)
    rsi_col = f"rsi_{cfg.rsi_period}"
    for row in t.rows:
        v = row[rsi_col]
        if isinstance(v, float) and not math.isnan(v):
            assert 0.0 <= v <= 100.0
