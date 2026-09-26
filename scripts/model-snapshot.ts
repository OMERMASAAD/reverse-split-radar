/**
 * model-snapshot — يرسم النموذج المرجعي المكتشف (رأس وكتفين مقلوب برأسٍ قاع
 * مزدوج) كما أخرجه المحرك فعلًا على THH/يومي، في ملف SVG مشروح بالعربية.
 */
import { writeFileSync } from "node:fs";
import { aggregate, generateMinutes, getSessionWindow } from "../lib/market/generator";
import { getProfile } from "../lib/market/profiles";
import { analyzeStock } from "../lib/strategy/engine";
import type { Candle } from "../lib/types";

const SYM = "THH";
const now = new Date();
const win = getSessionWindow(now);
const profile = getProfile(SYM);
const minutes = generateMinutes(profile, win);
const daily = aggregate(minutes, "1D");
const a = analyzeStock(SYM, "1D", daily, daily, minutes);
const pat = a.structure.pattern!;
const st = a.structure;

/* ---------- window & scales ---------- */
const W = 1440;
const H = 900;
const M = { top: 120, right: 190, bottom: 70, left: 40 };
const pw = W - M.left - M.right;
const ph = H - M.top - M.bottom;

const n = daily.length;
const from = Math.max(0, pat.startIndex - 12);
const view: Candle[] = daily.slice(from);
const breakI = a.events.breakTime
  ? view.findIndex((c) => c.time === a.events.breakTime)
  : -1;
const retestI = a.events.retestTime
  ? view.findIndex((c) => c.time === a.events.retestTime)
  : -1;

let lo = Math.min(...view.map((c) => c.low));
let hi = Math.max(...view.map((c) => c.high));
const pad = (hi - lo) * 0.06;
lo -= pad;
hi += pad;
const X = (i: number) => M.left + ((i + 0.5) / view.length) * pw;
const Y = (p: number) => M.top + ((hi - p) / (hi - lo)) * ph;
const cw = Math.max(2, (pw / view.length) * 0.62);

const dateFmt = new Intl.DateTimeFormat("ar-SA-u-ca-gregory-nu-latn", {
  day: "2-digit",
  month: "short",
});
const dt = (t: number) => dateFmt.format(new Date(t * 1000));

const L: string[] = [];
L.push(
  `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${W} ${H}" font-family="'Segoe UI',Tahoma,Arial,sans-serif">`,
  `<rect width="${W}" height="${H}" fill="#0b1220"/>`,
);

/* ---------- title ---------- */
L.push(
  `<text x="${W - 24}" y="42" text-anchor="end" fill="#f8fafc" font-size="26" font-weight="700" direction="rtl">${SYM} · الإطار اليومي — النموذج المرجعي كما كشفه المحرك</text>`,
  `<text x="${W - 24}" y="74" text-anchor="end" fill="#38bdf8" font-size="19" font-weight="600" direction="rtl">الحكم: ${a.verdict.emoji} ${a.verdict.label} · نقاط الاستراتيجية ${a.score}/100</text>`,
  `<text x="${W - 24}" y="100" text-anchor="end" fill="#fbbf24" font-size="15" direction="rtl">${pat.headNote ?? ""}</text>`,
);

/* ---------- grid + price axis ---------- */
const ticks = 8;
for (let t = 0; t <= ticks; t++) {
  const p = lo + ((hi - lo) * t) / ticks;
  const y = Y(p);
  L.push(
    `<line x1="${M.left}" y1="${y}" x2="${W - M.right}" y2="${y}" stroke="#1e293b" stroke-width="1"/>`,
    `<text x="${W - M.right + 8}" y="${y + 4}" fill="#64748b" font-size="12">${p.toFixed(2)}</text>`,
  );
}
for (let i = 0; i < view.length; i += Math.ceil(view.length / 12)) {
  L.push(
    `<text x="${X(i)}" y="${H - M.bottom + 24}" text-anchor="middle" fill="#475569" font-size="11">${dt(view[i].time)}</text>`,
  );
}

/* ---------- candles ---------- */
view.forEach((c, i) => {
  const up = c.close >= c.open;
  const col = up ? "#22c55e" : "#ef4444";
  const x = X(i);
  L.push(`<line x1="${x}" y1="${Y(c.high)}" x2="${x}" y2="${Y(c.low)}" stroke="${col}" stroke-width="1.2"/>`);
  const yo = Y(c.open);
  const yc = Y(c.close);
  L.push(
    `<rect x="${x - cw / 2}" y="${Math.min(yo, yc)}" width="${cw}" height="${Math.max(2, Math.abs(yo - yc))}" fill="${col}"/>`,
  );
});

