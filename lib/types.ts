/**
 * APEX Terminal — core domain types
 * "Reverse-Split Anchor Strategy" (استراتيجية الارتكاز لأسهم التقسيم العكسي والهابطة)
 */

export type Timeframe = "5m" | "15m" | "1h" | "4h" | "1D";

/** The strategy dashboard works on the daily + 4-hour frames only. */
export const TIMEFRAMES: Timeframe[] = ["4h", "1D"];

/** Arabic labels for the timeframe toggle / chips */
export const TIMEFRAME_AR: Record<Timeframe, string> = {
  "5m": "5د",
  "15m": "15د",
  "1h": "ساعة",
  "4h": "4س",
  "1D": "يومي",
};

export interface Candle {
  /** unix seconds */
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export type RsiZone = "OVERBOUGHT" | "STRONG" | "BULLISH" | "WEAK" | "OVERSOLD";

export type PatternKind = "INVERTED_HEAD_SHOULDERS" | "HEAD_SHOULDERS";

export interface SwingPoint {
  index: number;
  time: number;
  price: number;
  kind: "low" | "high";
}

export interface PatternResult {
  kind: PatternKind;
  label: string;
  emoji: string;
  description: string;
  /** 0..100 */
  confidence: number;
  neckline: number;
  depth: number;
  points: SwingPoint[];
  startIndex: number;
  /** when the head itself is a double bottom (as in the reference model) */
  headNote?: string | null;
  /** sessions from left shoulder to right shoulder */
  spanBars?: number;
}

export type StatusCode = "ANCHORED" | "BUILDING" | "BREAKOUT" | "BROKEN";

export interface StatusResult {
  code: StatusCode;
  label: string;
  emoji: string;
  detail: string;
}

export interface BottomInfo {
  level: number;
  index: number;
  time: number;
  /** consecutive sessions holding above the approved floor */
  holdsSessions: number;
  held: boolean;
}

export type BottomBehavior = "HIGHER_LOW" | "FLAT_BOTTOM" | "LOWER_LOW" | "NONE";

export interface TargetLevel {
  price: number;
  label: string;
  time: number | null;
  kind: "main" | "stage" | "support" | "neckline";
}

export interface ShortInfo {
  floatPct: number;
  daysToCover: number;
  trend: "rising" | "falling" | "flat";
  deltaPct: number;
}

export interface NewsItem {
  /** session offset from today (negative = past, positive = upcoming) */
  d: number;
  time: number;
  title: string;
  source: string;
  sentiment: "positive" | "negative" | "neutral";
  upcoming?: boolean;
}

export interface ChecklistItem {
  id: string;
  label: string;
  state: "yes" | "no" | "partial";
  detail: string;
}

export interface Quote {
  last: number;
  change: number;
  changePct: number;
  open: number;
  high: number;
  low: number;
  volume: number;
  prevClose: number;
}

export interface AnalysisResult {
  symbol: string;
  symbolName: string;
  sector: string;
  timeframe: Timeframe;
  candles: Candle[];
  /** daily frame — the strategy reference series */
  daily: Candle[];
  quote: Quote;
  hasSplit: boolean;
  split: { ratioLabel: string; time: number | null; spikeHigh: number } | null;
  emas: { ema20: number[]; ema30: number[]; ema50: number[] };
  vwap: {
    series: (number | null)[];
    value: number;
    distancePct: number;
    above: boolean;
    mode: "ANCHORED" | "SESSION";
  };
  rsi: {
    /** RSI of the chart timeframe (pane display) */
    series: number[];
    value: number;
    zone: RsiZone;
    /** daily-frame exit-oversold signal (strategy rule) */
    dailyValue: number;
    dailySeries: number[];
    exitOversold: boolean;
    crossRecent: boolean;
    signalTime: number | null;
  };
  structure: {
    bottom: BottomInfo;
    behavior: { kind: BottomBehavior; label: string; ok: boolean; detail: string; points: SwingPoint[] };
    testRetest: {
      testedResistance: boolean;
      resistanceLevel: number | null;
      testDetail: string;
      retestedBottom: boolean;
      retestDetail: string;
      sweep: boolean;
      sweepDetail: string;
      sweepTime: number | null;
      /** neckline breakout & its re-test (the reference model sequence) */
      neckBreak: boolean;
      neckBreakTime: number | null;
      neckRetest: boolean;
      neckRetestTime: number | null;
      neckRetestDetail: string;
    };
    pattern: PatternResult | null;
  };
  targets: {
    main: TargetLevel;
    stages: TargetLevel[];
    supports: TargetLevel[];
    neckline: number | null;
  };
  checklist: ChecklistItem[];
  verdict: StatusResult;
  score: number;
  /** chart-timeframe neckline events → on-chart markers */
  events: { breakTime: number | null; retestTime: number | null };
  short: ShortInfo;
  news: NewsItem[];
  newsTime: number;
}
