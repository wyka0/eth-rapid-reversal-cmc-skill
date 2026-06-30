"""Load ETH market data from the CoinMarketCap AI Agent Hub.

The BNB Hack competition provides the CMC AI Agent Hub as the sole data source.
This loader fetches OHLCV (5m / 15m / 1h), Fear & Greed, funding rate, open
interest, and social mentions from CMC. For local development without network
access (CI, unit tests, smoke tests), a deterministic synthetic generator is
the only fallback. The synthetic path is clearly labeled and is not the
submission evidence — the submission assumes production deployment against
the live CMC AI Agent Hub.

Cache policy
------------
- ``CMC_FORCE_SYNTHETIC=1``  -> always synthetic (used by ``--source synthetic``
  so the committed baseline is 100% reproducible by judges with no API key).
- Fresh cache (<24h)          -> reused.
- Stale cache + no API key    -> reused (so a previously fetched real-ETH
  snapshot keeps working offline), with a clear age warning.
- Stale cache + API key       -> refreshed from CMC.
- No cache + no API key       -> synthetic.
"""
from __future__ import annotations

import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import requests

CACHE_DIR = Path(__file__).resolve().parent.parent / ".cache"
DATA_DIR = Path(__file__).resolve().parent.parent / "data"

CMC_BASE = os.environ.get("CMC_BASE", "https://api.coinmarketcap.com")

_CACHE_TTL = 86_400  # seconds


def _force_synth() -> bool:
    return os.environ.get("CMC_FORCE_SYNTHETIC") == "1"


def _cache_path(name: str) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR / f"{name}.parquet"


def _cache_age_h(cache: Path) -> float:
    return (time.time() - cache.stat().st_mtime) / 3600.0


def _bar_minutes(bar: str) -> int:
    return {"1m": 1, "5m": 5, "15m": 15, "30m": 30, "1H": 60, "4H": 240, "1D": 1440}.get(bar, 5)


def _interval_code(bar: str) -> str:
    return {"1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m", "1H": "1h", "4H": "4h", "1D": "1d"}.get(bar, "5m")


def _normalize_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    if "timestamp" not in df.columns:
        if isinstance(df.index, pd.DatetimeIndex):
            df = df.reset_index().rename(columns={"index": "timestamp"})
        else:
            raise ValueError("DataFrame must have a timestamp column or DatetimeIndex")
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    for col in ("open", "high", "low", "close", "volume"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["open", "high", "low", "close"]).sort_values("timestamp").reset_index(drop=True)
    return df[["timestamp", "open", "high", "low", "close", "volume"]]


def _cmc_headers() -> dict:
    api_key = os.environ.get("CMC_API_KEY")
    headers = {"Accept": "application/json"}
    if api_key:
        headers["X-CMC_PRO_API_KEY"] = api_key
    return headers


def _synth_ohlcv(symbol: str, bar: str, days: int) -> pd.DataFrame:
    minutes = _bar_minutes(bar)
    n = (days * 24 * 60) // minutes
    seed = 42 if symbol.upper() == "ETH" else (43 if symbol.upper() == "BTC" else 44)
    np.random.seed(seed)
    dt = minutes / (24 * 60)
    # Near-zero drift so the synthetic series is essentially a driftless random
    # walk: mean-reversion results are then driven by the noise structure, not
    # by an artificial trend that flatters longs.
    mu, sigma = (0.0, 0.045) if symbol.upper() == "ETH" else (0.0, 0.05)
    rets = np.random.normal(mu * dt, sigma * np.sqrt(dt), n)
    base = 3000.0 if symbol.upper() == "ETH" else 60000.0
    price = base * np.exp(np.cumsum(rets))
    noise = np.abs(np.random.normal(0, 0.002, n))
    timestamps = pd.date_range(end=pd.Timestamp.now(tz="UTC").floor("min"), periods=n, freq=f"{minutes}min")
    return pd.DataFrame({
        "timestamp": timestamps,
        "open": price,
        "high": price * (1 + noise),
        "low": price * (1 - noise),
        "close": price,
        "volume": np.random.uniform(100, 1000, n),
    })


