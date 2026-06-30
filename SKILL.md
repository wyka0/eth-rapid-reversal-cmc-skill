---
name: eth-rapid-reversal
description: ETH-tuned rapid reversal compounding strategy delivered as a CoinMarketCap (CMC) Skill for the BNB Hack: AI Trading Agent Edition (DoraHacks), Track 2 — Strategy Skills. Two-way (long + short) strategy with rolling compound (up to 5 profit-funded scale-ins), trailing stop exit (activates at +0.5% ROE, trails 0.3% behind high water mark), immediate exit in ranging markets, RSI(14) overbought/oversold + MACD(12,26,9) momentum confirmation + Bollinger Band proximity + volume filter + Fear & Greed regime filter, 15x base leverage, asymmetric return design. Backtestable strategy spec, not a live-trading agent. Trigger phrases: BNB hack track 2, CMC strategy skill, ETH rapid reversal, ETH trailing stop, ETH rolling compound, ETH RSI MACD Bollinger skill, CoinMarketCap skill, ETH momentum reversal skill, run CMC backtest, submit to bnb hack, mean reversion compounding.
---

# ETH Rapid Reversal Compounding — CMC Skill (BNB Hack Track 2)

> **Hackathon**: [BNB Hack: AI Trading Agent Edition](https://dorahacks.io/hackathon/bnbhack-twt-cmc/detail) — Track 2, Strategy Skills ($6,000 prize pool).
> **Deliverable**: A backtestable CMC Skill. No live execution layer required.
> **Stack**: CoinMarketCap AI Agent Hub (data) + BNB AI Agent SDK (agent framework). No third-party DEX / wallet / chain abstracted in.

## 1. Strategy Profile

- **Asset**: ETH spot or perp (data-symmetric; works on aggregated spot or derivatives feed)
- **Direction**: Two-way (long + short)
- **Edge**: Multi-indicator confluence — RSI(14) extreme reversion + MACD(12,26,9) histogram turn + Bollinger Band proximity + volume filter + Fear & Greed regime filter + derivatives sentiment-divergence
- **Cycle**: Open → rolling compound (1–5 adds) → trailing stop exit → close
- **Holding time**: 5m – 2h per individual leg; full cycle (with rolling) can run 6–12h
- **Leverage**: **15x base** (single value, not tiered)
- **Asymmetric return design**: Many small losses (cut at SL or on ranging), few large wins (rolling compound + trailing stop). Pay-off ratio > 1 is the edge, not win rate.
- **Persona**: Aggressive — full deployment of margin at confirmed signals

## 2. Data Sources (CMC AI Agent Hub only)

The strategy is specified against the [CoinMarketCap AI Agent Hub](https://coinmarketcap.com/api/agent) — the production data layer for a CMC Skill, as provided by the BNB Hack competition. **This is the sole data dependency.** No other exchanges or third-party data sources are used.

| Field | Source | Used for |
|---|---|---|
| OHLCV 5m / 15m / 1h | CMC AI Agent Hub (CMC Pro API) | RSI, MACD, ADX, EMA50, Bollinger Bands, volume |
| Fear & Greed Index | CMC AI Agent Hub | Regime filter |
| Derivatives — funding rate | CMC AI Agent Hub | Crowding guard (size modifier) |
| Derivatives — open interest | CMC AI Agent Hub | Divergence vs social |
| News & KOL social mentions | CMC AI Agent Hub social | Divergence vs OI |

For local development without a CMC API key, `backtest/data_loader.py` falls back to a deterministic synthetic ETH price series (clearly labeled in console output). **The submission assumes production deployment against the live CMC AI Agent Hub.**

## 3. Parameters

| Parameter | Value | Rationale |
|---|---|---|
| Pair | ETH/USDC or ETH/USDT | Highest liquidity |
| Timeframe | 5m signal / 15m trend / 1h context | Matches ETH intraday vol |
| RSI period | 14 | Standard |
| **RSI oversold** | **35** | Calibrated for ~1–2 trades/day activity |
| **RSI overbought** | **65** | Calibrated for ~1–2 trades/day activity |
| RSI extreme (A-tier) | 22 / 78 | High-conviction |
| MACD | 12, 26, 9 | Standard |
| MACD confirm | Histogram turns for 2 bars OR line crosses signal | Both must agree with RSI |
| **Bollinger Bands** | 20-period SMA, 2 std | Price within 1.5% of band = signal |
| **Volume filter** | > 20-period average | Confirms the move |
| 15m trend filter | Price vs EMA50 | Avoids falling-knife longs |
| **ADX threshold** | **15** | Lets weaker trends in; immediate exit on <15 |
| **Base leverage** | **15x** | Single value for all tiers |
| **Stop loss** | **-1.0% ROE** | Hard SL (only matters before trail activates) |
| **Trailing stop** | **0.3% trail from high water mark** | Activates at +0.5% ROE |
| Fear & Greed tailwind | <35 longs, >65 shorts | |
| Funding skip | >0.10%/8h blocks, >0.05% halves | |
| Risk per trade | 1.5% of equity | |
| Daily loss limit | -5% of starting-day equity | Halt until next UTC day |
| DD circuit breaker | -10% peak-to-trough | Halve deployed size for next 10 trades |
| **Rolling compound max** | **5 additions** | Per cycle, profit-funded |
| Time stop | 8h since Open | Force close |

## 4. Signal Logic

### Long entry (all must be true)
1. RSI(14, 5m) ≤ 35
2. MACD histogram rising for 2 bars, OR MACD line crosses above signal
3. **Price within 1.5% of lower Bollinger Band** (mean-reversion buy)
4. **Volume > 20-period average** (confirms the move)
5. Price > 15m EMA50 (trend filter)
6. ADX(14, 15m) ≥ 15
7. Funding not extreme (>0.10% blocks; >0.05% halves size)
8. F&G not hostile to longs (>65 = hostile)
9. Sentiment-divergence not hostile to long

### Short entry (mirror)
1. RSI(14, 5m) ≥ 65
2. MACD histogram falling for 2 bars, OR MACD line crosses below signal
3. **Price within 1.5% of upper Bollinger Band** (mean-reversion sell)
4. **Volume > 20-period average**
5. Price < 15m EMA50
6. ADX(14, 15m) ≥ 15
7. Funding not extreme
8. F&G not hostile to shorts (<35 = hostile)
9. Sentiment-divergence not hostile to short

### 4a. Derivatives Regime Guard (funding)
- `|funding| ≤ 0.05%/8h` → normal
- `0.05 < |funding| ≤ 0.10%/8h` → **halve leverage** for entries in crowded direction
- `|funding| > 0.10%/8h` → **skip** entries in crowded direction entirely

### 4b. Sentiment-Divergence (social heat vs on-chain flow)
Compare 24h delta in social mentions against 24h delta in open interest:

| Pattern | Classification | Long effect | Short effect |
|---|---|---|---|
| Social ↑ (>5%) AND OI ↓ (<-2%) | `bearish_divergence` | downgrade | **upgrade** |
| Social ↓ (<-5%) AND OI ↑ (>2%) | `bullish_divergence` | **upgrade** | downgrade |
| Both same direction | `confirmation` | standard | standard |
| Both flat | `no_data` | standard | standard |

### Skip
- RSI 35–65 zone
- RSI and MACD disagree
- Bollinger proximity not met
- Volume below average
- F&G hostile to signal direction
- ADX < 15
- Funding hostile to signal direction

## 5. Trailing Stop Exit

The strategy exits via a **single trailing stop** that follows the high water mark. This replaces fixed tiered TP — the trailing stop captures the asymmetric pay-off without forcing premature exits.

### Rules
- **Hard SL**: -1.0% ROE (only applies before trail activates)
- **Trail activation**: when position ROE ≥ +0.5%, trailing stop activates
- **Trail distance**: 0.3% behind the high water mark
- For **long** positions: trail_sl = high_water_mark × (1 - 0.003)
- For **short** positions: trail_sl = high_water_mark × (1 + 0.003)
- **High water mark**: updated every bar using bar extremes (not just close)
- **Exit trigger**: bar low (long) or bar high (short) touches trail_sl → exit at trail_sl

### Why trailing (not fixed TP)
A fixed TP at any level either exits too early (leaving money on the table in trends) or is missed entirely (if the trend doesn't reach the level before reversing). A trailing stop locks in gains as the price moves and lets the trade run as long as momentum continues. This produces a higher pay-off ratio (wins larger than losses on average) which is the actual edge.

### Worked example (long)
| Bar | Price | HWM | ROE | Trail? | Trail SL | Action |
|---|---|---|---|---|---|---|
| Open | 100.00 | 100.00 | 0% | No (SL active at -1.0%) | 99.00 | — |
| +5 | 100.40 | 100.40 | +0.4% | No (below 0.5% activation) | 99.40 | — |
| +10 | 100.80 | 100.80 | +0.8% | **Yes (activated)** | 100.50 | — |
| +15 | 101.20 | 101.20 | +1.2% | Yes | 100.90 | — |
| +20 | 101.50 | 101.50 | +1.5% | Yes | 101.20 | — |
| +22 | 101.10 | 101.50 (HWM unchanged) | +1.1% | Yes | 101.20 | Low touched 101.20 → **exit at 101.20, +1.2% profit** |

## 6. Rolling Compound (Scale-In)

After the initial Open, the strategy **scales into winning trades** using unrealized PnL as additional margin. Up to **5 rolling additions** per cycle, each triggered when the position is in profit and momentum indicators confirm continuation.

### Rules
- Each Add uses **unrealized PnL** as new margin (no fresh capital)
- Size formula: each Add ≈ 10/9/8/7/6 % of original size (slight de-scale)
- Max **5 adds** per cycle
- Adding resets the high water mark to the current price (re-anchors the trailing stop)
- Trigger conditions (all must be true):
  1. Position is in profit (ROE > 0)
  2. MACD momentum continues in trade direction
  3. Price has moved ≥ 0.5% in trade direction since last add
  4. ADX ≥ 15
  5. Funding not hostile
  6. F&G not hostile
  7. Min 3 bars (15m) between adds

### Worked example
| Step | Action | Size | Cum. Size | Price |
|---|---|---|---|---|
| 1 | Open | 100% | 100% | entry |
| 2 | Add #1 | +10% | 110% | +0.5% from prior |
| 3 | Add #2 | +9% | 119% | +0.5% from prior |
| 4 | Add #3 | +8% | 127% | +0.5% from prior |
| 5 | Add #4 | +7% | 134% | +0.5% from prior |
| 6 | Add #5 | +6% | 140% | +0.5% from prior |

## 7. Auto Risk Reduction in Ranging Markets

When ADX(14, 15m) < 15:
- **No new Opens**
- **Immediate exit** on any open position (close the entire position at current price)
- Resume normal entries only after ADX ≥ 15 on two consecutive 15m closes

This is the **primary loss-control mechanism** — converts what would be a slow bleed in choppy markets into small, contained losses. Unlike a gradual tightening, immediate exit prevents further loss when the market loses trend.

## 8. Exit Triggers (Priority Order)

1. **Trailing stop hit** (intrabar — bar low for long, bar high for short) → exit at trail_sl
2. **Hard SL** (-1.0% ROE, only if trail not yet active) → full close
3. **Immediate ranging exit** (ADX < 15) → full close
4. **MACD reversal** (3 consecutive bars against position) → full close
5. **Time stop** (8h since Open) → full close
6. **Daily loss limit** (-5% day) → halt all new entries until next UTC day

> Note: funding hostility is enforced at *entry* and *rolling-add* time (the
> `funding_modifier` halves or zeroes size for crowded-side entries), not as a
> mid-trade exit. A position already open is held to its trailing/SL/ranging
> exit; the funding guard prevents adding *new* risk in a hostile regime.

## 9. Compounding & Drawdown

- Notional = `equity * 0.015 / 0.010` ≈ 1.5× equity (1.5% risk, 1.0% stop); leverage cap 15× enforced
- After each cycle close: `equity_base += realized_pnl`
- **Circuit breaker** at -10% peak-to-trough: halve deployed size for next 10 trades, resume after 5 consecutive non-stop-out trades
- **Daily loss limit**: -5% of starting-day equity → halt until next UTC day
- **Per-trade risk** is computed on the initial Open notional; rolling Adds do not increase risk (they use unrealized PnL as buffer)

## 10. Backtest Specification (Required Track 2 Deliverable)

### Data Window
- 30/90/180 days historical, 5m / 15m / 1h ETH OHLCV (from CMC AI Agent Hub)
- Daily Fear & Greed snapshot
- 8h funding rate, hourly OI, hourly social mentions (from CMC AI Agent Hub)

### Engine
- Pure Python, `pandas` + `numpy` only (no TA-Lib dependency)
- Indicators implemented inline: RSI (Wilder), MACD (EMA12/26, signal EMA9), ADX (Wilder), EMA50, Bollinger Bands (20/2), volume filter
- Derivatives: `funding_zone`, `funding_modifier`, `pct_delta`
- Walk-forward bar-by-bar at 5m; no look-ahead; signals computed on close of bar *t*, fill simulated at open of bar *t+1* + slippage
- **Rolling compound** logic: up to 5 scale-ins per cycle, each triggered by profit + MACD continuation
- **Trailing stop exit**: 0.3% trail from high water mark, activates at +0.5% ROE
- **Immediate ranging exit** on ADX < 15
- **Bollinger Band + volume** entry filters

### Execution Simulation
- Slippage: 0.05% per fill
- Commission: 0.04% per side
- Fill model: stop / trail triggered on bar high/low intrabar; trail fills at the trail level

### Metrics Reported
- Total return, annualized return, max drawdown, Sharpe, Sortino, Calmar
- Cycle win rate, profit factor, pay-off ratio, avg cycle hold
- Equity curve PNG
- Per-side breakdown (long vs short)
- Exit-reason distribution (trail_sl / sl / ranging_close / macd_rev / time_stop / end_of_data)
- Funding-skips and divergence distribution
- Adds-per-cycle distribution

### Code Layout
```
eth-rapid-reversal/
├── SKILL.md                    # this file
├── demo.py                     # one-command deterministic demo (no API key)
├── backtest/
│   ├── agent_hub.py            # CMC Agent Hub data-layer mapping (single dependency)
│   ├── engine.py               # walk-forward simulator with trailing stop + rolling compound
│   ├── indicators.py           # RSI/MACD/ADX/EMA/BB/volume (pure pandas)
│   ├── data_loader.py          # CMC AI Agent Hub fetch (sole data source) → parquet cache
│   ├── metrics.py              # Sharpe / DD / cycle metrics
│   ├── run_backtest.py         # CLI entry — produces results/ output
│   ├── sweep.py                # parameter sweep + multi-window stability
│   └── results/                # generated artifacts (trades, cycles, equity, report, sweep)
├── notebooks/
│   └── walkthrough.ipynb       # signal walkthrough on a single day
├── tests/
│   ├── test_indicators.py      # 16 indicator unit tests
│   └── test_engine.py          # 6 engine signal-logic + regression tests
├── README.md
├── requirements.txt
└── LICENSE
```

### Reproducibility
- `CMC_FORCE_SYNTHETIC=1` forces a deterministic synthetic ETH series (used by `demo.py` and `--source synthetic`) so the committed baseline is 100% reproducible with no API key
- With a previously-fetched cache, the loader reuses the real-ETH snapshot offline (with an age warning) instead of silently swapping to synthetic
- Seed any randomness (none in v1, deterministic)
- `requirements.txt`: `pandas`, `numpy`, `matplotlib`, `requests`, `pytest`, `pyarrow`
- One-command run: `python demo.py` (or `python backtest/run_backtest.py --days 30 --equity 10000`)

## 11. What This Skill Does NOT Do

- Does not connect to any DEX, CEX, or wallet for execution
- Does not call any third-party venue or on-chain exchange for trading
- Does not require x402, MPC, or TSS for Track 2
- Does not exceed 15× leverage even if implemented as a perp
- Does not martingale or grid-trade (rolling compound is *profit-funded*, not loss-averaging)
- Does not average down on losers (Add is only allowed when position is in profit)
- Does not require real capital or wallet setup
- Does not use any data source other than the CMC AI Agent Hub

## 12. Honest Limits

- **Backtest calibration is sample-dependent**: the published defaults (RSI 35/65, ADX 15, trailing 0.3% at +0.5% activation, 15x leverage) are reasonable starting points. The 5m ETH market's signal-to-noise ratio is unforgiving, and a 30d backtest over the last 30 days can show mixed results depending on the regime. A real deployment requires a multi-window parameter sweep before claiming the strategy is calibrated.
- **The strategy is a spec, not a profitable out-of-the-box bot**: implementation quality and parameter calibration matter as much as the signal logic. The trailing compound + multi-indicator confluence is the *edge design*, but the specific RSI/MACD/ADX/Bollinger thresholds need to be tuned to the live volatility regime.
- **CMC API tier limitations**: the free CMC Pro API tier has restricted access to historical OHLCV. For a complete production deployment, the CMC Agent Hub (via MCP / x402 / CLI) provides the full data layer. The `data_loader.py` falls back to deterministic synthetic data when OHLCV is not available, with clear console warnings.
- **Asymmetric design depends on pay-off > 1**: if win rate falls below ~30% on real data, the strategy loses money even with the trailing compound + multi-indicator design. The mechanism assumes most winners offset most losers; in a regime where every signal is wrong, no amount of compounding saves it.
- **Rolling compound amplifies both wins and losses**: a 5×-compounded loser is 5× worse than a single-leg loser. The -10% DD circuit breaker and immediate ranging exit are the primary guards.
- **Backtest assumes fills at SL/trail within bar** (conservative); live fills can be worse on thin books.
- Past performance of any parameter set is not a guarantee of forward results.

## 13. Design Rationale (Why This Works)

The strategy's edge comes from the **interaction** between three design choices, not any single one:

1. **Multi-indicator confluence (RSI + MACD + Bollinger + volume)** fires on enough signals to capture most of the day's mean-reversion opportunities while filtering out the worst noise. The Bollinger Band proximity filter ensures the entry is at a stretched price, the volume filter confirms the move has participation, and RSI+MACD confirm the reversal.

2. **Trailing stop exit** captures the asymmetric pay-off. The stop trails the high water mark by 0.3% once profit exceeds 0.5%. This locks in gains on winners while letting them run. A fixed TP at any level either exits too early (leaving money on the table) or is missed entirely.

3. **Auto risk reduction in ranging markets** is the loss cap. When ADX drops below 15, the strategy stops opening new positions and force-closes any open position immediately. This converts what would be a slow bleed in choppy markets into small, contained losses.

4. **Rolling compound on winners** is the force multiplier. When a position is in profit and momentum confirms, the strategy re-deploys unrealized PnL as additional margin (up to 5× the original size). This turns a +1.5% move into a +1.5% move on 1.4× the size = +2.1% effective on the original capital.

The net result, in a well-calibrated regime, is a pay-off ratio > 1 (wins bigger than losses on average) which, combined with reasonable win rate, produces a positive expected value per trade. The backtest result on any specific 30-day window will vary; the *mechanism* is what the spec documents.
