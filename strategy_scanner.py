import yfinance as yf
import pandas as pd
import numpy as np
import json
from datetime import datetime, timedelta


# ============================================================
# 🎯 REVERSE SPLIT STRATEGY SCANNER
# ============================================================
#
# الهدف:
# العثور على أسهم هادئة بعد Reverse Split
# هبطت بشكل واضح، اقتربت من دعم، اختبرت الدعم،
# RSI منخفض ويبدأ بالتحسن، MACD يتحسن،
# السيولة هادئة، Float و Short مناسبين،
# مع البحث عن محفز مستقبلي.
#
# السهم لا يتم حذفه بسبب التدهور.
# ============================================================


CANDIDATES_FILE = "reverse_split_candidates.json"

MIN_DAYS = 20
MAX_DAYS = 50

MIN_HISTORY_DAYS = 20

MAX_SHORT = 50000

# أقصى حركة نعتبرها هادئة بعد التقسيم
MAX_POST_SPLIT_MOVE = 0.50

# أقصى انطلاقة أولية
MAX_INITIAL_RUN = 0.20

# أقصى Volume Ratio نعتبره هادئاً
QUIET_VOLUME_RATIO = 1.50

# أقصى مسافة عن الدعم
SUPPORT_DISTANCE_MAX = 0.20

# الحد الأدنى لاختبارات الدعم
MIN_SUPPORT_TESTS = 2


# ============================================================
# قراءة المرشحين
# ============================================================

try:

    with open(CANDIDATES_FILE, "r", encoding="utf-8") as f:
        candidates = json.load(f)

    TICKERS = [
        item["symbol"]
        for item in candidates
        if isinstance(item, dict) and "symbol" in item
    ]

except Exception as e:

    print(f"❌ فشل تحميل قائمة المرشحين: {e}")
    TICKERS = []


# ============================================================
# أدوات مساعدة
# ============================================================

def safe_float(value):

    try:

        if value is None:
            return None

        value = float(value)

        if np.isnan(value):
            return None

        return value

    except Exception:

        return None


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

    rsi = 100 - (100 / (1 + rs))

    return rsi


# ============================================================
# MACD
# ============================================================

def calculate_macd(close):

    ema12 = close.ewm(
        span=12,
        adjust=False
    ).mean()

    ema26 = close.ewm(
        span=26,
        adjust=False
    ).mean()

    macd = ema12 - ema26

    signal = macd.ewm(
        span=9,
        adjust=False
    ).mean()

    histogram = macd - signal

    return macd, signal, histogram


# ============================================================
# استخراج Reverse Split
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

            # Yahoo Finance يسجل Reverse Split كرقم أقل من 1
            # مثال:
            # 1:5  = 0.2
            # 1:10 = 0.1

            if ratio < 1:

                try:

                    split_date = pd.Timestamp(date).date()

                except Exception:

                    continue

                if (
                    latest_date is None
                    or split_date > latest_date
                ):

                    latest_date = split_date
                    latest_ratio = ratio

        if latest_date is None:
            return None

        return latest_date, latest_ratio

    except Exception:

        return None


# ============================================================
# تحويل النسبة إلى صيغة مفهومة
# ============================================================

def reverse_ratio_text(ratio):

    try:

        if ratio is None or ratio <= 0:
            return "Unknown"

        reverse_number = round(1 / ratio)

        return f"{reverse_number}:1 Reverse split"

    except Exception:

        return "Reverse split"


# ============================================================
# حساب الدعم
# ============================================================

def calculate_support(df):

    if df is None or len(df) < 10:
        return None

    recent = df.tail(20)

    lows = recent["Low"].dropna().values

    if len(lows) == 0:
        return None

    support = float(
        np.percentile(lows, 15)
    )

    return support


# ============================================================
# عدد اختبارات الدعم
# ============================================================

def count_support_tests(df, support):

    if support is None or support <= 0:
        return 0

    tolerance = support * 0.04

    tests = 0

    recent_lows = df["Low"].tail(40)

    for low in recent_lows:

        low = safe_float(low)

        if low is None:
            continue

        if abs(low - support) <= tolerance:
            tests += 1

    return tests


# ============================================================
# فحص نصف شمعة الانطلاقة
# ============================================================

