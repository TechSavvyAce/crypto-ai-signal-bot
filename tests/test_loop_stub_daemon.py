from __future__ import annotations

from pathlib import Path

import pytest

from crypto_bot.cli.train_baseline import _demo_bars
from crypto_bot.features import FeatureConfig, compute_feature_table
from crypto_bot.loop.stub_daemon import feature_config_from_artifact, feature_row_for_model
from crypto_bot.market_data.types import Symbol
from crypto_bot.model.artifacts import TrendClassifierArtifact, load_trend_artifact, save_trend_artifact
from crypto_bot.model.dataset import build_xy_trend, join_features_labels
from crypto_bot.model.label_config import LabelConfig
from crypto_bot.model.labels import compute_label_table


def test_feature_config_from_artifact_meta() -> None:
    art = TrendClassifierArtifact(
        classifier=None,
        feature_columns=(),
        meta={"horizon": 10, "feature_vol_window": 22, "mom_horizon": 4, "rsi_period": 9},
    )
    fc = feature_config_from_artifact(art)
    assert fc.vol_window == 22
    assert fc.mom_horizon == 4
    assert fc.rsi_period == 9


def test_feature_config_mom_default_uses_horizon_cap() -> None:
    art = TrendClassifierArtifact(
        classifier=None,
        feature_columns=(),
        meta={"horizon": 3},
    )
    fc = feature_config_from_artifact(art)
    assert fc.mom_horizon == 3


@pytest.mark.asyncio
async def test_feature_row_for_model_matches_saved_columns(tmp_path: Path) -> None:
    pytest.importorskip("sklearn")
    from sklearn.dummy import DummyClassifier

    symbol = Symbol("BTC/USDT")
    bars = _demo_bars(400, symbol)
    feat_cfg = FeatureConfig(vol_window=10, mom_horizon=5, rsi_period=10)
    label_cfg = LabelConfig(horizon=5, vol_forward=5)
    ft = compute_feature_table(bars, feat_cfg)
    lt = compute_label_table(bars, label_cfg)
    sup = join_features_labels(bars, ft, lt)
    trend_col = label_cfg.column_names()[1]
    X, y = build_xy_trend(sup, trend_column=trend_col)
    clf = DummyClassifier(strategy="most_frequent").fit(X, y)
    meta = {
        "horizon": 5,
        "feature_vol_window": 10,
        "mom_horizon": 5,
        "rsi_period": 10,
    }
    save_trend_artifact(tmp_path, clf, sup.feature_columns, meta)
    art = load_trend_artifact(tmp_path)
    row = feature_row_for_model(bars, art)
    assert tuple(sorted(row)) == tuple(sorted(art.feature_columns))
    assert art.predict_row(row) in (-1, 0, 1)


@pytest.mark.asyncio
async def test_run_stub_daemon_one_cycle(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    pytest.importorskip("sklearn")
    from sklearn.dummy import DummyClassifier

    import crypto_bot.loop.stub_daemon as sd

    symbol = Symbol("BTC/USDT")
    bars = _demo_bars(400, symbol)
    feat_cfg = FeatureConfig(vol_window=10, mom_horizon=5, rsi_period=10)
    label_cfg = LabelConfig(horizon=5, vol_forward=5)
    ft = compute_feature_table(bars, feat_cfg)
    lt = compute_label_table(bars, label_cfg)
    sup = join_features_labels(bars, ft, lt)
    trend_col = label_cfg.column_names()[1]
    X, y = build_xy_trend(sup, trend_column=trend_col)
    clf = DummyClassifier(strategy="most_frequent").fit(X, y)
    save_trend_artifact(
        tmp_path,
        clf,
        sup.feature_columns,
        {"horizon": 5, "feature_vol_window": 10, "mom_horizon": 5, "rsi_period": 10},
    )

    async def _no_sleep(_: float) -> None:
        return None

    monkeypatch.setattr(sd.asyncio, "sleep", _no_sleep)

    await sd.run_stub_daemon(
        artifact_dir=tmp_path,
        max_steps=1,
        window_minutes=800,
        sleep_s=0.0,
        equity=10_000.0,
        symbol="BTC/USDT",
        quote_frac=0.01,
    )


@pytest.mark.asyncio
async def test_run_stub_daemon_ccxt_dry_closes_sync_exchange(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    pytest.importorskip("sklearn")
    from sklearn.dummy import DummyClassifier

    import crypto_bot.loop.stub_daemon as sd

    from crypto_bot.config import Settings
    from crypto_bot.execution import CcxtExecutionEngine, PaperExecutionEngine

    symbol = Symbol("BTC/USDT")
    bars = _demo_bars(400, symbol)
    feat_cfg = FeatureConfig(vol_window=10, mom_horizon=5, rsi_period=10)
    label_cfg = LabelConfig(horizon=5, vol_forward=5)
    ft = compute_feature_table(bars, feat_cfg)
    lt = compute_label_table(bars, label_cfg)
    sup = join_features_labels(bars, ft, lt)
    trend_col = label_cfg.column_names()[1]
    X, y = build_xy_trend(sup, trend_column=trend_col)
    clf = DummyClassifier(strategy="most_frequent").fit(X, y)
    save_trend_artifact(
        tmp_path,
        clf,
        sup.feature_columns,
        {"horizon": 5, "feature_vol_window": 10, "mom_horizon": 5, "rsi_period": 10},
    )

    closed: list[int] = []

    class _Ex:
        def close(self) -> None:
            closed.append(1)

    def _fake_engine(_settings: Settings, mode: str):
        if mode == "ccxt-dry":
            return CcxtExecutionEngine(_Ex(), dry_run=True)
        return PaperExecutionEngine()

    async def _no_sleep(_: float) -> None:
        return None

    monkeypatch.setattr(sd, "create_execution_engine", _fake_engine)
    monkeypatch.setattr(sd.asyncio, "sleep", _no_sleep)

    await sd.run_stub_daemon(
        artifact_dir=tmp_path,
        max_steps=1,
        window_minutes=800,
        sleep_s=0.0,
        equity=10_000.0,
        symbol="BTC/USDT",
        quote_frac=0.01,
        settings=Settings(),
        execution_mode="ccxt-dry",
    )
    assert closed == [1]
