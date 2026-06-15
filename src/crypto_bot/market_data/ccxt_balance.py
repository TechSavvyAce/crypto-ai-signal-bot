from __future__ import annotations

from typing import Any

from crypto_bot.risk.spot_balance import SpotBalanceFree


def split_spot_pair(symbol: str) -> tuple[str, str]:
    """Return (BASE, QUOTE) from ``BASE/QUOTE`` (CCXT unified symbol)."""
    s = symbol.strip().upper()
    if "/" not in s:
        msg = f"Expected BASE/QUOTE spot symbol, got {symbol!r}"
        raise ValueError(msg)
    base, quote = s.split("/", 1)
    b, q = base.strip(), quote.strip()
    if not b or not q:
        msg = f"Invalid spot symbol: {symbol!r}"
        raise ValueError(msg)
    return b, q


def free_amount_from_balance(balance: dict[str, Any], code: str) -> float:
    """Read CCXT unified ``fetch_balance`` free amount for *code* (e.g. ``USDT``)."""
    free = balance.get("free")
    if isinstance(free, dict) and code in free:
        return float(free.get(code) or 0.0)
    row = balance.get(code)
    if isinstance(row, dict) and "free" in row:
        return float(row.get("free") or 0.0)
    return 0.0


async def fetch_spot_balance_free(exchange: Any, symbol: str) -> SpotBalanceFree:
    """Async CCXT: ``fetch_balance`` → free base/quote for *symbol*."""
    base, quote = split_spot_pair(symbol)
    bal = await exchange.fetch_balance()
    return SpotBalanceFree(
        quote=free_amount_from_balance(bal, quote),
        base=free_amount_from_balance(bal, base),
    )
