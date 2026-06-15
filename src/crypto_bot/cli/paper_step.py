from __future__ import annotations

import argparse
import math
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from crypto_bot.execution import PaperExecutionEngine
from crypto_bot.model.artifacts import load_trend_artifact
from crypto_bot.pipeline import Orchestrator
from crypto_bot.risk import RiskEngine, RiskSessionState, RiskSettings, SpotBalanceFree


def main() -> None:
    p = argparse.ArgumentParser(
        description="One pipeline step: trend (model or override) → risk → paper market order.",
    )
    p.add_argument("--equity", type=float, default=10_000.0, help="Mark-to-market equity (quote)")
    p.add_argument("--price", type=float, default=50_000.0, help="Mark price for risk + fill")
    p.add_argument("--symbol", default="BTC/USDT")
    p.add_argument(
        "--trend",
        type=int,
        default=None,
        choices=[-1, 0, 1],
        help="If set, skip model and use this trend class",
    )
    p.add_argument(
        "--artifact-dir",
        default=None,
        help="Directory with classifier.joblib + meta.json (uses model when --trend omitted)",
    )
    p.add_argument("--quote-frac", type=float, default=0.01, help="Desired notional as fraction of equity")
    p.add_argument(
        "--spot-quote-free",
        type=float,
        default=None,
        help="If set (optionally with --spot-base-free), cap size using free spot balances",
    )
    p.add_argument("--spot-base-free", type=float, default=None, help="Free base balance for sell cap (see --spot-quote-free)")
    p.add_argument("--client-order-id", default=None, help="Idempotency key (default: random UUID)")
    args = p.parse_args()

    now = datetime.now(timezone.utc)
    risk = RiskEngine(RiskSettings(), RiskSessionState.start(args.equity, now))
    paper = PaperExecutionEngine()
    model = None
    if args.artifact_dir:
        model = load_trend_artifact(Path(args.artifact_dir))
    if model is None and args.trend is None:
        print("error: provide --trend and/or --artifact-dir", file=sys.stderr)
        raise SystemExit(2)

    orch = Orchestrator(
        risk=risk,
        execution=paper,
        symbol=args.symbol,
        model=model,
        quote_frac_per_signal=args.quote_frac,
    )
    row: dict = {}
    if model is not None:
        row = {c: 0.0 for c in model.feature_columns}
    cid = args.client_order_id or str(uuid.uuid4())
    spot_bal: SpotBalanceFree | None = None
    if args.spot_quote_free is not None or args.spot_base_free is not None:
        q = float(args.spot_quote_free) if args.spot_quote_free is not None else math.inf
        b = float(args.spot_base_free) if args.spot_base_free is not None else math.inf
        spot_bal = SpotBalanceFree(quote=q, base=b)
    out = orch.step(
        row if row else None,
        now=now,
        mark_equity=args.equity,
        mark_price=args.price,
        client_order_id=cid,
        trend_override=args.trend,
        spot_balance=spot_bal,
    )
    print(f"trend={out.trend} risk_allowed={out.risk.allowed} risk_reason={out.risk.reason}")
    if out.order:
        print(f"order_ok={out.order.ok} status={out.order.status} client_order_id={out.order.client_order_id}")
    else:
        print("order=None", f"note={out.note}")
    if paper.fills:
        f = paper.fills[-1]
        print(f"last_fill seq={f.sequence} side={f.side} qty={f.qty_base} px={f.fill_price}")


if __name__ == "__main__":
    main()
