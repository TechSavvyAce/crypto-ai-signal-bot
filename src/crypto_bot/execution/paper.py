from __future__ import annotations

from crypto_bot.execution.engine import ExecutionEngine
from crypto_bot.execution.types import FillRecord, OrderRequest, OrderResult, OrderSide


class PaperExecutionEngine(ExecutionEngine):
    """Immediate-fill simulator with **idempotent** ``client_order_id`` (safe retries)."""

    def __init__(self) -> None:
        self._idempotent: dict[str, OrderResult] = {}
        self.fills: list[FillRecord] = []
        self._seq = 0

    def submit(self, req: OrderRequest, *, mark_price: float) -> OrderResult:
        if req.client_order_id in self._idempotent:
            return self._idempotent[req.client_order_id]

        if req.qty_base <= 0 or mark_price <= 0:
            r = OrderResult(False, "rejected", "bad_qty_or_price", req.client_order_id)
            self._idempotent[req.client_order_id] = r
            return r

        if req.order_type == "limit":
            if req.limit_price is None or req.limit_price <= 0:
                r = OrderResult(False, "rejected", "limit_requires_limit_price", req.client_order_id)
                self._idempotent[req.client_order_id] = r
                return r
            if not _limit_is_marketable(req.side, float(req.limit_price), mark_price):
                r = OrderResult(False, "rejected", "limit_not_marketable_at_mark", req.client_order_id)
                self._idempotent[req.client_order_id] = r
                return r
            fill_price = float(req.limit_price)
        else:
            fill_price = float(mark_price)

        self._seq += 1
        self.fills.append(
            FillRecord(
                sequence=self._seq,
                client_order_id=req.client_order_id,
                symbol=req.symbol,
                side=req.side,
                qty_base=float(req.qty_base),
                fill_price=fill_price,
            )
        )
        r = OrderResult(True, "filled", "paper_fill", req.client_order_id)
        self._idempotent[req.client_order_id] = r
        return r


def _limit_is_marketable(side: OrderSide, limit_price: float, mark_price: float) -> bool:
    """V1: limit buy is marketable if mark at or below limit; limit sell if mark at or above."""
    if side == "buy":
        return mark_price <= limit_price
    return mark_price >= limit_price
