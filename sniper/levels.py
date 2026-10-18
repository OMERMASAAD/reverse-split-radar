# -*- coding: utf-8 -*-
"""
محرك المستويات: كشف «الثبات الأفقي» بنفس منطق قنص الذعر الأصلي، ثم خريطة
مستويات كاملة للجلسة (قاعدة، قاع/قمة اليوم، الافتتاح، ما قبل السوق، نطاق
الافتتاح، الفجوة، الأرقام المستديرة) — وهي طبقة تحليل إضافية.
V2: تحسين كشف موجة الصعود السابقة — يحدد قاع الحركة وقمتها ونسبة الصعود
وحجم التداول والدولار والوقت وما إذا كانت خلال الجلسة أو عدة جلسات.
"""
from __future__ import annotations

from datetime import time as dtime

import numpy as np
import pandas as pd

from .config import (BASE_TOUCH_TOL_PCT, CONS_MIN_MIN, CONS_RANGE_PCT, GAP_MIN_PCT,
                     NEAR_LOW_PCT, ROUND_NUMBER_STEP, RUNUP_MIN_PCT, RUNUP_VOLUME_MIN,
                     RUNUP_DOLLAR_VOLUME_MIN, RUNUP_MIN_BARS, RUNUP_TIME_MIN_MIN)
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
    """
    قياسات جودة القاعدة فوق منطق الثبات الأصلي.

    مرجع «قرب القاع» هو **قاع ما بعد القمة** (نهاية موجة الهبوط) لا قاع اليوم المطلق،
    لأن السهم في هذا النموذج صعد أولًا من قاع بعيد جدًا قبل أن ينهار.
    """
    day_low = float(day["Low"].astype(float).min())
    high_ts = day["High"].astype(float).idxmax()
    after_peak_low = float(day.loc[high_ts:, "Low"].astype(float).min())
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
    prior = win["High"].astype(float).iloc[:-1]
    base_high_prior = float(prior.max()) if len(prior) else base_high
    return {
        "base_low": round(base_low, 4),
        "base_high": round(base_high, 4),
        "base_high_prior": round(base_high_prior, 4),
        "broke_base": bool(price > base_high_prior),
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
        "post_peak_low": round(after_peak_low, 4),
        "near_low": bool(after_peak_low > 0
                         and (base_low - after_peak_low) / after_peak_low * 100.0 <= NEAR_LOW_PCT),
        "near_low_needed_pct": NEAR_LOW_PCT,
        "dist_base_low_pct": round((price / base_low - 1.0) * 100.0, 2) if base_low else None,
        "dist_base_high_pct": round((base_high / price - 1.0) * 100.0, 2) if price else None,
        "gap_from_post_peak_low_pct": round((base_low - after_peak_low) / after_peak_low * 100.0, 2)
        if after_peak_low else None,
        "gap_from_day_low_pct": round((base_low - day_low) / day_low * 100.0, 2) if day_low else None,
    }


