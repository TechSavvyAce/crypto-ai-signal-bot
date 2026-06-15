from __future__ import annotations

import pytest

from crypto_bot.execution import CcxtExecutionEngine, create_ccxt_execution_sync
from crypto_bot.execution.types import OrderRequest


class _FakeExchange:
    def __init__(self, *, fail: bool = False) -> None:
        self.calls: list[tuple[str, str, float, dict]] = []
        self._fail = fail

    def create_market_buy_order(self, symbol: str, amount: float, params: dict | None = None) -> dict:
        if self._fail:
            msg = "simulated_exchange_error"
            raise RuntimeError(msg)
        self.calls.append(("buy", symbol, float(amount), dict(params or {})))
        return {"id": "1", "status": "closed"}

    def create_market_sell_order(self, symbol: str, amount: float, params: dict | None = None) -> dict:
        self.calls.append(("sell", symbol, float(amount), dict(params or {})))
        return {"id": "2", "status": "closed"}


def test_ccxt_dry_run_delegates_to_paper_idempotency() -> None:
    ex = CcxtExecutionEngine(_FakeExchange(), dry_run=True)
    req = OrderRequest("BTC/USDT", "buy", 0.01, "same-cid", "market")
    r1 = ex.submit(req, mark_price=50_000.0)
    r2 = ex.submit(req, mark_price=50_000.0)
    assert r1.ok and r2.ok
    assert r1.client_order_id == r2.client_order_id == "same-cid"


def test_ccxt_live_market_buy_and_idempotent() -> None:
    fake = _FakeExchange()
    ex = CcxtExecutionEngine(fake, dry_run=False)
    req = OrderRequest("BTC/USDT", "buy", 0.001, "cid-live-1", "market")
    r1 = ex.submit(req, mark_price=1.0)
    r2 = ex.submit(req, mark_price=1.0)
    assert r1.ok and r2.ok
    assert len(fake.calls) == 1
    assert fake.calls[0][0] == "buy"
    assert fake.calls[0][3].get("newClientOrderId") == "cid-live-1"[:36]


def test_ccxt_live_rejects_limit() -> None:
    ex = CcxtExecutionEngine(_FakeExchange(), dry_run=False)
    req = OrderRequest("BTC/USDT", "buy", 0.01, "cid-lim", "limit")
    r = ex.submit(req, mark_price=1.0)
    assert not r.ok
    assert "live_limit" in r.message


def test_ccxt_live_maps_exception_to_order_result() -> None:
    ex = CcxtExecutionEngine(_FakeExchange(fail=True), dry_run=False)
    req = OrderRequest("BTC/USDT", "buy", 0.01, "cid-err", "market")
    r1 = ex.submit(req, mark_price=1.0)
    assert not r1.ok
    r2 = ex.submit(req, mark_price=1.0)
    assert not r2.ok
    assert r1.client_order_id == r2.client_order_id


def test_create_ccxt_unknown_exchange_raises() -> None:
    with pytest.raises(ValueError, match="Unknown"):
        create_ccxt_execution_sync("not_a_real_ccxt_exchange_id_xyz123")
