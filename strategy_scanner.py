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
# العثور على سهم هادئ بعد Reverse Split
# قريب من دعم مع تحسن تدريجي.
#
# الشروط المهمة:
# - Reverse Split حديث
# - هبوط/تصحيح معقول
# - قرب من الدعم
# - اختبارات دعم
# - RSI منخفض أو يتحسن
# - MACD يتحسن
# - Volume هادئ
# - Float مناسب
# - Short مناسب
# - محفز مستقبلي إن وجد
# - شرط نصف شمعة الانطلاقة
#
# السهم لا يتم حذفه بسبب التدهور.
# ============================================================


CANDIDATES_FILE = "reverse_split_candidates.json"


# ============================================================
# إعدادات الاستراتيجية
# ============================================================

MIN_DAYS = 20
MAX_DAYS = 50

MIN_HISTORY_DAYS = 20

MAX_SHORT = 50000

# أقصى حركة مطلقة نعتبرها هادئة بعد التقسيم
MAX_POST_SPLIT_MOVE = 0.50

# أقصى ارتفاع أولي في أول 5 جلسات
MAX_INITIAL_RUN = 0.20

# أقصى Volume Ratio للسهم الهادئ
QUIET_VOLUME_RATIO = 1.50

# أقصى مسافة عن الدعم
SUPPORT_DISTANCE_MAX = 0.20

# الحد الأدنى لاختبارات الدعم
MIN_SUPPORT_TESTS = 2


# ============================================================
# قراءة قائمة المرشحين
# ============================================================

