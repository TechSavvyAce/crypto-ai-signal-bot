from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from crypto_bot.config import Settings
from crypto_bot.model.registry import add_entry, default_registry_file_path, list_entries, resolve_artifact_dir


def _registry_path(args: argparse.Namespace, settings: Settings) -> Path:
    if args.registry_file is not None:
        p = args.registry_file
        return p.expanduser().resolve() if p.is_absolute() else (Path.cwd() / p).resolve()
    return default_registry_file_path(settings)


def _cmd_add(args: argparse.Namespace, settings: Settings) -> int:
    rf = _registry_path(args, settings)
    entry = add_entry(rf, args.artifact_dir.resolve(), name=args.name, version=args.version)
    print(f"registered name={entry.name!r} version={entry.version!r} path={entry.path}")
    print(f"fingerprint={entry.fingerprint}")
    print(f"registry_file={rf}")
    return 0


def _cmd_list(args: argparse.Namespace, settings: Settings) -> int:
    rf = _registry_path(args, settings)
    rows = list_entries(rf)
    if args.json:
        payload = [e.to_json_dict() for e in rows]
        json.dump({"registry_file": str(rf), "entries": payload}, sys.stdout, indent=2, default=str)
        sys.stdout.write("\n")
        return 0
    print(f"registry_file={rf} entries={len(rows)}")
    for e in rows:
        print(f"  {e.name}@{e.version}  path={e.path}  fp={e.fingerprint[:16]}…  at={e.registered_at}")
    return 0


def _cmd_path(args: argparse.Namespace, settings: Settings) -> int:
    rf = _registry_path(args, settings)
    p = resolve_artifact_dir(rf, args.name, args.version)
    if args.json:
        json.dump({"path": str(p)}, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0
    print(p)
    return 0


def main() -> None:
    settings = Settings()
    p = argparse.ArgumentParser(description="Name/version index for trained artifact directories.")
    p.add_argument(
        "--registry-file",
        type=Path,
        default=None,
        help="JSON registry file (default: CRYPTO_BOT_MODEL_REGISTRY_FILE or ./model_registry.json)",
    )
    sub = p.add_subparsers(dest="command", required=True)

    p_add = sub.add_parser("add", help="Register an artifact directory under a name and version")
    p_add.add_argument("--artifact-dir", type=Path, required=True)
    p_add.add_argument("--name", required=True)
    p_add.add_argument("--version", required=True)

    p_list = sub.add_parser("list", help="List registered artifacts")
    p_list.add_argument("--json", action="store_true")

    p_path = sub.add_parser("path", help="Print resolved filesystem path for name[/version]")
    p_path.add_argument("--name", required=True)
    p_path.add_argument("--version", default="latest", help="Version label or 'latest'")
    p_path.add_argument("--json", action="store_true")

    args = p.parse_args()
    try:
        if args.command == "add":
            code = _cmd_add(args, settings)
        elif args.command == "list":
            code = _cmd_list(args, settings)
        elif args.command == "path":
            code = _cmd_path(args, settings)
        else:
            code = 2
    except (FileNotFoundError, ValueError, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        raise SystemExit(2) from e
    raise SystemExit(code)


if __name__ == "__main__":
    main()
