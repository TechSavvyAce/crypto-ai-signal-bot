from __future__ import annotations

from pathlib import Path

from crypto_bot.config import Settings
from crypto_bot.model.registry import default_registry_file_path, resolve_artifact_dir


def resolve_daemon_artifact_dir(
    *,
    artifact_dir: Path | None,
    registry_name: str | None,
    registry_version: str,
    registry_file: Path | None,
    settings: Settings,
) -> Path:
    """Resolve ``--artifact-dir`` or ``--registry-name`` (+ file) to an on-disk artifact directory."""
    if artifact_dir is not None:
        return artifact_dir.expanduser().resolve()
    if registry_name:
        rf = registry_file.expanduser().resolve() if registry_file else default_registry_file_path(settings)
        return resolve_artifact_dir(rf, registry_name.strip(), registry_version.strip() or "latest")
    msg = "Provide --artifact-dir or --registry-name"
    raise ValueError(msg)
