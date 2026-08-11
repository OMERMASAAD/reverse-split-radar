import yfinance as yf
import pandas as pd
import numpy as np
import json
from datetime import datetime, timedelta

# ============================================================
# REVERSE SPLIT RADAR - FINAL V2
# ============================================================

CANDIDATES_FILE = "reverse_split_candidates.json"

# فترة مراقبة Reverse Split
MIN_DAYS = 20
MAX_DAYS = 50
MIN_HISTORY_DAYS = 60

# ------------------------------------------------------------
# شروط الاستراتيجية
# ------------------------------------------------------------

MAX_SHORT = 50000

# أقصى حركة مقبولة من افتتاح يوم التقسيم
MAX_POST_SPLIT_MOVE = 0.50

# أقصى انطلاقة أولى نعتبرها هادئة
MAX_INITIAL_RUN = 0.20

# Volume
QUIET_VOLUME_RATIO = 1.50

# قرب السعر من الدعم
SUPPORT_DISTANCE_MAX = 0.20

# أقل عدد لاختبارات الدعم
MIN_SUPPORT_TESTS = 2

# ------------------------------------------------------------
# إعدادات الانطلاقة
# ------------------------------------------------------------

# عدد الجلسات التي نبحث فيها عن الانطلاقة الأولى
IMPULSE_LOOKBACK_DAYS = 10

# أقل ارتفاع نعتبره انطلاقة حقيقية
MIN_IMPULSE_RUN = 0.10

# هامش السماح للوصول إلى نصف الانطلاقة
HALF_LEVEL_TOLERANCE = 0.03


# ============================================================
# تحميل المرشحين
# ============================================================

try:

    with open(
        CANDIDATES_FILE,
        "r",
        encoding="utf-8"
    ) as f:

        candidates = json.load(f)

    TICKERS = [
        str(item["symbol"]).upper()
        for item in candidates
        if isinstance(item, dict)
        and "symbol" in item
    ]

except Exception as e:

    print(f"ERROR loading candidates: {e}")

    TICKERS = []


# ============================================================
# أدوات عامة
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


def fmt_price(value):

    value = safe_float(value)

    if value is None:
        return "N/A"

    return f"${value:.4f}"


def fmt_num(value):

    value = safe_float(value)

    if value is None:
        return "N/A"

    return f"{value:,.0f}"


def fmt_pct(value):

    value = safe_float(value)

    if value is None:
        return "N/A"

    return f"{value:.1f}%"


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

    rsi = 100 - (
        100 / (1 + rs)
    )

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

            # Yahoo:
            # 1.0 = no split
            # 0.3333 = 3:1 reverse split
            if ratio >= 1:
                continue

            split_date = pd.Timestamp(
                date
            ).date()

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
# Reverse Split text
# ============================================================

def reverse_ratio_text(ratio):

    ratio = safe_float(ratio)

    if ratio is None or ratio <= 0:
        return "Unknown"

    reverse_number = round(1 / ratio)

    return (
        f"{reverse_number}:1 Reverse split"
    )


# ============================================================
# الدعم
# ============================================================

def calculate_support(df):

    if len(df) < 10:
        return None

    recent = df.tail(20)

    lows = recent[
        "Low"
    ].dropna().values

    if len(lows) == 0:
        return None

    return float(
        np.percentile(
            lows,
            15
        )
    )


# ============================================================
# اختبارات الدعم
# ============================================================

def count_support_tests(
    df,
    support
):

    if support is None:
        return 0

    tolerance = support * 0.04

    tests = 0

    for low in (
        df["Low"]
        .tail(40)
        .dropna()
    ):

        if abs(
            float(low) - support
        ) <= tolerance:

            tests += 1

    return tests


# ============================================================
# اكتشاف الانطلاقة الأولى
# ============================================================

