from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from crypto_bot.market_data.bars_sqlite import append_bars_sqlite, load_bars_sqlite
from crypto_bot.market_data.types import Bar, Symbol


def _bar(sym: Symbol, i: int) -> Bar:
    base = datetime(2024, 1, 1, tzinfo=timezone.utc) + timedelta(minutes=i)
    c = 100.0 + i * 0.01
    return Bar(symbol=sym, open_time=base, open=c, high=c + 0.1, low=c - 0.1, close=c, volume=1.0)


def test_append_load_bars_sqlite_roundtrip(tmp_path: Path) -> None:
    sym = Symbol("BTC/USDT")
    bars = [_bar(sym, i) for i in range(30)]
    db = tmp_path / "m.db"
    append_bars_sqlite(bars, db)
    loaded = load_bars_sqlite(db, symbol=sym)
    assert loaded == bars


def test_load_bars_sqlite_max_rows(tmp_path: Path) -> None:
    sym = Symbol("BTC/USDT")
    bars = [_bar(sym, i) for i in range(25)]
    db = tmp_path / "m.db"
    append_bars_sqlite(bars, db)
    loaded = load_bars_sqlite(db, symbol=sym, max_rows=7)
    assert len(loaded) == 7
    assert loaded[0].open_time == bars[0].open_time


def test_append_bars_sqlite_invalid_table_raises(tmp_path: Path) -> None:
    sym = Symbol("BTC/USDT")
    with pytest.raises(ValueError, match="Invalid SQLite table name"):
        append_bars_sqlite([_bar(sym, 0)], tmp_path / "x.db", table="bad;table")


def test_load_bars_sqlite_missing_table_raises(tmp_path: Path) -> None:
    import sqlite3

    db = tmp_path / "empty.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE other (x INT)")
    conn.commit()
    conn.close()
    with pytest.raises(ValueError, match="SQLite read failed"):
        load_bars_sqlite(db, symbol=Symbol("BTC/USDT"), table="ohlcv")


def test_append_or_replace_same_key(tmp_path: Path) -> None:
    sym = Symbol("BTC/USDT")
    db = tmp_path / "m.db"
    b1 = _bar(sym, 0)
    b2 = Bar(
        symbol=sym,
        open_time=b1.open_time,
        open=1.0,
        high=2.0,
        low=0.5,
        close=1.5,
        volume=9.0,
    )
    append_bars_sqlite([b1], db)
    append_bars_sqlite([b2], db)
    loaded = load_bars_sqlite(db, symbol=sym)
    assert len(loaded) == 1
    assert loaded[0].close == 1.5
    assert loaded[0].volume == 9.0
