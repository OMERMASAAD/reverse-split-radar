/**
 * Deterministic market-data engine.
 *
 * Builds a full minute-level OHLCV history (≈135 sessions) per symbol from the
 * regime scripts in profiles.ts, then aggregates it into the terminal's
 * timeframes (5m / 15m / 1h / 4h / 1D). Everything is seeded — the same symbol
 * always produces the same tape within a session, so signals are reproducible.
 */

import type { Candle, Timeframe } from "../types";
import { PROFILES, getProfile, type Key, type SymbolProfile } from "./profiles";

export const TOTAL_DAYS = 135;
const SESSION_MINUTES = 390; // 09:30 → 16:00 ET
const KAPPA = 0.02; // OU pull toward the anchor path

export const TF_MINUTES: Record<Timeframe, number> = {
  "5m": 5,
  "15m": 15,
  "1h": 60,
  "4h": 240,
  "1D": SESSION_MINUTES,
};

/* ------------------------------------------------------------------ */
/* Random helpers                                                      */
/* ------------------------------------------------------------------ */

function mulberry32(seed: number) {
  let a = seed >>> 0;
  return () => {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function hashStr(s: string): number {
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

/* ------------------------------------------------------------------ */
/* Keyframe sampling                                                   */
/* ------------------------------------------------------------------ */

function sampleKeys(keys: Key[], d: number, fallback = 1): number {
  if (!keys.length) return fallback;
  if (d <= keys[0].d) return keys[0].v;
  const last = keys[keys.length - 1];
  if (d >= last.d) return last.v;
  for (let i = 0; i < keys.length - 1; i++) {
    const a = keys[i];
    const b = keys[i + 1];
    if (d >= a.d && d <= b.d) {
      const t = (d - a.d) / (b.d - a.d);
      const s = t * t * (3 - 2 * t); // smoothstep
      return a.v + (b.v - a.v) * s;
    }
  }
  return fallback;
}

function sampleGap(keys: Key[], d: number): number | null {
  for (const k of keys) if (k.d === d) return k.v;
  return null;
}

/* ------------------------------------------------------------------ */
/* Trading calendar                                                    */
/* ------------------------------------------------------------------ */

/** US Eastern UTC offset (handles EDT/EST). */
function etOffsetHours(date: Date): number {
  const y = date.getUTCFullYear();
  const marchFirst = new Date(Date.UTC(y, 2, 1));
  const novFirst = new Date(Date.UTC(y, 10, 1));
  const secondSunMar =
    Date.UTC(y, 2, 8 + ((7 - marchFirst.getUTCDay()) % 7));
  const firstSunNov = Date.UTC(y, 10, 1 + ((7 - novFirst.getUTCDay()) % 7));
  const t = date.getTime();
  return t >= secondSunMar && t < firstSunNov ? -4 : -5;
}

/** 09:30 US/Eastern → UTC ms for the given calendar day. */
function sessionOpenUtcMs(day: Date): number {
  const off = etOffsetHours(day);
  return (
    Date.UTC(day.getUTCFullYear(), day.getUTCMonth(), day.getUTCDate(), 9, 30) -
    off * 3600_000
  );
}

export interface SessionWindow {
  /** ascending list of session dates (UTC midday markers) */
  days: Date[];
  /** minutes elapsed in the final session (1..390) */
  finalSessionMinutes: number;
  /** whether the final session is still live */
  marketOpen: boolean;
  key: string;
}

export function getSessionWindow(now: Date = new Date()): SessionWindow {
  const cursor = new Date(now);
  // roll back to the most recent weekday
  while (cursor.getUTCDay() === 0 || cursor.getUTCDay() === 6) {
    cursor.setUTCDate(cursor.getUTCDate() - 1);
    cursor.setUTCHours(20, 0, 0, 0);
  }
  const openMs = sessionOpenUtcMs(cursor);
  const closeMs = openMs + SESSION_MINUTES * 60_000;
  let finalDate = new Date(cursor);
  let minutes = SESSION_MINUTES;
  let marketOpen = false;
  if (now.getTime() < openMs) {
    // before the bell → previous session was the last one
    finalDate.setUTCDate(finalDate.getUTCDate() - 1);
    while (finalDate.getUTCDay() === 0 || finalDate.getUTCDay() === 6) {
      finalDate.setUTCDate(finalDate.getUTCDate() - 1);
    }
    minutes = SESSION_MINUTES;
  } else if (now.getTime() < closeMs) {
    minutes = Math.max(1, Math.floor((now.getTime() - openMs) / 60_000));
    marketOpen = true;
  }

  const days: Date[] = [];
  const d = new Date(finalDate);
  while (days.length < TOTAL_DAYS) {
    if (d.getUTCDay() !== 0 && d.getUTCDay() !== 6) days.unshift(new Date(d));
    d.setUTCDate(d.getUTCDate() - 1);
  }
  const key = `${finalDate.toISOString().slice(0, 10)}|${minutes}`;
  return { days, finalSessionMinutes: minutes, marketOpen, key };
}

/* ------------------------------------------------------------------ */
/* Minute-level generation                                             */
/* ------------------------------------------------------------------ */

const minuteCache = new Map<string, Candle[]>();

function uShape(f: number): number {
  return 1 + 1.35 * (Math.exp(-8 * f) + Math.exp(-8 * (1 - f)));
}

function roundTick(p: number, tick: number): number {
  return Math.round(p / tick) * tick;
}

export function generateMinutes(profile: SymbolProfile, win: SessionWindow): Candle[] {
  const cacheKey = `${profile.symbol}|${win.key}`;
  const cached = minuteCache.get(cacheKey);
  if (cached) return cached;

  const out: Candle[] = [];
  const symSeed = hashStr(profile.symbol);
  let prevClose = sampleKeys(profile.anchor, -(TOTAL_DAYS - 1)) ;

  for (let di = 0; di < win.days.length; di++) {
    const day = win.days[di];
    const dRel = di - (win.days.length - 1); // -(134) .. 0
    const isFinal = di === win.days.length - 1;
    const minutes = isFinal ? win.finalSessionMinutes : SESSION_MINUTES;

    const rng = mulberry32((symSeed ^ Math.imul(di + 1, 0x9e3779b1)) >>> 0);
    const gauss = () => {
      const u = Math.max(rng(), 1e-9);
      const v = rng();
      return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
    };

    const anchorOpen = prevClose;
    const anchorClose = sampleKeys(profile.anchor, dRel);
    const rs =
      profile.reverseSplit && dRel === profile.reverseSplit.d
        ? profile.reverseSplit
        : null;
    const scripted = sampleGap(profile.gaps, dRel);
    const dayVolMul = sampleKeys(profile.volatility, dRel);
    const dayVolumeMul = sampleKeys(profile.volume, dRel);
    const gap = rs ? rs.gapUp : (scripted ?? gauss() * 0.0022 * dayVolMul);

    const openMs = sessionOpenUtcMs(day);
    let p = anchorOpen * (1 + gap);
    const dayOpen = p;
    // reverse-split spike candle: vertical surge then exponential decay
    const spikeHigh = rs ? dayOpen * rs.spikeMult : 0;
    const sigmaBase = profile.minuteVol;

    for (let m = 0; m < minutes; m++) {
      const f = minutes > 1 ? m / (minutes - 1) : 1;
      let anchor: number;
      if (rs) {
        if (f <= 0.03) anchor = dayOpen + (spikeHigh - dayOpen) * (f / 0.03);
        else
          anchor =
            anchorClose +
            (spikeHigh - anchorClose) * Math.exp(-5.5 * (f - 0.03));
      } else {
        const sf =
          isFinal && profile.intraday?.length
            ? sampleKeys(profile.intraday, f * 100, f)
            : f * f * (3 - 2 * f);
        anchor = anchorOpen * Math.pow(anchorClose / anchorOpen, sf);
      }
      // track the split-day surge tightly; OU elsewhere
      const kappa = rs ? (f <= 0.04 ? 0.5 : KAPPA) : KAPPA;
      const sigma = sigmaBase * dayVolMul * (1 + 0.45 * (Math.exp(-6 * f) + Math.exp(-6 * (1 - f))));

      const o = p;
      const drift = kappa * (Math.log(anchor) - Math.log(Math.max(p, 1e-6)));
      p = p * Math.exp(drift + sigma * gauss());
      if (p < profile.tick * 2) p = profile.tick * 2;
      const c = p;

      const wickUp = Math.abs(gauss()) * sigma * 0.85;
      const wickDn = Math.abs(gauss()) * sigma * 0.85;
      const hi = Math.max(o, c) * (1 + wickUp);
      const lo = Math.min(o, c) * (1 - wickDn);

      const ret = Math.abs(c / o - 1);
      const vol =
        profile.baseVolume *
        dayVolumeMul *
        uShape(f) *
        (1 + 2.6 * (ret / Math.max(sigmaBase, 1e-6))) *
        Math.exp(0.35 * gauss());

      out.push({
        time: Math.floor((openMs + m * 60_000) / 1000),
        open: roundTick(o, profile.tick),
        high: roundTick(hi, profile.tick),
        low: roundTick(lo, profile.tick),
        close: roundTick(c, profile.tick),
        volume: Math.max(100, Math.round(vol / 100) * 100),
      });
    }
    prevClose = p;
  }

  minuteCache.set(cacheKey, out);
  return out;
}

/* ------------------------------------------------------------------ */
/* Aggregation                                                         */
/* ------------------------------------------------------------------ */

export function aggregate(minutes: Candle[], tf: Timeframe): Candle[] {
  if (tf === "1D") {
    const out: Candle[] = [];
    let cur: Candle | null = null;
    let curDay = -1;
    for (const m of minutes) {
      const day = new Date(m.time * 1000).getUTCDate() +
        new Date(m.time * 1000).getUTCMonth() * 100;
      if (!cur || day !== curDay) {
        if (cur) out.push(cur);
        curDay = day;
        cur = { time: m.time, open: m.open, high: m.high, low: m.low, close: m.close, volume: m.volume };
      } else {
        cur.high = Math.max(cur.high, m.high);
        cur.low = Math.min(cur.low, m.low);
        cur.close = m.close;
        cur.volume += m.volume;
      }
    }
    if (cur) out.push(cur);
    return out;
  }

  const tfMin = TF_MINUTES[tf];
  const out: Candle[] = [];
  let cur: Candle | null = null;
  let curBucket = "";
  for (const m of minutes) {
    const dt = new Date(m.time * 1000);
    const openMs = sessionOpenUtcMs(dt);
    const elapsedMin = Math.floor((m.time * 1000 - openMs) / 60_000);
    const chunk = Math.floor(elapsedMin / tfMin);
    const bucket = `${dt.getUTCFullYear()}-${dt.getUTCMonth()}-${dt.getUTCDate()}|${chunk}`;
    if (!cur || bucket !== curBucket) {
      if (cur) out.push(cur);
      curBucket = bucket;
      cur = { time: m.time, open: m.open, high: m.high, low: m.low, close: m.close, volume: m.volume };
    } else {
      cur.high = Math.max(cur.high, m.high);
      cur.low = Math.min(cur.low, m.low);
      cur.close = m.close;
      cur.volume += m.volume;
    }
  }
  if (cur) out.push(cur);
  return out;
}

/* ------------------------------------------------------------------ */
/* Public API                                                          */
/* ------------------------------------------------------------------ */

const tfCache = new Map<string, Candle[]>();

export function getCandles(symbol: string, tf: Timeframe, now: Date = new Date()): Candle[] {
  const win = getSessionWindow(now);
  const key = `${symbol}|${tf}|${win.key}`;
  const cached = tfCache.get(key);
  if (cached) return cached;
  const profile = getProfile(symbol);
  const minutes = generateMinutes(profile, win);
  const candles = aggregate(minutes, tf);
  tfCache.set(key, candles);
  return candles;
}

export interface TapeQuote {
  symbol: string;
  name: string;
  last: number;
  prevClose: number;
  changePct: number;
}

const tapeCache = new Map<string, { key: string; quotes: TapeQuote[] }>();

export function getTape(symbols: string[], now: Date = new Date()): TapeQuote[] {
  const win = getSessionWindow(now);
  const cached = tapeCache.get("all");
  if (cached && cached.key === win.key) {
    return symbols
      .map((s) => cached.quotes.find((q) => q.symbol === s))
      .filter(Boolean) as TapeQuote[];
  }
  const quotes: TapeQuote[] = [];
  for (const sym of Object.keys(PROFILES)) {
    const profile = getProfile(sym);
    const minutes = generateMinutes(profile, win);
    const daily = aggregate(minutes, "1D");
    const last = daily[daily.length - 1];
    const prev = daily[daily.length - 2] ?? last;
    quotes.push({
      symbol: sym,
      name: profile.name,
      last: last.close,
      prevClose: prev.close,
      changePct: ((last.close - prev.close) / prev.close) * 100,
    });
  }
  tapeCache.set("all", { key: win.key, quotes });
  return symbols
    .map((s) => quotes.find((q) => q.symbol === s))
    .filter(Boolean) as TapeQuote[];
}
