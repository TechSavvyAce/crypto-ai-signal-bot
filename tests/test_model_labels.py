from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

from crypto_bot.features import FeatureConfig, compute_feature_table
from crypto_bot.market_data.types import Bar, Symbol
from crypto_bot.model.dataset import build_xy_trend, join_features_labels
from crypto_bot.model.label_config import LabelConfig
from crypto_bot.model.labels import compute_label_table


def _sine_bars(n: int) -> list[Bar]:
    base = datetime(2020, 1, 1, tzinfo=timezone.utc)
    sym = Symbol("BTC/USDT")
    out: list[Bar] = []
    for i in range(n):
        t = base + timedelta(minutes=i)
        c = 100.0 + math.sin(i / 5.0) * 2.0
        out.append(
            Bar(
                symbol=sym,
                open_time=t,
                open=c,
                high=c * 1.001,
                low=c * 0.999,
                close=c,
                volume=1.0,
            )
        )
    return out


def test_compute_label_table_shape() -> None:
    bars = _sine_bars(40)
    cfg = LabelConfig(horizon=3, vol_forward=4)
    lt = compute_label_table(bars, cfg)
    assert len(lt.rows) == len(bars)
    assert lt.columns == cfg.column_names()


def test_forward_return_nan_tail() -> None:
    bars = _sine_bars(20)
    cfg = LabelConfig(horizon=5, vol_forward=4)
    lt = compute_label_table(bars, cfg)
    col = cfg.column_names()[0]
    assert math.isnan(float(lt.rows[-1][col]))
    assert not math.isnan(float(lt.rows[5][col]))


def test_join_and_build_xy() -> None:
    bars = _sine_bars(120)
    fcfg = FeatureConfig(vol_window=10, mom_horizon=4, rsi_period=8)
    lcfg = LabelConfig(horizon=5, vol_forward=4)
    ft = compute_feature_table(bars, fcfg)
    lt = compute_label_table(bars, lcfg)
    sup = join_features_labels(bars, ft, lt)
    trend_col = lcfg.column_names()[1]
    X, y = build_xy_trend(sup, trend_column=trend_col)
    assert len(X) == len(y)
    assert len(X) > 10
    assert all(v in (-1, 0, 1) for v in y)
