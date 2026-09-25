"use client";

import { Cpu, Database, ShieldCheck } from "lucide-react";

export default function Footer({ marketOpen }: { marketOpen: boolean }) {
  return (
    <footer className="flex flex-wrap items-center gap-x-5 gap-y-1 border-t border-line-soft bg-abyss-2/90 px-4 py-2 text-[10px] font-medium tracking-wide text-faint">
      <span className="flex items-center gap-1.5">
        <Cpu className="h-3 w-3 text-sky/70" />
        محرك الاستراتيجية الإصدار 2.4 · VWAP × OBV × MACD × RSI × النماذج السعرية
      </span>
      <span className="flex items-center gap-1.5">
        <Database className="h-3 w-3 text-violet/70" />
        تغذية محاكاة حتمية · 135 جلسة · دقة الدقيقة الواحدة
      </span>
      <span className="flex items-center gap-1.5">
        <ShieldCheck className="h-3 w-3 text-bull/70" />
        تحليل ورقي فقط — ليس نصيحة استثمارية
      </span>
      <span className="ms-auto flex items-center gap-1.5">
        <span
          className={`h-1.5 w-1.5 rounded-full ${marketOpen ? "bg-bull animate-pulse-dot" : "bg-faint"}`}
        />
        التغذية {marketOpen ? "حية-محاكاة" : "مغلقة-محاكاة"} · منصة APEX © 2026
      </span>
    </footer>
  );
}
