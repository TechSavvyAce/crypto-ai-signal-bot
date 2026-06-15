from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator, Sequence
from datetime import datetime, timezone
from typing import Any

import ccxt.async_support as ccxt_async

from crypto_bot.config import Settings
from crypto_bot.market_data.provider import MarketDataProvider
from crypto_bot.market_data.types import Bar, Symbol

logger = logging.getLogger(__name__)

_HIST_FETCH_MAX_ATTEMPTS = 6
_STREAM_BACKOFF_CAP_SEC = 60.0


def _ohlcv_row_to_bar(symbol: Symbol, row: list[float]) -> Bar:
    ts_ms = int(row[0])
    return Bar(
        symbol=symbol,
        open_time=datetime.fromtimestamp(ts_ms / 1000.0, tz=timezone.utc),
        open=float(row[1]),
        high=float(row[2]),
        low=float(row[3]),
        close=float(row[4]),
        volume=float(row[5]),
    )


class CcxtMarketDataProvider(MarketDataProvider):
    """OHLCV via CCXT async REST (historical + polling stream of closed bars).

    **Resilience:** ``fetch_historical`` retries each OHLCV page on transient errors
    (exponential sleep, capped). ``stream_bars`` uses exponential backoff on poll
    failures (capped) and resets after a successful fetch.
    """

    def __init__(
        self,
        exchange: Any,
        timeframe: str = "1m",
        *,
        poll_interval: float = 2.0,
    ) -> None:
        self._exchange = exchange
        self._timeframe = timeframe
        self._poll_interval = poll_interval

    @property
    def exchange(self) -> Any:
        """Underlying CCXT async exchange instance (markets loaded)."""
        return self._exchange

    def bar_period_seconds(self) -> float:
        """CCXT timeframe length in seconds (e.g. ``1m`` → 60)."""
        return float(self._exchange.parse_timeframe(self._timeframe))

    @classmethod
    async def create(
        cls,
        exchange_id: str,
        timeframe: str = "1m",
        *,
        poll_interval: float = 2.0,
        exchange_options: dict[str, Any] | None = None,
    ) -> CcxtMarketDataProvider:
        """Build a CCXT async exchange by id (e.g. ``binance``, ``kraken``)."""
        exchange_class = getattr(ccxt_async, exchange_id, None)
        if exchange_class is None:
            msg = f"Unknown CCXT exchange id: {exchange_id!r}"
            raise ValueError(msg)
        opts: dict[str, Any] = {"enableRateLimit": True}
        if exchange_options:
            opts.update(exchange_options)
        exchange = exchange_class(opts)
        try:
            await exchange.load_markets()
        except BaseException:
            try:
                await exchange.close()
            except Exception as exc:  # noqa: BLE001 — best-effort cleanup
                logger.warning("exchange.close() failed after load_markets error: %s", exc)
            raise
        return cls(exchange, timeframe, poll_interval=poll_interval)

    def _timeframe_ms(self) -> int:
        seconds = float(self._exchange.parse_timeframe(self._timeframe))
        return int(seconds * 1000)

    async def close(self) -> None:
        await self._exchange.close()

    async def fetch_historical(
        self,
        symbol: Symbol,
        start: datetime,
        end: datetime,
    ) -> Sequence[Bar]:
        if start.tzinfo is None or end.tzinfo is None:
            msg = "start and end must be timezone-aware (UTC)"
            raise ValueError(msg)
        if end <= start:
            return []

        tf_ms = self._timeframe_ms()
        start_ms = int(start.timestamp() * 1000)
        end_ms = int(end.timestamp() * 1000)
        bars: list[Bar] = []
        since = start_ms
        limit = 1000

        while since < end_ms:
            batch: list[list[float]] | None = None
            for attempt in range(_HIST_FETCH_MAX_ATTEMPTS):
                try:
                    batch = await self._exchange.fetch_ohlcv(
                        str(symbol),
                        self._timeframe,
                        since,
                        limit,
                    )
                    break
                except Exception:
                    if attempt >= _HIST_FETCH_MAX_ATTEMPTS - 1:
                        logger.exception(
                            "fetch_ohlcv failed in fetch_historical after %s attempts (since=%s)",
                            _HIST_FETCH_MAX_ATTEMPTS,
                            since,
                        )
                        raise
                    delay = min(30.0, 2.0**attempt)
                    logger.warning(
                        "fetch_ohlcv historical retry %s/%s in %.1fs (since=%s)",
                        attempt + 1,
                        _HIST_FETCH_MAX_ATTEMPTS,
                        delay,
                        since,
                    )
                    await asyncio.sleep(delay)
            assert batch is not None
            if not batch:
                break
            hit_end = False
            for row in batch:
                ts = int(row[0])
                if ts >= end_ms:
                    hit_end = True
                    break
                if ts < start_ms:
                    continue
                bars.append(_ohlcv_row_to_bar(symbol, row))
            last_ts = int(batch[-1][0])
            since = last_ts + tf_ms
            if hit_end or len(batch) < limit:
                break

        return bars

    async def stream_bars(self, symbol: Symbol) -> AsyncIterator[Bar]:
        tf_ms = self._timeframe_ms()
        last_emitted_open_ms: int | None = None
        consecutive_failures = 0

        while True:
            try:
                ohlcv: list[list[float]] = await self._exchange.fetch_ohlcv(
                    str(symbol),
                    self._timeframe,
                    limit=5,
                )
            except Exception:
                consecutive_failures += 1
                logger.exception(
                    "fetch_ohlcv failed during stream (try %s); backing off",
                    consecutive_failures,
                )
                delay = min(
                    _STREAM_BACKOFF_CAP_SEC,
                    max(self._poll_interval, 2.0 ** min(consecutive_failures, 6)),
                )
                await asyncio.sleep(delay)
                continue

            consecutive_failures = 0

            now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)

            for row in ohlcv:
                ts = int(row[0])
                if ts + tf_ms > now_ms:
                    continue
                if last_emitted_open_ms is not None and ts <= last_emitted_open_ms:
                    continue
                last_emitted_open_ms = ts
                yield _ohlcv_row_to_bar(symbol, row)

            await asyncio.sleep(self._poll_interval)


async def create_ccxt_provider_from_settings(settings: Settings) -> CcxtMarketDataProvider:
    """Wire :class:`CcxtMarketDataProvider` from :class:`~crypto_bot.config.Settings`."""
    opts: dict[str, Any] = {}
    if settings.ccxt_api_key:
        opts["apiKey"] = settings.ccxt_api_key
    if settings.ccxt_api_secret:
        opts["secret"] = settings.ccxt_api_secret
    return await CcxtMarketDataProvider.create(
        settings.ccxt_exchange,
        settings.ccxt_timeframe,
        poll_interval=settings.ccxt_poll_interval,
        exchange_options=opts or None,
    )
