"""Performance metrics for the ETH rapid reversal backtest.

Works on both cycles (full Open→Close trades) and legs (individual executions).
Cycle-level stats are the headline numbers; leg-level stats are for debugging.
"""
from __future__ import annotations

from typing import List

import numpy as np
import pandas as pd

from .engine import Cycle, Trade


def compute_metrics(
    equity: pd.Series,
    cycles: List[Cycle],
    legs: List[Trade],
    exit_reason_distribution: dict | None = None,
    adds_distribution: dict | None = None,
) -> dict:
    if len(equity) == 0:
        return {"error": "no equity data"}

    daily = equity.resample("D").last().dropna()
    if len(daily) < 2:
        return {"error": "insufficient daily samples"}

    rets = daily.pct_change().dropna()
    total_return = float(equity.iloc[-1] / equity.iloc[0] - 1)
    days = max((daily.index[-1] - daily.index[0]).days, 1)
    annual_return = float((1 + total_return) ** (365 / days) - 1)
    sharpe = float(rets.mean() / rets.std() * np.sqrt(365)) if rets.std() and rets.std() > 0 else 0.0
    downside = rets[rets < 0]
    sortino = float(rets.mean() / downside.std() * np.sqrt(365)) if len(downside) > 0 and downside.std() and downside.std() > 0 else 0.0

    peak = equity.cummax()
    dd = (equity - peak) / peak
    max_dd = float(dd.min())
    max_dd_dur_days = 0
    cur = 0
    for v in dd:
        if v < 0:
            cur += 1
            max_dd_dur_days = max(max_dd_dur_days, cur)
        else:
            cur = 0
    calmar = float(annual_return / abs(max_dd)) if max_dd < 0 else 0.0

    n_cycles = len(cycles)
    n_legs = len(legs)

    if n_cycles == 0:
        return {
            "total_return": total_return, "annual_return": annual_return,
            "max_drawdown": max_dd, "max_dd_duration_days": max_dd_dur_days,
            "sharpe": sharpe, "sortino": sortino, "calmar": calmar,
            "n_cycles": 0, "n_legs": 0,
            "exit_reason_distribution": exit_reason_distribution or {},
            "adds_distribution": adds_distribution or {},
        }

    cycle_wins = [c for c in cycles if c.total_pnl > 0]
    cycle_losses = [c for c in cycles if c.total_pnl <= 0]
    cycle_win_rate = len(cycle_wins) / n_cycles
    cycle_gross_profit = sum(c.total_pnl for c in cycle_wins)
    cycle_gross_loss = abs(sum(c.total_pnl for c in cycle_losses))
    cycle_profit_factor = float(cycle_gross_profit / cycle_gross_loss) if cycle_gross_loss > 0 else float("inf")
    avg_cycle_win = float(np.mean([c.total_pnl for c in cycle_wins])) if cycle_wins else 0.0
    avg_cycle_loss = float(np.mean([c.total_pnl for c in cycle_losses])) if cycle_losses else 0.0
    cycle_hold_hours = [(c.exit_ts - c.entry_ts).total_seconds() / 3600 for c in cycles if c.exit_ts]
    avg_cycle_hold = float(np.mean(cycle_hold_hours)) if cycle_hold_hours else 0.0

    pay_off_ratio = float(avg_cycle_win / abs(avg_cycle_loss)) if cycle_losses and avg_cycle_loss != 0 else float("inf")

    cycle_sides: dict = {}
    for c in cycles:
        cycle_sides.setdefault(c.side, []).append(c.total_pnl)
    cycle_side_breakdown = {
        k: {"n": len(v), "total_pnl": float(sum(v)), "avg_pnl": float(np.mean(v))}
        for k, v in sorted(cycle_sides.items())
    }

    cycle_tiers: dict = {}
    for c in cycles:
        cycle_tiers.setdefault(c.tier, []).append(c.total_pnl)
    cycle_tier_breakdown = {
        k: {"n": len(v), "total_pnl": float(sum(v)), "avg_pnl": float(np.mean(v))}
        for k, v in sorted(cycle_tiers.items())
    }

    leg_exits = [leg for leg in legs if leg.exit_ts is not None and leg.pnl_usd != 0]
    leg_wins = [l for l in leg_exits if l.pnl_usd > 0]
    leg_losses = [l for l in leg_exits if l.pnl_usd <= 0]
    leg_gross_profit = sum(l.pnl_usd for l in leg_wins)
    leg_gross_loss = abs(sum(l.pnl_usd for l in leg_losses))
    leg_profit_factor = float(leg_gross_profit / leg_gross_loss) if leg_gross_loss > 0 else float("inf")
    leg_win_rate = len(leg_wins) / len(leg_exits) if leg_exits else 0.0

    leg_types: dict = {}
    for l in leg_exits:
        leg_types.setdefault(l.leg_type, []).append(l.pnl_usd)
    leg_type_breakdown = {
        k: {"n": len(v), "total_pnl": float(sum(v)), "avg_pnl": float(np.mean(v))}
        for k, v in sorted(leg_types.items())
    }

    return {
        "total_return": total_return,
        "annual_return": annual_return,
        "max_drawdown": max_dd,
        "max_dd_duration_days": max_dd_dur_days,
        "sharpe": sharpe,
        "sortino": sortino,
        "calmar": calmar,
        "n_cycles": n_cycles,
        "n_legs": n_legs,
        "cycle_win_rate": cycle_win_rate,
        "cycle_profit_factor": cycle_profit_factor,
        "cycle_avg_win": avg_cycle_win,
        "cycle_avg_loss": avg_cycle_loss,
        "cycle_avg_hold_hours": avg_cycle_hold,
        "pay_off_ratio": pay_off_ratio,
        "leg_win_rate": leg_win_rate,
        "leg_profit_factor": leg_profit_factor,
        "cycle_side_breakdown": cycle_side_breakdown,
        "cycle_tier_breakdown": cycle_tier_breakdown,
        "leg_type_breakdown": leg_type_breakdown,
        "exit_reason_distribution": exit_reason_distribution or {},
        "adds_distribution": adds_distribution or {},
    }
