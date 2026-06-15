from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from crypto_bot.config import Settings
from crypto_bot.execution import CcxtExecutionEngine, create_execution_engine
from crypto_bot.loop.stub_daemon import (
    feature_config_from_artifact,
    feature_row_for_model,
)
from crypto_bot.market_data import create_ccxt_provider_from_settings
from crypto_bot.market_data.ccxt_balance import fetch_spot_balance_free
from crypto_bot.market_data.ccxt_provider import CcxtMarketDataProvider
from crypto_bot.market_data.normalize import (
    normalize_user_symbol,
    resolve_market_symbol,
    validate_timeframe,
)
from crypto_bot.market_data.provider import MarketDataProvider
from crypto_bot.market_data.types import Symbol
from crypto_bot.model.artifacts import load_trend_artifact
from crypto_bot.pipeline import Orchestrator
from crypto_bot.risk import RiskEngine, RiskSessionState, RiskSettings


async def run_ccxt_daemon(
    *,
    artifact_dir: Path,
    settings: Settings,
    symbol: str | None,
    max_steps: int,
    window_minutes: int,
    sleep_s: float,
    equity: float,
    quote_frac: float,
    provider: MarketDataProvider | None = None,
    execution_mode: str = "paper",
    use_balance_cap: bool = False,
) -> None:
    """Poll CCXT OHLCV (async REST), rebuild features, run :class:`Orchestrator` each cycle.

    *execution_mode*: ``paper`` | ``ccxt-dry`` | ``ccxt-live`` (see :func:`create_execution_engine`).

    If *provider* is set (e.g. tests), it is used instead of building from *settings* and
    symbol resolution skips the exchange when the provider is not :class:`CcxtMarketDataProvider`.

    When *use_balance_cap* is True and the provider is CCXT, each step calls ``fetch_balance``
    and passes free base/quote into risk sizing (requires credentials on most exchanges).
    """
    art = load_trend_artifact(artifact_dir)
    feat_cfg = feature_config_from_artifact(art)
    own_provider = provider is None
    md: MarketDataProvider | None = provider
    exec_engine = create_execution_engine(settings, execution_mode)
    try:
        if md is None:
            md = await create_ccxt_provider_from_settings(settings)

        symbol_raw = symbol or settings.default_symbol
        if isinstance(md, CcxtMarketDataProvider):
            validate_timeframe(md.exchange, settings.ccxt_timeframe)
            sym = resolve_market_symbol(md.exchange, symbol_raw)
        else:
            sym = Symbol(normalize_user_symbol(symbol_raw))

        risk = RiskEngine(RiskSettings(), RiskSessionState.start(equity, datetime.now(timezone.utc)))
        orch = Orchestrator(
            risk=risk,
            execution=exec_engine,
            symbol=str(sym),
            model=art,
            quote_frac_per_signal=quote_frac,
        )

        for i in range(max_steps):
            now = datetime.now(timezone.utc)
            min_wall_s = (feat_cfg.vol_window + feat_cfg.rsi_period + 10) * md.bar_period_seconds()
            span_s = max(float(window_minutes) * 60.0, min_wall_s)
            start = now - timedelta(seconds=span_s)
            bars = list(await md.fetch_historical(sym, start, now))
            if len(bars) < feat_cfg.vol_window + feat_cfg.rsi_period + 5:
                print(f"step={i} skip short_window bars={len(bars)}")
                await asyncio.sleep(sleep_s)
                continue
            row_vec = feature_row_for_model(bars, art)
            last_px = float(bars[-1].close)
            cid = str(uuid.uuid4())
            spot_bal = None
            if use_balance_cap and isinstance(md, CcxtMarketDataProvider):
                try:
                    spot_bal = await fetch_spot_balance_free(md.exchange, str(sym))
                except Exception as e:  # noqa: BLE001 — exchange-specific balance errors
                    print(f"step={i} warn balance_fetch_failed err={e!s}")
            out = orch.step(
                row_vec,
                now=now,
                mark_equity=equity,
                mark_price=last_px,
                client_order_id=cid,
                spot_balance=spot_bal,
            )
            print(
                f"step={i} trend={out.trend} risk_ok={out.risk.allowed} "
                f"order={out.order.status if out.order else None} note={out.note}"
            )
            await asyncio.sleep(sleep_s)
    finally:
        if own_provider and md is not None:
            await md.close()
        if isinstance(exec_engine, CcxtExecutionEngine):
            await asyncio.to_thread(exec_engine.close_sync)
