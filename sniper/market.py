# -*- coding: utf-8 -*-
"""الوصول إلى بيانات السوق (Yahoo Finance) وساعة الجلسة الأمريكية."""
from __future__ import annotations

import time
from datetime import datetime, time as dtime, timedelta, timezone

import pandas as pd

from . import config as C

OPEN, CLOSE = dtime(9, 30), dtime(16, 0)
PRE_OPEN = dtime(4, 0)
SCAN_INTERVAL_MIN = 15


def download(tickers, chunk: int = C.CHUNK, retries: int = C.DOWNLOAD_RETRIES,
             period: str = "5d", interval: str = "5m"):
    """
    تحميل دفعي (100 رمز/طلب) — أخف بكثير على Yahoo من طلب لكل سهم.
    يعيد {ticker: DataFrame} مع إزالة الصفوف الناقصة.
    """
    import yfinance as yf
    out = {}
    tickers = list(tickers)
    for i in range(0, len(tickers), chunk):
        group = tickers[i:i + chunk]
        raw = None
        for _ in range(max(1, retries)):
            try:
                raw = yf.download(group, period=period, interval=interval, prepost=True,
                                  group_by="ticker", auto_adjust=False, threads=True,
                                  progress=False)
            except Exception as exc:                      # noqa: BLE001 — الشبكة غير مضمونة
                print("download error", type(exc).__name__, str(exc)[:120])
                raw = None
            if raw is not None and not raw.empty:
                break
            time.sleep(C.DOWNLOAD_RETRY_SLEEP_S)
        if raw is None or raw.empty:
            continue
        levels = raw.columns.get_level_values(0) if isinstance(raw.columns, pd.MultiIndex) else []
        for ticker in group:
            frame = raw[ticker] if len(levels) and ticker in levels else (
                raw if len(group) == 1 else None)
            if frame is None:
                continue
            frame = frame.dropna(subset=["Open", "High", "Low", "Close"])
            if len(frame):
                if isinstance(frame.columns, pd.MultiIndex):
                    frame.columns = frame.columns.get_level_values(0)
                out[ticker] = frame
    return out


def download_daily(tickers, chunk: int = C.CHUNK, period: str = "3mo", retries: int = 2):
    """شموع يومية لبناء الكون (متوسط حجم، نطاق، سعر)."""
    return download(tickers, chunk=chunk, retries=retries, period=period, interval="1d")


def market_clock(now: datetime | None = None) -> dict:
    """حالة السوق الآن بتوقيت نيويورك + موعد المسح القادم ونسبة إنجاز الجلسة."""
    now = (now or datetime.now(timezone.utc)).astimezone(C.MARKET_TZ)
    clock = now.time()
    weekday = now.weekday()
    if weekday >= 5:
        phase, label = "weekend", "عطلة نهاية الأسبوع"
    elif clock < PRE_OPEN:
        phase, label = "closed", "السوق مغلق"
    elif clock < OPEN:
        phase, label = "premarket", "ما قبل الافتتاح"
    elif clock < CLOSE:
        phase, label = "regular", "الجلسة الرسمية"
    else:
        phase, label = "after_hours", "ما بعد الإغلاق"

    minutes = now.hour * 60 + now.minute
    next_step = ((minutes // SCAN_INTERVAL_MIN) + 1) * SCAN_INTERVAL_MIN
    next_scan = (now.replace(hour=0, minute=0, second=0, microsecond=0)
                 + timedelta(minutes=next_step))
    if next_scan.time() >= dtime(22, 0):
        next_scan = next_scan + timedelta(days=1)
    progress = None
    if phase == "regular":
        total = (CLOSE.hour * 60 + CLOSE.minute) - (OPEN.hour * 60 + OPEN.minute)
        progress = round((minutes - (OPEN.hour * 60 + OPEN.minute)) / total * 100.0, 1)
    return {
        "et_time": now.strftime("%H:%M:%S"),
        "et_date": now.date().isoformat(),
        "phase": phase, "phase_label": label,
        "is_trading_day": weekday < 5,
        "minutes_to_close": max(0, (CLOSE.hour * 60 + CLOSE.minute) - minutes) if phase == "regular" else None,
        "session_progress_pct": progress,
        "next_scan_at": next_scan.isoformat(),
        "seconds_to_next_scan": int((next_scan - now).total_seconds()),
    }


__all__ = ["download", "download_daily", "market_clock", "SCAN_INTERVAL_MIN"]
