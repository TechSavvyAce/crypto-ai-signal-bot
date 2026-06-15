from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from crypto_bot.risk.config import RiskSettings
from crypto_bot.risk.spot_balance import SpotBalanceFree
from crypto_bot.risk.state import RiskSessionState

Side = Literal[-1, 0, 1]


@dataclass(frozen=True)
class TradeIntent:
    """Desired exposure change before risk checks."""

    symbol: str
    side: Side  # -1 short, 0 flat, 1 long
    entry_price: float
    desired_notional_quote: float
    reduce_only: bool = False


@dataclass(frozen=True)
class RiskDecision:
    allowed: bool
    reason: str
    notional_quote: float
    qty_base: float
    stop_price: float | None
    reduce_only: bool


class RiskEngine:
    """Pre-trade sizing, stops, daily loss kill-switch (minimal v1)."""

    def __init__(self, settings: RiskSettings, session: RiskSessionState) -> None:
        self._cfg = settings
        self._session = session
        self._kill_switch = False

    @property
    def kill_switch(self) -> bool:
        return self._kill_switch

    @property
    def session(self) -> RiskSessionState:
        return self._session

    def sync_and_update(self, *, now: datetime, mark_equity: float) -> None:
        """Roll UTC session day if needed, then update kill-switch from drawdown."""
        rolled = self._session.roll_if_new_utc_day(now, mark_equity)
        if rolled:
            self._kill_switch = False
        start = self._session.session_start_equity
        if start > 0:
            dd = (start - mark_equity) / start
            if dd >= self._cfg.max_daily_loss_frac:
                self._kill_switch = True

    def reset_kill_switch(self) -> None:
        """Manual override (e.g. after operator acknowledgement)."""
        self._kill_switch = False

    def _stop_for(self, intent: TradeIntent) -> float | None:
        if intent.side == 0 or intent.entry_price <= 0:
            return None
        f = float(self._cfg.stop_loss_frac)
        if intent.side == 1:
            return intent.entry_price * (1.0 - f)
        return intent.entry_price * (1.0 + f)

    def evaluate(
        self,
        intent: TradeIntent,
        *,
        now: datetime,
        mark_equity: float,
        spot_balance: SpotBalanceFree | None = None,
    ) -> RiskDecision:
        self.sync_and_update(now=now, mark_equity=mark_equity)

        if intent.entry_price <= 0:
            return RiskDecision(False, "bad_entry_price", 0.0, 0.0, None, intent.reduce_only)

        if intent.side == 0:
            return RiskDecision(True, "flat", 0.0, 0.0, None, intent.reduce_only)

        if self._kill_switch and not intent.reduce_only:
            return RiskDecision(False, "kill_switch_daily_loss", 0.0, 0.0, None, True)

        cap_eq = float(mark_equity) * float(self._cfg.max_position_frac_equity)
        cap_lev = float(mark_equity) * float(self._cfg.max_leverage)
        cap = min(cap_eq, cap_lev)
        raw = abs(float(intent.desired_notional_quote))
        sized = min(raw, cap)

        if spot_balance is not None:
            buf = 1.0 - min(float(self._cfg.balance_clip_buffer_frac), 0.25)
            if intent.side == 1 and math.isfinite(spot_balance.quote):
                sized = min(sized, max(0.0, float(spot_balance.quote)) * buf)
            elif intent.side == -1 and math.isfinite(spot_balance.base):
                sized = min(sized, max(0.0, float(spot_balance.base)) * buf * float(intent.entry_price))

        if sized <= 0:
            return RiskDecision(
                False,
                "insufficient_balance",
                0.0,
                0.0,
                self._stop_for(intent),
                intent.reduce_only,
            )

        if sized < float(self._cfg.min_order_notional_quote):
            return RiskDecision(False, "below_min_notional", 0.0, 0.0, self._stop_for(intent), intent.reduce_only)

        qty = sized / intent.entry_price
        return RiskDecision(
            True,
            "ok",
            sized,
            qty,
            self._stop_for(intent),
            intent.reduce_only,
        )
