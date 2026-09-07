# -*- coding: utf-8 -*-
"""Lifecycle research for tradeable +70% post-reverse-split moves.

A case is successful when price reaches +70% during the move; subsequent
selling is not treated as failure. Daily features are cut strictly before the
explosion date. Intraday data is optional and explicitly marked unavailable
when the provider's historical interval limit prevents retrieval.
"""
from __future__ import annotations
import csv, json, math
from collections import Counter
from datetime import datetime
from pathlib import Path
import numpy as np
import pandas as pd
import yfinance as yf
from historical_study import add_indicators, fetch_ohlcv, safe_float

CASES_FILE = "historical_cases.json"
OUTPUT_FILE = "explosion_lifecycle.json"
CSV_FILE = "explosion_lifecycle.csv"


def dump(path, obj):
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


def first_post(df, split):
    return df[df.index >= pd.Timestamp(split)]


def pct(a, b):
    return (float(a) / float(b) - 1) * 100 if b and pd.notna(b) else None


def longest_near_support(series, support, tolerance=0.06):
    if support is None or not support:
        return 0
    best = cur = 0
    for value in series:
        if abs(float(value) / support - 1) <= tolerance:
            cur += 1; best = max(best, cur)
        else:
            cur = 0
    return best


def support_profile(pre):
    if len(pre) < 10:
        return {"support_price": None, "support_tests": 0, "support_stable_sessions": 0, "support_stable_days": 0, "support_note": "بيانات غير كافية"}
    lows = pre["Low"].tail(min(40, len(pre)))
    support = float(lows.quantile(0.20))
    tol = max(support * 0.05, 0.0001)
    tests = int((lows.sub(support).abs() <= tol).sum())
    stable = longest_near_support(pre["Close"].tail(min(40, len(pre))), support)
    return {"support_price": round(support, 6), "support_tests": tests, "support_stable_sessions": stable, "support_stable_days": stable, "support_tolerance_percent": 5.0}


def stage_metrics(df, split, event):
    post = first_post(df, split)
    event_ts = pd.Timestamp(event)
    pre_event = post[post.index < event_ts]
    if post.empty or pre_event.empty:
        return {"status": "insufficient_daily_data"}
    first = post.iloc[0]
    first_date = post.index[0]
    first5 = post.iloc[:min(5, len(post))]
    after_first = post.iloc[1:min(6, len(post))]
    base = float(first["Open"])
    first_close = float(first["Close"])
    high_before = float(pre_event["High"].max())
    high_date = pre_event["High"].idxmax().date().isoformat()
    trough_before = float(pre_event["Low"].min())
    trough_date = pre_event["Low"].idxmin().date().isoformat()
    high_i = int(pre_event["High"].values.argmax())
    trough_i = int(pre_event["Low"].values.argmin())
    support = support_profile(pre_event)
    indicators = add_indicators(df)
    last = indicators.loc[indicators.index < event_ts].iloc[-1]
    technical = {}
    for k in ["rsi14", "macd", "macd_signal", "macd_histogram", "ma20", "ma50", "volume_ratio_5d", "volume_ratio_10d", "volume_ratio_20d", "macd_slope_3d", "histogram_change", "ma20_slope_5d", "ma50_slope_5d"]:
        technical[k] = safe_float(last.get(k))
    return {
        "status": "ok",
        "split_date": str(split), "first_post_split_date": first_date.date().isoformat(),
        "first_post_split_open": round(base, 6), "first_post_split_high": round(float(first["High"]), 6),
        "first_post_split_low": round(float(first["Low"]), 6), "first_post_split_close": round(first_close, 6),
        "first_day_high_vs_open_percent": round(pct(first["High"], base), 2),
        "first_day_close_vs_open_percent": round(pct(first["Close"], base), 2),
        "first_day_volume": float(first["Volume"]),
        "first_5_sessions_high_vs_first_close_percent": round(pct(first5["High"].max(), first_close), 2),
        "first_5_sessions_close_vs_first_close_percent": round(pct(first5["Close"].max(), first_close), 2),
        "day_2_to_6_high_vs_first_close_percent": round(pct(after_first["High"].max(), first_close), 2) if not after_first.empty else None,
        "cleared_20_percent_after_split": bool((first5["High"].max() / first_close - 1) * 100 >= 20),
        "max_high_before_explosion": round(high_before, 6), "max_high_date_before_explosion": high_date,
        "drawdown_low_before_explosion": round(trough_before, 6), "drawdown_low_date_before_explosion": trough_date,
        "drawdown_from_pre_event_high_percent": round(pct(trough_before, high_before), 2),
        "recovery_from_trough_to_event_prev_close_percent": round(pct(pre_event["Close"].iloc[-1], trough_before), 2),
        "sessions_split_to_explosion": int(len(pre_event)),
        "sessions_from_high_to_trough": abs(trough_i - high_i),
        "pre_explosion_avg_volume": float(pre_event["Volume"].tail(5).mean()),
        "pre_explosion_volume_trend_5d_vs_20d": float(pre_event["Volume"].tail(5).mean() / pre_event["Volume"].tail(20).mean()) if pre_event["Volume"].tail(20).mean() else None,
        "technical_at_D_minus_1": technical,
        **support,
    }


