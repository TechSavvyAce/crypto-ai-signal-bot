from __future__ import annotations

from typing import Any

from crypto_bot.config import Settings
from crypto_bot.execution.ccxt_sync import create_ccxt_execution_sync
from crypto_bot.execution.engine import ExecutionEngine
from crypto_bot.execution.paper import PaperExecutionEngine


def create_execution_engine(settings: Settings, mode: str) -> ExecutionEngine:
    """Build an :class:`ExecutionEngine` for daemons and tools.

    * **paper** — :class:`PaperExecutionEngine` only.
    * **ccxt-dry** — :class:`CcxtExecutionEngine` with ``dry_run=True`` (orders still filled via
      internal paper; sync exchange object is constructed for parity with live wiring).
    * **ccxt-live** — :class:`CcxtExecutionEngine` with ``dry_run=False`` (**real spot market
      orders** when risk approves). Requires non-empty ``CRYPTO_BOT_CCXT_API_KEY`` /
      ``CRYPTO_BOT_CCXT_API_SECRET`` and ``CRYPTO_BOT_LIVE_TRADING_ACK=true`` (intentional opt-in).
    """
    key = mode.strip().lower().replace("-", "_")
    if key == "paper":
        return PaperExecutionEngine()
    opts: dict[str, Any] = {}
    if settings.ccxt_api_key:
        opts["apiKey"] = settings.ccxt_api_key
    if settings.ccxt_api_secret:
        opts["secret"] = settings.ccxt_api_secret

    if key == "ccxt_dry":
        return create_ccxt_execution_sync(
            settings.ccxt_exchange,
            dry_run=True,
            exchange_options=opts or None,
        )
    if key == "ccxt_live":
        if not settings.live_trading_ack:
            msg = (
                "Live execution refused: set CRYPTO_BOT_LIVE_TRADING_ACK=true in the environment "
                "after you understand real capital is at risk (see README 'Live trading')."
            )
            raise ValueError(msg)
        if not (settings.ccxt_api_key and settings.ccxt_api_secret):
            msg = "Live execution requires CRYPTO_BOT_CCXT_API_KEY and CRYPTO_BOT_CCXT_API_SECRET"
            raise ValueError(msg)
        return create_ccxt_execution_sync(
            settings.ccxt_exchange,
            dry_run=False,
            exchange_options=opts,
        )
    msg = f"Unknown execution mode {mode!r} (expected paper, ccxt-dry, or ccxt-live)"
    raise ValueError(msg)
