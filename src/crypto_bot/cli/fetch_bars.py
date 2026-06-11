from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from datetime import datetime, timedelta, timezone

from crypto_bot.config import Settings
from crypto_bot.market_data import create_ccxt_provider_from_settings
from crypto_bot.market_data.normalize import (
    resolve_market_symbol,
    validate_timeframe,
)


def _parse_iso_utc(s: str) -> datetime:
    dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


async def _run(args: argparse.Namespace) -> int:
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO))
    settings = Settings()
    symbol_raw = args.symbol or settings.default_symbol
    hours = float(args.hours)

    provider = await create_ccxt_provider_from_settings(settings)
    try:
        ex = provider.exchange
        symbol = resolve_market_symbol(ex, symbol_raw)
        validate_timeframe(ex, settings.ccxt_timeframe)

        end = datetime.now(timezone.utc)
        start = end - timedelta(hours=hours)
        if args.start is not None:
            start = _parse_iso_utc(args.start)
        if args.end is not None:
            end = _parse_iso_utc(args.end)

        bars = await provider.fetch_historical(symbol, start, end)
        if args.json:
            payload = [
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
        return 0
    finally:
        await provider.close()


def main() -> None:
    p = argparse.ArgumentParser(description="Fetch historical OHLCV via CCXT (public REST).")
    p.add_argument("--symbol", default=None, help="Override CRYPTO_BOT_DEFAULT_SYMBOL")
    p.add_argument("--hours", default=6.0, type=float, help="Window length if start/end omitted")
    p.add_argument("--start", default=None, help="ISO start (UTC), e.g. 2024-06-01T00:00:00Z")
    p.add_argument("--end", default=None, help="ISO end (UTC), exclusive")
    p.add_argument("--json", action="store_true", help="Print JSON array of bars")
    p.add_argument("--pretty", action="store_true", help="Pretty-print JSON")
    p.add_argument("--head", default=5, type=int, help="Plain mode: show first N rows")
    p.add_argument("--log-level", default="WARNING", help="Logging level")
    args = p.parse_args()
    try:
        raise SystemExit(asyncio.run(_run(args)))
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        raise SystemExit(2) from e


if __name__ == "__main__":
    main()
