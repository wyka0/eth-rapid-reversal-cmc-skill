# ETH Rapid Reversal — CMC Skill (BNB Hack Track 2)

A backtestable crypto trading strategy delivered as a [CoinMarketCap (CMC) Skill](https://coinmarketcap.com/api/agent) for the [**BNB Hack: AI Trading Agent Edition**](https://dorahacks.io/hackathon/bnbhack-twt-cmc/detail) — **Track 2: Strategy Skills**.

## What This Skill Does

Generates long and short entry/exit signals on **ETH/USDC** (and other CMC-listed pairs) using a **multi-indicator confluence** model:

- **RSI(14)** overbought/oversold mean-reversion
- **MACD(12,26,9)** histogram turn + zero-line cross for momentum confirmation
- **Fear & Greed Index** regime filter (F&G < 35 supports longs, > 65 supports shorts)
- **Funding rate** guard (reduces or skips entries in crowded-side regimes)
- **Social heat vs. on-chain OI divergence** tier modifier
- **ADX(14)** ranging auto-de-risk (close seed + halt entries when ADX < 15)
- **Trailing stop** exit (0.3% trail, activates at +0.5% ROE) — locks in asymmetric pay-off
- **Hard SL** at -1.0% ROE (only matters before trail activates)
- **15x base leverage**, rolling compound up to 5 profit-funded scale-ins
- **Daily loss limit** -5% of starting equity; **DD circuit breaker** at -10%

## Data Source (sole dependency)

The BNB Hack competition provides the **CoinMarketCap AI Agent Hub** as the data layer. This skill fetches all data from CMC — OHLCV, Fear & Greed, funding rate, open interest, and social mentions — via the CMC Pro API (the Python-accessible interface to the same data that the Agent Hub exposes via MCP / x402 / CLI).

**No other data sources are used.** For local development without a CMC key, a deterministic synthetic generator is the only fallback (clearly labeled, not used for submission evidence).

```python
CMC_BASE = "https://api.coinmarketcap.com"  # the CoinMarketCap Pro API
```

## Quick Start

Works on **Windows (PowerShell)**, **macOS**, and **Linux (bash)**. All commands use `python -m` to avoid PATH issues.

```bash
# 0. Clone the repo and enter the skill directory
git clone https://github.com/wyka0/eth-rapid-reversal-cmc-skill.git
cd eth-rapid-reversal-cmc-skill

# 1. Install dependencies
pip install -r requirements.txt

# 2. Set CMC API key (required for live data; without it, falls back to synthetic)
#    Linux / macOS (bash):
export CMC_API_KEY=your_key_here
#    Windows (PowerShell):
#    $env:CMC_API_KEY = "your_key_here"

# 3. Run a 30-day backtest on ETH/USDC
python backtest/run_backtest.py --days 30 --equity 10000

# 4. Run unit tests (use python -m pytest to avoid PATH issues)
python -m pytest tests/ -v
```

If `pytest` is installed system-wide, `pytest tests/ -v` also works. The `python -m pytest` form is the safest cross-platform option.

If `CMC_API_KEY` is not set, the backtest falls back to a deterministic synthetic ETH price series (clearly labeled in output). **The submission assumes production deployment against the live CMC AI Agent Hub.**

## Backtest Output

Running the backtest produces four artifacts in `backtest/results/`:

| File | Content |
|---|---|
| `trades.csv` | One row per execution leg (Open, Add, Close) with entry/exit prices, PnL, fills |
| `cycles.csv` | One row per full trade cycle with cycle-level PnL, hold time, add count, exit reason |
| `equity_curve.csv` | Bar-by-bar equity series |
| `equity_curve.png` | Equity plot |
| `report.md` | Full performance report with all metrics, tier breakdowns, exit-reason distribution |

## Backtest Parameters (defaults)

| Parameter | Value | Rationale |
|---|---|---|
| Pair | ETH/USDC | Highest CMC coverage |
| Timeframe | 5m signal / 15m trend / 1h context | Matches ETH intraday vol |
| RSI period | 14 | Standard |
| RSI oversold / overbought | 35 / 65 | Calibrated for ~1-2 trades/day activity |
| MACD | 12, 26, 9 | Standard |
| ADX threshold | 15 | Lets weaker trends in; immediate exit on <15 |
| Base leverage | 15x | Calibrated for ETH/USDC perpetual |
| Stop loss | -1.0% ROE | Asymmetric single-leg RR |
| Trailing stop | 0.3% trail from high water mark | Activates at +0.5% ROE |
| Fear & Greed tailwind | <35 longs, >65 shorts | |
| Funding extreme | >0.10%/8h skip, >0.05% halve | |
| Risk per trade | 1.5% of equity | |
| Daily loss limit | -5% | Halt until next UTC day |
| DD circuit breaker | -10% peak-to-trough | Halve leverage for next 10 trades |
| Rolling compound max | 5 additions | Profit-funded scale-ins |

## Repo Layout

```
eth-rapid-reversal/
├── SKILL.md                    # the strategy spec (this is the CMC Skill)
├── README.md                   # you are here
├── LICENSE                     # MIT
├── requirements.txt
├── backtest/
│   ├── indicators.py           # RSI / MACD / ADX / EMA / BB / volume (pure pandas)
│   ├── data_loader.py          # CMC AI Agent Hub fetch (sole data source)
│   ├── engine.py               # walk-forward simulator with trailing stop + rolling compound
│   ├── metrics.py              # Sharpe / DD / cycle metrics
│   ├── run_backtest.py         # CLI entry — produces results/ output
│   └── results/                # generated artifacts
├── notebooks/
│   └── walkthrough.ipynb       # signal walkthrough on a single day
└── tests/
    └── test_indicators.py      # 16 unit tests
```

## Honest Limits

- **Backtest calibration is sample-dependent**: the published defaults (RSI 35/65, ADX 15, trailing 0.3% at +0.5% activation, 15x leverage) are reasonable starting points. The 5m ETH market's signal-to-noise ratio is unforgiving, and a 30d backtest over the last 30 days can show mixed results depending on the regime. A real deployment requires a multi-window parameter sweep before claiming the strategy is calibrated.
- **The strategy is a spec, not a profitable out-of-the-box bot**: implementation quality and parameter calibration matter as much as the signal logic. The trailing compound + multi-indicator confluence is the *edge design*, but the specific RSI/MACD/ADX thresholds need to be tuned to the live volatility regime.
- **CMC test API key limitations**: the free CMC Pro API tier has restricted access to historical OHLCV. For a complete production deployment, the CMC Agent Hub (via MCP / x402 / CLI) provides the full data layer. The `data_loader.py` falls back to deterministic synthetic data when OHLCV is not available, with clear console warnings.
- **Asymmetric design depends on pay-off > 1**: if win rate falls below ~30% on real data, the strategy loses money even with the trailing compound + multi-indicator design. The mechanism assumes most winners offset most losers; in a regime where every signal is wrong, no amount of compounding saves it.
- **Rolling compound amplifies both wins and losses**: a 5×-compounded loser is 5× worse than a single-leg loser. The -10% DD circuit breaker and ADX-based ranging exit are the primary guards.
- **Backtest assumes fills at SL/TP within bar** (conservative); live fills can be worse on thin books.
- Past performance of any parameter set is not a guarantee of forward results.

## Design Rationale (Why This Works)

The strategy's edge comes from the **interaction** between three design choices:

1. **Multi-indicator confluence (RSI + MACD + F&G + divergence)** fires on enough signals to capture most of the day's mean-reversion opportunities while filtering out the worst noise.

2. **Trailing stop exit** captures the asymmetric pay-off. The stop trails the high water mark by 0.3% once profit exceeds 0.5%. This locks in gains on winners while letting them run. A fixed TP at any level either exits too early (leaving money on the table) or is missed entirely.

3. **Auto risk reduction in ranging markets** is the loss cap. When ADX drops below 15, the strategy stops opening new positions and force-closes any open position's seed. This converts what would be a slow bleed in choppy markets into small, contained losses.

4. **Rolling compound on winners** is the force multiplier. When a position is in profit and momentum confirms, the strategy re-deploys unrealized PnL as additional margin (up to 5× the original size). This turns a +1.5% move into a +1.5% move on 1.4× the size = +2.1% effective on the original capital.

The net result, in a well-calibrated regime, is a pay-off ratio > 1 (wins bigger than losses on average) which, combined with reasonable win rate, produces a positive expected value per trade.

## BNB Hack Submission

- **Competition**: [BNB Hack: AI Trading Agent Edition](https://dorahacks.io/hackathon/bnbhack-twt-cmc/detail)
- **Track**: 2 — Strategy Skills ($6,000 prize pool, 3 winners)
- **Data layer**: CoinMarketCap AI Agent Hub (provided by the competition)
- **Stack**: This skill (spec + backtest) is production-ready for the CMC AI Agent Hub and can be wrapped by the BNB AI Agent SDK for live execution
- **Deadline**: June 21, 2026

## License

MIT — see [LICENSE](LICENSE).
