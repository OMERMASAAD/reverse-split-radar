/* Engine smoke test — prints a strategy summary per symbol × timeframe. */
import { aggregate, generateMinutes, getCandles, getSessionWindow } from "../lib/market/generator";
import { getProfile } from "../lib/market/profiles";
import { analyze } from "../lib/strategy/engine";
import type { Timeframe } from "../lib/types";

const now = new Date();
const win = getSessionWindow(now);
console.log(
  `session window: last=${win.days[win.days.length - 1].toISOString().slice(0, 10)} minutes=${win.finalSessionMinutes} open=${win.marketOpen}\n`,
);

const tfs: Timeframe[] = ["5m", "15m", "1h", "4h", "1D"];
const symbols = ["THH", "ELPW", "MSGY", "AAPL", "NVDA", "GME"];

for (const sym of symbols) {
  const minutes = generateMinutes(getProfile(sym), win);
  const rows: string[] = [];
  for (const tf of tfs) {
    const candles = aggregate(minutes, tf);
    const a = analyze(sym, tf, candles, minutes);
    const planOk = a.plan.stop < a.plan.entry && a.plan.entry <= a.plan.t1 && a.plan.t1 < a.plan.t2;
    rows.push(
      [
        tf.padEnd(3),
        `bars=${String(candles.length).padStart(5)}`,
        a.status.code.padEnd(9),
        `${a.pattern.kind.slice(0, 14).padEnd(14)}${String(a.pattern.confidence).padStart(3)}%`,
        `rsi=${a.rsi.value.toFixed(0).padStart(3)}`,
        a.macd.state.slice(0, 9).padEnd(9),
        a.obv.flow.padEnd(7),
        `vwap=${(a.vwap.distancePct >= 0 ? "+" : "") + a.vwap.distancePct.toFixed(2)}%`,
        `sqz=${a.squeeze.percentile.toFixed(0).padStart(3)}pct${a.squeeze.fired ? "🔥" : "  "}`,
        `sig=${String(a.signals.length).padStart(2)}`,
        `score=${String(a.score).padStart(2)}`,
        planOk ? "plan✓" : `plan✗ stop=${a.plan.stop.toFixed(2)} entry=${a.plan.entry.toFixed(2)} t1=${a.plan.t1.toFixed(2)} t2=${a.plan.t2.toFixed(2)}`,
      ].join(" "),
    );
  }
  const last = minutes[minutes.length - 1];
  console.log(`── ${sym} (${getProfile(sym).name}) last=${last.close} ──`);
  rows.forEach((r) => console.log("   " + r));
  console.log();
}