def check_half_candle_condition(df, split_date):

    result = {
        "passed": False,
        "initial_run": None,
        "half_level": None,
        "lowest_after_run": None,
        "reason": ""
    }

    try:

        split_data = df[
            df.index.date >= split_date
        ].copy()

        if len(split_data) < 5:

            result["reason"] = (
                "بيانات غير كافية بعد التقسيم"
            )

            return result

        # أول 5 جلسات بعد Reverse Split
        first_days = split_data.head(5)

        first_open = safe_float(
            first_days.iloc[0]["Open"]
        )

        first_high = safe_float(
            first_days["High"].max()
        )

        if (
            first_open is None
            or first_high is None
            or first_open <= 0
        ):

            result["reason"] = (
                "تعذر تحديد افتتاح/قمة الانطلاقة"
            )

            return result

        initial_run = (
            (first_high - first_open)
            / first_open
        )

        result["initial_run"] = (
            initial_run * 100
        )

        # إذا ارتفع أكثر من 20%
        # لا نعتبره ضمن الانطلاقة الهادئة

        if initial_run > MAX_INITIAL_RUN:

            result["reason"] = (
                f"الانطلاقة الأولى قوية "
                f"({initial_run * 100:.1f}%)"
            )

            return result

        # نصف المسافة بين الافتتاح والقمة

        half_level = first_open + (
            (first_high - first_open) * 0.50
        )

        result["half_level"] = half_level

        # البيانات بعد أول 5 جلسات

        after_data = split_data.iloc[5:]

        if after_data.empty:

            result["reason"] = (
                "لا توجد بيانات كافية بعد الانطلاقة"
            )

            return result

        lowest = safe_float(
            after_data["Low"].min()
        )

        result["lowest_after_run"] = lowest

        # يجب أن يصل السهم إلى نصف منطقة الانطلاقة

        if (
            lowest is not None
            and lowest <= half_level
        ):

            result["passed"] = True

            result["reason"] = (
                "حقق شرط الهبوط إلى نصف منطقة الانطلاقة"
            )

        else:

            result["reason"] = (
                "لم يحقق شرط الهبوط إلى نصف منطقة الانطلاقة"
            )

        return result

    except Exception as e:

        result["reason"] = f"خطأ: {e}"

        return result


# ============================================================
# فحص محفزات مستقبلية
# ============================================================

def check_future_catalyst(stock):

    catalysts = []

    # --------------------------------------------------------
    # Earnings Calendar
    # --------------------------------------------------------

    try:

        calendar = stock.calendar

        if calendar is not None:

            if isinstance(calendar, dict):

                earnings = calendar.get(
                    "Earnings Date"
                )

                if earnings is not None:

                    catalysts.append(
                        "📅 موعد نتائج مالية"
                    )

            elif isinstance(calendar, pd.DataFrame):

                if not calendar.empty:

                    if "Earnings Date" in calendar.index:

                        catalysts.append(
                            "📅 موعد نتائج مالية"
                        )

    except Exception:

        pass

    # --------------------------------------------------------
    # Earnings Dates
    # --------------------------------------------------------

    try:

        earnings = stock.get_earnings_dates(
            limit=8
        )

        if (
            earnings is not None
            and not earnings.empty
        ):

            now = pd.Timestamp.now(
                tz=None
            )

            for date in earnings.index:

                try:

                    date_clean = pd.Timestamp(
                        date
                    )

                    if date_clean.tzinfo is not None:

                        date_clean = (
                            date_clean
                            .tz_localize(None)
                        )

                    if date_clean >= now:

                        catalysts.append(
                            "📅 نتائج مالية قادمة"
                        )

                        break

                except Exception:

                    continue

    except Exception:

        pass

    # إزالة التكرار

    catalysts = list(
        dict.fromkeys(catalysts)
    )

    return catalysts


# ============================================================
# تحليل السهم
# ============================================================

