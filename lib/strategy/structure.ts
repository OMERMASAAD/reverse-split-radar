/**
 * Market Structure Engine — استراتيجية الارتكاز لأسهم التقسيم العكسي والهابطة
 *
 * Runs on the DAILY frame (sessions) and answers the structural questions:
 *   1. ثبات القاع   — has price held above the approved floor ≥5 sessions?
 *   2. سلوك القيعان — flat bottom or higher low?
 *   3. الاختبار وإعادة الاختبار + سحب السيولة (liquidity sweep)
 *   4. النماذج      — Head & Shoulders family + neckline
 *   5. الأهداف      — split-spike pivotal target + staged falling-candle highs
 */

import type {
  BottomBehavior,
  BottomInfo,
  Candle,
  SwingPoint,
  TargetLevel,
} from "../types";
import { findSwings, rsi as rsiCalc } from "../indicators";
import { detectReversalPattern } from "./patterns";
import type { PatternResult } from "../types";
import type { SymbolProfile } from "../market/profiles";

export interface StructureResult {
  bottom: BottomInfo;
  behavior: {
    kind: BottomBehavior;
    label: string;
    ok: boolean;
    detail: string;
    points: SwingPoint[];
  };
  testRetest: {
    testedResistance: boolean;
    resistanceLevel: number | null;
    testDetail: string;
    retestedBottom: boolean;
    retestDetail: string;
    sweep: boolean;
    sweepDetail: string;
    sweepTime: number | null;
    /** neckline breakout & its re-test (the reference model sequence) */
    neckBreak: boolean;
    neckBreakTime: number | null;
    neckRetest: boolean;
    neckRetestTime: number | null;
    neckRetestDetail: string;
  };
  pattern: PatternResult | null;
  targets: {
    main: TargetLevel;
    stages: TargetLevel[];
    supports: TargetLevel[];
    neckline: number | null;
  };
  rsi: {
    series: number[];
    value: number;
    exitOversold: boolean;
    crossRecent: boolean;
    signalTime: number | null;
  };
}

const BOTTOM_WINDOW = 75; // sessions scanned for the capitulation floor

/** Cluster nearby levels (within tol) keeping the highest of each cluster. */
function clusterLevels(
  levels: { price: number; time: number; index: number }[],
  tol: number,
): { price: number; time: number; index: number }[] {
  const sorted = [...levels].sort((a, b) => a.price - b.price);
  const out: { price: number; time: number; index: number }[] = [];
  for (const lv of sorted) {
    const prev = out[out.length - 1];
    if (prev && Math.abs(lv.price - prev.price) / prev.price <= tol) {
      if (lv.price > prev.price) out[out.length - 1] = lv;
    } else {
      out.push(lv);
    }
  }
  return out;
}

