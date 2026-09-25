"use client";

import { Crosshair, Target } from "lucide-react";
import type { AnalysisResult } from "@/lib/types";
import { CardShell, StatePill, StatRow } from "./CardShell";
import { fmtPct, fmtPrice } from "@/lib/format";

export default function TradePlanCard({ analysis }: { analysis: AnalysisResult }) {
  const { plan, quote, pattern } = analysis;
  const precision = quote.last < 1 ? 4 : 2;
  const pctFrom = (v: number) => ((v - plan.entry) / plan.entry) * 100;

  const ladder = [
    { label: "الهدف الثاني · امتداد 1.618", price: plan.t2, tone: "text-bull-soft", border: "border-bull/40", bg: "bg-bull/10", dash: true, emoji: "🎯" },
    { label: "الهدف الأول · الحركة المقيسة", price: plan.t1, tone: "text-bull-soft", border: "border-bull/40", bg: "bg-bull/10", dash: true, emoji: "🎯" },
    { label: "خط الرقبة / المقاومة", price: pattern.neckline, tone: "text-bear-soft", border: "border-bear/40", bg: "bg-bear/5", dash: false, emoji: "⛔" },
    { label: plan.breakoutMode ? "الدخول · أمر شراء معلق" : "الدخول · تدفق السوق", price: plan.entry, tone: "text-sky", border: "border-sky/50", bg: "bg-sky/10", dash: false, emoji: "📍" },
    { label: "وقف الخسارة · القاع الهيكلي", price: plan.stop, tone: "text-bear-soft", border: "border-bear/50", bg: "bg-bear/10", dash: true, emoji: "🛑" },
  ].sort((a, b) => b.price - a.price);

  return (
    <CardShell
      icon={Target}
      title="خطة التداول الآلية"
      step="مخطط التنفيذ"
      accent="#34d399"
      right={
        <StatePill tone={plan.breakoutMode ? "gold" : "bull"}>
          {plan.breakoutMode ? "بانتظار الاختراق" : "الاختراق قيد التنفيذ"}
        </StatePill>
      }
    >
      {/* price ladder */}
      <div className="space-y-1.5">
        {ladder.map((row) => (
          <div
            key={row.label}
            className={`flex items-center justify-between rounded-lg border px-3 py-2 ${row.border} ${row.bg}`}
          >
            <span className="text-[10.5px] font-bold tracking-wide text-muted">
              {row.emoji} {row.label}
              {row.dash && <span className="ms-1.5 text-faint">- - -</span>}
            </span>
            <span className="flex items-baseline gap-2">
              <span className={`num text-[13px] font-black ${row.tone}`}>
                {fmtPrice(row.price, precision)}
              </span>
              <span className="num w-14 text-end text-[9.5px] text-faint">
                {fmtPct(pctFrom(row.price), 1)}
              </span>
            </span>
          </div>
        ))}
      </div>

      <div className="mt-3 grid grid-cols-3 gap-2">
        <div className="rounded-lg border border-line-soft bg-well/60 px-2.5 py-2 text-center">
          <div className="text-[9.5px] font-bold tracking-wide text-faint">عائد/مخاطرة ← هدف 1</div>
          <div className="num mt-0.5 text-[15px] font-black text-bull-soft">
            {plan.rr1.toFixed(2)}
          </div>
        </div>
        <div className="rounded-lg border border-line-soft bg-well/60 px-2.5 py-2 text-center">
          <div className="text-[9.5px] font-bold tracking-wide text-faint">عائد/مخاطرة ← هدف 2</div>
          <div className="num mt-0.5 text-[15px] font-black text-bull-soft">
            {plan.rr2.toFixed(2)}
          </div>
        </div>
        <div className="rounded-lg border border-line-soft bg-well/60 px-2.5 py-2 text-center">
          <div className="text-[9.5px] font-bold tracking-wide text-faint">المخاطرة</div>
          <div className="num mt-0.5 text-[15px] font-black text-bear-soft">
            {plan.riskPct.toFixed(1)}%
          </div>
        </div>
      </div>

      <div className="mt-2 border-t border-line-soft/60 pt-1.5">
        <StatRow
          label="هامش ATR(14) لكل شمعة"
          value={`± ${fmtPrice(analysis.atr, precision)}`}
          valueClass="text-muted"
        />
        <StatRow
          label="أسهم إشارات الشراء على الشارت"
          value={`${analysis.signals.length} في النافذة`}
          valueClass={analysis.signals.length ? "text-bull-soft" : "text-faint"}
        />
        <StatRow
          label="وضع الخطة"
          value={plan.breakoutMode ? "شراء معلق فوق خط الرقبة" : "استمرار اتجاه قائم"}
          valueClass="text-sky"
        />
      </div>

      <p className="mt-2 flex items-start gap-1.5 text-[10px] leading-relaxed text-faint">
        <Crosshair className="mt-px h-3 w-3 shrink-0" />
        خطة ورقية محاكاة — من إنتاج محرك الاستراتيجية تلقائيًا، وليست نصيحة استثمارية.
      </p>
    </CardShell>
  );
}
