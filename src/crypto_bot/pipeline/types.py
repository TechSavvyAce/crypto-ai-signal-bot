from __future__ import annotations

from dataclasses import dataclass

from crypto_bot.execution.types import OrderResult
from crypto_bot.risk.engine import RiskDecision


@dataclass(frozen=True)
class PipelineStepResult:
    """One decision cycle: trend → risk → optional paper order."""

    trend: int
    risk: RiskDecision
    order: OrderResult | None
    note: str
