# Phase 2 — First Explosion Start & RSI Timing Discovery

Generated: 2026-09-08T19:55:52+00:00

## Status

**Discovery only.** This phase does not build a trading strategy and does not select Entry, Stop Loss, Take Profit, or Research Score.

## Objective

The purpose is to identify when a rapid move first becomes observable without using the later knowledge that the stock eventually reached +70%. Several event-timing definitions are compared independently. Future prices are used only for outcomes after the signal date.

## Sample and coverage

The current universe contains **359 candidate rows**, **320 tickers with daily OHLCV**, and **1136 generated signal rows** across 5 candidate definitions.

| Definition | Meaning |
|---|---|
| A_10_from_low | First close at least 10% above the lowest close observed up to that date |
| B_20_from_low | First close at least 20% above the lowest close observed up to that date |
| C_20_in_1_3 | First close at least 20% above the close three sessions earlier |
| D_rapid_expansion | +20% over three sessions plus volume ratio 20D at least 1.5 |
| E_base_breakout | Close above prior ten-session high after a narrow base with volume expansion |

## Classification summary

| Class | Rows | Unique tickers | Mean RSI change S vs S-5 | Recovery rate | Mean max return 20 sessions |
|---|---:|---:|---:|---:|---:|
| Temporary Spike | 334 | 156 | 9.622605431940585 | 77.1% | 39.2% |
| No Significant Move | 534 | 203 | 11.004005121858205 | 81.4% | 3.7% |
| Gradual Rise | 78 | 45 | 5.390867847296279 | 78.2% | 261.4% |
| True Explosion | 112 | 57 | 12.146228687695952 | 79.5% | 300.8% |
| Rapid Move | 78 | 46 | 8.582451420114408 | 74.4% | 323.2% |

## RSI timing fields

For every candidate signal, RSI14 is recorded at S, S-1, S-2, S-3, S-4, S-5, S-6, S-7, S-10, S-15, and S-20. The outputs also include mean, median, minimum, maximum, range, changes over each lookback, and a five-session slope.

The key question is not whether RSI is high at D-1 after a move. The key question is whether RSI recovery, RSI slope, price expansion, or volume expansion appears earliest before the candidate start date.

## Outcome design

For each candidate signal date S, outcomes are measured only from S+1 onward over 1, 3, 5, 10, and 20 sessions. Each horizon tests +20%, +50%, +70%, +100%, and +200%. The future outcome is never used to create the signal features.

## Hypotheses for later testing only

The following are hypotheses, not strategies: RSI Recovery + Volume Expansion; RSI Rising + Base + Price Confirmation; Oversold Recovery + Price Confirmation; and Volume Leads RSI. They must be frozen and tested only after this discovery report is reviewed.

## What is not concluded

- No definition is declared the best before comparing coverage, speed, class purity, and robustness.
- No RSI threshold is declared an entry condition.
- No OOS strategy result is produced in this phase.
- Historical Float and Short Interest remain unavailable and are not substituted with current values.
- Repeated observations from the same ticker must be interpreted with stock-level clustering.

## Files

- `explosion_start_cases.csv` and `.json`: candidate signal rows and post-signal outcomes.
- `rsi_timing_analysis.csv`: RSI and indicator snapshots by relative day.
- `rsi_distribution.csv`: RSI bins at candidate signal dates.
- `feature_timing_analysis.csv`: earliest observed indicator conditions in the available lookback grid.
- `success_vs_failure.csv`: class-level comparison summary.
- `hypotheses_phase2.json`: hypotheses reserved for later testing.
- `oos_results.json`: intentionally marked not run because no rules were frozen.

## Limitations

- Signal definitions are candidate event-timing definitions, not trading rules.
- Outcomes begin after Signal Date; future OHLCV is never placed in features.
- Historical Float and Short Interest are unavailable and excluded.
- Rows are clustered by ticker in interpretation; no random row split is used.
