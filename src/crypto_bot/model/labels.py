from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from crypto_bot.market_data.types import Bar
from crypto_bot.model.label_config import LabelConfig

LABEL_SCHEMA_VERSION = "1.0.0"


def _pop_std(xs: list[float]) -> float:
    if len(xs) < 2:
        return float("nan")
    m = sum(xs) / len(xs)
    v = sum((x - m) ** 2 for x in xs) / len(xs)
    return math.sqrt(v)


@dataclass(frozen=True)
class LabelTable:
    schema_version: str
    config: LabelConfig
    columns: tuple[str, ...]
    rows: list[dict[str, Any]]

    @staticmethod
    def empty(config: LabelConfig | None = None) -> LabelTable:
        cfg = config or LabelConfig()
        return LabelTable(
            schema_version=LABEL_SCHEMA_VERSION,
            config=cfg,
            columns=cfg.column_names(),
            rows=[],
        )


def compute_label_table(bars: Sequence[Bar], config: LabelConfig | None = None) -> LabelTable:
    """Forward labels aligned 1:1 with *bars* (NaN when future window is incomplete)."""
    cfg = config or LabelConfig()
    cols = cfg.column_names()
    if not bars:
        return LabelTable.empty(cfg)

    closes = [float(b.close) for b in bars]
    n = len(closes)
    h = cfg.horizon
    w = cfg.vol_forward
    fwd_ret = [float("nan")] * n
    trend_cls = [float("nan")] * n
    fwd_logvol = [float("nan")] * n

    eps = float(cfg.trend_epsilon)

    for i in range(n):
        if i + h < n and closes[i] != 0.0:
            r = closes[i + h] / closes[i] - 1.0
            fwd_ret[i] = r
            if r > eps:
                trend_cls[i] = 1.0
            elif r < -eps:
                trend_cls[i] = -1.0
            else:
                trend_cls[i] = 0.0
        if i + w < n:
            log_rets: list[float] = []
            ok = True
            for k in range(1, w + 1):
                a, b = closes[i + k - 1], closes[i + k]
                if a == 0.0:
                    ok = False
                    break
                log_rets.append(math.log(b / a))
            if ok and len(log_rets) == w:
                fwd_logvol[i] = _pop_std(log_rets)

    rows: list[dict[str, Any]] = []
    for i, b in enumerate(bars):
        rows.append(
            {
                "open_time": b.open_time,
                "symbol": str(b.symbol),
                cols[0]: fwd_ret[i],
                cols[1]: trend_cls[i],
                cols[2]: fwd_logvol[i],
            }
        )

    return LabelTable(schema_version=LABEL_SCHEMA_VERSION, config=cfg, columns=cols, rows=rows)
