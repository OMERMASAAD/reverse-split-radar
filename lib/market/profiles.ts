/**
 * Symbol universe + hand-crafted regime scripts.
 *
 * The terminal runs on a deterministic simulated market feed so the strategy
 * engine is fully reproducible offline. Each symbol carries an "anchor script"
 * (keyframed price path, volatility & volume regimes, scripted gaps) that the
 * generator turns into realistic minute-level OHLCV data.
 *
 * Keyframe offsets `d` are trading days relative to the current session
 * (d = 0 → today, d = -30 → 30 sessions ago).
 */

export interface Key {
  d: number;
  v: number;
}

export interface SymbolProfile {
  symbol: string;
  name: string;
  sector: string;
  /** anchor close price keyframes */
  anchor: Key[];
  /** intraday volatility multiplier keyframes */
  volatility: Key[];
  /** volume multiplier keyframes */
  volume: Key[];
  /** scripted overnight gaps (fraction) */
  gaps: Key[];
  /**
   * Optional intraday shape for the CURRENT session: keys are % of session
   * (0..100), values are the fraction (0..1) of the day's move completed —
   * lets us script surge → digest → late-push days.
   */
  intraday?: Key[];
  /** base per-minute return volatility (fraction) */
  minuteVol: number;
  /** average shares traded per minute */
  baseVolume: number;
  /** price tick size */
  tick: number;
  featured?: boolean;
}

const A = (d: number, v: number): Key => ({ d, v });

/* ------------------------------------------------------------------ */
/* Hand-crafted setups                                                 */
/* ------------------------------------------------------------------ */

/** THH — capitulation → double-bottom base → tight squeeze flag → breakout TODAY. */
const THH: SymbolProfile = {
  symbol: "THH",
  name: "TutuHealth Holdings",
  sector: "تقنية حيوية · سهم صغير",
  anchor: [
    A(-134, 4.1), A(-112, 3.62), A(-88, 2.92), A(-64, 2.28), A(-50, 2.6),
    A(-37, 2.33), A(-23, 2.64), A(-15, 2.47), A(-9, 2.66), A(-6, 2.72),
    A(-5, 2.755), A(-4, 2.735), A(-3, 2.755), A(-2, 2.775), A(-1, 2.79),
    A(0, 3.11),
  ],
  volatility: [
    A(-134, 1.0), A(-90, 1.25), A(-64, 2.1), A(-50, 1.3), A(-30, 0.72),
    A(-10, 0.6), A(-4, 0.4), A(-2, 0.36), A(-1, 0.34), A(0, 1.8),
  ],
  volume: [
    A(-134, 0.9), A(-64, 2.6), A(-50, 1.2), A(-30, 0.55), A(-10, 0.5),
    A(-4, 0.36), A(-2, 0.4), A(-1, 0.45), A(0, 3.4),
  ],
  gaps: [A(-64, -0.055), A(0, 0.026)],
  intraday: [
    A(0, 0), A(8, 0.35), A(16, 0.55), A(26, 0.66), A(38, 0.6), A(50, 0.56),
    A(62, 0.62), A(74, 0.7), A(86, 0.88), A(100, 1),
  ],
  minuteVol: 0.0013,
  baseVolume: 8200,
  tick: 0.01,
  featured: true,
};

/** ELPW — pump & dump, dead-cat chops, weak bounce rejected below VWAP. */
const ELPW: SymbolProfile = {
  symbol: "ELPW",
  name: "Elpwire Networks",
  sector: "اتصالات · سهم متناهي الصغر",
  anchor: [
    A(-134, 0.88), A(-118, 0.96), A(-106, 0.9), A(-94, 1.0), A(-88, 1.18),
    A(-84, 1.42), A(-79, 2.08), A(-75, 2.44), A(-71, 1.92), A(-66, 1.4),
    A(-58, 0.95), A(-46, 0.74), A(-33, 0.83), A(-24, 0.71), A(-14, 0.735),
    A(-8, 0.775), A(-5, 0.82), A(-3, 0.835), A(-1, 0.782), A(0, 0.748),
  ],
  volatility: [
    A(-134, 1.0), A(-94, 1.2), A(-84, 2.6), A(-75, 3.2), A(-66, 2.4),
    A(-50, 1.3), A(-30, 0.95), A(-10, 1.1), A(-3, 1.35), A(0, 1.25),
  ],
  volume: [
    A(-134, 0.8), A(-88, 2.2), A(-80, 4.5), A(-72, 3.6), A(-60, 1.4),
    A(-45, 0.5), A(-25, 0.4), A(-8, 0.7), A(-3, 1.15), A(-1, 1.3), A(0, 1.1),
  ],
  gaps: [A(-84, 0.06), A(-75, 0.045), A(-71, -0.08), A(-64, -0.06), A(0, 0.032)],
  minuteVol: 0.0022,
  baseVolume: 31000,
  tick: 0.0001,
  featured: true,
};

/** MSGY — impulse leg up → correction → wide base building at mid-range. */
const MSGY: SymbolProfile = {
  symbol: "MSGY",
  name: "MessageYard Inc",
  sector: "برمجيات SaaS · سهم متوسط",
  anchor: [
    A(-134, 5.18), A(-112, 5.62), A(-92, 6.48), A(-78, 7.42), A(-68, 7.82),
    A(-58, 7.15), A(-48, 6.44), A(-38, 6.72), A(-30, 6.5), A(-20, 6.86),
    A(-12, 6.55), A(-7, 6.68), A(-4, 6.82), A(-2, 6.66), A(-1, 6.71),
    A(0, 6.78),
  ],
  volatility: [
    A(-134, 0.9), A(-70, 1.35), A(-48, 1.2), A(-30, 0.8), A(-12, 0.66),
    A(-4, 0.7), A(0, 0.72),
  ],
  volume: [
    A(-134, 0.85), A(-70, 1.9), A(-48, 1.4), A(-30, 0.9), A(-12, 0.62),
    A(-4, 0.7), A(-1, 0.78), A(0, 0.72),
  ],
  gaps: [A(-78, 0.03), A(-58, -0.035), A(0, 0.004)],
  minuteVol: 0.00088,
  baseVolume: 4300,
  tick: 0.01,
  featured: true,
};

