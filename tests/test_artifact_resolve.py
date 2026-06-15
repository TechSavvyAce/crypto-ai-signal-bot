from __future__ import annotations

from pathlib import Path

import pytest

from crypto_bot.cli.artifact_resolve import resolve_daemon_artifact_dir
from crypto_bot.config import Settings
from crypto_bot.model.registry import add_entry


def test_resolve_daemon_prefers_artifact_dir(tmp_path: Path) -> None:
    d = tmp_path / "art"
    d.mkdir()
    s = Settings()
    out = resolve_daemon_artifact_dir(
        artifact_dir=d,
        registry_name=None,
        registry_version="latest",
        registry_file=None,
        settings=s,
    )
    assert out == d.resolve()


def test_resolve_daemon_via_registry(tmp_path: Path) -> None:
    pytest.importorskip("sklearn")
    from crypto_bot.model.artifacts import save_trend_artifact

    reg = tmp_path / "r.json"
    art = tmp_path / "bundle"
    save_trend_artifact(art, object(), ("f",), {})
    add_entry(reg, art, name="n", version="v1")
    s = Settings()
    out = resolve_daemon_artifact_dir(
        artifact_dir=None,
        registry_name="n",
        registry_version="v1",
        registry_file=reg,
        settings=s,
    )
    assert out == art.resolve()


def test_resolve_daemon_requires_one_source() -> None:
    with pytest.raises(ValueError, match="Provide"):
        resolve_daemon_artifact_dir(
            artifact_dir=None,
            registry_name=None,
            registry_version="latest",
            registry_file=None,
            settings=Settings(),
        )
