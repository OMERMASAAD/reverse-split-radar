/**
 * Pattern Recognition Engine
 *
 * Detects, in priority order:
 *   1. Inverted Head & Shoulders (3 swing lows, middle = head)
 *   2. Double Bottom (2 swing lows within tolerance)
 *   3. Higher-Lows ladder (3+ ascending swing lows)
 *   4. Fallback: consolidation range (highest high / lowest low of last N bars)
 *
 * Each detection yields a neckline (breakout trigger), a structural pivot low
 * (stop-loss anchor) and the measured-move depth used for T1/T2 targets.
 */

import type { Candle, PatternResult, SwingPoint } from "../types";
import { findSwings } from "../indicators";

interface Ctx {
  candles: Candle[];
  lows: SwingPoint[];
  highs: SwingPoint[];
  lastIdx: number;
  lastClose: number;
  obvRising: boolean;
  rightVolRatio: number; // volume on the right leg vs left leg
  squeezeActive: boolean;
  rsiValue: number;
}

function highBetween(ctx: Ctx, fromIdx: number, toIdx: number): SwingPoint | null {
  const cands = ctx.highs.filter((h) => h.index > fromIdx && h.index < toIdx);
  if (cands.length) return cands.reduce((a, b) => (b.price > a.price ? b : a));
  // no confirmed swing high → use rolling max of highs in between
  let best: SwingPoint | null = null;
  for (let i = fromIdx + 1; i < toIdx; i++) {
    const p = ctx.candles[i].high;
    if (!best || p > best.price) best = { index: i, time: ctx.candles[i].time, price: p, kind: "high" };
  }
  return best;
}

function detectInvertedHS(ctx: Ctx): PatternResult | null {
  const lows = ctx.lows;
  if (lows.length < 3) return null;
  const [l1, l2, l3] = lows.slice(-3);
  const recent = ctx.lastIdx - l3.index <= 45;
  if (!recent) return null;
  const headDeeper = l2.price < l1.price && l2.price < l3.price;
  if (!headDeeper) return null;
  const shoulderSym = Math.abs(l1.price - l3.price) / Math.min(l1.price, l3.price);
  if (shoulderSym > 0.035) return null;
  const headDepth = (Math.min(l1.price, l3.price) - l2.price) / l2.price;
  if (headDepth < 0.012) return null;

  const h1 = highBetween(ctx, l1.index, l2.index);
  const h2 = highBetween(ctx, l2.index, l3.index);
  if (!h1 || !h2) return null;
  const neckline = Math.max(h1.price, h2.price);
  if (neckline <= Math.max(l1.price, l3.price)) return null;

  let confidence = 76;
  confidence += (0.035 - shoulderSym) * 400; // tighter shoulders → better
  confidence += Math.min(headDepth * 200, 10);
  if (l3.index > l1.index && ctx.rightVolRatio > 1.05) confidence += 6;
  if (ctx.obvRising) confidence += 6;
  if (ctx.squeezeActive) confidence += 4;
  if (ctx.rsiValue >= 80) confidence -= 8;
  confidence = Math.max(35, Math.min(97, Math.round(confidence)));

  return {
    kind: "INVERTED_HEAD_SHOULDERS",
    label: "رأس وكتفين مقلوب",
    emoji: "🏔️",
    description: `الرأس (أدنى قاع) عند ${l2.price.toFixed(3)} بين كتفين متماثلين. خط الرقبة ${neckline.toFixed(2)} هو نقطة التفعيل — الحركة المقيسة تتوقع امتدادًا بعمق الرأس كاملًا فوقه.`,
    confidence,
    neckline,
    pivotLow: l2.price,
    depth: neckline - l2.price,
    points: [l1, h1, l2, h2, l3],
    startIndex: l1.index,
  };
}

function detectDoubleBottom(ctx: Ctx): PatternResult | null {
  const lows = ctx.lows;
  if (lows.length < 2) return null;
  const [l1, l2] = lows.slice(-2);
  const recent = ctx.lastIdx - l2.index <= 40;
  if (!recent) return null;
  if (l2.index - l1.index < 6) return null;
  const diff = Math.abs(l1.price - l2.price) / Math.min(l1.price, l2.price);
  if (diff > 0.028) return null;

  const h = highBetween(ctx, l1.index, l2.index);
  if (!h) return null;
  const neckline = h.price;
  const pivotLow = Math.min(l1.price, l2.price);
  if (neckline - pivotLow <= 0) return null;
  const depthRatio = (neckline - pivotLow) / pivotLow;
  if (depthRatio < 0.01) return null;

  let confidence = 72;
  confidence += (0.028 - diff) * 500; // tighter second bottom → better
  if (ctx.rightVolRatio > 1.05) confidence += 5;
  if (ctx.obvRising) confidence += 7;
  if (ctx.squeezeActive) confidence += 5;
  if (ctx.rsiValue >= 80) confidence -= 8;
  confidence = Math.max(30, Math.min(96, Math.round(confidence)));

  return {
    kind: "DOUBLE_BOTTOM",
    label: "قاع مزدوج",
    emoji: "🩻",
    description: `اختباران للقاع ${pivotLow.toFixed(3)} صمدا بفارق ${(diff * 100).toFixed(1)}% فقط — البائعون استُنفدوا. إغلاقٌ فوق ${neckline.toFixed(2)} يؤكد الانعكاس ويفتح الحركة المقيسة للأعلى.`,
    confidence,
    neckline,
    pivotLow,
    depth: neckline - pivotLow,
    points: [l1, h, l2],
    startIndex: l1.index,
  };
}

