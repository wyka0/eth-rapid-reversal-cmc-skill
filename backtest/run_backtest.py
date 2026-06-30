"""Main entry point for the ETH rapid reversal backtest.

Outputs:
- trades.csv (legs) — one row per execution (open, add_1..5, reduce_tier_1..3, close)
- cycles.csv — one row per full trade cycle
- equity_curve.csv / .png
- report.md
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backtest.data_loader import (
    load_cmc_fear_greed,
    load_cmc_funding_rate,
    load_cmc_ohlcv,
    load_cmc_open_interest,
    load_cmc_social_mentions,
)
from backtest.engine import BacktestEngine
from backtest.metrics import compute_metrics


def _leg_rows(legs):
    return [
        {
            "cycle_id": l.cycle_id,
            "leg_type": l.leg_type,
            "entry_ts": l.entry_ts,
            "exit_ts": l.exit_ts,
            "side": l.side,
            "tier": l.tier,
            "leverage": l.leverage,
            "notional": round(l.notional, 2),
            "size": round(l.size, 6),
            "price": round(l.price, 4),
            "exit_price": round(l.exit_price, 4) if l.exit_price is not None else None,
            "exit_reason": l.exit_reason,
            "pnl_usd": round(l.pnl_usd, 4),
            "pnl_pct": round(l.pnl_pct, 4),
            "cum_size_after": round(l.cum_size_after, 6),
            "cum_avg_entry": round(l.cum_avg_entry, 4),
            "cum_notional_after": round(l.cum_notional_after, 2),
            "rsi_at_entry": round(l.rsi_at_entry, 2),
            "macd_hist_at_entry": round(l.macd_hist_at_entry, 4),
            "adx_at_entry": round(l.adx_at_entry, 2),
            "fg_at_entry": round(l.fg_at_entry, 1),
            "funding_at_entry": round(l.funding_at_entry, 4),
            "oi_delta_24h_pct": round(l.oi_delta_24h_at_entry, 2),
            "social_delta_24h_pct": round(l.social_delta_24h_at_entry, 2),
            "divergence": l.divergence_at_entry,
            "bars_since_open": l.bars_since_open,
            "bars_since_last_event": l.bars_since_last_event,
        }
        for l in legs
    ]


def _cycle_rows(cycles):
    return [
        {
            "cycle_id": c.cycle_id,
            "side": c.side,
            "entry_ts": c.entry_ts,
            "exit_ts": c.exit_ts,
            "avg_entry": round(c.avg_entry, 4),
            "exit_price": round(c.exit_price, 4) if c.exit_price else None,
            "original_size": round(c.original_size, 6),
            "max_size": round(c.max_size, 6),
            "leverage": c.leverage,
            "tier": c.tier,
            "exit_reason": c.exit_reason,
            "adds_count": c.adds_count,
            "bars_held": c.bars_held,
            "total_pnl": round(c.total_pnl, 4),
            "total_commission": round(c.total_commission, 4),
            "rsi_at_open": round(c.rsi_at_open, 2),
            "macd_hist_at_open": round(c.macd_hist_at_open, 4),
            "adx_at_open": round(c.adx_at_open, 2),
            "fg_at_open": round(c.fg_at_open, 1),
            "funding_at_open": round(c.funding_at_open, 4),
            "divergence_at_open": c.divergence_at_open,
        }
        for c in cycles
    ]


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--days", type=int, default=90)
    p.add_argument("--equity", type=float, default=10_000.0)
    p.add_argument("--source", choices=["cmc", "csv", "synthetic"], default="cmc")
    p.add_argument("--out", type=str, default=str(Path(__file__).resolve().parent / "results"))
    p.add_argument("--tweak", type=str, default=None, help="JSON string of param overrides")
    args = p.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.source == "synthetic":
        import os
        os.environ.pop("CMC_API_KEY", None)
        os.environ["CMC_FORCE_SYNTHETIC"] = "1"

    print(f"[1/4] Loading {args.days}d of 5m + 15m ETH data (source={args.source})...")
    if args.source == "csv":
        csv = Path("data") / f"eth_5m.csv"
        if csv.exists():
            df_5m = pd.read_csv(csv, parse_dates=["timestamp"])
            df_15m = pd.read_csv(Path("data") / f"eth_15m.csv", parse_dates=["timestamp"]) if (Path("data") / "eth_15m.csv").exists() else df_5m
        else:
            df_5m = df_15m = None
    else:
        df_5m = load_cmc_ohlcv(symbol="ETH", bar="5m", days=args.days)
        df_15m = load_cmc_ohlcv(symbol="ETH", bar="15m", days=args.days)
    print(f"       5m bars: {len(df_5m):,}  |  15m bars: {len(df_15m):,}")

    print(f"[2/4] Loading {args.days}d of F&G, funding, OI, social...")
    fg = load_cmc_fear_greed(days=args.days)
    funding = load_cmc_funding_rate("ETH", days=args.days)
    oi = load_cmc_open_interest("ETH", days=args.days)
    social = load_cmc_social_mentions("ETH", days=args.days)
    print(f"       F&G={len(fg)}  funding={len(funding)}  OI={len(oi)}  social={len(social)}")

    overrides = json.loads(args.tweak) if args.tweak else {}
    overrides.setdefault("starting_equity", args.equity)
    print(f"[3/4] Running backtest engine (equity=${args.equity:,.0f})...")
    engine = BacktestEngine(overrides)
    result = engine.run(df_5m, df_15m, fg, funding=funding, oi=oi, social=social)
    print(f"       Cycles: {len(result.cycles)}  |  Legs: {len(result.trades)}  |  Final: ${result.final_equity:,.2f}  |  MaxDD: {result.max_drawdown * 100:.2f}%  |  funding_skips: {result.funding_skips}")

    print("[4/4] Computing metrics, writing outputs...")
    metrics = compute_metrics(
        result.equity_curve, result.cycles, result.trades,
        exit_reason_distribution=result.exit_reason_distribution,
        adds_distribution=result.adds_distribution,
    )

    if result.trades:
        pd.DataFrame(_leg_rows(result.trades)).to_csv(out_dir / "trades.csv", index=False)
    if result.cycles:
        pd.DataFrame(_cycle_rows(result.cycles)).to_csv(out_dir / "cycles.csv", index=False)
    result.equity_curve.to_csv(out_dir / "equity_curve.csv", header=["equity"])
    print(f"       Saved {out_dir}/trades.csv  ({len(result.trades)} legs)")
    print(f"       Saved {out_dir}/cycles.csv  ({len(result.cycles)} cycles)")
    print(f"       Saved {out_dir}/equity_curve.csv")

    if len(result.equity_curve) > 0:
        fig, ax = plt.subplots(figsize=(12, 5))
        result.equity_curve.plot(ax=ax, color="#1f77b4", linewidth=1.2)
        ax.set_title(f"ETH Rapid Reversal — Equity Curve ({args.days}d, ${args.equity:,.0f} start)")
        ax.set_ylabel("Equity (USD)")
        ax.set_xlabel("Time")
        ax.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig(out_dir / "equity_curve.png", dpi=120)
        plt.close(fig)
        print(f"       Saved {out_dir}/equity_curve.png")

    report = f"""# Backtest Report — ETH Rapid Reversal (CMC Skill)

