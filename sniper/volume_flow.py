# -*- coding: utf-8 -*-
"""
تحليل الحجم والتدفق: RVOL، حجم نسبي حسب وقت الجلسة، دوران الفلوت، جفاف الحجم
داخل القاعدة مقابل موجة الهبوط، دلتا الحجم، وموقع الإغلاق (CLV).
كلها مشتقة من الشموع نفسها — بلا أي مصدر بيانات إضافي.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import BASE_VOLUME_LOOK, FLOW_LOOK
from .indicators import clv, volume_delta

BIG_PRINT_MULT = 3.0     # شمعة حجمها ≥ 3× الوسيط = بصمة كبيرة


def rvol_last(df: pd.DataFrame, window: int = 20) -> float | None:
    vol = df["Volume"].astype(float)
    if len(vol) < 2:
        return None
    avg = float(vol.iloc[-1 - window:-1].mean()) if len(vol) > window else float(vol.iloc[:-1].mean())
    return round(float(vol.iloc[-1]) / avg, 2) if avg > 0 else None


def relative_volume_by_time(df: pd.DataFrame, day: pd.DataFrame) -> dict | None:
    """
    حجم اليوم حتى اللحظة ÷ متوسط حجم الأيام السابقة حتى نفس اللحظة.
    أدق من مقارنة حجم جزئي بيوم كامل.
    """
    if df is None or df.empty or day is None or day.empty:
        return None
    today = day.index[-1].date()
    cut = day.index[-1].time()
    day_vol = float(day["Volume"].astype(float).sum())
    prior_days = sorted({d for d in df.index.date if d < today})
    totals = []
    for d in prior_days[-5:]:
        rows = df[df.index.date == d]
        same = rows[[t <= cut for t in rows.index.time]]
        if len(same):
            totals.append(float(same["Volume"].astype(float).sum()))
    if not totals:
        return None
    expected = float(np.mean(totals))
    return {
        "session_volume": int(day_vol),
        "expected_volume": int(expected),
        "relative_volume": round(day_vol / expected, 2) if expected > 0 else None,
        "compared_days": len(totals),
    }


def float_turnover(day: pd.DataFrame, float_shares) -> dict | None:
    """كم نسبة الفلوت تداولت اليوم — مقياس وقود السهم منخفض الفلوت."""
    if not float_shares or float(float_shares) <= 0:
        return None
    vol = float(day["Volume"].astype(float).sum())
    return {
        "float": int(float_shares),
        "turnover_pct": round(vol / float(float_shares) * 100.0, 2),
        "float_rotations": round(vol / float(float_shares), 2),
    }


def dry_up(df: pd.DataFrame, day: pd.DataFrame, base_window: pd.DataFrame | None) -> dict | None:
    """حجم القاعدة ÷ حجم موجة الهبوط — الجفاف يعني امتصاصًا لا توزيعًا."""
    if base_window is None or base_window.empty or day is None or day.empty:
        return None
    high_ts = day["High"].astype(float).idxmax()
    start = base_window.index[0]
    drop_rows = day.loc[high_ts:start].iloc[:-1] if start > high_ts else day.loc[high_ts:start]
    base_vol = float(base_window["Volume"].astype(float).mean())
    drop_vol = float(drop_rows["Volume"].astype(float).mean()) if len(drop_rows) else None
    look = df.tail(BASE_VOLUME_LOOK).iloc[:-len(base_window)] if len(df) > len(base_window) else df.iloc[:0]
    pre_vol = float(look["Volume"].astype(float).mean()) if len(look) else None
    ratio = base_vol / drop_vol if drop_vol else None
    return {
        "base_avg_volume": int(base_vol),
        "drop_avg_volume": int(drop_vol) if drop_vol else None,
        "pre_drop_avg_volume": int(pre_vol) if pre_vol else None,
        "base_vs_drop_ratio": round(ratio, 2) if ratio else None,
        "base_vs_predrop_ratio": round(base_vol / pre_vol, 2) if pre_vol else None,
        "dried_up": bool(ratio is not None and ratio <= 0.85),
    }


def flow_metrics(df: pd.DataFrame, base_window: pd.DataFrame | None, look: int = FLOW_LOOK) -> dict:
    """دلتا الحجم، CLV، نسبة الشموع الصاعدة، والبصمات الكبيرة داخل القاعدة."""
    tail = df.tail(look)
    delta = volume_delta(tail, look)
    clv_vals = clv(tail).fillna(0.0)
    closes = df["Close"].astype(float)
    ups = int((closes.diff().tail(look) > 0).sum())
    src = base_window if base_window is not None and len(base_window) else tail
    vol = src["Volume"].astype(float)
    median = float(vol.median()) if len(vol) else 0.0
    big = int((vol >= median * BIG_PRINT_MULT).sum()) if median > 0 else 0
    up_bars = int((src["Close"].astype(float).diff() > 0).sum())
    down_bars = int((src["Close"].astype(float).diff() < 0).sum())
    up_vol = float(src.loc[src["Close"].astype(float).diff() > 0, "Volume"].astype(float).sum())
    down_vol = float(src.loc[src["Close"].astype(float).diff() < 0, "Volume"].astype(float).sum())
    denom = up_vol + down_vol
    return {
        "volume_delta": int(delta),
        "clv_mean": round(float(clv_vals.mean()), 3) if len(clv_vals) else None,
        "clv_last": round(float(clv_vals.iloc[-1]), 3) if len(clv_vals) else None,
        "up_bars": up_bars, "down_bars": down_bars,
        "up_bar_ratio": round(ups / max(1, len(tail) - 1), 2),
        "big_prints": big,
        "up_volume": int(up_vol), "down_volume": int(down_vol),
        "volume_balance": round((up_vol - down_vol) / denom, 2) if denom > 0 else None,
        "net_buying": bool(delta > 0 and float(clv_vals.mean()) > 0),
    }


def volume_payload(df: pd.DataFrame, day: pd.DataFrame, base_window: pd.DataFrame | None,
                   float_shares=None) -> dict:
    """حزمة الحجم الكاملة للبطاقة."""
    vol = df["Volume"].astype(float)
    out = {
        "volume_last": int(vol.iloc[-1]) if len(vol) else 0,
        "volume_avg_20": int(vol.tail(20).mean()) if len(vol) else 0,
        "rvol": rvol_last(df),
        "day_volume": int(day["Volume"].astype(float).sum()) if day is not None and len(day) else 0,
    }
    out.update(flow_metrics(df, base_window))
    out["relative"] = relative_volume_by_time(df, day)
    out["float_turnover"] = float_turnover(day, float_shares)
    out["dry_up"] = dry_up(df, day, base_window)
    return out


__all__ = ["rvol_last", "relative_volume_by_time", "float_turnover", "dry_up",
           "flow_metrics", "volume_payload", "BIG_PRINT_MULT"]
