from __future__ import annotations

import json
from pathlib import Path

import pytest

from crypto_bot.config import Settings
from crypto_bot.model.registry import (
    REGISTRY_SCHEMA_VERSION,
    add_entry,
    default_registry_file_path,
    fingerprint_artifact_dir,
    list_entries,
    resolve_artifact_dir,
)


def test_fingerprint_stable(tmp_path: Path) -> None:
    pytest.importorskip("sklearn")
    from crypto_bot.model.artifacts import save_trend_artifact

    save_trend_artifact(
        tmp_path,
        object(),
        ("a",),
        {"horizon": 1},
    )
    fp1 = fingerprint_artifact_dir(tmp_path)
    fp2 = fingerprint_artifact_dir(tmp_path)
    assert fp1 == fp2
    assert len(fp1) == 64


def test_add_list_resolve_latest(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("sklearn")
    from crypto_bot.model.artifacts import save_trend_artifact

    reg = tmp_path / "reg.json"
    art1 = tmp_path / "run1"
    art2 = tmp_path / "run2"
    save_trend_artifact(art1, object(), ("x",), {"horizon": 1, "test_accuracy": 0.5})
    save_trend_artifact(art2, object(), ("y",), {"horizon": 2, "test_accuracy": 0.6})

    add_entry(reg, art1, name="demo", version="v1")
    add_entry(reg, art2, name="demo", version="v2")

    rows = list_entries(reg)
    assert len(rows) == 2
    assert {e.version for e in rows} == {"v1", "v2"}

    latest = resolve_artifact_dir(reg, "demo", "latest")
    assert latest.resolve() == art2.resolve()

    assert resolve_artifact_dir(reg, "demo", "v1").resolve() == art1.resolve()


def test_add_replaces_same_name_version(tmp_path: Path) -> None:
    pytest.importorskip("sklearn")
    from crypto_bot.model.artifacts import save_trend_artifact

    reg = tmp_path / "reg.json"
    art = tmp_path / "run"
    save_trend_artifact(art, object(), ("z",), {"horizon": 3})
    fp_before = fingerprint_artifact_dir(art)
    add_entry(reg, art, name="x", version="1")
    meta = json.loads((art / "meta.json").read_text(encoding="utf-8"))
    meta["horizon"] = 99
    (art / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    add_entry(reg, art, name="x", version="1")
    rows = list_entries(reg)
    assert len(rows) == 1
    assert rows[0].fingerprint != fp_before


def test_resolve_fingerprint_mismatch(tmp_path: Path) -> None:
    pytest.importorskip("sklearn")
    from crypto_bot.model.artifacts import save_trend_artifact

    reg = tmp_path / "reg.json"
    art = tmp_path / "run"
    save_trend_artifact(art, object(), ("z",), {"horizon": 1})
    add_entry(reg, art, name="demo", version="v1")
    meta = json.loads((art / "meta.json").read_text(encoding="utf-8"))
    meta["horizon"] = 2
    (art / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    with pytest.raises(ValueError, match="fingerprint mismatch"):
        resolve_artifact_dir(reg, "demo", "v1")


def test_default_registry_path_respects_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    s = Settings(model_registry_file="")
    assert default_registry_file_path(s) == (tmp_path / "model_registry.json").resolve()
    s2 = Settings(model_registry_file="custom.json")
    assert default_registry_file_path(s2) == (tmp_path / "custom.json").resolve()


def test_registry_schema_roundtrip(tmp_path: Path) -> None:
    pytest.importorskip("sklearn")
    from crypto_bot.model.artifacts import save_trend_artifact

    reg = tmp_path / "reg.json"
    art = tmp_path / "a"
    save_trend_artifact(art, object(), ("c",), {})
    add_entry(reg, art, name="n", version="v")
    data = json.loads(reg.read_text(encoding="utf-8"))
    assert data["schema_version"] == REGISTRY_SCHEMA_VERSION


def test_resolve_unknown_name_raises(tmp_path: Path) -> None:
    reg = tmp_path / "empty.json"
    reg.write_text('{"schema_version": 1, "entries": []}', encoding="utf-8")
    with pytest.raises(FileNotFoundError, match="No registry entries"):
        resolve_artifact_dir(reg, "missing", "latest")
