# Backtest Report — ETH Rapid Reversal (CMC Skill)

| Field | Value |
|---|---|
| Run (UTC) | 2026-06-30T20:23:50.759923+00:00 |
| Window | 30 days |
| Source | synthetic |
| Starting equity | $10,000.00 |
| Final equity | $10,526.93 |
| Peak equity | $10,795.61 |
| Max drawdown | -3.40% |
| Max DD duration | 2581 days |
| Daily-loss halts | 0 |
| Funding skips (hostile) | 46 |
| Funding halves (crowded) | 9 |

## Headline Cycle Metrics

| Metric | Value |
|---|---|
| Total Return | 5.27% |
| Annualized Return | 90.85% |
| Sharpe (daily, rf=0) | 4.92 |
| Sortino | 246.13 |
| Calmar | 26.74 |
| Cycles (full trades) | 20 |
| Legs (executions) | 48 |
| Cycle Win Rate | 75.0% |
| Cycle Profit Factor | 2.47 |
| Avg Cycle Win | $69.36 |
| Avg Cycle Loss | $-84.09 |
| **Pay-off Ratio** | **0.82** |
| Avg Cycle Hold | 0.8 h |

## Exit-Reason Distribution

How many cycles closed via each exit path (trail_sl / sl / ranging_close / macd_rev / time_stop / end_of_data):

```json
{
  "trail_sl": 15,
  "macd_rev": 2,
  "ranging_close": 1,
  "sl": 2
}
```

## Rolling-Compound Distribution

How many adds each cycle had (0 = no adds, 5 = maxed out):

```json
{
  "0": 13,
  "1": 6,
  "2": 1,
  "3": 0,
  "4": 0,
  "5": 0
}
```

## Cycle Side Breakdown

```json
{
  "short": {
    "n": 20,
    "total_pnl": 619.934776896814,
    "avg_pnl": 30.99673884484069
  }
}
```

## Cycle Tier Breakdown (entry tier)

```json
{
  "B": {
    "n": 15,
    "total_pnl": 229.86814424507702,
    "avg_pnl": 15.324542949671802
  },
  "C": {
    "n": 5,
    "total_pnl": 390.0666326517369,
    "avg_pnl": 78.01332653034737
  }
}
```

## Leg-Type Breakdown

```json
{
  "close": {
    "n": 20,
    "total_pnl": 619.934776896814,
    "avg_pnl": 30.99673884484069
  }
}
```

## Exit Reasons (cycle counts)

```json
{
  "trail_sl": 15,
  "macd_rev": 2,
  "ranging_close": 1,
  "sl": 2
}
```

## Divergence Distribution (signals evaluated)

```json
{
  "bullish_divergence": 0,
  "bearish_divergence": 0,
  "confirmation": 0,
  "no_data": 66
}
```

## See Also

- `trades.csv` — execution-level log (legs)
- `cycles.csv` — full trade cycles with PnL
- `equity_curve.csv` — bar-by-bar equity
- `equity_curve.png` — equity plot
