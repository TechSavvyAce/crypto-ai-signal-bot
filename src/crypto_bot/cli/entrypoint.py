from __future__ import annotations

import importlib
import sys
from typing import Final

"""Single entrypoint: ``crypto-bot <command>`` forwards to the same CLIs as ``crypto-<command>``."""

_COMMANDS: Final[dict[str, str]] = {
    "backtest": "crypto_bot.cli.backtest",
    "ccxt-daemon": "crypto_bot.cli.ccxt_daemon",
    "fetch-bars": "crypto_bot.cli.fetch_bars",
    "model-registry": "crypto_bot.cli.model_registry",
    "paper-step": "crypto_bot.cli.paper_step",
    "stub-daemon": "crypto_bot.cli.stub_daemon",
    "train-baseline": "crypto_bot.cli.train_baseline",
}


def _usage() -> str:
    lines = [
        "usage: crypto-bot <command> [args ...]",
        "",
        "commands (same as crypto-<command> scripts):",
    ]
    for name in sorted(_COMMANDS):
        lines.append(f"  {name}")
    lines.append("")
    lines.append("Examples:")
    lines.append("  crypto-bot fetch-bars --offline --hours 1 --head 3")
    lines.append("  crypto-bot backtest --help")
    return "\n".join(lines)


def main() -> None:
    argv = sys.argv
    if len(argv) < 2:
        print(_usage(), file=sys.stderr)
        raise SystemExit(2)
    cmd = argv[1]
    if cmd in ("-h", "--help"):
        print(_usage())
        raise SystemExit(0)
    mod_name = _COMMANDS.get(cmd)
    if mod_name is None:
        print(f"crypto-bot: unknown command {cmd!r}\n", file=sys.stderr)
        print(_usage(), file=sys.stderr)
        raise SystemExit(2)
    legacy_prog = f"crypto-{cmd}"
    sys.argv = [legacy_prog] + argv[2:]
    importlib.import_module(mod_name).main()
