"""Engine-level tests for the walk-forward backtest engine.

The indicator tests (test_indicators.py) cover the math primitives; these cover
the trade lifecycle: entries actually fire, the leverage cap holds, sizing is
risk-based (not double-counted by leverage), and the MACD-reversal exit can no
longer fire instantly at entry.
"""
from __future__ import annotations

import os

os.environ.setdefault("CMC_FORCE_SYNTHETIC", "1")

import pandas as pd

from backtest.data_loader import (
    load_cmc_fear_greed,
    load_cmc_funding_rate,
    load_cmc_ohlcv,
    load_cmc_open_interest,
    load_cmc_social_mentions,
)
from backtest.engine import DEFAULT_PARAMS, BacktestEngine

VALID_EXITS = {"trail_sl", "sl", "ranging_close", "macd_rev", "time_stop", "end_of_data"}


def _load_and_run_once(days=30):
    df5 = load_cmc_ohlcv("ETH", "5m", days)
    df15 = load_cmc_ohlcv("ETH", "15m", days)
    fg = load_cmc_fear_greed(days)
    funding = load_cmc_funding_rate("ETH", days)
    oi = load_cmc_open_interest("ETH", days)
    social = load_cmc_social_mentions("ETH", days)
    eng = BacktestEngine({"starting_equity": 10_000.0})
    return eng.run(df5, df15, fg, funding=funding, oi=oi, social=social)


# Load + run ONCE at import time; every test below asserts on this result.
_RESULT = _load_and_run_once()


def test_engine_produces_trades_on_synthetic():
    res = _RESULT
    assert len(res.cycles) > 0, "engine produced zero cycles — entry filters too strict"
    assert len(res.trades) >= 2 * len(res.cycles), "each cycle should have >= open+close legs"
    for c in res.cycles:
        assert c.exit_reason in VALID_EXITS, f"bad exit_reason {c.exit_reason}"
        assert pd.notna(c.total_pnl) and isinstance(c.total_pnl, float)


def test_leverage_cap_respected():
    res = _RESULT
    cap = DEFAULT_PARAMS["base_leverage"]
    for t in res.trades:
        if t.leg_type == "open":
            assert t.notional <= 10_000.0 * cap * 1.0001, (
                f"open notional {t.notional} exceeds {cap}x equity cap"
            )


def test_sizing_is_risk_based_not_leverage_inflated():
    """Default 1.5% risk / 1.0% stop -> ~1.5x effective, well under the 15x cap.

    This is the regression guard for the leverage double-count bug: previously
    sizing multiplied by leverage, forcing the cap to bind at 15x and then PnL
    multiplied by leverage again. Now the cap must NOT bind for a default-risk
    open with neutral funding.
    """
    res = _RESULT
    opens = [t for t in res.trades if t.leg_type == "open"]
    assert len(opens) > 0
    assert any(t.notional <= 10_000.0 * 1.6 for t in opens), (
        "no open used risk-based sizing; cap may be binding (leverage double-count)"
    )


def test_no_instant_macd_reversal_exit():
    """A mean-reversion long taken at oversold has a negative histogram by
    construction; the MACD-reversal exit must wait for momentum to confirm
    first, so it can never fire on the first management bar."""
    res = _RESULT
    for c in res.cycles:
        if c.exit_reason == "macd_rev":
            assert c.bars_held >= 2, (
                f"cycle {c.cycle_id} exited via macd_rev at bars_held={c.bars_held} "
                "(instant exit regression)"
            )


def test_pnl_not_leverage_inflated():
    """A single cycle's PnL must be bounded by a sane fraction of its deployed
    notional. The old double-count bug produced PnL ~15x too large."""
    res = _RESULT
    for c in res.cycles:
        deployed = c.max_size * c.avg_entry
        if deployed > 0:
            ratio = abs(c.total_pnl) / deployed
            assert ratio < 0.25, (
                f"cycle {c.cycle_id} |pnl|/notional={ratio:.3f} (>25%) — leverage double-count?"
            )


def test_trailing_stop_locked_on_winners():
    """At least one winning cycle should have used the trailing stop exit."""
    res = _RESULT
    winners = [c for c in res.cycles if c.total_pnl > 0]
    assert len(winners) > 0, "no winning cycles on synthetic data"
    assert any(c.exit_reason == "trail_sl" for c in winners), (
        "no winner exited via trail_sl — trailing stop not engaging"
    )


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-v"]))
