/**
 * APEX Strategy Engine
 *
 * Runs the full rulebook over a candle series and produces every artefact the
 * terminal renders: VWAP condition, OBV flow, MACD momentum state, RSI zone,
 * squeeze percentile, pattern recognition, buy-signal markers, trade plan and
 * the headline status badge.
 */

import type {
  AnalysisResult,
  BuySignal,
  Candle,
  ChecklistItem,
  MacdState,
  ObvFlow,
  PatternResult,
  Quote,
  RsiZone,
  StatusResult,
  Timeframe,
  TradePlan,
} from "../types";
import {
  anchoredVwap,
  atr,
  bollinger,
  ema,
  macd as macdCalc,
  obv as obvCalc,
  rsi as rsiCalc,
  sessionVwap,
  sma,
} from "../indicators";
import { detectPattern } from "./patterns";
import { getProfile } from "../market/profiles";

function lastValid(arr: number[]): number {
  for (let i = arr.length - 1; i >= 0; i--) if (!isNaN(arr[i])) return arr[i];
  return NaN;
}

function lastValidIdx(arr: (number | null)[], from: number): number {
  for (let i = from; i >= 0; i--) if (arr[i] != null && !isNaN(arr[i] as number)) return i;
  return -1;
}

function mean(arr: number[]): number {
  if (!arr.length) return 0;
  return arr.reduce((a, b) => a + b, 0) / arr.length;
}

/** Rolling percentile rank of each width value within its trailing window. */
function rollingPercentile(values: number[], lookback: number): number[] {
  const out = new Array<number>(values.length).fill(NaN);
  for (let i = 0; i < values.length; i++) {
    if (isNaN(values[i])) continue;
    const from = Math.max(0, i - lookback + 1);
    let below = 0;
    let total = 0;
    for (let j = from; j <= i; j++) {
      if (isNaN(values[j])) continue;
      total++;
      if (values[j] < values[i]) below++;
    }
    out[i] = total > 0 ? (below / total) * 100 : NaN;
  }
  return out;
}

function dayKeyOf(time: number): number {
  const d = new Date(time * 1000);
  return d.getUTCFullYear() * 10000 + (d.getUTCMonth() + 1) * 100 + d.getUTCDate();
}

function buildQuote(minutes: Candle[], candles: Candle[]): Quote {
  const source = minutes.length ? minutes : candles;
  const n = source.length;
  const lastKey = dayKeyOf(source[n - 1].time);
  let start = n - 1;
  while (start > 0 && dayKeyOf(source[start - 1].time) === lastKey) start--;
  const today = source.slice(start);
  const open = today[0].open;
  const high = Math.max(...today.map((c) => c.high));
  const low = Math.min(...today.map((c) => c.low));
  const close = today[today.length - 1].close;
  const volume = today.reduce((a, c) => a + c.volume, 0);
  // previous session close
  let prevClose = open;
  if (start > 0) {
    const prevKey = dayKeyOf(source[start - 1].time);
    let i = start - 1;
    while (i > 0 && dayKeyOf(source[i - 1].time) === prevKey) i--;
    prevClose = source[i].close;
  }
  return {
    last: close,
    open,
    high,
    low,
    volume,
    prevClose,
    change: close - prevClose,
    changePct: prevClose ? ((close - prevClose) / prevClose) * 100 : 0,
  };
}

