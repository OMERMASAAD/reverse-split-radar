# -*- coding: utf-8 -*-
"""
Historical Reverse-Split Research
---------------------------------
A separate, assumption-light research pipeline. It intentionally does not
change the live dashboard scanner or apply the old 20-50 day filter.

Research order:
  universe -> OHLCV -> event labels -> D-5..D-1 features -> controls -> stats
  -> chronological validation -> cautious strategy proposal.

Historical float/short fields are left null unless a dated observation exists;
current Yahoo values are never substituted for historical values.
"""
from __future__ import annotations

import json
import math
import os
import csv
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

try:
    from scipy.stats import mannwhitneyu
except Exception:
    mannwhitneyu = None

CANDIDATES_FILE = "reverse_split_candidates.json"
OUTPUT_FILE = "historical_study.json"
ANALYSIS_FILE = "historical_analysis.json"
CASES_FILE = "historical_cases.json"
FEATURES_CSV = "historical_features.csv"
BACKTEST_FILE = "strategy_backtest.json"
REPORT_FILE = "strategy_report.md"
LOOKBACK_CALENDAR_DAYS = 120
PRE_SESSIONS = 5
MIN_CONTEXT_SESSIONS = 55
EXPLOSION_THRESHOLDS = (70.0, 100.0, 200.0)
TRUE_EXPLOSION_WINDOW = 5
MIN_SINGLE_DAY_BURST = 20.0  # operational label boundary, not a strategy filter
CONTROL_MAX_PER_TICKER = 8
RANDOM_SEED = 42


def safe_float(value):
    try:
        value = float(value)
        return None if not math.isfinite(value) else value
    except Exception:
        return None


def load_json(path, default):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return default


def dump_json(path, payload):
    Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


def write_features_csv(cases, controls):
    rows = []
    for item in cases + controls:
        row = {"ticker": item.get("ticker"), "label": item.get("label"), "observation_date": item.get("observation_date") or item.get("explosion_date")}
        row.update(item.get("features") or {})
        row.pop("pre_explosion_sessions", None)
        rows.append(row)
    fields = sorted({k for row in rows for k in row})
    with open(FEATURES_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def load_universe():
    raw = load_json(CANDIDATES_FILE, [])
    rows = raw if isinstance(raw, list) else raw.get("candidates", [])
    today = date.today()
    out = []
    for row in rows:
        if not isinstance(row, dict) or not row.get("ticker"):
            continue
        try:
            split_date = pd.Timestamp(row.get("split_date")).date()
        except Exception:
            continue
        age = (today - split_date).days
        if age < 0 or age > LOOKBACK_CALENDAR_DAYS:
            continue
        out.append({
            "ticker": str(row["ticker"]).upper(),
            "company": row.get("company"),
            "split_date": split_date.isoformat(),
            "split_ratio": row.get("reverse_split") or row.get("split_ratio"),
            "split_age_calendar_days": age,
        })
    return out


def fetch_ohlcv(ticker, split_date):
    # We fetch enough pre-split context for indicators and the full post-split
    # window. No current fundamentals are used as historical values.
    start = pd.Timestamp(split_date) - pd.Timedelta(days=120)
    end = pd.Timestamp.today().normalize() + pd.Timedelta(days=2)
    try:
        df = yf.Ticker(ticker).history(start=start, end=end, auto_adjust=False, actions=False)
        if df is None or df.empty:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        needed = [c for c in ["Open", "High", "Low", "Close", "Volume"] if c in df.columns]
        df = df[needed].copy().dropna(subset=["Open", "High", "Low", "Close"])
        df.index = pd.to_datetime(df.index).tz_localize(None).normalize()
        return df[~df.index.duplicated(keep="last")]
    except Exception as exc:
        print(f"WARN {ticker}: {exc}")
        return None


def add_indicators(df):
    x = df.copy()
    close = x["Close"]
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14, min_periods=14).mean()
    loss = (-delta.clip(upper=0)).rolling(14, min_periods=14).mean()
    rs = gain / loss.replace(0, np.nan)
    x["rsi14"] = 100 - (100 / (1 + rs))
    ema12 = close.ewm(span=12, adjust=False, min_periods=12).mean()
    ema26 = close.ewm(span=26, adjust=False, min_periods=26).mean()
    x["macd"] = ema12 - ema26
    x["macd_signal"] = x["macd"].ewm(span=9, adjust=False, min_periods=9).mean()
    x["macd_histogram"] = x["macd"] - x["macd_signal"]
    x["ma20"] = close.rolling(20, min_periods=20).mean()
    x["ma50"] = close.rolling(50, min_periods=50).mean()
    x["return_1d"] = close.pct_change() * 100
    for n in (5, 10, 20):
        x[f"avg_volume_{n}d"] = x["Volume"].rolling(n, min_periods=n).mean()
        x[f"volume_ratio_{n}d"] = x["Volume"] / x[f"avg_volume_{n}d"].replace(0, np.nan)
    x["volume_acceleration"] = x["volume_ratio_5d"].diff()
    x["macd_slope_3d"] = x["macd"].diff(3)
    x["histogram_change"] = x["macd_histogram"].diff()
    x["ma20_slope_5d"] = x["ma20"].pct_change(5) * 100
    x["ma50_slope_5d"] = x["ma50"].pct_change(5) * 100
    return x


