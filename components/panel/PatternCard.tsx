"use client";

import { ScanSearch } from "lucide-react";
import type { AnalysisResult } from "@/lib/types";
import { CardShell, StatePill, StatRow } from "./CardShell";
import { fmtDay, fmtPrice } from "@/lib/format";

export default function PatternCard({ analysis }: { analysis: AnalysisResult }) {
  const { pattern, quote } = analysis;
  const precision = quote.last < 1 ? 4 : 2;
  const confTone =
    pattern.confidence >= 65 ? "bull" : pattern.confidence >= 45 ? "gold" : "bear";

  return (
    <CardShell
      icon={ScanSearch}
      title="PATTERN RECOGNITION"
      step="RULE 05 · STRUCTURE ENGINE"
      accent="#10b981"
      right={<StatePill tone={confTone}>{pattern.confidence}% CONF</StatePill>}
    >
      <div className="flex items-center gap-3 rounded-xl border border-line-soft/70 bg-well/60 px-3.5 py-3">
        <span className="text-2xl">{pattern.emoji}</span>
        <div className="min-w-0">
          <div className="num text-[13px] font-black tracking-wide text-ink">
            {pattern.label.toUpperCase()}
          </div>
          <div className="num mt-0.5 text-[9.5px] tracking-[0.2em] text-faint">
            {pattern.kind.replaceAll("_", " · ")}
          </div>
        </div>
      </div>

      {/* confidence bar */}
      <div className="mt-3">
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
          <div className="num mb-1.5 text-[9px] tracking-[0.22em] text-faint">
            DETECTED PIVOTS
          </div>
          <div className="flex flex-wrap gap-1.5">
            {pattern.points.map((p, i) => (
              <span
                key={i}
                className={`num rounded-md border px-2 py-1 text-[10px] font-semibold ${
                  p.kind === "low"
                    ? "border-bull/35 bg-bull/10 text-bull-soft"
                    : "border-bear/35 bg-bear/10 text-bear-soft"
                }`}
              >
                {p.kind === "low" ? "L" : "H"} {fmtPrice(p.price, precision)} ·{" "}
                <span className="text-faint">{fmtDay(p.time)}</span>
              </span>
            ))}
          </div>
        </div>
      )}

      <div className="mt-2 border-t border-line-soft/60 pt-1.5">
        <StatRow label="NECKLINE / TRIGGER" value={fmtPrice(pattern.neckline, precision)} valueClass="text-bear-soft" />
        <StatRow label="STRUCTURAL PIVOT LOW" value={fmtPrice(pattern.pivotLow, precision)} valueClass="text-bull-soft" />
        <StatRow label="MEASURED MOVE DEPTH" value={fmtPrice(pattern.depth, precision)} valueClass="text-ink" />
      </div>
    </CardShell>
  );
}
