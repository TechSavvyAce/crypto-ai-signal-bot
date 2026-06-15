from __future__ import annotations

import pytest

from crypto_bot.market_data.ccxt_balance import (
    fetch_spot_balance_free,
    free_amount_from_balance,
    split_spot_pair,
)


def test_split_spot_pair() -> None:
    assert split_spot_pair("btc/usdt") == ("BTC", "USDT")


def test_split_spot_pair_rejects_non_slash() -> None:
    with pytest.raises(ValueError, match="BASE/QUOTE"):
        split_spot_pair("BTCUSDT")


def test_free_amount_top_level_free_dict() -> None:
    bal = {"free": {"USDT": 100.5, "BTC": 0.01}}
    assert free_amount_from_balance(bal, "USDT") == pytest.approx(100.5)
    assert free_amount_from_balance(bal, "BTC") == pytest.approx(0.01)


def test_free_amount_nested_currency_rows() -> None:
    bal = {"USDT": {"free": 50.0, "used": 0.0, "total": 50.0}}
    assert free_amount_from_balance(bal, "USDT") == pytest.approx(50.0)


@pytest.mark.asyncio
async def test_fetch_spot_balance_free_mock_exchange() -> None:
    class Ex:
        async def fetch_balance(self) -> dict:
            return {"free": {"BTC": 0.02, "USDT": 123.0}}

    b = await fetch_spot_balance_free(Ex(), "BTC/USDT")
    assert b.base == pytest.approx(0.02)
    assert b.quote == pytest.approx(123.0)
