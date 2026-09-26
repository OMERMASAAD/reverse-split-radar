"use client";

import type { StatusResult } from "@/lib/types";

const TONES: Record<
  StatusResult["code"],
  { wrap: string; dot: string; text: string }
> = {
  BREAKOUT: {
    wrap: "border-bull/50 bg-bull/10 glow-bull",
    dot: "bg-bull text-bull",
    text: "text-bull-soft",
  },
  ANCHORED: {
    wrap: "border-sky/50 bg-sky/10",
    dot: "bg-sky text-sky",
    text: "text-sky",
  },
  BUILDING: {
    wrap: "border-gold/50 bg-gold/10 glow-gold",
    dot: "bg-gold text-gold",
    text: "text-gold",
  },
  BROKEN: {
    wrap: "border-bear/60 bg-bear/10 glow-bear",
    dot: "bg-bear text-bear",
    text: "text-bear-soft",
  },
};

export default function StatusBadge({
  status,
  compact = false,
}: {
  status: StatusResult;
  compact?: boolean;
}) {
  const tone = TONES[status.code];
  return (
    <div
      className={`inline-flex items-center gap-2 rounded-xl border px-3 py-2 backdrop-blur-sm transition-colors ${tone.wrap}`}
      title={status.detail}
    >
      <span
        className={`h-2 w-2 shrink-0 rounded-full animate-pulse-dot ${tone.dot}`}
      />
      <span
        className={`text-[11.5px] font-extrabold tracking-wide ${tone.text} ${
          compact ? "" : "whitespace-nowrap"
        }`}
      >
        {status.emoji} {status.label}
      </span>
    </div>
  );
}
