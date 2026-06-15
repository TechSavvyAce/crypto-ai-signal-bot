# Crypto AI Signal + Execution Bot

Systematic pipeline: **market data → features → model → risk → execution**.

- Roadmap and checklists: [docs/ROADMAP.md](docs/ROADMAP.md)  
- Module boundaries and flow: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

## Setup

```powershell
cd D:\task\demo\crypto_bot
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev,model]"
```

(`model` pulls in **scikit-learn** for `crypto-train-baseline` and the sklearn unit test; you can use `pip install -e ".[dev]"` only if you skip those.) For **Parquet** bars (`load_bars_parquet`, `crypto-backtest --bars-parquet`), add **`parquet`**: `pip install -e ".[dev,model,parquet]"`. The **`crypto-bot`** script lists all subcommands (`crypto-bot --help`).

## How to run

There is no single “live trader” entrypoint yet; you can run **tests**, **CLIs**, or short **Python snippets**. Use **`crypto-bot <command>`** as an umbrella for the same tools as **`crypto-<command>`** (e.g. `crypto-bot fetch-bars` ≡ `crypto-fetch-bars`). Use **`crypto-stub-daemon`** for a loop on synthetic bars, **`crypto-ccxt-daemon`** for live OHLCV (paper by default; optional **guarded** real orders via **`--execution ccxt-live`**), **`crypto-backtest`** for a walk-forward replay on demo bars, and **`crypto-paper-step`** for one-shot checks.

### 1. Tests (no network)

```powershell
cd D:\task\demo\crypto_bot
.\.venv\Scripts\Activate.ps1
python -m pytest tests -q
```

### 2. CLI: fetch candles (uses the internet + CCXT)

Uses env from `.env` if present (see [.env.example](.env.example)); defaults are Binance + `BTC/USDT` + `1m`.

```powershell
.\.venv\Scripts\Activate.ps1
crypto-fetch-bars --hours 1 --symbol BTC-USDT --head 5
```

Help:

```powershell
crypto-fetch-bars --help
```

**Offline / no DNS:** synthetic candles + optional features (good when VPN/firewall/DNS blocks `api.binance.com`):

```powershell
crypto-fetch-bars --offline --hours 2 --symbol BTC-USDT --head 5
crypto-fetch-bars --offline --features --json --pretty
```

**DNS or “Could not contact DNS servers”:** fix Windows DNS / VPN / firewall, then retry live mode. If `load_markets` fails, the CLI now exits with code **3** and prints a short hint; CCXT exchanges are **closed** on failure so you should not see “Unclosed client session” from a failed startup anymore.

**Save to disk (offline or live):** after a successful fetch, write the same OHLCV shape **`crypto-backtest`** expects:

```powershell
crypto-fetch-bars --offline --hours 1 --save-csv ./data/demo.csv
crypto-fetch-bars --offline --hours 1 --save-sqlite ./data/demo.db
crypto-fetch-bars --offline --hours 1 --save-parquet ./data/demo.parquet
```

Combine paths as needed. Parquet needs **`pip install 'crypto-bot[parquet]'`**. SQLite uses table **`ohlcv`** (override with **`--save-sqlite-table`**). See [.env.example](.env.example) for **never committing API keys**.

### 3. CLI: baseline trend model (synthetic demo bars + scikit-learn)

If you skipped `.[model]` during setup:

```powershell
pip install -e ".[model]"
```

Then:

```powershell
crypto-train-baseline --n-bars 600
crypto-train-baseline --n-bars 600 --save-dir ./artifacts/demo_run
```

Uses **chronological** train/test split (no shuffling). Exits **4** if scikit-learn is missing. The CLI prints **class counts**, **majority baseline** accuracy on the test set (always predict the most common train class), and whether the model **beats** that baseline—use that to judge if ~0.6 accuracy is meaningful. On the built-in sine demo, ~0.55–0.65 test accuracy is typical and may only slightly edge the baseline; **real CCXT data** and proper validation are what matter for trading.

Reload a saved bundle in code: `load_trend_artifact(Path("./artifacts/demo_run"))` then `predict_row({...})` (see `crypto_bot.model`).

### 4. CLI: one paper pipeline step (trend → risk → fill)

```powershell
crypto-paper-step --trend 1 --equity 10000 --price 50000
crypto-paper-step --artifact-dir ./artifacts/demo_run --equity 10000 --price 50000
```

Use **`--trend -1|0|1`** for smoke tests without a model. With **`--artifact-dir`**, omit `--trend` to use `predict_row` on a zero feature vector (demo only—real use passes actual feature rows in Python). Optional **`--spot-quote-free`** / **`--spot-base-free`** (either may be omitted → no cap on that leg) forward **free spot balances** into **`RiskEngine`** for the same clipping logic as the CCXT daemon’s **`--balance-cap`**.

### 5. CLI: stub daemon (rolling window → features → model → paper)

