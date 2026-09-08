# Reverse Split Explosion Radar — Statistical Strategy Discovery

Generated: 2026-09-08T23:31:03+00:00

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
| D-20 | 34.99 | 34.02 | 42.10829052393895 | 41.666230186005876 |
| D-15 | 36.02 | 33.25 | 41.793622699946546 | 41.83394225165591 |
| D-10 | 36.56 | 34.74 | 41.73714367853233 | 41.961311232026084 |
| D-7 | 34.79 | 33.47 | 42.046967341584065 | 42.426488970269695 |
| D-5 | 34.85 | 34.41 | 42.15783481696368 | 42.44146357734298 |
| D-4 | 35.50 | 35.52 | 41.97821691033835 | 42.372222100353284 |
| D-3 | 36.47 | 36.11 | 42.082062116978264 | 42.43090913609734 |
| D-2 | 38.00 | 37.06 | 42.107697048426544 | 42.60065193746438 |
| D-1 | 51.39 | 51.53 | 41.994471829573534 | 42.48130163270519 |

### RSI 22–27 test

| RSI D-1 range | Success cases | Control cases | Success rate |
|---|---:|---:|---:|
| <20 | 5 | 62 | 7.5% |
| 20-22 | 1 | 23 | 4.2% |
| 22-25 | 3 | 38 | 7.3% |
| 25-27 | 2 | 24 | 7.7% |
| 27-30 | 7 | 59 | 10.6% |
| 30-35 | 5 | 148 | 3.3% |
| 35-40 | 12 | 152 | 7.3% |
| 40-50 | 13 | 449 | 2.8% |
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

Rule tested: `drawdown <= -30% AND volume_ratio_20d >= 1.05`. Eligible windows: **143**; train cutoff: **2026-08-11**. Entry is the next available session open, with a conservative -20% stop and target exits.

| Target | Trades | Win rate | Avg return | Profit factor | OOS win rate |
|---|---:|---:|---:|---:|---:|
| +20% | 134 | 35.1% | -4.0% | 0.6441528706125341 | 19.0% |
| +50% | 138 | 13.8% | -3.8% | 0.7000191289419678 | 7.1% |
| +70% | 140 | 12.1% | -2.1% | 0.8350876308301546 | 9.3% |
| +100% | 140 | 9.3% | -1.1% | 0.91677507326706 | 4.8% |
| +200% | 143 | 3.5% | -0.2% | 0.9870790954004997 | 4.7% |

## Final status

**No final validated STRONG SETUP is declared yet.** The candidate rule is shown for auditability, not adoption. It must survive an independent later sample, clustered confidence intervals, realistic liquidity/slippage, and a pre-registered stop/target policy before being considered a strategy.

## Data limitations

- Historical Float and Short Interest are not available point-in-time and are not used as predictors.
- A success label is event-based (+70% reached); it is not by itself an executable trade return.
- Duplicate windows may belong to the same ticker; future confidence intervals should cluster by ticker.
- Current outputs should not be interpreted as investment advice.
