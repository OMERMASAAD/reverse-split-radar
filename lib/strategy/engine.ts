/**
 * APEX Strategy Engine — استراتيجية الارتكاز لأسهم التقسيم العكسي والهابطة
 *
 * Orchestrates the single-stock dashboard:
 *  · EMA 20 / 30 / 50 (mandatory overlays)
 *  · VWAP anchored at the strategy floor — MONITOR ONLY (never a reject rule)
 *  · RSI pane + positive exit-oversold signal (30 → 40+)
 *  · market-structure checks (floor hold, bottoms behaviour, test & re-test,
 *    liquidity sweep, H&S family + neckline)
 *  · reverse-split targets (spike-candle pivotal target + staged resistances)
 *  · verdict badge, weighted score, short-interest & news wire
 */

import type {
  AnalysisResult,
  Candle,
  ChecklistItem,
  NewsItem,
  Quote,
  RsiZone,
  StatusCode,
  StatusResult,
  Timeframe,
} from "../types";
import { anchoredVwap, ema, rsi as rsiCalc } from "../indicators";
import { analyzeStructure } from "./structure";
import { getProfile } from "../market/profiles";

function lastValid(arr: number[]): number {
  for (let i = arr.length - 1; i >= 0; i--) if (!isNaN(arr[i])) return arr[i];
  return NaN;
}

