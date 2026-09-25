"use client";

import { useEffect, useRef } from "react";
import {
  CandlestickSeries,
  ColorType,
  CrosshairMode,
  HistogramSeries,
  LineStyle,
  LineSeries,
  createChart,
  createSeriesMarkers,
  type CandlestickData,
  type HistogramData,
  type IChartApi,
  type IPriceLine,
  type ISeriesApi,
  type ISeriesMarkersPluginApi,
  type LineData,
  type MouseEventParams,
  type Time,
  type UTCTimestamp,
} from "lightweight-charts";
import { Boxes, Gauge } from "lucide-react";
import { TIMEFRAME_AR, type AnalysisResult } from "@/lib/types";
import { getProfile } from "@/lib/market/profiles";
import {
  AR_LOCALE,
  fmtBarTime,
  fmtCompactVolume,
  fmtPct,
  fmtPrice,
  fmtSigned,
} from "@/lib/format";

const UP = "#10b981";
const DOWN = "#ef4444";
const VWAP_COLOR = "#fb923c";
const SUPPORT = "#22c55e";
const NECKLINE = "#ef4444";
const TARGET = "#34d399";
const TARGET2 = "#6ee7b7";
const STOP = "#f87171";

function LegendChip({ color, label, dashed }: { color: string; label: string; dashed?: boolean }) {
  return (
    <span className="flex items-center gap-1.5 text-[10px] font-semibold tracking-wide text-muted">
      <span
        className="inline-block h-0 w-4 border-t-2"
        style={{
          borderColor: color,
          borderStyle: dashed ? "dashed" : "solid",
        }}
      />
      {label}
    </span>
  );
}