export function analyzeStructure(daily: Candle[], profile: SymbolProfile): StructureResult {
  const n = daily.length;
  const lastIdx = n - 1;
  const close = daily[lastIdx].close;

  /* ---------------- 1) the approved floor (القاع المعتمد) ---------------- */
  const winStart = Math.max(0, n - BOTTOM_WINDOW);
  let bottomIdx = winStart;
  for (let i = winStart; i < n; i++) {
    if (daily[i].low < daily[bottomIdx].low) bottomIdx = i;
  }
  const bottomLevel = daily[bottomIdx].low;

  // consecutive sessions holding above the floor since it was carved
  let holdsSessions = 0;
  for (let i = bottomIdx + 1; i < n; i++) {
    if (daily[i].close >= bottomLevel) holdsSessions++;
    else break;
  }
  // if the floor is very recent, count closes at/above it including the run-up
  const bottom: BottomInfo = {
    level: bottomLevel,
    index: bottomIdx,
    time: daily[bottomIdx].time,
    holdsSessions,
    held: holdsSessions >= 5,
  };

  /* ---------------- 2) bottom behaviour (سلوك القيعان) ---------------- */
  const swings = findSwings(daily, 2);
  const lows = swings.filter((s) => s.kind === "low");
  const highs = swings.filter((s) => s.kind === "high");

  // consider swing lows carved at/after the floor window
  const recentLows = lows.filter((l) => l.index >= bottomIdx - 3).slice(-3);
  let behavior: StructureResult["behavior"];
  if (recentLows.length >= 2) {
    const [l1, l2] = recentLows.slice(-2);
    const diff = (l2.price - l1.price) / l1.price;
    if (diff > 0.004) {
      behavior = {
        kind: "HIGHER_LOW",
        label: "قاع أعلى من قاع (Higher Low)",
        ok: true,
        detail: `القاع الأخير ${l2.price.toFixed(3)} أعلى من السابق ${l1.price.toFixed(3)} بفارق +${(diff * 100).toFixed(1)}% — المشترون يدافعون عند مستويات صاعدة.`,
        points: [l1, l2],
      };
    } else if (diff >= -0.02) {
      behavior = {
        kind: "FLAT_BOTTOM",
        label: "قاع ثابت / مزدوج",
        ok: true,
        detail: `اختباران للقاع صمدا عند ${l1.price.toFixed(3)} و ${l2.price.toFixed(3)} (فارق ${(diff * 100).toFixed(1)}%) — أرضية شراء مؤكدة.`,
        points: [l1, l2],
      };
    } else {
      behavior = {
        kind: "LOWER_LOW",
        label: "قاع أدنى من قاع (Lower Low)",
        ok: false,
        detail: `القاع الأخير ${l2.price.toFixed(3)} أدنى من السابق ${l1.price.toFixed(3)} — السلوك الانحداري ما زال قائمًا.`,
        points: [l1, l2],
      };
    }
  } else {
    behavior = {
      kind: "NONE",
      label: "غير محسوم",
      ok: false,
      detail: "لا توجد قيعان محورية كافية بعد القاع المعتمد للحكم على السلوك.",
      points: recentLows,
    };
  }

  /* ---------------- 3) test & re-test + liquidity sweep ---------------- */
  // nearest overhead resistance = lowest clustered swing-high above price
  const overhead = clusterLevels(
    highs.filter((h) => h.price > close * 1.005).map((h) => ({ price: h.price, time: h.time, index: h.index })),
    0.02,
  );
  const resistanceLevel = overhead.length ? overhead[0].price : null;

  let testedResistance = false;
  let testDetail = "لم يُرصد صعود لاختبار المقاومة القريبة خلال آخر 20 جلسة.";
  if (resistanceLevel != null) {
    const from = Math.max(0, n - 20);
    for (let i = from; i < n; i++) {
      if (daily[i].high >= resistanceLevel * 0.985) {
        testedResistance = true;
        testDetail = `جلسة ${new Date(daily[i].time * 1000).getUTCDate()}/${new Date(daily[i].time * 1000).getUTCMonth() + 1} لامست المقاومة ${resistanceLevel.toFixed(3)} (ضمن 1.5%).`;
        break;
      }
    }
  } else {
    testedResistance = false;
    testDetail = "لا توجد مقاومة قريبة مرصودة فوق السعر الحالي.";
  }

  // re-test of the floor: a pullback that came within 3% of the floor and closed above it
  let retestedBottom = false;
  let retestDetail = "لم يعد السعر لاختبار القاع المعتمد بعد تكوينه.";
  for (let i = bottomIdx + 3; i < n; i++) {
    const approached = daily[i].low <= bottomLevel * 1.03;
    const heldClose = daily[i].close >= bottomLevel;
    if (approached && heldClose) {
      retestedBottom = true;
      retestDetail = `إعادة اختبار للقاع ${bottomLevel.toFixed(3)}: لامس ${daily[i].low.toFixed(3)} وأغلق فوقه عند ${daily[i].close.toFixed(3)} — القاع صامد.`;
      break;
    }
  }

  // liquidity sweep: wick below the floor with an immediate close back above
  let sweep = false;
  let sweepTime: number | null = null;
  let sweepDetail = "لا أثر لسحب سيولة أسفل القاع المعتمد.";
  for (let i = Math.max(0, bottomIdx - 5); i < n; i++) {
    if (daily[i].low < bottomLevel * 0.995 && daily[i].close > bottomLevel) {
      sweep = true;
      sweepTime = daily[i].time;
      sweepDetail = `سحب سيولة مرصود: الفتيل ضرب ${daily[i].low.toFixed(3)} أسفل القاع ثم أُغلق فورًا فوقه عند ${daily[i].close.toFixed(3)} — مصيدة بيعية ارتدت.`;
      break;
    }
  }

  /* ---------------- 3b) neckline break → re-test sequence ---------------- */
  const pattern0 = detectReversalPattern({ candles: daily, fractalK: 2 });
  let neckBreak = false;
  let neckBreakTime: number | null = null;
  let neckRetest = false;
  let neckRetestTime: number | null = null;
  let neckRetestDetail = "لم يُكسر خط العنق بعد — الاختراق هو مفتاح التفعيل.";
  if (pattern0) {
    const nl = pattern0.neckline;
    // the breakout can only count AFTER the right shoulder completes
    const shoulderIdx = pattern0.points[pattern0.points.length - 1].index;
    let breakIdx = -1;
    for (let i = shoulderIdx + 1; i < n; i++) {
      if (breakIdx < 0) {
        if (daily[i].close > nl && daily[i - 1].close <= nl) {
          breakIdx = i;
          neckBreak = true;
          neckBreakTime = daily[i].time;
        }
      } else if (
        i > breakIdx + 1 &&
        daily[i].low <= nl * 1.015 &&
        daily[i].close >= nl * 0.99
      ) {
        // the break must have HELD between breakout and re-test (no collapse
        // back through the neckline in between — a bull trap, not a retest)
        let held = true;
        for (let m = breakIdx; m < i; m++) {
          if (daily[m].close < nl * 0.96) {
            held = false;
            break;
          }
        }
        if (!held) continue;
        neckRetest = true;
        neckRetestTime = daily[i].time;
        neckRetestDetail = `إعادة اختبار خط العنق ${nl.toFixed(3)}: ارتد من ${daily[i].low.toFixed(3)} وأغلق فوقه — تحوّل العنق من مقاومة إلى دعم (تأكيد النموذج).`;
        break;
      }
    }
    if (neckBreak && !neckRetest) {
      neckRetestDetail = `اختراق خط العنق ${nl.toFixed(3)} حدث — بانتظار إعادة الاختبار للدخول الآمن.`;
    }
    // failed breakout guard: price back below the neckline now → no valid break
    const lastClose = daily[n - 1].close;
    if (neckBreak && lastClose < nl * 0.97) {
      neckBreak = false;
      neckBreakTime = null;
      neckRetest = false;
      neckRetestTime = null;
      neckRetestDetail = `محاولة اختراق خط العنق ${nl.toFixed(3)} فشلت — عاد السعر أدناه (${lastClose.toFixed(3)}). النموذج قائم لكن التفعيل لم يكتمل.`;
    }
  }

  /* ---------------- 4) patterns — H&S family ---------------- */
  const pattern = pattern0;

  /* ---------------- 5) targets & resistances ---------------- */
  // pivotal target = reverse-split spike candle high (or major peak)
  let main: TargetLevel;
  const rs = profile.reverseSplit;
  let spikeIdx = -1;
  if (rs) {
    spikeIdx = n - 1 + rs.d;
    if (spikeIdx < 0 || spikeIdx >= n) spikeIdx = -1;
  }
  if (spikeIdx >= 0) {
    main = {
      price: daily[spikeIdx].high,
      label: `قمة شمعة التقسيم العكسي ${rs!.ratioLabel}`,
      time: daily[spikeIdx].time,
      kind: "main",
    };
  } else {
    // no split: major swing peak of the window
    let peakIdx = winStart;
    for (let i = winStart; i < n; i++) if (daily[i].high > daily[peakIdx].high) peakIdx = i;
    main = {
      price: daily[peakIdx].high,
      label: "القمة المحورية الرئيسية",
      time: daily[peakIdx].time,
      kind: "main",
    };
  }

  // staged targets = clustered swing highs between price and the pivotal target
  const stageCandidates = highs
    .filter((h) => h.price > close * 1.01 && h.price < main.price * 0.985)
    .map((h) => ({ price: h.price, time: h.time, index: h.index }));
  const clustered = clusterLevels(stageCandidates, 0.025).slice(-4);
  const stages: TargetLevel[] = clustered.map((lv, i) => ({
    price: lv.price,
    time: lv.time,
    kind: "stage",
    label:
      spikeIdx >= 0 && lv.index < spikeIdx
        ? `قمة شمعة بيعية (قبل التقسيم) — مقاومة ${i + 1}`
        : `قمة ارتداد هابطة — مقاومة ${i + 1}`,
  }));

  // supports: the approved floor (+ base shelf when distinct)
  const supports: TargetLevel[] = [
    { price: bottomLevel, label: "القاع المعتمد (أرضية الاستراتيجية)", time: daily[bottomIdx].time, kind: "support" },
  ];
  const baseStart = Math.max(bottomIdx + 1, n - 15);
  let baseLow = Infinity;
  let baseLowTime = 0;
  for (let i = baseStart; i < n; i++) {
    if (daily[i].low < baseLow) {
      baseLow = daily[i].low;
      baseLowTime = daily[i].time;
    }
  }
  if (isFinite(baseLow) && baseLow > bottomLevel * 1.015) {
    supports.push({ price: baseLow, label: "دعم القاعدة الحالي", time: baseLowTime, kind: "support" });
  }

  /* ---------------- RSI exit-oversold signal (daily) ---------------- */
  const closes = daily.map((c) => c.close);
  const rsiSeries = rsiCalc(closes, 14);
  const rsiValue = rsiSeries[n - 1];
  let exitOversold = false;
  let crossRecent = false;
  let signalTime: number | null = null;
  for (let i = Math.max(1, n - 40); i < n; i++) {
    if (!isNaN(rsiSeries[i]) && !isNaN(rsiSeries[i - 1]) && rsiSeries[i - 1] < 30 && rsiSeries[i] >= 30) {
      exitOversold = true;
      signalTime = daily[i].time;
      crossRecent = n - 1 - i <= 10;
    }
  }
  // a healthy climb through 40 after oversold also counts as the positive signal
  const climbedTo40 = exitOversold && rsiValue >= 40;

  return {
    bottom,
    behavior,
    testRetest: {
      testedResistance,
      resistanceLevel,
      testDetail,
      retestedBottom,
      retestDetail,
      sweep,
      sweepDetail,
      sweepTime,
      neckBreak,
      neckBreakTime,
      neckRetest,
      neckRetestTime,
      neckRetestDetail,
    },
    pattern,
    targets: {
      main,
      stages,
      supports,
      neckline: pattern ? pattern.neckline : null,
    },
    rsi: {
      series: rsiSeries,
      value: rsiValue,
      exitOversold: exitOversold || climbedTo40,
      crossRecent,
      signalTime,
    },
  };
}
