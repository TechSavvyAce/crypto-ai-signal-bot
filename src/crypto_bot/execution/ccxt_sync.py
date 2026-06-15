from __future__ import annotations

from typing import Any

from crypto_bot.execution.engine import ExecutionEngine
from crypto_bot.execution.paper import PaperExecutionEngine
from crypto_bot.execution.types import OrderRequest, OrderResult


class CcxtExecutionEngine(ExecutionEngine):
    """Sync CCXT exchange wrapper. **dry_run** delegates to an internal :class:`PaperExecutionEngine`."""

    def __init__(
        self,
        exchange: Any,
        *,
        dry_run: bool = True,
        paper: PaperExecutionEngine | None = None,
    ) -> None:
        self._ex = exchange
        self._dry_run = bool(dry_run)
        self._paper = paper or PaperExecutionEngine()
        self._live_results: dict[str, OrderResult] = {}

    @property
    def dry_run(self) -> bool:
        """When False, :meth:`submit` sends real exchange orders (spot market only in v1)."""
        return self._dry_run

    @property
    def paper(self) -> PaperExecutionEngine:
        """The simulator used when ``dry_run`` is True (same instance across submits)."""
        return self._paper

    def submit(self, req: OrderRequest, *, mark_price: float) -> OrderResult:
        if self._dry_run:
            return self._paper.submit(req, mark_price=mark_price)

        if req.client_order_id in self._live_results:
            return self._live_results[req.client_order_id]

        if req.order_type != "market":
            r = OrderResult(False, "rejected", "live_limit_not_supported", req.client_order_id)
            self._live_results[req.client_order_id] = r
            return r

        if req.qty_base <= 0:
            r = OrderResult(False, "rejected", "bad_qty", req.client_order_id)
            self._live_results[req.client_order_id] = r
            return r

        cid = req.client_order_id[:36]
        params = {"newClientOrderId": cid}
        try:
            if req.side == "buy":
                self._ex.create_market_buy_order(req.symbol, req.qty_base, params)
            else:
                self._ex.create_market_sell_order(req.symbol, req.qty_base, params)
        except Exception as e:  # noqa: BLE001 — exchange-specific errors
            r = OrderResult(False, "error", str(e)[:500], req.client_order_id)
            self._live_results[req.client_order_id] = r
            return r

        r = OrderResult(True, "filled", "live_exchange", req.client_order_id)
        self._live_results[req.client_order_id] = r
        return r

    def close_sync(self) -> None:
        """Close the underlying sync CCXT exchange (HTTP sessions). Safe to call multiple times."""
        closer = getattr(self._ex, "close", None)
        if callable(closer):
            closer()


def create_ccxt_execution_sync(
    exchange_id: str,
    *,
    dry_run: bool = True,
    exchange_options: dict[str, Any] | None = None,
) -> CcxtExecutionEngine:
    """Build a sync ``ccxt`` exchange by id (e.g. ``binance``)."""
    import ccxt  # local import: optional for importers who only use paper

    klass = getattr(ccxt, exchange_id, None)
    if klass is None:
        msg = f"Unknown sync CCXT exchange id: {exchange_id!r}"
        raise ValueError(msg)
    opts: dict[str, Any] = {"enableRateLimit": True}
    if exchange_options:
        opts.update(exchange_options)
    return CcxtExecutionEngine(klass(opts), dry_run=dry_run)
