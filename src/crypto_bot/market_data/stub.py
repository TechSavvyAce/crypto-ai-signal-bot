from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Sequence
from datetime import datetime, timedelta, timezone

from crypto_bot.market_data.provider import MarketDataProvider
from crypto_bot.market_data.types import Bar, Symbol


class StubMarketDataProvider(MarketDataProvider):
    """Synthetic bars for wiring tests before a real feed exists."""

    def __init__(self, *, base_price: float = 100.0, step_seconds: int = 60) -> None:
        self._base = base_price
        self._step = step_seconds

    async def stream_bars(self, symbol: Symbol) -> AsyncIterator[Bar]:
        t = datetime.now(timezone.utc).replace(second=0, microsecond=0)
        price = self._base
        while True:
            await asyncio.sleep(0.05)  # fast fake tick for demos
            o = price
            price = o * (1.0 + 0.001)
            h = max(o, price) * 1.0005
            low = min(o, price) * 0.9995
            c = price
            v = 1.0
            yield Bar(
                symbol=symbol,
                open_time=t,
                open=o,
                high=h,
                low=low,
                close=c,
                volume=v,
            )
            t += timedelta(seconds=self._step)

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

        out: list[Bar] = []
        t = start
        price = self._base
        while t < end:
            o = price
            price = o * (1.0 + 0.0003)
            h = max(o, price) * 1.0002
            low = min(o, price) * 0.9998
            c = price
            out.append(
                Bar(
                    symbol=symbol,
                    open_time=t,
                    open=o,
                    high=h,
                    low=low,
                    close=c,
                    volume=1.0,
                )
            )
            t += timedelta(seconds=self._step)
        return out
