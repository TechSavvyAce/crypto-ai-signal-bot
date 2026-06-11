# Crypto AI Signal + Execution Bot

Systematic pipeline: **market data → features → model → risk → execution**.

- Roadmap and checklists: [docs/ROADMAP.md](docs/ROADMAP.md)  
- Module boundaries and flow: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

## Setup

```bash
cd D:\task\demo\crypto_bot
python -m venv .venv
.\.venv\Scripts\activate
pip install -e ".[dev]"
```

## CCXT market data

Uses **async REST** (`ccxt.async_support`): historical OHLCV with pagination, and **polling** for new closed candles (no `ccxt.pro` WebSocket dependency).

```python
import asyncio
from datetime import datetime, timedelta, timezone

from crypto_bot.config import Settings
from crypto_bot.market_data import Symbol, create_ccxt_provider_from_settings

async def main() -> None:
    settings = Settings()
    md = await create_ccxt_provider_from_settings(settings)
    try:
        end = datetime.now(timezone.utc)
        start = end - timedelta(hours=6)
        bars = await md.fetch_historical(Symbol(settings.default_symbol), start, end)
        print(len(bars), "bars")
    finally:
        await md.close()

asyncio.run(main())
```

Environment variables (see [.env.example](.env.example)): `CRYPTO_BOT_CCXT_EXCHANGE`, `CRYPTO_BOT_CCXT_TIMEFRAME`, `CRYPTO_BOT_CCXT_POLL_INTERVAL`, optional API key/secret.

## Normalization helpers

`crypto_bot.market_data.normalize` provides UTC checks, `BASE-QUOTE` → `BASE/QUOTE`, symbol validation against `exchange.markets`, timeframe validation, and bar-grid floor/ceil for windows.

## CLI smoke test

After `pip install -e ".[dev]"` the `crypto-fetch-bars` script is on your PATH (inside the venv):

```bash
crypto-fetch-bars --hours 1 --symbol BTC-USDT --head 3
crypto-fetch-bars --start 2024-06-01T00:00:00Z --end 2024-06-01T02:00:00Z --json --pretty
```

## Current status

Phase 1: CCXT provider, **symbol/timeframe normalization**, and **`crypto-fetch-bars`** CLI. Next: optional Parquet cache, streaming hardening, or start **Phase 2 feature engine**.
