/**
 * APEX Terminal — core domain types
 */

export type Timeframe = "5m" | "15m" | "1h" | "4h" | "1D";

export const TIMEFRAMES: Timeframe[] = ["5m", "15m", "1h", "4h", "1D"];

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

export type MacdState =
  | "BULLISH_CROSS"
  | "BULLISH_EXPANSION"
  | "BULLISH_FADE"
  | "BEARISH_CROSS"
  | "BEARISH_EXPANSION"
  | "NEUTRAL";

export type ObvFlow = "INFLOW" | "OUTFLOW" | "MIXED";

export type RsiZone = "OVERBOUGHT" | "STRONG" | "BULLISH" | "WEAK" | "OVERSOLD";

export type PatternKind =
  | "INVERTED_HEAD_SHOULDERS"
  | "DOUBLE_BOTTOM"
  | "HIGHER_LOWS"
  | "RANGE";

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
  pivotLow: number;
  depth: number;
  points: SwingPoint[];
  startIndex: number;
}

export type StatusCode = "SQUEEZE" | "BASE" | "RISKY" | "MOMENTUM";

export interface StatusResult {
  code: StatusCode;
  label: string;
  emoji: string;
  detail: string;
}

export interface BuySignal {
  time: number;
  price: number;
}

export interface ChecklistItem {
  id: string;
  label: string;
  state: "pass" | "warn" | "fail";
  detail: string;
}

export interface TradePlan {
  entry: number;
  stop: number;
  t1: number;
  t2: number;
  rr1: number;
  rr2: number;
  riskPct: number;
  breakoutMode: boolean;
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
  timeframe: Timeframe;
  candles: Candle[];
  quote: Quote;
  vwap: {
    series: (number | null)[];
    value: number;
    distancePct: number;
    above: boolean;
    mode: "SESSION" | "ANCHORED";
  };
  obv: {
    series: number[];
    ema: number[];
    flow: ObvFlow;
    slopePct: number;
    vsEmaPct: number;
  };
  macd: {
    macd: number[];
    signal: number[];
    hist: number[];
    state: MacdState;
    freshCross: boolean;
    expanding: boolean;
    histValue: number;
  };
  rsi: {
    series: number[];
    value: number;
    zone: RsiZone;
    warning: boolean;
  };
  squeeze: {
    bandwidthPct: number;
    percentile: number;
    squeezing: boolean;
    fired: boolean;
    /** lowest BB-width percentile seen during the compression window */
    compressionPct: number;
  };
  atr: number;
  pattern: PatternResult;
  plan: TradePlan;
  status: StatusResult;
  signals: BuySignal[];
  checklist: ChecklistItem[];
  /** normalized 0..100 composite score */
  score: number;
}