try:

    with open(CANDIDATES_FILE, "r", encoding="utf-8") as f:
        candidates = json.load(f)

    TICKERS = [
        item["symbol"]
        for item in candidates
        if "symbol" in item
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

    except:

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

            # Reverse Split يكون عادةً ratio < 1
            if ratio < 1:

                split_date = date.to_pydatetime().date()

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
# تحويل النسبة
# ============================================================

def reverse_ratio_text(ratio):

    try:

        if ratio <= 0:
            return "Unknown"

        reverse_number = round(1 / ratio)

        return f"{reverse_number}:1 Reverse split"

    except:

        return "Reverse split"


# ============================================================
# حساب الدعم
# ============================================================

def calculate_support(df):

    if len(df) < 10:
        return None

    recent = df.tail(20)

    lows = recent["Low"].values

    if len(lows) == 0:
        return None

    support = float(
        np.percentile(lows, 15)
    )

    return support


# ============================================================
# حساب اختبارات الدعم
# ============================================================

def count_support_tests(df, support):

    if support is None:
        return 0

    tolerance = support * 0.04

    tests = 0

    for low in df["Low"].tail(40):

        if abs(
            float(low) - support
        ) <= tolerance:

            tests += 1

    return tests


# ============================================================
# شرط نصف شمعة الانطلاقة
# ============================================================

def check_half_candle_condition(
    df,
    split_date
):

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

        # أول 5 جلسات
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

        # نسبة الانطلاقة
        initial_run = (
            (first_high - first_open)
            / first_open
        )

        result["initial_run"] = (
            initial_run * 100
        )

        # إذا طار أكثر من 20%
        if initial_run > MAX_INITIAL_RUN:

            result["reason"] = (
                f"الانطلاقة الأولى قوية "
                f"({initial_run * 100:.1f}%)"
            )

            return result

        # نصف المسافة
        half_level = (
            first_open
            + (
                (first_high - first_open)
                * 0.50
            )
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
# المحفزات المستقبلية
# ============================================================

def check_future_catalyst(stock):

    catalysts = []

    # --------------------------------------------
    # Earnings Calendar
    # --------------------------------------------

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

            elif isinstance(
                calendar,
                pd.DataFrame
            ):

                if not calendar.empty:

                    if (
                        "Earnings Date"
                        in calendar.index
                    ):

                        catalysts.append(
                            "📅 موعد نتائج مالية"
                        )

    except Exception:

        pass

    # --------------------------------------------
    # Earnings Dates
    # --------------------------------------------

    try:

        earnings = stock.get_earnings_dates(
            limit=4
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
                    ).tz_localize(None)

                    if date_clean >= now:

                        catalysts.append(
                            "📅 نتائج مالية قادمة"
                        )

                        break

                except:

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

        # --------------------------------------------
        # Reverse Split
        # --------------------------------------------

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

        # --------------------------------------------
        # فترة الرادار
        # --------------------------------------------

        if not (
            MIN_DAYS
            <= days_since_split
            <= MAX_DAYS
        ):

            return None

        # --------------------------------------------
        # تحميل البيانات
        # --------------------------------------------

        start_date = (
            split_date
            - timedelta(days=100)
        )

        df = stock.history(
            start=start_date,
            end=today + timedelta(days=1),
            auto_adjust=False
        )

        if (
            df is None
            or df.empty
        ):

            return None

        if len(df) < MIN_HISTORY_DAYS:
            return None

        # --------------------------------------------
        # تنظيف البيانات
        # --------------------------------------------

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

        # --------------------------------------------
        # المؤشرات
        # --------------------------------------------

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

        # --------------------------------------------
        # RSI السابق
        # --------------------------------------------

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

        # --------------------------------------------
        # MACD يتحسن
        # --------------------------------------------

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

        # --------------------------------------------
        # Volume
        # --------------------------------------------

        volume_20 = safe_float(
            df["Volume"]
            .tail(20)
            .mean()
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
            and volume_ratio
            <= QUIET_VOLUME_RATIO
        )

        # --------------------------------------------
        # بيانات التقسيم
        # --------------------------------------------

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

        # --------------------------------------------
        # الحركة منذ التقسيم
        # --------------------------------------------

        post_split_change = None

        if (
            split_open is not None
            and split_open > 0
        ):

            post_split_change = (
                (
                    price
                    - split_open
                )
                / split_open
            ) * 100

        # --------------------------------------------
        # الهبوط من القمة
        # --------------------------------------------

        drawdown = (
            (
                price
                - split_high
            )
            / split_high
        ) * 100

        # --------------------------------------------
        # الدعم
        # --------------------------------------------

        support = calculate_support(df)

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

        # --------------------------------------------
        # نصف الشمعة
        # --------------------------------------------

        half_candle = (
            check_half_candle_condition(
                df,
                split_date
            )
        )

        # --------------------------------------------
        # Float / Short
        # --------------------------------------------

        float_shares = None
        short_shares = None

        try:

            info = stock.info

            float_shares = safe_float(
                info.get(
                    "floatShares"
                )
            )

            short_shares = safe_float(
                info.get(
                    "sharesShort"
                )
            )

        except:

            pass

        short_ok = (
            short_shares is not None
            and short_shares < MAX_SHORT
        )

        # --------------------------------------------
        # MA20
        # --------------------------------------------

        ma20_ok = (
            ma20 is not None
            and price <= ma20 * 1.10
        )

        # --------------------------------------------
        # محفز
        # --------------------------------------------

        catalysts = (
            check_future_catalyst(
                stock
            )
        )

        # ====================================================
        # SCORE
        # ====================================================

        score = 0

        signals = []

        warnings = []

        # --------------------------------------------
        # Reverse Split
        # --------------------------------------------

        score += 2

        signals.append(
            "✅ Reverse Split حديث"
        )

        # --------------------------------------------
        # Half Candle
        # --------------------------------------------

        if half_candle["passed"]:

            score += 3

            signals.append(
                "✅ تحقق شرط نصف شمعة الانطلاقة"
            )

        else:

            warnings.append(
                "⚠️ لم يتحقق شرط نصف شمعة الانطلاقة"
            )

        # --------------------------------------------
        # RSI
        # --------------------------------------------

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

        # --------------------------------------------
        # MACD
        # --------------------------------------------

        if macd_improving:

            score += 2

            signals.append(
                "✅ MACD يتحسن"
            )

        else:

            signals.append(
                "🟡 MACD لم يظهر تحسنًا كافيًا"
            )

        # --------------------------------------------
        # Volume
        # --------------------------------------------

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

        # --------------------------------------------
        # Support Tests
        # --------------------------------------------

        if (
            support_tests
            >= MIN_SUPPORT_TESTS
        ):

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

        # --------------------------------------------
        # Near Support
        # --------------------------------------------

        if near_support:

            score += 2

            signals.append(
                "✅ السعر قريب من الدعم"
            )

        # --------------------------------------------
        # Post Split Movement
        # --------------------------------------------
        #
        # مهم:
        # نستخدم abs() حتى لا نعطي نقطة لسهم
        # تحرك بقوة سواء للأعلى أو للأسفل.
        #
        # مثال:
        # +114.4% -> FAIL
        # -60%    -> FAIL
        # +15%    -> PASS
        # -15%    -> PASS
        # --------------------------------------------

        post_split_quiet = (
            post_split_change is not None
            and abs(post_split_change)
            <= MAX_POST_SPLIT_MOVE * 100
        )

        if post_split_quiet:

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

        # --------------------------------------------
        # Drawdown
        # --------------------------------------------

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

        # --------------------------------------------
        # Float
        # --------------------------------------------

        if (
            float_shares is not None
            and float_shares
            <= 4_000_000
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

        # --------------------------------------------
        # Short
        # --------------------------------------------

        if short_ok:

            score += 1

            signals.append(
                f"✅ Short منخفض "
                f"({short_shares:,.0f})
