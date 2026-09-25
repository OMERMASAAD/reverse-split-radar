"use client";

import { Waves } from "lucide-react";
import type { AnalysisResult } from "@/lib/types";
import { CardShell, StatePill, StatRow } from "./CardShell";
import { LinePairChart } from "./MiniChart";
import { fmtCompactVolume, fmtPct } from "@/lib/format";

export default function ObvCard({ analysis }: { analysis: AnalysisResult }) {
  const { obv } = analysis;
  const n = obv.series.length;
  const from = Math.max(0, n - 90);
  const a = obv.series.slice(from);
  const b = obv.ema.slice(from).map((v) => (isNaN(v) ? a[0] : v));

  const tone =
    obv.flow === "INFLOW" ? "bull" : obv.flow === "OUTFLOW" ? "bear" : "gold";

  return (
    <CardShell
      icon={Waves}
      title="OBV FLOW ENGINE"
      step="RULE 02 · ACCUMULATION / DISTRIBUTION"
      accent="#38bdf8"
      right={<StatePill tone={tone}>{obv.flow === "INFLOW" ? "▲ INFLOW" : obv.flow === "OUTFLOW" ? "▼ OUTFLOW" : "≈ MIXED"}</StatePill>}
    >
      <div className="h-14 w-full">
        <LinePairChart a={a} b={b} colorA="#38bdf8" colorB="#f59e0b" height={56} />
      </div>
      <div className="num mt-1 flex justify-between text-[9px] tracking-widest text-faint">
        <span className="text-sky">— OBV</span>
        <span className="text-gold">- - OBV 20 EMA</span>
        <span>LAST {fmtCompactVolume(Math.abs(obv.series[n - 1]))}</span>
      </div>

      <div className="mt-2 border-t border-line-soft/60 pt-1.5">
        <StatRow
          label="TRAJECTORY (10 BARS)"
          value={fmtPct(obv.slopePct, 1)}
          valueClass={obv.slopePct >= 0 ? "text-bull-soft" : "text-bear-soft"}
        />
        <StatRow
          label="OBV vs 20 EMA"
          value={`${obv.vsEmaPct >= 0 ? "+" : ""}${obv.vsEmaPct.toFixed(1)}%`}
          valueClass={obv.vsEmaPct >= 0 ? "text-bull-soft" : "text-bear-soft"}
        />
        <StatRow
          label="READ"
          value={
            obv.flow === "INFLOW"
              ? "VOLUME CONFIRMS THE MOVE"
              : obv.flow === "OUTFLOW"
                ? "SMART MONEY EXITING"
                : "NO CLEAR COMMITMENT"
          }
          valueClass={
            obv.flow === "INFLOW" ? "text-bull-soft" : obv.flow === "OUTFLOW" ? "text-bear-soft" : "text-gold"
          }
        />
      </div>
    </CardShell>
  );
}
