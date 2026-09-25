/**
 * Technical indicator library — pure functions over Candle[].
 * All series are index-aligned with the input candles (NaN/null until warm-up).
 */

import type { Candle, SwingPoint } from "./types";

/* ------------------------------------------------------------------ */
/* Moving averages                                                     */
/* ------------------------------------------------------------------ */

export function sma(values: number[], period: number): number[] {
  const out = new Array<number>(values.length).fill(NaN);
  let sum = 0;
  for (let i = 0; i < values.length; i++) {
    sum += values[i];
    if (i >= period) sum -= values[i - period];
    if (i >= period - 1) out[i] = sum / period;
  }
  return out;
}

export function ema(values: number[], period: number): number[] {
  const out = new Array<number>(values.length).fill(NaN);
  if (values.length < period) return out;
  const k = 2 / (period + 1);
  let seed = 0;
  for (let i = 0; i < period; i++) seed += values[i];
  seed /= period;
  out[period - 1] = seed;
  for (let i = period; i < values.length; i++) {
    out[i] = values[i] * k + out[i - 1] * (1 - k);
  }
  return out;
}

/* ------------------------------------------------------------------ */
/* VWAP                                                                */
/* ------------------------------------------------------------------ */

/** Day key (UTC date) for a candle timestamp. */
function dayKey(time: number): number {
  const d = new Date(time * 1000);
  return d.getUTCFullYear() * 10000 + (d.getUTCMonth() + 1) * 100 + d.getUTCDate();
}

/** Session VWAP — resets at the start of every trading day. */
export function sessionVwap(candles: Candle[]): (number | null)[] {
  const out: (number | null)[] = new Array(candles.length).fill(null);
  let cumPV = 0;
  let cumV = 0;
  let curDay = -1;
  for (let i = 0; i < candles.length; i++) {
    const c = candles[i];
    const dk = dayKey(c.time);
    if (dk !== curDay) {
      curDay = dk;
      cumPV = 0;
      cumV = 0;
    }
    const tp = (c.high + c.low + c.close) / 3;
    cumPV += tp * c.volume;
    cumV += c.volume;
    out[i] = cumV > 0 ? cumPV / cumV : null;
  }
  return out;
}

/**
 * Anchored VWAP — cumulative from a structural anchor bar (used on the 1D
 * timeframe where session VWAP is meaningless).
 */
export function anchoredVwap(candles: Candle[], anchorIndex: number): (number | null)[] {
  const out: (number | null)[] = new Array(candles.length).fill(null);
  let cumPV = 0;
  let cumV = 0;
  for (let i = anchorIndex; i < candles.length; i++) {
    const c = candles[i];
    const tp = (c.high + c.low + c.close) / 3;
    cumPV += tp * c.volume;
    cumV += c.volume;
    out[i] = cumV > 0 ? cumPV / cumV : null;
  }
  return out;
}

/* ------------------------------------------------------------------ */
/* OBV                                                                 */
/* ------------------------------------------------------------------ */

export function obv(candles: Candle[]): number[] {
  const out = new Array<number>(candles.length).fill(0);
  let v = 0;
  for (let i = 0; i < candles.length; i++) {
    if (i === 0) {
      out[i] = v;
      continue;
    }
    const c = candles[i];
    const p = candles[i - 1];
    if (c.close > p.close) v += c.volume;
    else if (c.close < p.close) v -= c.volume;
    out[i] = v;
  }
  return out;
}

/* ------------------------------------------------------------------ */
/* RSI (Wilder)                                                        */
/* ------------------------------------------------------------------ */

export function rsi(closes: number[], period = 14): number[] {
  const out = new Array<number>(closes.length).fill(NaN);
  if (closes.length <= period) return out;
  let gain = 0;
  let loss = 0;
  for (let i = 1; i <= period; i++) {
    const diff = closes[i] - closes[i - 1];
    if (diff >= 0) gain += diff;
    else loss -= diff;
  }
  gain /= period;
  loss /= period;
  out[period] = loss === 0 ? 100 : 100 - 100 / (1 + gain / loss);
  for (let i = period + 1; i < closes.length; i++) {
    const diff = closes[i] - closes[i - 1];
    gain = (gain * (period - 1) + Math.max(diff, 0)) / period;
    loss = (loss * (period - 1) + Math.max(-diff, 0)) / period;
    out[i] = loss === 0 ? 100 : 100 - 100 / (1 + gain / loss);
  }
  return out;
}

