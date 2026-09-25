"use client";

/** Lightweight SVG micro-charts for the analysis panel. */

export function LinePairChart({
  a,
  b,
  height = 56,
  colorA = "#38bdf8",
  colorB = "#f59e0b",
  fill = true,
}: {
  a: number[];
  b: number[];
  height?: number;
  colorA?: string;
  colorB?: string;
  fill?: boolean;
}) {
  const W = 300;
  const all = [...a, ...b].filter((v) => isFinite(v));
  if (all.length < 2) return <div style={{ height }} />;
  let min = Math.min(...all);
  let max = Math.max(...all);
  const pad = (max - min) * 0.12 || Math.abs(max) * 0.02 || 1;
  min -= pad;
  max += pad;

  const toPath = (arr: number[]) => {
    const n = arr.length;
    return arr
      .map((v, i) => {
        const x = (i / (n - 1)) * W;
        const y = height - ((v - min) / (max - min)) * height;
        return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
      })
      .join(" ");
  };

  const pathA = toPath(a);
  const areaA = fill
    ? `${pathA} L${W},${height} L0,${height} Z`
    : "";

  return (
    <svg
      viewBox={`0 0 ${W} ${height}`}
      preserveAspectRatio="none"
      className="h-full w-full"
      style={{ height }}
    >
      {fill && <path d={areaA} fill={colorA} opacity={0.08} />}
      <path d={toPath(b)} fill="none" stroke={colorB} strokeWidth={1.4} strokeDasharray="4 3" opacity={0.9} />
      <path d={pathA} fill="none" stroke={colorA} strokeWidth={1.8} />
    </svg>
  );
}

export function HistogramChart({
  hist,
  macdLine,
  signalLine,
  height = 56,
}: {
  hist: number[];
  macdLine: number[];
  signalLine: number[];
  height?: number;
}) {
  const W = 300;
  const n = hist.length;
  if (n < 2) return <div style={{ height }} />;
  const all = [...hist, ...macdLine, ...signalLine].filter((v) => isFinite(v));
  if (!all.length) return <div style={{ height }} />;
  const absMax = Math.max(...all.map(Math.abs)) || 1;

  const mid = height / 2;
  const scale = (v: number) => mid - (v / absMax) * (mid - 3);
  const bw = W / n;

  const toPath = (arr: number[]) =>
    arr
      .map((v, i) => {
        const x = i * bw + bw / 2;
        const y = scale(v);
        return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
      })
      .join(" ");

  return (
    <svg
      viewBox={`0 0 ${W} ${height}`}
      preserveAspectRatio="none"
      className="h-full w-full"
      style={{ height }}
    >
      <line x1={0} x2={W} y1={mid} y2={mid} stroke="#263349" strokeWidth={0.75} />
      {hist.map((v, i) => {
        const y = scale(v);
        const h = Math.abs(y - mid);
        return (
          <rect
            key={i}
            x={i * bw + bw * 0.15}
            y={Math.min(y, mid)}
            width={bw * 0.7}
            height={Math.max(h, 0.6)}
            fill={v >= 0 ? "#10b981" : "#ef4444"}
            opacity={0.55}
          />
        );
      })}
      <path d={toPath(macdLine)} fill="none" stroke="#38bdf8" strokeWidth={1.5} />
      <path d={toPath(signalLine)} fill="none" stroke="#f59e0b" strokeWidth={1.3} strokeDasharray="4 3" />
    </svg>
  );
}
