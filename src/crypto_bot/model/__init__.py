"""Model: labels, datasets, baseline trainers (Phase 3)."""

from crypto_bot.model.artifacts import (
    TrendClassifierArtifact,
    load_trend_artifact,
    save_trend_artifact,
)
from crypto_bot.model.baseline import time_series_split, train_trend_logreg
from crypto_bot.model.dataset import (
    SupervisedTable,
    build_xy_trend,
    default_feature_columns,
    join_features_labels,
)
from crypto_bot.model.label_config import LabelConfig
from crypto_bot.model.labels import LABEL_SCHEMA_VERSION, LabelTable, compute_label_table
from crypto_bot.model.metrics import accuracy, class_counts, majority_baseline_accuracy

__all__ = [
    "LABEL_SCHEMA_VERSION",
    "LabelConfig",
    "LabelTable",
    "SupervisedTable",
    "TrendClassifierArtifact",
    "accuracy",
    "build_xy_trend",
    "class_counts",
    "compute_label_table",
    "default_feature_columns",
    "join_features_labels",
    "load_trend_artifact",
    "majority_baseline_accuracy",
    "save_trend_artifact",
    "time_series_split",
    "train_trend_logreg",
]
