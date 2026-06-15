from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

from crypto_bot.backtest.walk_forward import run_walk_forward_backtest
from crypto_bot.cli.artifact_resolve import resolve_daemon_artifact_dir
from crypto_bot.cli.train_baseline import _demo_bars
from crypto_bot.config import Settings
from crypto_bot.market_data.bars_csv import load_bars_csv
from crypto_bot.market_data.bars_parquet import load_bars_parquet
from crypto_bot.market_data.bars_sqlite import load_bars_sqlite
from crypto_bot.market_data.normalize import normalize_user_symbol
from crypto_bot.market_data.types import Symbol
from crypto_bot.model.artifacts import load_trend_artifact
from crypto_bot.risk import SpotBalanceFree


def main() -> None:
    p = argparse.ArgumentParser(
        description=(
            "Walk-forward backtest: each step uses history bars[:i+1] (no lookahead), "
            "feature_row → Orchestrator → paper. Use built-in demo OHLCV, --bars-csv, --bars-parquet, or --bars-sqlite."
        ),
    )
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--artifact-dir", type=Path, default=None)
    src.add_argument("--registry-name", default=None)
    p.add_argument("--registry-version", default="latest")
    p.add_argument("--registry-file", type=Path, default=None)
    p.add_argument(
        "--bars-csv",
        type=Path,
        default=None,
        help="OHLCV CSV (header: open_time,open,high,low,close,volume — time column may be timestamp/time; UTC ISO)",
    )
    p.add_argument(
        "--bars-parquet",
        type=Path,
        default=None,
        help="OHLCV Parquet (same columns as CSV; requires pip install 'crypto-bot[parquet]')",
    )
    p.add_argument(
        "--bars-sqlite",
        type=Path,
        default=None,
        help="SQLite DB with OHLCV table (symbol, open_time ISO, open, high, low, close, volume); see load_bars_sqlite",
    )
    p.add_argument(
        "--bars-sqlite-table",
        default="ohlcv",
        help="Table name inside --bars-sqlite (letters, digits, underscore only)",
    )
    p.add_argument(
        "--max-rows",
        type=int,
        default=None,
        help="Read at most this many data rows (CSV, Parquet, or SQLite, chronological)",
    )
    p.add_argument(
        "--n-bars",
        type=int,
        default=800,
        help="Demo sine bars when no --bars-csv / --bars-parquet / --bars-sqlite",
    )
    p.add_argument("--symbol", default="BTC/USDT")
    p.add_argument("--equity", type=float, default=10_000.0)
    p.add_argument("--quote-frac", type=float, default=0.01)
    p.add_argument("--json", action="store_true")
    p.add_argument(
        "--spot-quote-free",
        type=float,
        default=None,
        help="Optional free quote balance for risk cap (omit for no cap on that leg)",
    )
    p.add_argument("--spot-base-free", type=float, default=None)
    p.add_argument(
        "--mark-to-market",
        action="store_true",
        help="Risk equity each bar = cash + position * close (spot-style paper accounting)",
    )
    args = p.parse_args()
    bar_sources = sum(
        1 for x in (args.bars_csv, args.bars_parquet, args.bars_sqlite) if x is not None
    )
    if bar_sources > 1:
        p.error("Use at most one of --bars-csv, --bars-parquet, --bars-sqlite")
    settings = Settings()
    try:
        adir = resolve_daemon_artifact_dir(
            artifact_dir=args.artifact_dir,
            registry_name=args.registry_name,
            registry_version=args.registry_version,
            registry_file=args.registry_file,
            settings=settings,
        )
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        raise SystemExit(2) from e

    art = load_trend_artifact(adir)
    sym = Symbol(normalize_user_symbol(args.symbol))
    if args.bars_csv is not None:
        try:
            bars = load_bars_csv(args.bars_csv, symbol=sym, max_rows=args.max_rows)
        except (OSError, ValueError, FileNotFoundError) as e:
            print(f"error: {e}", file=sys.stderr)
            raise SystemExit(2) from e
    elif args.bars_parquet is not None:
        try:
            bars = load_bars_parquet(args.bars_parquet, symbol=sym, max_rows=args.max_rows)
        except ImportError as e:
            print(f"error: {e}", file=sys.stderr)
            raise SystemExit(2) from e
        except (OSError, ValueError, FileNotFoundError, TypeError) as e:
            print(f"error: {e}", file=sys.stderr)
            raise SystemExit(2) from e
    elif args.bars_sqlite is not None:
        try:
            bars = load_bars_sqlite(
                args.bars_sqlite,
                symbol=sym,
                table=args.bars_sqlite_table,
                max_rows=args.max_rows,
            )
        except (OSError, ValueError, FileNotFoundError) as e:
            print(f"error: {e}", file=sys.stderr)
            raise SystemExit(2) from e
    else:
        bars = _demo_bars(args.n_bars, sym)

    spot_bal = None
    if args.spot_quote_free is not None or args.spot_base_free is not None:
        q = float(args.spot_quote_free) if args.spot_quote_free is not None else math.inf
        b = float(args.spot_base_free) if args.spot_base_free is not None else math.inf
        spot_bal = SpotBalanceFree(quote=q, base=b)

    out = run_walk_forward_backtest(
        bars,
        art=art,
        symbol=str(sym),
        initial_equity=args.equity,
        quote_frac=args.quote_frac,
        spot_balance=spot_bal,
        mark_to_market=args.mark_to_market,
    )
    if args.json:
        json.dump(out, sys.stdout, indent=2, default=str)
        sys.stdout.write("\n")
    else:
        if "error" in out:
            print(f"error={out['error']} n_bars={out['n_bars']} required_bars={out.get('required_bars')}")
            raise SystemExit(1)
        print(f"steps={out['steps']} n_bars={out['n_bars']} warmup_skip_bars={out['warmup_skip_bars']}")
        print(f"trend_counts={out['trend_counts']}")
        print(f"risk_block_counts={out['risk_block_counts']}")
        print(f"n_fills={out['n_fills']}")
        if out.get("mark_to_market"):
            print(
                f"final_equity={out['final_equity']:.4f} "
                f"cash_quote={out['final_cash_quote']:.4f} pos_base={out['final_position_base']:.8f}"
            )


if __name__ == "__main__":
    main()
