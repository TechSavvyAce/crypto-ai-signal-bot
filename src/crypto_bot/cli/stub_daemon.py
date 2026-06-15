from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from crypto_bot.cli.artifact_resolve import resolve_daemon_artifact_dir
from crypto_bot.config import Settings
from crypto_bot.loop.stub_daemon import run_stub_daemon


def main() -> None:
    p = argparse.ArgumentParser(
        description=(
            "Poll stub OHLCV: rolling window → features (from artifact meta) → "
            "trend model → risk → paper execution."
        ),
    )
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument(
        "--artifact-dir",
        type=Path,
        default=None,
        help="Directory with classifier.joblib + meta.json (from crypto-train-baseline --save-dir)",
    )
    src.add_argument(
        "--registry-name",
        default=None,
        help="Use artifact path from crypto-model-registry (see --registry-file)",
    )
    p.add_argument(
        "--registry-version",
        default="latest",
        help="Version label when using --registry-name (default: latest)",
    )
    p.add_argument(
        "--registry-file",
        type=Path,
        default=None,
        help="Registry JSON (default: CRYPTO_BOT_MODEL_REGISTRY_FILE or ./model_registry.json)",
    )
    p.add_argument("--max-steps", type=int, default=5, help="Number of poll cycles then exit")
    p.add_argument(
        "--window-minutes",
        type=int,
        default=600,
        help="How far back to fetch 1m-equivalent stub bars each cycle",
    )
    p.add_argument("--sleep", type=float, default=2.0, help="Seconds to wait between cycles")
    p.add_argument("--equity", type=float, default=10_000.0, help="Starting equity (quote) for risk")
    p.add_argument("--symbol", default="BTC/USDT")
    p.add_argument(
        "--quote-frac",
        type=float,
        default=0.01,
        help="Desired notional per signal as fraction of equity",
    )
    p.add_argument(
        "--execution",
        choices=("paper", "ccxt-dry"),
        default="paper",
        help="paper: PaperExecutionEngine; ccxt-dry: CcxtExecutionEngine(dry_run) → same paper fills",
    )
    args = p.parse_args()
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

    asyncio.run(
        run_stub_daemon(
            artifact_dir=adir,
            max_steps=args.max_steps,
            window_minutes=args.window_minutes,
            sleep_s=args.sleep,
            equity=args.equity,
            symbol=args.symbol,
            quote_frac=args.quote_frac,
            settings=settings,
            execution_mode=args.execution,
        )
    )


if __name__ == "__main__":
    main()
