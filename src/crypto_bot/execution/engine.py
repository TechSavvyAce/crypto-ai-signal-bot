from __future__ import annotations

from abc import ABC, abstractmethod

from crypto_bot.execution.types import OrderRequest, OrderResult


class ExecutionEngine(ABC):
    """Exchange or paper adapter: submit orders, return normalized outcomes."""

    @abstractmethod
    def submit(self, req: OrderRequest, *, mark_price: float) -> OrderResult:
        """Execute or queue *req*; *mark_price* is reference mid for paper fills."""
        ...
