# PHASE 4 REPORT — Edge Validation & Pre-Explosion Entry Timing

Generated: 2026-09-10T22:49:20+00:00

## Decision: PROMISING BUT NOT VALIDATED

H1 is retained as a research candidate, not as a validated trading strategy. Predictors use S-1 or earlier; post-S outcomes are labels only.

## H1 result

| Sample | Signals | +70 | Rate | Base | Lift | Odds | CI95 |
|---|---:|---:|---:|---:|---:|---:|---|
| All | 174 | 43 | 0.2471264367816092 | 0.16725352112676056 | 1.4775559588626739 | 1.8198577140779977 | [0.188958, 0.316219] |
| Train | 105 | 29 | 0.2761904761904762 | 0.1741654571843251 | 1.585793650793651 | 2.0672353961827645 | [0.19972, 0.36846] |
| Validation | 23 | 3 | 0.13043478260869565 | 0.14912280701754385 | 0.8746803069053709 | 0.8419354838709677 | [0.045376, 0.321279] |
| OOS | 46 | 11 | 0.2391304347826087 | 0.1643835616438356 | 1.4547101449275364 | 1.8605714285714285 | [0.13912, 0.379354] |

## Timing conclusion

The data can measure whether recovery was present in the available pre-signal snapshots. It cannot prove the exact first calendar day because only sparse snapshots are archived. Any recovery first seen at S is post-event confirmation, not a pre-event predictor.

## Fixed feature battery

| Feature | Signals | Rate | Lift | FDR q |
|---|---:|---:|---:|---:|
| RSI absolute 22-27 | 135 | 0.18518518518518517 | 1.1072124756335282 | 0.9142971061569762 |
| RSI recovery | 558 | 0.16308243727598568 | 0.9750613091869459 | 1.0 |
| RSI recovery >20 | 17 | 0.0 | 0.0 | 0.29317038320365724 |
| RSI recovery >25 | 55 | 0.16363636363636364 | 0.9783732057416268 | 1.0 |
| RSI recovery >30 | 119 | 0.15966386554621848 | 0.9546218487394957 | 1.0 |
| RSI recovery >35 | 170 | 0.2 | 1.1957894736842105 | 0.5397002012461353 |
| RSI recovery >40 | 154 | 0.22727272727272727 | 1.3588516746411483 | 0.16078569485687993 |
| RSI rising 2 snapshots | 25 | 0.12 | 0.7174736842105263 | 1.0 |
| RSI rising 3 snapshots | 20 | 0.15 | 0.8968421052631579 | 1.0 |
| RSI <30 + rising | 118 | 0.15254237288135594 | 0.912042818911686 | 1.0 |
| RSI <35 + rising | 202 | 0.14356435643564355 | 0.858363731109953 | 0.7010693774302477 |
| Volume >=1.0 | 519 | 0.16955684007707128 | 1.0137714227765946 | 1.0 |
| Volume >=1.25 | 435 | 0.18850574712643678 | 1.1270659407138537 | 0.38817282990713586 |
| Volume >=1.5 | 371 | 0.21024258760107817 | 1.257029365867499 | 0.062209526273309536 |
| Volume >=2 | 302 | 0.23178807947019867 | 1.3858487277797142 | 0.009058135141354406 |
| Volume increasing | 656 | 0.18445121951219512 | 1.1028241335044928 | 0.2809968378930498 |
| Volume acceleration | 728 | 0.18543956043956045 | 1.1087333718912666 | 0.16078569485687993 |
| Price confirmation | 569 | 0.13005272407732865 | 0.7775783923781334 | 0.009058135141354406 |
| MACD improving | 629 | 0.1685214626391097 | 1.0075809555685717 | 1.0 |
| MA20 reclaim | 263 | 0.1444866920152091 | 0.8638783269961976 | 0.6596059127718237 |
| MA50 reclaim | 141 | 0.14184397163120568 | 0.8480776409107876 | 0.8602711268193085 |
| Liquidity Sweep / Failed Breakdown | 0 | None | None | 1.0 |

