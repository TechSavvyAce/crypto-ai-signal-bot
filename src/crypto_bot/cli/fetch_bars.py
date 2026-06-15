from __future__ import annotations

import argparse
import asyncio
import csv
import json
import logging
import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone

import aiohttp

from ccxt.base.errors import ExchangeNotAvailable

from crypto_bot.config import Settings
from crypto_bot.features import FeatureConfig, FeatureTable, compute_feature_table
from crypto_bot.market_data import (
    StubMarketDataProvider,
    create_ccxt_provider_from_settings,
)
from crypto_bot.market_data.bars_parquet import save_bars_parquet
from crypto_bot.market_data.bars_sqlite import append_bars_sqlite
from crypto_bot.market_data.normalize import (
    normalize_user_symbol,
    resolve_market_symbol,
    validate_timeframe,
)
from crypto_bot.market_data.types import Bar, Symbol


def _parse_iso_utc(s: str) -> datetime:
    dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _print_network_help() -> None:
    print(
        "Could not reach the exchange (DNS/network/firewall/VPN). "
        "Try: fix DNS, disable blocking VPN, or run without network:\n"
        "  crypto-fetch-bars --offline --hours 1 --head 5\n"
        "  crypto-fetch-bars --offline --features --json --pretty",
        file=sys.stderr,
    )


def _bars_payload(bars: list[Bar]) -> list[dict]:
    return [
        {
            "open_time": b.open_time.isoformat(),
            "open": b.open,
            "high": b.high,
            "low": b.low,
            "close": b.close,
            "volume": b.volume,
        }
        for b in bars
    ]


def _write_bars_csv(bars: list[Bar], path: Path) -> None:
    path = path.expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["open_time", "open", "high", "low", "close", "volume"])
        for b in bars:
            w.writerow(
                [
                    b.open_time.isoformat(),
                    b.open,
                    b.high,
                    b.low,
                    b.close,
                    b.volume,
                ]
            )


def _maybe_persist_bars(ns: argparse.Namespace, bars: list[Bar], symbol: Symbol) -> int:
    """Write optional CSV / SQLite / Parquet outputs. Returns 0 or 2 (save failure)."""
    if not bars:
        return 0
    csv_path = getattr(ns, "save_csv", None)
    sqlite_path = getattr(ns, "save_sqlite", None)
    parquet_path = getattr(ns, "save_parquet", None)
    sqlite_table = getattr(ns, "save_sqlite_table", "ohlcv")
    if csv_path is None and sqlite_path is None and parquet_path is None:
        return 0
    try:
        if csv_path is not None:
            _write_bars_csv(bars, Path(csv_path))
        if sqlite_path is not None:
            append_bars_sqlite(bars, Path(sqlite_path), table=str(sqlite_table))
        if parquet_path is not None:
            save_bars_parquet(bars, Path(parquet_path))
    except ImportError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    except (OSError, ValueError) as e:
        print(f"error: failed to save bars: {e}", file=sys.stderr)
        return 2
    return 0


def _feature_payload(table: FeatureTable) -> dict:
    return {
        "schema_version": table.schema_version,
        "columns": list(table.columns),
        "rows": [
            {k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in row.items()}
            for row in table.rows
        ],
    }


async def _run_offline(args: argparse.Namespace, settings: Settings) -> int:
    symbol_raw = args.symbol or settings.default_symbol
    symbol = Symbol(normalize_user_symbol(symbol_raw))
    provider = StubMarketDataProvider()
    try:
        end = datetime.now(timezone.utc)
        start = end - timedelta(hours=float(args.hours))
        if args.start is not None:
            start = _parse_iso_utc(args.start)
        if args.end is not None:
            end = _parse_iso_utc(args.end)

        bars = await provider.fetch_historical(symbol, start, end)
        save_rc = _maybe_persist_bars(args, list(bars), symbol)
        if save_rc != 0:
            return save_rc
        table = compute_feature_table(bars, FeatureConfig()) if args.features else None

        if args.json:
            if args.features and table is not None:
                payload = {
                    "mode": "offline",
                    "bars": _bars_payload(bars),
                    "features": _feature_payload(table),
                }
                json.dump(payload, sys.stdout, indent=2 if args.pretty else None)
            else:
                json.dump(
                    {"mode": "offline", "bars": _bars_payload(bars)},
                    sys.stdout,
                    indent=2 if args.pretty else None,
                )
            sys.stdout.write("\n")
        else:
            print(f"mode=offline symbol={symbol} bars={len(bars)}")
            for b in bars[: args.head]:
                print(
                    f"{b.open_time.isoformat()} O={b.open:.4f} H={b.high:.4f} "
                    f"L={b.low:.4f} C={b.close:.4f} V={b.volume:.4f}"
                )
            if len(bars) > args.head:
                print(f"... ({len(bars) - args.head} more)")
            if table is not None:
                print(f"features schema={table.schema_version} columns={table.columns}")
                for row in table.rows[-args.head:]:
                    print({k: row[k] for k in table.columns if k in row})
        return 0
    finally:
        await provider.close()


