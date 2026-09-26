"use client";

import { Target } from "lucide-react";
import type { AnalysisResult } from "@/lib/types";
import { CardShell, StatePill } from "./CardShell";
import { fmtDay, fmtPct, fmtPrice } from "@/lib/format";

export default function TargetsCard({ analysis }: { analysis: AnalysisResult }) {
  const { targets, quote, split, hasSplit } = analysis;
  const precision = quote.last < 1 ? 4 : 2;
  const dist = (v: number) => ((v - quote.last) / quote.last) * 100;

  const ladder = [
    {
      key: "main",
      label: targets.main.label,
      price: targets.main.price,
      time: targets.main.time,
      cls: "border-gold/50 bg-gold/10",
      txt: "text-gold",
      emoji: "🎯",
    },
    ...targets.stages
      .slice()
      .reverse()
      .map((s, i) => ({
        key: `s${i}`,
        label: s.label,
        price: s.price,
        time: s.time,
        cls: "border-bear/35 bg-bear/8",
        txt: "text-bear-soft",
        emoji: "🧱",
      })),
    ...(targets.neckline != null
      ? [
          {
            key: "neck",
            label: "خط العنق — مستوى التفعيل",
            price: targets.neckline,
            time: null as number | null,
            cls: "border-bear/50 bg-bear/10",
            txt: "text-bear-soft",
            emoji: "⛔",
          },
        ]
      : []),
    {
      key: "now",
      label: "السعر الحالي",
      price: quote.last,
      time: null as number | null,
      cls: "border-sky/50 bg-sky/10",
      txt: "text-sky",
      emoji: "📍",
    },
    ...targets.supports.map((s, i) => ({
      key: `sup${i}`,
      label: s.label,
      price: s.price,
      time: s.time,
      cls: "border-bull/40 bg-bull/8",
      txt: "text-bull-soft",
      emoji: "🛡️",
    })),
  ].sort((a, b) => b.price - a.price);

  return (
    <CardShell
      icon={Target}
      title="الأهداف والمقاومات — خريطة الطريق"
      step={
        hasSplit && split
          ? `تقسيم عكسي ${split.ratioLabel} · قمة شمعة التقسيم هي الهدف المحوري`
          : "لا يوجد تقسيم عكسي — الهدف المحوري هو القمة الرئيسية"
      }
      accent="#f59e0b"
      right={
        hasSplit && split ? (
          <StatePill tone="gold">تقسيم {split.ratioLabel}</StatePill>
        ) : (
          <StatePill tone="muted">بدون تقسيم</StatePill>
        )
      }
    >
      <div className="space-y-1.5">
        {ladder.map((row) => (
          <div key={row.key} className={`rounded-lg border px-3 py-2 ${row.cls}`}>
            <div className="flex items-center justify-between gap-2">
              <span className="text-[10.5px] font-bold tracking-wide text-muted">
                {row.emoji} {row.label}
                {row.time != null && (
                  <span className="ms-1.5 text-[9px] text-faint">({fmtDay(row.time)})</span>
                )}
              </span>
              <span className="flex items-baseline gap-2">
                <span className={`num text-[13px] font-black ${row.txt}`}>
                  {fmtPrice(row.price, precision)}
                </span>
                {row.key !== "now" && (
                  <span className="num w-16 text-end text-[9.5px] text-faint">
                    {fmtPct(dist(row.price), 1)}
                  </span>
                )}
              </span>
            </div>
          </div>
        ))}
      </div>

      <p className="mt-2.5 text-[10px] leading-relaxed text-faint">
        الهدف المحوري = قمة شمعة التقسيم العكسي: مستوى الحسم للانعكاس الكامل. الأهداف
        المرحلية = قمم الشموع البيعية السابقة ومقاومات الارتداد — تُختبر تباعًا، وكل
        اختراق يُعاد اختباره قبل الامتداد.
      </p>
    </CardShell>
  );
}
