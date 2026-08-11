import yfinance as yf
import pandas as pd
import numpy as np
import json
import os
from datetime import datetime

# ============================================================
# TRIGGER SCANNER - FINAL
# يراقب المرشحين ويبحث عن تأكيد دخول على فريم 5 دقائق
# ============================================================

WATCHLIST_FILE = "trigger_watchlist.json"

# الأسهم الحالية من آخر نتيجة عندك
DEFAULT_WATCHLIST = [
    "GIPR", "PWCM", "POM", "MNDR", "RBNE",
    "EDBL", "VIVK", "SRXH", "YYGH", "GDC",
    "LABT", "PSQH", "NUWE", "HCWB", "MSS"
]

# ============================================================
# الإعدادات
# ============================================================

INTERVAL = "5m"
PERIOD = "5d"

MIN_VOLUME_RATIO = 1.50
MIN_RSI = 35
MAX_RSI = 70

SUPPORT_TOLERANCE = 0.03
BREAKOUT_LOOKBACK = 3

# ============================================================
# أدوات
# ============================================================

def safe_float(x):
    try:
        x = float(x)
        if np.isnan(x):
            return None
        return x
    except:
        return None


def fmt_price(x):
    x = safe_float(x)
    return "N/A" if x is None else f"${x:.4f}"


def fmt_num(x):
    x = safe_float(x)
    return "N/A" if x is None else f"{x:,.0f}"


def rsi(series, period=14):
    delta = series.diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(
        alpha=1 / period,
        adjust=False
    ).mean()

    avg_loss = loss.ewm(
        alpha=1 / period,
        adjust=False
    ).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)

    return 100 - (100 / (1 + rs))


# ============================================================
# تحميل قائمة المتابعة
# ============================================================

def load_watchlist():

    if os.path.exists(WATCHLIST_FILE):

        try:
            with open(
                WATCHLIST_FILE,
                "r",
                encoding="utf-8"
            ) as f:

                data = json.load(f)

                if isinstance(data, list):

                    result = []

                    for item in data:

                        if isinstance(item, dict):
                            symbol = item.get("symbol")
                        else:
                            symbol = item

                        if symbol:
                            result.append(
                                str(symbol).upper()
                            )

                    if result:
                        return list(dict.fromkeys(result))

        except Exception:
            pass

    return DEFAULT_WATCHLIST


# ============================================================
# تحليل سهم
# ============================================================

