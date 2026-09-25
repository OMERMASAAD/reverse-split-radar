"use client";

import { useEffect, useState } from "react";
import { Activity, Cpu, Radio } from "lucide-react";
import type { TapeQuote } from "@/lib/market/generator";
import type { StatusResult, Timeframe } from "@/lib/types";
import SearchBar from "./SearchBar";
import TimeframeToggle from "./TimeframeToggle";
import StatusBadge from "./StatusBadge";
import { fmtClock } from "@/lib/format";

export default function Header({
  universe,
  symbol,
  onSymbol,
  timeframe,
  onTimeframe,
  status,
  marketOpen,
}: {
  universe: TapeQuote[];
  symbol: string;
  onSymbol: (s: string) => void;
  timeframe: Timeframe;
  onTimeframe: (tf: Timeframe) => void;
  status: StatusResult;
  marketOpen: boolean;
}) {
  const [clock, setClock] = useState<Date | null>(null);

  useEffect(() => {
    setClock(new Date());
    const id = setInterval(() => setClock(new Date()), 1000);
    return () => clearInterval(id);
  }, []);

  return (
    <header className="relative z-40 border-b border-line-soft bg-abyss-2/90 backdrop-blur-md">
      <div className="flex flex-wrap items-center gap-x-5 gap-y-3 px-4 py-3 lg:flex-nowrap lg:px-5">
        {/* brand */}
        <div className="flex items-center gap-3">
          <div className="relative flex h-10 w-10 items-center justify-center rounded-xl border border-sky/40 bg-sky/10 glow-bull">
            <Activity className="h-5 w-5 text-bull-soft" strokeWidth={2.4} />
            <span className="absolute -right-0.5 -top-0.5 h-2 w-2 rounded-full bg-bull animate-pulse-dot" />
          </div>
          <div className="leading-tight">
            <div className="num text-[15px] font-black tracking-[0.22em] text-ink">
              APEX<span className="text-sky">·</span>TERMINAL
            </div>
            <div className="flex items-center gap-1.5 text-[10px] font-semibold tracking-wide text-faint">
              <Cpu className="h-3 w-3" /> مكتب التداول الآلي
            </div>
          </div>
        </div>

        {/* search */}
        <div className="order-3 w-full lg:order-none lg:w-auto lg:flex-1 lg:max-w-md">
          <SearchBar universe={universe} active={symbol} onSelect={onSymbol} />
        </div>

        <div className="ms-auto flex items-center gap-4">
          {/* timeframes */}
          <TimeframeToggle value={timeframe} onChange={onTimeframe} />

          {/* status */}
          <StatusBadge status={status} />

          {/* clock */}
          <div className="hidden flex-col items-start leading-tight xl:flex">
            <div className="num text-[15px] font-bold text-ink">
              {clock ? fmtClock(clock) : "--:--:--"}
            </div>
            <div className="flex items-center gap-1.5 text-[10px] font-semibold tracking-wide">
              <Radio
                className={`h-3 w-3 ${marketOpen ? "text-bull" : "text-faint"}`}
              />
              <span className={marketOpen ? "text-bull-soft" : "text-faint"}>
                {marketOpen ? "السوق مفتوح · نيويورك" : "مغلق · تغذية محاكاة"}
              </span>
            </div>
          </div>
        </div>
      </div>
    </header>
  );
}
