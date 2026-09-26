"use client";

import { useMemo, useState } from "react";
import { Newspaper, TrendingDown, TrendingUp } from "lucide-react";
import type { AnalysisResult, NewsItem } from "@/lib/types";
import { CardShell } from "./CardShell";
import { fmtDay } from "@/lib/format";

type Filter = "all" | "positive" | "negative" | "upcoming";

const FILTERS: { id: Filter; label: string }[] = [
  { id: "all", label: "الكل" },
  { id: "positive", label: "إيجابي" },
  { id: "negative", label: "سلبي" },
  { id: "upcoming", label: "قادم" },
];

function NewsRow({ item }: { item: NewsItem }) {
  const meta = item.upcoming
    ? { icon: "⏰", cls: "border-gold/40 bg-gold/8 text-gold" }
    : item.sentiment === "positive"
      ? { icon: "▲", cls: "border-bull/40 bg-bull/8 text-bull-soft" }
      : item.sentiment === "negative"
        ? { icon: "▼", cls: "border-bear/40 bg-bear/8 text-bear-soft" }
        : { icon: "●", cls: "border-line bg-well text-muted" };
  return (
    <li className={`rounded-lg border px-3 py-2 ${meta.cls}`}>
      <div className="flex items-center justify-between gap-2 text-[9.5px] font-semibold">
        <span>
          {meta.icon} {item.source}
        </span>
        <span className="num text-faint">{fmtDay(item.time)}</span>
      </div>
      <p className="mt-1 text-[11px] font-semibold leading-relaxed text-ink">{item.title}</p>
    </li>
  );
}

export default function ShortNewsCard({ analysis }: { analysis: AnalysisResult }) {
  const [filter, setFilter] = useState<Filter>("all");
  const s = analysis.short;

  const items = useMemo(() => {
    const sorted = [...analysis.news].sort((a, b) => b.time - a.time);
    if (filter === "all") return sorted;
    if (filter === "upcoming") return sorted.filter((x) => x.upcoming);
    return sorted.filter((x) => !x.upcoming && x.sentiment === filter);
  }, [analysis.news, filter]);

  const trendMeta =
    s.trend === "rising"
      ? { icon: TrendingUp, txt: "متصاعد ▲", cls: "text-bear-soft" }
      : s.trend === "falling"
        ? { icon: TrendingDown, txt: "متراجع ▼", cls: "text-bull-soft" }
        : { icon: TrendingUp, txt: "مستقر →", cls: "text-muted" };

  const insight =
    s.floatPct >= 20 && s.trend === "rising"
      ? "شورت مرتفع ومتزايد — ضغط بيعي حالي، لكنه وقود محتمل لقفزة تغطية (Short Squeeze) عند اختراق العنق."
      : s.floatPct >= 20
        ? "شورت مرتفع — عند تأكيد الاختراق قد تُجبر التغطية على تسريع الصعود."
        : s.trend === "falling"
          ? "تراجع البيع المكشوف — تخفيف تدريجي للضغط البيعي فوق السهم."
          : "البيع المكشوف منخفض التأثير على حركة السهم حاليًا.";

  return (
    <CardShell
      icon={Newspaper}
      title="مركز الأخبار والبيع المكشوف"
      step="الشورت المباشر + فلتر الأخبار القادمة والمباشرة"
      accent="#38bdf8"
    >
      <div className="grid grid-cols-3 gap-2">
        <div className="rounded-lg border border-line-soft bg-well/60 px-2.5 py-2 text-center">
          <div className="text-[9.5px] font-bold text-faint">الشورت من الطليق</div>
          <div className={`num mt-0.5 text-[16px] font-black ${s.floatPct >= 20 ? "text-bear-soft" : "text-ink"}`}>
            {s.floatPct.toFixed(1)}%
          </div>
        </div>
        <div className="rounded-lg border border-line-soft bg-well/60 px-2.5 py-2 text-center">
          <div className="text-[9.5px] font-bold text-faint">أيام التغطية</div>
          <div className="num mt-0.5 text-[16px] font-black text-ink">{s.daysToCover.toFixed(1)}</div>
        </div>
        <div className="rounded-lg border border-line-soft bg-well/60 px-2.5 py-2 text-center">
          <div className="text-[9.5px] font-bold text-faint">اتجاه الشورت</div>
          <div className={`mt-1 flex items-center justify-center gap-1 text-[11px] font-black ${trendMeta.cls}`}>
            {trendMeta.txt}
            <span className="num text-[9px]">
              ({s.deltaPct >= 0 ? "+" : ""}
              {s.deltaPct.toFixed(1)})
            </span>
          </div>
        </div>
      </div>

      <p className="mt-2 rounded-lg border border-line-soft/60 bg-abyss/40 px-3 py-2 text-[10.5px] leading-relaxed text-muted">
        {insight}
      </p>

      {/* quick news filter */}
      <div className="mt-3 flex items-center gap-1.5">
        {FILTERS.map((f) => (
          <button
            key={f.id}
            onClick={() => setFilter(f.id)}
            className={`rounded-md border px-2.5 py-1 text-[10px] font-bold transition-colors ${
              filter === f.id
                ? "border-sky/50 bg-sky/10 text-sky"
                : "border-line bg-well text-faint hover:text-muted"
            }`}
          >
            {f.label}
          </button>
        ))}
        <span className="num ms-auto text-[9.5px] text-faint">{items.length} خبر</span>
      </div>

      <ul className="mt-2 space-y-1.5">
        {items.map((item, i) => (
          <NewsRow key={i} item={item} />
        ))}
        {items.length === 0 && (
          <li className="rounded-lg border border-line-soft bg-well/40 px-3 py-2 text-[10.5px] text-faint">
            لا توجد أخبار ضمن هذا الفلتر حاليًا.
          </li>
        )}
      </ul>
    </CardShell>
  );
}