def analyze_stock(ticker):

    try:

        stock = yf.Ticker(ticker)

        # ----------------------------------------------------
        # Reverse Split
        # ----------------------------------------------------

        split_info = get_reverse_split_info(
            stock
        )

        if split_info is None:
            return None

        split_date, split_ratio = split_info

        today = datetime.now().date()

        days_since_split = (
            today - split_date
        ).days

        # ----------------------------------------------------
        # شرط 20 - 50 يوم
        # ----------------------------------------------------

        if not (
            MIN_DAYS
            <= days_since_split
            <= MAX_DAYS
        ):

            return None

        # ----------------------------------------------------
        # تحميل البيانات
        # ----------------------------------------------------

        start_date = (
            split_date
            - timedelta(days=100)
        )

        df = stock.history(
            start=start_date,
            end=today + timedelta(days=1),
            auto_adjust=False
        )

        if df is None or df.empty:
            return None

        if len(df) < MIN_HISTORY_DAYS:
            return None

        # ----------------------------------------------------
        # تنظيف
        # ----------------------------------------------------

        required_columns = [
            "Open",
            "High",
            "Low",
            "Close",
            "Volume"
        ]

        df = df.dropna(
            subset=required_columns
        )

        if len(df) < MIN_HISTORY_DAYS:
            return None

        # ----------------------------------------------------
        # المؤشرات
        # ----------------------------------------------------

        df["RSI"] = calculate_rsi(
            df["Close"]
        )

        (
            df["MACD"],
            df["MACD_SIGNAL"],
            df["MACD_HIST"]
        ) = calculate_macd(
            df["Close"]
        )

        df["MA20"] = (
            df["Close"]
            .rolling(20)
            .mean()
        )

        df["MA50"] = (
            df["Close"]
            .rolling(50)
            .mean()
        )

        latest = df.iloc[-1]

        price = safe_float(
            latest["Close"]
        )

        volume_today = safe_float(
            latest["Volume"]
        )

        rsi = safe_float(
            latest["RSI"]
        )

        macd = safe_float(
            latest["MACD"]
        )

        ma20 = safe_float(
            latest["MA20"]
        )

        ma50 = safe_float(
            latest["MA50"]
        )

        if price is None:
            return None

        # ----------------------------------------------------
        # RSI السابق
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
        # MACD يتحسن
        # ----------------------------------------------------

        macd_improving = False

        if len(df) >= 3:

            hist_prev = safe_float(
                df["MACD_HIST"].iloc[-2]
            )

            hist_prev2 = safe_float(
                df["MACD_HIST"].iloc[-3]
            )

            if (
                hist_prev is not None
                and hist_prev2 is not None
                and hist_prev > hist_prev2
            ):

                macd_improving = True

        # ----------------------------------------------------
        # Volume
        # ----------------------------------------------------

        volume_20 = safe_float(
            df["Volume"].tail(20).mean()
        )

        volume_ratio = None

        if (
            volume_today is not None
            and volume_20 is not None
            and volume_20 > 0
        ):

            volume_ratio = (
                volume_today
                / volume_20
            )

        quiet_volume = (
            volume_ratio is not None
            and volume_ratio <= QUIET_VOLUME_RATIO
        )

        # ----------------------------------------------------
        # بيانات ما بعد التقسيم
        # ----------------------------------------------------

        split_data = df[
            df.index.date >= split_date
        ]

        if split_data.empty:
            return None

        split_high = safe_float(
            split_data["High"].max()
        )

        split_open = safe_float(
            split_data.iloc[0]["Open"]
        )

        if split_high is None:
            return None

        # ----------------------------------------------------
        # الحركة منذ التقسيم
        # ----------------------------------------------------

        post_split_change = None

        if (
            split_open is not None
            and split_open > 0
        ):

            post_split_change = (
                (price - split_open)
                / split_open
            ) * 100

        # ----------------------------------------------------
        # الهبوط من القمة
        # ----------------------------------------------------

        drawdown = (
            (price - split_high)
            / split_high
        ) * 100

        # ----------------------------------------------------
        # الدعم
        # ----------------------------------------------------

        support = calculate_support(
            df
        )

        support_tests = count_support_tests(
            df,
            support
        )

        support_distance = None

        if (
            support is not None
            and support > 0
        ):

            support_distance = (
                (price - support)
                / support
            )

        near_support = (
            support_distance is not None
            and 0 <= support_distance
            <= SUPPORT_DISTANCE_MAX
        )

        # ----------------------------------------------------
        # نصف شمعة الانطلاقة
        # ----------------------------------------------------

        half_candle = (
            check_half_candle_condition(
                df,
                split_date
            )
        )

        # ----------------------------------------------------
        # Float و Short
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

        short_ok = (
            short_shares is not None
            and short_shares < MAX_SHORT
        )

        # ----------------------------------------------------
        # MA20
        # ----------------------------------------------------

        ma20_ok = (
            ma20 is not None
            and price <= ma20 * 1.10
        )

        # ----------------------------------------------------
        # المحفز
        # ----------------------------------------------------

        catalysts = check_future_catalyst(
            stock
        )

        # ----------------------------------------------------
        # النقاط
        # ----------------------------------------------------

        score = 0

        signals = []

        warnings = []

        # ----------------------------------------------------
        # Reverse Split
        # ----------------------------------------------------

        score += 2

        signals.append(
            "✅ Reverse Split حديث"
        )

        # ----------------------------------------------------
        # Half Candle
        # ----------------------------------------------------

        if half_candle["passed"]:

            score += 3

            signals.append(
                "✅ تحقق شرط نصف شمعة الانطلاقة"
            )

        else:

            warnings.append(
                "⚠️ لم يتحقق شرط نصف شمعة الانطلاقة"
            )

        # ----------------------------------------------------
        # RSI
        # ----------------------------------------------------

        if rsi is not None:

            if rsi < 30:

                score += 3

                if rsi_improving:

                    score += 2

                    signals.append(
                        f"✅ RSI منخفض ويتحسن "
                        f"({previous_rsi:.1f} → {rsi:.1f})"
                    )

                else:

                    signals.append(
                        f"🟡 RSI منخفض ({rsi:.1f}) "
                        "لكن لم يبدأ التحسن بعد"
                    )

            elif rsi < 35:

                score += 1

                signals.append(
                    f"🟡 RSI قريب من التشبع "
                    f"({rsi:.1f})"
                )

            else:

                warnings.append(
                    f"❌ RSI مرتفع ({rsi:.1f})"
                )

        # ----------------------------------------------------
        # MACD
        # ----------------------------------------------------

        if macd_improving:

            score += 2

            signals.append(
                "✅ MACD يتحسن"
            )

        else:

            signals.append(
                "🟡 MACD لم يظهر تحسنًا كافيًا"
            )

        # ----------------------------------------------------
        # Volume
        # ----------------------------------------------------

        if quiet_volume:

            score += 2

            signals.append(
                f"✅ Volume هادئ "
                f"({volume_today:,.0f})"
            )

        elif volume_ratio is not None:

            signals.append(
                f"🟢 توجد سيولة مقارنة بالمتوسط "
                f"({volume_today:,.0f})"
            )

        # ----------------------------------------------------
        # Support Tests
        # ----------------------------------------------------

        if support_tests >= MIN_SUPPORT_TESTS:

            score += 2

            signals.append(
                f"✅ اختبار دعم عدة مرات "
                f"({support_tests})"
            )

        elif support_tests == 1:

            score += 1

            signals.append(
                "🟡 يوجد اختبار دعم"
            )

        else:

            warnings.append(
                "⚠️ لا توجد اختبارات دعم كافية"
            )

        # ----------------------------------------------------
        # قرب الدعم
        # ----------------------------------------------------

        if near_support:

            score += 2

            signals.append(
                "✅ السعر قريب من الدعم"
            )

        # ----------------------------------------------------
        # الحركة بعد التقسيم
        # ----------------------------------------------------

        if (
            post_split_change is not None
            and abs(post_split_change)
            <= MAX_POST_SPLIT_MOVE * 100
        ):

            score += 1

            signals.append(
                f"✅ الحركة بعد التقسيم هادئة "
                f"({post_split_change:.1f}%)"
            )

        elif post_split_change is not None:

            warnings.append(
                f"⚠️ الحركة بعد التقسيم قوية "
                f"({post_split_change:.1f}%)"
            )

        # ----------------------------------------------------
        # الهبوط من القمة
        # ----------------------------------------------------

        if drawdown <= -30:

            score += 2

            signals.append(
                f"✅ هبوط قوي من القمة "
                f"({drawdown:.1f}%)"
            )

        elif drawdown <= -20:

            score += 1

            signals.append(
                f"🟡 تصحيح جيد "
                f"({drawdown:.1f}%)"
            )

        else:

            warnings.append(
                f"⚠️ التصحيح ضعيف "
                f"({drawdown:.1f}%)"
            )

        # ----------------------------------------------------
        # Float
        # ----------------------------------------------------

        if (
            float_shares is not None
            and float_shares <= 4_000_000
        ):

            score += 1

            signals.append(
                f"✅ Float منخفض "
                f"({float_shares:,.0f})"
            )

        elif float_shares is not None:

            warnings.append(
                f"⚠️ Float مرتفع "
                f"({float_shares:,.0f})"
            )

        # ----------------------------------------------------
        # Short
        # ----------------------------------------------------

        if short_ok:

            score += 1

            signals.append(
                f"✅ Short منخفض "
                f"({short_shares:,.0f})"
            )

        elif short_shares is not None:

            warnings.append(
                f"⚠️ Short مرتفع "
                f"({short_shares:,.0f})"
            )

        # ----------------------------------------------------
        # MA20
        # ----------------------------------------------------

        if ma20_ok:

            score += 1

            signals.append(
                "✅ قريب من MA20"
            )

        # ----------------------------------------------------
        # Catalyst
        # ----------------------------------------------------

        if catalysts:

            score += 2

            for catalyst in catalysts:

                signals.append(
                    f"🚀 {catalyst}"
                )

        else:

            signals.append(
                "⚪ لا يوجد محفز مستقبلي واضح "
                "من البيانات المتاحة"
            )

        # ====================================================
        # Core Conditions
        # ====================================================

        core_conditions = 0

        if half_candle["passed"]:
            core_conditions += 1

        if (
            rsi is not None
            and rsi < 30
        ):
            core_conditions += 1

        if rsi_improving:
            core_conditions += 1

        if macd_improving:
            core_conditions += 1

        if quiet_volume:
            core_conditions += 1

        if support_tests >= MIN_SUPPORT_TESTS:
            core_conditions += 1

        if near_support:
            core_conditions += 1

        if short_ok:
            core_conditions += 1

        if (
            post_split_change is not None
            and post_split_change <= 20
        ):
            core_conditions += 1

        # ====================================================
        # التقييم النهائي
        # ====================================================

        if (
            rsi is not None
            and rsi < 30
            and rsi_improving
            and half_candle["passed"]
            and core_conditions >= 6
        ):

            rating = (
                "🔥🔥🔥 MATCH قوي جداً"
            )

        elif (
            rsi is not None
            and rsi < 35
            and half_candle["passed"]
            and core_conditions >= 5
        ):

            rating = (
                "🔥🔥 WATCHLIST قوية"
            )

        elif core_conditions >= 4:

            rating = (
                "🟢 WATCHLIST"
            )

        else:

            rating = (
                "🟡 مراقبة"
            )

        # ====================================================
        # النتيجة
        # ====================================================

        return {

            "ticker": ticker,

            "score": score,

            "rating": rating,

            "price": price,

            "split_date": split_date,

            "split_ratio": split_ratio,

            "days_since_split": days_since_split,

            "post_split_change": post_split_change,

            "drawdown": drawdown,

            "support": support,

            "support_tests": support_tests,

            "volume_today": volume_today,

            "volume_20": volume_20,

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

            "half_candle": half_candle,

            "catalysts": catalysts,

            "signals": signals,

            "warnings": warnings,

            "core_conditions": core_conditions
        }

    except Exception as e:

        print(
            f"❌ خطأ في تحليل {ticker}: {e}"
        )

        return None


