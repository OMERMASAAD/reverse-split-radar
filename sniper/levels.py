# -*- coding: utf-8 -*-
"""
محرك المستويات: كشف «الثبات الأفقي» بنفس منطق قنص الذعر الأصلي، ثم خريطة
مستويات كاملة للجلسة (قاعدة، قاع/قمة اليوم، الافتتاح، ما قبل السوق، نطاق
الافتتاح، الفجوة، الأرقام المستديرة) — وهي طبقة تحليل إضافية.
"""
from __future__ import annotations

from datetime import time as dtime

import numpy as np
import pandas as pd

from .config import (BASE_TOUCH_TOL_PCT, CONS_MIN_MIN, CONS_RANGE_PCT, GAP_MIN_PCT,
                     NEAR_LOW_PCT, ROUND_NUMBER_STEP)
from .indicators import rolling_slope, stdev_pct

REGULAR_OPEN, REGULAR_CLOSE = dtime(9, 30), dtime(16, 0)
OPENING_RANGE_END = dtime(10, 0)


def detect_base(day: pd.DataFrame):
    """
    يمشي للخلف من آخر شمعة طالما مدى النافذة ≤ CONS_RANGE_PCT — نفس خوارزمية الأصل.
    يعيد (نافذة القاعدة، طابع بداية القاعدة) أو (None, None) إن لم يتوفر اليوم.
    """
    if day is None or day.empty:
        return None, None
    last_ts = day.index[-1]
    high_ts = day["High"].astype(float).idxmax()
    after = day.loc[high_ts:]
    hi, lo, start_ts = -np.inf, np.inf, last_ts
    for ts, row in after.iloc[::-1].iterrows():
        hi = max(hi, float(row["High"]))
        lo = min(lo, float(row["Low"]))
        if lo <= 0 or (hi - lo) / lo * 100.0 > CONS_RANGE_PCT:
            break
        start_ts = ts
    return after.loc[start_ts:], start_ts


