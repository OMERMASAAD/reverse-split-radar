"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { CornerDownLeft, Search } from "lucide-react";
import type { TapeQuote } from "@/lib/market/generator";
import { fmtPrice, fmtPct } from "@/lib/format";

export default function SearchBar({
  universe,
  active,
  onSelect,
}: {
  universe: TapeQuote[];
  active: string;
  onSelect: (symbol: string) => void;
}) {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [cursor, setCursor] = useState(0);
  const boxRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const results = useMemo(() => {
    const q = query.trim().toUpperCase();
    if (!q) return universe;
    return universe.filter(
      (u) => u.symbol.includes(q) || u.name.toUpperCase().includes(q),
    );
  }, [query, universe]);

  useEffect(() => setCursor(0), [query]);

  useEffect(() => {
    const onDocClick = (e: MouseEvent) => {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "/" && document.activeElement?.tagName !== "INPUT") {
        e.preventDefault();
        inputRef.current?.focus();
        setOpen(true);
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, []);

  const commit = (sym: string) => {
    onSelect(sym);
    setOpen(false);
    setQuery("");
    inputRef.current?.blur();
  };

  return (
    <div ref={boxRef} className="relative w-full max-w-md">
      <div
        className={`flex items-center gap-2.5 rounded-xl border bg-well/80 px-3.5 py-2.5 transition-colors ${
          open ? "border-sky/50 shadow-[0_0_0_3px_rgba(56,189,248,0.08)]" : "border-line-soft"
        }`}
      >
        <Search className="h-4 w-4 shrink-0 text-faint" />
        <input
          ref={inputRef}
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          onKeyDown={(e) => {
            if (e.key === "ArrowDown") {
              e.preventDefault();
              setCursor((c) => Math.min(c + 1, results.length - 1));
            } else if (e.key === "ArrowUp") {
              e.preventDefault();
              setCursor((c) => Math.max(c - 1, 0));
            } else if (e.key === "Enter") {
              const pick = results[cursor] ?? results[0];
              if (pick) commit(pick.symbol);
            } else if (e.key === "Escape") {
              setOpen(false);
            }
          }}
          placeholder="ابحث عن رمز السهم — THH، ELPW، MSGY، AAPL…"
          spellCheck={false}
          autoComplete="off"
          dir="rtl"
          className="w-full bg-transparent text-[12.5px] tracking-wide text-ink placeholder:text-faint focus:outline-none"
        />
        <kbd className="num hidden shrink-0 rounded-md border border-line bg-panel-2 px-1.5 py-0.5 text-[10px] text-faint md:block">
          /
        </kbd>
      </div>

      {open && results.length > 0 && (
        <div className="absolute left-0 right-0 top-[calc(100%+8px)] z-50 overflow-hidden rounded-xl border border-line bg-panel-2/98 shadow-2xl shadow-black/60 backdrop-blur-xl">
          <div className="flex items-center justify-between border-b border-line-soft px-3.5 py-2 text-[10px] font-semibold tracking-wide text-faint">
            <span>قائمة المتابعة — اختر سهمًا للتحميل</span>
            <span className="num flex items-center gap-1 text-[9px]">
              ENTER <CornerDownLeft className="h-3 w-3" />
            </span>
          </div>
          <ul className="max-h-80 overflow-y-auto py-1">
            {results.map((r, i) => {
              const up = r.changePct >= 0;
              return (
                <li key={r.symbol}>
                  <button
                    onClick={() => commit(r.symbol)}
                    onMouseEnter={() => setCursor(i)}
                    className={`flex w-full items-center gap-3 px-3.5 py-2.5 text-start transition-colors ${
                      i === cursor ? "bg-sky/10" : "hover:bg-panel/60"
                    } ${r.symbol === active ? "border-s-2 border-sky" : "border-s-2 border-transparent"}`}
                  >
                    <span className="num w-14 text-[13px] font-bold tracking-wider text-ink">
                      {r.symbol}
                    </span>
                    <span className="flex-1 truncate text-[12px] text-muted">{r.name}</span>
                    <span className="num text-[12px] text-ink">{fmtPrice(r.last)}</span>
                    <span
                      className={`num w-16 text-end text-[11.5px] font-semibold ${
                        up ? "text-bull-soft" : "text-bear-soft"
                      }`}
                    >
                      {fmtPct(r.changePct)}
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </div>
  );
}
