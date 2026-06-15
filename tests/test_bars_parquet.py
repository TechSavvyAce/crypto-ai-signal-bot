from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from crypto_bot.market_data.types import Bar, Symbol

pytest.importorskip("pyarrow")

from crypto_bot.market_data.bars_parquet import load_bars_parquet, save_bars_parquet


def _bar_at(sym: Symbol, i: int) -> Bar:
    base = datetime(2024, 1, 1, tzinfo=timezone.utc) + timedelta(minutes=i)
    c = 100.0 + i * 0.01
    return Bar(symbol=sym, open_time=base, open=c, high=c + 0.1, low=c - 0.1, close=c, volume=1.0)


def test_save_load_bars_parquet_roundtrip(tmp_path: Path) -> None:
    sym = Symbol("BTC/USDT")
    bars = [_bar_at(sym, i) for i in range(50)]
    path = tmp_path / "b.parquet"
    save_bars_parquet(bars, path)
    loaded = load_bars_parquet(path, symbol=sym)
    assert loaded == bars


def test_load_bars_parquet_sorts_by_time(tmp_path: Path) -> None:
    sym = Symbol("BTC/USDT")
    bars = [_bar_at(sym, i) for i in [5, 1, 3, 0, 4, 2]]
    path = tmp_path / "unsorted.parquet"
    save_bars_parquet(bars, path)
    loaded = load_bars_parquet(path, symbol=sym)
    assert [b.open_time for b in loaded] == sorted(b.open_time for b in bars)


def test_load_bars_parquet_max_rows(tmp_path: Path) -> None:
    sym = Symbol("BTC/USDT")
    bars = [_bar_at(sym, i) for i in range(20)]
    path = tmp_path / "m.parquet"
    save_bars_parquet(bars, path)
    loaded = load_bars_parquet(path, symbol=sym, max_rows=5)
    assert len(loaded) == 5


def test_load_bars_parquet_duplicate_time_raises(tmp_path: Path) -> None:
    import pyarrow as pa
    import pyarrow.parquet as pq

    sym = Symbol("BTC/USDT")
    t = datetime(2024, 1, 1, tzinfo=timezone.utc)
    table = pa.table(
        {
            "open_time": pa.array([t, t], type=pa.timestamp("us", tz="UTC")),
            "open": [1.0, 1.0],
            "high": [1.1, 1.1],
            "low": [0.9, 0.9],
            "close": [1.0, 1.0],
            "volume": [1.0, 1.0],
        }
    )
    path = tmp_path / "dup.parquet"
    pq.write_table(table, path)
    with pytest.raises(ValueError, match="Duplicate open_time"):
        load_bars_parquet(path, symbol=sym)