def base_metrics(win: pd.DataFrame, day: pd.DataFrame, start_ts, last_ts) -> dict:
    """قياسات جودة القاعدة (إضافية) فوق منطق الثبات الأصلي."""
    day_low = float(day["Low"].astype(float).min())
    base_low = float(win["Low"].astype(float).min())
    base_high = float(win["High"].astype(float).max())
    tol = abs(base_low) * BASE_TOUCH_TOL_PCT / 100.0
    touches = int((win["Low"].astype(float) <= base_low + tol).sum())
    half = max(1, len(win) // 2)
    first_min = float(win["Low"].astype(float).iloc[:half].min())
    second_min = float(win["Low"].astype(float).iloc[half:].min())
    higher_lows = bool(second_min >= first_min - tol)
    slope = rolling_slope(win["Close"].astype(float), look=len(win))
    closes = win["Close"].astype(float)
    slope_pct = None
    if slope is not None and len(closes) and float(closes.mean()) > 0:
        slope_pct = round(slope / float(closes.mean()) * 100.0, 4)
    price = float(win["Close"].astype(float).iloc[-1])
    return {
        "base_low": round(base_low, 4),
        "base_high": round(base_high, 4),
        "base_mid": round((base_low + base_high) / 2.0, 4),
        "base_bars": int(len(win)),
        "base_range_pct": round((base_high - base_low) / base_low * 100.0, 2) if base_low else None,
        "base_start": start_ts.isoformat(),
        "base_low_ts": win["Low"].astype(float).idxmin().isoformat(),
        "base_touches": touches,
        "base_higher_lows": higher_lows,
        "base_tightness_pct": stdev_pct(win),
        "base_slope_pct": slope_pct,
        "hold_min": int((last_ts - start_ts).total_seconds() / 60.0) + 5,
        "hold_needed": CONS_MIN_MIN,
        "near_low": bool(day_low > 0 and (base_low - day_low) / day_low * 100.0 <= NEAR_LOW_PCT),
        "dist_base_low_pct": round((price / base_low - 1.0) * 100.0, 2) if base_low else None,
        "dist_base_high_pct": round((base_high / price - 1.0) * 100.0, 2) if price else None,
        "day_low_gap_pct": round((base_low - day_low) / day_low * 100.0, 2) if day_low else None,
    }


def _slice(day: pd.DataFrame, t0: dtime | None = None, t1: dtime | None = None) -> pd.DataFrame:
    times = day.index.time
    mask = np.ones(len(day), dtype=bool)
    if t0 is not None:
        mask &= np.array([t >= t0 for t in times])
    if t1 is not None:
        mask &= np.array([t < t1 for t in times])
    return day[mask]


def session_levels(df: pd.DataFrame, day: pd.DataFrame) -> dict:
    """خريطة مستويات الجلسة: افتتاح، فجوة، ما قبل السوق، نطاق الافتتاح، 5 أيام."""
    price = float(day["Close"].astype(float).iloc[-1])
    day_high = float(day["High"].astype(float).max())
    day_low = float(day["Low"].astype(float).min())
    day_open = float(day["Open"].astype(float).iloc[0])
    prior = df[df.index.date < day.index[-1].date()]
    prev_close = float(prior["Close"].astype(float).iloc[-1]) if len(prior) else None
    pre = _slice(day, None, REGULAR_OPEN)
    regular = _slice(day, REGULAR_OPEN, REGULAR_CLOSE)
    opening = _slice(day, REGULAR_OPEN, OPENING_RANGE_END)
    post = _slice(day, REGULAR_CLOSE, None)

    def hl(x):
        if x is None or x.empty:
            return None, None
        return round(float(x["High"].astype(float).max()), 4), round(float(x["Low"].astype(float).min()), 4)

    pre_high, pre_low = hl(pre)
    or_high, or_low = hl(opening)
    post_high, post_low = hl(post)
    five_high = round(float(df["High"].astype(float).max()), 4)
    five_low = round(float(df["Low"].astype(float).min()), 4)
    step = max(ROUND_NUMBER_STEP, ROUND_NUMBER_STEP * (10 ** int(np.floor(np.log10(max(price, 1e-6))))))
    below = float(np.floor(price / step) * step)
    above = float(np.ceil(price / step) * step)
    return {
        "price": round(price, 4),
        "day_open": round(day_open, 4),
        "day_high": round(day_high, 4),
        "day_low": round(day_low, 4),
        "prev_close": round(prev_close, 4) if prev_close else None,
        "change_pct": round((price / prev_close - 1.0) * 100.0, 2) if prev_close else None,
        "gap_pct": round((day_open / prev_close - 1.0) * 100.0, 2) if prev_close else None,
        "has_gap": bool(prev_close and abs(day_open / prev_close - 1.0) * 100.0 >= GAP_MIN_PCT),
        "gap_direction": ("up" if prev_close and day_open > prev_close else "down") if prev_close else None,
        "premarket_high": pre_high, "premarket_low": pre_low,
        "opening_range_high": or_high, "opening_range_low": or_low,
        "after_hours_high": post_high, "after_hours_low": post_low,
        "five_day_high": five_high, "five_day_low": five_low,
        "round_number_below": round(below, 4), "round_number_above": round(above, 4),
        "range_of_day_pct": round((day_high - day_low) / day_low * 100.0, 2) if day_low else None,
        "position_in_range_pct": round((price - day_low) / (day_high - day_low) * 100.0, 1)
        if day_high > day_low else None,
        "drop_from_high_pct": round((price / day_high - 1.0) * 100.0, 1) if day_high else None,
        "bounce_from_low_pct": round((price / day_low - 1.0) * 100.0, 1) if day_low else None,
        "day_bars": int(len(day)),
        "premarket_bars": int(len(pre)), "regular_bars": int(len(regular)), "post_bars": int(len(post)),
        "phase": ("premarket" if len(pre) and not len(regular) else
                  "after_hours" if len(post) and not len(regular) else
                  "regular" if len(regular) else "unknown"),
    }


def levels_payload(df: pd.DataFrame) -> dict:
    """الواجهة الموحّدة: كشف القاعدة + مستويات الجلسة من إطار 5m كامل."""
    if df is None or df.empty:
        return {}
    last_ts = df.index[-1]
    day = df[df.index.date == last_ts.date()]
    win, start_ts = detect_base(day)
    out = session_levels(df, day)
    if win is not None and len(win):
        out["base"] = base_metrics(win, day, start_ts, last_ts)
        out["_base_window"] = win
    return out


__all__ = ["detect_base", "base_metrics", "session_levels", "levels_payload"]