def trading_age(df, split_date, idx):
    return int((df.index <= idx).sum() - (df.index < pd.Timestamp(split_date)).sum())


def first_post_split(df, split_date):
    return df[df.index >= pd.Timestamp(split_date)]


def find_events(df, split_date):
    post = first_post_split(df, split_date)
    if len(post) < MIN_CONTEXT_SESSIONS:
        return []
    events = []
    for threshold in EXPLOSION_THRESHOLDS:
        found = None
        for i in range(PRE_SESSIONS, len(post)):
            prior = post.iloc[:i]
            reference = float(prior["Close"].tail(PRE_SESSIONS).min())
            if not math.isfinite(reference) or reference <= 0:
                continue
            price = float(post.iloc[i]["High"])
            gain = (price / reference - 1) * 100
            if gain < threshold:
                continue
            window = post.iloc[i:min(i + TRUE_EXPLOSION_WINDOW, len(post))]
            prior_closes = post["Close"].shift(1)
            daily_jump = ((window["High"] / prior_closes.loc[window.index]) - 1) * 100
            max_single_jump = float(daily_jump.replace([np.inf, -np.inf], np.nan).max()) if not daily_jump.empty else 0.0
            max_close_gain = float((window["Close"].max() / reference - 1) * 100)
            is_burst = max_single_jump >= MIN_SINGLE_DAY_BURST
            classification = "true_explosion" if is_burst else "gradual_rally"
            if is_burst:
                closes = window["Close"]
                if float(closes.max()) < reference * (1 + threshold / 100) * 0.90:
                    classification = "temporary_spike"
                elif float(window["Low"].min()) <= float(window["High"].max()) * 0.70:
                    classification = "pump_and_fade"
                elif max_close_gain >= threshold:
                    classification = "sustained_breakout"
            found = {
                "explosion_date": post.index[i].date().isoformat(),
                "threshold": threshold,
                "reference_price": round(reference, 6),
                "explosion_price": round(float(post.iloc[i]["Close"]), 6),
                "maximum_high": round(float(post.iloc[i:min(i + 10, len(post))]["High"].max()), 6),
                "maximum_gain_percent": round(float((post.iloc[i:min(i + 10, len(post))]["High"].max() / reference - 1) * 100), 2),
                "days_from_split_to_explosion": (post.index[i].date() - pd.Timestamp(split_date).date()).days,
                "trading_sessions_from_split_to_explosion": trading_age(df, split_date, post.index[i]),
                "max_single_day_jump_percent": round(max_single_jump, 2),
                "classification": classification,
            }
            events.append(found)
            break
    return events