export default function ChartCanvas({ analysis }: { analysis: AnalysisResult }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const vwapRef = useRef<ISeriesApi<"Line"> | null>(null);
  const volumeRef = useRef<ISeriesApi<"Histogram"> | null>(null);
  const markersRef = useRef<ISeriesMarkersPluginApi<Time> | null>(null);
  const priceLinesRef = useRef<IPriceLine[]>([]);
  const analysisRef = useRef<AnalysisResult>(analysis);
  analysisRef.current = analysis;

  // legend DOM refs
  const lTime = useRef<HTMLSpanElement>(null);
  const lO = useRef<HTMLSpanElement>(null);
  const lH = useRef<HTMLSpanElement>(null);
  const lL = useRef<HTMLSpanElement>(null);
  const lC = useRef<HTMLSpanElement>(null);
  const lV = useRef<HTMLSpanElement>(null);
  const lVwap = useRef<HTMLSpanElement>(null);

  const profile = getProfile(analysis.symbol);
  const precision = profile.tick < 0.01 ? 4 : 2;
  const minMove = profile.tick;

  /* ---------------- chart bootstrap (once) ---------------- */
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    const chart = createChart(el, {
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: "#8ba0bd",
        fontSize: 11,
        fontFamily:
          "'JetBrains Mono', ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, monospace",
        attributionLogo: false,
      },
      localization: {
        locale: AR_LOCALE,
        dateFormat: "dd MMMM",
      },
      grid: {
        vertLines: { color: "rgba(139,160,189,0.05)" },
        horzLines: { color: "rgba(139,160,189,0.07)" },
      },
      crosshair: {
        mode: CrosshairMode.Normal,
        vertLine: { color: "#46587a", width: 1, style: LineStyle.Dotted, labelBackgroundColor: "#1e293b" },
        horzLine: { color: "#46587a", width: 1, style: LineStyle.Dotted, labelBackgroundColor: "#1e293b" },
      },
      rightPriceScale: {
        borderColor: "rgba(38,51,73,0.9)",
        scaleMargins: { top: 0.1, bottom: 0.08 },
        entireTextOnly: true,
      },
      timeScale: {
        borderColor: "rgba(38,51,73,0.9)",
        timeVisible: true,
        secondsVisible: false,
        rightOffset: 6,
        barSpacing: 9,
        minBarSpacing: 0.5,
      },
      autoSize: false,
    });
    chartRef.current = chart;

    const candles = chart.addSeries(
      CandlestickSeries,
      {
        upColor: UP,
        downColor: DOWN,
        borderUpColor: UP,
        borderDownColor: DOWN,
        wickUpColor: UP,
        wickDownColor: DOWN,
        priceLineVisible: false,
        lastValueVisible: true,
      },
      0,
    );
    candleRef.current = candles;

    const vwapLine = chart.addSeries(
      LineSeries,
      {
        color: VWAP_COLOR,
        lineWidth: 2,
        lineStyle: LineStyle.Solid,
        priceLineVisible: false,
        lastValueVisible: false,
        crosshairMarkerVisible: false,
      },
      0,
    );
    vwapRef.current = vwapLine;

    const volume = chart.addSeries(
      HistogramSeries,
      {
        priceFormat: { type: "volume" },
        priceLineVisible: false,
        lastValueVisible: false,
      },
      1,
    );
    volumeRef.current = volume;
    const panes = chart.panes();
    if (panes[1]) {
      panes[1].setHeight(96);
      panes[1].setStretchFactor(0.18);
    }

    markersRef.current = createSeriesMarkers(candles, []);

    const paintLegend = (
      time: number,
      o: number,
      h: number,
      l: number,
      c: number,
      v: number,
      vwap: number | null,
    ) => {
      const a = analysisRef.current;
      const tick = getProfile(a.symbol).tick;
      const prec = tick < 0.01 ? 4 : 2;
      if (lTime.current)
        lTime.current.textContent = fmtBarTime(time, a.timeframe !== "1D");
      if (lO.current) lO.current.textContent = fmtPrice(o, prec);
      if (lH.current) lH.current.textContent = fmtPrice(h, prec);
      if (lL.current) lL.current.textContent = fmtPrice(l, prec);
      if (lC.current) {
        lC.current.textContent = fmtPrice(c, prec);
        lC.current.style.color = c >= o ? UP : DOWN;
      }
      if (lV.current) lV.current.textContent = fmtCompactVolume(v);
      if (lVwap.current) {
        lVwap.current.textContent =
          vwap != null ? fmtPrice(vwap, prec) : "—";
        lVwap.current.style.color = VWAP_COLOR;
      }
    };

    chart.subscribeCrosshairMove((param: MouseEventParams) => {
      const cs = candleRef.current;
      if (!cs) return;
      const cd = param.seriesData?.get(cs) as CandlestickData<UTCTimestamp> | undefined;
      const vd = param.seriesData?.get(volumeRef.current!) as HistogramData<UTCTimestamp> | undefined;
      const ld = param.seriesData?.get(vwapRef.current!) as LineData<UTCTimestamp> | undefined;
      if (!cd || param.time == null) {
        const a = analysisRef.current;
        const bars = a.candles;
        const lastBar = bars[bars.length - 1];
        if (lastBar) {
          const vArr = a.vwap.series;
          paintLegend(lastBar.time, lastBar.open, lastBar.high, lastBar.low, lastBar.close, lastBar.volume, vArr[vArr.length - 1]);
        }
        return;
      }
      paintLegend(
        Number(param.time),
        cd.open,
        cd.high,
        cd.low,
        cd.close,
        vd?.value ?? 0,
        ld?.value ?? null,
      );
    });

    const ro = new ResizeObserver(() => {
      if (!containerRef.current || !chartRef.current) return;
      chartRef.current.applyOptions({
        width: containerRef.current.clientWidth,
        height: containerRef.current.clientHeight,
      });
    });
    ro.observe(el);
    chart.applyOptions({ width: el.clientWidth, height: el.clientHeight });

    return () => {
      ro.disconnect();
      markersRef.current?.detach();
      markersRef.current = null;
      chart.remove();
      chartRef.current = null;
      candleRef.current = null;
      vwapRef.current = null;
      volumeRef.current = null;
      priceLinesRef.current = [];
    };
  }, []);

  /* ---------------- data sync ---------------- */
  useEffect(() => {
    const chart = chartRef.current;
    const cs = candleRef.current;
    const vs = vwapRef.current;
    const hs = volumeRef.current;
    if (!chart || !cs || !vs || !hs) return;

    const { candles, vwap, plan, pattern, signals, timeframe, symbol } = analysis;
    const prof = getProfile(symbol);

    cs.applyOptions({
      priceFormat: {
        type: "price",
        precision: prof.tick < 0.01 ? 4 : 2,
        minMove: prof.tick,
      },
    });

    cs.setData(
      candles.map((c) => ({
        time: c.time as UTCTimestamp,
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close,
      })),
    );

    const vwapData: LineData<UTCTimestamp>[] = [];
    candles.forEach((c, i) => {
      const v = vwap.series[i];
      if (v != null && !isNaN(v)) vwapData.push({ time: c.time as UTCTimestamp, value: v });
    });
    vs.setData(vwapData);

    hs.setData(
      candles.map((c) => ({
        time: c.time as UTCTimestamp,
        value: c.volume,
        color:
          c.close >= c.open ? "rgba(16,185,129,0.42)" : "rgba(239,68,68,0.36)",
      })),
    );

    // ---- automated drawn levels ----
    priceLinesRef.current.forEach((l) => cs.removePriceLine(l));
    const lines: IPriceLine[] = [];
    lines.push(
      cs.createPriceLine({
        price: pattern.pivotLow,
        color: SUPPORT,
        lineWidth: 2,
        lineStyle: LineStyle.Solid,
        axisLabelVisible: true,
        title: `▲ الدعم ${fmtPrice(pattern.pivotLow, precision)}`,
      }),
      cs.createPriceLine({
        price: pattern.neckline,
        color: NECKLINE,
        lineWidth: 2,
        lineStyle: LineStyle.Solid,
        axisLabelVisible: true,
        title: `⛔ خط الرقبة ${fmtPrice(pattern.neckline, precision)}`,
      }),
      cs.createPriceLine({
        price: plan.t1,
        color: TARGET,
        lineWidth: 2,
        lineStyle: LineStyle.Dashed,
        axisLabelVisible: true,
        title: `🎯 هدف 1 ${fmtPrice(plan.t1, precision)}`,
      }),
      cs.createPriceLine({
        price: plan.t2,
        color: TARGET2,
        lineWidth: 2,
        lineStyle: LineStyle.Dashed,
        axisLabelVisible: true,
        title: `🎯 هدف 2 ${fmtPrice(plan.t2, precision)}`,
      }),
      cs.createPriceLine({
        price: plan.stop,
        color: STOP,
        lineWidth: 2,
        lineStyle: LineStyle.Dashed,
        axisLabelVisible: true,
        title: `🛑 وقف الخسارة ${fmtPrice(plan.stop, precision)}`,
      }),
    );
    priceLinesRef.current = lines;

    // ---- buy signal arrows ----
    markersRef.current?.setMarkers(
      signals.map((s) => ({
        time: s.time as UTCTimestamp,
        position: "belowBar" as const,
        color: "#34d399",
        shape: "arrowUp" as const,
        text: "شراء",
        size: 0.9,
      })),
    );

    const n = candles.length;
    const visible = timeframe === "1D" ? 130 : timeframe === "4h" ? 150 : 170;
    chart.timeScale().setVisibleLogicalRange({
      from: Math.max(0, n - visible),
      to: n - 1 + 8,
    });

    // reset legend to the latest bar
    const lastBar = candles[n - 1];
    if (lastBar && lC.current) {
      const v = vwap.series[n - 1];
      if (lTime.current)
        lTime.current.textContent = fmtBarTime(lastBar.time, timeframe !== "1D");
      if (lO.current) lO.current.textContent = fmtPrice(lastBar.open, precision);
      if (lH.current) lH.current.textContent = fmtPrice(lastBar.high, precision);
      if (lL.current) lL.current.textContent = fmtPrice(lastBar.low, precision);
      if (lC.current) {
        lC.current.textContent = fmtPrice(lastBar.close, precision);
        lC.current.style.color = lastBar.close >= lastBar.open ? UP : DOWN;
      }
      if (lV.current) lV.current.textContent = fmtCompactVolume(lastBar.volume);
      if (lVwap.current) lVwap.current.textContent = v != null ? fmtPrice(v, precision) : "—";
    }
  }, [analysis, precision, minMove]);

  /* ---------------- header stats ---------------- */
  const q = analysis.quote;
  const up = q.change >= 0;

  return (
    <section className="card flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
      {/* chart card header */}
      <div className="flex flex-wrap items-center gap-x-6 gap-y-2 border-b border-line-soft px-4 py-3">
        <div className="flex items-baseline gap-3">
          <div>
            <div className="num text-lg font-black tracking-[0.18em] text-ink">
              {analysis.symbol}
              <span className="ms-2 rounded-md border border-line bg-well px-1.5 py-0.5 align-middle text-[10px] font-bold text-sky">
                {TIMEFRAME_AR[analysis.timeframe]}
              </span>
            </div>
            <div className="text-[11.5px] text-muted">
              {analysis.symbolName} · {profile.sector}
            </div>
          </div>
        </div>

        <div className="flex items-baseline gap-2.5">
          <span className="num text-2xl font-black text-ink">
            {fmtPrice(q.last, precision)}
          </span>
          <span
            className={`num flex items-center gap-1 rounded-lg border px-2 py-1 text-[12px] font-bold ${
              up
                ? "border-bull/40 bg-bull/10 text-bull-soft"
                : "border-bear/40 bg-bear/10 text-bear-soft"
            }`}
          >
            {fmtSigned(q.change, precision)} ({fmtPct(q.changePct)})
          </span>
        </div>

        <div className="hidden items-center gap-4 text-[11px] text-faint md:flex">
          <span>
            افتتاح <b className="num text-muted">{fmtPrice(q.open, precision)}</b>
          </span>
          <span>
            أعلى <b className="num text-bull-soft">{fmtPrice(q.high, precision)}</b>
          </span>
          <span>
            أدنى <b className="num text-bear-soft">{fmtPrice(q.low, precision)}</b>
          </span>
          <span>
            الحجم <b className="num text-muted">{fmtCompactVolume(q.volume)}</b>
          </span>
        </div>

        <div className="ms-auto hidden items-center gap-3.5 lg:flex">
          <LegendChip color={VWAP_COLOR} label="VWAP" />
          <LegendChip color={SUPPORT} label="الدعم" />
          <LegendChip color={NECKLINE} label="خط الرقبة" />
          <LegendChip color={TARGET} label="هدف 1 / 2" dashed />
          <LegendChip color={STOP} label="وقف الخسارة" dashed />
        </div>
      </div>

      {/* canvas */}
      <div className="relative min-h-0 flex-1">
        <div ref={containerRef} dir="ltr" className="absolute inset-0" />

        {/* hover legend */}
        <div className="pointer-events-none absolute left-4 top-3 z-10">
          <div className="flex items-center gap-2 text-[10.5px] font-semibold tracking-wide text-faint">
            <Boxes className="h-3.5 w-3.5 text-sky/70" />
            <span className="num">{analysis.symbol}</span>
            <span>· {TIMEFRAME_AR[analysis.timeframe]} · تغذية محاكاة</span>
          </div>
          <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 rounded-lg border border-line-soft/60 bg-abyss/75 px-2.5 py-1.5 text-[11px] backdrop-blur-sm">
            <span className="text-faint" ref={lTime}>—</span>
            <span className="text-muted">
              افتتاح <b className="num text-ink" ref={lO}>—</b>
            </span>
            <span className="text-muted">
              أعلى <b className="num text-ink" ref={lH}>—</b>
            </span>
            <span className="text-muted">
              أدنى <b className="num text-ink" ref={lL}>—</b>
            </span>
            <span className="text-muted">
              إغلاق <b className="num" ref={lC}>—</b>
            </span>
            <span className="text-muted">
              الحجم <b className="num text-ink" ref={lV}>—</b>
            </span>
            <span className="text-muted">
              VWAP <b className="num" style={{ color: VWAP_COLOR }} ref={lVwap}>—</b>
            </span>
          </div>
        </div>

        {/* squeeze gauge chip */}
        <div className="pointer-events-none absolute right-3 top-3 z-10">
          <div className="flex items-center gap-2 rounded-lg border border-line-soft/60 bg-abyss/75 px-2.5 py-1.5 text-[10.5px] font-semibold backdrop-blur-sm">
            <Gauge className={`h-3.5 w-3.5 ${analysis.squeeze.squeezing ? "text-gold" : "text-faint"}`} />
            <span className="text-faint">عرض بولنجر</span>
            <b className={`num ${analysis.squeeze.squeezing ? "text-gold" : "text-muted"}`}>
              المئين {analysis.squeeze.percentile.toFixed(0)}
            </b>
            {analysis.squeeze.fired && (
              <span className="rounded bg-bull/15 px-1.5 py-0.5 font-bold text-bull-soft">
                انطلق 🚀
              </span>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}
