# Sweep + Stability — ETH Rapid Reversal (CMC Skill)

Window: 30d | source: synthetic | equity: $10,000

## 1. Parameter Sweep (defaults neighbourhood, NOT optimised)

| Variant | Return | MaxDD | Sharpe | Cycles | Win% | Pay-off |
|---|---|---|---|---|---|---|
| default | +4.85% | -3.41% | 4.73 | 20 | 70.0% | 0.99 |
| rsi 30/70 | -2.00% | -3.86% | -3.95 | 5 | 40.0% | 0.85 |
| rsi 40/60 | +1.44% | -4.80% | 0.26 | 35 | 62.9% | 0.74 |
| adx 20 | +1.16% | -3.53% | 1.21 | 13 | 61.5% | 0.90 |
| risk 3.0% | +9.69% | -6.38% | 4.74 | 20 | 70.0% | 0.99 |

## 2. Multi-Window Stability

| Window | Return | MaxDD | Sharpe | Cycles | Win% | Pay-off |
|---|---|---|---|---|---|---|
| window 1/2 (4320 bars) | +0.67% | -1.95% | 1.32 | 6 | 66.7% | 0.72 |
| window 2/2 (4320 bars) | +4.85% | -3.41% | 6.92 | 20 | 70.0% | 0.99 |

_A structural edge keeps positive expectancy across most windows; a single lucky window does not._
