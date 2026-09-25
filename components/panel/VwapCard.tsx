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
      title="VWAP CONDITION"
      step="RULE 01 · INSTITUTIONAL BIAS"
      accent="#fb923c"
      right={
        vwap.above ? (
          <StatePill tone="bull">▲ ABOVE</StatePill>
        ) : (
          <StatePill tone="bear">▼ BELOW</StatePill>
        )
      }
    >
      <div className="flex items-baseline justify-between">
        <span className="num text-[22px] font-black" style={{ color: vwap.distancePct >= 0 ? "#34d399" : "#f87171" }}>
          {fmtPct(vwap.distancePct)}
        </span>
        <span className="num text-[10.5px] text-faint">
          PRICE {fmtPrice(quote.last, precision)} vs {vwap.mode === "ANCHORED" ? "AVWAP" : "VWAP"}{" "}
          <b className="text-vwap">{fmtPrice(vwap.value, precision)}</b>
        </span>
      </div>

      {/* distance meter — centre = VWAP */}
      <div className="relative mt-3 h-2 rounded-full bg-gradient-to-r from-bear/35 via-well to-bull/35">
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
      <div className="num mt-1.5 flex justify-between text-[9px] tracking-widest text-faint">
        <span>-3%</span>
        <span className="text-vwap">VWAP</span>
        <span>+3%</span>
      </div>

      <div className="mt-2 border-t border-line-soft/60 pt-1.5">
        <StatRow
          label={vwap.mode === "ANCHORED" ? "ANCHOR" : "SESSION RESET"}
          value={vwap.mode === "ANCHORED" ? "STRUCTURAL PIVOT LOW" : "DAILY 09:30 NY"}
          valueClass="text-muted"
        />
        <StatRow
          label="VERDICT"
          value={vwap.above ? "BUYERS IN CONTROL" : "SELLERS IN CONTROL"}
          valueClass={vwap.above ? "text-bull-soft" : "text-bear-soft"}
        />
      </div>
    </CardShell>
  );
}
