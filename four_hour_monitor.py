# -*- coding: utf-8 -*-
"""
4-Hour Pulse Monitor - Reverse Split Radar
============================================

سكربت مستقل تمامًا عن strategy_scanner.py و history_tracker.py.
لا يعيد حساب Score/Core/Rating إطلاقًا (هذه تبقى حصريًا من التحليل
اليومي الكامل بعد إغلاق السوق - المرجع الوحيد المعتمد للقرار).

مهمة هذا السكربت فقط: مراقبة خفيفة أثناء جلسة التداول (كل ~4 ساعات)
لأسهم الرادار الحالية (من reverse_split_dashboard.json)، لرصد:

- هل السعر دخل/اقترب من منطقة نصف الشمعة (half zone) المكتشفة أصلًا
  في التحليل اليومي؟
- هل هناك ارتفاع غير عادي في حجم التداول خلال آخر 4 ساعات؟
- RSI على فريم 4 ساعات (مؤشر سريع إضافي، ليس بديلاً عن RSI اليومي).

يشمل الجلب الآن بيانات ما قبل الافتتاح (Pre-market، prepost=True)،
لأن حركات انفجارية مهمة (مثل نموذج Hudson Capital) قد تبدأ فعليًا
قبل ساعات التداول الرسمية.

النتيجة تُحفظ في four_hour_pulse.json وتُعرض في الداشبورد كـ"نبض"
إضافي بجانب كل سهم - دون التأثير على التقييم اليومي الأساسي.
"""

import json
from datetime import datetime

import numpy as np
import pandas as pd
import yfinance as yf

RADAR_RESULTS_FILE = "reverse_split_dashboard.json"
PULSE_FILE = "four_hour_pulse.json"

VOLUME_SPIKE_RATIO = 2.0


def safe_float(x):
    try:
        if x is None:
            return None
        x = float(x)
        return None if x != x else x
    except Exception:
        return None


def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save_json(path, payload):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def load_radar_results():
    data = load_json(RADAR_RESULTS_FILE, {})
    return data.get("results", []) if isinstance(data, dict) else []


def calculate_rsi(close, period=14):
    delta = close.diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)

    return 100 - (100 / (1 + rs))


def get_4h_candles(ticker):
    """
    yfinance لا يدعم interval='4h' مباشرة، لذلك نجلب بيانات ساعة
    (60m) ونجمّعها (resample) إلى شموع 4 ساعات بأنفسنا.
    """

    try:

        stock = yf.Ticker(ticker)

        df = stock.history(
            period="30d",
            interval="60m",
            auto_adjust=False,
            prepost=True,
        )

        if df is None or df.empty:
            return None

        df = df.dropna(
            subset=["Open", "High", "Low", "Close", "Volume"]
        )

        if len(df) < 8:
            return None

        four_hour = df.resample("4h").agg({
            "Open": "first",
            "High": "max",
            "Low": "min",
            "Close": "last",
            "Volume": "sum",
        }).dropna()

        if len(four_hour) < 5:
            return None

        return four_hour

    except Exception as e:

        print(f"ERROR fetching 4h data for {ticker}: {e}")
        return None


def analyze_pulse(ticker, zone_low, zone_high):

    df = get_4h_candles(ticker)

    if df is None:
        return None

    df["RSI"] = calculate_rsi(df["Close"])

    latest = df.iloc[-1]

    price = safe_float(latest["Close"])
    volume = safe_float(latest["Volume"])
    rsi_4h = safe_float(latest["RSI"])

    volume_avg = safe_float(
        df["Volume"].iloc[-6:-1].mean()
    ) if len(df) >= 6 else None

    volume_ratio = None

    if volume is not None and volume_avg is not None and volume_avg > 0:
        volume_ratio = volume / volume_avg

    if price is None:
        return None

    in_zone = (
        zone_low is not None
        and zone_high is not None
        and zone_low <= price <= zone_high
    )

    volume_spike = (
        volume_ratio is not None
        and volume_ratio >= VOLUME_SPIKE_RATIO
    )

    if in_zone and volume_spike:

        status = "ZONE_WITH_VOLUME"

        note = (
            "السعر داخل منطقة نصف الشمعة مع ارتفاع ملحوظ في الحجم "
            "خلال آخر 4 ساعات."
        )

    elif in_zone:

        status = "IN_ZONE"

        note = "السعر حاليًا داخل منطقة نصف الشمعة المكتشفة."

    elif volume_spike:

        status = "VOLUME_SPIKE"

        note = (
            "ارتفاع ملحوظ في الحجم خلال آخر 4 ساعات (خارج منطقة "
            "نصف الشمعة)."
        )

    else:

        status = "NORMAL"

        note = "لا تغييرات ملحوظة خلال آخر 4 ساعات."

    return {

        "ticker": ticker,

        "checked_at": datetime.now().isoformat(),

        "price": price,
        "rsi_4h": round(rsi_4h, 1) if rsi_4h is not None else None,
        "volume_ratio_4h": (
            round(volume_ratio, 2)
            if volume_ratio is not None
            else None
        ),

        "in_zone": in_zone,
        "volume_spike": volume_spike,

        "status": status,
        "note": note,
    }


def main():

    print("=" * 60)
    print("4-HOUR PULSE MONITOR")
    print("=" * 60)

    radar_results = load_radar_results()

    print(f"عدد أسهم الرادار الحالية: {len(radar_results)}")

    pulses = {}

    for r in radar_results:

        ticker = r.get("ticker")

        if not ticker:
            continue

        half = r.get("half") or {}

        zone_low = safe_float(half.get("zone_low"))
        zone_high = safe_float(half.get("zone_high"))

        print(f"فحص نبض: {ticker} ...")

        result = analyze_pulse(ticker, zone_low, zone_high)

        if result:

            pulses[ticker] = result

            print(f"  -> {result['status']}: {result['note']}")

        else:

            print("  -> تعذر جلب بيانات 4 ساعات.")

    payload = {

        "updated_at":
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),

        "pulses": pulses,
    }

    save_json(PULSE_FILE, payload)

    print(f"\nتم حفظ: {PULSE_FILE}")

    print("=" * 60)
    print("انتهت مراقبة النبض.")
    print("=" * 60)


if __name__ == "__main__":
    main()
