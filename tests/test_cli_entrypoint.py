from __future__ import annotations

import sys
import types

import pytest


def test_crypto_bot_unknown_command(capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    from crypto_bot.cli import entrypoint as ep

    monkeypatch.setattr(sys, "argv", ["crypto-bot", "nope"])
    with pytest.raises(SystemExit) as ei:
        ep.main()
    assert ei.value.code == 2
    err = capsys.readouterr().err
    assert "unknown command" in err
    assert "fetch-bars" in err


def test_crypto_bot_help(capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    from crypto_bot.cli import entrypoint as ep

    monkeypatch.setattr(sys, "argv", ["crypto-bot", "--help"])
    with pytest.raises(SystemExit) as ei:
        ep.main()
    assert ei.value.code == 0
    out = capsys.readouterr().out
    assert "fetch-bars" in out


def test_crypto_bot_dispatches_argv(monkeypatch: pytest.MonkeyPatch) -> None:
    from crypto_bot.cli import entrypoint as ep

    seen: list[list[str]] = []

    def fake_main() -> None:
        seen.append(list(sys.argv))

    fake_mod = types.ModuleType("crypto_bot.cli.fetch_bars")
    fake_mod.main = fake_main
    monkeypatch.setitem(sys.modules, "crypto_bot.cli.fetch_bars", fake_mod)
    monkeypatch.setattr(sys, "argv", ["crypto-bot", "fetch-bars", "--offline", "--head", "1"])
    ep.main()
    assert seen == [["crypto-fetch-bars", "--offline", "--head", "1"]]
