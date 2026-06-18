"""Sanity tests for indicators. Run with: pytest tests/ -v"""
from __future__ import annotations

import numpy as np
import pandas as pd

from backtest.indicators import (
    adx,
    atr,
    divergence_modifier,
    divergence_signal,
    ema,
    fear_greed_alignment,
    fear_greed_zone,
    funding_allows_side,
    funding_modifier,
    funding_zone,
    macd,
    pct_delta,
    rsi,
)


def test_rsi_extreme_low_returns_low_value():
    s = pd.Series([100.0] * 20 + [50.0] * 30)
    out = rsi(s, 14)
    assert out.iloc[-1] < 30


def test_rsi_extreme_high_returns_high_value():
    s = pd.Series([50.0] * 20 + [100.0] * 30)
    out = rsi(s, 14)
    assert out.iloc[-1] > 70


def test_macd_returns_three_columns():
    s = pd.Series(np.cumsum(np.random.default_rng(0).normal(0, 1, 200)) + 1000)
    df = macd(s)
    assert set(df.columns) == {"macd", "signal", "hist"}
    assert len(df) == 200
    assert df["hist"].iloc[-1] == df["macd"].iloc[-1] - df["signal"].iloc[-1]


def test_ema_smooths_input():
    s = pd.Series(np.random.default_rng(1).normal(100, 5, 200))
    e = ema(s, 20)
    assert e.notna().all()
    assert abs(e.std()) < abs(s.std())


def test_atr_is_positive_and_finite():
    n = 200
    rng = np.random.default_rng(2)
    df = pd.DataFrame({
        "high": rng.uniform(100, 110, n),
        "low": rng.uniform(90, 100, n),
        "close": rng.uniform(95, 105, n),
    })
    a = atr(df["high"], df["low"], df["close"], 14)
    valid = a.dropna()
    assert (valid > 0).all()
    assert np.isfinite(valid).all()


def test_adx_in_unit_interval():
    n = 300
    rng = np.random.default_rng(3)
    df = pd.DataFrame({
        "high": rng.uniform(100, 110, n),
        "low": rng.uniform(90, 100, n),
        "close": rng.uniform(95, 105, n),
    })
    a = adx(df["high"], df["low"], df["close"], 14)
    valid = a.dropna()
    assert ((valid >= 0) & (valid <= 100)).all()


def test_fear_greed_zone_boundaries():
    assert fear_greed_zone(0) == "extreme_fear"
    assert fear_greed_zone(24) == "extreme_fear"
    assert fear_greed_zone(25) == "fear"
    assert fear_greed_zone(44) == "fear"
    assert fear_greed_zone(45) == "neutral"
    assert fear_greed_zone(55) == "neutral"
    assert fear_greed_zone(56) == "greed"
    assert fear_greed_zone(75) == "greed"
    assert fear_greed_zone(76) == "extreme_greed"
    assert fear_greed_zone(100) == "extreme_greed"


def test_fear_greed_alignment_long():
    assert fear_greed_alignment(15, "long") == "tailwind"
    assert fear_greed_alignment(40, "long") == "tailwind"
    assert fear_greed_alignment(50, "long") == "neutral"
    assert fear_greed_alignment(70, "long") == "headwind"
    assert fear_greed_alignment(85, "long") == "headwind"


def test_fear_greed_alignment_short():
    assert fear_greed_alignment(85, "short") == "tailwind"
    assert fear_greed_alignment(60, "short") == "tailwind"
    assert fear_greed_alignment(50, "short") == "neutral"
    assert fear_greed_alignment(40, "short") == "headwind"
    assert fear_greed_alignment(15, "short") == "headwind"


def test_funding_zone_thresholds():
    assert funding_zone(0.20) == "long_crowded_extreme"
    assert funding_zone(0.06) == "long_crowded"
    assert funding_zone(0.04) == "neutral"
    assert funding_zone(-0.04) == "neutral"
    assert funding_zone(-0.06) == "short_crowded"
    assert funding_zone(-0.20) == "short_crowded_extreme"


def test_funding_allows_side():
    assert funding_allows_side(0.02, "long") is True
    assert funding_allows_side(0.02, "short") is True
    assert funding_allows_side(0.06, "long") is False
    assert funding_allows_side(0.06, "short") is True
    assert funding_allows_side(-0.06, "long") is True
    assert funding_allows_side(-0.06, "short") is False
    assert funding_allows_side(0.20, "long") is False
    assert funding_allows_side(0.20, "short") is True


def test_funding_modifier():
    assert funding_modifier(0.02, "long") == 1.0
    assert funding_modifier(0.06, "long") == 0.5
    assert funding_modifier(0.20, "long") == 0.0
    assert funding_modifier(0.06, "short") == 1.0
    assert funding_modifier(-0.06, "short") == 0.5
    assert funding_modifier(-0.20, "short") == 0.0


def test_divergence_signal_classification():
    assert divergence_signal(10, -3) == "bearish_divergence"
    assert divergence_signal(-10, 3) == "bullish_divergence"
    assert divergence_signal(10, 5) == "confirmation"
    assert divergence_signal(-10, -5) == "confirmation"
    assert divergence_signal(1, 1) == "no_data"
    assert divergence_signal(10, 0) == "no_data"


def test_divergence_modifier_for_long():
    assert divergence_modifier("bearish_divergence", "long") == "downgrade"
    assert divergence_modifier("bullish_divergence", "long") == "upgrade"
    assert divergence_modifier("confirmation", "long") == "none"
    assert divergence_modifier("no_data", "long") == "none"


def test_divergence_modifier_for_short():
    assert divergence_modifier("bearish_divergence", "short") == "upgrade"
    assert divergence_modifier("bullish_divergence", "short") == "downgrade"
    assert divergence_modifier("confirmation", "short") == "none"


def test_pct_delta():
    s = pd.Series([100.0, 110.0, 121.0, 133.0])
    d = pct_delta(s, 1)
    assert abs(d.iloc[1] - 10.0) < 0.01
    assert abs(d.iloc[2] - 10.0) < 0.01
    assert pd.isna(d.iloc[0])


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-v"]))