def fetch_4h(ticker, event):
    # Yahoo generally limits 4h history to roughly 60 calendar days. Request
    # the exact window; unavailable is a valid, documented result.
    event_ts = pd.Timestamp(event)
    try:
        bars = yf.Ticker(ticker).history(start=event_ts - pd.Timedelta(days=12), end=event_ts + pd.Timedelta(days=1), interval="4h", auto_adjust=False, actions=False)
        if bars is None or bars.empty:
            return {"status": "unavailable", "reason": "مزود البيانات لم يرجع شموع 4 ساعات لهذه الفترة"}
        if isinstance(bars.columns, pd.MultiIndex): bars.columns = bars.columns.get_level_values(0)
        bars.index = pd.to_datetime(bars.index).tz_localize(None)
        pre = bars[bars.index < event_ts]
        if len(pre) < 5:
            return {"status": "unavailable", "reason": "عدد شموع 4 ساعات قبل الحدث غير كافٍ"}
        last = pre.iloc[-1]
        vol5 = pre["Volume"].tail(5).mean(); vol20 = pre["Volume"].tail(20).mean()
        ret = pre["Close"].pct_change() * 100
        return {"status": "ok", "bars_before_event": len(pre), "last_bar_utc": pre.index[-1].isoformat(), "last_open": safe_float(last["Open"]), "last_high": safe_float(last["High"]), "last_low": safe_float(last["Low"]), "last_close": safe_float(last["Close"]), "last_volume": safe_float(last["Volume"]), "range_5_bars_percent": safe_float((pre["High"].tail(5).max() / pre["Low"].tail(5).min() - 1) * 100), "return_5_bars_percent": safe_float((pre["Close"].iloc[-1] / pre["Close"].iloc[-6] - 1) * 100) if len(pre) >= 6 else None, "volume_ratio_5_vs_20": safe_float(vol5 / vol20) if vol20 else None, "volume_trend_last_3_vs_prior_3": safe_float(pre["Volume"].tail(3).mean() / pre["Volume"].iloc[-6:-3].mean()) if len(pre) >= 6 and pre["Volume"].iloc[-6:-3].mean() else None, "positive_bars_last_5": int((ret.tail(5) > 0).sum())}
    except Exception as exc:
        return {"status": "unavailable", "reason": str(exc)[:180]}


