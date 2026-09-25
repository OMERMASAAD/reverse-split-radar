# APEX Terminal — منصة التداول الآلي الاحترافية

A high-end, production-ready trading desk web app built with **Next.js 15 (App Router)**,
**Tailwind CSS v4**, **Lucide icons** and the **TradingView Lightweight Charts v5** engine.

**واجهة عربية بالكامل (RTL)** — all terminology, status badges, analysis cards and chart
levels are rendered in Arabic; ticker symbols and universal indicator names (VWAP, RSI,
MACD, OBV) stay in Latin script, as is standard on Arabic trading desks.

![stack](https://img.shields.io/badge/Next.js-15-black) ![lwc](https://img.shields.io/badge/Lightweight--Charts-5-2962ff) ![tailwind](https://img.shields.io/badge/Tailwind-4-38bdf8)

## What it does

The terminal runs a five-rule automated strategy engine over any symbol in the watchlist
universe and paints the full execution blueprint directly on the chart:

1. **VWAP Condition** — price vs session VWAP (orange line) with % distance meter.
2. **OBV Flow Engine** — On-Balance Volume vs its 20 EMA → INFLOW / OUTFLOW / MIXED.
3. **MACD Momentum** — 12/26/9 signal-line crossover + histogram expansion tracking.
4. **RSI Range Meter** — Wilder-14 gauge with a violet **≥ 80 overbought warning**.
5. **Pattern Recognition** — auto-detects **Inverted Head & Shoulders**, **Double Bottom**,
   **Higher-Lows ladders** (fallback: consolidation range) with confidence scoring.

### Chart overlays (auto-drawn)

| Level | Style |
| --- | --- |
| VWAP (session / anchored on 1D) | solid **orange** line series |
| Structural pivot support | solid **green** price line |
| Neckline breakout / resistance | solid **red** price line |
| Target 1 (1× measured move) | dashed **green** price line |
| Target 2 (1.618× measured move) | dashed **green** price line |
| Stop-loss (structural pivot low) | dashed **red** price line |
| Buy signals | **arrow-up markers** beneath qualifying candles |

### Status badge

The header badge re-evaluates on every timeframe toggle:
`🚀 SQUEEZE CONFIRMED` · `⏳ BASE BUILDING` · `⚠️ RISKY / BELOW VWAP` · `⚡ MOMENTUM RUN`,
driven by Bollinger-bandwidth percentile (squeeze), VWAP reclaim and neckline breaks.

## Data feed

Fully **deterministic simulated tape** (no external API keys, reproducible signals):

- 135 trading sessions per symbol generated at **1-minute resolution** from hand-crafted
  regime scripts (anchor path, volatility & volume regimes, scripted gaps) — see
  `lib/market/profiles.ts`.
- Minute bars are aggregated into **5m / 15m / 1h / 4h / 1D**; toggling a timeframe
  instantly re-runs the whole engine and repaints targets.
- Featured setups: **THH** (squeeze → breakout), **ELPW** (below-VWAP rejection),
  **MSGY** (base building), **AAPL** (higher-lows uptrend), plus NVDA/TSLA/AMD/GME/PLTR/SOFI.

## Running

```bash
npm install
npm run dev        # http://localhost:3000
npm run build      # production build
npm start          # serve production build
```

## Structure

```
app/            Next.js App Router shell (layout, page, theme)
components/
  terminal/     header, search, timeframe toggle, status badge, ticker tape, footer
  chart/        Lightweight-Charts canvas + hover legend + level chips
  panel/        analysis cards (status, VWAP, OBV, MACD, RSI, pattern, trade plan)
lib/
  market/       deterministic tape generator + symbol regime profiles
  indicators.ts VWAP · OBV · RSI · MACD · Bollinger · ATR · fractal swings
  strategy/     pattern recognition + full rulebook engine
  types.ts      domain model
```

> ⚠️ Paper/simulation only — everything rendered is generated analysis, **not investment advice**.
