from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from crypto_bot.market_data.bars_csv import _finalize_sorted_bars, _parse_open_time
from crypto_bot.market_data.types import Bar, Symbol


def _require_pyarrow():
    try:
        import pyarrow as pa
        import pyarrow.compute as pc
        import pyarrow.parquet as pq
    except ImportError as e:
        msg = "Parquet support requires pyarrow; pip install 'crypto-bot[parquet]'"
        raise ImportError(msg) from e
    return pa, pc, pq


def _phys_name(table: Any, *logical_names: str) -> str:
    cmap = {n.strip().lower().replace(" ", "_"): n for n in table.column_names}
    for cand in logical_names:
        key = cand.strip().lower().replace(" ", "_")
        if key in cmap:
            return cmap[key]
    msg = f"Missing column matching one of {logical_names!r}; got {table.column_names!r}"
    raise ValueError(msg)


def _time_column_to_utc_list(col, pa, pc) -> list[datetime]:
    col = col.combine_chunks()
    t = col.type
    if pa.types.is_timestamp(t):
        # Strip Arrow tz before to_pylist(): aware TimestampScalar.as_py() uses
        # zoneinfo and fails on Windows without the optional ``tzdata`` package.
        if getattr(t, "tz", None) is not None:
            col = pc.cast(col, pa.timestamp(t.unit))
        out: list[datetime] = []
        for x in col.to_pylist():
            if x is None:
                msg = "null open_time in Parquet row"
                raise ValueError(msg)
            if x.tzinfo is None:
                x = x.replace(tzinfo=timezone.utc)
            else:
                x = x.astimezone(timezone.utc)
            out.append(x)
        return out
    if pa.types.is_string(t) or pa.types.is_large_string(t):
        return [_parse_open_time(str(x)) for x in col.to_pylist()]
    msg = f"Unsupported time column type {t!r}; use timestamp (UTC) or ISO string"
    raise TypeError(msg)


def load_bars_parquet(path: Path, *, symbol: Symbol, max_rows: int | None = None) -> list[Bar]:
    """Load OHLCV bars from a Parquet file (same logical columns as :func:`load_bars_csv`).

    Requires **pyarrow** (``pip install 'crypto-bot[parquet]'``). Column names are
    case-insensitive: **open_time** (or **timestamp**, **time**), **open**, **high**,
    **low**, **close**, **volume** (or **vol**). Time column should be UTC timestamps or
    ISO-8601 strings. Rows are sorted by open time; duplicates raise ``ValueError``.
    """
    pa, pc, pq = _require_pyarrow()

    path = path.expanduser().resolve()
    if not path.is_file():
        msg = f"Parquet not found: {path}"
        raise FileNotFoundError(msg)

    table = pq.read_table(path)
    if max_rows is not None:
        table = table.slice(0, max_rows)

    tname = _phys_name(table, "open_time", "timestamp", "time")
    oname = _phys_name(table, "open")
    hname = _phys_name(table, "high")
    lname = _phys_name(table, "low")
    cname = _phys_name(table, "close")
    try:
        vname = _phys_name(table, "volume")
    except ValueError:
        vname = _phys_name(table, "vol")

    times = _time_column_to_utc_list(table.column(tname), pa, pc)
    opens = table.column(oname).combine_chunks().to_pylist()
    highs = table.column(hname).combine_chunks().to_pylist()
    lows = table.column(lname).combine_chunks().to_pylist()
    closes = table.column(cname).combine_chunks().to_pylist()
    vols = table.column(vname).combine_chunks().to_pylist()

    n = len(times)
    if not (n == len(opens) == len(highs) == len(lows) == len(closes) == len(vols)):
        msg = "Parquet columns have different lengths"
        raise ValueError(msg)

    raw_rows: list[tuple[datetime, Bar]] = []
    for i in range(n):
        try:
            ts = times[i]
            o = float(opens[i])
            h = float(highs[i])
            lo = float(lows[i])
            c = float(closes[i])
            vol = float(vols[i])
        except (TypeError, ValueError) as e:
            msg = f"Bad Parquet row {i + 1}: {e}"
            raise ValueError(msg) from e
        raw_rows.append(
            (
                ts,
                Bar(
                    symbol=symbol,
                    open_time=ts,
                    open=o,
                    high=h,
                    low=lo,
                    close=c,
                    volume=vol,
                ),
            )
        )

    return _finalize_sorted_bars(raw_rows)


def save_bars_parquet(bars: Sequence[Bar], path: Path) -> None:
    """Write bars to a single Parquet file (columns: open_time, open, high, low, close, volume)."""
    pa, _, pq = _require_pyarrow()

    path = path.expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    times = pa.array([b.open_time for b in bars], type=pa.timestamp("us", tz="UTC"))
    table = pa.table(
        {
            "open_time": times,
            "open": pa.array([b.open for b in bars], type=pa.float64()),
            "high": pa.array([b.high for b in bars], type=pa.float64()),
            "low": pa.array([b.low for b in bars], type=pa.float64()),
            "close": pa.array([b.close for b in bars], type=pa.float64()),
            "volume": pa.array([b.volume for b in bars], type=pa.float64()),
        }
    )
    pq.write_table(table, path)
