# Backtest Report — ETH Rapid Reversal (CMC Skill)

| Field | Value |
|---|---|
| Run (UTC) | 2026-06-18T09:03:59.271914+00:00 |
| Window | 30 days |
| Source | cmc |
| Starting equity | $10,000.00 |
| Final equity | $10,000.00 |
| Peak equity | $10,000.00 |
| Max drawdown | 0.00% |
| Max DD duration | 0 days |
| Daily-loss halts | 0 |
| Funding skips (hostile) | 0 |
| Funding halves (crowded) | 0 |

## Headline Cycle Metrics

| Metric | Value |
|---|---|
| Total Return | 0.00% |
| Annualized Return | 0.00% |
| Sharpe (daily, rf=0) | 0.00 |
| Sortino | 0.00 |
| Calmar | 0.00 |
| Cycles (full trades) | 0 |
| Legs (executions) | 0 |
| Cycle Win Rate | 0.0% |
| Cycle Profit Factor | 0.00 |
| Avg Cycle Win | $0.00 |
| Avg Cycle Loss | $0.00 |
| **Pay-off Ratio** | **0.00** |
| Avg Cycle Hold | 0.0 h |

## Tier-Reached Distribution

How many cycles reached each tier before closing (tier1=first reduce triggered, tier3=after seed, full_close=hit final TP or exit):

```json
{}
```

## Rolling-Compound Distribution

How many adds each cycle had (0 = no adds, 5 = maxed out):

```json
{
  "0": 0,
  "1": 0,
  "2": 0,
  "3": 0,
  "4": 0,
  "5": 0
}
```

## Cycle Side Breakdown

```json
{}
```

## Cycle Tier Breakdown (entry tier)

```json
{}
```

## Leg-Type Breakdown

```json
{}
```

## Exit Reasons

```json
{}
```

## Divergence Distribution (signals evaluated)

```json
{
  "bullish_divergence": 0,
  "bearish_divergence": 0,
  "confirmation": 0,
  "no_data": 0
}
```

## See Also

- `trades.csv` — execution-level log (legs)
- `cycles.csv` — full trade cycles with PnL
- `equity_curve.csv` — bar-by-bar equity
- `equity_curve.png` — equity plot
