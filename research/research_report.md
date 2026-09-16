# Reverse Split Explosion Radar — Statistical Strategy Discovery

Generated: 2026-09-16T14:38:37+00:00

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

RSI D-1 coverage: 100 successful windows and 1231 controls. Historical OHLCV coverage determines whether earlier snapshots D-20 through D-2 are populated.

| Snapshot | Success mean | Success median | Control mean | Control median |
|---|---:|---:|---:|---:|
| D-20 | 35.22 | 34.29 | 42.223214819948474 | 41.910570561303224 |
| D-15 | 36.09 | 33.51 | 41.906112953902095 | 41.943600790478165 |
| D-10 | 36.56 | 34.74 | 41.907285589941395 | 42.06825672956141 |
| D-7 | 34.81 | 33.47 | 42.19267197328897 | 42.44183348488574 |
| D-5 | 34.89 | 34.41 | 42.270002913313945 | 42.44183348488574 |
| D-4 | 35.54 | 35.52 | 42.103703112810024 | 42.378115032197464 |
| D-3 | 36.51 | 36.11 | 42.18641486371441 | 42.44183348488574 |
| D-2 | 37.90 | 37.06 | 42.20826836094538 | 42.60234327666866 |
| D-1 | 51.56 | 51.78 | 42.0872912795052 | 42.51502790204361 |

### RSI 22–27 test

| RSI D-1 range | Success cases | Control cases | Success rate |
|---|---:|---:|---:|
| <20 | 5 | 61 | 7.6% |
| 20-22 | 1 | 20 | 4.8% |
| 22-25 | 3 | 32 | 8.6% |
| 25-27 | 2 | 24 | 7.7% |
| 27-30 | 7 | 58 | 10.8% |
| 30-35 | 5 | 147 | 3.3% |
| 35-40 | 11 | 152 | 6.7% |
| 40-50 | 13 | 442 | 2.9% |
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

Rule tested: `drawdown <= -30% AND volume_ratio_20d >= 1.05`. Eligible windows: **141**; train cutoff: **2026-08-10**. Entry is the next available session open, with a conservative -20% stop and target exits.

| Target | Trades | Win rate | Avg return | Profit factor | OOS win rate |
|---|---:|---:|---:|---:|---:|
| +20% | 132 | 36.4% | -3.4% | 0.6849815641149664 | 19.0% |
| +50% | 136 | 14.0% | -3.0% | 0.7562698537979804 | 7.1% |
| +70% | 138 | 12.3% | -1.3% | 0.8964245032091456 | 9.3% |
| +100% | 138 | 9.4% | -0.3% | 0.9804224619351889 | 4.8% |
| +200% | 141 | 3.5% | 0.7% | 1.0517149763993816 | 4.7% |

## Final status

**No final validated STRONG SETUP is declared yet.** The candidate rule is shown for auditability, not adoption. It must survive an independent later sample, clustered confidence intervals, realistic liquidity/slippage, and a pre-registered stop/target policy before being considered a strategy.

## Data limitations

- Historical Float and Short Interest are not available point-in-time and are not used as predictors.
- A success label is event-based (+70% reached); it is not by itself an executable trade return.
- Duplicate windows may belong to the same ticker; future confidence intervals should cluster by ticker.
- Current outputs should not be interpreted as investment advice.
