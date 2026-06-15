from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Sequence
from datetime import datetime

from crypto_bot.market_data.types import Bar, Symbol


class MarketDataProvider(ABC):
    """Exchange or replay source of normalized bars."""

    def bar_period_seconds(self) -> float:
        """Seconds between consecutive bar opens for this feed (used for min history windows)."""
        return 60.0

    @abstractmethod
    async def stream_bars(self, symbol: Symbol) -> AsyncIterator[Bar]:
        """Yield new bars as they close (provider defines timeframe)."""
        ...

    @abstractmethod
    async def fetch_historical(
        self,
        symbol: Symbol,
        start: datetime,
        end: datetime,
    ) -> Sequence[Bar]:
        """Closed bars in [start, end), UTC, ascending by open_time."""
        ...
