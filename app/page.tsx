"use client";

import { useEffect, useMemo, useState } from "react";
import Header from "@/components/terminal/Header";
import TickerTape from "@/components/terminal/TickerTape";
import Footer from "@/components/terminal/Footer";
import ChartCanvas from "@/components/chart/ChartCanvas";
import AnalysisPanel from "@/components/panel/AnalysisPanel";
import {
  aggregate,
  generateMinutes,
  getCandles,
  getSessionWindow,
  getTape,
  type TapeQuote,
} from "@/lib/market/generator";
import { UNIVERSE, getProfile } from "@/lib/market/profiles";
import { analyzeStock } from "@/lib/strategy/engine";
import { TIMEFRAMES, type Timeframe } from "@/lib/types";

function BootSkeleton() {
  return (
    <div className="flex min-h-screen flex-col">
      <div className="h-[68px] border-b border-line-soft bg-abyss-2/80" />
      <div className="h-8 border-b border-line-soft bg-abyss-2/50" />
      <div className="flex flex-1 gap-3 p-3">
        <div className="card relative flex-1 overflow-hidden">
          <div className="absolute inset-x-0 top-0 h-24 animate-scan bg-gradient-to-b from-transparent via-sky/5 to-transparent" />
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 text-faint">
            <div className="h-10 w-10 animate-spin rounded-full border-2 border-line border-t-sky" />
            <div className="text-[12px] font-bold tracking-wide">جارٍ تهيئة محرك السوق…</div>
            <div className="text-[10px] tracking-wide text-line">
              توليد تغذية حتمية · 135 جلسة · فحص هيكلي وأهداف فورية
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
  const [timeframe, setTimeframe] = useState<Timeframe>("1D");
  const [tape, setTape] = useState<TapeQuote[]>([]);

  useEffect(() => {
    setMounted(true);
  }, []);

  const now = useMemo(() => (mounted ? new Date() : null), [mounted]);
  const win = useMemo(() => (now ? getSessionWindow(now) : null), [now]);

  const minutes = useMemo(() => {
    if (!win) return null;
    return generateMinutes(getProfile(symbol), win);
  }, [symbol, win]);

  const daily = useMemo(() => {
    if (!minutes) return null;
    return aggregate(minutes, "1D");
  }, [minutes]);

  const candles = useMemo(() => {
    if (!minutes || !daily) return null;
    return timeframe === "1D" ? daily : aggregate(minutes, timeframe);
  }, [minutes, daily, timeframe]);

  const analysis = useMemo(() => {
    if (!candles || !daily || !minutes || candles.length < 60) return null;
    return analyzeStock(symbol, timeframe, candles, daily, minutes);
  }, [symbol, timeframe, candles, daily, minutes]);

  useEffect(() => {
    if (!now) return;
    const id = setTimeout(() => {
      setTape(getTape(UNIVERSE.map((p) => p.symbol), now));
    }, 30);
    return () => clearTimeout(id);
  }, [now]);

  useEffect(() => {
    if (!now) return;
    for (const tf of TIMEFRAMES) getCandles(symbol, tf, now);
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
        status={analysis.verdict}
        marketOpen={win.marketOpen}
      />
      <TickerTape quotes={tape} active={symbol} onSelect={setSymbol} />

      <main className="grid-noise flex min-h-0 flex-1 flex-col gap-3 p-3 xl:flex-row">
        <div className="flex min-h-[520px] flex-col xl:min-h-0 xl:flex-1">
          <ChartCanvas analysis={analysis} />
        </div>
        <AnalysisPanel analysis={analysis} />
      </main>

      <Footer marketOpen={win.marketOpen} />
    </div>
  );
}
