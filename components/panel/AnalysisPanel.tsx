"use client";

import { FlaskConical } from "lucide-react";
import { TIMEFRAME_AR, type AnalysisResult } from "@/lib/types";
import StatusCard from "./StatusCard";
import VwapCard from "./VwapCard";
import ObvCard from "./ObvCard";
import MacdCard from "./MacdCard";
import RsiCard from "./RsiCard";
import PatternCard from "./PatternCard";
import TradePlanCard from "./TradePlanCard";

export default function AnalysisPanel({ analysis }: { analysis: AnalysisResult }) {
  return (
    <aside className="flex min-h-0 w-full flex-col gap-3 overflow-y-auto pb-1 xl:w-[400px] xl:shrink-0 xl:pe-1">
      <div className="flex items-center gap-2 px-1 pt-1 text-[11px] font-bold tracking-wide text-faint">
        <FlaskConical className="h-3.5 w-3.5 text-violet/80" />
        محرك التحليل الفني — قاعدة بقاعدة
        <span className="num ms-auto rounded border border-line bg-well px-1.5 py-0.5 text-[9px] font-semibold text-muted">
          {analysis.symbol} · {TIMEFRAME_AR[analysis.timeframe]}
        </span>
      </div>

      <StatusCard analysis={analysis} />
      <VwapCard analysis={analysis} />
      <ObvCard analysis={analysis} />
      <MacdCard analysis={analysis} />
      <RsiCard analysis={analysis} />
      <PatternCard analysis={analysis} />
      <TradePlanCard analysis={analysis} />
    </aside>
  );
}
