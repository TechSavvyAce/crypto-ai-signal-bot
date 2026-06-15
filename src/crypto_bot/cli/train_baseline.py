from __future__ import annotations

import argparse
import math
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from crypto_bot.features import FeatureConfig, compute_feature_table
from crypto_bot.features.schema import FEATURE_SCHEMA_VERSION
from crypto_bot.market_data.normalize import normalize_user_symbol
from crypto_bot.market_data.types import Bar, Symbol
from crypto_bot.model.artifacts import save_trend_artifact
from crypto_bot.model.baseline import time_series_split, train_trend_logreg
from crypto_bot.model.dataset import build_xy_trend, join_features_labels
from crypto_bot.model.label_config import LabelConfig
from crypto_bot.model.labels import LABEL_SCHEMA_VERSION, compute_label_table
from crypto_bot.model.metrics import class_counts, majority_baseline_accuracy


def _demo_bars(n: int, symbol: Symbol) -> list[Bar]:
    """Synthetic OHLCV with mixed local trends so labels are not degenerate."""
    base = datetime(2020, 1, 1, tzinfo=timezone.utc)
    out: list[Bar] = []
    for i in range(n):
        t = base + timedelta(minutes=i)
        c = 100.0 + math.sin(i / 6.0) * 4.0 + (i % 5) * 0.12 + math.sin(i / 31.0) * 1.5
        out.append(
            Bar(
                symbol=symbol,
                open_time=t,
                open=c,
                high=c * 1.001,
                low=c * 0.999,
                close=c,
                volume=1.0,
            )
        )
    return out


def main() -> None:
    p = argparse.ArgumentParser(
        description="Train a baseline multinomial logistic model on trend class (synthetic demo bars).",
    )
    p.add_argument("--n-bars", type=int, default=800, help="Number of 1-minute demo candles")
    p.add_argument("--symbol", default="BTC/USDT", help="Symbol label on synthetic bars")
    p.add_argument("--horizon", type=int, default=5, help="Label forward horizon (bars)")
    p.add_argument("--vol-forward", type=int, default=5, help="Forward window for vol label")
    p.add_argument("--train-frac", type=float, default=0.7, help="Chronological train fraction")
    p.add_argument(
        "--feature-vol",
        type=int,
        default=15,
        help="Feature rolling vol window (must be < usable rows)",
    )
    p.add_argument(
        "--save-dir",
        default=None,
        help="If set, write classifier.joblib + meta.json for inference",
    )
    args = p.parse_args()

    symbol = Symbol(normalize_user_symbol(args.symbol))
    bars = _demo_bars(args.n_bars, symbol)
    if len(bars) < args.horizon + args.feature_vol + 5:
        print("error: not enough bars for chosen windows", file=sys.stderr)
        raise SystemExit(1)

    label_cfg = LabelConfig(horizon=args.horizon, vol_forward=args.vol_forward)
    feat_cfg = FeatureConfig(
        vol_window=args.feature_vol,
        mom_horizon=min(5, args.horizon),
        rsi_period=10,
    )
    ft = compute_feature_table(bars, feat_cfg)
    lt = compute_label_table(bars, label_cfg)
    supervised = join_features_labels(bars, ft, lt)
    trend_col = label_cfg.column_names()[1]
    X, y = build_xy_trend(supervised, trend_column=trend_col)
    if len(X) < 20:
        print(f"error: only {len(X)} complete rows after NaN drop; increase --n-bars", file=sys.stderr)
        raise SystemExit(1)

    x_tr, x_te, y_tr, y_te = time_series_split(X, y, train_frac=args.train_frac)
    try:
        out = train_trend_logreg(x_tr, y_tr, x_te, y_te)
    except RuntimeError as e:
        print(f"error: {e}", file=sys.stderr)
        raise SystemExit(4) from e

    maj_acc = majority_baseline_accuracy(y_te, y_tr)
    beats = out["test_accuracy"] > maj_acc

    print(f"rows={len(X)} train={len(x_tr)} test={len(x_te)} classes={out['classes']}")
    print(f"train_class_counts={class_counts(y_tr)} test_class_counts={class_counts(y_te)}")
    print(f"test_majority_baseline_accuracy={maj_acc:.4f}  # always predict train mode class")
    print(f"train_accuracy={out['train_accuracy']:.4f} test_accuracy={out['test_accuracy']:.4f}")
    print(f"model_beats_majority_baseline={beats}")

    if args.save_dir:
        out_dir = Path(args.save_dir)
        meta = {
            "feature_schema_version": FEATURE_SCHEMA_VERSION,
            "label_schema_version": LABEL_SCHEMA_VERSION,
            "trend_column": trend_col,
            "n_bars": args.n_bars,
            "horizon": args.horizon,
            "vol_forward": args.vol_forward,
            "train_frac": args.train_frac,
            "feature_vol_window": args.feature_vol,
            "mom_horizon": feat_cfg.mom_horizon,
            "rsi_period": feat_cfg.rsi_period,
            "train_accuracy": out["train_accuracy"],
            "test_accuracy": out["test_accuracy"],
            "test_majority_baseline_accuracy": maj_acc,
            "model_beats_majority_baseline": beats,
        }
        save_trend_artifact(out_dir, out["model"], supervised.feature_columns, meta)
        print(f"saved_artifact={out_dir.resolve()}")


if __name__ == "__main__":
    main()