def detect_initial_impulse(
    df,
    split_date
):

    result = {

        "found": False,

        "initial_open": None,

        "initial_high": None,

        "initial_low": None,

        "initial_run": None,

        "half_level": None,

        "lowest_after_impulse": None,

        "days_to_high": None,

        "pullback_pct": None,

        "passed": False,

        "reason": ""

    }

    try:

        data = df[
            df.index.date >= split_date
        ].copy()

        if len(data) < 5:

            result["reason"] = (
                "بيانات غير كافية بعد التقسيم"
            )

            return result

        # ----------------------------------------------------
        # افتتاح يوم التقسيم
        # ----------------------------------------------------

        first_open = safe_float(
            data.iloc[0]["Open"]
        )

        if (
            first_open is None
            or first_open <= 0
        ):

            result["reason"] = (
                "تعذر تحديد افتتاح الانطلاقة"
            )

            return result

        # ----------------------------------------------------
        # البحث عن أول قمة مهمة
        # ----------------------------------------------------

        search_data = data.head(
            IMPULSE_LOOKBACK_DAYS
        )

        highest_idx = (
            search_data["High"].idxmax()
        )

        highest_pos = (
            search_data.index.get_loc(
                highest_idx
            )
        )

        initial_high = safe_float(
            search_data.loc[
                highest_idx,
                "High"
            ]
        )

        if (
            initial_high is None
            or initial_high <= first_open
        ):

            result["reason"] = (
                "لم يتم العثور على انطلاقة"
            )

            return result

        initial_run = (
            (
                initial_high
                - first_open
            )
            / first_open
        )

        result["initial_open"] = first_open

        result["initial_high"] = initial_high

        result["initial_run"] = (
            initial_run * 100
        )

        result["days_to_high"] = (
            highest_pos + 1
        )

        # ----------------------------------------------------
        # أقل ارتفاع للانطلاقة
        # ----------------------------------------------------

        if initial_run < MIN_IMPULSE_RUN:

            result["reason"] = (
                f"الانطلاقة ضعيفة "
                f"({initial_run * 100:.1f}%)"
            )

            return result

        result["found"] = True

        # ----------------------------------------------------
        # نصف منطقة الانطلاقة
        # ----------------------------------------------------

        half_level = (
            first_open
            + (
                (
                    initial_high
                    - first_open
                )
                * 0.50
            )
        )

        result["half_level"] = half_level

        # ----------------------------------------------------
        # أدنى سعر بعد القمة
        # ----------------------------------------------------

        after_high = data.iloc[
            highest_pos + 1:
        ]

        if after_high.empty:

            result["reason"] = (
                "الانطلاقة حدثت حديثاً "
                "ولم يحدث Pullback بعد"
            )

            return result

        lowest_after = safe_float(
            after_high["Low"].min()
        )

        result[
            "lowest_after_impulse"
        ] = lowest_after

        # ----------------------------------------------------
        # هل وصل لنصف الانطلاقة؟
        # ----------------------------------------------------

        if lowest_after is not None:

            pullback_pct = (
                (
                    initial_high
                    - lowest_after
                )
                / (
                    initial_high
                    - first_open
                )
            ) * 100

            result[
                "pullback_pct"
            ] = pullback_pct

        # السماح بأن يكون قريباً جداً من المستوى
        tolerance = (
            half_level
            * HALF_LEVEL_TOLERANCE
        )

        if (
            lowest_after is not None
            and lowest_after
            <= half_level + tolerance
        ):

            result["passed"] = True

            result["reason"] = (
                "وصل إلى نصف منطقة الانطلاقة"
            )

        else:

            result["reason"] = (
                "لم يصل إلى نصف منطقة الانطلاقة"
            )

        return result

    except Exception as e:

        result["reason"] = (
            f"خطأ في الانطلاقة: {e}"
        )

        return result


# ============================================================
# المحفزات
# ============================================================

