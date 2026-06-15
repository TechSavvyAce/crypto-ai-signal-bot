from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

OrderSide = Literal["buy", "sell"]
OrderType = Literal["market", "limit"]


@dataclass(frozen=True)
class OrderRequest:
    """Intent to place one order (paper or live adapter maps this to exchange API)."""

    symbol: str
    side: OrderSide
    qty_base: float
    client_order_id: str
    order_type: OrderType = "market"
    limit_price: float | None = None


@dataclass(frozen=True)
class OrderResult:
    ok: bool
    status: str
    message: str
    client_order_id: str


@dataclass(frozen=True)
class FillRecord:
    """Single simulated fill (paper)."""

    sequence: int
    client_order_id: str
    symbol: str
    side: OrderSide
    qty_base: float
    fill_price: float
