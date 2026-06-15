from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class RiskSettings(BaseSettings):
    """Risk limits; override with ``CRYPTO_BOT_RISK_*`` environment variables."""

    model_config = SettingsConfigDict(env_prefix="CRYPTO_BOT_RISK_", env_file=".env", extra="ignore")

    max_daily_loss_frac: float = Field(
        default=0.02,
        ge=0.0,
        le=1.0,
        description="Session kill-switch when (start_equity - equity) / start_equity reaches this",
    )
    max_position_frac_equity: float = Field(
        default=0.1,
        ge=0.0,
        le=1.0,
        description="Cap notional as fraction of mark-to-market equity",
    )
    max_leverage: float = Field(default=3.0, ge=1.0, description="Hard cap on notional / equity")
    stop_loss_frac: float = Field(
        default=0.01,
        ge=0.0,
        le=0.5,
        description="Stop distance from entry as fraction of price (symmetric long/short)",
    )
    min_order_notional_quote: float = Field(
        default=10.0,
        ge=0.0,
        description="Reject orders below this notional (quote currency, e.g. USDT)",
    )
    balance_clip_buffer_frac: float = Field(
        default=0.002,
        ge=0.0,
        le=0.25,
        description="When spot free balances are supplied, scale them by (1 - this) before capping size",
    )