/** AAPL — steady mega-cap uptrend, constructive higher lows at highs. */
const AAPL: SymbolProfile = {
  symbol: "AAPL",
  name: "Apple Inc.",
  sector: "تقنية · شركة عملاقة",
  anchor: [
    A(-134, 196.5), A(-118, 201), A(-100, 208.5), A(-84, 216), A(-70, 226.5),
    A(-58, 219.5), A(-46, 228), A(-34, 237.5), A(-22, 241.5), A(-14, 236.5),
    A(-7, 245.5), A(-3, 249.5), A(-1, 251.4), A(0, 253.8),
  ],
  volatility: [
    A(-134, 0.95), A(-70, 1.2), A(-40, 1.0), A(-14, 0.85), A(-5, 0.72),
    A(0, 0.78),
  ],
  volume: [
    A(-134, 1.0), A(-70, 1.5), A(-40, 1.1), A(-14, 0.9), A(-5, 0.75),
    A(-1, 1.05), A(0, 0.88),
  ],
  gaps: [A(-58, -0.012), A(-14, -0.008), A(0, 0.0026)],
  minuteVol: 0.00052,
  baseVolume: 92000,
  tick: 0.01,
  featured: true,
};

/* ------------------------------------------------------------------ */
/* Procedural profiles for the rest of the searchable universe         */
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

interface ProceduralSpec {
  symbol: string;
  name: string;
  sector: string;
  start: number;
  drift: number; // total drift over the window (fraction)
  minuteVol: number;
  baseVolume: number;
  tick: number;
  chop: number; // 0..1 pullback intensity
}

function procedural(spec: ProceduralSpec): SymbolProfile {
  const rng = mulberry32(hashStr(spec.symbol));
  const gauss = () => {
    const u = Math.max(rng(), 1e-9);
    const v = rng();
    return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
  };
  const anchor: Key[] = [];
  const volatility: Key[] = [];
  const volume: Key[] = [];
  const step = 9;
  let level = spec.start;
  for (let d = -134; d <= 0; d += step) {
    const progress = (d + 134) / 134;
    const trend = (spec.drift * spec.start * step) / 134;
    level = Math.max(
      spec.start * 0.25,
      level + trend + level * spec.minuteVol * Math.sqrt(step * 390) * gauss() * (0.55 + spec.chop),
    );
    anchor.push(A(d, +level.toFixed(spec.tick < 0.01 ? 3 : 2)));
    volatility.push(A(d, +(0.75 + rng() * 0.8).toFixed(2)));
    volume.push(A(d, +(0.6 + rng() * 1.1).toFixed(2)));
    void progress;
  }
  anchor.push(A(0, +level.toFixed(spec.tick < 0.01 ? 3 : 2)));
  volatility.push(A(0, +(0.8 + rng() * 0.5).toFixed(2)));
  volume.push(A(0, +(0.8 + rng() * 0.8).toFixed(2)));
  return {
    symbol: spec.symbol,
    name: spec.name,
    sector: spec.sector,
    anchor,
    volatility,
    volume,
    gaps: [],
    minuteVol: spec.minuteVol,
    baseVolume: spec.baseVolume,
    tick: spec.tick,
  };
}

const NVDA = procedural({
  symbol: "NVDA", name: "NVIDIA Corp.", sector: "أشباه موصلات",
  start: 128, drift: 0.62, minuteVol: 0.00095, baseVolume: 64000, tick: 0.01, chop: 0.5,
});
const TSLA = procedural({
  symbol: "TSLA", name: "Tesla Inc.", sector: "سيارات كهربائية",
  start: 242, drift: 0.08, minuteVol: 0.00125, baseVolume: 51000, tick: 0.01, chop: 0.95,
});
const AMD = procedural({
  symbol: "AMD", name: "Advanced Micro Devices", sector: "أشباه موصلات",
  start: 138, drift: 0.3, minuteVol: 0.00105, baseVolume: 33000, tick: 0.01, chop: 0.65,
});
const GME = procedural({
  symbol: "GME", name: "GameStop Corp.", sector: "تجزئة · سهم ميمي",
  start: 24.5, drift: -0.12, minuteVol: 0.00165, baseVolume: 21000, tick: 0.01, chop: 0.9,
});
const PLTR = procedural({
  symbol: "PLTR", name: "Palantir Technologies", sector: "ذكاء اصطناعي دفاعي",
  start: 32, drift: 0.85, minuteVol: 0.00115, baseVolume: 48000, tick: 0.01, chop: 0.6,
});
const SOFI = procedural({
  symbol: "SOFI", name: "SoFi Technologies", sector: "تقنية مالية",
  start: 8.4, drift: 0.4, minuteVol: 0.00135, baseVolume: 39000, tick: 0.01, chop: 0.75,
});

export const PROFILES: Record<string, SymbolProfile> = {
  THH, ELPW, MSGY, AAPL, NVDA, TSLA, AMD, GME, PLTR, SOFI,
};

export const UNIVERSE = Object.values(PROFILES);

export function getProfile(symbol: string): SymbolProfile {
  return PROFILES[symbol.toUpperCase()] ?? THH;
}
