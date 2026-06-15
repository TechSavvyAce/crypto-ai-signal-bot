from __future__ import annotations

from pathlib import Path

import pytest

from crypto_bot.backtest.walk_forward import _apply_paper_fill, run_walk_forward_backtest
from crypto_bot.cli.train_baseline import _demo_bars
from crypto_bot.features import FeatureConfig, compute_feature_table
from crypto_bot.loop.stub_daemon import feature_config_from_artifact
from crypto_bot.market_data.types import Symbol
from crypto_bot.model.dataset import build_xy_trend, join_features_labels
from crypto_bot.model.label_config import LabelConfig
from crypto_bot.model.labels import compute_label_table
from crypto_bot.execution.types import FillRecord
from crypto_bot.model.artifacts import TrendClassifierArtifact, load_trend_artifact, save_trend_artifact


def test_apply_paper_fill_buy_sell() -> None:
    buy = FillRecord(
        sequence=1,
        client_order_id="a",
        symbol="BTC/USDT",
        side="buy",
        qty_base=1.0,
        fill_price=100.0,
    )
    cash, pos = _apply_paper_fill(1000.0, 0.0, buy)
    assert cash == 900.0 and pos == 1.0
    sell = FillRecord(
        sequence=2,
        client_order_id="b",
        symbol="BTC/USDT",
        side="sell",
        qty_base=0.5,
        fill_price=110.0,
    )
    cash2, pos2 = _apply_paper_fill(cash, pos, sell)
    assert cash2 == 900.0 + 55.0 and pos2 == 0.5


def test_walk_forward_insufficient_bars() -> None:
    art = TrendClassifierArtifact(classifier=None, feature_columns=("x",), meta={"horizon": 5})
    bars = _demo_bars(5, Symbol("BTC/USDT"))
    out = run_walk_forward_backtest(
        bars,
        art=art,
        symbol="BTC/USDT",
        initial_equity=10_000.0,
        quote_frac=0.01,
        mark_to_market=True,
    )
    assert out.get("error") == "insufficient_bars"
    assert out.get("mark_to_market") is True


@pytest.mark.parametrize("n_bars", [400, 800])
def test_walk_forward_runs_and_counts(n_bars: int, tmp_path: Path) -> None:
    sklearn = pytest.importorskip("sklearn")
    _ = sklearn
    from sklearn.dummy import DummyClassifier

    symbol = Symbol("BTC/USDT")
    bars = _demo_bars(n_bars, symbol)
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
    art = load_trend_artifact(tmp_path)
    out = run_walk_forward_backtest(
        bars,
        art=art,
        symbol="BTC/USDT",
        initial_equity=10_000.0,
        quote_frac=0.05,
    )
    assert "error" not in out
    fc = feature_config_from_artifact(art)
    start = fc.vol_window + fc.rsi_period + 5 - 1
    assert out["steps"] == n_bars - start
    assert out["n_fills"] >= 0
    assert sum(out["trend_counts"].values()) == out["steps"]
    assert out.get("mark_to_market") is False


def test_walk_forward_mark_to_market_final_fields(tmp_path: Path) -> None:
    sklearn = pytest.importorskip("sklearn")
    _ = sklearn
    from sklearn.dummy import DummyClassifier

    symbol = Symbol("BTC/USDT")
    bars = _demo_bars(800, symbol)
    feat_cfg = FeatureConfig(vol_window=10, mom_horizon=5, rsi_period=10)
    label_cfg = LabelConfig(horizon=5, vol_forward=5)
    ft = compute_feature_table(bars, feat_cfg)
    lt = compute_label_table(bars, label_cfg)
    sup = join_features_labels(bars, ft, lt)
    trend_col = label_cfg.column_names()[1]
    X, y = build_xy_trend(sup, trend_column=trend_col)
    clf = DummyClassifier(strategy="constant", constant=1).fit(X, y)
    save_trend_artifact(
        tmp_path,
        clf,
        sup.feature_columns,
        {"horizon": 5, "feature_vol_window": 10, "mom_horizon": 5, "rsi_period": 10},
    )
    art = load_trend_artifact(tmp_path)
    out = run_walk_forward_backtest(
        bars,
        art=art,
        symbol="BTC/USDT",
        initial_equity=10_000.0,
        quote_frac=0.05,
        mark_to_market=True,
    )
    assert "error" not in out
    assert out["mark_to_market"] is True
    assert out["n_fills"] > 0
    assert "final_cash_quote" in out and "final_position_base" in out and "final_equity" in out
    last_close = float(bars[-1].close)
    assert out["final_equity"] == pytest.approx(out["final_cash_quote"] + out["final_position_base"] * last_close)


def test_walk_forward_on_csv_file(tmp_path: Path) -> None:
    from datetime import datetime, timedelta, timezone

    pytest.importorskip("sklearn")
    from sklearn.dummy import DummyClassifier

    from crypto_bot.market_data.bars_csv import load_bars_csv

    sym = Symbol("BTC/USDT")
    csv_path = tmp_path / "m.csv"
    lines = ["open_time,open,high,low,close,volume"]
    base = datetime(2024, 1, 1, tzinfo=timezone.utc)
    for i in range(400):
        t = base + timedelta(minutes=i)
        c = 100.0 + i * 0.01
        lines.append(f"{t.isoformat()},{c},{c + 0.1},{c - 0.1},{c},1.0")
    csv_path.write_text("\n".join(lines), encoding="utf-8")
    bars_csv = load_bars_csv(csv_path, symbol=sym)

    feat_cfg = FeatureConfig(vol_window=10, mom_horizon=5, rsi_period=10)
    label_cfg = LabelConfig(horizon=5, vol_forward=5)
    ft = compute_feature_table(bars_csv, feat_cfg)
    lt = compute_label_table(bars_csv, label_cfg)
    sup = join_features_labels(bars_csv, ft, lt)
    trend_col = label_cfg.column_names()[1]
    X, y = build_xy_trend(sup, trend_column=trend_col)
    clf = DummyClassifier(strategy="most_frequent").fit(X, y)
    art_dir = tmp_path / "art"
    art_dir.mkdir()
    save_trend_artifact(
        art_dir,
        clf,
        sup.feature_columns,
        {"horizon": 5, "feature_vol_window": 10, "mom_horizon": 5, "rsi_period": 10},
    )
    art = load_trend_artifact(art_dir)
    out = run_walk_forward_backtest(
        bars_csv,
        art=art,
        symbol="BTC/USDT",
        initial_equity=10_000.0,
        quote_frac=0.05,
    )
    assert "error" not in out
    assert out["steps"] > 100
