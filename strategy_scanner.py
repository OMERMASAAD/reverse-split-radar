import yfinance as yf
import pandas as pd
import numpy as np
import json
from datetime import datetime, timedelta

# ============================================================
# REVERSE SPLIT RADAR - FINAL VERSION
# ============================================================

CANDIDATES_FILE = "reverse_split_candidates.json"

MIN_DAYS = 20
MAX_DAYS = 50
MIN_HISTORY_DAYS = 30

MAX_SHORT = 50000
MAX_FLOAT = 4_000_000

# الحركة من افتتاح يوم الـ Reverse Split
MAX_POST_SPLIT_MOVE = 0.50

# أقصى ارتفاع أولي خلال أول 5 جلسات
MAX_INITIAL_RUN = 0.20

QUIET_VOLUME_RATIO = 1.50
SUPPORT_DISTANCE_MAX = 0.20
MIN_SUPPORT_TESTS = 2


# ============================================================
# قراءة قائمة المرشحين
# ============================================================

try:
    with open(CANDIDATES_FILE, "r", encoding="utf-8") as f:
        candidates = json.load(f)

    TICKERS = [
        str(item["symbol"]).upper()
        for item in candidates
        if isinstance(item, dict) and item.get("symbol")
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


def fmt_num(value):
    value = safe_float(value)

    if value is None:
        return "N/A"

    return f"{value:,.0f}"


def fmt_price(value):
    value = safe_float(value)

    if value is None:
        return "N/A"

    return f"${value:.4f}"


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

            if ratio is None or ratio >= 1:
                continue

            split_date = pd.Timestamp(date).date()

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

    ratio = safe_float(ratio)

    if ratio is None or ratio <= 0:
        return "Unknown"

    return f"{round(1 / ratio)}:1 Reverse split"


# ============================================================
# حساب الدعم
# ============================================================

def calculate_support(df):

    if len(df) < 10:
        return None

    recent = df.tail(20)

    lows = (
        recent["Low"]
        .dropna()
        .astype(float)
        .values
    )

    if len(lows) == 0:
        return None

    return float(
        np.percentile(lows, 15)
    )


# ============================================================
# عدد اختبارات الدعم
# ============================================================

def count_support_tests(df, support):

    if support is None or support <= 0:
        return 0

    tolerance = support * 0.04

    tests = 0

    lows = (
        df["Low"]
        .tail(40)
        .dropna()
    )

    for low in lows:

        if abs(
            float(low) - support
        ) <= tolerance:

            tests += 1

    return tests


# ============================================================
# بيانات يوم التقسيم
# ============================================================

def get_split_price_data(df, split_date):

    result = {

        "split_open": None,
        "split_high": None,
        "split_low": None,
        "split_close": None,

        "post_split_high": None,
        "post_split_low": None,

        "post_split_days": 0

    }

    split_data = df[
        df.index.date >= split_date
    ].copy()

    if split_data.empty:
        return result

    first_day = split_data.iloc[0]

    result["split_open"] = safe_float(
        first_day["Open"]
    )

    result["split_high"] = safe_float(
        first_day["High"]
    )

    result["split_low"] = safe_float(
        first_day["Low"]
    )

    result["split_close"] = safe_float(
        first_day["Close"]
    )

    result["post_split_high"] = safe_float(
        split_data["High"].max()
    )

    result["post_split_low"] = safe_float(
        split_data["Low"].min()
    )

    result["post_split_days"] = len(
        split_data
    )

    return result


# ============================================================
# تحليل الانطلاقة الأولى
# ============================================================

def check_initial_run(df, split_date):

    result = {

        "passed": False,

        "split_open": None,

        "initial_open": None,
        "initial_high": None,
        "initial_low": None,

        "initial_run": None,

        "half_level": None,

        "lowest_after_run": None,

        "reason": ""

    }

    try:

        split_data = df[
            df.index.date >= split_date
        ].copy()

        if len(split_data) < 6:

            result["reason"] = (
                "بيانات أقل من 6 جلسات بعد التقسيم"
            )

            return result

        # افتتاح يوم الـ Reverse Split
        split_open = safe_float(
            split_data.iloc[0]["Open"]
        )

        # أول 5 جلسات
        first_days = split_data.head(5)

        initial_high = safe_float(
            first_days["High"].max()
        )

        initial_low = safe_float(
            first_days["Low"].min()
        )

        if (
            split_open is None
            or initial_high is None
        ):

            result["reason"] = (
                "تعذر تحديد افتتاح أو قمة الانطلاقة"
            )

            return result

        result["split_open"] = split_open

        result["initial_open"] = split_open

        result["initial_high"] = initial_high

        result["initial_low"] = initial_low

        # نسبة الانطلاقة
        initial_run = (
            initial_high - split_open
        ) / split_open

        result["initial_run"] = initial_run

        # منتصف منطقة الانطلاقة
        half_level = (
            split_open
            + (
                (initial_high - split_open)
                * 0.50
            )
        )

        result["half_level"] = half_level

        # البيانات بعد أول 5 جلسات
        after_run = split_data.iloc[5:]

        if after_run.empty:

            result["reason"] = (
                "لا توجد بيانات بعد أول 5 جلسات"
            )

            return result

        lowest_after_run = safe_float(
            after_run["Low"].min()
        )

        result["lowest_after_run"] = (
            lowest_after_run
        )

        # الانطلاقة يجب ألا تكون قوية جداً
        if initial_run > MAX_INITIAL_RUN:

            result["reason"] = (
                f"الانطلاقة الأولى قوية "
                f"({initial_run * 100:.1f}%)"
            )

            return result

        # يجب أن يعود السهم إلى نصف المنطقة
        if (
            lowest_after_run is not None
            and lowest_after_run <= half_level
        ):

            result["passed"] = True

            result["reason"] = (
                "PASS: انطلاقة هادئة + "
                "تصحيح إلى نصف المنطقة"
            )

        else:

            result["reason"] = (
                "FAIL: لم يعد السعر إلى "
                "نصف منطقة الانطلاقة"
            )

        return result

    except Exception as e:

        result["reason"] = (
            f"خطأ: {e}"
        )

        return result


# ============================================================
# المحفزات المستقبلية
# ============================================================

def check_future_catalyst(stock):

    catalysts = []

    # --------------------------------------------------------
    # نتائج مالية قادمة
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

                    if (
                        date_clean.tzinfo
                        is not None
                    ):

                        date_clean = (
                            date_clean.tz_localize(
                                None
                            )
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

    # --------------------------------------------------------
    # Calendar
    # --------------------------------------------------------

    try:

        calendar = stock.calendar

        if calendar is not None:

            if isinstance(
                calendar,
                pd.DataFrame
            ):

                if (
                    not calendar.empty
                    and "Earnings Date"
                    in calendar.index
                ):

                    catalysts.append(
                        "📅 موعد نتائج مالية"
                    )

            elif isinstance(
                calendar,
                dict
            ):

                if calendar.get(
                    "Earnings Date"
                ) is not None:

                    catalysts.append(
                        "📅 موعد نتائج مالية"
                    )

    except Exception:

        pass

    return list(
        dict.fromkeys(catalysts)
    )


# ============================================================
# تحليل السهم
# ============================================================

def analyze_stock(ticker):

    try:

        stock = yf.Ticker(
            ticker
        )

        # ----------------------------------------------------
        # Reverse Split
        # ----------------------------------------------------

        split_info = (
            get_reverse_split_info(
                stock
            )
        )

        if split_info is None:
            return None

        split_date, split_ratio = (
            split_info
        )

        today = datetime.now().date()

        days_since_split = (
            today - split_date
        ).days

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
            - timedelta(days=120)
        )

        df = stock.history(
            start=start_date,
            end=today + timedelta(days=1),
            auto_adjust=False,
            actions=True
        )

        if (
            df is None
            or df.empty
        ):

            return None

        required = [
            "Open",
            "High",
            "Low",
            "Close",
            "Volume"
        ]

        df = df.dropna(
            subset=required
        )

        if len(df) < MIN_HISTORY_DAYS:

            return None

        # ----------------------------------------------------
        # المؤشرات
        # ----------------------------------------------------

        df["RSI"] = (
            calculate_rsi(
                df["Close"]
            )
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

        if price is None:
            return None

        rsi = safe_float(
            latest["RSI"]
        )

        macd = safe_float(
            latest["MACD"]
        )

        macd_hist = safe_float(
            latest["MACD_HIST"]
        )

        ma20 = safe_float(
            latest["MA20"]
        )

        ma50 = safe_float(
            latest["MA50"]
        )

        # ----------------------------------------------------
        # RSI
        # ----------------------------------------------------

        previous_rsi = (
            safe_float(
                df["RSI"].iloc[-2]
            )
            if len(df) >= 2
            else None
        )

        rsi_prev2 = (
            safe_float(
                df["RSI"].iloc[-3]
            )
            if len(df) >= 3
            else None
        )

        rsi_improving = (
            rsi is not None
            and previous_rsi is not None
            and rsi > previous_rsi
        )

        rsi_turning_up = (
            rsi is not None
            and previous_rsi is not None
            and rsi_prev2 is not None
            and rsi > previous_rsi >= rsi_prev2
        )

        # ----------------------------------------------------
        # MACD
        # ----------------------------------------------------

        hist_prev = (
            safe_float(
                df["MACD_HIST"].iloc[-2]
            )
            if len(df) >= 2
            else None
        )

        hist_prev2 = (
            safe_float(
                df["MACD_HIST"].iloc[-3]
            )
            if len(df) >= 3
            else None
        )

        macd_improving = (
            hist_prev is not None
            and hist_prev2 is not None
            and macd_hist is not None
            and macd_hist > hist_prev > hist_prev2
        )

        # ----------------------------------------------------
        # Volume
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # بيانات التقسيم
        # ----------------------------------------------------

        split_prices = (
            get_split_price_data(
                df,
                split_date
            )
        )

        split_open = (
            split_prices["split_open"]
        )

        split_high = (
            split_prices["split_high"]
        )

        split_low = (
            split_prices["split_low"]
        )

        split_close = (
            split_prices["split_close"]
        )

        post_split_high = (
            split_prices["post_split_high"]
        )

        post_split_low = (
            split_prices["post_split_low"]
        )

        if split_open is None:
            return None

        # ----------------------------------------------------
        # الحركة من افتتاح يوم التقسيم
        # ----------------------------------------------------

        post_split_change = (
            price - split_open
        ) / split_open

        # ----------------------------------------------------
        # الهبوط من القمة
        # ----------------------------------------------------

        drawdown = None

        if (
            post_split_high is not None
            and post_split_high > 0
        ):

            drawdown = (
                price
                - post_split_high
            ) / post_split_high

        # ----------------------------------------------------
        # التعافي من القاع
        # ----------------------------------------------------

        recovery_from_low = None

        if (
            post_split_low is not None
            and post_split_low > 0
        ):

            recovery_from_low = (
                price
                - post_split_low
            ) / post_split_low

        # ----------------------------------------------------
        # الدعم
        # ----------------------------------------------------

        support = calculate_support(
            df
        )

        support_tests = (
            count_support_tests(
                df,
                support
            )
        )

        support_distance = None

        if (
            support is not None
            and support > 0
        ):

            support_distance = (
                price - support
            ) / support

        near_support = (
            support_distance is not None
            and 0 <= support_distance
            <= SUPPORT_DISTANCE_MAX
        )

        # ----------------------------------------------------
        # الانطلاقة
        # ----------------------------------------------------

        initial_run = (
            check_initial_run(
                df,
                split_date
            )
        )

        # ----------------------------------------------------
        # Float / Short
        # ----------------------------------------------------

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

        except Exception:

            pass

        float_ok = (
            float_shares is not None
            and float_shares
            <= MAX_FLOAT
        )

        short_ok = (
            short_shares is not None
            and short_shares
            <= MAX_SHORT
        )

        # ----------------------------------------------------
        # MA20
        # ----------------------------------------------------

        ma20_ok = (
            ma20 is not None
            and price <= ma20 * 1.10
        )

        # ----------------------------------------------------
        # Catalysts
        # ----------------------------------------------------

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

        # Reverse Split
        score += 2

        signals.append(
            "✅ Reverse Split حديث"
        )

        # افتتاح التقسيم
        signals.append(
            "📌 افتتاح يوم Reverse Split: "
            + fmt_price(split_open)
        )

        # ----------------------------------------------------
        # الانطلاقة
        # ----------------------------------------------------

        if initial_run["passed"]:

            score += 3

            signals.append(
                "✅ انطلاقة هادئة + تصحيح ناجح"
            )

        else:

            warnings.append(
                "⚠️ شرط الانطلاقة: "
                + initial_run["reason"]
            )

        # ----------------------------------------------------
        # RSI
        # ----------------------------------------------------

        if rsi is not None:

            if rsi < 30:

                score += 3

                if rsi_turning_up:

                    score += 2

                    signals.append(
                        "✅ RSI منخفض ويتحسن بوضوح "
                        f"({rsi_prev2:.1f} → "
                        f"{previous_rsi:.1f} → "
                        f"{rsi:.1f})"
                    )

                elif rsi_improving:

                    score += 1

                    signals.append(
                        "🟡 RSI منخفض ويبدأ التحسن "
                        f"({previous_rsi:.1f} → "
                        f"{rsi:.1f})"
                    )

                else:

                    signals.append(
                        f"🟡 RSI منخفض لكن بدون تحسن "
                        f"({rsi:.1f})"
                    )

            elif rsi < 35:

                score += 1

                signals.append(
                    f"🟡 RSI قريب من التشبع البيعي "
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
                "✅ MACD Histogram يتحسن "
                "لثلاث جلسات"
            )

        else:

            signals.append(
                "🟡 MACD لم يظهر تحسنًا "
                "متتاليًا كافيًا"
            )

        # ----------------------------------------------------
        # Volume
        # ----------------------------------------------------

        if quiet_volume:

            score += 2

            signals.append(
                f"✅ Volume هادئ "
                f"({fmt_num(volume_today)})"
            )

        elif volume_ratio is not None:

            signals.append(
                f"🟡 Volume Ratio مرتفع نسبيًا "
                f"({volume_ratio:.2f}x)"
            )

        # ----------------------------------------------------
        # Support
        # ----------------------------------------------------

        if support_tests >= MIN_SUPPORT_TESTS:

            score += 2

            signals.append(
                f"✅ اختبارات دعم متعددة "
                f"({support_tests})"
            )

        elif support_tests == 1:

            score += 1

            signals.append(
                "🟡 اختبار دعم واحد"
            )

        else:

            warnings.append(
                "⚠️ لا توجد اختبارات دعم كافية"
            )

        # قرب الدعم
        if near_support:

            score += 2

            signals.append(
                "✅ السعر قريب من الدعم "
                + fmt_price(support)
            )

        # ----------------------------------------------------
        # الحركة من افتتاح التقسيم
        # ----------------------------------------------------

        if (
            abs(post_split_change)
            <= MAX_POST_SPLIT_MOVE
        ):

            score += 1

            signals.append(
                "✅ الحركة من افتتاح التقسيم "
                f"مقبولة "
                f"({post_split_change * 100:.1f}%)"
            )

        else:

            warnings.append(
                "⚠️ الحركة من افتتاح التقسيم "
                f"قوية "
                f"({post_split_change * 100:.1f}%)"
            )

        # ----------------------------------------------------
        # Drawdown
        # ----------------------------------------------------

        if drawdown is not None:

            if drawdown <= -0.30:

                score += 2

                signals.append(
                    "✅ هبوط قوي من القمة "
                    f"({drawdown * 100:.1f}%)"
                )

            elif drawdown <= -0.20:

                score += 1

                signals.append(
                    "🟡 تصحيح جيد "
                    f"({drawdown * 100:.1f}%)"
                )

            else:

                warnings.append(
                    "⚠️ التصحيح ضعيف "
                    f"({drawdown * 100:.1f}%)"
                )

        # ----------------------------------------------------
        # Float
        # ----------------------------------------------------

        if float_ok:

            score += 1

            signals.append(
                "✅ Float منخفض "
                f"({fmt_num(float_shares)})"
            )

        elif float_shares is not None:

            warnings.append(
                "⚠️ Float مرتفع "
                f"({fmt_num(float_shares)})"
            )

        # ----------------------------------------------------
        # Short
        # ----------------------------------------------------

        if short_ok:

            score += 1

            signals.append(
                "✅ Short منخفض "
                f"({fmt_num(short_shares)})"
            )

        elif short_shares is not None:

            warnings.append(
                "⚠️ Short مرتفع "
                f"({fmt_num(short_shares)})"
            )

        # ----------------------------------------------------
        # MA20
        # ----------------------------------------------------

        if ma20_ok:

            score += 1

            signals.append(
                "✅ السعر قريب من MA20"
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

        # ====================================================
        # CORE CONDITIONS
        # ====================================================

        core_conditions = 0

        if initial_run["passed"]:
            core_conditions += 1

        if (
            rsi is not None
            and rsi < 30
        ):
            core_conditions += 1

        if rsi_turning_up:
            core_conditions += 1

        elif rsi_improving:
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

        if abs(post_split_change) <= 0.20:
            core_conditions += 1

        if (
            drawdown is not None
            and drawdown <= -0.20
        ):
            core_conditions += 1

        # ====================================================
        # FINAL RATING
        # ====================================================

        if (
            rsi is not None
            and rsi < 30
            and rsi_turning_up
            and initial_run["passed"]
            and support_tests >= MIN_SUPPORT_TESTS
            and core_conditions >= 7
        ):

            rating = (
                "🔥🔥🔥 MATCH قوي جداً"
            )

        elif (
            rsi is not None
            and rsi < 35
            and initial_run["passed"]
            and support_tests >= MIN_SUPPORT_TESTS
            and core_conditions >= 6
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

            "days_since_split": (
                days_since_split
            ),

            "split_open": split_open,

            "split_high": split_high,

            "split_low": split_low,

            "split_close": split_close,

            "post_split_high": (
                post_split_high
            ),

            "post_split_low": (
                post_split_low
            ),

            "post_split_change": (
                post_split_change
            ),

            "drawdown": drawdown,

            "recovery_from_low": (
                recovery_from_low
            ),

            "support": support,

            "support_tests": (
                support_tests
            ),

            "volume_today": (
                volume_today
            ),

            "volume_20": (
                volume_20
            ),

            "volume_ratio": (
                volume_ratio
            ),

            "rsi": rsi,

            "previous_rsi": (
                previous_rsi
            ),

            "rsi_prev2": (
                rsi_prev2
            ),

            "rsi_improving": (
                rsi_improving
            ),

            "rsi_turning_up": (
                rsi_turning_up
            ),

            "macd": macd,

            "macd_hist": (
                macd_hist
            ),

            "macd_improving": (
                macd_improving
            ),

            "ma20": ma20,

            "ma50": ma50,

            "float_shares": (
                float_shares
            ),

            "short_shares": (
                short_shares
            ),

            "initial_run": (
                initial_run
            ),

            "catalysts": (
                catalysts
            ),

            "signals": (
                signals
            ),

            "warnings": (
                warnings
            ),

            "core_conditions": (
                core_conditions
            )
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

print("=" * 75)

print(
    "🎯 REVERSE SPLIT STRATEGY SCANNER - FINAL"
)

print("=" * 75)

print(
    "🎯 الهدف: اكتشاف سهم هادئ بعد Reverse Split "
    "مع تصحيح + دعم + RSI/MACD يتحسنان"
)

print(
    f"📅 الرادار: "
    f"{MIN_DAYS} إلى {MAX_DAYS} يوم بعد التقسيم"
)

print(
    f"📋 عدد المرشحين: "
    f"{len(TICKERS)}"
)

print("=" * 75)


results = []


if not TICKERS:

    print(
        "❌ لا توجد أسهم في "
        "reverse_split_candidates.json"
    )

else:

    for ticker in TICKERS:

        print(
            f"\n🔎 تحليل الاستراتيجية: "
            f"{ticker}"
        )

        result = analyze_stock(
            ticker
        )

        if result is None:

            print(
                "⚪ خارج فترة الرادار "
                "أو لا توجد بيانات كافية"
            )

            continue

        results.append(
            result
        )

        print("\n📊 بيانات السهم")

        print("-" * 75)

        print(
            f"💰 السعر الحالي: "
            f"{fmt_price(result['price'])}"
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

        print(
            f"💵 افتتاح يوم التقسيم: "
            f"{fmt_price(result['split_open'])}"
        )

        print(
            f"📈 أعلى سعر منذ التقسيم: "
            f"{fmt_price(result['post_split_high'])}"
        )

        print(
            f"📉 أدنى سعر منذ التقسيم: "
            f"{fmt_price(result['post_split_low'])}"
        )

        print(
            f"📊 الحركة من افتتاح يوم التقسيم: "
            f"{result['post_split_change'] * 100:.1f}%"
        )

        if result["drawdown"] is not None:

            print(
                f"📉 الهبوط من أعلى سعر: "
                f"{result['drawdown'] * 100:.1f}%"
            )

        if result["recovery_from_low"] is not None:

            print(
                f"🔄 التعافي من أدنى سعر: "
                f"{result['recovery_from_low'] * 100:.1f}%"
            )

        print(
            f"🟢 الدعم: "
            f"{fmt_price(result['support'])}"
        )

        print(
            f"🔄 اختبارات الدعم: "
            f"{result['support_tests']}"
        )

        print(
            f"📊 Volume اليوم: "
            f"{fmt_num(result['volume_today'])}"
        )

        print(
            f"📊 متوسط Volume 20: "
            f"{fmt_num(result['volume_20'])}"
        )

        if result["volume_ratio"] is not None:

            print(
                f"📊 Volume Ratio: "
                f"{result['volume_ratio']:.2f}x"
            )

        print(
            f"📉 RSI: "
            f"{result['rsi']:.1f}"
            if result["rsi"] is not None
            else "📉 RSI: N/A"
        )

        if result["previous_rsi"] is not None:

            print(
                f"📈 RSI السابق: "
                f"{result['previous_rsi']:.1f}"
            )

        if result["rsi_prev2"] is not None:

            print(
                f"📈 RSI قبل السابق: "
                f"{result['rsi_prev2']:.1f}"
            )

        print(
            f"📉 MACD: "
            f"{result['macd']:.5f}"
            if result["macd"] is not None
            else "📉 MACD: N/A"
        )

        print(
            f"📊 MA20: "
            f"{fmt_price(result['ma20'])}"
        )

        print(
            f"📊 MA50: "
            f"{fmt_price(result['ma50'])}"
        )

        print(
            f"📐 Core Conditions: "
            f"{result['core_conditions']}"
        )

        # ----------------------------------------------------
        # تحليل الانطلاقة
        # ----------------------------------------------------

        hc = result["initial_run"]

        print(
            "\n🕯️ تحليل انطلاقة Reverse Split"
        )

        print(
            f"💵 افتتاح الانطلاقة: "
            f"{fmt_price(hc['split_open'])}"
        )

        print(
            f"📈 قمة أول 5 جلسات: "
            f"{fmt_price(hc['initial_high'])}"
        )

        if hc["initial_run"] is not None:

            print(
                f"📈 الانطلاقة الأولى: "
                f"{hc['initial_run'] * 100:.1f}%"
            )

        print(
            f"🎯 مستوى نصف الانطلاقة: "
            f"{fmt_price(hc['half_level'])}"
        )

        print(
            f"📉 أقل سعر بعد الانطلاقة: "
            f"{fmt_price(hc['lowest_after_run'])}"
        )

        print(
            "🟢 PASS"
            if hc["passed"]
            else "🔴 FAIL"
        )

        # ----------------------------------------------------
        # إشارات
        # ----------------------------------------------------

        print(
            "\n🔍 إشارات التحليل"
        )

        print("-" * 75)

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

def ranking_key(r):

    rating_rank = {

        "🔥🔥🔥 MATCH قوي جداً": 4,

        "🔥🔥 WATCHLIST قوية": 3,

        "🟢 WATCHLIST": 2,

        "🟡 مراقبة": 1

    }

    return (

        rating_rank.get(
            r["rating"],
            0
        ),

        r["core_conditions"],

        r["score"],

        r["rsi_turning_up"],

        r["initial_run"]["passed"],

        r["support_tests"]

    )


results = sorted(

    results,

    key=ranking_key,

    reverse=True

)


# ============================================================
# أفضل الأسهم
# ============================================================

print("\n")

print("=" * 75)

print(
    "🏆 أفضل الأسهم المطابقة للاستراتيجية"
)

print("=" * 75)


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


watchlist = [

    r for r in results

    if r["rating"]
    == "🟢 WATCHLIST"

]


if strong_matches:

    print(
        "\n🔥🔥🔥 MATCH قوي جداً"
    )

    for i, r in enumerate(
        strong_matches[:7],
        1
    ):

        print(

            f"{i}. {r['ticker']} | "

            f"Score: {r['score']} | "

            f"RSI: {r['rsi']:.1f} | "

            f"Open: {fmt_price(r['split_open'])} | "

            f"Now: {fmt_price(r['price'])} | "

            f"Support: {fmt_price(r['support'])} | "

            f"Tests: {r['support_tests']} | "

            f"{r['rating']}"

        )

else:

    print(
        "\n⚪ لا يوجد MATCH قوي جداً حالياً"
    )


if strong_watchlist:

    print(
        "\n🔥🔥 WATCHLIST قوية"
    )

    for i, r in enumerate(
        strong_watchlist[:10],
        1
    ):

        print(

            f"{i}. {r['ticker']} | "

            f"Score: {r['score']} | "

            f"RSI: {r['rsi']:.1f} | "

            f"Open: {fmt_price(r['split_open'])} | "

            f"Now: {fmt_price(r['price'])} | "

            f"Support: {fmt_price(r['support'])} | "

            f"Tests: {r['support_tests']} | "

            f"{r['rating']}"

        )


if watchlist:

    print(
        "\n🟢 WATCHLIST"
    )

    for i, r in enumerate(
        watchlist[:10],
        1
    ):

        rsi_text = (

            f"{r['rsi']:.1f}"

            if r["rsi"]