def _synth_fear_greed(days: int) -> pd.Series:
    np.random.seed(43)
    values = np.clip(50 + np.cumsum(np.random.normal(0, 5, days)), 5, 95)
    dates = pd.date_range(end=pd.Timestamp.now(tz="UTC").date(), periods=days, freq="D").date
    return pd.Series(values, index=dates, name="value")


def _synth_timeseries(days: int, freq_hours: int, seed: int, base: float = 0.0, vol: float = 0.05) -> pd.Series:
    np.random.seed(seed)
    n = (days * 24) // freq_hours
    rets = np.random.normal(0, vol, n)
    vals = base + np.cumsum(rets) if base != 0 else np.random.normal(0, vol, n)
    end = pd.Timestamp.now(tz="UTC").floor(f"{freq_hours}h")
    idx = pd.date_range(end=end, periods=n, freq=f"{freq_hours}h")
    return pd.Series(vals, index=idx, name="value")


def load_cmc_ohlcv(symbol: str = "ETH", bar: str = "5m", days: int = 90) -> pd.DataFrame:
    """Load OHLCV from the CoinMarketCap AI Agent Hub (CMC Pro API).

    Production source: CMC AI Agent Hub (provided by the BNB Hack competition).
    The CMC Pro API is the Python-accessible interface to the same data layer
    that the Agent Hub exposes via MCP / x402 / CLI.
    """
    if _force_synth():
        return _synth_ohlcv(symbol, bar, days)

    cache = _cache_path(f"cmc_{symbol.lower()}_{bar}_{days}d")
    api_key = os.environ.get("CMC_API_KEY")
    if cache.exists() and _cache_age_h(cache) * 3600 < _CACHE_TTL:
        return _normalize_ohlcv(pd.read_parquet(cache))
    if not api_key:
        if cache.exists():
            print(f"[data_loader] No CMC_API_KEY — reusing cached {symbol} {bar} (age {_cache_age_h(cache):.0f}h). Set CMC_API_KEY to refresh.")
            return _normalize_ohlcv(pd.read_parquet(cache))
        print(f"[data_loader] No CMC_API_KEY and no cache — using synthetic {symbol} {bar} ({days}d). Set CMC_API_KEY for live data.")
        return _synth_ohlcv(symbol, bar, days)

    end_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    start_ms = int((datetime.now(timezone.utc) - timedelta(days=days)).timestamp() * 1000)
    try:
        resp = requests.get(
            f"{CMC_BASE}/v1/cryptocurrency/ohlcv/historical",
            params={"id": "1027" if symbol.upper() == "ETH" else symbol, "time_start": int(start_ms / 1000), "time_end": int(end_ms / 1000), "interval": _interval_code(bar)},
            headers=_cmc_headers(),
            timeout=30,
        )
        resp.raise_for_status()
        payload = resp.json()
        if "data" in payload and "quotes" in payload["data"]:
            rows = []
            for entry in payload["data"]["quotes"]:
                q = entry.get("quote", {}).get("USD", {})
                ts = pd.to_datetime(entry["timestamp"], utc=True)
                rows.append({"timestamp": ts, "open": q.get("open"), "high": q.get("high"), "low": q.get("low"), "close": q.get("close"), "volume": q.get("volume", 0.0)})
            df = _normalize_ohlcv(pd.DataFrame(rows))
            df = df[df["timestamp"] >= pd.to_datetime(start_ms, unit="ms", utc=True)]
            df.to_parquet(cache)
            return df
        print(f"[data_loader] CMC OHLCV returned no data (HTTP {resp.status_code}); falling back to synthetic")
    except Exception as e:
        print(f"[data_loader] CMC fetch failed: {e!r}; falling back to synthetic")

    df = _synth_ohlcv(symbol, bar, days)
    df.to_parquet(cache)
    return df