# ============================================================
# تشغيل Scanner
# ============================================================

print("\n")
print("=" * 65)

print(
    "🎯 REVERSE SPLIT STRATEGY SCANNER"
)

print("=" * 65)

print(
    "🎯 الهدف: سهم هادئ بعد Reverse Split "
    "وقريب من دعم مع تحسن تدريجي"
)

print(
    f"📅 الفترة: {MIN_DAYS} إلى {MAX_DAYS} يوم"
)

print(
    f"📋 عدد المرشحين: {len(TICKERS)}"
)

print("=" * 65)


results = []


if not TICKERS:

    print(
        "❌ لا توجد أسهم للفحص"
    )

else:

    for ticker in TICKERS:

        print(
            f"\n🔎 تحليل الاستراتيجية: {ticker}"
        )

        result = analyze_stock(
            ticker
        )

        if result is None:

            print(
                "⚪ لا توجد بيانات كافية "
                "أو خارج فترة الرادار"
            )

            continue

        results.append(result)

        # ----------------------------------------------------
        # البيانات
        # ----------------------------------------------------

        print("\n📊 بيانات السهم")
        print("-" * 65)

        print(
            f"💰 السعر الحالي: "
            f"${result['price']:.4f}"
        )

        print(
            f"📅 Reverse Split: "
            f"{result['split_date']}"
        )

        print(
            f"📌 نسبة التقسيم: "
            f"{reverse_ratio_text(result['split_ratio'])}"
        )

        print(
            f"⏱️ الأيام منذ التقسيم: "
            f"{result['days_since_split']}"
        )

        if result["post_split_change"] is not None:

            print(
                f"📈 الحركة منذ التقسيم: "
                f"{result['post_split_change']:.1f}%"
            )

        print(
            f"📉 الهبوط من أعلى سعر: "
            f"{result['drawdown']:.1f}%"
        )

        if result["support"] is not None:

            print(
                f"🟢 الدعم: "
                f"${result['support']:.4f}"
            )

        else:

            print(
                "🟢 الدعم: غير محدد"
            )

        print(
            f"🔄 اختبارات الدعم: "
            f"{result['support_tests']}"
        )

        print(
            f"📊 Volume اليوم: "
            f"{result['volume_today']:,.0f}"
        )

        if result["volume_20"] is not None:

            print(
                f"📊 متوسط Volume 20: "
                f"{result['volume_20']:,.0f}"
            )

        else:

            print(
                "📊 متوسط Volume 20: N/A"
            )

        if result["volume_ratio"] is not None:

            print(
                f"📊 Volume Ratio: "
                f"{result['volume_ratio']:.2f}x"
            )

        if result["rsi"] is not None:

            print(
                f"📉 RSI: "
                f"{result['rsi']:.1f}"
            )

        else:

            print(
                "📉 RSI: N/A"
            )

        if result["previous_rsi"] is not None:

            print(
                f"📈 RSI السابق: "
                f"{result['previous_rsi']:.1f}"
            )

        if result["macd"] is not None:

            print(
                f"📉 MACD: "
                f"{result['macd']:.5f}"
            )

        else:

            print(
                "📉 MACD: N/A"
            )

        if result["ma20"] is not None:

            print(
                f"📊 MA20: "
                f"${result['ma20']:.4f}"
            )

        else:

            print(
                "📊 MA20: N/A"
            )

        if result["ma50"] is not None:

            print(
                f"📊 MA50: "
                f"${result['ma50']:.4f}"
            )

        else:

            print(
                "📊 MA50: N/A"
            )

        print(
            f"📐 Core Conditions: "
            f"{result['core_conditions']}"
        )

        # ----------------------------------------------------
        # نصف الشمعة
        # ----------------------------------------------------

        print(
            "\n🕯️ شرط نصف شمعة الانطلاقة"
        )

        if (
            result["half_candle"]["initial_run"]
            is not None
        ):

            print(
                f"📈 الانطلاقة الأولى: "
                f"{result['half_candle']['initial_run']:.1f}%"
            )

        if (
            result["half_candle"]["half_level"]
            is not None
        ):

            print(
                f"🎯 مستوى النصف: "
                f"${result['half_candle']['half_level']:.4f}"
            )

        if (
            result["half_candle"]["lowest_after_run"]
            is not None
        ):

            print(
                f"📉 أقل سعر بعد الانطلاقة: "
                f"${result['half_candle']['lowest_after_run']:.4f}"
            )

        if result["half_candle"]["passed"]:

            print("🟢 PASS")

        else:

            print("🔴 FAIL")

        # ----------------------------------------------------
        # الإشارات
        # ----------------------------------------------------

        print(
            "\n🔍 إشارات التحليل"
        )

        print("-" * 65)

        for signal in result["signals"]:

            print(signal)

        for warning in result["warnings"]:

            print(warning)

        print(
            "\n🚦 التقييم النهائي:"
        )

        print(
            result["rating"]
        )

        print(
            f"🎯 SCORE: "
            f"{result['score']}"
        )


