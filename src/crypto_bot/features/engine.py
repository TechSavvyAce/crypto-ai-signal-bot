from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from crypto_bot.features.config import FeatureConfig
from crypto_bot.features.schema import FEATURE_SCHEMA_VERSION
from crypto_bot.market_data.types import Bar


def _assert_sorted_ohlcv(bars: Sequence[Bar]) -> None:
    if len(bars) <= 1:
        return
    sym = bars[0].symbol
    prev_t = bars[0].open_time
    for b in bars[1:]:
        if b.symbol != sym:
            msg = "All bars must share the same symbol"
            raise ValueError(msg)
        if b.open_time <= prev_t:
            msg = "Bars must be strictly increasing by open_time"
            raise ValueError(msg)
        prev_t = b.open_time


def _mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else float("nan")


def _pop_std(xs: list[float]) -> float:
    if len(xs) < 2:
        return float("nan")
    m = _mean(xs)
    v = sum((x - m) ** 2 for x in xs) / len(xs)
    return math.sqrt(v)


def _rsi_wilder(closes: list[float], period: int) -> list[float]:
    """RSI (Wilder) aligned with *closes* index; NaN until index >= period."""
    n = len(closes)
    out = [float("nan")] * n
    if n < period + 1:
        return out

    deltas: list[float] = []
    for i in range(1, n):
        deltas.append(closes[i] - closes[i - 1])

    gains = [max(d, 0.0) for d in deltas]
    losses = [max(-d, 0.0) for d in deltas]

    # First RSI at bar index `period` uses deltas indices 0..period-1 (P deltas)
    idx = period
    avg_g = sum(gains[0:period]) / period
    avg_l = sum(losses[0:period]) / period
    out[idx] = _rsi_from_averages(avg_g, avg_l)

    for idx in range(period + 1, n):
        g = gains[idx - 1]
        ell = losses[idx - 1]
        avg_g = (avg_g * (period - 1) + g) / period
        avg_l = (avg_l * (period - 1) + ell) / period
        out[idx] = _rsi_from_averages(avg_g, avg_l)

    return out


def _rsi_from_averages(avg_g: float, avg_l: float) -> float:
    if avg_l == 0.0 and avg_g == 0.0:
        return 50.0
    if avg_l == 0.0:
        return 100.0
    if avg_g == 0.0:
        return 0.0
    rs = avg_g / avg_l
    return 100.0 - (100.0 / (1.0 + rs))


@dataclass(frozen=True)
class FeatureTable:
    """Column-major contract: *columns* order matches each row dict keys."""

    schema_version: str
    config: FeatureConfig
    columns: tuple[str, ...]
    rows: list[dict[str, Any]]

    @staticmethod
    def empty(config: FeatureConfig | None = None) -> FeatureTable:
        cfg = config or FeatureConfig()
        return FeatureTable(
            schema_version=FEATURE_SCHEMA_VERSION,
            config=cfg,
            columns=cfg.column_names(),
            rows=[],
        )


def compute_feature_table(
    bars: Sequence[Bar],
    config: FeatureConfig | None = None,
) -> FeatureTable:
    """Compute per-bar features using only information available at bar *close*.

    *bars* must be ascending by ``open_time`` and one symbol. First row has NaNs
    where lookback is missing (represented as ``float('nan')``).
    """
    cfg = config or FeatureConfig()
    cols = cfg.column_names()
    if not bars:
        return FeatureTable.empty(cfg)

    _assert_sorted_ohlcv(bars)

    closes = [float(b.close) for b in bars]
    log_rets: list[float] = []
    rets: list[float] = []
    for i in range(len(closes)):
        if i == 0:
            rets.append(float("nan"))
            log_rets.append(float("nan"))
            continue
        prev = closes[i - 1]
        if prev == 0.0:
            rets.append(float("nan"))
            log_rets.append(float("nan"))
            continue
        r = closes[i] / prev - 1.0
        rets.append(r)
        log_rets.append(math.log(closes[i] / prev))

    w = cfg.vol_window
    vol_roll: list[float] = []
    for i in range(len(log_rets)):
        if i < w:
            vol_roll.append(float("nan"))
            continue
        window = log_rets[i - w + 1 : i + 1]
        vol_roll.append(_pop_std(window))

    k = cfg.mom_horizon
    mom: list[float] = []
    for i in range(len(closes)):
        if i < k:
            mom.append(float("nan"))
            continue
        base = closes[i - k]
        if base == 0.0:
            mom.append(float("nan"))
        else:
            mom.append(closes[i] / base - 1.0)

    rsi = _rsi_wilder(closes, cfg.rsi_period)

    rows: list[dict[str, Any]] = []
    for i, b in enumerate(bars):
        rows.append(
            {
                "open_time": b.open_time,
                "symbol": str(b.symbol),
                "ret_1": rets[i],
                "log_ret_1": log_rets[i],
                cols[4]: vol_roll[i],
                cols[5]: mom[i],
                cols[6]: rsi[i],
            }
        )

    return FeatureTable(
        schema_version=FEATURE_SCHEMA_VERSION,
        config=cfg,
        columns=cols,
        rows=rows,
    )
