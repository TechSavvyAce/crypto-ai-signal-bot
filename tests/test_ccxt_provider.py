from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from crypto_bot.market_data import CcxtMarketDataProvider, Symbol


class _FakeExchange:
    """Minimal async exchange surface used by CcxtMarketDataProvider."""

    def parse_timeframe(self, timeframe: str) -> float:
        return 60.0

    def __init__(self, ohlcv_responses: list[list[list[float]]]) -> None:
        self.ohlcv_responses = ohlcv_responses
        self.call_index = 0

    async def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        since: int | None = None,
        limit: int | None = None,
    ) -> list[list[float]]:
        if self.call_index < len(self.ohlcv_responses):
            out = self.ohlcv_responses[self.call_index]
            self.call_index += 1
            return out
        return []

    async def close(self) -> None:
        return None


@pytest.mark.asyncio
async def test_fetch_historical_paginates_and_respects_end() -> None:
    start = datetime(2024, 6, 1, 0, 0, tzinfo=timezone.utc)
    start_ms = int(start.timestamp() * 1000)
    tf_ms = 60_000
    row0 = [start_ms + 0 * tf_ms, 1, 1, 1, 1, 1.0]
    row1 = [start_ms + 1 * tf_ms, 2, 2, 2, 2, 2.0]
    row2 = [start_ms + 2 * tf_ms, 3, 3, 3, 3, 3.0]
    ex = _FakeExchange([[row0, row1], [row2]])
    p = CcxtMarketDataProvider(ex, "1m")
    end = start + timedelta(minutes=2)
    bars = await p.fetch_historical(Symbol("BTC/USDT"), start, end)
    assert len(bars) == 2
    assert bars[0].open == 1.0
    assert bars[1].open == 2.0
    await p.close()


@pytest.mark.asyncio
async def test_fetch_historical_stops_when_batch_crosses_end() -> None:
    start = datetime(2024, 6, 1, 0, 0, tzinfo=timezone.utc)
    start_ms = int(start.timestamp() * 1000)
    tf_ms = 60_000
    row0 = [start_ms, 1, 1, 1, 1, 1.0]
    row_cross = [start_ms + 5 * tf_ms, 9, 9, 9, 9, 9.0]
    ex = _FakeExchange([[row0, row_cross]])
    p = CcxtMarketDataProvider(ex, "1m")
    end = start + timedelta(minutes=3)
    bars = await p.fetch_historical(Symbol("BTC/USDT"), start, end)
    assert len(bars) == 1
    assert bars[0].open == 1.0
    await p.close()


@pytest.mark.asyncio
async def test_create_rejects_unknown_exchange() -> None:
    with pytest.raises(ValueError, match="Unknown CCXT"):
        await CcxtMarketDataProvider.create("not_a_real_ccxt_exchange_id_xyz")


@pytest.mark.asyncio
async def test_stream_yields_closed_bar_once() -> None:
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    tf_ms = 60_000
    t0 = now_ms - 3 * tf_ms
    row = [t0, 10.0, 11.0, 9.0, 10.5, 7.0]
    ex = _FakeExchange([[row]])
    p = CcxtMarketDataProvider(ex, "1m", poll_interval=0.01)
    gen = p.stream_bars(Symbol("ETH/USDT"))
    try:
        bar = await asyncio.wait_for(anext(gen), timeout=2.0)
    finally:
        await gen.aclose()
        await p.close()
    assert bar.close == 10.5
    assert bar.symbol == "ETH/USDT"


@pytest.mark.asyncio
async def test_create_closes_exchange_when_load_markets_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    import crypto_bot.market_data.ccxt_provider as cp

    class Boom:
        last: object | None = None

        def __init__(self, opts: dict) -> None:
            type(self).last = self
            self.closed = False

        async def load_markets(self) -> None:
            msg = "dns"
            raise OSError(msg)

        async def close(self) -> None:
            self.closed = True

    monkeypatch.setattr(cp.ccxt_async, "binance", Boom, raising=True)
    with pytest.raises(OSError, match="dns"):
        await CcxtMarketDataProvider.create("binance")
    assert Boom.last is not None
    assert getattr(Boom.last, "closed") is True


class _HistFlakyExchange:
    """Fails fetch_ohlcv ``fail_first`` times, then returns one batch."""

    def parse_timeframe(self, timeframe: str) -> float:
        return 60.0

    def __init__(self, fail_first: int, rows: list[list[float]]) -> None:
        self._fail_left = fail_first
        self._rows = rows

    async def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        since: int | None = None,
        limit: int | None = None,
    ) -> list[list[float]]:
        if self._fail_left > 0:
            self._fail_left -= 1
            msg = "transient"
            raise OSError(msg)
        return [list(r) for r in self._rows]

    async def close(self) -> None:
        return None


@pytest.mark.asyncio
async def test_fetch_historical_retries_transient_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    async def no_sleep(_: float) -> None:
        return None

    monkeypatch.setattr(asyncio, "sleep", no_sleep)

    start = datetime(2024, 6, 1, 0, 0, tzinfo=timezone.utc)
    start_ms = int(start.timestamp() * 1000)
    row0 = [start_ms, 1.0, 1.0, 1.0, 1.0, 1.0]
    ex = _HistFlakyExchange(2, [row0])
    p = CcxtMarketDataProvider(ex, "1m")
    end = start + timedelta(minutes=1)
    bars = await p.fetch_historical(Symbol("BTC/USDT"), start, end)
    assert len(bars) == 1
    assert bars[0].open == 1.0
    await p.close()


@pytest.mark.asyncio
async def test_fetch_historical_raises_after_max_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    async def no_sleep(_: float) -> None:
        return None

    monkeypatch.setattr(asyncio, "sleep", no_sleep)

    class AlwaysFail:
        def parse_timeframe(self, timeframe: str) -> float:
            return 60.0

        async def fetch_ohlcv(
            self,
            symbol: str,
            timeframe: str,
            since: int | None = None,
            limit: int | None = None,
        ) -> list[list[float]]:
            raise OSError("always")

        async def close(self) -> None:
            return None

    start = datetime(2024, 6, 1, 0, 0, tzinfo=timezone.utc)
    ex = AlwaysFail()
    p = CcxtMarketDataProvider(ex, "1m")
    end = start + timedelta(minutes=1)
    with pytest.raises(OSError, match="always"):
        await p.fetch_historical(Symbol("BTC/USDT"), start, end)
    await p.close()


@pytest.mark.asyncio
async def test_stream_exponential_backoff_on_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    async def no_sleep(_: float) -> None:
        return None

    monkeypatch.setattr(asyncio, "sleep", no_sleep)

    class FlakyStream:
        def parse_timeframe(self, timeframe: str) -> float:
            return 60.0

        def __init__(self) -> None:
            self.calls = 0

        async def fetch_ohlcv(
            self,
            symbol: str,
            timeframe: str,
            since: int | None = None,
            limit: int | None = None,
        ) -> list[list[float]]:
            self.calls += 1
            if self.calls <= 2:
                raise ConnectionError("boom")
            now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
            t0 = now_ms - 3 * 60_000
            return [[t0, 10.0, 11.0, 9.0, 10.5, 7.0]]

        async def close(self) -> None:
            return None

    ex = FlakyStream()
    p = CcxtMarketDataProvider(ex, "1m", poll_interval=0.01)
    gen = p.stream_bars(Symbol("ETH/USDT"))
    try:
        bar = await asyncio.wait_for(anext(gen), timeout=2.0)
    finally:
        await gen.aclose()
        await p.close()
    assert ex.calls == 3
    assert bar.close == 10.5
