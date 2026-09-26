"use client";

import { Gauge } from "lucide-react";
import type { AnalysisResult } from "@/lib/types";
import { CardShell, StatePill } from "./CardShell";
import { LinePairChart } from "./MiniChart";

const ZONE_META = {
  OVERBOUGHT: { label: "تشبع شرائي", tone: "violet" as const, color: "#a78bfa" },
  STRONG: { label: "قوي / ساخن", tone: "gold" as const, color: "#f59e0b" },
  BULLISH: { label: "نطاق صاعد", tone: "bull" as const, color: "#10b981" },
  WEAK: { label: "ضعيف", tone: "muted" as const, color: "#8ba0bd" },
  OVERSOLD: { label: "تشبع بيعي", tone: "sky" as const, color: "#38bdf8" },
};

export default function RsiCard({ analysis }: { analysis: AnalysisResult }) {
  const { rsi } = analysis;
  const meta = ZONE_META[rsi.zone];
  const v = Math.max(0, Math.min(100, rsi.value));
  const from = Math.max(0, rsi.dailySeries.length - 70);
  const series = rsi.dailySeries.slice(from).map((x) => (isNaN(x) ? 50 : x));
  const flat40 = series.map(() => 40);

  return (
    <CardShell
      icon={Gauge}
      title="مؤشر القوة النسبية RSI"
      step="الإيجابية: الخروج من التشبع البيعي (فوق 30 ← 40+)"
      accent="#a78bfa"
      right={<StatePill tone={meta.tone}>{meta.label}</StatePill>}
    >
      <div className="flex items-end justify-between">
        <span
          className="num text-[30px] font-black leading-none"
          style={{ color: meta.color, textShadow: `0 0 24px ${meta.color}44` }}
        >
          {v.toFixed(1)}
        </span>
        <span className="pb-1 text-[10px] font-semibold text-faint">
          RSI اليومي {rsi.dailyValue.toFixed(1)} · لوحة الشارت تعرض الفريم الحالي
        </span>
      </div>

      <div dir="ltr" className="relative mt-3 h-2.5 overflow-hidden rounded-full">
        <div
          className="absolute inset-0"
          style={{
            background:
              "linear-gradient(90deg, #38bdf8 0%, #38bdf8 30%, #64748b 30%, #64748b 50%, #10b981 50%, #10b981 70%, #f59e0b 70%, #f59e0b 80%, #a78bfa 80%, #a78bfa 100%)",
            opacity: 0.5,
          }}
        />
        <div
          className="absolute top-1/2 h-5 w-1.5 -translate-x-1/2 -translate-y-1/2 rounded-full border border-abyss transition-all duration-500"
          style={{ left: `${v}%`, background: meta.color, boxShadow: `0 0 12px ${meta.color}` }}
        />
      </div>
      <div dir="ltr" className="num mt-1.5 flex justify-between text-[9px] tracking-widest text-faint">
        <span>0</span>
        <span className="text-sky">30</span>
        <span>40</span>
        <span>50</span>
        <span>70</span>
        <span>100</span>
      </div>

      <div dir="ltr" className="mt-2 h-12 w-full">
        <LinePairChart a={series} b={flat40} colorA="#a78bfa" colorB="#64748b" height={48} fill={false} />
      </div>

      {rsi.exitOversold ? (
        <div className="mt-2 flex items-start gap-2 rounded-lg border border-bull/45 bg-bull/10 px-3 py-2">
          <span className="text-[13px]">✅</span>
          <p className="text-[11px] leading-relaxed text-bull-soft">
            <b>إشارة إيجابية:</b> RSI خرج من منطقة التشبع البيعي (صعد فوق 30)
            {rsi.dailyValue >= 40 ? " واستقر فوق 40 — الزخم الشرائي يتسلّم القيادة." : " ويتقدم نحو 40 — الإيجابية قيد التكوين."}
          </p>
        </div>
      ) : (
        <p className="mt-2 text-[10.5px] leading-relaxed text-muted">
          لم يُرصد خروج من التشبع البيعي خلال آخر 40 جلسة — الإشارة الإيجابية تظهر فور
          صعود RSI فوق 30 باتجاه 40+.
        </p>
      )}
    </CardShell>
  );
}
