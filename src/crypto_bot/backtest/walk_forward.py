from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from typing import Any

from crypto_bot.execution import PaperExecutionEngine
from crypto_bot.execution.types import FillRecord
from crypto_bot.loop.stub_daemon import feature_config_from_artifact, feature_row_for_model
from crypto_bot.market_data.types import Bar
from crypto_bot.model.artifacts import TrendClassifierArtifact
from crypto_bot.pipeline import Orchestrator
from crypto_bot.risk import RiskEngine, RiskSessionState, RiskSettings
from crypto_bot.risk.spot_balance import SpotBalanceFree


def _apply_paper_fill(cash_quote: float, pos_base: float, fill: FillRecord) -> tuple[float, float]:
    """Spot-style accounting: buy spends quote and adds base; sell does the reverse."""
    cost = float(fill.qty_base) * float(fill.fill_price)
    if fill.side == "buy":
        return cash_quote - cost, pos_base + float(fill.qty_base)
    return cash_quote + cost, pos_base - float(fill.qty_base)


def run_walk_forward_backtest(
    bars: Sequence[Bar],
    *,
    art: TrendClassifierArtifact,
    symbol: str,
    initial_equity: float,
    quote_frac: float,
    risk_settings: RiskSettings | None = None,
    spot_balance: SpotBalanceFree | None = None,
    mark_to_market: bool = False,
) -> dict[str, Any]:
    """Walk forward in time: each bar closes, recompute features on ``bars[:i+1]``, run :class:`Orchestrator`.

    By default **mark_equity** passed to risk is fixed at **initial_equity**. With **mark_to_market**,
    before each step ``mark_equity = cash_quote + position_base * bar.close`` after applying any new
    paper fills from the previous step (simple spot cash + marked position).
    """
    if len(bars) < 3:
        msg = "Need at least a few bars for backtest"
        raise ValueError(msg)

    feat_cfg = feature_config_from_artifact(art)
    start_index = feat_cfg.vol_window + feat_cfg.rsi_period + 5 - 1
    if start_index >= len(bars):
        return {
            "error": "insufficient_bars",
            "n_bars": len(bars),
            "required_bars": start_index + 1,
            "trend_counts": {},
            "risk_block_counts": {},
            "n_fills": 0,
            "steps": 0,
            "mark_to_market": bool(mark_to_market),
        }

    t0 = bars[start_index].open_time
    risk = RiskEngine(risk_settings or RiskSettings(), RiskSessionState.start(float(initial_equity), t0))
    paper = PaperExecutionEngine()
    orch = Orchestrator(
        risk=risk,
        execution=paper,
        symbol=symbol,
        model=art,
        quote_frac_per_signal=quote_frac,
    )

    trend_counts: Counter[int] = Counter()
    risk_block_counts: Counter[str] = Counter()

    cash_quote = float(initial_equity)
    pos_base = 0.0

    for i in range(start_index, len(bars)):
        bar = bars[i]
        slice_bars = list(bars[: i + 1])
        row = feature_row_for_model(slice_bars, art)
        px = float(bar.close)
        if mark_to_market:
            mark_eq = cash_quote + pos_base * px
        else:
            mark_eq = float(initial_equity)
        n_fills_before = len(paper.fills)
        out = orch.step(
            row,
            now=bar.open_time,
            mark_equity=mark_eq,
            mark_price=px,
            client_order_id=f"bt-{i}",
            spot_balance=spot_balance,
        )
        for f in paper.fills[n_fills_before:]:
            cash_quote, pos_base = _apply_paper_fill(cash_quote, pos_base, f)
        trend_counts[out.trend] += 1
        if not out.risk.allowed:
            risk_block_counts[out.risk.reason] += 1

    last_px = float(bars[-1].close)
    result: dict[str, Any] = {
        "n_bars": len(bars),
        "warmup_skip_bars": start_index,
        "steps": len(bars) - start_index,
        "trend_counts": dict(sorted(trend_counts.items())),
        "risk_block_counts": dict(sorted(risk_block_counts.items())),
        "n_fills": len(paper.fills),
        "mark_to_market": bool(mark_to_market),
    }
    if mark_to_market:
        result["final_cash_quote"] = cash_quote
        result["final_position_base"] = pos_base
        result["final_equity"] = cash_quote + pos_base * last_px
    return result