Polls the **stub** market data provider on a timer, rebuilds features from the artifact’s `meta.json` windows, runs the same **`Orchestrator`** path as `crypto-paper-step`, and prints each cycle. Requires **`[model]`** so `classifier.joblib` can load. Pass **`--artifact-dir`** or **`--registry-name`** (optional **`--registry-version`**, **`--registry-file`**). Optional **`--execution ccxt-dry`** builds a sync CCXT client (`dry_run=True`, fills still via paper) and closes it when the loop exits—useful before wiring real orders.

```powershell
crypto-train-baseline --n-bars 600 --save-dir ./artifacts/demo_run
crypto-stub-daemon --artifact-dir ./artifacts/demo_run --max-steps 3 --sleep 1 --window-minutes 800
crypto-model-registry add --artifact-dir ./artifacts/demo_run --name demo --version v1
crypto-stub-daemon --registry-name demo --max-steps 3 --sleep 1 --window-minutes 800
```

### 6. CLI: CCXT daemon (live candles → features → model → execution)

Same pipeline as the stub daemon, but each cycle **fetches OHLCV** via **`CRYPTO_BOT_CCXT_*`** (exchange, timeframe, keys). Default **`--execution paper`** (simulated fills). **`--execution ccxt-dry`** uses a real sync CCXT client with **`dry_run=True`** (fills still simulated). **`--execution ccxt-live`** can send **real spot market orders** when risk approves — see **Live trading (real orders)** below (mandatory env acknowledgement + API keys). **`--balance-cap`** calls **`fetch_balance`** each cycle and passes free **base/quote** into risk sizing (usually needs **API keys**). If balance fetch fails, the step logs a warning and runs **without** a balance cap for that cycle. Exits **3** on DNS/network errors (same spirit as `crypto-fetch-bars`). Misconfiguration of live mode exits **2**. Default **`--sleep`** is 60s so you do not hammer public REST. Use **`--artifact-dir`** or **`--registry-name`** like the stub daemon.

```powershell
crypto-ccxt-daemon --artifact-dir ./artifacts/demo_run --max-steps 3 --sleep 30 --window-minutes 800
crypto-ccxt-daemon --registry-name demo --max-steps 3 --sleep 30 --window-minutes 800 --balance-cap
```

### Live trading (real orders)

This repo **does not guarantee profit**. Automated spot trading can **lose money** quickly (model error, bugs, fees, slippage, exchange issues).

**Minimum checklist before `--execution ccxt-live`:**

1. **Paper first** — run the same artifact with **`--execution paper`** (or **`ccxt-dry`**) for many cycles; confirm behavior and sizing.
2. **Exchange account** — use a **sub-account** or small balance; API key **without withdrawal** permission if your exchange supports it; IP allowlist.
3. **Environment** — set **`CRYPTO_BOT_CCXT_API_KEY`**, **`CRYPTO_BOT_CCXT_API_SECRET`**, and **`CRYPTO_BOT_LIVE_TRADING_ACK=true`** (the daemon refuses live mode without this explicit flag).
4. **Start tiny** — low **`--equity`** / **`--quote-frac`** in line with what you can afford to lose; consider **testnet** if your exchange exposes it via CCXT (not all do uniformly).
5. **Operational** — watch logs; **`--max-steps`** limits run length during experiments.

Example (after you accept the risk yourself):

```powershell
$env:CRYPTO_BOT_LIVE_TRADING_ACK="true"
crypto-ccxt-daemon --artifact-dir ./artifacts/demo_run --max-steps 2 --sleep 120 --execution ccxt-live --quote-frac 0.001 --balance-cap
```

### 7. CLI: walk-forward backtest (demo OHLCV, CSV, Parquet, or SQLite)

Bar-by-bar replay: each step uses **`bars[:i+1]`** (no lookahead), **`feature_row_for_model` → `Orchestrator` → paper**. Default bars match **`crypto-train-baseline`**’s sine demo. Use **at most one** of **`--bars-csv`**, **`--bars-parquet`**, or **`--bars-sqlite path.db`**. Parquet needs **`pip install 'crypto-bot[parquet]'`**. SQLite uses table **`ohlcv`** by default (**`--bars-sqlite-table`** to override): columns **`symbol`**, **`open_time`** (UTC ISO text), **`open`**, **`high`**, **`low`**, **`close`**, **`volume`**; primary key **`(symbol, open_time)`**. Populate with **`crypto-fetch-bars --save-sqlite`**, **`append_bars_sqlite`** in Python, or your own ETL. UTF-8 CSV header: **`open_time`**,**`open`**,**`high`**,**`low`**,**`close`**,**`volume`** — **`timestamp`** / **`time`** and **`vol`** aliases allowed. Optional **`--max-rows`**. By default **risk** uses fixed **`mark_equity`** = **`--equity`**. **`--mark-to-market`** uses **cash + position × close** (JSON/text adds **`final_*`** fields). Programmatic: **`load_bars_csv`** / **`load_bars_parquet`** / **`load_bars_sqlite`** + **`run_walk_forward_backtest(..., mark_to_market=...)`**.

