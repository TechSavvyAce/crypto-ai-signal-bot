from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from crypto_bot.market_data.normalize import (
    align_range_to_timeframe,
    floor_bar_open_utc,
    normalize_user_symbol,
    require_utc,
    resolve_market_symbol,
    validate_timeframe,
)
from crypto_bot.market_data.types import Symbol


def test_normalize_user_symbol_hyphen_to_slash() -> None:
    assert normalize_user_symbol("btc-usdt") == "BTC/USDT"


def test_normalize_user_symbol_slash_passthrough() -> None:
    assert normalize_user_symbol("ETH/USDT") == "ETH/USDT"


def test_require_utc_rejects_naive() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        require_utc(datetime(2024, 1, 1))


def test_require_utc_converts_to_utc() -> None:
    dt = datetime(2024, 1, 1, 12, 0, tzinfo=timezone(timedelta(hours=2)))
    out = require_utc(dt)
    assert out.utcoffset() == timezone.utc.utcoffset(None)
    assert out.hour == 10


def test_resolve_market_symbol() -> None:
    class Ex:
        id = "fake"
        markets = {"BTC/USDT": {"symbol": "BTC/USDT"}}

    assert resolve_market_symbol(Ex(), "btc-usdt") == Symbol("BTC/USDT")


def test_resolve_market_symbol_unknown() -> None:
    class Ex:
        id = "fake"
        markets: dict = {}

    with pytest.raises(ValueError, match="Unknown market"):
        resolve_market_symbol(Ex(), "NOPE/USDT")


def test_validate_timeframe() -> None:
    class Ex:
        id = "fake"

        def parse_timeframe(self, tf: str) -> float:
            if tf == "1m":
                return 60.0
            raise ValueError("bad")

    assert validate_timeframe(Ex(), "1m") == "1m"
    with pytest.raises(ValueError, match="Invalid timeframe"):
        validate_timeframe(Ex(), "99x")


def test_floor_bar_open_utc() -> None:
    t = datetime(2024, 6, 1, 12, 3, 45, tzinfo=timezone.utc)
    floored = floor_bar_open_utc(t, 60.0)
    assert floored == datetime(2024, 6, 1, 12, 3, 0, tzinfo=timezone.utc)


def test_align_range_to_timeframe() -> None:
    start = datetime(2024, 6, 1, 12, 3, 45, tzinfo=timezone.utc)
    end = datetime(2024, 6, 1, 12, 7, 10, tzinfo=timezone.utc)
    a, b = align_range_to_timeframe(start, end, 60.0)
    assert a == datetime(2024, 6, 1, 12, 3, 0, tzinfo=timezone.utc)
    assert b == datetime(2024, 6, 1, 12, 8, 0, tzinfo=timezone.utc)
