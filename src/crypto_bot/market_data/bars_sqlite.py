from __future__ import annotations

import re
import sqlite3
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

from crypto_bot.market_data.bars_csv import _finalize_sorted_bars, _parse_open_time
from crypto_bot.market_data.types import Bar, Symbol

_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _validate_table(name: str) -> str:
    if not _IDENT.fullmatch(name):
        msg = f"Invalid SQLite table name: {name!r} (use letters, digits, underscore; start with letter or _)"
        raise ValueError(msg)
    return name


def ensure_bars_sqlite_schema(conn: sqlite3.Connection, *, table: str) -> None:
    """Create OHLCV table if missing: PK (symbol, open_time), columns match :class:`Bar` (time as ISO text)."""
    t = _validate_table(table)
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {t} (
            symbol TEXT NOT NULL,
            open_time TEXT NOT NULL,
            open REAL NOT NULL,
            high REAL NOT NULL,
            low REAL NOT NULL,
            close REAL NOT NULL,
            volume REAL NOT NULL,
            PRIMARY KEY (symbol, open_time)
        )
        """
    )


def append_bars_sqlite(bars: Sequence[Bar], path: Path, *, table: str = "ohlcv") -> None:
    """Insert or replace rows (by symbol + open_time). Creates the DB file and table as needed."""
    path = path.expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    t = _validate_table(table)
    conn = sqlite3.connect(path)
    try:
        ensure_bars_sqlite_schema(conn, table=t)
        conn.executemany(
            f"""
            INSERT OR REPLACE INTO {t}
            (symbol, open_time, open, high, low, close, volume)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    str(b.symbol),
                    b.open_time.isoformat(),
                    b.open,
                    b.high,
                    b.low,
                    b.close,
                    b.volume,
                )
                for b in bars
            ],
        )
        conn.commit()
    finally:
        conn.close()


def load_bars_sqlite(
    path: Path,
    *,
    symbol: Symbol,
    table: str = "ohlcv",
    max_rows: int | None = None,
) -> list[Bar]:
    """Load bars for ``symbol`` ordered by ``open_time`` ascending (UTC ISO strings in DB).

    ``max_rows`` keeps the first N bars in time order (after sort), same spirit as CSV/Parquet loaders.
    """
    path = path.expanduser().resolve()
    if not path.is_file():
        msg = f"SQLite database not found: {path}"
        raise FileNotFoundError(msg)
    t = _validate_table(table)
    sym = str(symbol)
    conn = sqlite3.connect(path)
    try:
        try:
            if max_rows is not None:
                cur = conn.execute(
                    f"""
                    SELECT open_time, open, high, low, close, volume
                    FROM {t} WHERE symbol = ? ORDER BY open_time ASC LIMIT ?
                    """,
                    (sym, max_rows),
                )
            else:
                cur = conn.execute(
                    f"""
                    SELECT open_time, open, high, low, close, volume
                    FROM {t} WHERE symbol = ? ORDER BY open_time ASC
                    """,
                    (sym,),
                )
        except sqlite3.OperationalError as e:
            msg = f"SQLite read failed (table {t!r}): {e}"
            raise ValueError(msg) from e
        rows = cur.fetchall()
    finally:
        conn.close()

    raw_rows: list[tuple[datetime, Bar]] = []
    for i, (ts_raw, o, h, lo, c, vol) in enumerate(rows):
        try:
            ts = _parse_open_time(str(ts_raw))
            bar = Bar(
                symbol=symbol,
                open_time=ts,
                open=float(o),
                high=float(h),
                low=float(lo),
                close=float(c),
                volume=float(vol),
            )
        except (TypeError, ValueError) as e:
            msg = f"Bad SQLite row {i + 1}: {e}"
            raise ValueError(msg) from e
        raw_rows.append((ts, bar))

    return _finalize_sorted_bars(raw_rows)
