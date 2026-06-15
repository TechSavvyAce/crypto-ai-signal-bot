from __future__ import annotations

import pytest

from crypto_bot.config import Settings
from crypto_bot.execution import CcxtExecutionEngine, PaperExecutionEngine
from crypto_bot.execution.factory import create_execution_engine


def test_factory_paper() -> None:
    e = create_execution_engine(Settings(), "paper")
    assert isinstance(e, PaperExecutionEngine)


def test_factory_unknown_mode() -> None:
    with pytest.raises(ValueError, match="Unknown execution mode"):
        create_execution_engine(Settings(), "live-now")


def test_factory_ccxt_dry_uses_mocked_sync_build(monkeypatch: pytest.MonkeyPatch) -> None:
    from crypto_bot.execution import factory as factory_mod

    def fake_create(
        exchange_id: str,
        *,
        dry_run: bool = True,
        exchange_options: dict | None = None,
    ) -> CcxtExecutionEngine:
        assert dry_run is True
        assert exchange_id == "binance"

        class _Ex:
            def close(self) -> None:
                return None

        return CcxtExecutionEngine(_Ex(), dry_run=True)

    monkeypatch.setattr(factory_mod, "create_ccxt_execution_sync", fake_create)
    e = create_execution_engine(Settings(ccxt_exchange="binance"), "ccxt-dry")
    assert isinstance(e, CcxtExecutionEngine)
    e.close_sync()


def test_factory_ccxt_live_requires_ack() -> None:
    s = Settings(ccxt_api_key="k", ccxt_api_secret="s", live_trading_ack=False)
    with pytest.raises(ValueError, match="LIVE_TRADING_ACK"):
        create_execution_engine(s, "ccxt-live")


def test_factory_ccxt_live_requires_keys() -> None:
    s = Settings(live_trading_ack=True)
    with pytest.raises(ValueError, match="API_KEY"):
        create_execution_engine(s, "ccxt-live")


def test_factory_ccxt_live_uses_mocked_sync_build(monkeypatch: pytest.MonkeyPatch) -> None:
    from crypto_bot.execution import factory as factory_mod

    def fake_create(
        exchange_id: str,
        *,
        dry_run: bool = True,
        exchange_options: dict | None = None,
    ) -> CcxtExecutionEngine:
        assert dry_run is False
        assert exchange_id == "binance"
        assert exchange_options is not None and "apiKey" in exchange_options

        class _Ex:
            def close(self) -> None:
                return None

        return CcxtExecutionEngine(_Ex(), dry_run=False)

    monkeypatch.setattr(factory_mod, "create_ccxt_execution_sync", fake_create)
    s = Settings(
        ccxt_exchange="binance",
        ccxt_api_key="k",
        ccxt_api_secret="s",
        live_trading_ack=True,
    )
    e = create_execution_engine(s, "ccxt-live")
    assert isinstance(e, CcxtExecutionEngine)
    assert e.dry_run is False
    e.close_sync()
