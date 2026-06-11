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
- [ ] Persistence optional: SQLite/Parquet for backfill and replay
- [ ] Health: reconnect, rate limits, backoff (partial: rate limit via CCXT; stream has backoff on errors)

## Phase 2 — Feature engine

- [ ] Feature store contract: `bars_in → matrix/vector out`
- [ ] Baseline features: returns, rolling vol, RSI or simple momentum proxies
- [ ] Version features with a schema (column names + dtypes) for reproducibility

## Phase 3 — AI model

- [ ] Labeling / targets for trend, vol regime, momentum (define precisely)
- [ ] Train/eval pipeline (walk-forward or time-split; no shuffle leakage)
- [ ] Inference service: load model, batch or stream predictions
- [ ] Model registry: path + hash + training config snapshot

## Phase 4 — Risk engine

- [ ] Position sizing from vol / equity / max leverage
- [ ] Stop logic (hard stop, ATR-style, or time stop)
- [ ] Daily max loss + kill switch + “reduce only” mode
- [ ] Pre-trade checks: min notional, max exposure per symbol

## Phase 5 — Execution engine

- [ ] Order types you need (market/limit), idempotency keys
- [ ] Paper trading mode vs live keys
- [ ] Fill/slippage logging; reconciliation with exchange positions

## Phase 6 — Operations

- [ ] Single entrypoint (CLI or daemon): modes `paper` | `live` | `backtest`
- [ ] Metrics / alerts (optional: Telegram, email)
- [ ] Secrets only via env; never commit keys

---

## Suggested order of execution (one-by-one)

1. **Market data** — without clean data, nothing downstream is trustworthy.  
2. **Features** — frozen schema before you train.  
3. **Model** — start with a simple baseline (e.g. logistic / small MLP) before complexity.  
4. **Risk** — enforce before any live order.  
5. **Execution** — last mile; paper first for a long soak.

When Phase 0–1 are done, we tick boxes here and move to Feature engine as the next vertical slice.