```powershell
crypto-train-baseline --n-bars 800 --save-dir ./artifacts/demo_run
crypto-backtest --artifact-dir ./artifacts/demo_run --n-bars 800 --quote-frac 0.05 --json
crypto-backtest --artifact-dir ./artifacts/demo_run --n-bars 800 --quote-frac 0.05 --mark-to-market --json
crypto-backtest --artifact-dir ./artifacts/demo_run --bars-csv ./data/btc_1m.csv --max-rows 5000 --json
crypto-backtest --artifact-dir ./artifacts/demo_run --bars-parquet ./data/btc_1m.parquet --max-rows 5000 --json
crypto-backtest --artifact-dir ./artifacts/demo_run --bars-sqlite ./data/btc_1m.db --max-rows 5000 --json
```

### 8. Python REPL or a small script

With the venv activated, `import crypto_bot` works after `pip install -e ".[dev]"`. Use the snippets under **CCXT market data** and **Feature engine** below (paste into a `run.py` or `python -c "..."`).

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

## Feature engine (Phase 2)

Versioned tabular features from sorted OHLCV bars: `ret_1`, `log_ret_1`, rolling log-return volatility (`vol_roll_{N}`), momentum (`mom_{K}`), Wilder RSI (`rsi_{P}`). See `crypto_bot.features.compute_feature_table`.

```python
from crypto_bot.features import FeatureConfig, compute_feature_table

# bars: list[Bar] from CCXT or stub …
table = compute_feature_table(bars, FeatureConfig(vol_window=20, mom_horizon=10, rsi_period=14))
print(table.schema_version, table.columns, len(table.rows))
```

## Model (Phase 3)

Forward-looking labels (`compute_label_table`) + join with features (`join_features_labels`, `build_xy_trend`) + baseline logistic (`train_trend_logreg`). **Interpretation:** compare `test_accuracy` to `test_majority_baseline_accuracy`; if the model does not beat the majority baseline, the signal is weak for that split. **Artifacts:** `save_trend_artifact` / `load_trend_artifact` / `TrendClassifierArtifact.predict_row` in `crypto_bot.model` (written by `crypto-train-baseline --save-dir`).

**Registry (name + version):** `crypto-model-registry` keeps a JSON index of artifact directories with a **SHA-256 fingerprint** of `classifier.joblib` + `meta.json` (tamper detection on resolve). Default registry file: **`./model_registry.json`** or **`CRYPTO_BOT_MODEL_REGISTRY_FILE`**. Daemons accept **`--registry-name`** / **`--registry-version`** instead of **`--artifact-dir`**.

```powershell
crypto-model-registry add --artifact-dir ./artifacts/demo_run --name demo --version v1
crypto-model-registry list
crypto-model-registry path --name demo --version latest
```

## Risk engine (Phase 4)

`crypto_bot.risk`: **`RiskSettings`** (env `CRYPTO_BOT_RISK_*`), **`RiskSessionState`** (UTC day anchor), **`RiskEngine.evaluate(..., spot_balance=…)`** — caps notional vs equity + leverage; optional **`SpotBalanceFree`** (free base/quote) clips buys by **quote** and sells by **base×price** after a **`balance_clip_buffer_frac`** haircut; enforces min order size, attaches a **percent stop**, and trips a **daily loss kill-switch** (new risk blocked unless `reduce_only=True`).

## Execution (Phase 5)

`crypto_bot.execution`: **`OrderRequest`** / **`OrderResult`** / **`FillRecord`**, abstract **`ExecutionEngine`**, **`PaperExecutionEngine`**, sync **`CcxtExecutionEngine`** (`execution/ccxt_sync.py`) with **`dry_run=True`** (delegates to the same paper instance) or **`dry_run=False`** for real **`create_market_*_order`** calls (spot market only in v1; limit live orders are rejected). Helpers: **`create_ccxt_execution_sync`**, **`create_execution_engine(settings, "paper"|"ccxt-dry"|"ccxt-live")`** — **`ccxt-live`** requires API keys + **`CRYPTO_BOT_LIVE_TRADING_ACK=true`** (see README **Live trading**). Daemons: **`--execution paper`** (default), **`ccxt-dry`**, or **`ccxt-live`** (CCXT daemon only).

## Pipeline (Phase 6 slice)

`crypto_bot.pipeline`: **`Orchestrator`** — trend (`TrendClassifierArtifact` or `--trend` override) → **`TradeIntent`** → **`RiskEngine`** → **`ExecutionEngine`** (paper, **`ccxt-dry`**, or guarded **`ccxt-live`** on the CCXT daemon). CLIs: **`crypto-paper-step`**, **`crypto-stub-daemon`**, **`crypto-ccxt-daemon`**, **`crypto-backtest`**, **`crypto-model-registry`** (after `pip install -e .`).

Programmatic backtest: **`crypto_bot.market_data.load_bars_csv`**, **`crypto_bot.backtest.run_walk_forward_backtest`**.

## Current status

Phase 6 slice: **`Orchestrator`** + daemons + **`crypto-backtest`** + **`crypto-model-registry`** + sync **`CcxtExecutionEngine`**. **Live:** **`crypto-ccxt-daemon --execution ccxt-live`** (guarded; see README). Next: **metrics**, **reconciliation**, **streaming catalog**.
