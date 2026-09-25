"use client";

import { Gauge } from "lucide-react";
import type { AnalysisResult } from "@/lib/types";
import { CardShell, StatePill } from "./CardShell";

const ZONE_META = {
  OVERBOUGHT: { label: "OVERBOUGHT", tone: "violet" as const, color: "#a78bfa" },
  STRONG: { label: "STRONG / HOT", tone: "gold" as const, color: "#f59e0b" },
  BULLISH: { label: "BULLISH BAND", tone: "bull" as const, color: "#10b981" },
  WEAK: { label: "WEAK", tone: "muted" as const, color: "#8ba0bd" },
  OVERSOLD: { label: "OVERSOLD", tone: "sky" as const, color: "#38bdf8" },
};

export default function RsiCard({ analysis }: { analysis: AnalysisResult }) {
  const { rsi } = analysis;
  const meta = ZONE_META[rsi.zone];
  const v = Math.max(0, Math.min(100, rsi.value));

  return (
    <CardShell
      icon={Gauge}
      title="RSI RANGE METER"
      step="RULE 04 · WILDER 14"
      accent="#a78bfa"
      right={<StatePill tone={meta.tone}>{meta.label}</StatePill>}
    >
      <div className="flex items-end justify-between">
        <span
          className="num text-[34px] font-black leading-none"
          style={{ color: meta.color, textShadow: `0 0 24px ${meta.color}44` }}
        >
          {v.toFixed(1)}
        </span>
        <span className="num pb-1 text-[10px] tracking-[0.18em] text-faint">
          TRIGGERS ≥ 80 · IDEAL 50–75
        </span>
      </div>

      {/* zoned gradient meter */}
      <div className="relative mt-3 h-2.5 overflow-hidden rounded-full">
        <div
          className="absolute inset-0"
          style={{
            background:
              "linear-gradient(90deg, #38bdf8 0%, #38bdf8 30%, #64748b 30%, #64748b 50%, #10b981 50%, #10b981 70%, #f59e0b 70%, #f59e0b 80%, #a78bfa 80%, #a78bfa 100%)",
            opacity: 0.55,
          }}
        />
        <div
          className="absolute top-1/2 h-5 w-1.5 -translate-x-1/2 -translate-y-1/2 rounded-full border border-abyss transition-all duration-500"
          style={{ left: `${v}%`, background: meta.color, boxShadow: `0 0 12px ${meta.color}` }}
        />
      </div>
      <div className="num mt-1.5 flex justify-between text-[9px] tracking-widest text-faint">
        <span>0</span>
        <span>30</span>
        <span>50</span>
        <span>70</span>
        <span className="text-violet">80</span>
        <span>100</span>
      </div>

      {rsi.warning && (
        <div className="mt-3 flex items-start gap-2 rounded-lg border border-violet/45 bg-violet/10 px-3 py-2 glow-violet">
          <span className="text-[13px]">🟣</span>
          <p className="text-[11px] leading-relaxed text-violet">
            <b className="num tracking-wide">OVERBOUGHT TRIGGER — RSI ≥ 80.</b> Momentum is
            vertically stretched; breakout entries here carry elevated mean-reversion risk.
            Scale in only on pullbacks that hold VWAP.
          </p>
        </div>
      )}
      {!rsi.warning && (
        <p className="mt-3 text-[11px] leading-relaxed text-muted">
          Oscillator inside the <b style={{ color: meta.color }}>{meta.label.toLowerCase()}</b>{" "}
          band — {v >= 50 ? "buyers own the momentum window." : "momentum needs confirmation before deployment."}
        </p>
      )}
    </CardShell>
  );
}
