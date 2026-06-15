from __future__ import annotations

from datetime import datetime

from crypto_bot.execution import ExecutionEngine, OrderRequest
from crypto_bot.model.artifacts import TrendClassifierArtifact
from crypto_bot.pipeline.types import PipelineStepResult
from crypto_bot.risk import RiskEngine, TradeIntent
from crypto_bot.risk.spot_balance import SpotBalanceFree


class Orchestrator:
    """Wire trend signal → ``TradeIntent`` → ``RiskEngine`` → ``ExecutionEngine``."""

    def __init__(
        self,
        *,
        risk: RiskEngine,
        execution: ExecutionEngine,
        symbol: str,
        model: TrendClassifierArtifact | None = None,
        quote_frac_per_signal: float = 0.01,
    ) -> None:
        self._risk = risk
        self._exec = execution
        self._symbol = symbol
        self._model = model
        if not (0.0 < quote_frac_per_signal <= 1.0):
            msg = "quote_frac_per_signal must be in (0, 1]"
            raise ValueError(msg)
        self._quote_frac = float(quote_frac_per_signal)

    def _trend_from(
        self,
        feature_row: dict,
        trend_override: int | None,
    ) -> int:
        if trend_override is not None:
            if trend_override not in (-1, 0, 1):
                msg = "trend_override must be -1, 0, or 1"
                raise ValueError(msg)
            return int(trend_override)
        if self._model is None:
            msg = "Either pass trend_override or construct Orchestrator with a model"
            raise ValueError(msg)
        return int(self._model.predict_row(feature_row))

    @staticmethod
    def _intent_for_trend(
        trend: int,
        symbol: str,
        entry_price: float,
        desired_notional_quote: float,
    ) -> TradeIntent:
        if trend == 0:
            return TradeIntent(symbol, 0, entry_price, 0.0)
        side = 1 if trend == 1 else -1
        return TradeIntent(symbol, side, entry_price, abs(float(desired_notional_quote)))

    def step(
        self,
        feature_row: dict | None,
        *,
        now: datetime,
        mark_equity: float,
        mark_price: float,
        client_order_id: str,
        trend_override: int | None = None,
        spot_balance: SpotBalanceFree | None = None,
    ) -> PipelineStepResult:
        if trend_override is None and self._model is not None:
            if not feature_row:
                msg = "feature_row is required when using a trained model"
                raise ValueError(msg)
            row = feature_row
        else:
            row = feature_row or {}
        trend = self._trend_from(row, trend_override)
        desired = float(mark_equity) * self._quote_frac
        intent = self._intent_for_trend(trend, self._symbol, mark_price, desired)
        rd = self._risk.evaluate(intent, now=now, mark_equity=mark_equity, spot_balance=spot_balance)

        if intent.side == 0 or rd.notional_quote <= 0 or not rd.allowed:
            note = rd.reason if not rd.allowed else "flat_or_zero_size"
            return PipelineStepResult(trend, rd, None, note)

        side: str = "buy" if intent.side == 1 else "sell"
        req = OrderRequest(
            self._symbol,
            side,
            rd.qty_base,
            client_order_id,
            order_type="market",
        )
        res = self._exec.submit(req, mark_price=mark_price)
        return PipelineStepResult(trend, rd, res, "submitted")
