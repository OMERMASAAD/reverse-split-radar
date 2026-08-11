import yfinance as yf
import pandas as pd
import numpy as np
import json
from datetime import datetime, timedelta

# ============================================================
# REVERSE SPLIT RADAR - FINAL
# ============================================================

CANDIDATES_FILE = "reverse_split_candidates.json"

MIN_DAYS = 20
MAX_DAYS = 50
MIN_HISTORY_DAYS = 60

# منطقة نصف افتتاح شمعة التقسيم
HALF_ZONE_TOLERANCE = 0.15

# الدعم
SUPPORT_TOLERANCE = 0.04
MIN_SUPPORT_TESTS = 2

# Volume
QUIET_VOLUME_RATIO = 1.50

# Short
MAX_SHORT = 50000

# Float
MAX_FLOAT = 4000000

# ============================================================
# تحميل الأسهم
# ============================================================

def load_tickers():
    try:
        with open(CANDIDATES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, list):
            return [
                str(x["symbol"]).upper()
                for x in data
                if isinstance(x, dict) and "symbol" in x
            ]

        if isinstance(data, dict):
            items = data.get("candidates", [])
            return [
                str(x["symbol"]).upper()
                for x in items
                if isinstance(x, dict) and "symbol" in x
            ]

    except Exception as e:
        print(f"ERROR loading candidates: {e}")

    return []

TICKERS = load_tickers()

# ============================================================
# أدوات
# ============================================================

def safe_float(x):
    try:
        if x is None:
            return None
        x = float(x)
        if np.isnan(x):
            return None
        return x
    except Exception:
        return None


def fmt_price(x):
    x = safe_float(x)
    return "N/A" if x is None else f"${x:.4f}"


def fmt_num(x):
    x = safe_float(x)
    return "N/A" if x is None else f"{x:,.0f}"


# ============================================================
# RSI
# ============================================================

def calculate_rsi(close, period=14):
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)

    return 100 - (100 / (1 + rs))


# ============================================================
# MACD
# ============================================================

def calculate_macd(close):
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()

    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    hist = macd - signal

    return macd, signal, hist


# ============================================================
# Reverse Split
# ============================================================

def get_reverse_split_info(stock):
    try:
        splits = stock.splits

        if splits is None or splits.empty:
            return None

        latest_date = None
        latest_ratio = None

        for date, ratio in splits.items():
            ratio = safe_float(ratio)

            if ratio is None:
                continue

            # yfinance:
            # Reverse split غالباً يظهر كـ 0.5 أو 0.3333
            if ratio >= 1:
                continue

            d = pd.Timestamp(date).date()

            if latest_date is None or d > latest_date:
                latest_date = d
                latest_ratio = ratio

        if latest_date is None:
            return None

        return latest_date, latest_ratio

    except Exception:
        return None


def reverse_ratio_text(ratio):
    ratio = safe_float(ratio)

    if ratio is None or ratio <= 0:
        return "Unknown"

    return f"{round(1 / ratio)}:1 Reverse split"


# ============================================================
# الدعم
# ============================================================

def calculate_support(df):
    if len(df) < 10:
        return None

    recent = df.tail(40)

    lows = recent["Low"].dropna()

    if lows.empty:
        return None

    # نأخذ منطقة القيعان المتكررة بدلاً من قاع واحد
    return float(np.percentile(lows, 15))


# ============================================================
# حساب اختبارات الدعم
# ============================================================

def count_support_tests(df, support):
    if support is None:
        return 0

    tolerance = support * SUPPORT_TOLERANCE

    tests = 0
    last_test_index = None

    recent = df.tail(40)

    for idx, row in recent.iterrows():
        low = safe_float(row["Low"])

        if low is None:
            continue

        if abs(low - support) <= tolerance:
            if last_test_index is None:
                tests += 1
                last_test_index = idx
            else:
                days_gap = (idx.date() - last_test_index.date()).days

                # لا نحسب نفس الاختبار عدة مرات في نفس الحركة
                if days_gap >= 2:
                    tests += 1
                    last_test_index = idx

    return tests


