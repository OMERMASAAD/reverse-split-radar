"use client";

import { ClipboardCheck } from "lucide-react";
import type { AnalysisResult } from "@/lib/types";
import { CardShell } from "./CardShell";

function YesNo({ ok, partial }: { ok: boolean; partial?: boolean }) {
  return (
    <span
      className={`rounded-md border px-2 py-0.5 text-[10px] font-black ${
        ok
          ? "border-bull/50 bg-bull/10 text-bull-soft"
          : partial
            ? "border-gold/50 bg-gold/10 text-gold"
            : "border-bear/50 bg-bear/10 text-bear-soft"
      }`}
    >
      {ok ? "نعم" : partial ? "جزئيًا" : "لا"}
    </span>
  );
}

function SubPill({ label, ok }: { label: string; ok: boolean }) {
  return (
    <span
      className={`flex items-center gap-1 rounded-md border px-1.5 py-0.5 text-[9.5px] font-semibold ${
        ok ? "border-bull/40 bg-bull/8 text-bull-soft" : "border-line bg-well text-faint"
      }`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${ok ? "bg-bull" : "bg-faint"}`} />
      {label}: {ok ? "نعم" : "لا"}
    </span>
  );
}

export default function StructureCard({ analysis }: { analysis: AnalysisResult }) {
  const { checklist, structure } = analysis;
  const tr = structure.testRetest;
  const rows = checklist.slice(0, 4); // monitoring rows live in the verdict card

  return (
    <CardShell
      icon={ClipboardCheck}
      title="الفحص الهيكلي والسلوكي — نعم / لا"
      step="شروط استراتيجية الارتكاز على الفريم اليومي"
      accent="#38bdf8"
    >
      <ul className="space-y-3">
        {rows.map((item, i) => (
          <li key={item.id} className="rounded-lg border border-line-soft/60 bg-well/40 px-3 py-2.5">
            <div className="flex items-center justify-between gap-2">
              <span className="text-[11px] font-extrabold tracking-wide text-ink">
                {i + 1}. {item.label}
              </span>
              <YesNo ok={item.state === "yes"} partial={item.state === "partial"} />
            </div>
            <p className="mt-1 text-[10.5px] leading-relaxed text-muted">{item.detail}</p>

            {item.id === "testretest" && (
              <div className="mt-2 flex flex-wrap gap-1.5">
                <SubPill label="اختبار المقاومة" ok={tr.testedResistance} />
                <SubPill label="إعادة اختبار القاع" ok={tr.retestedBottom} />
                <SubPill label="سحب سيولة" ok={tr.sweep} />
                <SubPill label="اختراق العنق" ok={tr.neckBreak} />
                <SubPill label="إعادة اختبار العنق" ok={tr.neckRetest} />
              </div>
            )}
            {item.id === "testretest" && tr.sweep && (
              <p className="mt-1.5 text-[10px] leading-relaxed text-bull-soft/90">{tr.sweepDetail}</p>
            )}
            {item.id === "testretest" && tr.neckBreak && (
              <p className="mt-1 text-[10px] leading-relaxed text-sky/90">{tr.neckRetestDetail}</p>
            )}

            {item.id === "pattern" && structure.pattern?.headNote && (
              <p className="mt-1.5 rounded-md border border-bull/30 bg-bull/8 px-2 py-1 text-[10px] leading-relaxed text-bull-soft">
                🩻 {structure.pattern.headNote}
              </p>
            )}
          </li>
        ))}
      </ul>
    </CardShell>
  );
}