def main():
    raw = json.loads(Path(CASES_FILE).read_text(encoding="utf-8"))
    cases = raw.get("success_cases", [])
    rows, errors = [], []
    for i, case in enumerate(cases, 1):
        ticker = case["ticker"]; print(f"[{i}/{len(cases)}] {ticker}")
        df = fetch_ohlcv(ticker, case["split_date"])
        if df is None:
            rows.append({"ticker": ticker, "split_date": case["split_date"], "explosion_date": case["explosion_date"], "status": "no_daily_data", "four_hour": {"status": "unavailable"}})
            errors.append({"ticker": ticker, "error": "no_daily_data"}); continue
        rows.append({"ticker": ticker, "company": case.get("company"), "split_ratio": case.get("split_ratio"), "explosion_date": case["explosion_date"], "threshold": case.get("threshold"), "maximum_gain_percent": case.get("maximum_gain_percent"), "classification": case.get("classification"), "lifecycle": stage_metrics(df, case["split_date"], case["explosion_date"]), "four_hour": fetch_4h(ticker, case["explosion_date"])})
    ok4 = sum(1 for r in rows if r.get("four_hour", {}).get("status") == "ok")
    classes = Counter(r.get("classification") for r in rows)
    out = {"generated_at": datetime.utcnow().replace(microsecond=0).isoformat() + "Z", "methodology": {"success_definition": "+70% reached; later fade is not failure", "daily_features_cutoff": "strictly before explosion date", "four_hour_note": "4h availability depends on provider historical interval limits", "support_definition": "20th percentile of recent pre-event lows with 5% touch tolerance"}, "sample": {"cases": len(rows), "daily_ok": sum(r.get("lifecycle", {}).get("status") == "ok" for r in rows), "four_hour_ok": ok4, "four_hour_unavailable": len(rows) - ok4, "classifications": dict(classes), "errors": errors}, "common_summary": {"first_day_20_percent_rate": float(sum(bool(r.get("lifecycle", {}).get("cleared_20_percent_after_split")) for r in rows) / len(rows) * 100) if rows else None, "median_first_day_high_vs_open_percent": float(np.nanmedian([r["lifecycle"]["first_day_high_vs_open_percent"] for r in rows if r.get("lifecycle", {}).get("status") == "ok"])), "median_drawdown_before_explosion_percent": float(np.nanmedian([r["lifecycle"]["drawdown_from_pre_event_high_percent"] for r in rows if r.get("lifecycle", {}).get("status") == "ok"])), "median_support_tests": float(np.nanmedian([r["lifecycle"]["support_tests"] for r in rows if r.get("lifecycle", {}).get("status") == "ok"])), "median_support_stable_sessions": float(np.nanmedian([r["lifecycle"]["support_stable_sessions"] for r in rows if r.get("lifecycle", {}).get("status") == "ok"])), "median_sessions_split_to_explosion": float(np.nanmedian([r["lifecycle"]["sessions_split_to_explosion"] for r in rows if r.get("lifecycle", {}).get("status") == "ok"]))}, "cases": rows}
    dump(OUTPUT_FILE, out)
    fields = ["ticker", "split_date", "explosion_date", "classification", "maximum_gain_percent", "first_post_split_open", "first_day_high_vs_open_percent", "first_day_close_vs_open_percent", "first_5_sessions_high_vs_first_close_percent", "day_2_to_6_high_vs_first_close_percent", "cleared_20_percent_after_split", "drawdown_from_pre_event_high_percent", "recovery_from_trough_to_event_prev_close_percent", "sessions_split_to_explosion", "support_price", "support_tests", "support_stable_sessions", "four_hour_status", "four_hour_volume_ratio_5_vs_20"]
    with open(CSV_FILE, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader()
        for r in rows:
            l = r.get("lifecycle", {}); h = r.get("four_hour", {})
            w.writerow({"ticker": r.get("ticker"), "split_date": l.get("split_date"), "explosion_date": r.get("explosion_date"), "classification": r.get("classification"), "maximum_gain_percent": r.get("maximum_gain_percent"), **{k: l.get(k) for k in fields if k in l}, "four_hour_status": h.get("status"), "four_hour_volume_ratio_5_vs_20": h.get("volume_ratio_5_vs_20")})
    print(f"Saved {OUTPUT_FILE}: {len(rows)} cases; 4h available={ok4}")

if __name__ == "__main__": main()