# ============================================================
# أهم جزء:
# نصف افتتاح شمعة Reverse Split
# ============================================================

def analyze_half_zone(df, split_date):
    result = {
        "split_open": None,
        "half_level": None,
        "zone_low": None,
        "zone_high": None,
        "tests": 0,
        "successful_tests": 0,
        "stable": False,
        "passed": False,
        "status": "FAIL",
        "reason": ""
    }

    try:
        split_rows = df[df.index.date == split_date].copy()

        if split_rows.empty:
            result["reason"] = "لا توجد شمعة يوم التقسيم"
            return result

        split_open = safe_float(split_rows.iloc[0]["Open"])

        if split_open is None or split_open <= 0:
            result["reason"] = "تعذر تحديد افتتاح يوم التقسيم"
            return result

        # نصف افتتاح يوم التقسيم
        half_level = split_open / 2.0

        # ±15%
        zone_low = half_level * (1 - HALF_ZONE_TOLERANCE)
        zone_high = half_level * (1 + HALF_ZONE_TOLERANCE)

        result["split_open"] = split_open
        result["half_level"] = half_level
        result["zone_low"] = zone_low
        result["zone_high"] = zone_high

        after = df[df.index.date > split_date].copy()

        if after.empty:
            result["reason"] = "لا توجد بيانات بعد التقسيم"
            return result

        # ----------------------------------------------------
        # نبحث عن الاختبارات
        # ----------------------------------------------------

        tests = []

        for idx, row in after.iterrows():
            low = safe_float(row["Low"])
            close = safe_float(row["Close"])
            high = safe_float(row["High"])

            if low is None:
                continue

            # دخل منطقة نصف الشمعة
            if zone_low <= low <= zone_high:

                # هل حصل ارتداد؟
                rebound = False

                if close is not None:
                    rebound = close > low * 1.03

                tests.append({
                    "date": idx,
                    "low": low,
                    "close": close,
                    "high": high,
                    "rebound": rebound
                })

        # ----------------------------------------------------
        # تجميع الاختبارات القريبة من بعضها
        # ----------------------------------------------------

        grouped = []

        for test in tests:

            if not grouped:
                grouped.append(test)
                continue

            prev = grouped[-1]

            gap = (
                test["date"].date()
                - prev["date"].date()
            ).days

            if gap >= 2:
                grouped.append(test)

        result["tests"] = len(grouped)

        successful = sum(
            1 for x in grouped
            if x["rebound"]
        )

        result["successful_tests"] = successful

        # ----------------------------------------------------
        # هل ثبت الدعم؟
        # ----------------------------------------------------

        if len(grouped) >= 2 and successful >= 1:

            result["stable"] = True
            result["passed"] = True
            result["status"] = "PASS"

            result["reason"] = (
                "اختباران أو أكثر مع ثبات وارتداد"
            )

        elif len(grouped) == 1:

            result["status"] = "WATCH"

            result["reason"] = (
                "اختبار واحد فقط - ننتظر إعادة الاختبار"
            )

        else:

            result["status"] = "WAIT"

            result["reason"] = (
                "لم يتأكد القاع بعد"
            )

        return result

    except Exception as e:

        result["reason"] = f"خطأ: {e}"

        return result


# ============================================================
# المحفزات
# ============================================================

