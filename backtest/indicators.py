"""Technical indicators using pure pandas/numpy. No TA-Lib dependency."""
from __future__ import annotations

import numpy as np
import pandas as pd


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    rs = avg_gain / avg_loss
    out = 100 - (100 / (1 + rs))
    out = out.where(avg_loss > 0, 100.0)
    out = out.where(avg_gain > 0, 0.0)
    return out.fillna(50.0)


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    hist = macd_line - signal_line
    return pd.DataFrame({"macd": macd_line, "signal": signal_line, "hist": hist})


def ema(close: pd.Series, period: int) -> pd.Series:
    return close.ewm(span=period, adjust=False).mean()


def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    prev_close = close.shift(1)
    tr = pd.concat(
        [(high - low), (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    ).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()


def adx(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = pd.Series(np.where((up_move > down_move) & (up_move > 0), up_move, 0.0), index=high.index)
    minus_dm = pd.Series(np.where((down_move > up_move) & (down_move > 0), down_move, 0.0), index=high.index)
    tr = atr(high, low, close, period)
    plus_di = 100 * plus_dm.ewm(alpha=1 / period, adjust=False).mean() / tr.replace(0, np.nan)
    minus_di = 100 * minus_dm.ewm(alpha=1 / period, adjust=False).mean() / tr.replace(0, np.nan)
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    return dx.ewm(alpha=1 / period, adjust=False).mean().fillna(0.0)


def bollinger_bands(close: pd.Series, period: int = 20, std: float = 2.0):
    sma = close.rolling(period).mean()
    rolling_std = close.rolling(period).std()
    upper = sma + (rolling_std * std)
    lower = sma - (rolling_std * std)
    return upper, sma, lower


def volume_above_average(volume: pd.Series, period: int = 20, multiplier: float = 1.5) -> pd.Series:
    avg_vol = volume.rolling(period).mean()
    return volume > (avg_vol * multiplier)


def fear_greed_zone(value: float) -> str:
    if value < 25:
        return "extreme_fear"
    if value < 45:
        return "fear"
    if value <= 55:
        return "neutral"
    if value <= 75:
        return "greed"
    return "extreme_greed"


def fear_greed_alignment(fg_value: float, side: str) -> str:
    zone = fear_greed_zone(fg_value)
    if side == "long":
        if zone in ("extreme_fear", "fear"):
            return "tailwind"
        if zone == "neutral":
            return "neutral"
        return "headwind"
    if side == "short":
        if zone in ("extreme_greed", "greed"):
            return "tailwind"
        if zone == "neutral":
            return "neutral"
        return "headwind"
    return "neutral"


def funding_zone(value_pct: float) -> str:
    if value_pct > 0.10:
        return "long_crowded_extreme"
    if value_pct > 0.05:
        return "long_crowded"
    if value_pct < -0.10:
        return "short_crowded_extreme"
    if value_pct < -0.05:
        return "short_crowded"
    return "neutral"


def funding_allows_side(funding_value_pct: float, side: str) -> bool:
    zone = funding_zone(funding_value_pct)
    if side == "long" and zone in ("long_crowded", "long_crowded_extreme"):
        return False
    if side == "short" and zone in ("short_crowded", "short_crowded_extreme"):
        return False
    return True


def funding_modifier(funding_value_pct: float, side: str) -> float:
    zone = funding_zone(funding_value_pct)
    if zone in ("long_crowded_extreme", "short_crowded_extreme"):
        return 0.0
    if side == "long" and zone == "long_crowded":
        return 0.5
    if side == "short" and zone == "short_crowded":
        return 0.5
    return 1.0


def divergence_signal(social_delta_pct: float, oi_delta_pct: float,
                      social_threshold: float = 5.0, oi_threshold: float = 2.0) -> str:
    if abs(social_delta_pct) < social_threshold and abs(oi_delta_pct) < oi_threshold:
        return "no_data"
    if social_delta_pct > social_threshold and oi_delta_pct < -oi_threshold:
        return "bearish_divergence"
    if social_delta_pct < -social_threshold and oi_delta_pct > oi_threshold:
        return "bullish_divergence"
    if (social_delta_pct > social_threshold and oi_delta_pct > oi_threshold) or (
        social_delta_pct < -social_threshold and oi_delta_pct < -oi_threshold
    ):
        return "confirmation"
    return "no_data"


def divergence_modifier(div: str, side: str) -> str:
    if side == "long":
        if div == "bearish_divergence":
            return "downgrade"
        if div == "bullish_divergence":
            return "upgrade"
    elif side == "short":
        if div == "bearish_divergence":
            return "upgrade"
        if div == "bullish_divergence":
            return "downgrade"
    return "none"


def pct_delta(series: pd.Series, periods: int) -> pd.Series:
    prev = series.shift(periods)
    return ((series - prev) / prev.replace(0, np.nan)) * 100