/* ------------------------------------------------------------------ */
/* MACD (12, 26, 9)                                                    */
/* ------------------------------------------------------------------ */

export interface MacdResult {
  macd: number[];
  signal: number[];
  hist: number[];
}

export function macd(closes: number[], fast = 12, slow = 26, signalP = 9): MacdResult {
  const emaFast = ema(closes, fast);
  const emaSlow = ema(closes, slow);
  const macdLine = closes.map((_, i) =>
    isNaN(emaFast[i]) || isNaN(emaSlow[i]) ? NaN : emaFast[i] - emaSlow[i],
  );
  // signal EMA over the valid MACD region
  const firstValid = macdLine.findIndex((v) => !isNaN(v));
  const signal = new Array<number>(closes.length).fill(NaN);
  if (firstValid >= 0) {
    const sub = macdLine.slice(firstValid);
    const sigSub = ema(sub, signalP);
    for (let i = 0; i < sigSub.length; i++) signal[firstValid + i] = sigSub[i];
  }
  const hist = macdLine.map((v, i) =>
    isNaN(v) || isNaN(signal[i]) ? NaN : v - signal[i],
  );
  return { macd: macdLine, signal, hist };
}

/* ------------------------------------------------------------------ */
/* Bollinger Bands + squeeze percentile                                */
/* ------------------------------------------------------------------ */

export interface BollingerResult {
  upper: number[];
  middle: number[];
  lower: number[];
  /** band width as % of the middle band */
  widthPct: number[];
}

export function bollinger(closes: number[], period = 20, mult = 2): BollingerResult {
  const middle = sma(closes, period);
  const upper = new Array<number>(closes.length).fill(NaN);
  const lower = new Array<number>(closes.length).fill(NaN);
  const widthPct = new Array<number>(closes.length).fill(NaN);
  for (let i = period - 1; i < closes.length; i++) {
    let acc = 0;
    for (let j = i - period + 1; j <= i; j++) acc += (closes[j] - middle[i]) ** 2;
    const sd = Math.sqrt(acc / period);
    upper[i] = middle[i] + mult * sd;
    lower[i] = middle[i] - mult * sd;
    widthPct[i] = middle[i] > 0 ? ((upper[i] - lower[i]) / middle[i]) * 100 : NaN;
  }
  return { upper, middle, lower, widthPct };
}

/** Percentile rank (0..100) of the latest width within the lookback window. */
export function widthPercentile(widthPct: number[], lookback = 120): number {
  const n = widthPct.length;
  const last = widthPct[n - 1];
  if (isNaN(last)) return 100;
  const window = widthPct.slice(Math.max(0, n - lookback), n).filter((v) => !isNaN(v));
  if (!window.length) return 100;
  const below = window.filter((v) => v < last).length;
  return (below / window.length) * 100;
}

/* ------------------------------------------------------------------ */
/* ATR                                                                 */
/* ------------------------------------------------------------------ */

export function atr(candles: Candle[], period = 14): number[] {
  const out = new Array<number>(candles.length).fill(NaN);
  if (candles.length <= period) return out;
  const trs: number[] = [];
  for (let i = 0; i < candles.length; i++) {
    const c = candles[i];
    if (i === 0) {
      trs.push(c.high - c.low);
      continue;
    }
    const p = candles[i - 1];
    trs.push(Math.max(c.high - c.low, Math.abs(c.high - p.close), Math.abs(c.low - p.close)));
  }
  let a = 0;
  for (let i = 0; i < period; i++) a += trs[i];
  a /= period;
  out[period - 1] = a;
  for (let i = period; i < candles.length; i++) {
    a = (a * (period - 1) + trs[i]) / period;
    out[i] = a;
  }
  return out;
}

/* ------------------------------------------------------------------ */
/* Swing pivots (fractals)                                             */
/* ------------------------------------------------------------------ */

export function findSwings(candles: Candle[], k = 3): SwingPoint[] {
  const pts: SwingPoint[] = [];
  for (let i = k; i < candles.length - k; i++) {
    let isLow = true;
    let isHigh = true;
    for (let j = i - k; j <= i + k; j++) {
      if (j === i) continue;
      if (candles[j].low <= candles[i].low) isLow = false;
      if (candles[j].high >= candles[i].high) isHigh = false;
      if (!isLow && !isHigh) break;
    }
    if (isLow) pts.push({ index: i, time: candles[i].time, price: candles[i].low, kind: "low" });
    if (isHigh) pts.push({ index: i, time: candles[i].time, price: candles[i].high, kind: "high" });
  }
  return pts;
}