export function analyze(
  symbol: string,
  timeframe: Timeframe,
  candles: Candle[],
  minutes: Candle[],
): AnalysisResult {
  const profile = getProfile(symbol);
  const n = candles.length;
  const closes = candles.map((c) => c.close);
  const volumes = candles.map((c) => c.volume);
  const last = candles[n - 1];

  /* ---------------- VWAP ---------------- */
  let vwapSeries: (number | null)[];
  let vwapMode: "SESSION" | "ANCHORED" = "SESSION";
  if (timeframe === "1D") {
    vwapMode = "ANCHORED";
    // anchor to the structural pivot low of the last 90 sessions
    const lookback = Math.min(90, n);
    let anchorIdx = n - lookback;
    let lowest = Infinity;
    for (let i = n - lookback; i < n; i++) {
      if (candles[i].low < lowest) {
        lowest = candles[i].low;
        anchorIdx = i;
      }
    }
    vwapSeries = anchoredVwap(candles, anchorIdx);
  } else {
    vwapSeries = sessionVwap(candles);
  }
  const vwapIdx = lastValidIdx(vwapSeries, n - 1);
  const vwapValue = vwapIdx >= 0 ? (vwapSeries[vwapIdx] as number) : last.close;
  const vwapAbove = last.close >= vwapValue;
  const vwapDistPct = vwapValue ? ((last.close - vwapValue) / vwapValue) * 100 : 0;

  /* ---------------- OBV flow ---------------- */
  const obvSeries = obvCalc(candles);
  const obvEma = ema(obvSeries, 20);
  const obvLast = obvSeries[n - 1];
  const obvEmaLast = lastValid(obvEma);
  const obvPrev = obvSeries[Math.max(0, n - 11)];
  const obvEmaPrev = obvEma[Math.max(0, n - 11)];
  const obvTrajectoryUp = obvLast > obvPrev && obvEmaLast > (isNaN(obvEmaPrev) ? obvEmaLast : obvEmaPrev);
  const obvAboveEma = obvLast >= obvEmaLast;
  let obvFlow: ObvFlow = "MIXED";
  if (obvAboveEma && obvTrajectoryUp) obvFlow = "INFLOW";
  else if (!obvAboveEma && !obvTrajectoryUp) obvFlow = "OUTFLOW";
  const obvRange = Math.max(1e-9, Math.abs(obvEmaLast) || 1);
  const obvVsEmaPct = ((obvLast - obvEmaLast) / obvRange) * 100;
  const obvSlopePct = obvPrev !== 0 ? ((obvLast - obvPrev) / Math.abs(obvPrev)) * 100 : 0;

  /* ---------------- MACD ---------------- */
  const m = macdCalc(closes);
  const histLast = lastValid(m.hist);
  let macdState: MacdState = "NEUTRAL";
  let freshCross = false;
  let expanding = false;
  {
    let crossIdx = -1;
    for (let i = n - 1; i >= Math.max(1, n - 4); i--) {
      if (!isNaN(m.hist[i]) && !isNaN(m.hist[i - 1]) && m.hist[i - 1] <= 0 && m.hist[i] > 0) {
        crossIdx = i;
        break;
      }
    }
    const bearCross =
      !isNaN(m.hist[n - 1]) && !isNaN(m.hist[n - 2]) && m.hist[n - 2] >= 0 && m.hist[n - 1] < 0;
    expanding =
      n >= 3 &&
      !isNaN(m.hist[n - 1]) && !isNaN(m.hist[n - 2]) && !isNaN(m.hist[n - 3]) &&
      Math.abs(m.hist[n - 1]) > Math.abs(m.hist[n - 2]) &&
      Math.abs(m.hist[n - 2]) > Math.abs(m.hist[n - 3]);
    if (crossIdx >= 0) {
      macdState = "BULLISH_CROSS";
      freshCross = crossIdx >= n - 3;
    } else if (bearCross) {
      macdState = "BEARISH_CROSS";
    } else if (histLast > 0) {
      macdState = expanding ? "BULLISH_EXPANSION" : "BULLISH_FADE";
    } else if (histLast < 0) {
      const recovering =
        n >= 2 && !isNaN(m.hist[n - 1]) && !isNaN(m.hist[n - 2]) && m.hist[n - 1] > m.hist[n - 2];
      macdState = recovering ? "NEUTRAL" : "BEARISH_EXPANSION";
    }
  }

  /* ---------------- RSI ---------------- */
  const rsiSeries = rsiCalc(closes, 14);
  const rsiValue = lastValid(rsiSeries);
  let rsiZone: RsiZone = "BULLISH";
  if (rsiValue >= 80) rsiZone = "OVERBOUGHT";
  else if (rsiValue >= 70) rsiZone = "STRONG";
  else if (rsiValue >= 50) rsiZone = "BULLISH";
  else if (rsiValue >= 30) rsiZone = "WEAK";
  else rsiZone = "OVERSOLD";
  const rsiWarning = rsiValue >= 80;

  /* ---------------- Squeeze ---------------- */
  const bb = bollinger(closes, 20, 2);
  const pctRank = rollingPercentile(bb.widthPct, 120);
  const pctLast = lastValid(pctRank);
  const squeezing = pctLast <= 20;
  const bandwidthPct = lastValid(bb.widthPct);

  /* ---------------- ATR ---------------- */
  const atrSeries = atr(candles, 14);
  const atrLast = lastValid(atrSeries) || last.close * 0.01;

  /* ---------------- Pattern ---------------- */
  const volRecent = mean(volumes.slice(-20));
  const volPrior = mean(volumes.slice(-40, -20));
  const rightVolRatio = volPrior > 0 ? volRecent / volPrior : 1;
  const fractalK = timeframe === "1D" ? 2 : timeframe === "4h" ? 3 : 3;
  const pattern: PatternResult = detectPattern({
    candles,
    obvRising: obvFlow === "INFLOW",
    rightVolRatio,
    squeezeActive: squeezing,
    rsiValue,
    fractalK,
  });

  /* ---------------- Squeeze fire + status ---------------- */
  let fired = false;
  let compressionPct = pctLast;
  {
    // compression window scales with the timeframe (~1.5 sessions)
    const barsPerSession =
      timeframe === "5m" ? 78 : timeframe === "15m" ? 26 : timeframe === "1h" ? 7 : timeframe === "4h" ? 2 : 1;
    const firedLookback = Math.max(8, Math.ceil(barsPerSession * 1.5));
    const from = Math.max(0, n - firedLookback);
    for (let i = from; i < n; i++) {
      if (!isNaN(pctRank[i]) && pctRank[i] <= 26) {
        const brokeNeck = last.close > pattern.neckline;
        const brokeBand = !isNaN(bb.upper[i]) && last.close > bb.upper[i];
        const thrust =
          vwapAbove &&
          expanding &&
          histLast > 0 &&
          n >= 4 &&
          last.close / candles[n - 4].close - 1 > 0.01;
        if (brokeNeck || brokeBand || thrust) {
          fired = true;
          compressionPct = Math.min(compressionPct, pctRank[i]);
        }
      }
    }
  }

  let status: StatusResult;
  if (!vwapAbove) {
    status = {
      code: "RISKY",
      label: "RISKY / BELOW VWAP",
      emoji: "⚠️",
      detail: `Price is ${Math.abs(vwapDistPct).toFixed(2)}% under VWAP — institutions are selling into the tape. Stand aside until reclaimed.`,
    };
  } else if (fired) {
    status = {
      code: "SQUEEZE",
      label: "SQUEEZE CONFIRMED",
      emoji: "🚀",
      detail: `Volatility compression (BB-width ${compressionPct.toFixed(0)}th percentile) released to the upside — MACD + volume confirm the expansion leg is live.`,
    };
  } else if (squeezing || last.close < pattern.neckline) {
    status = {
      code: "BASE",
      label: "BASE BUILDING",
      emoji: "⏳",
      detail: squeezing
        ? `Bands pinched to the ${pctLast.toFixed(0)}th percentile — energy loading inside the ${pattern.label}. Trigger at ${pattern.neckline.toFixed(2)}.`
        : `Structure forming below the ${pattern.neckline.toFixed(2)} neckline. Let the breakout prove itself before entry.`,
    };
  } else {
    status = {
      code: "MOMENTUM",
      label: "MOMENTUM RUN",
      emoji: "⚡",
      detail: "Trending above VWAP with the pattern neckline already reclaimed — manage trailing stops, do not chase extended entries.",
    };
  }

  /* ---------------- Buy signals ---------------- */
  const volSma20 = sma(volumes, 20);
  const signals: BuySignal[] = [];
  const scanFrom = Math.max(60, n - 400);
  for (let i = scanFrom; i < n; i++) {
    const v = vwapSeries[i];
    if (v == null || isNaN(v)) continue;
    if (isNaN(m.hist[i]) || isNaN(m.hist[i - 1])) continue;
    if (isNaN(rsiSeries[i]) || isNaN(obvEma[i]) || isNaN(volSma20[i])) continue;
    const crossed = m.hist[i - 1] <= 0 && m.hist[i] > 0;
    const aboveVwap = candles[i].close > v;
    const rsiOk = rsiSeries[i] >= 50 && rsiSeries[i] <= 78;
    const obvOk = obvSeries[i] > obvEma[i];
    const volOk = volumes[i] >= 1.15 * volSma20[i];
    if (crossed && aboveVwap && rsiOk && obvOk && volOk) {
      signals.push({ time: candles[i].time, price: candles[i].low });
    }
  }
  const signalMarkers = signals.slice(-14);

  /* ---------------- Trade plan ---------------- */
  const breakoutMode = last.close < pattern.neckline;
  let entry = breakoutMode ? pattern.neckline * 1.002 : last.close;
  let stop = pattern.pivotLow;
  if (stop >= entry) stop = entry - 2 * atrLast;
  let t1 = pattern.neckline + pattern.depth;
  let t2 = pattern.neckline + 1.618 * pattern.depth;
  if (t1 <= entry) t1 = entry + Math.max(pattern.depth * 0.75, atrLast * 1.5);
  if (t2 <= t1) t2 = entry + (t1 - entry) * 2;
  const risk = entry - stop;
  const plan: TradePlan = {
    entry,
    stop,
    t1,
    t2,
    rr1: risk > 0 ? (t1 - entry) / risk : 0,
    rr2: risk > 0 ? (t2 - entry) / risk : 0,
    riskPct: entry > 0 ? (risk / entry) * 100 : 0,
    breakoutMode,
  };

  /* ---------------- Checklist ---------------- */
  const checklist: ChecklistItem[] = [
    {
      id: "vwap",
      label: "VWAP Condition",
      state: vwapAbove ? (vwapDistPct > 0.4 ? "pass" : "warn") : "fail",
      detail: vwapAbove
        ? `${vwapDistPct.toFixed(2)}% above ${vwapMode === "ANCHORED" ? "AVWAP" : "VWAP"} (${vwapValue.toFixed(2)})`
        : `${Math.abs(vwapDistPct).toFixed(2)}% below VWAP (${vwapValue.toFixed(2)})`,
    },
    {
      id: "obv",
      label: "OBV Flow Engine",
      state: obvFlow === "INFLOW" ? "pass" : obvFlow === "MIXED" ? "warn" : "fail",
      detail:
        obvFlow === "INFLOW"
          ? `Accumulation — OBV riding above its 20 EMA (+${obvSlopePct.toFixed(1)}% / 10 bars)`
          : obvFlow === "OUTFLOW"
            ? `Distribution — OBV below 20 EMA and rolling over (${obvSlopePct.toFixed(1)}% / 10 bars)`
            : `Indecision — OBV tangled with its 20 EMA (${obvSlopePct.toFixed(1)}% / 10 bars)`,
    },
    {
      id: "macd",
      label: "MACD Momentum",
      state:
        macdState === "BULLISH_CROSS" || macdState === "BULLISH_EXPANSION"
          ? "pass"
          : macdState === "BULLISH_FADE" || macdState === "NEUTRAL"
            ? "warn"
            : "fail",
      detail: `${macdState.replace("_", " ").toLowerCase()} · hist ${histLast >= 0 ? "+" : ""}${histLast.toFixed(4)}${expanding ? " · expanding" : ""}`,
    },
    {
      id: "rsi",
      label: "RSI Range Meter",
      state: rsiWarning ? "warn" : rsiValue >= 50 && rsiValue < 78 ? "pass" : rsiValue >= 45 ? "warn" : "fail",
      detail: rsiWarning
        ? `RSI ${rsiValue.toFixed(1)} ≥ 80 — OVEREXTENDED, entry risk elevated`
        : `RSI ${rsiValue.toFixed(1)} in the ${rsiZone.toLowerCase()} band`,
    },
    {
      id: "pattern",
      label: "Pattern Recognition",
      state:
        pattern.kind === "RANGE"
          ? "fail"
          : pattern.confidence >= 60
            ? "pass"
            : "warn",
      detail: `${pattern.label} · ${pattern.confidence}% confidence · neckline ${pattern.neckline.toFixed(2)}`,
    },
  ];

  const score = Math.round(
    Math.min(
      99,
      mean(
        checklist.map((c) => (c.state === "pass" ? 100 : c.state === "warn" ? 55 : 8)),
      ) * 0.7 + pattern.confidence * 0.3,
    ),
  );

  const quote = buildQuote(minutes, candles);

  return {
    symbol,
    symbolName: profile.name,
    timeframe,
    candles,
    quote,
    vwap: {
      series: vwapSeries,
      value: vwapValue,
      distancePct: vwapDistPct,
      above: vwapAbove,
      mode: vwapMode,
    },
    obv: { series: obvSeries, ema: obvEma, flow: obvFlow, slopePct: obvSlopePct, vsEmaPct: obvVsEmaPct },
    macd: {
      macd: m.macd,
      signal: m.signal,
      hist: m.hist,
      state: macdState,
      freshCross,
      expanding,
      histValue: histLast,
    },
    rsi: { series: rsiSeries, value: rsiValue, zone: rsiZone, warning: rsiWarning },
    squeeze: { bandwidthPct, percentile: pctLast, squeezing, fired, compressionPct },
    atr: atrLast,
    pattern,
    plan,
    status,
    signals: signalMarkers,
    checklist,
    score,
  };
}
