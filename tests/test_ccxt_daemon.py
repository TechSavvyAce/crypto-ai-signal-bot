from __future__ import annotations

from pathlib import Path

import pytest

from crypto_bot.config import Settings
from crypto_bot.loop.ccxt_daemon import run_ccxt_daemon
from crypto_bot.market_data import StubMarketDataProvider


@pytest.mark.asyncio
async def test_ccxt_daemon_one_cycle_with_injected_stub(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    pytest.importorskip("sklearn")
    from sklearn.dummy import DummyClassifier

    import crypto_bot.loop.ccxt_daemon as cd

    from crypto_bot.cli.train_baseline import _demo_bars
    from crypto_bot.features import FeatureConfig, compute_feature_table
    from crypto_bot.market_data.types import Symbol
    from crypto_bot.model.artifacts import save_trend_artifact
    from crypto_bot.model.dataset import build_xy_trend, join_features_labels
    from crypto_bot.model.label_config import LabelConfig
    from crypto_bot.model.labels import compute_label_table

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

    monkeypatch.setattr(cd.asyncio, "sleep", _no_sleep)

    stub = StubMarketDataProvider()
    await run_ccxt_daemon(
        artifact_dir=tmp_path,
        settings=Settings(),
        symbol="BTC/USDT",
        max_steps=1,
        window_minutes=800,
        sleep_s=0.0,
        equity=10_000.0,
        quote_frac=0.01,
        provider=stub,
    )