def analyze(ticker):

    try:

        stock = yf.Ticker(ticker)

        df = stock.history(
            period=PERIOD,
            interval=INTERVAL,
            auto_adjust=False,
            prepost=False
        )

        if df is None or df.empty:
            return None

        df = df.dropna(
            subset=[
                "Open",
                "High",
                "Low",
                "Close",
                "Volume"
            ]
        )

        if len(df) < 30:
            return None

        df["RSI"] = rsi(df["Close"])

        # ----------------------------------------------------
        # آخر شمعة مكتملة
        # ----------------------------------------------------

        last = df.iloc[-1]
        prev = df.iloc[-2]

        price = safe_float(last["Close"])
        open_price = safe_float(last["Open"])
        high = safe_float(last["High"])
        low = safe_float(last["Low"])
        volume = safe_float(last["Volume"])

        prev_high = safe_float(prev["High"])

        current_rsi = safe_float(last["RSI"])
        previous_rsi = safe_float(prev["RSI"])

        # ----------------------------------------------------
        # Volume
        # ----------------------------------------------------

        volume_avg = safe_float(
            df["Volume"].iloc[-21:-1].mean()
        )

        volume_ratio = None

        if (
            volume is not None
            and volume_avg is not None
            and volume_avg > 0
        ):

            volume_ratio = (
                volume / volume_avg
            )

        volume_confirmed = (
            volume_ratio is not None
            and volume_ratio >= MIN_VOLUME_RATIO
        )

        # ----------------------------------------------------
        # الدعم - آخر 12 شمعة
        # ----------------------------------------------------

        support_window = df.iloc[-12:]

        support = safe_float(
            support_window["Low"].min()
        )

        support_distance = None

        if (
            support is not None
            and support > 0
            and price is not None
        ):

            support_distance = (
                (price - support)
                / support
            ) * 100

        near_support = (
            support_distance is not None
            and -3 <= support_distance <= 15
        )

        # ----------------------------------------------------
        # اختبارات الدعم
        # ----------------------------------------------------

        support_tests = 0

        if support is not None:

            tolerance = (
                support
                * SUPPORT_TOLERANCE
            )

            for x in support_window["Low"]:

                if abs(float(x) - support) <= tolerance:
                    support_tests += 1

        support_confirmed = (
            support_tests >= 2
        )

        # ----------------------------------------------------
        # Breakout
        # ----------------------------------------------------

        previous_high = safe_float(
            df["High"]
            .iloc[
                -(BREAKOUT_LOOKBACK + 1):-1
            ].max()
        )

        breakout = (
            price is not None
            and previous_high is not None
            and price > previous_high
        )

        # ----------------------------------------------------
        # شمعة صاعدة
        # ----------------------------------------------------

        green_candle = (
            price is not None
            and open_price is not None
            and price > open_price
        )

        candle_strength = 0

        if (
            green_candle
            and high is not None
            and low is not None
            and high > low
        ):

            candle_strength = (
                (price - open_price)
                / (high - low)
            )

        strong_candle = (
            candle_strength >= 0.50
        )

        # ----------------------------------------------------
        # RSI
        # ----------------------------------------------------

        rsi_improving = (
            current_rsi is not None
            and previous_rsi is not None
            and current_rsi > previous_rsi
        )

        rsi_ok = (
            current_rsi is not None
            and MIN_RSI <= current_rsi <= MAX_RSI
        )

        # ----------------------------------------------------
        # Higher Low
        # ----------------------------------------------------

        higher_low = False

        if len(df) >= 6:

            recent_low = safe_float(
                df["Low"].iloc[-3:].min()
            )

            previous_low = safe_float(
                df["Low"].iloc[-6:-3].min()
            )

            if (
                recent_low is not None
                and previous_low is not None
                and recent_low > previous_low
            ):
                higher_low = True

        # ====================================================
        # SCORE
        # ====================================================

        score = 0
        signals = []
        warnings = []

        if support_confirmed:
            score += 2
            signals.append(
                f"دعم مؤكد ({support_tests} اختبارات)"
            )
        else:
            warnings.append(
                f"الدعم غير مؤكد ({support_tests} اختبار)"
            )

        if near_support:
            score += 1
            signals.append(
                f"السعر قريب من الدعم {fmt_price(support)}"
            )

        if higher_low:
            score += 2
            signals.append(
                "Higher Low"
            )

        if green_candle:
            score += 1
            signals.append(
                "شمعة خضراء"
            )

        if strong_candle:
            score += 1
            signals.append(
                "شمعة صعود قوية"
            )

        if breakout:
            score += 3
            signals.append(
                "BREAKOUT"
            )

        if volume_confirmed:
            score += 3
            signals.append(
                f"Volume تأكيدي {volume_ratio:.2f}x"
            )
        else:
            if volume_ratio is not None:
                warnings.append(
                    f"Volume ضعيف {volume_ratio:.2f}x"
                )

        if rsi_ok:
            score += 1
            signals.append(
                f"RSI مناسب {current_rsi:.1f}"
            )

        if rsi_improving:
            score += 2
            signals.append(
                f"RSI يتحسن {previous_rsi:.1f} → {current_rsi:.1f}"
            )

        # ====================================================
        # القرار
        # ====================================================

        # أقوى إشارة:
        # دعم + Higher Low + Breakout + Volume
        if (
            support_confirmed
            and breakout
            and volume_confirmed
            and higher_low
        ):

            status = "ENTRY_TRIGGER"

            action = (
                "إشارة دخول: "
                "اختراق + حجم + دعم مؤكد"
            )

        elif (
            support_confirmed
            and (
                higher_low
                or breakout
            )
            and volume_confirmed
        ):

            status = "ALMOST_READY"

            action = (
                "قريب جداً: انتظر تأكيد إضافي"
            )

        elif support_confirmed:

            status = "WAIT"

            action = (
                "الدعم موجود. "
                "انتظر صعود وحجم"
            )

        else:

            status = "WAIT_SUPPORT"

            action = (
                "انتظر تكوين/تأكيد الدعم"
            )

        return {

            "ticker": ticker,
            "price": price,
            "support": support,
            "support_tests": support_tests,
            "support_distance": support_distance,
            "volume": volume,
            "volume_ratio": volume_ratio,
            "rsi": current_rsi,
            "previous_rsi": previous_rsi,
            "rsi_improving": rsi_improving,
            "higher_low": higher_low,
            "green_candle": green_candle,
            "strong_candle": strong_candle,
            "breakout": breakout,
            "score": score,
            "status": status,
            "action": action,
            "signals": signals,
            "warnings": warnings
        }

    except Exception as e:

        print(
            f"ERROR {ticker}: {e}"
        )

        return None


