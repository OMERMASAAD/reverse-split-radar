/* Engine smoke test — anchor-strategy summary per symbol × timeframe. */
import { aggregate, generateMinutes, getSessionWindow } from "../lib/market/generator";
import { getProfile } from "../lib/market/profiles";
import { analyzeStock } from "../lib/strategy/engine";
import type { Timeframe } from "../lib/types";

const now = new Date();
const win = getSessionWindow(now);
console.log(
  `session: last=${win.days[win.days.length - 1].toISOString().slice(0, 10)} minutes=${win.finalSessionMinutes} open=${win.marketOpen}\n`,
);

const tfs: Timeframe[] = ["4h", "1D"];
const symbols = ["THH", "ELPW", "MSGY", "AAPL", "GME"];

for (const sym of symbols) {
  const profile = getProfile(sym);
  const minutes = generateMinutes(profile, win);
  const daily = aggregate(minutes, "1D");
  for (const tf of tfs) {
    const candles = tf === "1D" ? daily : aggregate(minutes, tf);
    const a = analyzeStock(sym, tf, candles, daily, minutes);
    const st = a.structure;
    console.log(
      [
        `${sym}/${tf}`.padEnd(9),
        a.verdict.code.padEnd(9),
        `score=${String(a.score).padStart(2)}`,
        `floor=${st.bottom.level.toFixed(2)}×${st.bottom.holdsSessions}d${st.bottom.held ? "✓" : "✗"}`,
        st.behavior.kind.slice(0, 10).padEnd(10),
        `test=${st.testRetest.testedResistance ? "Y" : "n"}`,
        `retest=${st.testRetest.retestedBottom ? "Y" : "n"}`,
        `sweep=${st.testRetest.sweep ? "Y" : "n"}`,
        `neck=${st.testRetest.neckBreak ? (st.testRetest.neckRetest ? "break+retest" : "break") : "-"}`,
        `pat=${a.structure.pattern ? a.structure.pattern.kind.slice(0, 6) + "@" + a.structure.pattern.neckline.toFixed(2) : "none".padEnd(9)}`,
        `rsi=${a.rsi.dailyValue.toFixed(0)}${a.rsi.exitOversold ? "↗" : " "}`,
        `main=${a.targets.main.price.toFixed(2)}`,
        `stages=[${a.targets.stages.map((s) => s.price.toFixed(2)).join(",")}]`,
        `vwap=${a.vwap.distancePct >= 0 ? "+" : ""}${a.vwap.distancePct.toFixed(1)}%`,
      ].join(" "),
    );
  }
  console.log();
}
