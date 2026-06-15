from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from crypto_bot.cli.fetch_bars import _run
from crypto_bot.market_data.bars_csv import load_bars_csv
from crypto_bot.market_data.bars_sqlite import load_bars_sqlite
from crypto_bot.market_data.types import Symbol


def _ns_base(**kwargs: object) -> argparse.Namespace:
    defaults: dict[str, object] = {
        "offline": True,
        "features": False,
        "symbol": "BTC-USDT",
        "hours": 2.0,
        "start": None,
        "end": None,
        "json": False,
        "pretty": False,
        "head": 5,
        "log_level": "WARNING",
        "save_csv": None,
        "save_sqlite": None,
        "save_parquet": None,
        "save_sqlite_table": "ohlcv",
    }
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


@pytest.mark.asyncio
async def test_run_offline_smoke() -> None:
    ns = _ns_base(head=2)
    assert await _run(ns) == 0


@pytest.mark.asyncio
async def test_run_offline_with_features_json() -> None:
    ns = _ns_base(features=True, symbol="ETH/USDT", hours=3.0, json=True, head=3)
    assert await _run(ns) == 0


@pytest.mark.asyncio
async def test_run_offline_save_csv_and_sqlite(tmp_path: Path) -> None:
    sym = Symbol("BTC/USDT")
    csv_p = tmp_path / "o.csv"
    db_p = tmp_path / "b.db"
    ns = _ns_base(save_csv=csv_p, save_sqlite=db_p, head=1)
    assert await _run(ns) == 0
    assert csv_p.is_file()
    assert db_p.is_file()
    from_csv = load_bars_csv(csv_p, symbol=sym)
    from_sql = load_bars_sqlite(db_p, symbol=sym)
    assert from_csv == from_sql


@pytest.mark.asyncio
async def test_run_offline_save_parquet(tmp_path: Path) -> None:
    pytest.importorskip("pyarrow")
    sym = Symbol("BTC/USDT")
    pq_p = tmp_path / "o.parquet"
    ns = _ns_base(save_parquet=pq_p, head=1)
    assert await _run(ns) == 0
    from crypto_bot.market_data.bars_parquet import load_bars_parquet

    bars = load_bars_parquet(pq_p, symbol=sym)
    assert len(bars) > 0
    assert bars[0].symbol == sym
