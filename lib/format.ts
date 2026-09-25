/** Display formatting helpers */

export function fmtPrice(v: number, digits?: number): string {
  if (!isFinite(v)) return "—";
  const d =
    digits ??
    (v >= 1000 ? 2 : v >= 100 ? 2 : v >= 10 ? 2 : v >= 1 ? 3 : 4);
  return v.toLocaleString("en-US", {
    minimumFractionDigits: d,
    maximumFractionDigits: d,
  });
}

export function fmtSigned(v: number, digits = 2): string {
  if (!isFinite(v)) return "—";
  const s = fmtPrice(Math.abs(v), digits);
  return `${v >= 0 ? "+" : "−"}${s}`;
}

export function fmtPct(v: number, digits = 2): string {
  if (!isFinite(v)) return "—";
  return `${v >= 0 ? "+" : ""}${v.toFixed(digits)}%`;
}

export function fmtCompactVolume(v: number): string {
  if (!isFinite(v) || v <= 0) return "0";
  if (v >= 1e9) return `${(v / 1e9).toFixed(2)}B`;
  if (v >= 1e6) return `${(v / 1e6).toFixed(2)}M`;
  if (v >= 1e3) return `${(v / 1e3).toFixed(1)}K`;
  return `${Math.round(v)}`;
}

export function fmtClock(d: Date): string {
  return d
    .toLocaleTimeString("en-US", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false,
      timeZone: "America/New_York",
    })
    .replace(/:/g, ":");
}

export function fmtDay(time: number): string {
  const d = new Date(time * 1000);
  return d.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  });
}

export function fmtBarTime(time: number, intraday: boolean): string {
  const d = new Date(time * 1000);
  if (intraday) {
    return d.toLocaleString("en-US", {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
      timeZone: "America/New_York",
    });
  }
  return d.toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    timeZone: "America/New_York",
  });
}