# ============================================================
# تشغيل
# ============================================================

watchlist = load_watchlist()

print()
print("=" * 75)
print("5-MINUTE TRIGGER SCANNER")
print("=" * 75)
print(
    f"وقت الفحص: "
    f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
)
print(
    f"عدد الأسهم: {len(watchlist)}"
)
print("=" * 75)

results = []

for ticker in watchlist:

    print(
        f"تحليل {ticker} ..."
    )

    result = analyze(ticker)

    if result:
        results.append(result)


# ============================================================
# ترتيب
# ============================================================

order = {
    "ENTRY_TRIGGER": 4,
    "ALMOST_READY": 3,
    "WAIT": 2,
    "WAIT_SUPPORT": 1
}

results.sort(
    key=lambda x: (
        order.get(x["status"], 0),
        x["score"],
        x["volume_ratio"] or 0
    ),
    reverse=True
)


# ============================================================
# النتائج
# ============================================================

print()
print("=" * 75)
print("أفضل الفرص الآن")
print("=" * 75)

for i, r in enumerate(results, 1):

    print()
    print(
        f"{i}. {r['ticker']} | "
        f"{r['status']} | "
        f"Score {r['score']}"
    )

    print(
        f"   السعر: {fmt_price(r['price'])} | "
        f"الدعم: {fmt_price(r['support'])} | "
        f"اختبارات: {r['support_tests']}"
    )

    print(
        f"   RSI: "
        f"{r['rsi']:.1f}"
        if r["rsi"] is not None
        else "   RSI: N/A"
    )

    print(
        f"   Volume Ratio: "
        f"{r['volume_ratio']:.2f}x"
        if r["volume_ratio"] is not None
        else "   Volume Ratio: N/A"
    )

    print(
        f"   Higher Low: "
        f"{'YES' if r['higher_low'] else 'NO'} | "
        f"Breakout: "
        f"{'YES' if r['breakout'] else 'NO'}"
    )

    print(
        f"   الخطوة: {r['action']}"
    )

    for signal in r["signals"]:
        print(
            f"   OK: {signal}"
        )

    for warning in r["warnings"]:
        print(
            f"   WARN: {warning}"
        )


# ============================================================
# ENTRY TRIGGERS فقط
# ============================================================

entries = [
    r for r in results
    if r["status"] == "ENTRY_TRIGGER"
]

print()
print("=" * 75)
print("ENTRY TRIGGERS")
print("=" * 75)

if entries:

    for r in entries:

        print(
            f"{r['ticker']} | "
            f"PRICE {fmt_price(r['price'])} | "
            f"RSI {r['rsi']:.1f} | "
            f"VOL {r['volume_ratio']:.2f}x | "
            f"SUPPORT {fmt_price(r['support'])}"
        )

        print(
            ">>> دخول مشروط: "
            "تأكد من استمرار الحجم وعدم كسر الدعم."
        )

else:

    print(
        "لا يوجد ENTRY_TRIGGER حالياً."
    )

    print(
        "وهذا طبيعي: ننتظر أن يبدأ السهم فعلياً."
    )


# ============================================================
# الخلاصة
# ============================================================

print()
print("=" * 75)
print("الخلاصة")
print("=" * 75)

print(
    "MATCH من الرادار = مرشح."
)

print(
    "ENTRY_TRIGGER = تأكيد حركة على فريم 5 دقائق."
)

print(
    "لا دخول بسبب RSI وحده."
)

print(
    "لا دخول بسبب الدعم وحده."
)

print(
    "أفضل إشارة = دعم مؤكد + Higher Low + "
    "Breakout + Volume."
)

print("=" * 75)
