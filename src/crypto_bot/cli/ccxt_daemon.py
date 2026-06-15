from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

import aiohttp
from ccxt.base.errors import ExchangeNotAvailable

from crypto_bot.cli.artifact_resolve import resolve_daemon_artifact_dir
from crypto_bot.config import Settings
from crypto_bot.loop.ccxt_daemon import run_ccxt_daemon


def _network_help() -> None:
    print(
        "Could not reach the exchange (DNS/network/firewall/VPN). "
        "Try: fix DNS, use `crypto-stub-daemon` for offline, or:\n"
        "  crypto-fetch-bars --offline --hours 1 --head 5",
        file=sys.stderr,
    )


async def _async_main(
    args: argparse.Namespace,
    artifact_dir: Path,
    settings: Settings,
) -> int:
    try:
        await run_ccxt_daemon(
            artifact_dir=artifact_dir,
            settings=settings,
            symbol=args.symbol,
            max_steps=args.max_steps,
            window_minutes=args.window_minutes,
            sleep_s=args.sleep,
            equity=args.equity,
            quote_frac=args.quote_frac,
            execution_mode=args.execution,
            use_balance_cap=args.balance_cap,
        )
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    except (ExchangeNotAvailable, OSError, aiohttp.ClientError) as e:
        print(f"error: {e}", file=sys.stderr)
        _network_help()
        return 3
    return 0


def main() -> None:
    p = argparse.ArgumentParser(
        description=(
            "Poll live CCXT OHLCV (see CRYPTO_BOT_CCXT_* env): rolling window → features "
            "(from artifact meta) → trend model → risk → execution "
            "(paper, ccxt-dry, or ccxt-live — see README 'Live trading')."
        ),
    )
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--artifact-dir", type=Path, default=None)
    src.add_argument("--registry-name", default=None)
    p.add_argument("--registry-version", default="latest")
    p.add_argument("--registry-file", type=Path, default=None)
    p.add_argument("--max-steps", type=int, default=5)
    p.add_argument(
        "--window-minutes",
        type=int,
        default=600,
        help="Wall-clock lookback; extended if the chart timeframe needs more bars for features",
    )
    p.add_argument("--sleep", type=float, default=60.0, help="Seconds between poll cycles")
    p.add_argument("--equity", type=float, default=10_000.0)
    p.add_argument("--symbol", default=None, help="Override CRYPTO_BOT_DEFAULT_SYMBOL")
    p.add_argument("--quote-frac", type=float, default=0.01)
    p.add_argument(
        "--execution",
        choices=("paper", "ccxt-dry", "ccxt-live"),
        default="paper",
        help=(
            "paper: simulated fills; ccxt-dry: CCXT client dry_run, still paper; "
            "ccxt-live: REAL spot market orders (needs API keys + CRYPTO_BOT_LIVE_TRADING_ACK=true)"
        ),
    )
    p.add_argument(
        "--balance-cap",
        action="store_true",
        help="Each cycle: fetch spot free balances via CCXT and cap notional in RiskEngine (needs API keys on most exchanges)",
    )
    args = p.parse_args()
    if args.execution == "ccxt-live":
        print(
            "*** crypto-ccxt-daemon: --execution ccxt-live may place REAL spot market orders. "
            "No profit guarantee; you can lose your stake. ***",
            file=sys.stderr,
        )
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
    sys.exit(asyncio.run(_async_main(args, adir, settings)))


if __name__ == "__main__":
    main()
