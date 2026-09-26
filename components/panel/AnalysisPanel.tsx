"use client";

import { FlaskConical } from "lucide-react";
import { TIMEFRAME_AR, type AnalysisResult } from "@/lib/types";
import VerdictCard from "./VerdictCard";
import StructureCard from "./StructureCard";
import TargetsCard from "./TargetsCard";
import RsiCard from "./RsiCard";
import ShortNewsCard from "./ShortNewsCard";

export default function AnalysisPanel({ analysis }: { analysis: AnalysisResult }) {
  return (
    <aside className="flex min-h-0 w-full flex-col gap-3 overflow-y-auto pb-1 xl:w-[400px] xl:shrink-0 xl:pe-1">
      <div className="flex items-center gap-2 px-1 pt-1 text-[11px] font-bold tracking-wide text-faint">
        <FlaskConical className="h-3.5 w-3.5 text-violet/80" />
        تقرير السهم الفردي — مباشر وفوري
        <span className="num ms-auto rounded border border-line bg-well px-1.5 py-0.5 text-[9px] font-semibold text-muted">
          {analysis.symbol} · {TIMEFRAME_AR[analysis.timeframe]}
        </span>
      </div>

      <VerdictCard analysis={analysis} />
      <StructureCard analysis={analysis} />
      <TargetsCard analysis={analysis} />
      <RsiCard analysis={analysis} />
      <ShortNewsCard analysis={analysis} />
    </aside>
  );
}
