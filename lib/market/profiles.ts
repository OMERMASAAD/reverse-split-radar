/**
 * Symbol universe + hand-crafted regime scripts.
 *
 * The terminal runs on a deterministic simulated market feed so the strategy
 * engine is fully reproducible offline. Each symbol carries an "anchor script"
 * (keyframed price path, volatility & volume regimes, scripted gaps) plus — for
 * reverse-split names — the split event, short-interest data and a news wire.
 *
 * Keyframe offsets `d` are trading days relative to the current session
 * (d = 0 → today, d = -30 → 30 sessions ago).
 */

export interface Key {
  d: number;
  v: number;
}

export interface ReverseSplitInfo {
  /** session offset of the split day (negative) */
  d: number;
  ratioLabel: string;
  /** opening gap-up fraction on the split day */
  gapUp: number;
  /** spike high = open × spikeMult (in the first minutes of the session) */
  spikeMult: number;
}

export interface ShortData {
  floatPct: number;
  daysToCover: number;
  trend: "rising" | "falling" | "flat";
  deltaPct: number;
}

export interface NewsSeed {
  d: number;
  title: string;
  source: string;
  sentiment: "positive" | "negative" | "neutral";
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
   * (0..100), values are the fraction (0..1) of the day's move completed.
   */
  intraday?: Key[];
  /** reverse-split event (spike candle = the strategy's pivotal target) */
  reverseSplit?: ReverseSplitInfo;
  short: ShortData;
  news: NewsSeed[];
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
/* Hand-crafted reverse-split setups                                   */
/* ------------------------------------------------------------------ */

/**
 * THH — decline → 1:20 reverse split (spike candle ≈5.9) → collapse →
 * capitulation floor 2.28 → double-bottom base → breakout TODAY.
 */
const THH: SymbolProfile = {
  symbol: "THH",
  name: "TutuHealth Holdings",
  sector: "تقنية حيوية · سهم صغير · تقسيم عكسي 1:20",
  anchor: [
    A(-134, 4.1), A(-112, 3.62), A(-90, 3.18), A(-78, 3.0), A(-73, 2.95),
    A(-72, 3.48), // split day close (spike high scripted ≈ 5.9)
    A(-68, 3.12), A(-62, 2.72), A(-56, 2.48), A(-52, 2.5),
    // ── قاعدة النموذج المرجعي: كتف / رأس بقاع مزدوج / كتف ──
    A(-48, 2.44), // الكتف الأيسر
    A(-46, 2.58), // ارتداد → أول خط العنق
    A(-44, 2.28), // القاع الأول (الرأس — أدنى قاع)
    A(-42, 2.4),
    A(-40, 2.3), // القاع الثاني (رأس بقاع مزدوج)
    A(-37, 2.62), // ارتداد → ثاني خط العنق (≈2.60)
    A(-33, 2.42), // الكتف الأيمن
    A(-30, 2.5),
    A(-28, 2.66), // اختراق خط العنق
    A(-24, 2.58), // إعادة اختبار العنق → تحوّل لدعم
    A(-20, 2.64), A(-18, 2.74), A(-15, 2.7), A(-12, 2.68),
    A(-9, 2.66), A(-6, 2.72), A(-5, 2.755), A(-4, 2.735), A(-3, 2.755),
    A(-2, 2.775), A(-1, 2.79), A(0, 3.11),
  ],
  volatility: [
    A(-134, 1.0), A(-90, 1.2), A(-73, 1.4), A(-72, 2.4), A(-66, 2.0),
    A(-50, 1.3), A(-30, 0.72), A(-10, 0.6), A(-4, 0.4), A(-2, 0.36),
    A(-1, 0.34), A(0, 1.8),
  ],
  volume: [
    A(-134, 0.9), A(-73, 1.6), A(-72, 7.5), A(-66, 2.4), A(-50, 1.2),
    A(-30, 0.55), A(-10, 0.5), A(-4, 0.36), A(-2, 0.4), A(-1, 0.45), A(0, 3.4),
  ],
  gaps: [A(-44, -0.05), A(0, 0.026)],
  intraday: [
    A(0, 0), A(8, 0.35), A(16, 0.55), A(26, 0.66), A(38, 0.6), A(50, 0.56),
    A(62, 0.62), A(74, 0.7), A(86, 0.88), A(100, 1),
  ],
  reverseSplit: { d: -72, ratioLabel: "1:20", gapUp: 0.14, spikeMult: 1.75 },
  short: { floatPct: 24.8, daysToCover: 3.1, trend: "falling", deltaPct: -3.2 },
  news: [
    { d: 3, title: "إعلان نتائج الربع المالي — بعد 3 جلسات", source: "تقويم الشركة", sentiment: "neutral" },
    { d: 0, title: "اختراق مستوى 3.00 بحجم تداول 3× المتوسط — رصد مؤسسي", source: "ماسح الحجم", sentiment: "positive" },
    { d: -1, title: "ترقية داخلية: تجميع واضح بعد إعادة الهيكلة", source: "مكتب أبحاث", sentiment: "positive" },
    { d: -3, title: "تحديث تشغيلي: خفض المصروفات 18% بعد التقسيم العكسي", source: "بيان شركة", sentiment: "positive" },
    { d: -6, title: "دعوى جماعية معلقة من مساهمين سابقين", source: "سجلات محاكم", sentiment: "negative" },
    { d: -9, title: "البيع المكشوف يتراجع 3 نقاط خلال أسبوعين", source: "تقرير شورت", sentiment: "positive" },
    { d: -14, title: "إتمام هيكلة الديون قصيرة الأجل بنجاح", source: "بيان شركة", sentiment: "positive" },
  ],
  minuteVol: 0.0013,
  baseVolume: 8200,
  tick: 0.01,
  featured: true,
};

/**
 * ELPW — declining micro-cap → 1:30 reverse split (spike ≈2.33) → dump →
 * floor 0.71 → weak bounce, still fragile near the floor.
 */
const ELPW: SymbolProfile = {
  symbol: "ELPW",
  name: "Elpwire Networks",
  sector: "اتصالات · سهم متناهي الصغر · تقسيم عكسي 1:30",
  anchor: [
    A(-134, 1.25), A(-112, 1.08), A(-94, 0.95), A(-82, 0.87), A(-76, 0.84),
    A(-75, 1.95), // split day close (spike high scripted ≈ 2.33)
    A(-72, 1.72), A(-68, 1.4), A(-60, 1.02), A(-52, 0.86), A(-46, 0.74),
    A(-33, 0.83), A(-24, 0.71), A(-14, 0.735), A(-8, 0.775), A(-5, 0.82),
    A(-3, 0.835), A(-1, 0.782), A(0, 0.748),
  ],
  volatility: [
    A(-134, 1.0), A(-94, 1.2), A(-76, 1.8), A(-75, 3.0), A(-70, 2.6),
    A(-60, 2.0), A(-46, 1.3), A(-30, 0.95), A(-10, 1.1), A(-3, 1.35), A(0, 1.25),
  ],
  volume: [
    A(-134, 0.9), A(-80, 1.8), A(-76, 2.6), A(-75, 8.0), A(-70, 4.0),
    A(-58, 2.2), A(-45, 1.0), A(-25, 0.4), A(-8, 0.7), A(-3, 1.15),
    A(-1, 1.3), A(0, 1.1),
  ],
  gaps: [A(-71, -0.07), A(-60, -0.05), A(0, 0.032)],
  reverseSplit: { d: -75, ratioLabel: "1:30", gapUp: 1.1, spikeMult: 1.32 },
  short: { floatPct: 41.5, daysToCover: 5.8, trend: "rising", deltaPct: 4.4 },
  news: [
    { d: 5, title: "إعلان نتائج الربع — بعد 5 جلسات", source: "تقويم الشركة", sentiment: "neutral" },
    { d: 0, title: "تداول كثيف دون 0.80 — ضغط بيعي مستمر", source: "ماسح الحجم", sentiment: "negative" },
    { d: -2, title: "تمديد مهلة سداد ديون قصيرة الأجل", source: "بيان شركة", sentiment: "positive" },
    { d: -5, title: "خفض تصنيف من مكتب أبحاث صغير", source: "مكتب أبحاث", sentiment: "negative" },
    { d: -8, title: "بيع داخلي: الرئيس التنفيذي يبيع 2% من حصته", source: "إفصاح تنظيمي", sentiment: "negative" },
    { d: -12, title: "رفع البيع المكشوف إلى 41% من الطليق", source: "تقرير شورت", sentiment: "negative" },
  ],
  minuteVol: 0.0022,
  baseVolume: 31000,
  tick: 0.0001,
  featured: true,
};

/**
 * MSGY — decline → 1:10 reverse split (spike ≈8.9) → recovery impulse →
 * correction → wide base 6.4–6.9 under the split-spike target.
 */
const MSGY: SymbolProfile = {
  symbol: "MSGY",
  name: "MessageYard Inc",
  sector: "برمجيات SaaS · سهم متوسط · تقسيم عكسي 1:10",
  anchor: [
    A(-134, 6.3), A(-126, 5.4), A(-120, 4.98), A(-119, 4.95),
    A(-118, 5.08), // split day close (spike high scripted ≈ 8.9)
    A(-114, 4.85), A(-106, 5.05), A(-96, 5.6), A(-88, 6.35), A(-78, 7.42),
    A(-68, 7.82), A(-58, 7.15), A(-48, 6.44), A(-38, 6.72), A(-30, 6.5),
    A(-20, 6.86), A(-12, 6.55), A(-7, 6.68), A(-4, 6.82), A(-2, 6.66),
    A(-1, 6.71), A(0, 6.78),
  ],
  volatility: [
    A(-134, 0.95), A(-119, 1.3), A(-118, 2.6), A(-112, 1.6), A(-100, 1.1),
    A(-70, 1.35), A(-48, 1.2), A(-30, 0.8), A(-12, 0.66), A(-4, 0.7), A(0, 0.72),
  ],
  volume: [
    A(-134, 0.9), A(-119, 1.6), A(-118, 7.0), A(-112, 2.2), A(-100, 1.1),
    A(-70, 1.9), A(-48, 1.4), A(-30, 0.9), A(-12, 0.62), A(-4, 0.7),
    A(-1, 0.78), A(0, 0.72),
  ],
  gaps: [A(-118, 0.05), A(-58, -0.035), A(0, 0.004)],
  reverseSplit: { d: -118, ratioLabel: "1:10", gapUp: 0.05, spikeMult: 1.71 },
  short: { floatPct: 11.2, daysToCover: 1.9, trend: "flat", deltaPct: 0.3 },
  news: [
    { d: 8, title: "يوم المحللين — بعد 8 جلسات", source: "تقويم الشركة", sentiment: "neutral" },
    { d: 0, title: "استقرار فوق دعم 6.50 للأسبوع الثالث", source: "ماسح المستويات", sentiment: "positive" },
    { d: -1, title: "عقود اشتراك جديدة في قطاع التعليم", source: "بيان شركة", sentiment: "positive" },
    { d: -4, title: "منافس يطلق منتجًا مشابهًا — ضغط هامشي محتمل", source: "أخبار قطاع", sentiment: "negative" },
    { d: -10, title: "توسيع اتفاقية توزيع في الخليج", source: "بيان شركة", sentiment: "positive" },
  ],
  minuteVol: 0.00088,
  baseVolume: 4300,
  tick: 0.01,
  featured: true,
};

/** AAPL — mega-cap uptrend, no reverse split (main target = major peak). */
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
    A(-134, 0.95), A(-70, 1.2), A(-40, 1.0), A(-14, 0.85), A(-5, 0.72), A(0, 0.78),
  ],
  volume: [
    A(-134, 1.0), A(-70, 1.5), A(-40, 1.1), A(-14, 0.9), A(-5, 0.75),
    A(-1, 1.05), A(0, 0.88),
  ],
  gaps: [A(-58, -0.012), A(-14, -0.008), A(0, 0.0026)],
  short: { floatPct: 0.7, daysToCover: 1.1, trend: "flat", deltaPct: -0.1 },
  news: [
    { d: 4, title: "حدث إطلاق منتجات جديد — بعد 4 جلسات", source: "تقويم الشركة", sentiment: "neutral" },
    { d: 0, title: "اقتراب من قمم تاريخية بسيولة مؤسسية", source: "ماسح الحجم", sentiment: "positive" },
    { d: -2, title: "تقرير: طلب قوي على الفئة الأعلى", source: "سلسلة توريد", sentiment: "positive" },
    { d: -6, title: "غرامة تنظيمية محتملة في سوق أوروبي", source: "أخبار تنظيمية", sentiment: "negative" },
  ],
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

