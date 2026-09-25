"use client";

import { Anchor } from "lucide-react";
import type { AnalysisResult } from "@/lib/types";
import { CardShell, StatePill, StatRow } from "./CardShell";
import { fmtPct, fmtPrice } from "@/lib/format";

export default function VwapCard({ analysis }: { analysis: AnalysisResult }) {
  const { vwap, quote } = analysis;
  const precision = quote.last < 1 ? 4 : 2;
  // clamp the distance bar to ±3%
  const pos = Math.max(-3, Math.min(3, vwap.distancePct));
  const pct = ((pos + 3) / 6) * 100;

  return (
    <CardShell
      icon={Anchor}
      title="شرط VWAP — متوسط السعر المرجّح"
      step="القاعدة 01 · انحياز المؤسسات"
      accent="#fb923c"
      right={
        vwap.above ? (
          <StatePill tone="bull">▲ فوق VWAP</StatePill>
        ) : (
          <StatePill tone="bear">▼ تحت VWAP</StatePill>
        )
      }
    >
      <div className="flex items-baseline justify-between">
        <span className="num text-[22px] font-black" style={{ color: vwap.distancePct >= 0 ? "#34d399" : "#f87171" }}>
          {fmtPct(vwap.distancePct)}
        </span>
        <span className="text-[10.5px] text-faint">
          السعر <b className="num">{fmtPrice(quote.last, precision)}</b> مقابل{" "}
          {vwap.mode === "ANCHORED" ? "VWAP المرساة" : "VWAP الجلسة"}{" "}
          <b className="num" style={{ color: "#fb923c" }}>{fmtPrice(vwap.value, precision)}</b>
        </span>
      </div>

      {/* distance meter — centre = VWAP */}
      <div dir="ltr" className="relative mt-3 h-2 rounded-full bg-gradient-to-r from-bear/35 via-well to-bull/35">
        <div className="absolute left-1/2 top-1/2 h-4 w-px -translate-y-1/2 bg-vwap/80" />
        <div
          className="absolute top-1/2 h-3.5 w-3.5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-abyss transition-all duration-500"
          style={{
            left: `${pct}%`,
            background: vwap.above ? "#10b981" : "#ef4444",
            boxShadow: `0 0 10px ${vwap.above ? "#10b98199" : "#ef444499"}`,
          }}
        />
      </div>
      <div dir="ltr" className="num mt-1.5 flex justify-between text-[9px] tracking-widest text-faint">
        <span>-3%</span>
        <span className="text-vwap">VWAP</span>
        <span>+3%</span>
      </div>

      <div className="mt-2 border-t border-line-soft/60 pt-1.5">
        <StatRow
          label={vwap.mode === "ANCHORED" ? "نقطة الترسية" : "إعادة ضبط الجلسة"}
          value={vwap.mode === "ANCHORED" ? "القاع الهيكلي" : "يوميًا 09:30 نيويورك"}
          valueClass="text-muted"
        />
        <StatRow
          label="الخلاصة"
          value={vwap.above ? "المشترون يسيطرون" : "البائعون يسيطرون"}
          valueClass={vwap.above ? "text-bull-soft" : "text-bear-soft"}
        />
      </div>
    </CardShell>
  );
}