def check_future_catalyst(stock):

    catalysts = []

    # --------------------------------------------------------
    # Calendar
    # --------------------------------------------------------

    try:

        calendar = stock.calendar

        if isinstance(
            calendar,
            dict
        ):

            earnings = calendar.get(
                "Earnings Date"
            )

            if earnings is not None:

                catalysts.append(
                    "موعد نتائج مالية"
                )

        elif isinstance(
            calendar,
            pd.DataFrame
        ):

            if (
                not calendar.empty
                and "Earnings Date"
                in calendar.index
            ):

                catalysts.append(
                    "موعد نتائج مالية"
                )

    except Exception:

        pass

    # --------------------------------------------------------
    # Earnings Dates
    # --------------------------------------------------------

    try:

        earnings = (
            stock.get_earnings_dates(
                limit=4
            )
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

                    clean_date = (
                        pd.Timestamp(date)
                    )

                    if (
                        clean_date.tzinfo
                        is not None
                    ):

                        clean_date = (
                            clean_date
                            .tz_localize(None)
                        )

                    if clean_date >= now:

                        catalysts.append(
                            "نتائج مالية قادمة"
                        )

                        break

                except Exception:

                    continue

    except Exception:

        pass

    return list(
        dict.fromkeys(
            catalysts
        )
    )


# ============================================================
# تحليل سهم
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
        # التاريخ
        # ----------------------------------------------------

        start_date = (
            split_date
            - timedelta(days=120)
        )

        df = stock.history(

            start=start_date,

            end=(
                today
                + timedelta(days=1)
            ),

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

        macd_hist = safe_float(
            latest["MACD_HIST"]
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

            and rsi < previous_rsi
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
        # بيانات Reverse Split
        # ----------------------------------------------------

        split_data = df[
            df.index.date >= split_date
        ].copy()

        if split_data.empty:
            return None

        split_open = safe_float(
            split_data.iloc[0]["Open"]
        )

        split_high = safe_float(
            split_data["High"].max()
        )

        split_low = safe_float(
            split_data["Low"].min()
        )

        if split_open is None:
            return None

        # ----------------------------------------------------
        # الحركة من افتتاح التقسيم
        # ----------------------------------------------------

        post_split_change = (
            (
                price
                - split_open
            )
            / split_open
        ) * 100

        # ----------------------------------------------------
        # Drawdown
        # ----------------------------------------------------

        drawdown = None

        if (
            split_high is not None
            and split_high > 0
        ):

            drawdown = (
                (
                    price
                    - split_high
                )
                / split_high
            ) * 100

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

        impulse = (
            detect_initial_impulse(
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

        short_ok = (

            short_shares is not None

            and short_shares
            < MAX_SHORT
        )

        # ----------------------------------------------------
        # MA20
        # ----------------------------------------------------

        ma20_ok = (

            ma20 is not None

            and price <= ma20 * 1.10
        )

        # ----------------------------------------------------
        # Catalyst
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
            "Reverse Split حديث"
        )

        # ----------------------------------------------------
        # الانطلاقة
        # ----------------------------------------------------

        if impulse["passed"]:

            score += 3

            signals.append(
                "تحقق شرط نصف الانطلاقة"
            )

        else:

            warnings.append(
                "لم يتحقق شرط نصف الانطلاقة"
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
                        f"RSI منخفض ويتحسن "
                        f"({previous_rsi:.1f} -> "
                        f"{rsi:.1f})"
                    )

                else:

                    signals.append(
                        f"RSI منخفض "
                        f"({rsi:.1f}) "
                        f"لكن لم يبدأ التحسن"
                    )

            elif rsi < 35:

                score += 1

                signals.append(
                    f"RSI قريب من التشبع البيعي "
                    f"({rsi:.1f})"
                )

            else:

                warnings.append(
                    f"RSI مرتفع ({rsi:.1f})"
                )

        # ----------------------------------------------------
        # MACD
        # ----------------------------------------------------

        if macd_improving:

            score += 2

            signals.append(
                "MACD يتحسن"
            )

        else:

            warnings.append(
                "MACD لم يظهر تحسنًا كافيًا"
            )

        # ----------------------------------------------------
        # Volume
        # ----------------------------------------------------

        if quiet_volume:

            score += 2

            signals.append(
                f"Volume هادئ "
                f"({fmt_num(volume_today)})"
            )

        elif volume_ratio is not None:

            signals.append(
                f"Volume نشط "
                f"({fmt_num(volume_today)})"
            )

        # ----------------------------------------------------
        # Support tests
        # ----------------------------------------------------

        if (
            support_tests
            >= MIN_SUPPORT_TESTS
        ):

            score += 2

            signals.append(
                f"اختبار دعم عدة مرات "
                f"({support_tests})"
            )

        elif support_tests == 1:

            score += 1

            signals.append(
                "يوجد اختبار دعم واحد"
            )

        else:

            warnings.append(
                "لا توجد اختبارات دعم كافية"
            )

        # ----------------------------------------------------
        # Near Support
        # ----------------------------------------------------

        if near_support:

            score += 2

            signals.append(
                "السعر قريب من الدعم"
            )

        # ----------------------------------------------------
        # Post Split Movement
        # ----------------------------------------------------

        if (
            post_split_change is not None
            and abs(
                post_split_change
            ) <= MAX_POST_SPLIT_MOVE * 100
        ):

            score += 1

            signals.append(
                f"الحركة من افتتاح التقسيم "
                f"مقبولة "
                f"({post_split_change:.1f}%)"
            )

        elif post_split_change is not None:

            warnings.append(
                f"الحركة من افتتاح التقسيم "
                f"قوية "
                f"({post_split_change:.1f}%)"
            )

        # ----------------------------------------------------
        # Drawdown
        # ----------------------------------------------------

        if drawdown is not None:

            if drawdown <= -30:

                score += 2

                signals.append(
                    f"هبوط قوي من القمة "
                    f"({drawdown:.1f}%)"
                )

            elif drawdown <= -20:

                score += 1

                signals.append(
                    f"تصحيح جيد من القمة "
                    f"({drawdown:.1f}%)"
                )

            else:

                warnings.append(
                    f"التصحيح ضعيف "
                    f"({drawdown:.1f}%)"
                )

        # ----------------------------------------------------
        # Float
        # ----------------------------------------------------

        if (
            float_shares is not None
            and float_shares
            <= 4_000_000
        ):

            score += 1

            signals.append(
                f"Float منخفض "
                f"({fmt_num(float_shares)})"
            )

        elif float_shares is not None:

            warnings.append(
                f"Float مرتفع "
                f"({fmt_num(float_shares)})"
            )

        # ----------------------------------------------------
        # Short
        # ----------------------------------------------------

        if short_ok:

            score += 1

            signals.append(
                f"Short منخفض "
                f"({fmt_num(short_shares)})"
            )

        elif short_shares is not None:

            warnings.append(
                f"Short مرتفع "
                f"({fmt_num(short_shares)})"
            )

        # ----------------------------------------------------
        # MA20
        # ----------------------------------------------------

        if ma20_ok:

            score += 1

            signals.append(
                "السعر قريب من MA20"
            )

        # ----------------------------------------------------
        # Catalyst
        # ----------------------------------------------------

        if catalysts:

            score += 2

            for catalyst in catalysts:

                signals.append(
                    catalyst
                )

        else:

            warnings.append(
                "لا يوجد محفز مستقبلي واضح"
            )

        # ====================================================
        # CORE CONDITIONS
        # ====================================================

        core_conditions = 0

        if impulse["passed"]:
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

        if (
            support_tests
            >= MIN_SUPPORT_TESTS
        ):
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
        # FINAL RATING
        # ====================================================

        if (
            rsi is not None
            and rsi < 30
            and rsi_improving
            and impulse["passed"]
            and core_conditions >= 6
        ):

            rating = (
                "MATCH قوي جداً"
            )

        elif (
            rsi is not None
            and rsi < 35
            and impulse["passed"]
            and core_conditions >= 5
        ):

            rating = (
                "WATCHLIST قوية"
            )

        elif core_conditions >= 4:

            rating = "WATCHLIST"

        else:

            rating = "مراقبة"

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

            "days_since_split":
                days_since_split,

            "split_open":
                split_open,

            "split_high":
                split_high,

            "split_low":
                split_low,

            "post_split_change":
                post_split_change,

            "drawdown":
                drawdown,

            "support":
                support,

            "support_tests":
                support_tests,

            "volume_today":
                volume_today,

            "volume_20":
                volume_20,

            "volume_ratio":
                volume_ratio,

            "rsi":
                rsi,

            "previous_rsi":
                previous_rsi,

            "rsi_improving":
                rsi_improving,

            "macd":
                macd,

            "macd_hist":
                macd_hist,

            "macd_improving":
                macd_improving,

            "ma20":
                ma20,

            "ma50":
                ma50,

            "float_shares":
                float_shares,

            "short_shares":
                short_shares,

            "impulse":
                impulse,

            "catalysts":
                catalysts,

            "signals":
                signals,

            "warnings":
                warnings,

            "core_conditions":
                core_conditions

        }

    except Exception as e:

        print(
            f"ERROR analyzing {ticker}: {e}"
        )

        return None


# ============================================================
# تشغيل Scanner
# ============================================================

print()

print("=" * 70)

print(
    "REVERSE SPLIT RADAR - FINAL V2"
)

print("=" * 70)

print(
    f"الفترة المستهدفة: "
    f"{MIN_DAYS} إلى {MAX_DAYS} يوم"
)

print(
    f"عدد المرشحين: "
    f"{len(TICKERS)}"
)

print("=" * 70)


results = []


if not TICKERS:

    print(
        "لا توجد أسهم في ملف المرشحين."
    )

else:

    for ticker in TICKERS:

        print()

        print(
            f"تحليل: {ticker}"
        )

        result = analyze_stock(
            ticker
        )

        if result is None:

            print(
                "لا توجد بيانات كافية "
                "أو السهم خارج الفترة."
            )

            continue

        results.append(
            result
        )

        print(
            "-" * 70
        )

        print(
            f"السعر الحالي: "
            f"{fmt_price(result['price'])}"
        )

        print(
            f"Reverse Split: "
            f"{result['split_date']}"
        )

        print(
            f"النسبة: "
            f"{reverse_ratio_text(result['split_ratio'])}"
        )

        print(
            f"الأيام منذ التقسيم: "
            f"{result['days_since_split']}"
        )

        print(
            f"افتتاح يوم التقسيم: "
            f"{fmt_price(result['split_open'])}"
        )

        print(
            f"أعلى سعر منذ التقسيم: "
            f"{fmt_price(result['split_high'])}"
        )

        print(
            f"أدنى سعر منذ التقسيم: "
            f"{fmt_price(result['split_low'])}"
        )

        print(
            f"الحركة من افتتاح يوم التقسيم: "
            f"{fmt_pct(result['post_split_change'])}"
        )

        print(
            f"الهبوط من أعلى سعر: "
            f"{fmt_pct(result['drawdown'])}"
        )

        print(
            f"الدعم: "
            f"{fmt_price(result['support'])}"
        )

        print(
            f"اختبارات الدعم: "
            f"{result['support_tests']}"
        )

        print(
            f"Volume اليوم: "
            f"{fmt_num(result['volume_today'])}"
        )

        print(
            f"متوسط Volume 20: "
            f"{fmt_num(result['volume_20'])}"
        )

        print(
            f"Volume Ratio: "
            f"{result['volume_ratio']:.2f}x"
            if result["volume_ratio"]
            is not None
            else "Volume Ratio: N/A"
        )

        print(
            f"RSI: "
            f"{result['rsi']:.1f}"
            if result["rsi"] is not None
            else "RSI: N/A"
        )

        print(
            f"RSI السابق: "
            f"{result['previous_rsi']:.1f}"
            if result["previous_rsi"]
            is not None
            else "RSI السابق: N/A"
        )

        print(
            f"MACD: "
            f"{result['macd']:.5f}"
            if result["macd"] is not None
            else "MACD: N/A"
        )

        print(
            f"MA20: "
            f"{fmt_price(result['ma20'])}"
        )

        print(
            f"MA50: "
            f"{fmt_price(result['ma50'])}"
        )

        print(
            f"Core Conditions: "
            f"{result['core_conditions']}"
        )

        # ====================================================
        # الانطلاقة
        # ====================================================

        imp = result[
            "impulse"
        ]

        print()

        print(
            "شرط نصف الانطلاقة"
        )

        print(
            f"افتتاح الانطلاقة: "
            f"{fmt_price(imp['initial_open'])}"
        )

        print(
            f"قمة الانطلاقة: "
            f"{fmt_price(imp['initial_high'])}"
        )

        print(
            f"الانطلاقة الأولى: "
            f"{fmt_pct(imp['initial_run'])}"
        )

        print(
            f"مستوى نصف الانطلاقة: "
            f"{fmt_price(imp['half_level'])}"
        )

        print(
            f"أدنى سعر بعد الانطلاقة: "
            f"{fmt_price(imp['lowest_after_impulse'])}"
        )

        print(
            f"عدد الأيام حتى القمة: "
            f"{imp['days_to_high']}"
            if imp["days_to_high"]
            is not None
            else "عدد الأيام حتى القمة: N/A"
        )

        print(
            f"نسبة الـ Pullback: "
            f"{fmt_pct(imp['pullback_pct'])}"
        )

        if imp["passed"]:

            print(
                "PASS"
            )

        else:

            print(
                f"FAIL - {imp['reason']}"
            )

        # ====================================================
        # الإشارات
        # ====================================================

        print()

        print(
            "إشارات التحليل"
        )

        print(
            "-" * 70
        )

        for signal in result[
            "signals"
        ]:

            print(
                f"OK: {signal}"
            )

        for warning in result[
            "warnings"
        ]:

            print(
                f"WARN: {warning}"
            )

        print()

        print(
            f"التقييم النهائي: "
            f"{result['rating']}"
        )

        print(
            f"SCORE: "
            f"{result['score']}"
        )


# ============================================================
# ترتيب النتائج
# ============================================================

rating_order = {

    "MATCH قوي جداً": 3,

    "WATCHLIST قوية": 2,

    "WATCHLIST": 1,

    "مراقبة": 0
}


results = sorted(

    results,

    key=lambda x: (

        rating_order.get(
            x["rating"],
            0