def support_tests(window):
    if len(window) < 5:
        return 0
    support = float(window["Low"].quantile(0.20))
    tolerance = max(support * 0.04, 0.0001)
    return int((window["Low"].sub(support).abs() <= tolerance).sum())


def make_features(df, split_date, event_date):
    idx = pd.Timestamp(event_date)
    hist = df.loc[df.index < idx]
    if len(hist) < MIN_CONTEXT_SESSIONS:
        return None
    last = hist.iloc[-1]
    w5 = hist.tail(5)
    w10 = hist.tail(10)
    w20 = hist.tail(20)
    close = float(last["Close"])
    low20, high20 = float(w20["Low"].min()), float(w20["High"].max())
    low50, high50 = float(hist.tail(50)["Low"].min()), float(hist.tail(50)["High"].max())
    prev_peak = float(hist["High"].iloc[:-1].tail(20).max()) if len(hist) > 1 else high20
    prev_low = float(hist["Low"].iloc[:-1].tail(20).min()) if len(hist) > 1 else low20
    row = {
        "observation_date": idx.date().isoformat(),
        "window_end": hist.index[-1].date().isoformat(),
        "split_age_trading_sessions": trading_age(df, split_date, hist.index[-1]),
        "open": float(last["Open"]), "high": float(last["High"]), "low": float(last["Low"]), "close": close,
        "daily_range_percent": (float(last["High"] - last["Low"]) / close * 100) if close else None,
        "body_percent": (float(abs(last["Close"] - last["Open"])) / close * 100) if close else None,
        "upper_wick_percent": (float(last["High"] - max(last["Open"], last["Close"])) / close * 100) if close else None,
        "lower_wick_percent": (float(min(last["Open"], last["Close"]) - last["Low"]) / close * 100) if close else None,
        "gap_percent": float((last["Open"] / hist["Close"].iloc[-2] - 1) * 100) if len(hist) > 1 else None,
        "change_percent": float(last["return_1d"]),
        "distance_from_recent_low_percent": (close / low20 - 1) * 100 if low20 else None,
        "distance_from_recent_high_percent": (close / high20 - 1) * 100 if high20 else None,
        "distance_from_ma20_percent": (close / float(last["ma20"]) - 1) * 100 if pd.notna(last["ma20"]) and last["ma20"] else None,
        "distance_from_ma50_percent": (close / float(last["ma50"]) - 1) * 100 if pd.notna(last["ma50"]) and last["ma50"] else None,
        "highest_high_20d": high20, "lowest_low_20d": low20, "highest_high_50d": high50, "lowest_low_50d": low50,
        "drawdown_from_previous_peak_percent": (close / prev_peak - 1) * 100 if prev_peak else None,
        "recovery_from_recent_bottom_percent": (close / prev_low - 1) * 100 if prev_low else None,
        "volume": float(last["Volume"]),
        "avg_volume_5d": float(last["avg_volume_5d"]) if pd.notna(last["avg_volume_5d"]) else None,
        "avg_volume_10d": float(last["avg_volume_10d"]) if pd.notna(last["avg_volume_10d"]) else None,
        "avg_volume_20d": float(last["avg_volume_20d"]) if pd.notna(last["avg_volume_20d"]) else None,
        "volume_ratio_5d": float(last["volume_ratio_5d"]) if pd.notna(last["volume_ratio_5d"]) else None,
        "volume_ratio_10d": float(last["volume_ratio_10d"]) if pd.notna(last["volume_ratio_10d"]) else None,
        "volume_ratio_20d": float(last["volume_ratio_20d"]) if pd.notna(last["volume_ratio_20d"]) else None,
        "volume_acceleration": float(last["volume_acceleration"]) if pd.notna(last["volume_acceleration"]) else None,
        "volume_trend_5d_vs_20d": float(w5["Volume"].mean() / w20["Volume"].mean()) if w20["Volume"].mean() else None,
        "price_volume_change_5d": float((w5["Close"].iloc[-1] / w5["Close"].iloc[0] - 1) * 100),
        "rsi14": float(last["rsi14"]) if pd.notna(last["rsi14"]) else None,
        "rsi_change_5d": float(last["rsi14"] - hist["rsi14"].iloc[-6]) if len(hist) >= 6 and pd.notna(last["rsi14"]) and pd.notna(hist["rsi14"].iloc[-6]) else None,
        "macd": float(last["macd"]) if pd.notna(last["macd"]) else None,
        "macd_signal": float(last["macd_signal"]) if pd.notna(last["macd_signal"]) else None,
        "macd_histogram": float(last["macd_histogram"]) if pd.notna(last["macd_histogram"]) else None,
        "histogram_change": float(last["histogram_change"]) if pd.notna(last["histogram_change"]) else None,
        "macd_slope_3d": float(last["macd_slope_3d"]) if pd.notna(last["macd_slope_3d"]) else None,
        "ma20": float(last["ma20"]) if pd.notna(last["ma20"]) else None,
        "ma50": float(last["ma50"]) if pd.notna(last["ma50"]) else None,
        "ma20_slope_5d": float(last["ma20_slope_5d"]) if pd.notna(last["ma20_slope_5d"]) else None,
        "ma50_slope_5d": float(last["ma50_slope_5d"]) if pd.notna(last["ma50"]) else None,
        "ma20_above_ma50": bool(last["ma20"] > last["ma50"]) if pd.notna(last["ma20"]) and pd.notna(last["ma50"]) else None,
        "support_tests_20d": support_tests(w20),
        "consolidation_range_5d_percent": float((w5["High"].max() / w5["Low"].min() - 1) * 100),
        "consolidation_range_10d_percent": float((w10["High"].max() / w10["Low"].min() - 1) * 100),
        "higher_lows_5d": int((w5["Low"].diff().dropna() > 0).sum()),
        "lower_highs_5d": int((w5["High"].diff().dropna() < 0).sum()),
        "volatility_10d_percent": float(w10["return_1d"].std()) if len(w10) > 1 else None,
        # Historical float/short values are deliberately unavailable here.
        "float_shares_historical": None, "short_interest_historical": None,
        "short_percent_historical": None, "days_to_cover_historical": None,
        "historical_fundamentals_note": "غير متاح تاريخيًا؛ لم يتم استبداله بقيم اليوم.",
    }
    # Compact D-5..D-1 OHLCV vector for direct case review.
    row["pre_explosion_sessions"] = [
        {"relative_day": f"D-{i}", "date": d.date().isoformat(), "open": float(r.Open), "high": float(r.High), "low": float(r.Low), "close": float(r.Close), "volume": float(r.Volume)}
        for i, (d, r) in enumerate(w5.iloc[::-1].iterrows(), start=1)
    ][::-1]
    return row


