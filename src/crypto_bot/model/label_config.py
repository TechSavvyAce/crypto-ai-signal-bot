from __future__ import annotations

from pydantic import BaseModel, Field


class LabelConfig(BaseModel):
    """Forward-looking targets derived from future closes (training / evaluation only)."""

    model_config = {"frozen": True}

    horizon: int = Field(default=5, ge=1, description="Bars ahead for return / trend label")
    trend_epsilon: float = Field(default=1e-4, ge=0.0, description="|fwd_ret| below this → flat class")
    vol_forward: int = Field(
        default=5,
        ge=2,
        description="Count of one-bar forward log-returns used for vol label",
    )

    def column_names(self) -> tuple[str, ...]:
        h, w = self.horizon, self.vol_forward
        return (
            f"fwd_ret_{h}",
            f"trend_cls_{h}",
            f"fwd_logvol_{w}",
        )