async def _run_ccxt(args: argparse.Namespace, settings: Settings) -> int:
    symbol_raw = args.symbol or settings.default_symbol
    try:
        provider = await create_ccxt_provider_from_settings(settings)
    except (ExchangeNotAvailable, OSError, aiohttp.ClientError) as e:
        print(f"error: {e}", file=sys.stderr)
        _print_network_help()
        return 3
    try:
        ex = provider.exchange
        symbol = resolve_market_symbol(ex, symbol_raw)
        validate_timeframe(ex, settings.ccxt_timeframe)

        end = datetime.now(timezone.utc)
        start = end - timedelta(hours=float(args.hours))
        if args.start is not None:
            start = _parse_iso_utc(args.start)
        if args.end is not None:
            end = _parse_iso_utc(args.end)

        try:
            bars = await provider.fetch_historical(symbol, start, end)
        except (ExchangeNotAvailable, OSError, aiohttp.ClientError) as e:
            print(f"error: {e}", file=sys.stderr)
            _print_network_help()
            return 3

        save_rc = _maybe_persist_bars(args, list(bars), symbol)
        if save_rc != 0:
            return save_rc

        table = compute_feature_table(bars, FeatureConfig()) if args.features else None

        if args.json:
            if args.features and table is not None:
                json.dump(
                    {
                        "mode": "ccxt",
                        "exchange": settings.ccxt_exchange,
                        "symbol": str(symbol),
                        "bars": _bars_payload(bars),
                        "features": _feature_payload(table),
                    },
                    sys.stdout,
                    indent=2 if args.pretty else None,
                )
            else:
                payload = {
                    "mode": "ccxt",
                    "exchange": settings.ccxt_exchange,
                    "symbol": str(symbol),
                    "bars": _bars_payload(bars),
                }
                json.dump(payload, sys.stdout, indent=2 if args.pretty else None)
            sys.stdout.write("\n")
        else:
            print(f"exchange={settings.ccxt_exchange} symbol={symbol} bars={len(bars)}")
            for b in bars[: args.head]:
                print(
                    f"{b.open_time.isoformat()} O={b.open:.4f} H={b.high:.4f} "
                    f"L={b.low:.4f} C={b.close:.4f} V={b.volume:.4f}"
                )
            if len(bars) > args.head:
                print(f"... ({len(bars) - args.head} more)")
            if table is not None:
                print(f"features schema={table.schema_version} columns={table.columns}")
                for row in table.rows[-args.head:]:
                    print({k: row[k] for k in table.columns if k in row})
        return 0
    finally:
        await provider.close()


async def _run(args: argparse.Namespace) -> int:
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO))
    settings = Settings()
    if args.offline:
        return await _run_offline(args, settings)
    return await _run_ccxt(args, settings)


def main() -> None:
    p = argparse.ArgumentParser(
        description=(
            "Fetch historical OHLCV via CCXT (public REST) or offline stub. "
            "Optional --save-csv / --save-sqlite / --save-parquet write bars for crypto-backtest."
        ),
    )
    p.add_argument("--offline", action="store_true", help="Use synthetic bars (no network / DNS)")
    p.add_argument("--features", action="store_true", help="Also compute Phase-2 feature table")
    p.add_argument("--symbol", default=None, help="Override CRYPTO_BOT_DEFAULT_SYMBOL")
    p.add_argument("--hours", default=6.0, type=float, help="Window length if start/end omitted")
    p.add_argument("--start", default=None, help="ISO start (UTC), e.g. 2024-06-01T00:00:00Z")
    p.add_argument("--end", default=None, help="ISO end (UTC), exclusive")
    p.add_argument("--json", action="store_true", help="Print JSON array of bars")
    p.add_argument("--pretty", action="store_true", help="Pretty-print JSON")
    p.add_argument("--head", default=5, type=int, help="Plain mode: show first N rows (features: last N)")
    p.add_argument("--log-level", default="WARNING", help="Logging level")
    p.add_argument(
        "--save-csv",
        type=Path,
        default=None,
        help="After fetch, write UTF-8 OHLCV CSV (header matches load_bars_csv)",
    )
    p.add_argument(
        "--save-sqlite",
        type=Path,
        default=None,
        help="After fetch, append rows into SQLite (same schema as load_bars_sqlite)",
    )
    p.add_argument(
        "--save-parquet",
        type=Path,
        default=None,
        help="After fetch, write Parquet file (requires pip install 'crypto-bot[parquet]')",
    )
    p.add_argument(
        "--save-sqlite-table",
        default="ohlcv",
        help="Table name for --save-sqlite (same rules as crypto-backtest --bars-sqlite-table)",
    )
    args = p.parse_args()
    try:
        raise SystemExit(asyncio.run(_run(args)))
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        raise SystemExit(2) from e


if __name__ == "__main__":
    main()
