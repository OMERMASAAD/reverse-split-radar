/**
 * Pattern Recognition Engine — Head & Shoulders family (النموذج المرجعي)
 *
 * Scans the recent swing triples for:
 *   1. Inverted Head & Shoulders — left shoulder / head (often a DOUBLE BOTTOM)
 *      / right shoulder, neckline above → bullish reversal
 *   2. Head & Shoulders — bearish mirror
 *
 * Calibrated for the reference model: shoulders symmetric within 4.5%,
 * head depth ≥ 1.2%, pattern completion within the last 60 sessions.
 */

import type { Candle, PatternResult, SwingPoint } from "../types";
import { findSwings } from "../indicators";

interface Ctx {
  candles: Candle[];
  lows: SwingPoint[];
  highs: SwingPoint[];
  lastIdx: number;
  obvRising: boolean;
  rsiValue: number;
}

function highBetween(ctx: Ctx, fromIdx: number, toIdx: number): SwingPoint | null {
  const cands = ctx.highs.filter((h) => h.index > fromIdx && h.index < toIdx);
  if (cands.length) return cands.reduce((a, b) => (b.price > a.price ? b : a));
  let best: SwingPoint | null = null;
  for (let i = fromIdx + 1; i < toIdx; i++) {
    const p = ctx.candles[i].high;
    if (!best || p > best.price)
      best = { index: i, time: ctx.candles[i].time, price: p, kind: "high" };
  }
  return best;
}

function lowBetween(ctx: Ctx, fromIdx: number, toIdx: number): SwingPoint | null {
  const cands = ctx.lows.filter((l) => l.index > fromIdx && l.index < toIdx);
  if (cands.length) return cands.reduce((a, b) => (b.price < a.price ? b : a));
  let best: SwingPoint | null = null;
  for (let i = fromIdx + 1; i < toIdx; i++) {
    const p = ctx.candles[i].low;
    if (!best || p < best.price)
      best = { index: i, time: ctx.candles[i].time, price: p, kind: "low" };
  }
  return best;
}

/** double-bottom inside the head zone (القاع الأول + القاع الثاني) */
function headDoubleBottomNote(ctx: Ctx, fromIdx: number, toIdx: number): string | null {
  const headLows = ctx.lows.filter((l) => l.index > fromIdx && l.index < toIdx);
  for (let i = 0; i < headLows.length - 1; i++) {
    for (let j = i + 1; j < headLows.length; j++) {
      const a = headLows[i];
      const b = headLows[j];
      if (
        Math.abs(a.price - b.price) / Math.min(a.price, b.price) <= 0.025 &&
        Math.abs(a.index - b.index) >= 3
      ) {
        return `الرأس قاع مزدوج: القاع الأول ${a.price.toFixed(3)} والثاني ${b.price.toFixed(3)} — قاعان متتاليان يبنيان منطقة الارتكاز.`;
      }
    }
  }
  return null;
}

function detectInvertedHS(ctx: Ctx): PatternResult | null {
  const pool = ctx.lows.slice(-9);
  // scan triples (non-consecutive allowed — the head may itself be a double
  // bottom, i.e. two swing lows sitting between shoulder and shoulder)
  for (let k = pool.length - 1; k >= 2; k--) {
    for (let j = k - 1; j >= 1; j--) {
      for (let i = j - 1; i >= 0; i--) {
        const [l1, l2, l3] = [pool[i], pool[j], pool[k]];
        if (l2.index - l1.index < 3 || l3.index - l2.index < 3) continue;
        if (ctx.lastIdx - l3.index > 60) continue;
        if (!(l2.price < l1.price && l2.price < l3.price)) continue;
        // l2 must be the lowest low of the whole formation
        const between = pool.filter((p) => p.index > l1.index && p.index < l3.index);
        if (between.some((p) => p.price < l2.price)) continue;
        const shoulderSym = Math.abs(l1.price - l3.price) / Math.min(l1.price, l3.price);
        if (shoulderSym > 0.045) continue;
        const headDepth = (Math.min(l1.price, l3.price) - l2.price) / l2.price;
        if (headDepth < 0.012) continue;

        const h1 = highBetween(ctx, l1.index, l2.index);
        const h2 = highBetween(ctx, l2.index, l3.index);
        if (!h1 || !h2) continue;
        const neckline = (h1.price + h2.price) / 2;
        if (neckline <= Math.max(l1.price, l3.price)) continue;
        // stale-pattern guard: neckline must stay within reach of price
        const lastClose = ctx.candles[ctx.lastIdx].close;
        if (neckline > lastClose * 1.3) continue;

        const headNote = headDoubleBottomNote(ctx, l1.index, l3.index);
        let confidence = 74;
        confidence += (0.045 - shoulderSym) * 350;
        confidence += Math.min(headDepth * 200, 10);
        if (headNote) confidence += 5;
        if (ctx.obvRising) confidence += 6;
        confidence = Math.max(35, Math.min(97, Math.round(confidence)));
        const spanBars = l3.index - l1.index;

        return {
          kind: "INVERTED_HEAD_SHOULDERS",
          label: "رأس وكتفين مقلوب",
          emoji: "🏔️",
          description: `الكتف الأيسر ${l1.price.toFixed(3)}، الرأس ${l2.price.toFixed(3)}، الكتف الأيمن ${l3.price.toFixed(3)} — اكتمل النموذج خلال ${spanBars} جلسة. خط العنق ${neckline.toFixed(2)} هو مستوى التفعيل: اختراقه ثم إعادة اختباره يفتح الهدف بعمق الرأس (${(neckline + (neckline - l2.price)).toFixed(2)}).`,
          confidence,
          neckline,
          depth: neckline - l2.price,
          points: [l1, h1, l2, h2, l3],
          startIndex: l1.index,
          headNote,
          spanBars,
        };
      }
    }
  }
  return null;
}

