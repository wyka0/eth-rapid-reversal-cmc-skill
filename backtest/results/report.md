# Backtest Report — ETH Rapid Reversal (CMC Skill)

| Field | Value |
|---|---|
| Run (UTC) | 2026-06-30T20:51:50.970764+00:00 |
| Window | 30 days |
| Source | synthetic |
| Starting equity | $10,000.00 |
| Final equity | $10,484.54 |
| Peak equity | $10,753.21 |
| Max drawdown | -3.41% |
| Max DD duration | 8.972222222222221 days |
| Daily-loss halts | 0 |
| Funding skips (hostile) | 45 |
| Funding halves (crowded) | 9 |

## Headline Cycle Metrics

| Metric | Value |
|---|---|
| Total Return | 4.85% |
| Annualized Return | 81.40% |
| Sharpe (daily, rf=0) | 4.73 |
| Sortino | 225.52 |
| Calmar | 23.86 |
| Cycles (full trades) | 20 |
| Legs (executions) | 47 |
| Cycle Win Rate | 70.0% |
| Cycle Profit Factor | 2.32 |
| Avg Cycle Win | $72.58 |
| Avg Cycle Loss | $-73.11 |
| **Pay-off Ratio** | **0.99** |
| Avg Cycle Hold | 0.9 h |

## Exit-Reason Distribution

How many cycles closed via each exit path (trail_sl / sl / ranging_close / macd_rev / time_stop / end_of_data):

```json
{
  "macd_rev": 3,
  "trail_sl": 14,
  "ranging_close": 1,
  "sl": 2
}
```

## Rolling-Compound Distribution

How many adds each cycle had (0 = no adds, 5 = maxed out):

```json
{
  "0": 14,
  "1": 5,
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
    "total_pnl": 577.5401265462425,
    "avg_pnl": 28.877006327312124
  }
}
```

## Cycle Tier Breakdown (entry tier)

```json
{
  "B": {
    "n": 16,
    "total_pnl": 211.66637817050923,
    "avg_pnl": 13.229148635656829
  },
  "C": {
    "n": 4,
    "total_pnl": 365.87374837573316,
    "avg_pnl": 91.46843709393329
  }
}
```

## Leg-Type Breakdown

```json
{
  "close": {
    "n": 20,
    "total_pnl": 577.5401265462425,
    "avg_pnl": 28.877006327312124
  }
}
```

## Divergence Distribution (signals evaluated)

```json
{
  "bullish_divergence": 0,
  "bearish_divergence": 0,
  "confirmation": 0,
  "no_data": 65
}
```

## See Also

- `trades.csv` — execution-level log (legs)
- `cycles.csv` — full trade cycles with PnL
- `equity_curve.csv` — bar-by-bar equity
- `equity_curve.png` — equity plot
