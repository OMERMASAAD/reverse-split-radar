# Reverse Split Explosion Radar — Statistical Strategy Discovery

Generated: 2026-09-15T01:34:57+00:00

## Executive conclusion

The research universe contains **102 +70% success windows** and **1254 control windows** from the 180-calendar-day universe. This is a discovery study, not a validated live strategy. The key point is that RSI 22–27 is tested rather than assumed.

## Threshold outcomes

| Target | Successful events | Median sessions | Median calendar days |
|---|---:|---:|---:|
| +20% | 102 | — | — |
| +50% | 102 | — | — |
| +70% | 102 | 20.0 | 28.0 |
| +100% | 86 | 23.5 | 31.5 |
| +200% | 49 | 28.0 | 37.0 |

## RSI14 analysis

RSI D-1 coverage: 102 successful windows and 1254 controls. Historical OHLCV coverage determines whether earlier snapshots D-20 through D-2 are populated.

| Snapshot | Success mean | Success median | Control mean | Control median |
|---|---:|---:|---:|---:|
| D-20 | 34.99 | 34.02 | 42.12026726415406 | 41.78383350071807 |
| D-15 | 36.02 | 33.25 | 41.793131690785394 | 41.84958912069446 |
| D-10 | 36.56 | 34.74 | 41.73552058182246 | 42.055026925026986 |
| D-7 | 34.79 | 33.47 | 42.02107515352177 | 42.449589569081354 |
| D-5 | 34.86 | 34.41 | 42.09453191058228 | 42.44146357734298 |
| D-4 | 35.50 | 35.52 | 41.93830141282269 | 42.3990499097532 |
| D-3 | 36.47 | 36.11 | 42.04116060971654 | 42.447424979137665 |
| D-2 | 38.00 | 37.06 | 42.06673767748823 | 42.62166435113546 |
| D-1 | 51.39 | 51.53 | 41.96816449586991 | 42.50975389706697 |

### RSI 22–27 test

| RSI D-1 range | Success cases | Control cases | Success rate |
|---|---:|---:|---:|
| <20 | 5 | 62 | 7.5% |
| 20-22 | 1 | 23 | 4.2% |
| 22-25 | 3 | 38 | 7.3% |
| 25-27 | 2 | 24 | 7.7% |
| 27-30 | 7 | 60 | 10.4% |
| 30-35 | 5 | 151 | 3.2% |
| 35-40 | 12 | 152 | 7.3% |
| 40-50 | 13 | 445 | 2.8% |
| 50-+ | 54 | 299 | 15.3% |

## Feature comparison

Feature statistics, p-values, effect proxies, and median lift are in `statistical_analysis.json`. These are discovery statistics and are not adjusted for multiple testing.

## Candidate combinations

| Combination | N | Successes | Success rate | Coverage |
|---|---:|---:|---:|---:|
| drawdown_30 + volume_1_05 | 144 | 30 | 20.8% | 10.6% |
| rsi_recovering + volume_1_05 | 183 | 29 | 15.8% | 13.5% |
| macd_improving + volume_1_05 | 181 | 27 | 14.9% | 13.3% |
| support_2plus + volume_1_05 | 307 | 43 | 14.0% | 22.6% |
| rsi_22_27 + volume_1_05 | 22 | 3 | 13.6% | 1.6% |

## Candidate next-session backtest

Rule tested: `drawdown <= -30% AND volume_ratio_20d >= 1.05`. Eligible windows: **142**; train cutoff: **2026-08-10**. Entry is the next available session open, with a conservative -20% stop and target exits.

| Target | Trades | Win rate | Avg return | Profit factor | OOS win rate |
|---|---:|---:|---:|---:|---:|
| +20% | 133 | 35.3% | -4.1% | 0.6400116652480052 | 21.4% |
| +50% | 137 | 13.9% | -3.9% | 0.6965189031781966 | 7.1% |
| +70% | 139 | 12.2% | -2.2% | 0.8316571314459035 | 9.3% |
| +100% | 139 | 9.4% | -1.2% | 0.9134188875493316 | 4.8% |
| +200% | 142 | 3.5% | -0.2% | 0.9838285333079212 | 4.7% |

## Final status

**No final validated STRONG SETUP is declared yet.** The candidate rule is shown for auditability, not adoption. It must survive an independent later sample, clustered confidence intervals, realistic liquidity/slippage, and a pre-registered stop/target policy before being considered a strategy.

## Data limitations

- Historical Float and Short Interest are not available point-in-time and are not used as predictors.
- A success label is event-based (+70% reached); it is not by itself an executable trade return.
- Duplicate windows may belong to the same ticker; future confidence intervals should cluster by ticker.
- Current outputs should not be interpreted as investment advice.
