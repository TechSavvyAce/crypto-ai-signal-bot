from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REGISTRY_SCHEMA_VERSION = 1

_SUMMARY_KEYS = (
    "feature_schema_version",
    "label_schema_version",
    "horizon",
    "feature_vol_window",
    "mom_horizon",
    "rsi_period",
    "train_accuracy",
    "test_accuracy",
    "test_majority_baseline_accuracy",
    "model_beats_majority_baseline",
)


def fingerprint_artifact_dir(artifact_dir: Path) -> str:
    """SHA-256 over ``classifier.joblib`` + ``meta.json`` bytes (stable order)."""
    d = artifact_dir.resolve()
    meta_path = d / "meta.json"
    clf_path = d / "classifier.joblib"
    if not meta_path.is_file() or not clf_path.is_file():
        msg = f"Missing classifier.joblib or meta.json under {d}"
        raise FileNotFoundError(msg)
    h = hashlib.sha256()
    h.update(b"meta.json|")
    h.update(meta_path.read_bytes())
    h.update(b"|classifier.joblib|")
    h.update(clf_path.read_bytes())
    return h.hexdigest()


def _read_meta_dict(artifact_dir: Path) -> dict[str, Any]:
    meta_path = artifact_dir.resolve() / "meta.json"
    return json.loads(meta_path.read_text(encoding="utf-8"))


def _summary_from_meta(meta: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k in _SUMMARY_KEYS:
        if k in meta:
            out[k] = meta[k]
    return out


def _load_registry_raw(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"schema_version": REGISTRY_SCHEMA_VERSION, "entries": []}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        msg = "Registry file must contain a JSON object"
        raise ValueError(msg)
    entries = data.get("entries", [])
    if not isinstance(entries, list):
        msg = "Registry entries must be a list"
        raise ValueError(msg)
    return {"schema_version": int(data.get("schema_version", 1)), "entries": entries}


def _save_registry_raw(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, indent=2, default=str)
    path.write_text(payload + "\n", encoding="utf-8")


@dataclass(frozen=True)
class RegistryEntry:
    """One registered artifact directory (name + version + integrity)."""

    name: str
    version: str
    path: Path
    fingerprint: str
    registered_at: str
    summary: dict[str, Any]

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "path": str(self.path),
            "fingerprint": self.fingerprint,
            "registered_at": self.registered_at,
            "summary": self.summary,
        }

    @staticmethod
    def from_json_dict(row: dict[str, Any]) -> RegistryEntry:
        return RegistryEntry(
            name=str(row["name"]),
            version=str(row["version"]),
            path=Path(str(row["path"])),
            fingerprint=str(row["fingerprint"]),
            registered_at=str(row["registered_at"]),
            summary=dict(row.get("summary") or {}),
        )


def list_entries(registry_file: Path) -> list[RegistryEntry]:
    raw = _load_registry_raw(registry_file)
    out: list[RegistryEntry] = []
    for row in raw["entries"]:
        if isinstance(row, dict) and "name" in row and "version" in row:
            out.append(RegistryEntry.from_json_dict(row))
    return out


def add_entry(
    registry_file: Path,
    artifact_dir: Path,
    *,
    name: str,
    version: str,
) -> RegistryEntry:
    """Register *artifact_dir* under *name*/*version* (replaces same name+version)."""
    d = artifact_dir.resolve()
    fp = fingerprint_artifact_dir(d)
    meta = _read_meta_dict(d)
    summary = _summary_from_meta(meta)
    now = datetime.now(timezone.utc).isoformat()
    entry = RegistryEntry(
        name=name.strip(),
        version=version.strip(),
        path=d,
        fingerprint=fp,
        registered_at=now,
        summary=summary,
    )
    if not entry.name or not entry.version:
        msg = "name and version must be non-empty"
        raise ValueError(msg)

    data = _load_registry_raw(registry_file)
    entries: list[dict[str, Any]] = []
    for row in data["entries"]:
        if not isinstance(row, dict):
            continue
        if row.get("name") == entry.name and row.get("version") == entry.version:
            continue
        entries.append(row)
    entries.append(entry.to_json_dict())
    data["entries"] = entries
    data["schema_version"] = REGISTRY_SCHEMA_VERSION
    _save_registry_raw(registry_file, data)
    return entry


def resolve_artifact_dir(registry_file: Path, name: str, version: str = "latest") -> Path:
    """Resolve filesystem path to a registered artifact bundle.

    *version* ``latest`` picks the most recently registered entry for *name*.
    """
    entries = list_entries(registry_file)
    matching = [e for e in entries if e.name == name]
    if not matching:
        msg = f"No registry entries for name={name!r} in {registry_file}"
        raise FileNotFoundError(msg)
    if version == "latest":
        chosen = max(matching, key=lambda e: e.registered_at)
    else:
        chosen = next((e for e in matching if e.version == version), None)
        if chosen is None:
            msg = f"No registry entry for name={name!r} version={version!r} in {registry_file}"
            raise FileNotFoundError(msg)
    p = chosen.path.resolve()
    if not (p / "classifier.joblib").is_file() or not (p / "meta.json").is_file():
        msg = f"Registered path missing artifact files: {p}"
        raise FileNotFoundError(msg)
    current_fp = fingerprint_artifact_dir(p)
    if current_fp != chosen.fingerprint:
        msg = (
            f"Artifact fingerprint mismatch for {name}@{chosen.version}: "
            f"registry has {chosen.fingerprint[:12]}…, disk has {current_fp[:12]}…"
        )
        raise ValueError(msg)
    return p


def default_registry_file_path(settings: Any) -> Path:
    """Default JSON registry path: env ``model_registry_file`` or ``./model_registry.json``."""
    raw = str(getattr(settings, "model_registry_file", "") or "").strip()
    if raw:
        p = Path(raw)
        return p.expanduser().resolve() if p.is_absolute() else (Path.cwd() / p).resolve()
    return (Path.cwd() / "model_registry.json").resolve()
