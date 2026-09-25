"use client";

import { Cpu, Database, ShieldCheck } from "lucide-react";

export default function Footer({ marketOpen }: { marketOpen: boolean }) {
  return (
    <footer className="num flex flex-wrap items-center gap-x-5 gap-y-1 border-t border-line-soft bg-abyss-2/90 px-4 py-2 text-[9.5px] tracking-[0.16em] text-faint">
      <span className="flex items-center gap-1.5">
        <Cpu className="h-3 w-3 text-sky/70" />
        STRATEGY ENGINE v2.4 · VWAP × OBV × MACD × RSI × PATTERN
      </span>
      <span className="flex items-center gap-1.5">
        <Database className="h-3 w-3 text-violet/70" />
        DETERMINISTIC SIMULATED TAPE · 135 SESSIONS · 1-MIN RESOLUTION
      </span>
      <span className="flex items-center gap-1.5">
        <ShieldCheck className="h-3 w-3 text-bull/70" />
        PAPER ANALYSIS ONLY — NOT INVESTMENT ADVICE
      </span>
      <span className="ml-auto flex items-center gap-1.5">
        <span
          className={`h-1.5 w-1.5 rounded-full ${marketOpen ? "bg-bull animate-pulse-dot" : "bg-faint"}`}
        />
        FEED {marketOpen ? "LIVE-SIM" : "CLOSED-SIM"} · APEX TERMINAL © 2026
      </span>
    </footer>
  );
}
