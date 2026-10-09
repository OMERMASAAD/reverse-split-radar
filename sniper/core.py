# -*- coding: utf-8 -*-
"""
قلب النظام: تقييم كل سهم ثم دمج الحالة مع المسح السابق (شطب آلي + متابعة نتائج).

بوابة الدخول والشروط الأربعة **مطابقة** لقنص الذعر الأصلي:
هبوط ≤ -30% من قمة اليوم · ثبات أفقي (تذبذب ≤ 5%) ≥ 60 دقيقة قرب قاع اليوم ·
RSI يخرج من التشبع البيعي · OBV صاعد أو انحراف إيجابي · MACD تقاطع/هيستوجرام أخضر.
وما فوق ذلك طبقات تحليل إضافية لا تغيّر تعريف `complete`.
"""
from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pandas as pd

from . import config as C
from .indicators import (ema, indicators_frame, macd, obv, resample_bars, rsi,
                         anchored_vwap_value)
from .levels import base_metrics, detect_base, runup_metrics, session_levels
from .risk import risk_plan
from .scoring import combine, confirmations, core_score, grade_payload, missing_conditions
from .volume_flow import volume_payload


def to_et(df: pd.DataFrame) -> pd.DataFrame:
    """تحويل فهرس الشموع إلى توقيت نيويورك (يتعامل مع فهرس naive أو UTC)."""
    out = df.copy()
    idx = out.index
    out.index = idx.tz_localize("UTC").tz_convert(C.MARKET_TZ) if idx.tz is None else idx.tz_convert(C.MARKET_TZ)
    return out


def _round(value, digits=4):
    if value is None:
        return None
    try:
        val = float(value)
    except (TypeError, ValueError):
        return None
    return round(val, digits) if np.isfinite(val) else None


def mtf_confirmation(df: pd.DataFrame, rule: str = C.MTF_RESAMPLE) -> dict:
    """طبقة تأكيد على الفريم الأعلى: قاع أعلى من قاع + إغلاق فوق EMA9."""
    higher = resample_bars(df, rule)
    if higher is None or len(higher) < C.MTF_HIGHER_LOW_LOOK + 1:
        return {"aligned": False, "note": "شموع %s غير كافية" % rule}
    tail = higher.tail(C.MTF_HIGHER_LOW_LOOK)
    lows = tail["Low"].astype(float).to_numpy()
    split = len(lows) // 2
    first_min, second_min = float(lows[:split].min()), float(lows[split:].min())
    higher_low = bool(second_min > first_min)
    e9 = ema(higher["Close"].astype(float), C.EMA_FAST)
    close = float(higher["Close"].astype(float).iloc[-1])
    above_ema = bool(np.isfinite(e9.iloc[-1]) and close > float(e9.iloc[-1]))
    r = rsi(higher["Close"].astype(float), C.RSI_PERIOD)
    aligned = bool(higher_low and above_ema)
    return {
        "aligned": aligned,
        "higher_low": higher_low,
        "above_ema": above_ema,
        "rsi": _round(r.iloc[-1], 1),
        "close": _round(close),
        "ema_fast": _round(e9.iloc[-1]),
        "bars": int(len(higher)),
        "note": ("قاع أعلى وإغلاق فوق EMA9 على %s" % rule) if aligned
        else ("لا تأكيد على %s" % rule),
    }


def chart_payload(df: pd.DataFrame, limit: int = C.CHART_BARS) -> list[dict]:
    """شموع + قيم المؤشرات جاهزة للرسم مباشرة في الداشبورد (بلا إعادة حساب في JS)."""
    enriched = indicators_frame(df)
    rows = []
    for ts, row in enriched.tail(limit).iterrows():
        rows.append({
            "time": ts.isoformat(),
            "open": _round(row["Open"]), "high": _round(row["High"]),
            "low": _round(row["Low"]), "close": _round(row["Close"]),
            "volume": int(row["Volume"]) if np.isfinite(row["Volume"]) else 0,
            "rsi": _round(row["rsi"], 1),
            "ema_fast": _round(row["ema_fast"]),
            "ema_slow": _round(row["ema_slow"]),
            "macd_line": _round(row["macd"], 5),
            "macd_signal": _round(row["macd_signal"], 5),
            "macd_hist": _round(row["macd_hist"], 5),
            "obv": _round(row["obv"], 1),
            "vwap": _round(row["vwap"]),
        })
    return rows


