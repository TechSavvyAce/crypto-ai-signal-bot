from __future__ import annotations

from pathlib import Path

import pytest

from crypto_bot.market_data.bars_csv import load_bars_csv
from crypto_bot.market_data.types import Symbol


def test_load_bars_csv_roundtrip_and_sort(tmp_path: Path) -> None:
    p = tmp_path / "b.csv"
    p.write_text(
        "open_time,open,high,low,close,volume\n"
        "2024-06-02T00:00:00+00:00,2,2.1,1.9,2.0,10\n"
        "2024-06-01T00:00:00+00:00,1,1.1,0.9,1.0,5\n",
        encoding="utf-8",
    )
    sym = Symbol("BTC/USDT")
    bars = load_bars_csv(p, symbol=sym)
    assert len(bars) == 2
    assert bars[0].open_time.isoformat().startswith("2024-06-01")
    assert bars[1].close == pytest.approx(2.0)
    assert bars[0].symbol == sym


def test_load_bars_csv_timestamp_and_vol_aliases(tmp_path: Path) -> None:
    p = tmp_path / "b.csv"
    p.write_text(
        "timestamp,open,high,low,close,vol\n"
        "2024-01-01T12:00:00Z,10,11,9,10.5,1\n",
        encoding="utf-8",
    )
    bars = load_bars_csv(p, symbol=Symbol("ETH/USDT"))
    assert len(bars) == 1
    assert bars[0].volume == pytest.approx(1.0)


def test_load_bars_csv_duplicate_time_raises(tmp_path: Path) -> None:
    p = tmp_path / "b.csv"
    p.write_text(
        "open_time,open,high,low,close,volume\n"
        "2024-01-01T00:00:00+00:00,1,1,1,1,1\n"
        "2024-01-01T00:00:00+00:00,2,2,2,2,2\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="Duplicate open_time"):
        load_bars_csv(p, symbol=Symbol("BTC/USDT"))


def test_load_bars_csv_max_rows(tmp_path: Path) -> None:
    p = tmp_path / "b.csv"
    p.write_text(
        "open_time,open,high,low,close,volume\n"
        "2024-01-01T00:00:00+00:00,1,1,1,1,1\n"
        "2024-01-02T00:00:00+00:00,2,2,2,2,2\n"
        "2024-01-03T00:00:00+00:00,3,3,3,3,3\n",
        encoding="utf-8",
    )
    bars = load_bars_csv(p, symbol=Symbol("BTC/USDT"), max_rows=1)
    assert len(bars) == 1