function detectHigherLows(ctx: Ctx): PatternResult | null {
  const lows = ctx.lows.slice(-4);
  if (lows.length < 3) return null;
  const last3 = lows.slice(-3);
  const recent = ctx.lastIdx - last3[2].index <= 55;
  if (!recent) return null;
  const ascending =
    last3[1].price > last3[0].price * 1.001 && last3[2].price > last3[1].price * 1.001;
  if (!ascending) return null;

  // neckline = most recent swing high after the last low (or rolling high)
  const hs = ctx.highs.filter((h) => h.index > last3[2].index - 3);
  let neckline: number;
  if (hs.length) {
    neckline = hs[hs.length - 1].price;
  } else {
    neckline = -Infinity;
    for (let i = last3[1].index; i < ctx.candles.length; i++) {
      neckline = Math.max(neckline, ctx.candles[i].high);
    }
  }
  if (neckline <= last3[2].price) return null;

  // stop anchor = most recent structural low of the ladder
  const pivotLow = last3[2].price;
  let confidence = 62;
  confidence += Math.min(((last3[2].price - last3[0].price) / last3[0].price) * 260, 12);
  if (ctx.obvRising) confidence += 7;
  if (ctx.rightVolRatio > 1.05) confidence += 4;
  if (ctx.rsiValue >= 80) confidence -= 8;
  confidence = Math.max(28, Math.min(92, Math.round(confidence)));

  return {
    kind: "HIGHER_LOWS",
    label: "سلّم قيعان صاعدة",
    emoji: "🪜",
    description: `المشترون رفعوا القاع مع كل تصحيح (${last3.map((l) => l.price.toFixed(2)).join(" ← ")}). سلّم الطلب سليم — الضغط فوق ${neckline.toFixed(2)} يمدّد التسلسل الصاعد.`,
    confidence,
    neckline,
    pivotLow,
    depth: neckline - last3[2].price,
    points: last3,
    startIndex: last3[0].index,
  };
}

function fallbackRange(ctx: Ctx): PatternResult {
  const lookback = Math.min(30, ctx.candles.length);
  const slice = ctx.candles.slice(-lookback);
  const neckline = Math.max(...slice.map((c) => c.high));
  const pivotLow = Math.min(...slice.map((c) => c.low));
  const brokeUp = ctx.lastClose >= neckline * 0.998;
  return {
    kind: "RANGE",
    label: brokeUp ? "اختراق نطاق (بدون نموذج كلاسيكي)" : "نطاق تجميع",
    emoji: brokeUp ? "💥" : "📦",
    description: brokeUp
      ? `لا يوجد نموذج انعكاسي كلاسيكي — السعر يخترق صندوق ${pivotLow.toFixed(2)} – ${neckline.toFixed(2)} على قوة الزخم الخام. تداول استعادة المستوى ولا تطارد الامتداد.`
      : `لا يوجد هيكل انعكاسي مؤكد بعد. السعر ينضغط داخل ${pivotLow.toFixed(2)} – ${neckline.toFixed(2)}؛ انتظر اختراقًا مقبولًا قبل المخاطرة.`,
    confidence: 40,
    neckline,
    pivotLow,
    depth: neckline - pivotLow,
    points: [],
    startIndex: ctx.candles.length - lookback,
  };
}

export interface PatternInputs {
  candles: Candle[];
  obvRising: boolean;
  rightVolRatio: number;
  squeezeActive: boolean;
  rsiValue: number;
  /** fractal strength: 2 for intraday, 3+ for higher timeframes */
  fractalK?: number;
}

export function detectPattern(input: PatternInputs): PatternResult {
  const { candles } = input;
  const k = input.fractalK ?? 3;
  const swings = findSwings(candles, k);
  const lows = swings.filter((s) => s.kind === "low");
  const highs = swings.filter((s) => s.kind === "high");
  const lastIdx = candles.length - 1;

  const ctx: Ctx = {
    candles,
    lows,
    highs,
    lastIdx,
    lastClose: candles[lastIdx]?.close ?? 0,
    obvRising: input.obvRising,
    rightVolRatio: input.rightVolRatio,
    squeezeActive: input.squeezeActive,
    rsiValue: input.rsiValue,
  };

  return (
    detectInvertedHS(ctx) ??
    detectDoubleBottom(ctx) ??
    detectHigherLows(ctx) ??
    fallbackRange(ctx)
  );
}
