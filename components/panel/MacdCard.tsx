"use client";

import { Zap } from "lucide-react";
import type { AnalysisResult } from "@/lib/types";
import { CardShell, StatePill, StatRow } from "./CardShell";
import { HistogramChart } from "./MiniChart";

const STATE_META: Record<
  string,
  { label: string; tone: "bull" | "bear" | "gold" | "muted" }
> = {
  BULLISH_CROSS: { label: "▲ تقاطع صاعد", tone: "bull" },
  BULLISH_EXPANSION: { label: "▲ توسع صاعد", tone: "bull" },
  BULLISH_FADE: { label: "▲ صاعد يخفت", tone: "gold" },
  BEARISH_CROSS: { label: "▼ تقاطع هابط", tone: "bear" },
  BEARISH_EXPANSION: { label: "▼ توسع هابط", tone: "bear" },
  NEUTRAL: { label: "≈ محايد يتعافى", tone: "muted" },
};

export default function MacdCard({ analysis }: { analysis: AnalysisResult }) {
  const { macd } = analysis;
  const n = macd.hist.length;
  const from = Math.max(0, n - 70);
  const meta = STATE_META[macd.state] ?? STATE_META.NEUTRAL;

  const macdLine = macd.macd.slice(from).map((v) => (isNaN(v) ? 0 : v));
  const sigLine = macd.signal.slice(from).map((v) => (isNaN(v) ? 0 : v));
  const hist = macd.hist.slice(from).map((v) => (isNaN(v) ? 0 : v));

  const last = macd.hist[n - 1];
  const prev = macd.hist[n - 2];

  return (
    <CardShell
      icon={Zap}
      title="زخم MACD"
      step="القاعدة 03 · تقاطع 12 / 26 / 9"
      accent="#f59e0b"
      right={<StatePill tone={meta.tone}>{meta.label}</StatePill>}
    >
      <div dir="ltr" className="h-14 w-full">
        <HistogramChart hist={hist} macdLine={macdLine} signalLine={sigLine} height={56} />
      </div>
      <div dir="ltr" className="num mt-1 flex justify-between text-[9px] tracking-widest text-faint">
        <span className="text-sky">— MACD</span>
        <span className="text-gold">- - SIGNAL</span>
        <span>الهستوجرام {macd.expanding ? "يتوسع ⏩" : "مستقر"}</span>
      </div>

      <div className="mt-2 border-t border-line-soft/60 pt-1.5">
        <StatRow
          label="الهستوجرام"
          value={`${last >= 0 ? "+" : ""}${last.toFixed(4)} (${last >= prev ? "▲" : "▼"} ${(last - prev).toFixed(4)})`}
          valueClass={last >= 0 ? "text-bull-soft" : "text-bear-soft"}
        />
        <StatRow
          label="التقاطع"
          value={
            macd.freshCross
              ? "تقاطع جديد مع خط الإشارة ≤ 3 شموع"
              : last >= 0
                ? "فوق خط الإشارة"
                : "تحت خط الإشارة"
          }
          valueClass={macd.freshCross ? "text-bull-soft" : last >= 0 ? "text-ink" : "text-bear-soft"}
        />
        <StatRow
          label="الحكم على الزخم"
          value={
            macd.state.startsWith("BULLISH")
              ? macd.expanding
                ? "تسارع للأعلى"
                : "صاعد يفقد قوته"
              : macd.state === "NEUTRAL"
                ? "تجميع"
                : "ضغط هابط"
          }
          valueClass={
            macd.state === "BULLISH_EXPANSION" || macd.state === "BULLISH_CROSS"
              ? "text-bull-soft"
              : macd.state.startsWith("BEARISH")
                ? "text-bear-soft"
                : "text-gold"
          }
        />
      </div>
    </CardShell>
  );
}