def get_catalysts(stock):
    catalysts = []

    try:
        calendar = stock.calendar

        if isinstance(calendar, dict):

            if calendar.get("Earnings Date") is not None:
                catalysts.append("موعد نتائج مالية")

        elif isinstance(calendar, pd.DataFrame):

            if (
                not calendar.empty
                and "Earnings Date" in calendar.index
            ):
                catalysts.append("موعد نتائج مالية")

    except Exception:
        pass

    try:
        earnings = stock.get_earnings_dates(limit=4)

        if earnings is not None and not earnings.empty:

            now = pd.Timestamp.now()

            for d in earnings.index:

                try:
                    d = pd.Timestamp(d)

                    if d.tzinfo is not None:
                        d = d.tz_localize(None)

                    if d >= now:
                        catalysts.append("نتائج مالية قادمة")
                        break

                except Exception:
                    continue

    except Exception:
        pass

    return list(dict.fromkeys(catalysts))


# ============================================================
# تحليل سهم
# ============================================================

def analyze_stock(ticker):

    try:

        stock = yf.Ticker(ticker)

        split_info = get_reverse_split_info(stock)

        if split_info is None:
            return None

        split_date, split_ratio = split_info

        today = datetime.now().date()

        days_since_split = (
            today - split_date
        ).days

        if not (
            MIN_DAYS <= days_since_split <= MAX_DAYS
        ):
            return None

        # ----------------------------------------------------
        # بيانات
        # ----------------------------------------------------

        start = split_date - timedelta(days=150)

        df = stock.history(
            start=start,
            end=today + timedelta(days=1),
            auto_adjust=False
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

        if len(df) < MIN_HISTORY_DAYS:
            return None

        # ----------------------------------------------------
        # Indicators
        # ----------------------------------------------------

        df["RSI"] = calculate_rsi(df["Close"])

        (
            df["MACD"],
            df["MACD_SIGNAL"],
            df["MACD_HIST"]
        ) = calculate_macd(df["Close"])

        df["MA20"] = df["Close"].rolling(20).mean()
        df["MA50"] = df["Close"].rolling(50).mean()

        latest = df.iloc[-1]

        price = safe_float(latest["Close"])
        volume = safe_float(latest["Volume"])

        rsi = safe_float(latest["RSI"])
        macd = safe_float(latest["MACD"])
        macd_hist = safe_float(latest["MACD_HIST"])

        ma20 = safe_float(latest["MA20"])
        ma50 = safe_float(latest["MA50"])

        if price is None:
            return None

        # ----------------------------------------------------
        # RSI
        # ----------------------------------------------------

        previous_rsi = None

        if len(df) >= 2:
            previous_rsi = safe_float(
                df["RSI"].iloc[-2]
            )

        rsi_improving = (
            rsi is not None
            and previous_rsi is not None
            and rsi > previous_rsi
        )

        # ----------------------------------------------------
        # MACD
        # ----------------------------------------------------

        macd_improving = False

        if len(df) >= 3:

            h1 = safe_float(
                df["MACD_HIST"].iloc[-2]
            )

            h2 = safe_float(
                df["MACD_HIST"].iloc[-3]
            )

            if (
                h1 is not None
                and h2 is not None
                and h1 > h2
            ):
                macd_improving = True

        # ----------------------------------------------------
        # Volume
        # ----------------------------------------------------

        volume20 = safe_float(
            df["Volume"].tail(20).mean()
        )

        volume_ratio = None

        if volume is not None and volume20:
            volume_ratio = volume / volume20

        quiet_volume = (
            volume_ratio is not None
            and volume_ratio <= QUIET_VOLUME_RATIO
        )

        # ----------------------------------------------------
        # بيانات منذ التقسيم
        # ----------------------------------------------------

        post = df[df.index.date >= split_date].copy()

        if post.empty:
            return None

        split_open = safe_float(
            post.iloc[0]["Open"]
        )

        split_high = safe_float(
            post["High"].max()
        )

        split_low = safe_float(
            post["Low"].min()
        )

        if split_open is None:
            return None

        post_change = (
            (price - split_open)
            / split_open
        ) * 100

        drawdown = None

        if split_high and split_high > 0:

            drawdown = (
                (price - split_high)
                / split_high
            ) * 100

        # ----------------------------------------------------
        # نصف الشمعة + الثبات
        # ----------------------------------------------------

        half = analyze_half_zone(
            df,
            split_date
        )

        # ----------------------------------------------------
        # الدعم العام
        # ----------------------------------------------------

        support = calculate_support(df)

        support_tests = count_support_tests(
            df,
            support
        )

        near_support = False

        if support and support > 0:

            distance = (
                (price - support)
                / support
            )

            near_support = (
                0 <= distance <= 0.20
            )

        # ----------------------------------------------------
        # Float / Short
        # ----------------------------------------------------

        float_shares = None
        short_shares = None

        try:

            info = stock.info

            float_shares = safe_float(
                info.get("floatShares")
            )

            short_shares = safe_float(
                info.get("sharesShort")
            )

        except Exception:
            pass

        float_ok = (
            float_shares is not None
            and float_shares <= MAX_FLOAT
        )

        short_ok = (
            short_shares is not None
            and short_shares <= MAX_SHORT
        )

        # ----------------------------------------------------
        # MA
        # ----------------------------------------------------

        ma20_ok = (
            ma20 is not None
            and price <= ma20 * 1.10
        )

        # ----------------------------------------------------
        # Catalysts
        # ----------------------------------------------------

        catalysts = get_catalysts(stock)

        # ====================================================
        # SCORE
        # ====================================================

        score = 0
        signals = []
        warnings = []

        # Reverse split
        score += 2
        signals.append("Reverse Split حديث")

        # Half zone
        if half["passed"]:

            score += 4

            signals.append(
                f"دعم نصف الشمعة مؤكد "
                f"({half['tests']} اختبارات)"
            )

        elif half["status"] == "WATCH":

            score += 1

            warnings.append(
                "اختبار واحد فقط لنصف الشمعة"
            )

        else:

            warnings.append(
                "لم يتأكد دعم نصف الشمعة"
            )

        # RSI
        if rsi is not None:

            if rsi < 30:

                score += 3

                if rsi_improving:

                    score += 2

                    signals.append(
                        f"RSI منخفض ويتحسن "
                        f"({previous_rsi:.1f}->{rsi:.1f})"
                    )

                else:

                    signals.append(
                        f"RSI منخفض ({rsi:.1f})"
                    )

            elif rsi < 35:

                score += 1

                signals.append(
                    f"RSI قريب من التشبع البيعي "
                    f"({rsi:.1f})"
                )

            elif rsi < 50:

                signals.append(
                    f"RSI محايد ({rsi:.1f})"
                )

            else:

                warnings.append(
                    f"RSI مرتفع ({rsi:.1f})"
                )

        # MACD
        if macd_improving:

            score += 2
            signals.append("MACD يتحسن")

        else:

            warnings.append(
                "MACD لم يظهر تحسنًا كافيًا"
            )

        # Volume
        if quiet_volume:

            score += 2

            signals.append(
                f"Volume هادئ ({fmt_num(volume)})"
            )

        elif volume_ratio is not None:

            signals.append(
                f"Volume Ratio {volume_ratio:.2f}x"
            )

        # Support
        if support_tests >= 2:

            score += 2

            signals.append(
                f"الدعم العام اختُبر {support_tests} مرات"
            )

        elif support_tests == 1:

            score += 1

            signals.append(
                "يوجد اختبار دعم واحد"
            )

        # Near support
        if near_support:

            score += 1
            signals.append("السعر قريب من الدعم")

        # Drawdown
        if drawdown is not None:

            if drawdown <= -40:

                score += 3

                signals.append(
                    f"هبوط قوي من القمة ({drawdown:.1f}%)"
                )

            elif drawdown <= -30:

                score += 2

                signals.append(
                    f"تصحيح جيد من القمة ({drawdown:.1f}%)"
                )

            elif drawdown <= -20:

                score += 1

                signals.append(
                    f"تصحيح متوسط ({drawdown:.1f}%)"
                )

        # Float
        if float_ok:

            score += 1

            signals.append(
                f"Float منخفض ({fmt_num(float_shares)})"
            )

        # Short
        if short_ok:

            score += 1

            signals.append(
                f"Short منخفض ({fmt_num(short_shares)})"
            )

        elif short_shares is not None:

            warnings.append(
                f"Short مرتفع ({fmt_num(short_shares)})"
            )

        # MA20
        if ma20_ok:

            score += 1
            signals.append("السعر قريب من MA20")

        # Catalyst
        if catalysts:

            score += 2

            for c in catalysts:
                signals.append(c)

        # ====================================================
        # CORE CONDITIONS
        # ====================================================

        core = 0

        if half["passed"]:
            core += 2

        elif half["status"] == "WATCH":
            core += 1

        if rsi is not None and rsi < 35:
            core += 1

        if rsi_improving:
            core += 1

        if macd_improving:
            core += 1

        if quiet_volume:
            core += 1

        if support_tests >= 2:
            core += 1

        if near_support:
            core += 1

        if float_ok:
            core += 1

        if catalysts:
            core += 1

        # ====================================================
        # الخطوة التالية
        # ====================================================

        if (
            half["passed"]
            and rsi_improving
            and macd_improving
            and core >= 6
        ):

            next_step = "READY_TRIGGER"

            next_text = (
                "الدعم مؤكد. انتظر تأكيد صعود/حجم للدخول."
            )

        elif half["passed"]:

            next_step = "WAIT_TRIGGER"

            next_text = (
                "الدعم مؤكد، لكن ننتظر تحسن المؤشرات أو محفز."
            )

        elif half["status"] == "WATCH":

            next_step = "WAIT_RETEST"

            next_text = (
                "تم اختبار المنطقة مرة واحدة. "
                "انتظر إعادة الاختبار والثبات."
            )

        else:

            next_step = "WAIT_SUPPORT"

            next_text = (
                "لا تدخل. انتظر تكوين قاع واختبار دعم واضح."
            )

        # ====================================================
        # التصنيف
        # ====================================================

        if (
            next_step == "READY_TRIGGER"
            and score >= 18
        ):

            rating = "MATCH قوي جداً"

        elif (
            half["passed"]
            and core >= 5
        ):

            rating = "WATCHLIST قوية"

        elif core >= 3:

            rating = "WATCHLIST"

        else:

            rating = "مراقبة"

        return {
            "ticker": ticker,
            "score": score,
            "rating": rating,
            "next_step": next_step,
            "next_text": next_text,
            "price": price,
            "split_date": split_date,
            "split_ratio": split_ratio,
            "days_since_split": days_since_split,
            "split_open": split_open,
            "split_high": split_high,
            "split_low": split_low,
            "post_change": post_change,
            "drawdown": drawdown,
            "support": support,
            "support_tests": support_tests,
            "volume": volume,
            "volume20": volume20,
            "volume_ratio": volume_ratio,
            "rsi": rsi,
            "previous_rsi": previous_rsi,
            "rsi_improving": rsi_improving,
            "macd": macd,
            "macd_improving": macd_improving,
            "ma20": ma20,
            "ma50": ma50,
            "float_shares": float_shares,
            "short_shares": short_shares,
            "half": half,
            "catalysts": catalysts,
            "signals": signals,
            "warnings": warnings,
            "core": core
        }

    except Exception as e:

        print(
            f"ERROR analyzing {ticker}: {e}"
        )

        return None


# ============================================================
# تشغيل
# ============================================================

print()
print("=" * 75)
print("REVERSE SPLIT RADAR - FINAL STRATEGY")
print("=" * 75)
print(
    f"الفترة: {MIN_DAYS}-{MAX_DAYS} يوم بعد Reverse Split"
)
print(
    f"منطقة نصف الافتتاح: ±{HALF_ZONE_TOLERANCE * 100:.0f}%"
)
print(
    "تأكيد الدعم: اختباران على الأقل مع ثبات/ارتداد"
)
print(
    f"عدد الأسهم: {len(TICKERS)}"
)
print("=" * 75)

results = []

for ticker in TICKERS:

    print(f"\nتحليل: {ticker}")

    result = analyze_stock(ticker)

    if result is None:

        print(
            "لا توجد بيانات كافية أو السهم خارج الفترة."
        )

        continue

    results.append(result)

    print("-" * 75)

    print(
        f"السعر الحالي: {fmt_price(result['price'])}"
    )

    print(
        f"Reverse Split: {result['split_date']}"
    )

    print(
        f"النسبة: {reverse_ratio_text(result['split_ratio'])}"
    )

    print(
        f"الأيام منذ التقسيم: {result['days_since_split']}"
    )

    print(
        f"افتتاح يوم التقسيم: {fmt_price(result['split_open'])}"
    )

    print(
        f"أعلى سعر منذ التقسيم: {fmt_price(result['split_high'])}"
    )

    print(
        f"أدنى سعر منذ التقسيم: {fmt_price(result['split_low'])}"
    )

    print(
        f"الحركة من الافتتاح: {result['post_change']:.1f}%"
    )

    if result["drawdown"] is not None:
        print(
            f"الهبوط من القمة: {result['drawdown']:.1f}%"
        )

    print(
        f"الدعم العام: {fmt_price(result['support'])}"
    )

    print(
        f"اختبارات الدعم العام: {result['support_tests']}"
    )

    print(
        f"Volume: {fmt_num(result['volume'])}"
    )

    if result["volume_ratio"] is not None:
        print(
            f"Volume Ratio: {result['volume_ratio']:.2f}x"
        )

    print(
        f"RSI: "
        f"{result['rsi']:.1f}"
        if result["rsi"] is not None
        else "RSI: N/A"
    )

    if result["previous_rsi"] is not None:
        print(
            f"RSI السابق: {result['previous_rsi']:.1f}"
        )

    print(
        f"MACD: "
        f"{result['macd']:.5f}"
        if result["macd"] is not None
        else "MACD: N/A"
    )

    print(
        f"MA20: {fmt_price(result['ma20'])}"
    )

    print(
        f"MA50: {fmt_price(result['ma50'])}"
    )

    # --------------------------------------------------------
    # نصف الشمعة
    # --------------------------------------------------------

    h = result["half"]

    print()
    print("منطقة نصف شمعة التقسيم")
    print("-" * 75)

    print(
        f"نصف الافتتاح: {fmt_price(h['half_level'])}"
    )

    print(
        f"منطقة البحث عن القاع: "
        f"{fmt_price(h['zone_low'])} - "
        f"{fmt_price(h['zone_high'])}"
    )

    print(
        f"اختبارات المنطقة: {h['tests']}"
    )

    print(
        f"اختبارات ناجحة/ارتداد: {h['successful_tests']}"
    )

    print(
        f"حالة الدعم: {h['status']}"
    )

    print(
        f"التفسير: {h['reason']}"
    )

    # --------------------------------------------------------
    # إشارات
    # --------------------------------------------------------

    print()
    print("إشارات التحليل")
    print("-" * 75)

    for s in result["signals"]:
        print(f"OK: {s}")

    for w in result["warnings"]:
        print(f"WARN: {w}")

    # --------------------------------------------------------
    # النتيجة
    # --------------------------------------------------------

    print()
    print(
        f"التقييم: {result['rating']}"
    )

    print(
        f"SCORE: {result['score']}"
    )

    print(
        f"CORE: {result['core']}"
    )

    print(
        f"الخطوة التالية: {result['next_step']}"
    )

    print(
        f">>> {result['next_text']}"
    )


# ============================================================
# ترتيب
# ============================================================

rating_order = {
    "MATCH قوي جداً": 4,
    "WATCHLIST قوية": 3,
    "WATCHLIST": 2,
    "مراقبة": 1
}

results.sort(
    key=lambda x: (
        rating_order.get(x["rating"], 0),
        x["half"]["passed"],
        x["half"]["tests"],
        x["rsi_improving"],
        x["macd_improving"],
        x["core"],
        x["score"]
    ),
    reverse=True
)


# ============================================================
# أفضل الأسهم
# ============================================================

print()
print("=" * 75)
print("أفضل الأسهم")
print("=" * 75)

for title in [
    "MATCH قوي جداً",
    "WATCHLIST قوية",
    "WATCHLIST"
]:

    group = [
        r for r in results
        if r["rating"] == title
    ]

    if not group:
        continue

    print()
    print(title)
    print("-" * 75)

    for i, r in enumerate(group[:10], 1):

        rsi_text = (
            f"{r['rsi']:.1f}"
            if r["rsi"] is not None
            else "N/A"
        )

        print(
            f"{i}. {r['ticker']} | "
            f"Score {r['score']} | "
            f"RSI {rsi_text} | "
            f"Vol {fmt_num(r['volume'])} | "
            f"Price {fmt_price(r['price'])} | "
            f"Half {fmt_price(r['half']['half_level'])} | "
            f"Tests {r['half']['tests']} | "
            f"{r['next_step']}"
        )


# ============================================================
# قائمة الأولوية
# ============================================================

print()
print("=" * 75)
print("قائمة الأولوية للمتابعة")
print("=" * 75)

priority = [
    r for r in results
    if r["next_step"] in [
        "READY_TRIGGER",
        "WAIT_TRIGGER",
        "WAIT_RETEST"
    ]
]

if priority:

    for i, r in enumerate(priority[:15], 1):

        print()
        print(
            f"{i}. {r['ticker']} "
            f"| {r['rating']} "
            f"| Score {r['score']}"
        )

        print(
            f"   السعر: {fmt_price(r['price'])}"
        )

        print(
            f"   منطقة نصف الشمعة: "
            f"{fmt_price(r['half']['zone_low'])} - "
            f"{fmt_price(r['half']['zone_high'])}"
        )

        print(
            f"   الاختبارات: "
            f"{r['half']['tests']}"
        )

        print(
            f"   الخطوة: {r['next_text']}"
        )

else:

    print(
        "لا يوجد سهم حاليًا في مرحلة تأكيد الدعم."
    )


# ============================================================
# المحفزات
# ============================================================

print()
print("=" * 75)
print("المحفزات المستقبلية")
print("=" * 75)

found = False

for r in results:

    if not r["catalysts"]:
        continue

    found = True

    print()
    print(r["ticker"])

    for c in r["catalysts"]:
        print(f"  - {c}")

if not found:

    print(
        "لا توجد محفزات مستقبلية واضحة من البيانات المتاحة."
    )


# ============================================================
# الخلاصة
# ============================================================

print()
print("=" * 75)
print("الخلاصة النهائية")
print("=" * 75)

print(
    "الرادار يبحث عن سهم بعد Reverse Split حديث، "
    "ثم يبحث عن منطقة نصف افتتاح شمعة التقسيم."
)

print(
    f"منطقة نصف الشمعة تستخدم ±{HALF_ZONE_TOLERANCE * 100:.0f}% "
    "بدلاً من اشتراط رقم واحد."
)

print(
    "اختبار واحد = مراقبة."
)

print(
    "اختباران مع ثبات/ارتداد = دعم مؤكد."
)

print(
    "كسر المنطقة والاستمرار في الهبوط = لا تأكيد للدعم."
)

print(
    "بعد تأكيد الدعم ننتظر RSI/MACD/Volume "
    "وتأكيد حركة السعر قبل التفكير بالدخول."
)

print()
print(
    "انتهى Reverse Split Strategy Scanner."
)
print("=" * 75)
