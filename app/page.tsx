"use client";

import { useEffect, useMemo, useState } from "react";
import Header from "@/components/terminal/Header";
import TickerTape from "@/components/terminal/TickerTape";
import Footer from "@/components/terminal/Footer";
import ChartCanvas from "@/components/chart/ChartCanvas";
import AnalysisPanel from "@/components/panel/AnalysisPanel";
import { aggregate, generateMinutes, getCandles, getSessionWindow, getTape, type TapeQuote } from "@/lib/market/generator";
import { UNIVERSE, getProfile } from "@/lib/market/profiles";
import { analyze } from "@/lib/strategy/engine";
import type { Timeframe } from "@/lib/types";

function BootSkeleton() {
  return (
    <div className="flex min-h-screen flex-col">
      <div className="h-[68px] border-b border-line-soft bg-abyss-2/80" />
      <div className="h-8 border-b border-line-soft bg-abyss-2/50" />
      <div className="flex flex-1 gap-3 p-3">
        <div className="card relative flex-1 overflow-hidden">
          <div className="absolute inset-x-0 top-0 h-24 animate-scan bg-gradient-to-b from-transparent via-sky/5 to-transparent" />
          <div className="num absolute inset-0 flex flex-col items-center justify-center gap-3 text-faint">
            <div className="h-10 w-10 animate-spin rounded-full border-2 border-line border-t-sky" />
            <div className="text-[11px] tracking-[0.3em]">INITIALIZING MARKET ENGINE…</div>
            <div className="text-[9px] tracking-[0.2em] text-line">
              GENERATING DETERMINISTIC TAPE · 135 SESSIONS · 1-MIN RESOLUTION
            </div>
          </div>
        </div>
        <div className="hidden w-[400px] shrink-0 flex-col gap-3 xl:flex">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="card h-28 animate-pulse opacity-60" style={{ animationDelay: `${i * 120}ms` }} />
          ))}
        </div>
      </div>
    </div>
  );
}

export default function TerminalPage() {
  const [mounted, setMounted] = useState(false);
  const [symbol, setSymbol] = useState("THH");
  const [timeframe, setTimeframe] = useState<Timeframe>("15m");
  const [tape, setTape] = useState<TapeQuote[]>([]);

  useEffect(() => {
    setMounted(true);
  }, []);

  /* freeze "now" once on the client — the tape is deterministic per session */
  const now = useMemo(() => (mounted ? new Date() : null), [mounted]);

  const win = useMemo(() => (now ? getSessionWindow(now) : null), [now]);

  const minutes = useMemo(() => {
    if (!win) return null;
    return generateMinutes(getProfile(symbol), win);
  }, [symbol, win]);

  const candles = useMemo(() => {
    if (!minutes) return null;
    return aggregate(minutes, timeframe);
  }, [minutes, timeframe]);

  const analysis = useMemo(() => {
    if (!candles || !minutes || candles.length < 60) return null;
    return analyze(symbol, timeframe, candles, minutes);
  }, [symbol, timeframe, candles, minutes]);

  /* warm the shared candle cache + ticker tape in the background */
  useEffect(() => {
    if (!now) return;
    const id = setTimeout(() => {
      setTape(getTape(UNIVERSE.map((p) => p.symbol), now));
    }, 30);
    return () => clearTimeout(id);
  }, [now]);

  useEffect(() => {
    if (!now) return;
    // pre-warm the active symbol across timeframes so toggling is instant
    for (const tf of ["5m", "15m", "1h", "4h", "1D"] as Timeframe[]) {
      getCandles(symbol, tf, now);
    }
  }, [symbol, now]);

  if (!mounted || !analysis || !win) return <BootSkeleton />;

  return (
    <div className="flex min-h-screen flex-col xl:h-screen xl:overflow-hidden">
      <Header
        universe={tape}
        symbol={symbol}
        onSymbol={setSymbol}
        timeframe={timeframe}
        onTimeframe={setTimeframe}
        status={analysis.status}
        marketOpen={win.marketOpen}
      />
      <TickerTape quotes={tape} active={symbol} onSelect={setSymbol} />

      <main className="grid-noise flex min-h-0 flex-1 flex-col gap-3 p-3 xl:flex-row">
        <div className="flex min-h-[480px] flex-col xl:min-h-0 xl:flex-1">
          <ChartCanvas analysis={analysis} />
        </div>
        <AnalysisPanel analysis={analysis} />
      </main>

      <Footer marketOpen={win.marketOpen} />
    </div>
  );
}
