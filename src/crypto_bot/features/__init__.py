"""Feature computation (Phase 2): versioned tabular features from OHLCV bars."""

from crypto_bot.features.config import FeatureConfig
from crypto_bot.features.engine import FeatureTable, compute_feature_table
from crypto_bot.features.schema import FEATURE_SCHEMA_VERSION

__all__ = [
    "FEATURE_SCHEMA_VERSION",
    "FeatureConfig",
    "FeatureTable",
    "compute_feature_table",
]
