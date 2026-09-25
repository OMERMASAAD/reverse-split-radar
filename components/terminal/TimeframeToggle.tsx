"use client";

import { TIMEFRAMES, type Timeframe } from "@/lib/types";

export default function TimeframeToggle({
  value,
  onChange,
}: {
  value: Timeframe;
  onChange: (tf: Timeframe) => void;
}) {
  return (
    <div
      className="flex items-center gap-0.5 rounded-xl border border-line-soft bg-well/80 p-1"
      role="tablist"
      aria-label="Chart timeframe"
    >
      {TIMEFRAMES.map((tf) => {
        const active = tf === value;
        return (
          <button
            key={tf}
            role="tab"
            aria-selected={active}
            onClick={() => onChange(tf)}
            className={`num rounded-lg px-3 py-1.5 text-[11px] font-bold tracking-wider transition-all ${
              active
                ? "bg-sky/15 text-sky shadow-[inset_0_0_0_1px_rgba(56,189,248,0.35)]"
                : "text-faint hover:bg-panel-2 hover:text-muted"
            }`}
          >
            {tf}
          </button>
        );
      })}
    </div>
  );
}
