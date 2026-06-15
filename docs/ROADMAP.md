# Crypto AI Signal + Execution Bot — Roadmap

Phases build in pipeline order: each phase produces something runnable or testable before the next depends on it.

## Phase 0 — Foundations (this repo)

- [x] Roadmap + architecture docs
- [x] Python package layout + dependency pin file (`pyproject.toml`, `src/crypto_bot/`)
- [x] Config loading via env (`Settings` in `config.py`)
- [x] Stub market data provider + tests (proves the `MarketDataProvider` contract)
- [x] **CCXT** async provider: historical OHLCV + polled stream of closed bars
- [x] Normalization helpers + `crypto-fetch-bars` CLI entrypoint

## Phase 1 — Market data

- [x] Provider interface + CCXT historical + stream (polling)
- [x] Normalization: symbol mapping (`resolve_market_symbol`), UTC helpers, bar alignment (`floor` / `align_range`)
- [x] Persistence optional (partial): Parquet + SQLite OHLCV (`load_bars_parquet`, `save_bars_parquet`, `load_bars_sqlite`, `append_bars_sqlite`) + `crypto-backtest --bars-parquet` / `--bars-sqlite`; [ ] larger catalog / streaming ingest
- [ ] Health: reconnect, rate limits, backoff (partial: rate limit via CCXT; stream exponential backoff on errors; **historical** page retries + backoff)

## Phase 2 — Feature engine

- [x] Feature store contract: `compute_feature_table(bars) -> FeatureTable` (ordered columns + schema version)
- [x] Baseline features: `ret_1`, `log_ret_1`, rolling vol of log returns, momentum, Wilder RSI
- [x] Version features with a schema (`FEATURE_SCHEMA_VERSION` + window-specific column names from `FeatureConfig`)

## Phase 3 — AI model

- [x] Labeling / targets: forward return, discrete trend class (`-1/0/1`), forward 1-bar log-vol window (`LabelConfig`, `compute_label_table`, schema `LABEL_SCHEMA_VERSION`)
- [x] Train/eval baseline: chronological split (`time_series_split`) + multinomial logistic trend (`train_trend_logreg`, `crypto-train-baseline` CLI on synthetic demo OHLCV)
- [x] Inference artifact: `save_trend_artifact` / `load_trend_artifact`, `TrendClassifierArtifact.predict_row` (CLI `--save-dir`)
- [x] Model registry (partial): JSON index `crypto-model-registry` + SHA-256 fingerprint on resolve; daemons `--registry-name`; [ ] batch/stream packaging beyond daemons

## Phase 4 — Risk engine

- [x] Position cap: `max_position_frac_equity` × equity, bounded by `max_leverage` × equity
- [x] Stop hint: symmetric `stop_loss_frac` from entry (long/short)
- [x] Daily max loss kill-switch + UTC session roll (`RiskSessionState`, `RiskEngine`)
- [x] Pre-trade: `min_order_notional_quote`; `reduce_only` bypasses kill for unwind-style intents

## Phase 5 — Execution engine

- [x] Order types: market + limit (v1 limit: instant marketability check at `mark_price`)
- [x] Paper trading: `PaperExecutionEngine` with fill ledger
- [x] Idempotency: stable `client_order_id` → same `OrderResult`, single fill
- [x] Sync CCXT wrapper: `CcxtExecutionEngine` (`dry_run=True` → paper; `dry_run=False` → market orders); guarded **`crypto-ccxt-daemon --execution ccxt-live`** (`CRYPTO_BOT_LIVE_TRADING_ACK` + API keys)
- [x] Spot balance clip: `fetch_spot_balance_free` + `RiskEngine.evaluate(..., spot_balance=…)`; daemon `--balance-cap`
- [ ] Live soak + fill/slippage realism; full reconciliation (positions, fees, transfers)

## Phase 6 — Operations

- [ ] Single entrypoint (CLI or daemon): modes `paper` | `live` | `backtest` (partial: **`crypto-bot`** umbrella; **`crypto-ccxt-daemon --execution ccxt-live`** for guarded real spot orders; backtest + CSV/Parquet/SQLite + **`--mark-to-market`**; [ ] unified `live` product polish)
- [ ] Metrics / alerts (optional: Telegram, email)
- [x] Secrets only via env (partial: `.env.example` + README; never commit `.env` or keys)

---

## Suggested order of execution (one-by-one)

1. **Market data** — without clean data, nothing downstream is trustworthy.  
2. **Features** — frozen schema before you train.  
3. **Model** — start with a simple baseline (e.g. logistic / small MLP) before complexity.  
4. **Risk** — enforce before any live order.  
5. **Execution** — last mile; paper first for a long soak.

When Phase 0–1 are done, we tick boxes here and move to Feature engine as the next vertical slice.
