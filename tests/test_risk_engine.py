from __future__ import annotations

from datetime import datetime, timezone

import pytest

from crypto_bot.risk import RiskEngine, RiskSessionState, RiskSettings, SpotBalanceFree, TradeIntent


@pytest.fixture
def cfg() -> RiskSettings:
    return RiskSettings(
        max_daily_loss_frac=0.02,
        max_position_frac_equity=0.5,
        max_leverage=3.0,
        stop_loss_frac=0.01,
        min_order_notional_quote=5.0,
    )


def test_stop_long_short(cfg: RiskSettings) -> None:
    t0 = datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)
    s = RiskSessionState.start(10_000.0, t0)
    eng = RiskEngine(cfg, s)
    long_i = TradeIntent("BTC/USDT", 1, 100.0, 1000.0)
    d = eng.evaluate(long_i, now=t0, mark_equity=10_000.0)
    assert d.stop_price == pytest.approx(99.0)
    short_i = TradeIntent("BTC/USDT", -1, 100.0, 1000.0)
    d2 = eng.evaluate(short_i, now=t0, mark_equity=10_000.0)
    assert d2.stop_price == pytest.approx(101.0)


def test_min_notional_rejects(cfg: RiskSettings) -> None:
    t0 = datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)
    eng = RiskEngine(cfg, RiskSessionState.start(10_000.0, t0))
    i = TradeIntent("BTC/USDT", 1, 50_000.0, 2.0)
    d = eng.evaluate(i, now=t0, mark_equity=10_000.0)
    assert not d.allowed
    assert d.reason == "below_min_notional"


def test_daily_loss_kill_blocks_new_risk(cfg: RiskSettings) -> None:
    t0 = datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)
    eng = RiskEngine(cfg, RiskSessionState.start(10_000.0, t0))
    eng.sync_and_update(now=t0, mark_equity=9750.0)
    assert eng.kill_switch
    i = TradeIntent("BTC/USDT", 1, 100.0, 1000.0)
    d = eng.evaluate(i, now=t0, mark_equity=9750.0)
    assert not d.allowed
    assert d.reason == "kill_switch_daily_loss"


def test_reduce_only_allowed_under_kill(cfg: RiskSettings) -> None:
    t0 = datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)
    eng = RiskEngine(cfg, RiskSessionState.start(10_000.0, t0))
    eng.sync_and_update(now=t0, mark_equity=9750.0)
    i = TradeIntent("BTC/USDT", 1, 100.0, 1000.0, reduce_only=True)
    d = eng.evaluate(i, now=t0, mark_equity=9750.0)
    assert d.allowed


def test_new_utc_day_resets_kill(cfg: RiskSettings) -> None:
    d1 = datetime(2025, 1, 1, 23, 0, tzinfo=timezone.utc)
    d2 = datetime(2025, 1, 2, 1, 0, tzinfo=timezone.utc)
    eng = RiskEngine(cfg, RiskSessionState.start(10_000.0, d1))
    eng.sync_and_update(now=d1, mark_equity=9750.0)
    assert eng.kill_switch
    eng.sync_and_update(now=d2, mark_equity=10_000.0)
    assert not eng.kill_switch


def test_spot_balance_caps_buy_notional(cfg: RiskSettings) -> None:
    t0 = datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)
    eng = RiskEngine(cfg, RiskSessionState.start(10_000.0, t0))
    i = TradeIntent("BTC/USDT", 1, 50_000.0, 5000.0)
    d = eng.evaluate(i, now=t0, mark_equity=10_000.0, spot_balance=SpotBalanceFree(quote=100.0, base=0.0))
    assert d.allowed
    buf = 1.0 - cfg.balance_clip_buffer_frac
    assert d.notional_quote == pytest.approx(100.0 * buf)


def test_spot_balance_caps_sell_notional(cfg: RiskSettings) -> None:
    t0 = datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)
    eng = RiskEngine(cfg, RiskSessionState.start(10_000.0, t0))
    i = TradeIntent("BTC/USDT", -1, 50_000.0, 5000.0)
    d = eng.evaluate(i, now=t0, mark_equity=10_000.0, spot_balance=SpotBalanceFree(quote=9_999.0, base=0.01))
    assert d.allowed
    buf = 1.0 - cfg.balance_clip_buffer_frac
    assert d.notional_quote == pytest.approx(0.01 * buf * 50_000.0)


def test_spot_balance_zero_quote_blocks_buy(cfg: RiskSettings) -> None:
    t0 = datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)
    eng = RiskEngine(cfg, RiskSessionState.start(10_000.0, t0))
    i = TradeIntent("BTC/USDT", 1, 50_000.0, 5000.0)
    d = eng.evaluate(i, now=t0, mark_equity=10_000.0, spot_balance=SpotBalanceFree(quote=0.0, base=1.0))
    assert not d.allowed
    assert d.reason == "insufficient_balance"