def evaluate(df, now=None, meta=None):
    """
    يعيد (dict | None, reason). أي سهم هبط ≤ -30% من قمة اليوم يظهر في الرادار مع
    حالة كل شرط؛ و`complete`=True فقط عند تحقق الشروط الأربعة معًا (كما في الأصل).
    """
    meta = meta or {}
    if df is None or len(df) < C.MIN_BARS:
        return None, "no_data"
    df = to_et(df)
    now = (now or datetime.now(timezone.utc)).astimezone(C.MARKET_TZ)
    last_ts = df.index[-1]
    if (now - last_ts).total_seconds() / 60.0 > C.STALE_MIN:
        return None, "stale"
    day = df[df.index.date == last_ts.date()]
    if len(day) < C.MIN_DAY_BARS:
        return None, "no_data"

    price = float(day["Close"].iloc[-1])
    day_high = float(day["High"].max())
    day_low = float(day["Low"].min())
    if day_high <= 0:
        return None, "no_data"

    # ── الرجل الأولى: لا نرصد سهمًا لم يصعد أولًا بحجم عالي
    runup = runup_metrics(df, day)
    if not runup["ok"]:
        return None, runup["reason"]              # no_runup | weak_runup_volume

    drop = (price / day_high - 1.0) * 100.0
    if drop > C.DROP_MAX_PCT:                     # لم يهبط بما يكفي
        return None, "no_drop"
    if drop < C.DROP_MIN_PCT:                     # انهيار أعمق من النموذج المستهدف
        return None, "too_deep"
    drop_in_band = bool(C.DROP_MIN_PCT <= drop <= C.DROP_MAX_PCT)

    # ---------------- الثبات الأفقي (نفس الخوارزمية)
    win, start_ts = detect_base(day)
    base = base_metrics(win, day, start_ts, last_ts) if win is not None and len(win) else {}
    base_low = float(base.get("base_low") or day_low)
    base_ok = bool(base.get("hold_min", 0) >= C.CONS_MIN_MIN and base.get("near_low"))

    # ---------------- المؤشرات على كامل الـ 5 أيام (تسخين كافٍ)
    close = df["Close"].astype(float)
    vol = df["Volume"].astype(float)
    r = rsi(close, C.RSI_PERIOD)
    rsi_now = rsi_min = rsi_peak = None
    rsi_ok = False
    rsi_mode = "—"
    oversold_touch = weakness_pullback = False
    if r.dropna().shape[0] >= C.RSI_LOOK:
        rsi_now, rsi_min = float(r.iloc[-1]), float(r.iloc[-C.RSI_LOOK:].min())
        day_rsi = r[r.index.date == last_ts.date()]
        rsi_peak = float(day_rsi.max()) if day_rsi.dropna().shape[0] else rsi_now
        oversold_touch = bool(rsi_min <= C.RSI_OVERSOLD)
        weakness_pullback = bool((rsi_peak - rsi_min) >= C.RSI_PULLBACK_MIN)
        recovering = bool(rsi_now >= C.RSI_EXIT
                          and (rsi_now - rsi_min) >= C.RSI_RECOVERY_MIN
                          and rsi_now <= C.RSI_STRENGTH_MAX)
        rsi_ok = bool((oversold_touch or weakness_pullback) and recovering)
        rsi_mode = ("تشبّع بيعي ثم تحسّن" if oversold_touch else
                    "تراجع من قمة اليوم ثم تحسّن" if weakness_pullback else
                    "يتحسن" if recovering else "لم يخرج من الضعف بعد")

    o = obv(close, vol)
    lows = df["Low"].astype(float)
    obv_rising = bool(o.iloc[-1] > o.iloc[-C.OBV_LOOK])
    obv_div = bool(lows.iloc[-C.OBV_LOOK:].min() <= lows.iloc[-2 * C.OBV_LOOK:-C.OBV_LOOK].min()
                   and o.iloc[-C.OBV_LOOK:].min() > o.iloc[-2 * C.OBV_LOOK:-C.OBV_LOOK].min())
    obv_ok = bool(obv_rising or obv_div)

    ml, ms, mh = macd(close)
    cross = bool(((ml.shift(1) <= ms.shift(1)) & (ml > ms)).iloc[-C.MACD_CROSS_LOOK:].any())
    macd_ok = bool(cross or float(mh.iloc[-1]) > 0)

    checks = {"base": base_ok, "rsi": rsi_ok, "obv": obv_ok, "macd": macd_ok}
    score, score_label = core_score(checks, bool(base.get("near_low")))

    # ---------------- الطبقات الإضافية
    atr_series = indicators_frame(df)["atr"]
    atr_value = float(atr_series.iloc[-1]) if np.isfinite(atr_series.iloc[-1]) else None
    volume = volume_payload(df, day, win, meta.get("float"))
    levels = session_levels(df, day)
    levels["base"] = base
    base_for_confirm = dict(base)
    base_for_confirm["_dry_up"] = volume.get("dry_up") or {}
    mtf = mtf_confirmation(df)
    vwap_anchor = int(df.index.get_loc(start_ts)) if start_ts in df.index else None
    vwap_value = anchored_vwap_value(day if vwap_anchor is None else df, vwap_anchor)
    risk = risk_plan(price, base_low, base.get("base_high"), atr_value, vwap_value)
    confirm_checks, confirm_details = confirmations(base_for_confirm, price, vwap_value, mtf,
                                                    volume, risk)
    grades = grade_payload(score, confirm_checks)

    volume_last = float(vol.iloc[-1])
    volume_avg = float(vol.tail(20).mean())
    rvol = volume_last / volume_avg if volume_avg > 0 else None
    turnover = (volume.get("float_turnover") or {}).get("turnover_pct")
    relative = volume.get("relative") or {}

    result = {
        # --- حقول الأصل (ثابتة الاسم والمعنى)
        "price": _round(price), "day_high": _round(day_high), "day_low": _round(day_low),
        "drop_pct": round(drop, 1), "hold_min": int(base.get("hold_min") or 0),
        "hold_needed": C.CONS_MIN_MIN, "base_low": _round(base_low),
        "near_low": bool(base.get("near_low")),
        "dist_from_low_pct": round((price / float(base["post_peak_low"]) - 1.0) * 100.0, 1)
        if base.get("post_peak_low") else None,
        "dist_from_day_low_pct": round((price / day_low - 1.0) * 100.0, 1) if day_low else None,
        "target": _round(price * (1.0 + C.TARGET_PCT / 100.0)), "target_pct": C.TARGET_PCT,
        "rsi": _round(rsi_now, 1), "rsi_min": _round(rsi_min, 1),
        "rsi_peak": _round(rsi_peak, 1),
        "rsi_pullback": _round(rsi_peak - rsi_min, 1) if rsi_peak is not None and rsi_min is not None else None,
        "rsi_oversold_touch": oversold_touch, "rsi_weakness_pullback": weakness_pullback,
        "rsi_mode": rsi_mode,
        "obv": "صاعد" if obv_rising else ("انحراف إيجابي" if obv_div else "ضعيف"),
        "macd": "تقاطع" if cross else ("هيستوجرام أخضر" if macd_ok else "سلبي"),
        "checks": checks, "complete": all(checks.values()),
        "strength_score": score, "strength_label": score_label,
        "volume_last": int(volume_last), "volume_avg": int(volume_avg),
        "rvol": _round(rvol, 2), "dollar_volume": round(price * volume_last, 2),
        "last_bar": last_ts.isoformat(),
        # --- التطويرات
        "score": grades["score"], "grade": grades["grade"],
        "confirm_score": grades["confirm_score"],
        "confirmations": confirm_checks, "confirmation_details": confirm_details,
        "missing_conditions": missing_conditions(checks, confirm_checks),
        "state": C.STATE_READY if all(checks.values()) else (
            C.STATE_BUILDING if base_ok else C.STATE_NEW),
        "risk": risk,
        "levels": {key: value for key, value in levels.items() if key != "_base_window"},
        "volume": volume,
        "mtf": mtf,
        "vwap": _round(vwap_value),
        "atr": _round(atr_value),
        "float": meta.get("float"), "float_status": meta.get("float_status"),
        "float_source": meta.get("float_source"),
        "float_turnover_pct": turnover,
        "relative_volume": relative.get("relative_volume"),
        "reverse_split": bool(meta.get("reverse_split")),
        "company": meta.get("company"),
        "chart": chart_payload(df),
        "indicators_now": {
            "rsi": _round(rsi_now, 1),
            "ema_fast": _round(ema(close, C.EMA_FAST).iloc[-1]),
            "ema_slow": _round(ema(close, C.EMA_SLOW).iloc[-1]),
            "macd_line": _round(ml.iloc[-1], 5), "macd_signal": _round(ms.iloc[-1], 5),
            "macd_hist": _round(mh.iloc[-1], 5),
            "obv": _round(o.iloc[-1], 1), "obv_slope": _round(float(o.iloc[-1] - o.iloc[-C.OBV_LOOK]), 1),
            "vwap": _round(vwap_value), "atr": _round(atr_value),
            "atr_pct": _round(float(atr_value) / price * 100.0, 2) if atr_value and price else None,
        },
        "combined_score": combine(score, grades["confirm_score"]),
        "runup": runup,
        "drop_in_band": drop_in_band,
        "drop_band": [C.DROP_MIN_PCT, C.DROP_MAX_PCT],
        "target_2": risk.get("target_2"),
        "vwap_is_ceiling": risk.get("vwap_is_ceiling"),
        "entry_modes": risk.get("entry_modes") or [],
    }
    return result, "ok"


__all__ = ["evaluate", "to_et", "mtf_confirmation", "chart_payload"]
