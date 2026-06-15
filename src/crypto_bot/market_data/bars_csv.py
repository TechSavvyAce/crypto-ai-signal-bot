from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path

from crypto_bot.market_data.types import Bar, Symbol


def _parse_open_time(value: str) -> datetime:
    s = value.strip()
    if not s:
        msg = "empty open_time"
        raise ValueError(msg)
    dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _norm_key(k: str) -> str:
    return k.strip().lower().replace(" ", "_")


def _finalize_sorted_bars(raw_rows: list[tuple[datetime, Bar]]) -> list[Bar]:
    """Sort by open time, reject duplicates, return bars only."""
    if not raw_rows:
        msg = "No data rows"
        raise ValueError(msg)
    raw_rows.sort(key=lambda x: x[0])
    seen: set[datetime] = set()
    out: list[Bar] = []
    for ts, bar in raw_rows:
        if ts in seen:
            msg = f"Duplicate open_time: {ts.isoformat()}"
            raise ValueError(msg)
        seen.add(ts)
        out.append(bar)
    return out


def _field(row: dict[str, str], *names: str) -> str:
    for n in names:
        for k, v in row.items():
            if _norm_key(k) == n:
                return v.strip() if isinstance(v, str) else str(v).strip()
    msg = f"Missing column matching one of {names!r} in row keys {list(row)!r}"
    raise KeyError(msg)


def load_bars_csv(path: Path, *, symbol: Symbol, max_rows: int | None = None) -> list[Bar]:
    """Load ascending OHLCV bars from a UTF-8 CSV.

    Header row required. Recognized columns (case-insensitive):

    - **open_time** (or **timestamp**, **time**) — ISO-8601 UTC, e.g. ``2024-01-15T12:00:00+00:00``
    - **open**, **high**, **low**, **close**, **volume** (or **vol**)

    Rows are sorted by ``open_time``; duplicate open times raise ``ValueError``.
    """
    path = path.expanduser().resolve()
    if not path.is_file():
        msg = f"CSV not found: {path}"
        raise FileNotFoundError(msg)

    raw_rows: list[tuple[datetime, Bar]] = []
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            msg = "CSV has no header row"
            raise ValueError(msg)
        keys = {_norm_key(k) for k in reader.fieldnames if k}
        base = {"open", "high", "low", "close"}
        if not base.issubset(keys):
            msg = f"CSV header must include open,high,low,close; got {reader.fieldnames!r}"
            raise ValueError(msg)
        if "volume" not in keys and "vol" not in keys:
            msg = f"CSV header must include volume or vol; got {reader.fieldnames!r}"
            raise ValueError(msg)
        time_ok = any(t in keys for t in ("open_time", "timestamp", "time"))
        if not time_ok:
            msg = f"CSV header must include open_time, timestamp, or time; got {reader.fieldnames!r}"
            raise ValueError(msg)

        for i, row in enumerate(reader):
            if max_rows is not None and i >= max_rows:
                break
            if not any((v or "").strip() for v in row.values()):
                continue
            try:
                ts_raw = _field(row, "open_time", "timestamp", "time")
                ts = _parse_open_time(ts_raw)
                o = float(_field(row, "open"))
                h = float(_field(row, "high"))
                lo = float(_field(row, "low"))
                c = float(_field(row, "close"))
                try:
                    vol_s = _field(row, "volume")
                except KeyError:
                    vol_s = _field(row, "vol")
                vol = float(vol_s)
            except (KeyError, ValueError, TypeError) as e:
                msg = f"Bad CSV row {i + 2}: {e}"  # +2: 1-based + header
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
