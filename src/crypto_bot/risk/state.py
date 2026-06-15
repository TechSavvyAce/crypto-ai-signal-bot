from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone


@dataclass
class RiskSessionState:
    """Rolling UTC-day session anchor for daily loss tracking."""

    session_start_equity: float
    session_date: date

    @classmethod
    def start(cls, equity: float, now: datetime) -> RiskSessionState:
        d = now.astimezone(timezone.utc).date()
        return cls(session_start_equity=float(equity), session_date=d)

    def roll_if_new_utc_day(self, now: datetime, mark_equity: float) -> bool:
        """If *now* is a new UTC calendar day, reset anchor to *mark_equity*. Returns True if rolled."""
        d = now.astimezone(timezone.utc).date()
        if d != self.session_date:
            self.session_date = d
            self.session_start_equity = float(mark_equity)
            return True
        return False