| Field | Value |
|---|---|
| Run (UTC) | {datetime.now(timezone.utc).isoformat()} |
| Window | {args.days} days |
| Source | {args.source} |
| Starting equity | ${args.equity:,.2f} |
| Final equity | ${result.final_equity:,.2f} |
| Peak equity | ${result.peak_equity:,.2f} |
| Max drawdown | {metrics.get('max_drawdown', 0) * 100:.2f}% |
| Max DD duration | {metrics.get('max_dd_duration_days', 0)} days |
| Daily-loss halts | {result.daily_loss_halts} |
| Funding skips (hostile) | {result.funding_skips} |
| Funding halves (crowded) | {result.funding_size_halves} |

## Headline Cycle Metrics

| Metric | Value |
|---|---|
| Total Return | {metrics.get('total_return', 0) * 100:.2f}% |
| Annualized Return | {metrics.get('annual_return', 0) * 100:.2f}% |
| Sharpe (daily, rf=0) | {metrics.get('sharpe', 0):.2f} |
| Sortino | {metrics.get('sortino', 0):.2f} |
| Calmar | {metrics.get('calmar', 0):.2f} |
| Cycles (full trades) | {metrics.get('n_cycles', 0)} |
| Legs (executions) | {metrics.get('n_legs', 0)} |
| Cycle Win Rate | {metrics.get('cycle_win_rate', 0) * 100:.1f}% |
| Cycle Profit Factor | {metrics.get('cycle_profit_factor', 0):.2f} |
| Avg Cycle Win | ${metrics.get('cycle_avg_win', 0):,.2f} |
| Avg Cycle Loss | ${metrics.get('cycle_avg_loss', 0):,.2f} |
| **Pay-off Ratio** | **{metrics.get('pay_off_ratio', 0):.2f}** |
| Avg Cycle Hold | {metrics.get('cycle_avg_hold_hours', 0):.1f} h |

## Exit-Reason Distribution

How many cycles closed via each exit path (trail_sl / sl / ranging_close / macd_rev / time_stop / end_of_data):

```json
{json.dumps(metrics.get('exit_reason_distribution', {}), indent=2)}
```

## Rolling-Compound Distribution

How many adds each cycle had (0 = no adds, 5 = maxed out):

```json
{json.dumps(metrics.get('adds_distribution', {}), indent=2)}
```

## Cycle Side Breakdown

```json
{json.dumps(metrics.get('cycle_side_breakdown', {}), indent=2)}
```

## Cycle Tier Breakdown (entry tier)

```json
{json.dumps(metrics.get('cycle_tier_breakdown', {}), indent=2)}
```

## Leg-Type Breakdown

```json
{json.dumps(metrics.get('leg_type_breakdown', {}), indent=2)}
```

## Exit Reasons (cycle counts)

```json
{json.dumps(metrics.get('exit_reason_distribution', {}), indent=2)}
```

## Divergence Distribution (signals evaluated)

```json
{json.dumps(result.divergence_distribution, indent=2)}
```

## See Also

- `trades.csv` — execution-level log (legs)
- `cycles.csv` — full trade cycles with PnL
- `equity_curve.csv` — bar-by-bar equity
- `equity_curve.png` — equity plot
"""
    (out_dir / "report.md").write_text(report)
    print(f"       Saved {out_dir}/report.md")
    print("\n=== Headline ===")
    print(f"Return: {metrics.get('total_return', 0) * 100:+.2f}%  |  MaxDD: {metrics.get('max_drawdown', 0) * 100:.2f}%  |  Sharpe: {metrics.get('sharpe', 0):.2f}  |  Cycles: {metrics.get('n_cycles', 0)}  |  Cycle Win%: {metrics.get('cycle_win_rate', 0) * 100:.1f}%  |  Pay-off: {metrics.get('pay_off_ratio', 0):.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
