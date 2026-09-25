"use client";

import type { LucideIcon } from "lucide-react";

export function CardShell({
  icon: Icon,
  title,
  step,
  right,
  children,
  accent,
}: {
  icon: LucideIcon;
  title: string;
  step?: string;
  right?: React.ReactNode;
  children: React.ReactNode;
  accent?: string;
}) {
  return (
    <div className="card overflow-hidden">
      <div className="flex items-center gap-2.5 border-b border-line-soft/70 bg-well/40 px-3.5 py-2.5">
        <div
          className="flex h-6 w-6 items-center justify-center rounded-md border"
          style={{
            borderColor: accent ? `${accent}55` : "#26334955",
            background: accent ? `${accent}14` : "#1e293b55",
          }}
        >
          <Icon className="h-3.5 w-3.5" style={{ color: accent ?? "#8ba0bd" }} />
        </div>
        <div className="min-w-0">
          <div className="num text-[11px] font-bold tracking-[0.16em] text-ink">
            {title}
          </div>
          {step && (
            <div className="num text-[9px] tracking-[0.22em] text-faint">{step}</div>
          )}
        </div>
        <div className="ml-auto flex items-center gap-2">{right}</div>
      </div>
      <div className="px-3.5 py-3">{children}</div>
    </div>
  );
}

export function StatePill({
  tone,
  children,
}: {
  tone: "bull" | "bear" | "gold" | "violet" | "sky" | "muted";
  children: React.ReactNode;
}) {
  const map = {
    bull: "border-bull/45 bg-bull/10 text-bull-soft",
    bear: "border-bear/50 bg-bear/10 text-bear-soft",
    gold: "border-gold/45 bg-gold/10 text-gold",
    violet: "border-violet/50 bg-violet/10 text-violet",
    sky: "border-sky/45 bg-sky/10 text-sky",
    muted: "border-line bg-well text-muted",
  } as const;
  return (
    <span
      className={`num rounded-md border px-2 py-0.5 text-[9.5px] font-bold tracking-[0.14em] ${map[tone]}`}
    >
      {children}
    </span>
  );
}

export function StatRow({
  label,
  value,
  valueClass = "text-ink",
}: {
  label: string;
  value: string;
  valueClass?: string;
}) {
  return (
    <div className="flex items-center justify-between py-1">
      <span className="num text-[10px] tracking-[0.14em] text-faint">{label}</span>
      <span className={`num text-[12px] font-semibold ${valueClass}`}>{value}</span>
    </div>
  );
}
