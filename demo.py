"""One-command demo for the ETH Rapid Reversal CMC Skill.

    python demo.py

Runs the full strategy pipeline on a deterministic synthetic ETH series (no
CMC_API_KEY needed), prints a presentation-ready summary, and writes the
standard artifacts to backtest/results/. This is the fastest way for a judge
to see the strategy work end-to-end.

For live CoinMarketCap Agent Hub data instead:
    $env:CMC_API_KEY = "your_key"        # Windows PowerShell
    export CMC_API_KEY=your_key           # macOS / Linux
    python demo.py --source cmc
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from backtest.agent_hub import field_map, load_all
from backtest.engine import BacktestEngine
from backtest.metrics import compute_metrics


def _ascii_equity(eq, width=48, height=10):
    vals = list(eq)
    if not vals:
        return "(no equity samples)"
    step = max(1, len(vals) // width)
    pts = vals[::step][:width]
    lo, hi = min(pts), max(pts)
    span = (hi - lo) or 1.0
    rows = []
    for r in range(height, 0, -1):
        thresh = lo + span * (r / height)
        line = "".join("#" if v >= thresh else " " for v in pts)
        rows.append(line)
    return "\n".join(rows)


def main() -> int:
    ap = argparse.ArgumentParser(description="ETH Rapid Reversal CMC Skill — demo")
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--equity", type=float, default=10_000.0)
    ap.add_argument("--source", choices=["cmc", "synthetic"], default="synthetic")
    args = ap.parse_args()

    if args.source == "synthetic":
        os.environ.pop("CMC_API_KEY", None)
        os.environ["CMC_FORCE_SYNTHETIC"] = "1"

    print("=" * 68)
    print("  ETH RAPID REVERSAL — CMC Skill (BNB Hack Track 2)")
    print("  Multi-indicator confluence + trailing stop + rolling compound")
    print("=" * 68)
    print("\n[1/3] CMC AI Agent Hub data layer:")
    print(field_map())
    print(f"\n[2/3] Loading {args.days}d ETH data (source={args.source})...")
    bundle = load_all("ETH", args.days)
    print(f"      5m bars: {len(bundle.df_5m):,} | 15m bars: {len(bundle.df_15m):,}")

    print(f"\n[3/3] Running walk-forward engine (equity=${args.equity:,.0f})...")
    eng = BacktestEngine({"starting_equity": args.equity})
    res = eng.run(bundle.df_5m, bundle.df_15m, bundle.fear_greed,
                  funding=bundle.funding, oi=bundle.open_interest, social=bundle.social)
    m = compute_metrics(res.equity_curve, res.cycles, res.trades,
                        exit_reason_distribution=res.exit_reason_distribution,
                        adds_distribution=res.adds_distribution)

    print("\n" + "-" * 68)
    print("  HEADLINE")
    print("-" * 68)
    print(f"  Cycles:           {m.get('n_cycles', 0)}")
    print(f"  Legs:             {m.get('n_legs', 0)}")
    print(f"  Total return:     {m.get('total_return', 0) * 100:+.2f}%")
    print(f"  Max drawdown:     {m.get('max_drawdown', 0) * 100:.2f}%")
    print(f"  Sharpe (daily):   {m.get('sharpe', 0):.2f}")
    print(f"  Sortino:          {m.get('sortino', 0):.2f}")
    print(f"  Calmar:           {m.get('calmar', 0):.2f}")
    print(f"  Cycle win rate:   {m.get('cycle_win_rate', 0) * 100:.1f}%")
    print(f"  Profit factor:    {m.get('cycle_profit_factor', 0):.2f}")
    print(f"  Pay-off ratio:    {m.get('pay_off_ratio', 0):.2f}")
    print(f"  Avg cycle hold:   {m.get('cycle_avg_hold_hours', 0):.1f} h")
    print(f"  Final equity:     ${res.final_equity:,.2f}")
    print(f"  Funding skips:    {res.funding_skips}  | halves: {res.funding_size_halves}")

    print("\n  EXIT-REASON DISTRIBUTION")
    for k, v in sorted(res.exit_reason_distribution.items(), key=lambda x: -x[1]):
        print(f"    {k:16} {v}")

    print("\n  ROLLING-COMPOUND DISTRIBUTION (adds per cycle)")
    for k in sorted(res.adds_distribution):
        print(f"    {k} adds: {res.adds_distribution[k]}")

    print("\n  EQUITY CURVE (ASCII)")
    print(_ascii_equity(res.equity_curve))

    # Persist artifacts so the demo doubles as the results generator.
    out = Path(__file__).resolve().parent / "backtest" / "results"
    out.mkdir(parents=True, exist_ok=True)
    if res.trades:
        import pandas as pd
        from backtest.run_backtest import _cycle_rows, _leg_rows
        pd.DataFrame(_leg_rows(res.trades)).to_csv(out / "trades.csv", index=False)
        pd.DataFrame(_cycle_rows(res.cycles)).to_csv(out / "cycles.csv", index=False)
    res.equity_curve.to_csv(out / "equity_curve.csv", header=["equity"])
    if len(res.equity_curve) > 0:
        fig, ax = plt.subplots(figsize=(12, 5))
        res.equity_curve.plot(ax=ax, color="#1f77b4", linewidth=1.2)
        ax.set_title(f"ETH Rapid Reversal — Equity Curve ({args.days}d, ${args.equity:,.0f})")
        ax.set_ylabel("Equity (USD)")
        ax.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig(out / "equity_curve.png", dpi=120)
        plt.close(fig)
    print(f"\nArtifacts written to {out}\\  (trades.csv, cycles.csv, "
          f"equity_curve.csv, equity_curve.png)")
    print("\nReproducible baseline:  python demo.py            (deterministic synthetic)")
    print("Live Agent Hub data:    python demo.py --source cmc   (needs CMC_API_KEY)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
