"use client";

import { ScanSearch } from "lucide-react";
import type { AnalysisResult } from "@/lib/types";
import { CardShell, StatePill, StatRow } from "./CardShell";
import { fmtDay, fmtPrice } from "@/lib/format";

const KIND_AR: Record<string, string> = {
  INVERTED_HEAD_SHOULDERS: "رأس وكتفين مقلوب",
  DOUBLE_BOTTOM: "قاع مزدوج",
  HIGHER_LOWS: "قيعان صاعدة",
  RANGE: "نطاق تجميع",
};

export default function PatternCard({ analysis }: { analysis: AnalysisResult }) {
  const { pattern, quote } = analysis;
  const precision = quote.last < 1 ? 4 : 2;
  const confTone =
    pattern.confidence >= 65 ? "bull" : pattern.confidence >= 45 ? "gold" : "bear";

  return (
    <CardShell
      icon={ScanSearch}
      title="محرك التعرف على النماذج السعرية"
      step="القاعدة 05 · تحليل الهياكل"
      accent="#10b981"
      right={<StatePill tone={confTone}>ثقة {pattern.confidence}%</StatePill>}
    >
      <div className="flex items-center gap-3 rounded-xl border border-line-soft/70 bg-well/60 px-3.5 py-3">
        <span className="text-2xl">{pattern.emoji}</span>
        <div className="min-w-0">
          <div className="text-[13.5px] font-black tracking-wide text-ink">
            {pattern.label}
          </div>
          <div className="mt-0.5 text-[10px] font-semibold tracking-wide text-faint">
            النموذج المرصود: {KIND_AR[pattern.kind] ?? pattern.kind}
          </div>
        </div>
      </div>

      {/* confidence bar */}
      <div className="mt-3" dir="ltr">
        <div className="h-1.5 overflow-hidden rounded-full bg-well">
          <div
            className="h-full rounded-full transition-all duration-700"
            style={{
              width: `${pattern.confidence}%`,
              background:
                pattern.confidence >= 65
                  ? "linear-gradient(90deg,#059669,#34d399)"
                  : pattern.confidence >= 45
                    ? "linear-gradient(90deg,#b45309,#fbbf24)"
                    : "linear-gradient(90deg,#b91c1c,#f87171)",
            }}
          />
        </div>
      </div>

      <p className="mt-3 text-[11.5px] leading-relaxed text-muted">{pattern.description}</p>

      {/* detected swing points */}
      {pattern.points.length > 0 && (
        <div className="mt-3 rounded-lg border border-line-soft/60 bg-abyss/40 px-3 py-2">
          <div className="mb-1.5 text-[9.5px] font-bold tracking-wide text-faint">
            النقاط المحورية المكتشفة
          </div>
          <div className="flex flex-wrap gap-1.5">
            {pattern.points.map((p, i) => (
              <span
                key={i}
                className={`rounded-md border px-2 py-1 text-[10px] font-semibold ${
                  p.kind === "low"
                    ? "border-bull/35 bg-bull/10 text-bull-soft"
                    : "border-bear/35 bg-bear/10 text-bear-soft"
                }`}
              >
                {p.kind === "low" ? "قاع" : "قمة"}{" "}
                <b className="num">{fmtPrice(p.price, precision)}</b> ·{" "}
                <span className="text-faint">{fmtDay(p.time)}</span>
              </span>
            ))}
          </div>
        </div>
      )}

      <div className="mt-2 border-t border-line-soft/60 pt-1.5">
        <StatRow label="خط الرقبة / نقطة التفعيل" value={fmtPrice(pattern.neckline, precision)} valueClass="text-bear-soft" />
        <StatRow label="القاع الهيكلي (مرساة الوقف)" value={fmtPrice(pattern.pivotLow, precision)} valueClass="text-bull-soft" />
        <StatRow label="عمق الحركة المقيسة" value={fmtPrice(pattern.depth, precision)} valueClass="text-ink" />
      </div>
    </CardShell>
  );
}
