from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from crypto_bot.config import Settings
from crypto_bot.execution import CcxtExecutionEngine, create_execution_engine
from crypto_bot.features import FeatureConfig, compute_feature_table
from crypto_bot.market_data import StubMarketDataProvider
from crypto_bot.market_data.types import Symbol
from crypto_bot.model.artifacts import TrendClassifierArtifact, load_trend_artifact
from crypto_bot.pipeline import Orchestrator
from crypto_bot.risk import RiskEngine, RiskSessionState, RiskSettings


def feature_config_from_artifact(art: TrendClassifierArtifact) -> FeatureConfig:
    """Rebuild training feature windows from artifact ``meta.json``."""
    m = art.meta
    horizon = int(m.get("horizon", 5))
    return FeatureConfig(
        vol_window=int(m.get("feature_vol_window", 15)),
        mom_horizon=int(m.get("mom_horizon", min(5, horizon))),
        rsi_period=int(m.get("rsi_period", 10)),
    )


def feature_row_for_model(bars: list, art: TrendClassifierArtifact) -> dict[str, float]:
    """Last bar’s feature vector with only columns the classifier expects."""
    ft = compute_feature_table(bars, feature_config_from_artifact(art))
    row = ft.rows[-1]
    return {k: float(row[k]) for k in art.feature_columns}


async def run_stub_daemon(
    *,
    artifact_dir: Path,
    max_steps: int,
    window_minutes: int,
    sleep_s: float,
    equity: float,
    symbol: str,
    quote_frac: float,
    settings: Settings | None = None,
    execution_mode: str = "paper",
) -> None:
    """Poll stub OHLCV, rebuild features, run :class:`Orchestrator` each cycle."""
    art = load_trend_artifact(artifact_dir)
    feat_cfg = feature_config_from_artifact(art)
    sym = Symbol(symbol)
    cfg = settings or Settings()
    exec_engine = create_execution_engine(cfg, execution_mode)
    stub = StubMarketDataProvider()
    risk = RiskEngine(RiskSettings(), RiskSessionState.start(equity, datetime.now(timezone.utc)))
    orch = Orchestrator(
        risk=risk,
        execution=exec_engine,
        symbol=symbol,
        model=art,
        quote_frac_per_signal=quote_frac,
    )
    try:
        for i in range(max_steps):
            now = datetime.now(timezone.utc)
            min_wall_s = (feat_cfg.vol_window + feat_cfg.rsi_period + 10) * stub.bar_period_seconds()
            span_s = max(float(window_minutes) * 60.0, min_wall_s)
            start = now - timedelta(seconds=span_s)
            bars = list(await stub.fetch_historical(sym, start, now))
            if len(bars) < feat_cfg.vol_window + feat_cfg.rsi_period + 5:
                print(f"step={i} skip short_window bars={len(bars)}")
                await asyncio.sleep(sleep_s)
                continue
            row_vec = feature_row_for_model(bars, art)
            last_px = float(bars[-1].close)
            cid = str(uuid.uuid4())
            out = orch.step(
                row_vec,
                now=now,
                mark_equity=equity,
                mark_price=last_px,
                client_order_id=cid,
            )
            print(
                f"step={i} trend={out.trend} risk_ok={out.risk.allowed} "
                f"order={out.order.status if out.order else None} note={out.note}"
            )
            await asyncio.sleep(sleep_s)
    finally:
        await stub.close()
        if isinstance(exec_engine, CcxtExecutionEngine):
            await asyncio.to_thread(exec_engine.close_sync)