def median(values):
    vals = [v for v in values if v is not None and math.isfinite(float(v))]
    return float(np.median(vals)) if vals else None


def feature_stats(success, control):
    success_names = set(success[0]) if success else set()
    control_names = set(control[0]) if control else set()
    names = sorted(success_names & control_names)
    result = {}
    for name in names:
        a = np.array([x[name] for x in success if isinstance(x.get(name), (int, float)) and math.isfinite(float(x[name]))], dtype=float)
        b = np.array([x[name] for x in control if isinstance(x.get(name), (int, float)) and math.isfinite(float(x[name]))], dtype=float)
        if len(a) < 3 or len(b) < 3:
            continue
        p = None
        if mannwhitneyu:
            try: p = float(mannwhitneyu(a, b, alternative="two-sided").pvalue)
            except Exception: pass
        # Cliff's delta: probability success value > control - reverse.
        sample_a, sample_b = a[:200], b[:200]
        delta = float((sum(x > y for x in sample_a for y in sample_b) - sum(x < y for x in sample_a for y in sample_b)) / (len(sample_a) * len(sample_b)))
        result[name] = {
            "success_n": int(len(a)), "control_n": int(len(b)),
            "success_mean": float(np.mean(a)), "control_mean": float(np.mean(b)),
            "success_median": float(np.median(a)), "control_median": float(np.median(b)),
            "success_std": float(np.std(a, ddof=1)) if len(a) > 1 else 0.0,
            "control_std": float(np.std(b, ddof=1)) if len(b) > 1 else 0.0,
            "difference_mean": float(np.mean(a) - np.mean(b)),
            "cliffs_delta": delta, "mann_whitney_p": p,
        }
    return result


