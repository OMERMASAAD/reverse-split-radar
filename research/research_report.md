# Reverse Split Explosion Radar — Statistical Strategy Discovery

Generated: 2026-09-08T11:52:51+00:00

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

RSI D-1 coverage: 101 successful windows and 1241 controls. Historical OHLCV coverage determines whether earlier snapshots D-20 through D-2 are populated.

| Snapshot | Success mean | Success median | Control mean | Control median |
|---|---:|---:|---:|---:|
| D-20 | 34.97 | 33.80 | 42.22260252274921 | 41.89594767891396 |
| D-15 | 35.92 | 33.13 | 41.835201978040956 | 41.855086528996274 |
| D-10 | 36.52 | 34.65 | 41.745318563020255 | 41.99112304104831 |
| D-7 | 34.70 | 33.40 | 42.08667226947569 | 42.44183348488574 |
| D-5 | 34.66 | 34.05 | 42.199869775993896 | 42.51367432440197 |
| D-4 | 35.21 | 35.17 | 42.01620481497712 | 42.41998478730894 |
| D-3 | 36.26 | 35.56 | 42.110801135803094 | 42.444208333924024 |
| D-2 | 37.82 | 36.94 | 42.128165092450956 | 42.60981047198981 |
| D-1 | 51.09 | 51.39 | 42.01220852402565 | 42.48130163270519 |

### RSI 22–27 test

| RSI D-1 range | Success cases | Control cases | Success rate |
|---|---:|---:|---:|
| <20 | 5 | 62 | 7.5% |
| 20-22 | 1 | 23 | 4.2% |
| 22-25 | 3 | 38 | 7.3% |
| 25-27 | 2 | 24 | 7.7% |
| 27-30 | 7 | 58 | 10.8% |
| 30-35 | 5 | 144 | 3.4% |
| 35-40 | 12 | 150 | 7.4% |
| 40-50 | 13 | 447 | 2.8% |
| 50-+ | 53 | 295 | 15.2% |

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
| +20% | 134 | 35.1% | -4.0% | 0.6441528706125336 | 19.0% |
| +50% | 138 | 13.8% | -3.8% | 0.7000191289419667 | 7.1% |
| +70% | 140 | 12.1% | -2.1% | 0.8350876308301535 | 9.3% |
| +100% | 140 | 9.3% | -1.1% | 0.9167750732670584 | 4.8% |
| +200% | 143 | 3.5% | -0.2% | 0.9870790954004981 | 4.7% |

## Final status

**No final validated STRONG SETUP is declared yet.** The candidate rule is shown for auditability, not adoption. It must survive an independent later sample, clustered confidence intervals, realistic liquidity/slippage, and a pre-registered stop/target policy before being considered a strategy.

## Data limitations

- Historical Float and Short Interest are not available point-in-time and are not used as predictors.
- A success label is event-based (+70% reached); it is not by itself an executable trade return.
- Duplicate windows may belong to the same ticker; future confidence intervals should cluster by ticker.
- Current outputs should not be interpreted as investment advice.