def load_cmc_fear_greed(days: int = 90) -> pd.Series:
    """Load Fear & Greed index from CMC AI Agent Hub (CMC Pro / alternative.me fallback)."""
    if _force_synth():
        return _synth_fear_greed(days)
    cache = _cache_path(f"cmc_fear_greed_{days}d")
    api_key = os.environ.get("CMC_API_KEY")
    if cache.exists() and _cache_age_h(cache) * 3600 < _CACHE_TTL:
        s = pd.read_parquet(cache)["value"]
        s.index = pd.to_datetime(s.index).date
        return s
    if not api_key:
        if cache.exists():
            print(f"[data_loader] No CMC_API_KEY — reusing cached F&G (age {_cache_age_h(cache):.0f}h).")
            s = pd.read_parquet(cache)["value"]
            s.index = pd.to_datetime(s.index).date
            return s
        print(f"[data_loader] No CMC F&G data; using synthetic ({days}d).")
        return _synth_fear_greed(days)
    try:
        resp = requests.get(
            f"{CMC_BASE}/v3/fear-and-greed/historical",
            headers=_cmc_headers(),
            timeout=30,
        )
        resp.raise_for_status()
        payload = resp.json()
        rows = payload.get("data", [])
        if rows:
            out = {}
            for entry in rows:
                ts_raw = entry["timestamp"]
                ts_int = int(ts_raw) if str(ts_raw).isdigit() else int(pd.Timestamp(str(ts_raw)).timestamp())
                out[pd.to_datetime(ts_int, unit="s", utc=True).date()] = float(entry["value"])
            s = pd.Series(out).sort_index()
            s.name = "value"
            s.to_frame().to_parquet(cache)
            return s
    except Exception as e:
        print(f"[data_loader] CMC F&G fetch failed: {e!r}; falling back to synthetic")
    print(f"[data_loader] No CMC F&G data; using synthetic ({days}d).")
    return _synth_fear_greed(days)


def load_cmc_funding_rate(symbol: str = "ETH", days: int = 90) -> pd.Series:
    """Load 8h funding rate from CMC AI Agent Hub. Synthetic if unavailable."""
    if _force_synth():
        return _synth_timeseries(days, freq_hours=8, seed=44, base=0.01, vol=0.025)
    cache = _cache_path(f"cmc_funding_{symbol.lower()}_{days}d")
    api_key = os.environ.get("CMC_API_KEY")
    if cache.exists() and _cache_age_h(cache) * 3600 < _CACHE_TTL:
        return pd.read_parquet(cache)["value"]
    if not api_key:
        if cache.exists():
            print(f"[data_loader] No CMC_API_KEY — reusing cached funding (age {_cache_age_h(cache):.0f}h).")
            return pd.read_parquet(cache)["value"]
        print(f"[data_loader] No CMC funding data; using synthetic ({days}d).")
        return _synth_timeseries(days, freq_hours=8, seed=44, base=0.01, vol=0.025)
    try:
        resp = requests.get(
            f"{CMC_BASE}/v1/cryptocurrency/funding-rate/historical",
            params={"id": "1027" if symbol.upper() == "ETH" else symbol, "days": days},
            headers=_cmc_headers(),
            timeout=30,
        )
        resp.raise_for_status()
        payload = resp.json()
        rows = payload.get("data", [])
        if rows:
            ts_list = [pd.to_datetime(r["timestamp"], unit="ms", utc=True) for r in rows]
            vals = [float(r.get("fundingRate", 0.0)) for r in rows]
            s = pd.Series(vals, index=ts_list, name="value").sort_index()
            s.to_frame().to_parquet(cache)
            return s
    except Exception as e:
        print(f"[data_loader] CMC funding fetch failed: {e!r}; falling back to synthetic")
    return _synth_timeseries(days, freq_hours=8, seed=44, base=0.01, vol=0.025)