def chronological_split(rows):
    rows = sorted(rows, key=lambda x: x["explosion_date"] if x.get("label") == "success" else x.get("observation_date", ""))
    n = len(rows)
    if n < 10:
        return {"train": rows, "validation": [], "out_of_sample": [], "status": "insufficient_sample_for_split"}
    return {"train": rows[: int(n * .6)], "validation": rows[int(n * .6): int(n * .8)], "out_of_sample": rows[int(n * .8):], "status": "chronological_split"}


def main():
    universe = load_universe()
    print(f"Historical research universe: {len(universe)} reverse splits in last {LOOKBACK_CALENDAR_DAYS} days")
    cases, all_controls, errors = [], [], []
    for n, item in enumerate(universe, 1):
        ticker = item["ticker"]
        print(f"[{n}/{len(universe)}] {ticker}")
        df = fetch_ohlcv(ticker, item["split_date"])
        if df is None:
            errors.append({"ticker": ticker, "error": "no_ohlcv"})
            continue
        df = add_indicators(df)
        events = find_events(df, item["split_date"])
        primary = next((e for e in events if e["threshold"] == 70.0 and e["classification"] in {"true_explosion", "sustained_breakout", "pump_and_fade", "temporary_spike"}), None)
        if primary:
            feat = make_features(df, item["split_date"], primary["explosion_date"])
            if feat:
                cases.append({**item, **primary, "label": "success", "features": feat, "all_threshold_events": events})
        # Controls are pre-event observations from the same reverse-split universe.
        post = first_post_split(df, item["split_date"])
        event_dates = {pd.Timestamp(e["explosion_date"]) for e in events if e["threshold"] == 70.0}
        candidates = []
        for i in range(MIN_CONTEXT_SESSIONS, len(post) - 5):
            d = post.index[i]
            if any(abs((d - ed).days) <= 7 for ed in event_dates):
                continue
            feat = make_features(df, item["split_date"], d.date().isoformat())
            if feat: candidates.append({**item, "observation_date": d.date().isoformat(), "label": "control", "features": feat})
        # Deterministic spacing avoids overweighting a single ticker.
        for c in candidates[::max(1, len(candidates) // CONTROL_MAX_PER_TICKER or 1)][:CONTROL_MAX_PER_TICKER]:
            all_controls.append(c)
    success_features = [x["features"] for x in cases]
    control_features = [x["features"] for x in all_controls]
    stats = feature_stats(success_features, control_features)
    splits = chronological_split(cases)
    # Discovery is descriptive and conservative: no strategy is approved without
    # both separation and enough observations; thresholds are not hard-coded trade rules.
    discovered = []
    for name, s in stats.items():
        p = s.get("mann_whitney_p")
        if p is not None and p <= 0.10 and abs(s["cliffs_delta"]) >= 0.147:
            discovered.append({"feature": name, **s, "candidate_status": "research_candidate_not_validated"})
    discovered.sort(key=lambda x: (x.get("mann_whitney_p", 1), -abs(x.get("cliffs_delta", 0))))
    by_class = Counter(e["classification"] for c in cases for e in c.get("all_threshold_events", []) if e["threshold"] == 70.0)
    output = {
        "generated_at": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "methodology_version": "v1.0_no_lookahead",
        "universe": {"lookback_calendar_days": LOOKBACK_CALENDAR_DAYS, "count": len(universe), "no_age_filter": True},
        "labels": {"thresholds_percent": list(EXPLOSION_THRESHOLDS), "primary_threshold_percent": 70.0, "true_explosion_window_sessions": TRUE_EXPLOSION_WINDOW, "minimum_single_day_burst_percent": MIN_SINGLE_DAY_BURST, "note": "Operational event labels separate fast bursts from gradual rallies; labels may use post-event prices, features never do."},
        "sample": {"success_cases": len(cases), "control_windows": len(all_controls), "errors": errors, "classification_70": dict(by_class)},
        "data_quality": {"historical_float_available": False, "historical_short_available": False, "note": "Current float/short values were not substituted for historical values."},
        "statistical_features": stats,
        "discovered_candidates": discovered[:30],
        "validation": {"split": splits["status"], "train_cases": len(splits["train"]), "validation_cases": len(splits["validation"]), "out_of_sample_cases": len(splits["out_of_sample"]), "status": "not_validated" if len(splits["out_of_sample"]) < 5 else "requires_walk_forward_and_more_history"},
        "strategy_proposal": {"status": "not_approved", "reason": "هذه أول لقطة 120 يومًا؛ لا يجوز اعتماد استراتيجية أو عتبات قبل تراكم حالات كافية واختبار زمني خارج العينة.", "candidate_features": [x["feature"] for x in discovered[:10]]},
    }
    dump_json(OUTPUT_FILE, output)
    dump_json(ANALYSIS_FILE, {"generated_at": output["generated_at"], "feature_statistics": stats, "discovered_candidates": discovered[:30], "classifications": dict(by_class), "data_quality": output["data_quality"]})
    dump_json(CASES_FILE, {"generated_at": output["generated_at"], "success_cases": cases, "control_windows": all_controls})
    write_features_csv(cases, all_controls)
    dump_json(BACKTEST_FILE, {"status": "not_run", "reason": "لا توجد استراتيجية مكتشفة ومثبتة خارج العينة بعد؛ يمنع تشغيل Backtest انتقائيًا قبل اكتمال validation/OOS.", "training_cases": len(splits["train"]), "validation_cases": len(splits["validation"]), "out_of_sample_cases": len(splits["out_of_sample"])})
    Path(REPORT_FILE).write_text("""# تقرير البحث التاريخي لأسهم Reverse Split

## الحالة

هذا التقرير مولد آليًا من بيانات تاريخية، ولا يعلن استراتيجية تداول قبل اكتمال الفصل الزمني والتحقق خارج العينة.

## المنهج

تغطي الدراسة آخر 120 يومًا تقويميًا من عمليات التقسيم العكسي المؤكدة. لكل حالة انفجار، تُحسب الخصائص باستخدام البيانات المتاحة حتى D-1 فقط، وتُقارن بنوافذ ضابطة من نفس الكون. لم تُستخدم قيم الفلوت أو الشورت الحالية كبديل عن القيم التاريخية.

## الملفات

- `historical_study.json`: ملخص المنهج والعينة والحالة.
- `historical_analysis.json`: إحصاءات الخصائص والمرشحات البحثية.
- `historical_cases.json`: الحالات والنوافذ الضابطة التفصيلية.
- `historical_features.csv`: جدول الخصائص للتحليل الخارجي.
- `strategy_backtest.json`: حالة الـBacktest، ولا يُشغّل قبل التحقق.

## ملاحظة منهجية

النتائج المرشحة ليست استراتيجية معتمدة. يلزم تراكم حالات كافية، تحقق زمني، واختبار خارج العينة قبل اعتماد أي حد للسعر أو RSI أو الحجم أو الفلوت أو الشورت.
""", encoding="utf-8")
    print(f"Saved {OUTPUT_FILE}: {len(cases)} success cases, {len(all_controls)} controls, {len(discovered)} candidates")


if __name__ == "__main__":
    main()
