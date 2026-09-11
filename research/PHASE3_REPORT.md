# Phase 3 — Hypothesis Testing, Strategy Freeze, OOS & Walk-forward

Generated: 2026-09-11T01:13:41+00:00

## Decision: NO VALIDATED EDGE YET

This phase tests the user-specified hypotheses rather than inventing a new strategy. All Phase 3 predictors are restricted to snapshots at S-1 or earlier; post-signal OHLCV is used only for outcomes.

## Data and controls

The archived Phase 2 dataset contains **1136 candidate rows** across **255 tickers** and five candidate start definitions. Confidence intervals use 1,000 deterministic ticker-level bootstrap resamples. P-values are adjusted with Benjamini-Hochberg FDR.

## Start-definition comparison

| Definition | Signals | Tickers | True Explosion | Rapid Move | Gradual | Temporary | No Significant | Median sessions to +70 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| A_10_from_low | 276 | 255 | 18 | 29 | 24 | 82 | 123 | 10.0 |
| B_20_from_low | 273 | 252 | 23 | 24 | 24 | 85 | 117 | 10.0 |
| C_20_in_1_3 | 238 | 222 | 27 | 12 | 11 | 69 | 119 | 3.0 |
| D_rapid_expansion | 202 | 187 | 27 | 8 | 11 | 53 | 103 | 3.0 |
| E_base_breakout | 147 | 140 | 17 | 5 | 8 | 45 | 72 | 3.0 |

## Hypothesis results

| Hypothesis | Signals | Successes | Rate | Lift | Odds ratio | RR | Clustered 95% CI | FDR q |
|---|---:|---:|---:|---:|---:|---:|---|---:|
| H1_RSI_Recovery_Volume_Expansion | 174 | 43 | 0.2471264367816092 | 1.4775559588626739 | 1.8198577140779977 | 1.4775559588626739 | [0.15957283644432843, 0.3433734939759036] | 0.0077465462438276855 |
| H2_RSI_Rising_Base_Price | 282 | 26 | 0.09219858156028368 | 0.5512504665920119 | 0.42730564024390244 | 0.5512504665920119 | [0.050536367601095145, 0.1400140562248996] | 0.0002695512743191398 |
| H3_Oversold_Recovery_Price | 209 | 31 | 0.14832535885167464 | 0.8868295139763284 | 0.8412126351494594 | 0.8868295139763284 | [0.0828642117684922, 0.21782178217821782] | 0.6305873465344461 |
| H4_Volume_Leads_RSI | 62 | 10 | 0.16129032258064516 | 0.9643463497453311 | 0.9551282051282052 | 0.9643463497453311 | [0.04542929292929293, 0.29411764705882354] | 1.0 |

## Freeze and OOS

Train ends **2026-07-02**; validation ends **2026-07-29**. The frozen rule is **H1_RSI_Recovery_Volume_Expansion**. It was selected before OOS was read.

| Split | Signals | Successes | Rate | Lift | Clustered CI |
|---|---:|---:|---:|---:|---|
| train metrics | 105 | 29 | 0.2761904761904762 | 1.585793650793651 | [0.16662844036697247, 0.39475853094274144] |
| validation metrics | 23 | 3 | 0.13043478260869565 | 0.8746803069053709 | [0.0, 0.3480590062111799] |
| oos metrics | 46 | 11 | 0.2391304347826087 | 1.4547101449275364 | [0.06059090909090909, 0.4313836898395722] |

## Interpretation

A result is not treated as a validated edge merely because its in-sample success rate is high. It must survive the temporal OOS split, ticker-clustered uncertainty, and multiple-testing review. If it does not, the correct label remains **NO VALIDATED EDGE YET** and the dashboard must remain paper-monitoring only.

## Limitations

- Historical Float, Short Interest, borrow, spreads, and point-in-time news are not available and are not backfilled with current values.
- Candidate start dates came from Phase 2 discovery. A production signal engine must reproduce the frozen rule from data available at the time.
- Intraday 4H data was not used to create an independent strategy. It should be tested only after the daily rule has an OOS edge.
