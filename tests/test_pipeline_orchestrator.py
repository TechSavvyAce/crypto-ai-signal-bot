from __future__ import annotations

from datetime import datetime, timezone

from crypto_bot.execution import PaperExecutionEngine
from crypto_bot.pipeline import Orchestrator
from crypto_bot.risk import RiskEngine, RiskSessionState, RiskSettings


def test_orchestrator_flat_skips_order() -> None:
    t = datetime(2025, 6, 1, 12, 0, tzinfo=timezone.utc)
    risk = RiskEngine(RiskSettings(), RiskSessionState.start(10_000.0, t))
    paper = PaperExecutionEngine()
    orch = Orchestrator(risk=risk, execution=paper, symbol="BTC/USDT", model=None)
    out = orch.step(
        None,
        now=t,
        mark_equity=10_000.0,
        mark_price=50_000.0,
        client_order_id="c1",
        trend_override=0,
    )
    assert out.trend == 0
    assert out.order is None
    assert out.risk.allowed
    assert paper.fills == []


def test_orchestrator_long_places_market() -> None:
    t = datetime(2025, 6, 1, 12, 0, tzinfo=timezone.utc)
    risk = RiskEngine(RiskSettings(), RiskSessionState.start(10_000.0, t))
    paper = PaperExecutionEngine()
    orch = Orchestrator(risk=risk, execution=paper, symbol="BTC/USDT", model=None, quote_frac_per_signal=0.05)
    out = orch.step(
        None,
        now=t,
        mark_equity=10_000.0,
        mark_price=50_000.0,
        client_order_id="c2",
        trend_override=1,
    )
    assert out.trend == 1
    assert out.order is not None and out.order.ok
    assert len(paper.fills) == 1
    assert paper.fills[0].side == "buy"