const NEWS_TEMPLATES: NewsSeed[] = [
  { d: 6, title: "إعلان نتائج الربع المالي — خلال أسبوع", source: "تقويم الشركة", sentiment: "neutral" },
  { d: 0, title: "نشاط تداول أعلى من المتوسط اليوم", source: "ماسح الحجم", sentiment: "positive" },
  { d: -2, title: "تحديث تشغيلي دوري للمستثمرين", source: "بيان شركة", sentiment: "neutral" },
  { d: -5, title: "تغير في ملكية صناديق كبرى", source: "إفصاح تنظيمي", sentiment: "neutral" },
  { d: -8, title: "ضغوط تنافسية على الهوامش", source: "أخبار قطاع", sentiment: "negative" },
  { d: -11, title: "توسعة شراكة توزيع إقليمية", source: "بيان شركة", sentiment: "positive" },
];

interface ProceduralSpec {
  symbol: string;
  name: string;
  sector: string;
  start: number;
  drift: number;
  minuteVol: number;
  baseVolume: number;
  tick: number;
  chop: number;
  shortFloat?: number;
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
    const trend = (spec.drift * spec.start * step) / 134;
    level = Math.max(
      spec.start * 0.25,
      level + trend + level * spec.minuteVol * Math.sqrt(step * 390) * gauss() * (0.55 + spec.chop),
    );
    anchor.push(A(d, +level.toFixed(spec.tick < 0.01 ? 3 : 2)));
    volatility.push(A(d, +(0.75 + rng() * 0.8).toFixed(2)));
    volume.push(A(d, +(0.6 + rng() * 1.1).toFixed(2)));
  }
  anchor.push(A(0, +level.toFixed(spec.tick < 0.01 ? 3 : 2)));
  volatility.push(A(0, +(0.8 + rng() * 0.5).toFixed(2)));
  volume.push(A(0, +(0.8 + rng() * 0.8).toFixed(2)));

  const shortFloat =
    spec.shortFloat ?? +(2 + rng() * 34).toFixed(1);
  const news = NEWS_TEMPLATES.map((t, i) => ({
    ...t,
    d: t.d - Math.floor(rng() * 2),
    title: t.title,
  })).filter((_, i) => i < 5);

  return {
    symbol: spec.symbol,
    name: spec.name,
    sector: spec.sector,
    anchor,
    volatility,
    volume,
    gaps: [],
    short: {
      floatPct: shortFloat,
      daysToCover: +(0.8 + rng() * 5).toFixed(1),
      trend: rng() > 0.6 ? "rising" : rng() > 0.3 ? "falling" : "flat",
      deltaPct: +((rng() - 0.5) * 6).toFixed(1),
    },
    news,
    minuteVol: spec.minuteVol,
    baseVolume: spec.baseVolume,
    tick: spec.tick,
  };
}