# ============================================================
# ترتيب النتائج
# ============================================================

def result_sort_key(x):

    rating = x.get(
        "rating",
        ""
    )

    rsi = x.get(
        "rsi"
    )

    return (

        rating.startswith(
            "🔥🔥🔥"
        ),

        rating.startswith(
            "🔥🔥"
        ),

        rsi is not None
        and rsi < 30,

        x.get(
            "rsi_improving",
            False
        ),

        x.get(
            "half_candle",
            {}
        ).get(
            "passed",
            False
        ),

        x.get(
            "core_conditions",
            0
        ),

        x.get(
            "score",
            0
        )
    )


results = sorted(
    results,
    key=result_sort_key,
    reverse=True
)


# ============================================================
# أفضل الأسهم
# ============================================================

print("\n")
print("=" * 65)

print(
    "🏆 أفضل الأسهم المطابقة للاستراتيجية"
)

print("=" * 65)


strong_matches = [

    r for r in results

    if r["rating"]
    == "🔥🔥🔥 MATCH قوي جداً"

]


strong_watchlist = [

    r for r in results

    if r["rating"]
    == "🔥🔥 WATCHLIST قوية"

]


# ============================================================
# MATCH
# ============================================================

if strong_matches:

    print(
        "\n🔥🔥🔥 MATCH قوي جداً"
    )

    for i, r in enumerate(
        strong_matches[:7],
        1
    ):

        support_text = (
            f"${r['support']:.4f}"
            if r["support"] is not None
            else "N/A"
        )

        rsi_text = (
            f"{r['rsi']:.1f}"
            if r["rsi"] is not None
            else "N/A"
        )

        print(
            f"{i}. {r['ticker']} | "
            f"Score: {r['score']} | "
            f"RSI: {rsi_text} | "
            f"Volume: {r['volume_today']:,.0f} | "
            f"Support: {support_text} | "
            f"Tests: {r['support_tests']} | "
            f"{r['rating']}"
        )