function lastValidIdx(arr: (number | null)[], from: number): number {
  for (let i = from; i >= 0; i--) if (arr[i] != null && !isNaN(arr[i] as number)) return i;
  return -1;
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
  let prevClose = open;
  if (start > 0) prevClose = source[start - 1].close;
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

/** neckline break + re-test on the CHART timeframe (drives on-chart markers) */
function tfNecklineEvents(candles: Candle[], neckline: number | null) {
  if (neckline == null) return { breakTime: null as number | null, retestTime: null as number | null };
  const n = candles.length;
  let breakIdx = -1;
  let breakTime: number | null = null;
  let retestTime: number | null = null;
  const from = Math.max(1, n - 80);
  for (let i = from; i < n; i++) {
    if (breakIdx < 0) {
      if (candles[i].close > neckline && candles[i - 1].close <= neckline) {
        breakIdx = i;
        breakTime = candles[i].time;
      }
    } else if (
      i > breakIdx + 1 &&
      candles[i].low <= neckline * 1.015 &&
      candles[i].close >= neckline * 0.99
    ) {
      retestTime = candles[i].time;
      break;
    }
  }
  return { breakTime, retestTime };
}

export function analyzeStock(
  symbol: string,
  timeframe: Timeframe,
  candles: Candle[],
  daily: Candle[],
  minutes: Candle[],
): AnalysisResult {
  const profile = getProfile(symbol);
  const n = candles.length;
  const dn = daily.length;
  const closes = candles.map((c) => c.close);
  const last = candles[n - 1];
  const dLast = daily[dn - 1];

  /* ---------------- structure on the daily frame ---------------- */
  const structure = analyzeStructure(daily, profile);
  const floor = structure.bottom.level;

  /* ---------------- mandatory EMAs ---------------- */
  const emas = {
    ema20: ema(closes, 20),
    ema30: ema(closes, 30),
    ema50: ema(closes, 50),
  };

  /* ---------------- VWAP — anchored at the strategy floor (monitor only) */
  let anchorIdx = -1;
  for (let i = n - 1; i >= 0; i--) {
    if (candles[i].low <= floor * 1.01) {
      anchorIdx = i;
      break;
    }
  }
  if (anchorIdx < 0) {
    anchorIdx = Math.max(0, n - 90);
    let lo = Infinity;
    for (let i = anchorIdx; i < n; i++) {
      if (candles[i].low < lo) {
        lo = candles[i].low;
        anchorIdx = i;
      }
    }
  }
  const vwapSeries = anchoredVwap(candles, anchorIdx);
  const vIdx = lastValidIdx(vwapSeries, n - 1);
  const vwapValue = vIdx >= 0 ? (vwapSeries[vIdx] as number) : last.close;
  const vwapAbove = last.close >= vwapValue;
  const vwapDistPct = vwapValue ? ((last.close - vwapValue) / vwapValue) * 100 : 0;

  /* ---------------- RSI: chart pane + daily strategy signal ---------------- */
  const rsiSeries = rsiCalc(closes, 14);
  const rsiValue = lastValid(rsiSeries);
  let rsiZone: RsiZone = "BULLISH";
  if (rsiValue >= 80) rsiZone = "OVERBOUGHT";
  else if (rsiValue >= 70) rsiZone = "STRONG";
  else if (rsiValue >= 50) rsiZone = "BULLISH";
  else if (rsiValue >= 30) rsiZone = "WEAK";
  else rsiZone = "OVERSOLD";

  /* ---------------- verdict (no VWAP rejection anywhere) ---------------- */
  const brokenRecently =
    daily[dn - 1].close < floor * 0.99 ||
    daily[dn - 2]?.close < floor * 0.99 ||
    daily[dn - 3]?.close < floor * 0.99;

  const nlNow = structure.targets.neckline;
  const breakoutValid =
    structure.testRetest.neckBreak && (nlNow === null || daily[dn - 1].close > nlNow);

  /* ---------------- events on the chart timeframe ---------------- */
  const events = breakoutValid
    ? tfNecklineEvents(candles, nlNow)
    : { breakTime: null, retestTime: null };

  let code: StatusCode;
  if (brokenRecently) code = "BROKEN";
  else if (structure.bottom.held && structure.behavior.ok && breakoutValid)
    code = "BREAKOUT";
  else if (structure.bottom.held && structure.behavior.ok) code = "ANCHORED";
  else code = "BUILDING";

  const verdictByCode: Record<StatusCode, StatusResult> = {
    BREAKOUT: {
      code: "BREAKOUT",
      label: "اختراق مؤكد — النموذج فعّال",
      emoji: "🚀",
      detail: `القاع المعتمد ${floor.toFixed(3)} صامد، وسلوك القيعان إيجابي، وخط العنق ${structure.targets.neckline?.toFixed(2)} تم اختراقه. التسلسل المرجعي مكتمل: اختراق ← إعادة اختبار ← امتداد صاعد نحو الأهداف المرحلية ثم الهدف المحوري.`,
    },
    ANCHORED: {
      code: "ANCHORED",
      label: "ارتكاز مؤكد — بانتظار التفعيل",
      emoji: "⚓",
      detail: `السعر مرتكز فوق القاع المعتمد ${floor.toFixed(3)} لـ ${structure.bottom.holdsSessions} جلسة متتالية بسلوك قيعان إيجابي. المراقبة: اختراق خط العنق ${structure.targets.neckline ? structure.targets.neckline.toFixed(2) : (structure.testRetest.resistanceLevel ?? dLast.close).toFixed(2)} ثم إعادة اختباره.`,
    },
    BUILDING: {
      code: "BUILDING",
      label: "قيد بناء الارتكاز",
      emoji: "⏳",
      detail: `القاع المعتمد ${floor.toFixed(3)} مرصود لكن شروط الثبات/سلوك القيعان لم تكتمل بعد (${structure.bottom.holdsSessions} جلسة ثبات). لا دخول قبل خمسة جلسات ثبات على الأقل فوق الأرضية.`,
    },
    BROKEN: {
      code: "BROKEN",
      label: "كسر القاع — خارج الاستراتيجية",
      emoji: "⚠️",
      detail: `الإغلاق تحت القاع المعتمد ${floor.toFixed(3)} — فرضية الارتكاز ملغية حتى إشعار آخر. أي ارتداد حالي مجرد تصحيح داخل الاتجاه الهابط.`,
    },
  };
  const verdict = verdictByCode[code];

  /* ---------------- checklist (نعم / لا) ---------------- */
  const tr = structure.testRetest;
  const neckConfirmed = tr.neckBreak && tr.neckRetest;
  const subYes =
    [tr.testedResistance, tr.retestedBottom, tr.sweep].filter(Boolean).length +
    (tr.neckBreak ? 1 : 0) +
    (tr.neckRetest ? 1 : 0);
  const checklist: ChecklistItem[] = [
    {
      id: "floor",
      label: "ثبات القاع — ≥ 5 جلسات فوق القاع المعتمد",
      state: structure.bottom.held ? "yes" : "no",
      detail: `${structure.bottom.holdsSessions} جلسة إغلاق متتالية فوق ${floor.toFixed(3)} (القاع محفور قبل ${dn - 1 - structure.bottom.index} جلسة).`,
    },
    {
      id: "behavior",
      label: "سلوك القيعان — قاع ثابت أو قاع أعلى",
      state: structure.behavior.ok ? "yes" : "no",
      detail: structure.behavior.detail,
    },
    {
      id: "testretest",
      label: "الاختبار والاختبار المضاد + سحب السيولة",
      state: neckConfirmed || subYes >= 2 ? "yes" : subYes === 1 ? "partial" : "no",
      detail: `اختبار المقاومة: ${tr.testedResistance ? "نعم" : "لا"} · إعادة اختبار القاع: ${tr.retestedBottom ? "نعم" : "لا"} · سحب سيولة: ${tr.sweep ? "نعم" : "لا"} · اختراق العنق: ${tr.neckBreak ? "نعم" : "لا"} · إعادة اختبار العنق: ${tr.neckRetest ? "نعم" : "لا"}`,
    },
    {
      id: "pattern",
      label: "نماذج الحركة السعرية — رأس وكتفين (أو مقلوب) وخط العنق",
      state: !structure.pattern
        ? "no"
        : structure.pattern.kind === "INVERTED_HEAD_SHOULDERS"
          ? structure.pattern.confidence >= 60
            ? "yes"
            : "partial"
          : "no",
      detail: structure.pattern
        ? structure.pattern.kind === "INVERTED_HEAD_SHOULDERS"
          ? `${structure.pattern.label} · ثقة ${structure.pattern.confidence}% · خط العنق ${structure.pattern.neckline.toFixed(3)}${structure.pattern.headNote ? " · الرأس قاع مزدوج" : ""}`
          : `تنبيه: ${structure.pattern.label} (هابط) · خط العنق ${structure.pattern.neckline.toFixed(3)} — لا يدعم اتجاه الارتكاز الصاعد.`
        : "لا يوجد نموذج رأس وكتفين مؤكد حاليًا على اليومي.",
    },
    {
      id: "rsi-signal",
      label: "إشارة RSI — الخروج من التشبع البيعي (30 ← 40+)",
      state: structure.rsi.exitOversold
        ? structure.rsi.value >= 40
          ? "yes"
          : "partial"
        : "no",
      detail: structure.rsi.exitOversold
        ? `RSI اليومي ${structure.rsi.value.toFixed(1)} — خرج من تحت 30 وصعد ${structure.rsi.value >= 40 ? "فوق 40 (إشارة إيجابية مكتملة)" : "نحو 40 (إيجابية قيد التكوين)"}.`
        : `RSI اليومي ${structure.rsi.value.toFixed(1)} — لم يُرصد خروج من التشبع البيعي خلال آخر 40 جلسة.`,
    },
    {
      id: "vwap-monitor",
      label: "مراقبة VWAP (إيجابية ممتازة — غير مانعة)",
      state: vwapAbove ? "yes" : "no",
      detail: vwapAbove
        ? `السعر أعلى VWAP المرساة بالقاع بنسبة +${vwapDistPct.toFixed(2)}% — استعادة إيجابية ممتازة تُعزز الارتكاز.`
        : `السعر أدنى VWAP المرساة بنسبة ${vwapDistPct.toFixed(2)}% — ملاحظة مراقبة فقط، لا ترفض السهم وفق الاستراتيجية.`,
    },
  ];

  /* ---------------- weighted score ---------------- */
  const weights: Record<string, number> = {
    floor: 25,
    behavior: 20,
    testretest: 20,
    pattern: 15,
    "rsi-signal": 10,
    "vwap-monitor": 10,
  };
  let acc = 0;
  let total = 0;
  for (const item of checklist) {
    const w = weights[item.id] ?? 10;
    total += w;
    acc += w * (item.state === "yes" ? 1 : item.state === "partial" ? 0.5 : 0);
  }
  const score = Math.round((acc / total) * 100);

  /* ---------------- split + news + short ---------------- */
  const rs = profile.reverseSplit;
  const splitIdx = rs ? dn - 1 + rs.d : -1;
  const split =
    rs && splitIdx >= 0 && splitIdx < dn
      ? {
          ratioLabel: rs.ratioLabel,
          time: daily[splitIdx].time,
          spikeHigh: structure.targets.main.price,
        }
      : null;

  const newsTime = dLast.time;
  const news: NewsItem[] = profile.news.map((seed) => ({
    d: seed.d,
    time: newsTime + seed.d * 86400,
    title: seed.title,
    source: seed.source,
    sentiment: seed.sentiment,
    upcoming: seed.d > 0,
  }));

  const quote = buildQuote(minutes, candles);

  return {
    symbol,
    symbolName: profile.name,
    sector: profile.sector,
    timeframe,
    candles,
    daily,
    quote,
    hasSplit: split != null,
    split,
    emas,
    vwap: {
      series: vwapSeries,
      value: vwapValue,
      distancePct: vwapDistPct,
      above: vwapAbove,
      mode: "ANCHORED",
    },
    rsi: {
      series: rsiSeries,
      value: rsiValue,
      zone: rsiZone,
      dailyValue: structure.rsi.value,
      dailySeries: structure.rsi.series,
      exitOversold: structure.rsi.exitOversold,
      crossRecent: structure.rsi.crossRecent,
      signalTime: structure.rsi.signalTime,
    },
    structure,
    targets: structure.targets,
    checklist,
    verdict,
    score,
    events,
    short: profile.short,
    news,
    newsTime,
  };
}
