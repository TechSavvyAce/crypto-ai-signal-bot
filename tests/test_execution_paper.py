from __future__ import annotations

from crypto_bot.execution import OrderRequest, PaperExecutionEngine


def test_paper_market_fill() -> None:
    ex = PaperExecutionEngine()
    r = ex.submit(
        OrderRequest("BTC/USDT", "buy", 0.01, "cid-1"),
        mark_price=50_000.0,
    )
    assert r.ok and r.status == "filled"
    assert len(ex.fills) == 1
    assert ex.fills[0].fill_price == 50_000.0


def test_paper_idempotent_same_client_order_id() -> None:
    ex = PaperExecutionEngine()
    req = OrderRequest("BTC/USDT", "buy", 0.02, "cid-repeat")
    a = ex.submit(req, mark_price=100.0)
    b = ex.submit(req, mark_price=999.0)
    assert a == b
    assert len(ex.fills) == 1


def test_paper_limit_buy_not_marketable() -> None:
    ex = PaperExecutionEngine()
    r = ex.submit(
        OrderRequest("BTC/USDT", "buy", 0.01, "cid-2", order_type="limit", limit_price=40_000.0),
        mark_price=50_000.0,
    )
    assert not r.ok
    assert r.status == "rejected"


def test_paper_limit_buy_fills_when_mark_below_limit() -> None:
    ex = PaperExecutionEngine()
    r = ex.submit(
        OrderRequest("BTC/USDT", "buy", 0.01, "cid-3", order_type="limit", limit_price=51_000.0),
        mark_price=50_000.0,
    )
    assert r.ok
    assert ex.fills[0].fill_price == 51_000.0


def test_paper_limit_sell_marketable() -> None:
    ex = PaperExecutionEngine()
    r = ex.submit(
        OrderRequest("BTC/USDT", "sell", 0.01, "cid-4", order_type="limit", limit_price=49_000.0),
        mark_price=50_000.0,
    )
    assert r.ok
    assert ex.fills[0].fill_price == 49_000.0
