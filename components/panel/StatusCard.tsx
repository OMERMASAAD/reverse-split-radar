"use client";

import { AlertTriangle, CheckCircle2, ShieldAlert, XCircle } from "lucide-react";
import type { AnalysisResult } from "@/lib/types";
import StatusBadge from "../terminal/StatusBadge";

function ScoreRing({ score }: { score: number }) {
  const r = 22;
  const c = 2 * Math.PI * r;
  const tone =
    score >= 70 ? "#10b981" : score >= 45 ? "#f59e0b" : "#ef4444";
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

export default function StatusCard({ analysis }: { analysis: AnalysisResult }) {
  const iconFor = (state: "pass" | "warn" | "fail") =>
    state === "pass" ? (
      <CheckCircle2 className="h-4 w-4 shrink-0 text-bull" />
    ) : state === "warn" ? (
      <AlertTriangle className="h-4 w-4 shrink-0 text-gold" />
    ) : (
      <XCircle className="h-4 w-4 shrink-0 text-bear" />
    );

  return (
    <div className="card overflow-hidden">
      <div className="flex items-center gap-3 border-b border-line-soft/70 bg-well/40 px-3.5 py-3">
        <ScoreRing score={analysis.score} />
        <div className="min-w-0 flex-1">
          <div className="text-[10.5px] font-bold tracking-wide text-faint">
            جاهزية الفرصة
          </div>
          <div className="mt-1.5">
            <StatusBadge status={analysis.status} />
          </div>
        </div>
      </div>

      <div className="flex items-start gap-2.5 border-b border-line-soft/60 px-3.5 py-3">
        <ShieldAlert className="mt-0.5 h-3.5 w-3.5 shrink-0 text-sky/80" />
        <p className="text-[11.5px] leading-relaxed text-muted">{analysis.status.detail}</p>
      </div>

      {/* rule-by-rule checklist */}
      <ul className="divide-y divide-line-soft/50">
        {analysis.checklist.map((item, i) => (
          <li key={item.id} className="flex items-start gap-2.5 px-3.5 py-2.5">
            {iconFor(item.state)}
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <span className="num text-[11px] font-extrabold tracking-wide text-ink">
                  {String(i + 1).padStart(2, "0")} · {item.label}
                </span>
                {item.state === "warn" && item.id === "rsi" && analysis.rsi.warning && (
                  <span className="rounded border border-violet/50 bg-violet/10 px-1.5 py-px text-[9px] font-bold tracking-wide text-violet">
                    تحذير تشبع ≥ 80
                  </span>
                )}
              </div>
              <p className="mt-0.5 truncate text-[11px] text-muted">{item.detail}</p>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
