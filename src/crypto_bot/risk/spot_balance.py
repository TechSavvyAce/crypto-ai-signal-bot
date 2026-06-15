from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SpotBalanceFree:
    """Spot free balances for a single market (base / quote), used to cap notional before orders."""

    quote: float
    base: float
