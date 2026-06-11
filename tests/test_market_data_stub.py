from datetime import datetime, timedelta, timezone

import pytest

from crypto_bot.market_data import StubMarketDataProvider
from crypto_bot.market_data.types import Symbol


@pytest.mark.asyncio
async def test_stub_historical_empty_when_end_before_start() -> None:
    p = StubMarketDataProvider()
    start = datetime(2024, 1, 2, tzinfo=timezone.utc)
    end = datetime(2024, 1, 1, tzinfo=timezone.utc)
    bars = await p.fetch_historical(Symbol("BTC/USDT"), start, end)
    assert bars == []


@pytest.mark.asyncio
async def test_stub_historical_returns_ascending_bars() -> None:
    p = StubMarketDataProvider(step_seconds=60)
    start = datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc)
    end = start + timedelta(minutes=5)
    bars = await p.fetch_historical(Symbol("BTC/USDT"), start, end)
    assert len(bars) == 5
    assert bars[0].open_time < bars[1].open_time
    assert bars[0].symbol == "BTC/USDT"
