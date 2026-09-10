# STRATEGY FREEZE — Phase 3

## Status

NO VALIDATED EDGE YET

## Frozen rule

`H1_RSI_Recovery_Volume_Expansion`

The rule was selected using train and validation only. OOS was not used to alter it.

## Data discipline

Features use S-1 or earlier snapshots. No future return, high, volume, RSI, support, float, short interest, or news is used.

## Execution

No broker, order, auto-trading, Telegram, or real-money execution. Any dashboard display must be labelled Paper Signal / Research.

## Risk fields

Stop, target, holding period, slippage, spread, and liquidity cannot be frozen as validated execution parameters until a rule survives OOS with point-in-time execution data.
