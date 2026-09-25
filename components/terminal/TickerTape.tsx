"use client";

import { ArrowDownRight, ArrowUpRight } from "lucide-react";
import type { TapeQuote } from "@/lib/market/generator";
import { fmtPrice, fmtPct } from "@/lib/format";

function TapeItem({
  q,
  active,
  onSelect,
}: {
  q: TapeQuote;
  active: boolean;
  onSelect: (s: string) => void;
}) {
  const up = q.changePct >= 0;
  return (
    <button
      onClick={() => onSelect(q.symbol)}
      className={`num group flex shrink-0 items-center gap-2 border-r border-line-soft px-4 py-1.5 text-[11px] transition-colors ${
        active ? "bg-sky/10" : "hover:bg-panel/60"
      }`}
    >
      <span
        className={`font-bold tracking-wider ${active ? "text-sky" : "text-ink"}`}
      >
        {q.symbol}
      </span>
      <span className="text-muted">{fmtPrice(q.last)}</span>
      <span
        className={`flex items-center gap-0.5 font-semibold ${
          up ? "text-bull-soft" : "text-bear-soft"
        }`}
      >
        {up ? (
          <ArrowUpRight className="h-3 w-3" />
        ) : (
          <ArrowDownRight className="h-3 w-3" />
        )}
        {fmtPct(q.changePct)}
      </span>
    </button>
  );
}

export default function TickerTape({
  quotes,
  active,
  onSelect,
}: {
  quotes: TapeQuote[];
  active: string;
  onSelect: (s: string) => void;
}) {
  const doubled = [...quotes, ...quotes];
  return (
    <div className="tape-mask relative overflow-hidden border-b border-line-soft bg-abyss-2/70">
      <div className="flex w-max animate-marquee hover:[animation-play-state:paused]">
        {doubled.map((q, i) => (
          <TapeItem
            key={`${q.symbol}-${i}`}
            q={q}
            active={q.symbol === active}
            onSelect={onSelect}
          />
        ))}
      </div>
    </div>
  );
}
