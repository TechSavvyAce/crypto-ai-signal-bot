from __future__ import annotations

from pydantic import BaseModel, Field


class FeatureConfig(BaseModel):
    """Windows for baseline technical features."""

    model_config = {"frozen": True}

    vol_window: int = Field(default=20, ge=2, description="Rolling window for log-return volatility")
    mom_horizon: int = Field(default=10, ge=1, description="Momentum lookback in bars")
    rsi_period: int = Field(default=14, ge=2, description="RSI Wilder period")

    def column_names(self) -> tuple[str, ...]:
        return (
            "open_time",
            "symbol",
            "ret_1",
            "log_ret_1",
            f"vol_roll_{self.vol_window}",
            f"mom_{self.mom_horizon}",
            f"rsi_{self.rsi_period}",
        )
