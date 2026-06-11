from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from crypto_bot.market_data.types import Symbol


def require_utc(dt: datetime) -> datetime:
    """Return *dt* as an aware UTC timestamp. Rejects naive datetimes."""
    if dt.tzinfo is None:
        msg = "datetime must be timezone-aware (use UTC)"
        raise ValueError(msg)
    return dt.astimezone(timezone.utc)


def normalize_user_symbol(raw: str) -> str:
    """Normalize common user input toward CCXT unified ``BASE/QUOTE`` form."""
    s = raw.strip()
    if not s:
        msg = "symbol must be non-empty"
        raise ValueError(msg)
    if "/" in s:
        return s
    if "-" in s:
        base, _, quote = s.partition("-")
        if quote:
            return f"{base.strip().upper()}/{quote.strip().upper()}"
    return s


def resolve_market_symbol(exchange: Any, raw: str) -> Symbol:
    """Resolve *raw* against ``exchange.markets`` after light normalization."""
    candidate = normalize_user_symbol(raw)
    if candidate not in exchange.markets:
        msg = f"Unknown market symbol {candidate!r} for {exchange.id}"
        raise ValueError(msg)
    market = exchange.markets[candidate]
    unified = market.get("symbol") or candidate
    return Symbol(str(unified))


def validate_timeframe(exchange: Any, timeframe: str) -> str:
    """Ensure *timeframe* parses for this exchange (CCXT convention)."""
    try:
        seconds = float(exchange.parse_timeframe(timeframe))
    except (TypeError, ValueError, AttributeError) as e:
        msg = f"Invalid timeframe {timeframe!r} for {getattr(exchange, 'id', 'exchange')}"
        raise ValueError(msg) from e
    if seconds <= 0:
        msg = f"Invalid timeframe {timeframe!r} for {getattr(exchange, 'id', 'exchange')}"
        raise ValueError(msg)
    return timeframe


def floor_bar_open_utc(open_time: datetime, timeframe_seconds: float) -> datetime:
    """Floor *open_time* (UTC) to the start of a bar of length *timeframe_seconds*."""
    t = require_utc(open_time)
    step_ms = int(round(float(timeframe_seconds) * 1000))
    if step_ms <= 0:
        msg = "timeframe_seconds must be positive"
        raise ValueError(msg)
    ts_ms = int(t.timestamp() * 1000)
    floored_ms = (ts_ms // step_ms) * step_ms
    return datetime.fromtimestamp(floored_ms / 1000.0, tz=timezone.utc)


def align_range_to_timeframe(
    start: datetime,
    end: datetime,
    timeframe_seconds: float,
) -> tuple[datetime, datetime]:
    """Return aligned ``(start_floor, end_ceil)`` in UTC for bar-grid windows.

    *end_ceil* is the smallest bar boundary ``>= end`` (ms resolution), useful when
    *end* is an arbitrary wall clock and you want a stable OHLCV ``[start, end)`` slice.
    """
    s = require_utc(start)
    e = require_utc(end)
    if e <= s:
        msg = "end must be after start"
        raise ValueError(msg)
    start_floor = floor_bar_open_utc(s, timeframe_seconds)
    step_ms = int(round(float(timeframe_seconds) * 1000))
    if step_ms <= 0:
        msg = "timeframe_seconds must be positive"
        raise ValueError(msg)
    e_ms = int(e.timestamp() * 1000)
    end_ceil_ms = ((e_ms + step_ms - 1) // step_ms) * step_ms
    end_ceil = datetime.fromtimestamp(end_ceil_ms / 1000.0, tz=timezone.utc)
    if end_ceil <= start_floor:
        end_ceil = start_floor + timedelta(milliseconds=step_ms)
    return start_floor, end_ceil
