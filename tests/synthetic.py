# -*- coding: utf-8 -*-
"""مولّد بيانات 5m اصطناعية للاختبارات (بلا إنترنت)."""
from __future__ import annotations

import numpy as np
import pandas as pd

BARS_PER_DAY = 120
END_DATE = "2026-10-06"


def _quiet_days(rng, start_price, days):
    rows = []
    for day in days[:-1]:
        for k in range(BARS_PER_DAY):
            ts = day.replace(hour=9, minute=30) + pd.Timedelta(minutes=5 * k)
            price = start_price * (1 + rng.normal(0, 0.002))
            rows.append((ts, price, price * 1.003, price * 0.997, price, 20_000))
    return rows


def make(post_low_bars: int = 30, crash_to: float = 0.60, flat_noise: float = 0.004,
         seed: int = 1, start_price: float = 2.0, base_trend: float = 0.02,
         up_volume: int = 70_000, down_volume: int = 25_000, extra_tail=None,
         pad_bars: int = 0, pad_noise: float = 0.0006, end_date: str = END_DATE,
         end_ts=None):
    """
    يبني 4 أيام: 3 هادئة + يوم انهيار صباحي ثم ثبات أفقي قرب القاع.
    `extra_tail` قائمة أسعار إضافية تُضاف بعد الثبات (اختراق أو كسر).
    """
    rng = np.random.default_rng(seed)
    days = pd.bdate_range(end=end_date, periods=4, tz="America/New_York")
    rows = _quiet_days(rng, start_price, days)

    day = days[-1]
    total = 22 + post_low_bars + len(extra_tail or []) + pad_bars
    if end_ts is not None:
        # نُرجِع بداية اليوم للوراء حتى تنتهي كل الرموز عند نفس الشمعة (لا «تقادم» زائفًا)
        ts0 = end_ts - pd.Timedelta(minutes=5 * (total - 1))
    else:
        ts0 = day.replace(hour=4)
    path = [start_price * (1 + 0.5 * i / 12) for i in range(12)]      # قفزة صباحية
    peak = path[-1]
    path += list(np.linspace(peak, peak * crash_to, 10))               # انهيار عمودي
    low = path[-1]
    for i in range(post_low_bars):                                     # ثبات + تجميع
        path.append(low * (1 + base_trend * i / max(1, post_low_bars) + rng.normal(0, flat_noise)))
    volumes = []
    for i, price in enumerate(path):
        high, low_bar = price * 1.004, price * 0.996
        up = i > 0 and price >= path[i - 1]
        volume = 400_000 if 12 <= i < 22 else (up_volume if up else down_volume)
        volumes.append(volume)
        rows.append((ts0 + pd.Timedelta(minutes=5 * i), price, high, low_bar, price, volume))

    if extra_tail:
        base_end = rows[-1][0]
        for j, price in enumerate(extra_tail):
            ts = base_end + pd.Timedelta(minutes=5 * (j + 1))
            high, low_bar = price * 1.006, price * 0.994
            rows.append((ts, price, high, low_bar, price, up_volume * 2 if price >= rows[-1][1] else down_volume))

    if pad_bars > 0:                                  # شموع هادئة لتوحيد آخر شمعة بين الرموز
        last_ts, last_price = rows[-1][0], float(rows[-1][1])
        for k in range(pad_bars):
            ts = last_ts + pd.Timedelta(minutes=5 * (k + 1))
            price = last_price * (1 + rng.normal(0, pad_noise))
            rows.append((ts, price, price * 1.0015, price * 0.9985, price, 18_000))

    frame = pd.DataFrame(rows, columns=["ts", "Open", "High", "Low", "Close", "Volume"]).set_index("ts")
    return frame, frame.index[-1].to_pydatetime()


def make_no_history(post_low_bars: int = 30, **kwargs):
    """يوم واحد فقط (بلا تسخين كافٍ للمؤشرات)."""
    frame, now = make(post_low_bars=post_low_bars, **kwargs)
    last_day = frame.index[-1].date()
    return frame[frame.index.date == last_day], now


def make_breakout(step: float = 0.008, post_low_bars: int = 28, flat_noise: float = 0.004, **kwargs):
    """قاعدة مكتملة ثم 3 شموع انطلاق تكسر قمة الثبات (مع بقاء القاعدة صالحة)."""
    probe, _ = make(post_low_bars=post_low_bars, flat_noise=flat_noise, **kwargs)
    start = float(probe["Close"].iloc[-1])
    tail = [start * (1 + step) ** i for i in range(1, 4)]
    return make(post_low_bars=post_low_bars, flat_noise=flat_noise, extra_tail=tail, **kwargs)


def make_recovered(crash_to: float = 0.60, start_price: float = 2.0, **kwargs):
    """
    إطار ارتد فيه السهم فوق حدّ -30% من قمة اليوم (بوابة الدخول لم تعد محققة) —
    يُستخدم لاختبار مسار «ضعفت الإشارة» و«الإسقاط».
    """
    peak = start_price * 1.5
    base_low = peak * crash_to
    recovered = peak * 0.78                        # أي -22% فقط من القمة
    tail = list(np.linspace(base_low * 1.01, recovered, 4))
    return make(crash_to=crash_to, start_price=start_price, extra_tail=tail, **kwargs)


def universe_stub(tickers=("AAA", "BBB"), float_value=2_500_000, built_on="2026-10-06"):
    return {
        "built_on": built_on, "built_at": "2026-10-06T12:00:00+00:00", "count": len(tickers),
        "rules": {"price": [0.5, 10.0], "max_float": 5_000_000, "min_avg_volume": 100_000},
        "tickers": [{"ticker": t, "price": 1.0, "avg_vol": 500_000, "range_pct": 20.0,
                     "float": float_value, "float_status": "bound",
                     "float_source": "yahoo_outstanding", "reverse_split": False}
                    for t in tickers],
    }


def daily_frame(seed: int = 3, bars: int = 40, price: float = 2.0, volume: int = 400_000):
    """شموع يومية لاختبار بناء الكون."""
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range(end="2026-10-06", periods=bars, tz="America/New_York")
    closes = price * np.cumprod(1 + rng.normal(0, 0.03, bars))
    frame = pd.DataFrame({
        "Open": closes * 0.99, "High": closes * 1.05, "Low": closes * 0.95,
        "Close": closes, "Volume": [volume] * bars,
    }, index=idx)
    return frame