function detectHeadShoulders(ctx: Ctx): PatternResult | null {
  const pool = ctx.highs.slice(-9);
  for (let k = pool.length - 1; k >= 2; k--) {
    for (let j = k - 1; j >= 1; j--) {
      for (let i = j - 1; i >= 0; i--) {
        const [h1, h2, h3] = [pool[i], pool[j], pool[k]];
        if (h2.index - h1.index < 3 || h3.index - h2.index < 3) continue;
        if (ctx.lastIdx - h3.index > 60) continue;
        if (!(h2.price > h1.price && h2.price > h3.price)) continue;
        const between = pool.filter((p) => p.index > h1.index && p.index < h3.index);
        if (between.some((p) => p.price > h2.price)) continue;
        const shoulderSym = Math.abs(h1.price - h3.price) / Math.max(h1.price, h3.price);
        if (shoulderSym > 0.045) continue;
        const headDepth = (h2.price - Math.max(h1.price, h3.price)) / h2.price;
        if (headDepth < 0.012) continue;

        const t1 = lowBetween(ctx, h1.index, h2.index);
        const t2 = lowBetween(ctx, h2.index, h3.index);
        if (!t1 || !t2) continue;
        const neckline = (t1.price + t2.price) / 2;
        if (neckline >= Math.min(h1.price, h3.price)) continue;

        let confidence = 70;
        confidence += (0.045 - shoulderSym) * 350;
        confidence += Math.min(headDepth * 200, 10);
        confidence = Math.max(35, Math.min(96, Math.round(confidence)));

        return {
          kind: "HEAD_SHOULDERS",
          label: "رأس وكتفين",
          emoji: "⛰️",
          description: `الرأس (القمة الأعلى) عند ${h2.price.toFixed(3)} بين كتفين — نموذج انعكاس هابط. خط العنق ${neckline.toFixed(2)} هو مستوى الحسم، وكسره يفتح هبوطًا بعمق الرأس (${(neckline - (h2.price - neckline)).toFixed(2)}).`,
          confidence,
          neckline,
          depth: h2.price - neckline,
          points: [h1, t1, h2, t2, h3],
          startIndex: h1.index,
          headNote: null,
          spanBars: h3.index - h1.index,
        };
      }
    }
  }
  return null;
}

export interface PatternInputs {
  candles: Candle[];
  obvRising?: boolean;
  rsiValue?: number;
  fractalK?: number;
}

/** Returns the H&S-family pattern in force, or null when none is confirmed. */
export function detectReversalPattern(input: PatternInputs): PatternResult | null {
  const { candles } = input;
  const k = input.fractalK ?? 2;
  const swings = findSwings(candles, k);
  const ctx: Ctx = {
    candles,
    lows: swings.filter((s) => s.kind === "low"),
    highs: swings.filter((s) => s.kind === "high"),
    lastIdx: candles.length - 1,
    obvRising: input.obvRising ?? false,
    rsiValue: input.rsiValue ?? 50,
  };
  return detectInvertedHS(ctx) ?? detectHeadShoulders(ctx);
}
