"""Execution: order submission adapters (Phase 5)."""

from crypto_bot.execution.ccxt_sync import CcxtExecutionEngine, create_ccxt_execution_sync
from crypto_bot.execution.engine import ExecutionEngine
from crypto_bot.execution.factory import create_execution_engine
from crypto_bot.execution.paper import PaperExecutionEngine
from crypto_bot.execution.types import FillRecord, OrderRequest, OrderResult, OrderSide

__all__ = [
    "CcxtExecutionEngine",
    "ExecutionEngine",
    "FillRecord",
    "OrderRequest",
    "OrderResult",
    "OrderSide",
    "PaperExecutionEngine",
    "create_ccxt_execution_sync",
    "create_execution_engine",
]