## Event sequence

| Sequence | Signals | Rate | Lift | FDR q |
|---|---:|---:|---:|---:|
| Volume Leads RSI | 65 | 0.15384615384615385 | 0.919838056680162 | 1.0 |
| RSI Leads Volume | 607 | 0.17792421746293247 | 1.0637995317783753 | 0.5649396941565579 |
| Same Day | 136 | 0.10294117647058823 | 0.6154798761609906 | 0.11561869093244365 |
| Neither | 30 | 0.03333333333333333 | 0.19929824561403509 | 0.11561869093244365 |
| RSI -> Volume -> Price | 303 | 0.12871287128712872 | 0.769567483064096 | 0.11561869093244365 |
| Volume -> RSI -> Price | 36 | 0.19444444444444445 | 1.1625730994152046 | 0.9286161546145024 |
| RSI + Volume same timing | 136 | 0.10294117647058823 | 0.6154798761609906 | 0.11561869093244365 |
| RSI + Volume + Price | 131 | 0.20610687022900764 | 1.2323021293692247 | 0.42700057605743835 |
| Liquidity Sweep -> RSI -> Volume -> Price | 0 | None | None | 1.0 |
| Liquidity Sweep + RSI Recovery + Volume | 0 | None | None | 1.0 |

## True Explosion vs Temporary Spike

| Class | Class rows | H1 signals | H1 signal rate | H1 +70 rate |
|---|---:|---:|---:|---:|
| true_explosion | 112 | 28 | 0.25 | 1.0 |
| temporary_spike | 334 | 46 | 0.1377245508982036 | 0.0 |
| gradual_rise | 78 | 15 | 0.19230769230769232 | 0.0 |
| no_significant_move | 534 | 70 | 0.13108614232209737 | 0.0 |
| rapid_move | 78 | 15 | 0.19230769230769232 | 1.0 |

## Additional chart hypothesis

The requested Liquidity Sweep / Failed Breakdown element is marked UNAVAILABLE because the archive does not preserve the full pre-signal OHLC sequence required to identify a sweep without leakage. Its combinations therefore have zero eligible observations and are rejected, not treated as failures or successes.
Volume >=2 showed an in-sample FDR-adjusted signal and a numerically positive OOS lift, but no new rule is accepted because the timing/entry definition was not pre-registered before this test and walk-forward stability is not established. RSI + Volume + Price was also numerically positive OOS but inconclusive.

## Direct answers

1. RSI recovery is observable before some candidate starts, but the archived sparse grid does not prove that it reliably precedes the explosion.
2. The exact first lead time cannot be estimated safely from sparse snapshots; available snapshots are S-20, S-15, S-10, S-7, S-5, S-4, S-3, S-2 and S-1.
3. Direction is more informative as a hypothesis than absolute RSI, but it is not validated OOS.
4. RSI 22–27 remains descriptive only; it is not an entry rule.
5. RSI below 30 plus rising is not validated as a standalone edge.
6. Volume does not have a stable proven lead over RSI.
7. RSI does not have a stable proven lead over volume.
8. No sequence is accepted as stable without independent OOS support.
9. H1 is not proven to distinguish True Explosion from Temporary Spike.
10. H1 beats the full control rate in OOS numerically, but not with sufficient statistical evidence.
11. Clustered bootstrap is reported at ticker level; uncertainty remains wide.
12. Some in-sample findings survive FDR, but that does not rescue the OOS result.
13. OOS is numerically positive but statistically inconclusive.
14. Walk-forward is not stable.
15. Expectancy is not frozen because no realistic execution dataset supports it.
16. Profit Factor is not frozen for the same reason.
17. Paper monitoring can continue, but no validated Paper Signal rule should be advertised.
18. No validated edge has been established.