def runup_metrics(df: pd.DataFrame, day: pd.DataFrame) -> dict:
    """
    الرجل الأولى V2: تحديد واضح لموجة الصعود السابقة مع منع استخدام معلومات مستقبلية.
    - يستخدم طريقة واضحة: قاع ما قبل القمة (أدنى Low حتى القمة) + متوسط حجم قبل الحركة
    - يحسب dollar volume + الوقت + هل الحركة خلال جلسة أو عدة جلسات
    - لا يختلق قمة/قاع عند نقص البيانات — يصنف كـ incomplete_data
    """
    if day is None or day.empty:
        return {"ok": False, "reason": "no_data", "incomplete": True}
    high_ts = day["High"].astype(float).idxmax()
    day_high = float(day["High"].astype(float).max())
    climb = day.loc[:high_ts]
    if climb.empty:
        return {"ok": False, "reason": "no_data", "incomplete": True}
    low_ts = climb["Low"].astype(float).idxmin()
    launch_low = float(climb["Low"].astype(float).min())
    runup_pct = (day_high / launch_low - 1.0) * 100.0 if launch_low > 0 else 0.0
    leg = day.loc[low_ts:high_ts]
    leg_volume = float(leg["Volume"].astype(float).mean()) if len(leg) else 0.0
    # V2: حساب قيمة التداول بالدولار أثناء الصعود (متوسط السعر × الحجم)
    leg_dollar = float((leg["Close"].astype(float) * leg["Volume"].astype(float)).sum()) if len(leg) else 0.0
    leg_dollar_avg = float((leg["Close"].astype(float) * leg["Volume"].astype(float)).mean()) if len(leg) else 0.0
    prior = df.loc[:low_ts].iloc[:-1].tail(20)
    baseline = float(prior["Volume"].astype(float).mean()) if len(prior) else None
    baseline_dollar = float((prior["Close"].astype(float) * prior["Volume"].astype(float)).mean()) if len(prior) else None
    ratio = leg_volume / baseline if baseline and baseline > 0 else None
    dollar_ratio = leg_dollar_avg / baseline_dollar if baseline_dollar and baseline_dollar > 0 else None
    ok_pct = bool(runup_pct >= RUNUP_MIN_PCT)
    ok_vol = bool(ratio is not None and ratio >= RUNUP_VOLUME_MIN)
    # V2: فحص الحد الأدنى لعدد الشموع والوقت وقيمة التداول
    enough_bars = len(leg) >= RUNUP_MIN_BARS
    enough_time = int((high_ts - low_ts).total_seconds() / 60.0) >= RUNUP_TIME_MIN_MIN if low_ts != high_ts else False
    # dollar volume check: إذا كان leg_dollar < الحد فقد تكون الحركة ضعيفة السيولة
    enough_dollar = leg_dollar >= RUNUP_DOLLAR_VOLUME_MIN if leg_dollar else False
    # تحديد ما إذا كانت الحركة داخل الجلسة أو عبر جلسات
    # حاليًا نستخدم يوم واحد فقط، لكن إن كانت low_ts و high_ts في نفس التاريخ فهي intraday
    try:
        low_date = low_ts.date()
        high_date = high_ts.date()
        intraday = bool(low_date == high_date)
        session_span = "intraday" if intraday else "multi_session"
    except Exception:
        intraday = None
        session_span = "unknown"
    # تحقق البيانات الكافية
    incomplete = False
    if len(prior) < 5:
        # بيانات غير كافية لتحديد خط الأساس بدقة — نصنف كغير مكتمل لكن لا نفترض volume
        incomplete = True
    reason = ("ok" if (ok_pct and ok_vol) else
              "low_runup" if not ok_pct else "weak_runup_volume")
    # تجميع إضافي للعرض والتحليل
    return {
        "ok": bool(ok_pct and ok_vol),
        "reason": reason,
        "incomplete": incomplete,
        "incomplete_reason": "بيانات خط الأساس أقل من 5 شموع قبل القاع" if incomplete else None,
        "launch_low": round(launch_low, 4),
        "launch_low_ts": low_ts.isoformat(),
        "day_high": round(day_high, 4),
        "day_high_ts": high_ts.isoformat(),
        "peak_price": round(day_high, 4),
        "trough_price": round(launch_low, 4),
        "runup_pct": round(runup_pct, 1),
        "runup_needed_pct": RUNUP_MIN_PCT,
        "runup_bars": int(len(leg)),
        "runup_min": int((high_ts - low_ts).total_seconds() / 60.0),
        "runup_avg_volume": int(leg_volume),
        "baseline_avg_volume": int(baseline) if baseline else None,
        "runup_volume_ratio": round(ratio, 2) if ratio is not None else None,
        "runup_volume_needed": RUNUP_VOLUME_MIN,
        "runup_dollar_volume": int(leg_dollar),
        "runup_dollar_avg": int(leg_dollar_avg) if leg_dollar_avg else None,
        "baseline_dollar_avg": int(baseline_dollar) if baseline_dollar else None,
        "dollar_ratio": round(dollar_ratio, 2) if dollar_ratio is not None else None,
        "enough_bars": enough_bars,
        "enough_time": enough_time,
        "enough_dollar": enough_dollar,
        "session_span": session_span,
        "intraday": intraday,
        "time_to_peak_min": int((high_ts - low_ts).total_seconds() / 60.0),
        "note": (f"صعود {runup_pct:.0f}% بحجم {ratio:.1f}×" if ratio is not None
                 else f"صعود {runup_pct:.0f}%"),
        "detail_note": f"من {launch_low:.2f} → {day_high:.2f} ({runup_pct:.0f}%) خلال {int((high_ts - low_ts).total_seconds()/60)} دقيقة، حجم {ratio:.1f}×" if ratio is not None else f"صعود {runup_pct:.0f}%",
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


__all__ = ["detect_base", "base_metrics", "runup_metrics", "session_levels", "levels_payload", "drawdown_metrics"]
def drawdown_metrics(peak_price: float, current_low: float, current_price: float = None) -> dict:
    """
    احتساب Drawdown من القمة الصحيحة للموجة الحالية إلى أدنى سعر بعد القمة.
    Drawdown % = (Peak - Current Low) / Peak * 100
    تُستخدم القمة الصحيحة (قمة الموجة الحالية) وليس قمة يومية غير مرتبطة.
    """
    if not peak_price or peak_price <= 0 or current_low is None:
        return {"drawdown_pct": None, "category": "غير معروف", "peak": peak_price, "low": current_low}
    dd = (peak_price - current_low) / peak_price * 100.0
    # فئات تحليلية قابلة للتعديل
    abs_dd = abs(dd)
    from .config import drop_category
    cat = drop_category(abs_dd)
    return {
        "peak": round(float(peak_price), 4),
        "low": round(float(current_low), 4),
        "drawdown_pct": round(dd, 1),
        "drawdown_abs_pct": round(abs_dd, 1),
        "category": cat,
        "recovery_pct": round((current_price / current_low - 1.0) * 100.0, 1) if current_price and current_low else None,
    }