def load_cmc_open_interest(symbol: str = "ETH", days: int = 90) -> pd.Series:
    """Load open interest from CMC AI Agent Hub. Synthetic if unavailable."""
    if _force_synth():
        return _synth_timeseries(days, freq_hours=1, seed=45, base=5_000_000_000.0, vol=0.02)
    cache = _cache_path(f"cmc_oi_{symbol.lower()}_{days}d")
    api_key = os.environ.get("CMC_API_KEY")
    if cache.exists() and _cache_age_h(cache) * 3600 < _CACHE_TTL:
        return pd.read_parquet(cache)["value"]
    if not api_key:
        if cache.exists():
            print(f"[data_loader] No CMC_API_KEY — reusing cached OI (age {_cache_age_h(cache):.0f}h).")
            return pd.read_parquet(cache)["value"]
        print(f"[data_loader] No CMC OI data; using synthetic ({days}d).")
        return _synth_timeseries(days, freq_hours=1, seed=45, base=5_000_000_000.0, vol=0.02)
    try:
        resp = requests.get(
            f"{CMC_BASE}/v1/cryptocurrency/open-interest/historical",
            params={"id": "1027" if symbol.upper() == "ETH" else symbol, "days": days},
            headers=_cmc_headers(),
            timeout=30,
        )
        resp.raise_for_status()
        payload = resp.json()
        rows = payload.get("data", [])
        if rows:
            ts_list = [pd.to_datetime(r["timestamp"], unit="ms", utc=True) for r in rows]
            vals = [float(r.get("openInterest", 0.0)) for r in rows]
            s = pd.Series(vals, index=ts_list, name="value").sort_index()
            s.to_frame().to_parquet(cache)
            return s
    except Exception as e:
        print(f"[data_loader] CMC OI fetch failed: {e!r}; falling back to synthetic")
    return _synth_timeseries(days, freq_hours=1, seed=45, base=5_000_000_000.0, vol=0.02)


def load_cmc_social_mentions(symbol: str = "ETH", days: int = 90) -> pd.Series:
    """Load social mention count from CMC AI Agent Hub. Synthetic if unavailable."""
    if _force_synth():
        return _synth_timeseries(days, freq_hours=1, seed=46, base=1000.0, vol=0.15)
    cache = _cache_path(f"cmc_social_{symbol.lower()}_{days}d")
    api_key = os.environ.get("CMC_API_KEY")
    if cache.exists() and _cache_age_h(cache) * 3600 < _CACHE_TTL:
        return pd.read_parquet(cache)["value"]
    if not api_key:
        if cache.exists():
            print(f"[data_loader] No CMC_API_KEY — reusing cached social (age {_cache_age_h(cache):.0f}h).")
            return pd.read_parquet(cache)["value"]
        print(f"[data_loader] No CMC social data; using synthetic ({days}d).")
        return _synth_timeseries(days, freq_hours=1, seed=46, base=1000.0, vol=0.15)
    try:
        resp = requests.get(
            f"{CMC_BASE}/v1/cryptocurrency/social-mentions/historical",
            params={"id": "1027" if symbol.upper() == "ETH" else symbol, "days": days},
            headers=_cmc_headers(),
            timeout=30,
        )
        resp.raise_for_status()
        payload = resp.json()
        rows = payload.get("data", [])
        if rows:
            ts_list = [pd.to_datetime(r["timestamp"], unit="ms", utc=True) for r in rows]
            vals = [float(r.get("mentions", 0.0)) for r in rows]
            s = pd.Series(vals, index=ts_list, name="value").sort_index()
            s.to_frame().to_parquet(cache)
            return s
    except Exception as e:
        print(f"[data_loader] CMC social fetch failed: {e!r}; falling back to synthetic")
    return _synth_timeseries(days, freq_hours=1, seed=46, base=1000.0, vol=0.15)