# ============================================================
# WATCHLIST
# ============================================================

if strong_watchlist:

    print(
        "\n🔥🔥 WATCHLIST قوية"
    )

    for i, r in enumerate(
        strong_watchlist[:10],
        1
    ):

        support_text = (
            f"${r['support']:.4f}"
            if r["support"] is not None
            else "N/A"
        )

        rsi_text = (
            f"{r['rsi']:.1f}"
            if r["rsi"] is not None
            else "N/A"
        )

        print(
            f"{i}. {r['ticker']} | "
            f"Score: {r['score']} | "
            f"RSI: {rsi_text} | "
            f"Volume: {r['volume_today']:,.0f} | "
            f"Support: {support_text} | "
            f"Tests: {r['support_tests']} | "
            f"{r['rating']}"
        )


# ============================================================
# لا توجد نتائج قوية
# ============================================================

if (
    not strong_matches
    and not strong_watchlist
):

    print(
        "⚠️ لا يوجد حالياً سهم يحقق "
        "الشروط القوية بالكامل."
    )

    print(
        "هذا طبيعي؛ الرادار سيستمر "
        "في المتابعة اليومية."
    )


# ============================================================
# المحفزات القادمة
# ============================================================

print("\n")
print("=" * 65)

print(
    "🚀 المحفزات المستقبلية"
)

print("=" * 65)


found_catalyst = False


for r in results:

    if r["catalysts"]:

        found_catalyst = True

        print(
            f"\n🚀 {r['ticker']}"
        )

        for catalyst in r["catalysts"]:

            print(
                f"   {catalyst}"
            )


if not found_catalyst:

    print(
        "⚪ لم يتم العثور على محفز مستقبلي "
        "واضح من البيانات المتاحة."
    )


# ============================================================
# ملاحظة مهمة
# ============================================================

print("\n")
print("=" * 65)

print(
    "ℹ️ ملاحظة"
)

print("=" * 65)

print(
    "السهم الذي يتدهور لا يتم حذفه تلقائياً."
)

print(
    "قد يبقى في نتائج المراقبة لأن الضغط "
    "قد يكون تجميعاً أو تخويفاً للمضاربين."
)

print(
    "لكن لا يتم اعتباره MATCH قوي إلا بعد "
    "تحقق الشروط الأساسية."
)

print("\n")
print("=" * 65)

print(
    "✅ انتهى Strategy Scanner"
)

print("=" * 65)