/* ---------- horizontal strategy lines ---------- */
const hline = (p: number, color: string, dash: string, label: string, lw = 1.6) => {
  const y = Y(p);
  L.push(
    `<line x1="${M.left}" y1="${y}" x2="${W - M.right}" y2="${y}" stroke="${color}" stroke-width="${lw}" ${dash ? `stroke-dasharray="${dash}"` : ""}/>`,
    `<text x="${W - M.right + 8}" y="${y - 6}" fill="${color}" font-size="13" font-weight="600" direction="rtl">${label}</text>`,
  );
};
hline(st.bottom.level, "#4ade80", "", `القاع المعتمد ${st.bottom.level.toFixed(2)}`);
hline(pat.neckline, "#f87171", "7 5", `خط العنق ${pat.neckline.toFixed(2)}`, 2);
hline(a.targets.main.price, "#fbbf24", "10 6", `🎯 الهدف المحوري ${a.targets.main.price.toFixed(2)}`, 2);
a.targets.stages.forEach((s, k) =>
  hline(s.price, "#94a3b8", "4 6", `مرحلة ${k + 1} — ${s.price.toFixed(2)}`, 1.1),
);

/* ---------- pattern sketch: l1 → h1 → head → h2 → l3 ---------- */
const pts = pat.points.map((p) => ({ x: X(p.index - from), y: Y(p.price) }));
L.push(
  `<polyline points="${pts.map((p) => `${p.x},${p.y}`).join(" ")}" fill="none" stroke="#38bdf8" stroke-width="2.4" stroke-linejoin="round" opacity="0.95"/>`,
);

/* point labels */
const labels = [
  { i: 0, txt: "الكتف الأيسر", price: pat.points[0].price, dy: 26, anchor: "middle" },
  { i: 2, txt: "الرأس (قاع مزدوج)", price: pat.points[2].price, dy: 30, anchor: "middle" },
  { i: 4, txt: "الكتف الأيمن", price: pat.points[4].price, dy: 26, anchor: "middle" },
];
for (const lb of labels) {
  const p = pat.points[lb.i];
  const x = X(p.index - from);
  const y = Y(p.price);
  L.push(
    `<circle cx="${x}" cy="${y}" r="6" fill="#0b1220" stroke="#38bdf8" stroke-width="2.5"/>`,
    `<text x="${x}" y="${y + lb.dy}" text-anchor="middle" fill="#7dd3fc" font-size="14" font-weight="600" direction="rtl">${lb.txt} ${lb.price.toFixed(2)}</text>`,
  );
}
/* double-bottom head markers (both head lows) */
const headLows = st.behavior.points.filter(
  (p) => p.index > pat.points[0].index && p.index < pat.points[4].index && p.kind === "low",
);
for (const p of [pat.points[2], ...headLows]) {
  const x = X(p.index - from);
  const y = Y(p.price);
  L.push(`<circle cx="${x}" cy="${y}" r="4" fill="#fbbf24" opacity="0.9"/>`);
}

/* ---------- event markers ---------- */
const marker = (i: number, color: string, txt: string) => {
  if (i < 0) return;
  const x = X(i);
  const yTop = Y(view[i].high);
  L.push(
    `<path d="M ${x} ${yTop - 12} l -9 16 h 18 Z" fill="${color}"/>`,
    `<text x="${x}" y="${yTop - 20}" text-anchor="middle" fill="${color}" font-size="15" font-weight="700" direction="rtl">${txt}</text>`,
  );
};
marker(breakI, "#4ade80", "① اختراق خط العنق");
marker(retestI, "#38bdf8", "② إعادة الاختبار — العنق صار دعمًا");

/* final rally annotation */
if (breakI >= 0) {
  const xl = X(view.length - 1);
  L.push(
    `<text x="${xl - 8}" y="${Y(view[view.length - 1].high) - 44}" text-anchor="end" fill="#22c55e" font-size="15" font-weight="700" direction="rtl">③ حركة صعودية قوية نحو الأهداف</text>`,
  );
}

/* ---------- legend ---------- */
const lg = [
  ["#22c55e", "شموع صاعدة"],
  ["#ef4444", "شموع هابطة"],
  ["#38bdf8", "رسم النموذج (كتف/رأس/كتف)"],
  ["#f87171", "خط العنق (مستوى التفعيل)"],
  ["#fbbf24", "الهدف المحوري — قمة شمعة التقسيم"],
  ["#4ade80", "القاع المعتمد"],
];
lg.forEach(([c, t], k) => {
  const y = M.top + 16 + k * 24;
  L.push(
    `<rect x="${M.left + 6}" y="${y - 10}" width="16" height="10" rx="2" fill="${c}"/>`,
    `<text x="${M.left + 30}" y="${y}" fill="#cbd5e1" font-size="13" direction="rtl">${t}</text>`,
  );
});

L.push(`</svg>`);
writeFileSync("model-THH.svg", L.join("\n"));
console.log("written model-THH.svg");
console.log("neckline:", pat.neckline.toFixed(3), "| break:", a.events.breakTime, "| retest:", a.events.retestTime);
