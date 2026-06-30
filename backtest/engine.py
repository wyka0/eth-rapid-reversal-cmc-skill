"""Walk-forward backtest engine for the ETH rapid reversal strategy — trailing-stop variant.

Architecture:
- RSI(14) + MACD(12,26,9) + Fear & Greed + derivatives funding + social/OI divergence
- Two-way long/short
- **Trailing stop exit** (replaces fixed tiered TP): stop trails high water mark by `trail_distance_pct` once profit > `trail_activation_pct`
- Hard SL at `-sl_pct` (only matters before trail activates)
- Rolling compound: up to 5 profit-funded scale-ins per cycle
- Base leverage: 15x (single value, no tiered)
- Immediate exit on ranging (ADX < threshold)
- Daily loss limit + drawdown circuit breaker
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np
import pandas as pd

from .indicators import (
    adx,
    bollinger_bands,
    divergence_modifier,
    divergence_signal,
    ema,
    fear_greed_alignment,
    funding_modifier,
    macd,
    pct_delta,
    rsi,
    volume_above_average,
)


@dataclass
class Trade:
    """One execution leg within a cycle (Open, Add, Close)."""
    cycle_id: str
    leg_type: str
    entry_ts: pd.Timestamp
    side: str
    tier: str
    leverage: float
    notional: float
    size: float
    price: float
    exit_ts: Optional[pd.Timestamp] = None
    exit_price: Optional[float] = None
    exit_reason: Optional[str] = None
    pnl_usd: float = 0.0
    pnl_pct: float = 0.0
    cum_size_after: float = 0.0
    cum_avg_entry: float = 0.0
    cum_notional_after: float = 0.0
    rsi_at_entry: float = 0.0
    macd_hist_at_entry: float = 0.0
    adx_at_entry: float = 0.0
    fg_at_entry: float = 50.0
    funding_at_entry: float = 0.0
    social_delta_24h_at_entry: float = 0.0
    oi_delta_24h_at_entry: float = 0.0
    divergence_at_entry: str = "no_data"
    bars_since_open: int = 0
    bars_since_last_event: int = 0


@dataclass
class Cycle:
    """Full trade cycle from Open to Close, aggregating all legs."""
    cycle_id: str
    side: str
    entry_ts: pd.Timestamp
    avg_entry: float
    original_size: float
    leverage: float
    tier: str
    adds_count: int = 0
    cum_size: float = 0.0
    total_notional: float = 0.0
    max_size: float = 0.0
    high_water_mark: float = 0.0
    trailing_active: bool = False
    momentum_confirmed: bool = False
    exit_ts: Optional[pd.Timestamp] = None
    exit_price: Optional[float] = None
    exit_reason: Optional[str] = None
    total_pnl: float = 0.0
    total_commission: float = 0.0
    bars_held: int = 0
    rsi_at_open: float = 0.0
    macd_hist_at_open: float = 0.0
    adx_at_open: float = 0.0
    fg_at_open: float = 50.0
    funding_at_open: float = 0.0
    divergence_at_open: str = "no_data"
    last_event_ts: Optional[pd.Timestamp] = None
    last_event_price: float = 0.0


@dataclass
class BacktestResult:
    trades: List[Trade] = field(default_factory=list)
    cycles: List[Cycle] = field(default_factory=list)
    equity_curve: pd.Series = field(default_factory=lambda: pd.Series(dtype=float))
    final_equity: float = 0.0
    peak_equity: float = 0.0
    max_drawdown: float = 0.0
    daily_loss_halts: int = 0
    funding_skips: int = 0
    funding_size_halves: int = 0
    divergence_distribution: dict = field(default_factory=dict)
    exit_reason_distribution: dict = field(default_factory=dict)
    adds_distribution: dict = field(default_factory=dict)


DEFAULT_PARAMS = {
    "rsi_period": 14,
    "rsi_oversold": 35,
    "rsi_overbought": 65,
    "rsi_extreme_low": 22,
    "rsi_extreme_high": 78,
    "macd_fast": 12,
    "macd_slow": 26,
    "macd_signal": 9,
    "ema_trend": 50,
    "adx_period": 14,
    "adx_threshold": 15,
    "base_leverage": 15.0,
    "sl_pct": 0.010,
    "trail_distance_pct": 0.003,
    "trail_activation_pct": 0.005,
    "bollinger_period": 20,
    "bollinger_std": 2.0,
    "bollinger_proximity": 0.015,
    "volume_period": 20,
    "volume_multiplier": 1.0,
    "risk_per_trade": 0.015,
    "dd_circuit_pct": 0.10,
    "dd_circuit_halve_trades": 10,
    "dd_circuit_recovery_wins": 5,
    "fg_long_tailwind_max": 35,
    "fg_short_tailwind_min": 65,
    "funding_crowded_pct": 0.05,
    "funding_extreme_pct": 0.10,
    "divergence_social_threshold_pct": 5.0,
    "divergence_oi_threshold_pct": 2.0,
    "divergence_lookback_hours": 24,
    "slippage_pct": 0.0005,
    "commission_pct": 0.0004,
    "starting_equity": 10_000.0,
    "daily_loss_limit_pct": 0.05,
    "warmup_bars": 60,
    "rolling_max_times": 5,
    "rolling_add_pcts": [0.10, 0.09, 0.08, 0.07, 0.06],
    "rolling_min_profit_pct": 0.005,
    "rolling_min_bars_between": 3,
    "time_stop_bars": 96,
}


def _as_ms_utc(idx) -> pd.DatetimeIndex:
    ts = pd.to_datetime(idx, utc=True)
    if isinstance(ts, pd.DatetimeIndex):
        return ts.as_unit("ms")
    return ts.dt.as_unit("ms")


class BacktestEngine:
    def __init__(self, params: Optional[dict] = None):
        self.params = {**DEFAULT_PARAMS, **(params or {})}

    def run(
        self,
        df_5m: pd.DataFrame,
        df_15m: pd.DataFrame,
        fg_daily: pd.Series,
        funding: Optional[pd.Series] = None,
        oi: Optional[pd.Series] = None,
        social: Optional[pd.Series] = None,
    ) -> BacktestResult:
        p = self.params
        equity = float(p["starting_equity"])
        equity_base = equity
        peak_equity = equity
        equity_curve: list[dict] = []
        trades: List[Trade] = []
        cycles: List[Cycle] = []
        current: Optional[Cycle] = None
        dd_breaker_active = False
        dd_breaker_remaining = 0
        wins_after_dd = 0
        current_day = None
        daily_start_equity = equity
        daily_halts = 0
        funding_skips = 0
        funding_size_halves = 0
        div_dist: dict = {"bullish_divergence": 0, "bearish_divergence": 0, "confirmation": 0, "no_data": 0}
        exit_reason_dist: dict = {}
        adds_dist: dict = {i: 0 for i in range(p["rolling_max_times"] + 1)}

        if "timestamp" not in df_5m.columns:
            raise ValueError("df_5m must have a timestamp column")
        df_5m = df_5m.sort_values("timestamp").reset_index(drop=True)
        df_15m = df_15m.sort_values("timestamp").reset_index(drop=True)
        df_5m["timestamp"] = pd.to_datetime(df_5m["timestamp"], utc=True).dt.as_unit("ms")
        df_15m["timestamp"] = pd.to_datetime(df_15m["timestamp"], utc=True).dt.as_unit("ms")

        close5 = df_5m["close"]
        rsi5 = rsi(close5, p["rsi_period"])
        macd_df = macd(close5, p["macd_fast"], p["macd_slow"], p["macd_signal"])
        macd_hist = macd_df["hist"]
        ema15 = ema(df_15m["close"], p["ema_trend"])
        adx15 = adx(df_15m["high"], df_15m["low"], df_15m["close"], p["adx_period"])
        bb_upper, bb_mid, bb_lower = bollinger_bands(close5, p["bollinger_period"], p["bollinger_std"])
        vol_above = volume_above_average(df_5m["volume"], p["volume_period"], p["volume_multiplier"])

        base = df_5m[["timestamp"]].copy()
        df_15_ind = pd.DataFrame({
            "timestamp": _as_ms_utc(df_15m["timestamp"]),
            "ema50_15m": ema15.values,
            "adx_15m": adx15.values,
        }).sort_values("timestamp")
        base = pd.merge_asof(base, df_15_ind, on="timestamp", direction="backward")

        bb_df = pd.DataFrame({
            "timestamp": _as_ms_utc(bb_upper.index),
            "bb_upper": bb_upper.values,
            "bb_mid": bb_mid.values,
            "bb_lower": bb_lower.values,
            "vol_above": vol_above.values.astype(float),
        }).sort_values("timestamp")
        base = pd.merge_asof(base, bb_df, on="timestamp", direction="backward")

        base["funding"] = 0.0
        if funding is not None and len(funding) > 0:
            fund_df = pd.DataFrame({
                "timestamp": _as_ms_utc(funding.index),
                "funding": funding.values.astype(float),
            }).sort_values("timestamp")
            base = pd.merge_asof(base, fund_df, on="timestamp", direction="backward", suffixes=("", "_f"))
            if "funding_f" in base.columns:
                base["funding"] = base["funding_f"].fillna(base["funding"])
                base = base.drop(columns=["funding_f"])
        base["funding"] = base["funding"].fillna(0.0)

        base["oi_delta_24h_pct"] = 0.0
        if oi is not None and len(oi) > 0:
            hours = int(p["divergence_lookback_hours"])
            oi_delta = pct_delta(oi, hours).ffill().fillna(0.0)
            oi_df = pd.DataFrame({
                "timestamp": _as_ms_utc(oi_delta.index),
                "oi_delta_24h_pct": oi_delta.values,
            }).sort_values("timestamp")
            base = pd.merge_asof(base, oi_df, on="timestamp", direction="backward", suffixes=("", "_o"))
            if "oi_delta_24h_pct_o" in base.columns:
                base["oi_delta_24h_pct"] = base["oi_delta_24h_pct_o"].fillna(base["oi_delta_24h_pct"])
                base = base.drop(columns=["oi_delta_24h_pct_o"])
        base["oi_delta_24h_pct"] = base["oi_delta_24h_pct"].fillna(0.0)

        base["social_delta_24h_pct"] = 0.0
        if social is not None and len(social) > 0:
            hours = int(p["divergence_lookback_hours"])
            soc_delta = pct_delta(social, hours).ffill().fillna(0.0)
            soc_df = pd.DataFrame({
                "timestamp": _as_ms_utc(soc_delta.index),
                "social_delta_24h_pct": soc_delta.values,
            }).sort_values("timestamp")
            base = pd.merge_asof(base, soc_df, on="timestamp", direction="backward", suffixes=("", "_s"))
            if "social_delta_24h_pct_s" in base.columns:
                base["social_delta_24h_pct"] = base["social_delta_24h_pct_s"].fillna(base["social_delta_24h_pct"])
                base = base.drop(columns=["social_delta_24h_pct_s"])
        base["social_delta_24h_pct"] = base["social_delta_24h_pct"].fillna(0.0)

        base = base.reset_index(drop=True)
        warmup = max(p["warmup_bars"], 30)
        n = len(df_5m)
        cycle_id_counter = 0

        def finalize_cycle(reason: str, exit_price: float, exit_ts: pd.Timestamp):
            nonlocal equity, wins_after_dd, dd_breaker_remaining, dd_breaker_active, current
            if current is None:
                return
            self._close_cycle(current, exit_price, exit_ts, reason, trades, p)
            equity += current.total_pnl
            cycles.append(current)
            if current.total_pnl > 0:
                wins_after_dd += 1
            if dd_breaker_active:
                dd_breaker_remaining -= 1
                if dd_breaker_remaining <= 0 and wins_after_dd >= p["dd_circuit_recovery_wins"]:
                    dd_breaker_active = False
                    wins_after_dd = 0
            adds_dist[current.adds_count] = adds_dist.get(current.adds_count, 0) + 1
            exit_reason_dist[reason] = exit_reason_dist.get(reason, 0) + 1
            current = None

        for i in range(warmup, n):
            row = df_5m.iloc[i]
            ts = pd.Timestamp(row["timestamp"])
            o, h, l, c = row["open"], row["high"], row["low"], row["close"]
            rsi_v = float(rsi5.iloc[i]) if not pd.isna(rsi5.iloc[i]) else 50.0
            mh = float(macd_hist.iloc[i]) if not pd.isna(macd_hist.iloc[i]) else 0.0
            mh_prev = float(macd_hist.iloc[i - 1]) if not pd.isna(macd_hist.iloc[i - 1]) else 0.0
            mh_prev2 = float(macd_hist.iloc[i - 2]) if not pd.isna(macd_hist.iloc[i - 2]) else 0.0
            ema_v = float(base["ema50_15m"].iloc[i]) if not pd.isna(base["ema50_15m"].iloc[i]) else c
            adx_v = float(base["adx_15m"].iloc[i]) if not pd.isna(base["adx_15m"].iloc[i]) else 0.0
            funding_v = float(base["funding"].iloc[i]) if not pd.isna(base["funding"].iloc[i]) else 0.0
            oi_d = float(base["oi_delta_24h_pct"].iloc[i]) if not pd.isna(base["oi_delta_24h_pct"].iloc[i]) else 0.0
            soc_d = float(base["social_delta_24h_pct"].iloc[i]) if not pd.isna(base["social_delta_24h_pct"].iloc[i]) else 0.0
            bb_up = float(base["bb_upper"].iloc[i]) if not pd.isna(base["bb_upper"].iloc[i]) else c
            bb_lo = float(base["bb_lower"].iloc[i]) if not pd.isna(base["bb_lower"].iloc[i]) else c
            vol_ok = float(base["vol_above"].iloc[i]) if not pd.isna(base["vol_above"].iloc[i]) else 0.0 > 0.5

            day = ts.date()
            if day != current_day:
                current_day = day
                daily_start_equity = equity

            daily_loss_breach = equity < daily_start_equity * (1 - p["daily_loss_limit_pct"])

            # ============ ENTRY ============
            if current is None and not daily_loss_breach and adx_v >= p["adx_threshold"]:
                fg_val = self._get_fg(fg_daily, ts)
                side = None
                if rsi_v <= p["rsi_oversold"]:
                    side = "long"
                elif rsi_v >= p["rsi_overbought"]:
                    side = "short"
                if side is not None:
                    fg_align = fear_greed_alignment(fg_val, side)
                    trend_ok = (side == "long" and c > ema_v) or (side == "short" and c < ema_v)
                    if side == "long":
                        bb_ok = c <= bb_lo * (1 + p["bollinger_proximity"])
                    else:
                        bb_ok = c >= bb_up * (1 - p["bollinger_proximity"])
                    if fg_align != "headwind" and trend_ok and bb_ok and vol_ok:
                        div = divergence_signal(soc_d, oi_d, p["divergence_social_threshold_pct"], p["divergence_oi_threshold_pct"])
                        div_dist[div] = div_dist.get(div, 0) + 1
                        tier = self._tier(rsi_v, mh, mh_prev, mh_prev2, fg_align, div, side, p)
                        lev = p["base_leverage"]
                        fund_mult = funding_modifier(funding_v, side)
                        if fund_mult == 0.5:
                            funding_size_halves += 1
                        if fund_mult == 0.0:
                            funding_skips += 1
                            side = None
                        if side is not None:
                            entry_px = c * (1 + p["slippage_pct"]) if side == "long" else c * (1 - p["slippage_pct"])
                            # Risk-based sizing (spec section 9): risk `risk_per_trade` of equity at a
                            # `sl_pct` price stop. `base_leverage` is the notional cap (15x) and rarely
                            # binds under the default 1.5% risk / 1.0% stop (-> ~1.5x effective). The DD
                            # circuit breaker halves the deployed size (real risk reduction, since the
                            # cap does not bind). Leverage is baked into the notional, so PnL must NOT
                            # be multiplied by leverage again downstream.
                            risk_mult = 0.5 if dd_breaker_active else 1.0
                            raw_notional = equity_base * p["risk_per_trade"] / p["sl_pct"] * risk_mult
                            cap_notional = equity * lev
                            size_notional = min(raw_notional, cap_notional) * fund_mult
                            size_eth = size_notional / entry_px
                            commission = size_notional * p["commission_pct"]
                            equity -= commission
                            cycle_id_counter += 1
                            current = Cycle(
                                cycle_id=f"C{cycle_id_counter:04d}",
                                side=side,
                                entry_ts=ts,
                                avg_entry=entry_px,
                                original_size=size_eth,
                                leverage=lev,
                                tier=tier,
                                cum_size=size_eth,
                                total_notional=size_notional,
                                max_size=size_eth,
                                high_water_mark=entry_px,
                                rsi_at_open=rsi_v,
                                macd_hist_at_open=mh,
                                adx_at_open=adx_v,
                                fg_at_open=fg_val,
                                funding_at_open=funding_v,
                                divergence_at_open=div,
                                last_event_ts=ts,
                                last_event_price=entry_px,
                            )
                            trades.append(Trade(
                                cycle_id=current.cycle_id,
                                leg_type="open",
                                entry_ts=ts,
                                side=side,
                                tier=tier,
                                leverage=lev,
                                notional=size_notional,
                                size=size_eth,
                                price=entry_px,
                                cum_size_after=size_eth,
                                cum_avg_entry=entry_px,
                                cum_notional_after=size_notional,
                                rsi_at_entry=rsi_v,
                                macd_hist_at_entry=mh,
                                adx_at_entry=adx_v,
                                fg_at_entry=fg_val,
                                funding_at_entry=funding_v,
                                social_delta_24h_at_entry=soc_d,
                                oi_delta_24h_at_entry=oi_d,
                                divergence_at_entry=div,
                                bars_since_open=0,
                                bars_since_last_event=0,
                            ))

            # ============ EXIT + MANAGEMENT ============
            if current is not None:
                current.bars_held += 1

                # Update high water mark using bar extremes (not just close)
                if current.side == "long":
                    # Best favorable price for long = highest seen
                    hwm_candidate = max(h, current.high_water_mark)
                else:
                    # Best favorable price for short = lowest seen
                    if current.high_water_mark == 0:
                        hwm_candidate = l
                    else:
                        hwm_candidate = min(l, current.high_water_mark)
                current.high_water_mark = hwm_candidate

                # Price move on the blended position (unleveraged). Leverage lives in the
                # notional sizing, so thresholds (SL / trail activation) are price moves,
                # matching the worked example in SKILL.md section 5.
                if current.side == "long":
                    pm = (c - current.avg_entry) / current.avg_entry
                else:
                    pm = (current.avg_entry - c) / current.avg_entry

                # Track whether momentum has confirmed in the trade direction. This guards the
                # MACD-reversal exit: a mean-reversion long taken at deep oversold has a negative
                # histogram by construction, so we must not exit on "histogram adverse" until
                # momentum had actually confirmed in our favour first.
                if (current.side == "long" and mh > 0) or (current.side == "short" and mh < 0):
                    current.momentum_confirmed = True

                # Activate trailing stop once in profit enough (price-move threshold)
                if pm >= p["trail_activation_pct"]:
                    current.trailing_active = True

                # Calculate trailing stop level
                trail_sl = None
                if current.trailing_active:
                    if current.side == "long":
                        trail_sl = current.high_water_mark * (1 - p["trail_distance_pct"])
                    else:
                        trail_sl = current.high_water_mark * (1 + p["trail_distance_pct"])

                # ============ EXIT DECISION (priority order) ============
                exit_px = None
                reason = None

                # 1. Hard SL (only if trailing not yet active)
                if not current.trailing_active and pm <= -p["sl_pct"]:
                    exit_px = c
                    reason = "sl"

                # 2. Trailing stop hit (intrabar — use bar extremes)
                elif trail_sl is not None:
                    if current.side == "long" and l <= trail_sl:
                        exit_px = trail_sl
                        reason = "trail_sl"
                    elif current.side == "short" and h >= trail_sl:
                        exit_px = trail_sl
                        reason = "trail_sl"

                # 3. Immediate ranging exit
                if exit_px is None and adx_v < p["adx_threshold"]:
                    exit_px = c
                    reason = "ranging_close"

                # 4. MACD reversal — 3 consecutive bars against the position, but ONLY after
                #    momentum had confirmed in the trade direction (spec section 8).
                if exit_px is None and current.momentum_confirmed:
                    adverse = (
                        (current.side == "long" and mh < 0 and mh_prev < 0 and mh_prev2 < 0)
                        or (current.side == "short" and mh > 0 and mh_prev > 0 and mh_prev2 > 0)
                    )
                    if adverse:
                        exit_px = c
                        reason = "macd_rev"

                # 5. Time stop
                if exit_px is None and current.bars_held >= p["time_stop_bars"]:
                    exit_px = c
                    reason = "time_stop"

                if exit_px is not None:
                    finalize_cycle(reason, exit_px, ts)
                    continue

                # ============ ROLLING COMPOUND ============
                if current.adds_count < p["rolling_max_times"]:
                    last_px = current.last_event_price if current.last_event_price > 0 else current.avg_entry
                    if current.side == "long":
                        price_move = (c - last_px) / last_px
                        macd_continues = mh > 0
                    else:
                        price_move = (last_px - c) / last_px
                        macd_continues = mh < 0
                    fg_align = fear_greed_alignment(self._get_fg(fg_daily, ts), current.side)
                    bars_since_last = (ts - current.last_event_ts).total_seconds() / 300.0 if current.last_event_ts else 999
                    if (
                        pm > 0
                        and macd_continues
                        and price_move >= p["rolling_min_profit_pct"]
                        and adx_v >= p["adx_threshold"]
                        and funding_modifier(funding_v, current.side) > 0
                        and fg_align != "headwind"
                        and bars_since_last >= p["rolling_min_bars_between"]
                    ):
                        self._do_add(current, c, ts, trades, p, equity, mh, rsi_v, adx_v, self._get_fg(fg_daily, ts), funding_v, soc_d, oi_d, div)

            # ============ EQUITY TRACKING ============
            if equity > peak_equity:
                peak_equity = equity
            dd = (peak_equity - equity) / peak_equity if peak_equity > 0 else 0.0
            if dd >= p["dd_circuit_pct"] and not dd_breaker_active:
                dd_breaker_active = True
                dd_breaker_remaining = p["dd_circuit_halve_trades"]
                wins_after_dd = 0
                equity_base = equity
            if daily_loss_breach and current is None and day != current_day:
                daily_halts += 1

            equity_curve.append({"timestamp": ts, "equity": equity})

        if current is not None:
            finalize_cycle("end_of_data", df_5m.iloc[-1]["close"], df_5m.iloc[-1]["timestamp"])

        eq = pd.Series(
            [r["equity"] for r in equity_curve],
            index=pd.DatetimeIndex([r["timestamp"] for r in equity_curve]),
            name="equity",
        )
        peak = eq.cummax()
        dd_series = (eq - peak) / peak
        return BacktestResult(
            trades=trades,
            cycles=cycles,
            equity_curve=eq,
            final_equity=equity,
            peak_equity=peak_equity,
            max_drawdown=float(abs(dd_series.min())) if len(dd_series) > 0 else 0.0,
            daily_loss_halts=daily_halts,
            funding_skips=funding_skips,
            funding_size_halves=funding_size_halves,
            divergence_distribution=div_dist,
            exit_reason_distribution=exit_reason_dist,
            adds_distribution=adds_dist,
        )

    def _tier(self, rsi_v, mh, mh_prev, mh_prev2, fg_align, div, side, p):
        if side == "long":
            extreme = rsi_v <= p["rsi_extreme_low"]
        else:
            extreme = rsi_v >= p["rsi_extreme_high"]
        macd_cross = (mh > 0 and mh_prev <= 0) or (mh < 0 and mh_prev >= 0)
        macd_turn = abs(mh) > abs(mh_prev) and abs(mh_prev) >= abs(mh_prev2)
        if extreme and (macd_cross or macd_turn) and fg_align == "tailwind":
            base = "A"
        elif macd_turn and fg_align != "headwind":
            base = "B"
        else:
            base = "C"
        div_mod = divergence_modifier(div, side)
        if div_mod == "downgrade":
            return "B" if base == "A" else "C"
        if div_mod == "upgrade" and base == "C":
            return "B"
        return base

    def _do_add(self, cycle: Cycle, c: float, ts: pd.Timestamp, trades: List[Trade], p: dict, equity: float,
                mh: float, rsi_v: float, adx_v: float, fg_val: float, funding_v: float,
                soc_d: float, oi_d: float, div: str):
        idx = cycle.adds_count
        if idx >= len(p["rolling_add_pcts"]):
            return
        add_pct = p["rolling_add_pcts"][idx]
        add_size = cycle.original_size * add_pct
        if cycle.side == "long":
            entry_px = c * (1 + p["slippage_pct"])
        else:
            entry_px = c * (1 - p["slippage_pct"])
        notional = add_size * entry_px
        commission = notional * p["commission_pct"]
        cycle.total_commission += commission
        prev_size = cycle.cum_size
        prev_notional = cycle.total_notional
        new_size = prev_size + add_size
        new_notional = prev_notional + notional
        cycle.avg_entry = (cycle.avg_entry * prev_notional + entry_px * notional) / new_notional
        cycle.cum_size = new_size
        cycle.total_notional = new_notional
        cycle.adds_count += 1
        cycle.max_size = max(cycle.max_size, new_size)
        cycle.last_event_ts = ts
        cycle.last_event_price = c
        # Reset trailing — new avg_entry changes the math
        if cycle.side == "long":
            cycle.high_water_mark = max(cycle.high_water_mark, entry_px)
        else:
            if cycle.high_water_mark == 0:
                cycle.high_water_mark = entry_px
            else:
                cycle.high_water_mark = min(cycle.high_water_mark, entry_px)
        trades.append(Trade(
            cycle_id=cycle.cycle_id,
            leg_type=f"add_{cycle.adds_count}",
            entry_ts=ts,
            side=cycle.side,
            tier=cycle.tier,
            leverage=cycle.leverage,
            notional=notional,
            size=add_size,
            price=entry_px,
            cum_size_after=new_size,
            cum_avg_entry=cycle.avg_entry,
            cum_notional_after=new_notional,
            rsi_at_entry=rsi_v,
            macd_hist_at_entry=mh,
            adx_at_entry=adx_v,
            fg_at_entry=fg_val,
            funding_at_entry=funding_v,
            social_delta_24h_at_entry=soc_d,
            oi_delta_24h_at_entry=oi_d,
            divergence_at_entry=div,
            bars_since_open=cycle.bars_held,
            bars_since_last_event=0,
        ))

    def _close_cycle(self, cycle: Cycle, exit_px: float, ts: pd.Timestamp, reason: str,
                     trades: List[Trade], p: dict):
        if cycle.cum_size <= 1e-9:
            cycle.exit_ts = ts
            cycle.exit_price = exit_px
            cycle.exit_reason = reason
            return
        if cycle.side == "long":
            exit_adj = exit_px * (1 - p["slippage_pct"])
            ret = exit_adj / cycle.avg_entry - 1.0
        else:
            exit_adj = exit_px * (1 + p["slippage_pct"])
            ret = 1.0 - exit_adj / cycle.avg_entry
        # PnL on the blended position. Leverage is already baked into the notional sizing
        # (position sized off risk_per_trade / sl_pct, capped at base_leverage x equity), so
        # multiplying by leverage again here would double-count it (the original bug).
        notional = cycle.cum_size * exit_adj
        pnl = notional * ret - notional * p["commission_pct"]
        commission = notional * p["commission_pct"]
        cycle.total_pnl += pnl
        cycle.total_commission += commission
        trades.append(Trade(
            cycle_id=cycle.cycle_id,
            leg_type="close",
            entry_ts=ts,
            side=cycle.side,
            tier=cycle.tier,
            leverage=cycle.leverage,
            notional=notional,
            size=cycle.cum_size,
            price=cycle.avg_entry,
            exit_ts=ts,
            exit_price=exit_adj,
            exit_reason=reason,
            pnl_usd=pnl,
            pnl_pct=ret * 100,
            cum_size_after=0.0,
            cum_avg_entry=cycle.avg_entry,
            cum_notional_after=0.0,
            bars_since_open=cycle.bars_held,
            bars_since_last_event=0,
        ))
        cycle.cum_size = 0.0
        cycle.total_notional = 0.0
        cycle.exit_ts = ts
        cycle.exit_price = exit_adj
        cycle.exit_reason = reason

    def _get_fg(self, fg_daily: pd.Series, ts: pd.Timestamp) -> float:
        if not isinstance(fg_daily.index, pd.DatetimeIndex):
            try:
                fg_daily = pd.Series(fg_daily.values, index=pd.to_datetime(list(fg_daily.index)).date)
            except Exception:
                return 50.0
        day = ts.date()
        if day in fg_daily.index:
            return float(fg_daily.loc[day])
        prior_idx = [d for d in fg_daily.index if d < day]
        if prior_idx:
            return float(fg_daily.loc[max(prior_idx)])
        return 50.0
