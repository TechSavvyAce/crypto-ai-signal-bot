from __future__ import annotations

from datetime import datetime, timezone
from typing import NewType

from pydantic import BaseModel, Field

Symbol = NewType("Symbol", str)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Bar(BaseModel):
    """Single OHLCV candle in UTC."""

    symbol: Symbol
    open_time: datetime = Field(description="Candle open, UTC")
    open: float
    high: float
    low: float
    close: float
    volume: float

    model_config = {"frozen": True}
