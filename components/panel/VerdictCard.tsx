"use client";

import { Anchor, ShieldAlert } from "lucide-react";
import type { AnalysisResult } from "@/lib/types";
import StatusBadge from "../terminal/StatusBadge";

function ScoreRing({ score }: { score: number }) {
  const r = 22;
  const c = 2 * Math.PI * r;
  const tone = score >= 70 ? "#10b981" : score >= 45 ? "#f59e0b" : "#ef4444";
  return (
    <div className="relative h-14 w-14 shrink-0">
      <svg viewBox="0 0 52 52" className="h-full w-full -rotate-90">
        <circle cx="26" cy="26" r={r} fill="none" stroke="#1c2839" strokeWidth="5" />
        <circle
          cx="26"
          cy="26"
          r={r}
          fill="none"
          stroke={tone}
          strokeWidth="5"
          strokeLinecap="round"
          strokeDasharray={`${(score / 100) * c} ${c}`}
          style={{ transition: "stroke-dasharray 0.6s ease" }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="num text-[14px] font-black leading-none text-ink">{score}</span>
        <span className="text-[8px] font-bold tracking-wide text-faint">التقييم</span>
      </div>
    </div>
  );
}

export default function VerdictCard({ analysis }: { analysis: AnalysisResult }) {
  const { vwap, rsi } = analysis;
  return (
    <div className="card overflow-hidden">
      <div className="flex items-center gap-3 border-b border-line-soft/70 bg-well/40 px-3.5 py-3">
        <ScoreRing score={analysis.score} />
        <div className="min-w-0 flex-1">
          <div className="text-[10.5px] font-bold tracking-wide text-faint">
            حكم استراتيجية الارتكاز
          </div>
          <div className="mt-1.5">
            <StatusBadge status={analysis.verdict} />
          </div>
        </div>
      </div>

      <div className="flex items-start gap-2.5 border-b border-line-soft/60 px-3.5 py-3">
        <ShieldAlert className="mt-0.5 h-3.5 w-3.5 shrink-0 text-sky/80" />
        <p className="text-[11.5px] leading-relaxed text-muted">{analysis.verdict.detail}</p>
      </div>

      {/* monitoring strip — VWAP is advisory only, per the strategy rules */}
      <div className="grid grid-cols-1 gap-2 px-3.5 py-3 sm:grid-cols-2">
        <div
          className={`rounded-lg border px-3 py-2 ${
            vwap.above ? "border-bull/40 bg-bull/8" : "border-line bg-well/60"
          }`}
        >
          <div className="flex items-center gap-1.5 text-[10px] font-bold text-faint">
            <Anchor className="h-3 w-3" style={{ color: "#fb923c" }} />
            مراقبة VWAP (غير مانعة)
          </div>
          <div className={`num mt-1 text-[13px] font-black ${vwap.above ? "text-bull-soft" : "text-muted"}`}>
            {vwap.above ? `أعلى VWAP +${vwap.distancePct.toFixed(2)}%` : `أدنى VWAP ${vwap.distancePct.toFixed(2)}%`}
          </div>
          <div className="mt-0.5 text-[9.5px] leading-snug text-faint">
            {vwap.above ? "استعادة إيجابية ممتازة تعزز الارتكاز" : "ملاحظة مراقبة فقط — لا ترفض السهم"}
          </div>
        </div>

        <div
          className={`rounded-lg border px-3 py-2 ${
            rsi.exitOversold ? "border-bull/40 bg-bull/8" : "border-line bg-well/60"
          }`}
        >
          <div className="text-[10px] font-bold text-faint">إشارة RSI الإيجابية</div>
          <div className={`num mt-1 text-[13px] font-black ${rsi.exitOversold ? "text-bull-soft" : "text-muted"}`}>
            RSI اليومي {rsi.dailyValue.toFixed(1)}
          </div>
          <div className="mt-0.5 text-[9.5px] leading-snug text-faint">
            {rsi.exitOversold
              ? rsi.dailyValue >= 40
                ? "خرج من التشبع البيعي وصعد فوق 40 — إشارة مكتملة"
                : "خرج من تحت 30 ويتجه نحو 40 — إيجابية قيد التكوين"
              : "لا خروج من التشبع البيعي بعد"}
          </div>
        </div>
      </div>
    </div>
  );
}