const NVDA = procedural({
  symbol: "NVDA", name: "NVIDIA Corp.", sector: "أشباه موصلات",
  start: 128, drift: 0.62, minuteVol: 0.00095, baseVolume: 64000, tick: 0.01, chop: 0.5, shortFloat: 1.4,
});
const TSLA = procedural({
  symbol: "TSLA", name: "Tesla Inc.", sector: "سيارات كهربائية",
  start: 242, drift: 0.08, minuteVol: 0.00125, baseVolume: 51000, tick: 0.01, chop: 0.95, shortFloat: 3.2,
});
const AMD = procedural({
  symbol: "AMD", name: "Advanced Micro Devices", sector: "أشباه موصلات",
  start: 138, drift: 0.3, minuteVol: 0.00105, baseVolume: 33000, tick: 0.01, chop: 0.65, shortFloat: 2.1,
});
const GME = procedural({
  symbol: "GME", name: "GameStop Corp.", sector: "تجزئة · سهم ميمي",
  start: 24.5, drift: -0.12, minuteVol: 0.00165, baseVolume: 21000, tick: 0.01, chop: 0.9, shortFloat: 21.4,
});
const PLTR = procedural({
  symbol: "PLTR", name: "Palantir Technologies", sector: "ذكاء اصطناعي دفاعي",
  start: 32, drift: 0.85, minuteVol: 0.00115, baseVolume: 48000, tick: 0.01, chop: 0.6, shortFloat: 4.8,
});
const SOFI = procedural({
  symbol: "SOFI", name: "SoFi Technologies", sector: "تقنية مالية",
  start: 8.4, drift: 0.4, minuteVol: 0.00135, baseVolume: 39000, tick: 0.01, chop: 0.75, shortFloat: 12.6,
});

export const PROFILES: Record<string, SymbolProfile> = {
  THH, ELPW, MSGY, AAPL, NVDA, TSLA, AMD, GME, PLTR, SOFI,
};

export const UNIVERSE = Object.values(PROFILES);

export function getProfile(symbol: string): SymbolProfile {
  return PROFILES[symbol.toUpperCase()] ?? THH;
}
