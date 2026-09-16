# Reverse Split Explosion Radar — Statistical Strategy Discovery

Generated: 2026-09-16T01:30:11+00:00

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

RSI D-1 coverage: 101 successful windows and 1247 controls. Historical OHLCV coverage determines whether earlier snapshots D-20 through D-2 are populated.

| Snapshot | Success mean | Success median | Control mean | Control median |
|---|---:|---:|---:|---:|
| D-20 | 35.12 | 34.25 | 42.22819846624683 | 41.947051460583296 |
| D-15 | 36.06 | 33.37 | 41.90156136494968 | 41.969433606877764 |
| D-10 | 36.61 | 34.82 | 41.866159571017626 | 42.06825672956141 |
| D-7 | 34.84 | 33.53 | 42.14981454584849 | 42.44183348488574 |
| D-5 | 34.94 | 34.78 | 42.22172235030211 | 42.44183348488574 |
| D-4 | 35.61 | 35.88 | 42.064171380735765 | 42.378115032197464 |
| D-3 | 36.61 | 36.67 | 42.16486891254069 | 42.44183348488574 |
| D-2 | 38.05 | 37.17 | 42.18522531791291 | 42.60234327666866 |
| D-1 | 51.55 | 51.68 | 42.072991847025875 | 42.51502790204361 |

### RSI 22–27 test

| RSI D-1 range | Success cases | Control cases | Success rate |
|---|---:|---:|---:|
| <20 | 5 | 62 | 7.5% |
| 20-22 | 1 | 23 | 4.2% |
| 22-25 | 3 | 34 | 8.1% |
| 25-27 | 2 | 24 | 7.7% |
| 27-30 | 7 | 58 | 10.8% |
| 30-35 | 5 | 149 | 3.2% |
| 35-40 | 11 | 152 | 6.7% |
| 40-50 | 13 | 445 | 2.8% |
| 50-+ | 54 | 300 | 15.3% |

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

Rule tested: `drawdown <= -30% AND volume_ratio_20d >= 1.05`. Eligible windows: **144**; train cutoff: **2026-08-10**. Entry is the next available session open, with a conservative -20% stop and target exits.

| Target | Trades | Win rate | Avg return | Profit factor | OOS win rate |
|---|---:|---:|---:|---:|---:|
| +20% | 135 | 36.3% | -3.5% | 0.6799701076297143 | 20.9% |
| +50% | 139 | 13.7% | -3.2% | 0.7459185008955314 | 7.0% |
| +70% | 141 | 12.1% | -1.5% | 0.8831104067648238 | 9.1% |
| +100% | 141 | 9.2% | -0.4% | 0.9655432623017343 | 4.7% |
| +200% | 144 | 3.5% | 0.5% | 1.035786244719599 | 4.5% |

## Final status

**No final validated STRONG SETUP is declared yet.** The candidate rule is shown for auditability, not adoption. It must survive an independent later sample, clustered confidence intervals, realistic liquidity/slippage, and a pre-registered stop/target policy before being considered a strategy.

## Data limitations

- Historical Float and Short Interest are not available point-in-time and are not used as predictors.
- A success label is event-based (+70% reached); it is not by itself an executable trade return.
- Duplicate windows may belong to the same ticker; future confidence intervals should cluster by ticker.
- Current outputs should not be interpreted as investment advice.
