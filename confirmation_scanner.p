import yfinance as yf
import pandas as pd
import numpy as np
import json
from datetime import datetime

# ============================================================
# CONFIRMATION SCANNER
# المرحلة الثانية بعد Reverse Split Radar
# ============================================================

CANDIDATES_FILE = "reverse_split_candidates.json"

# ------------------------------------------------------------
# إعدادات الاستراتيجية
# ------------------------------------------------------------

MAX_STOCKS = 15

# منطقة نصف شمعة التقسيم:
# من 50% من الافتتاح إلى ±10%
HALF_ZONE_TOLERANCE = 0.10

# تأكيد الدعم
MIN_SUPPORT_TESTS = 2
SUPPORT_TOLERANCE = 0.05

# Volume
VOLUME_CONFIRM_RATIO = 1.50
VOLUME_STRONG_RATIO = 2.00

# RSI
RSI_MAX_ENTRY = 65

# عدد الشموع المطلوبة
MIN_DATA = 40


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


def price(value):
    value = safe_float(value)

    if value is None:
        return "N/A"

    return f"${value:.4f}"


def number(value):
    value = safe_float(value)

    if value is None:
        return "N/A"

    return f"{value:,.0f}"


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
# قراءة المرشحين
# ============================================================

def load_candidates():

    try:

        with open(
            CANDIDATES_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            data = json.load(f)

        tickers = []

        for item in data:

            if isinstance(item, dict):

                symbol = item.get("symbol")

                if symbol:

                    tickers.append(
                        str(symbol).upper()
                    )

            elif isinstance(item, str):

                tickers.append(
                    item.upper()
                )

        return list(
            dict.fromkeys(tickers)
        )[:MAX_STOCKS]

    except Exception as e:

        print(
            f"ERROR loading candidates: {e}"
        )

        return []


# ============================================================
# حساب الدعم
# ============================================================

def calculate_support(df):

    if len(df) < 20:
        return None

    lows = (
        df["Low"]
        .tail(40)
        .dropna()
    )

    if lows.empty:
        return None

    return float(
        np.percentile(
            lows.values,
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

    tolerance = (
        support *
        SUPPORT_TOLERANCE
    )

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
# منطقة نصف شمعة التقسيم
# ============================================================

def calculate_half_zone(
    split_open
):

    if (
        split_open is None
        or split_open <= 0
    ):

        return None

    half_price = (
        split_open * 0.50
    )

    lower = (
        half_price *
        (1 - HALF_ZONE_TOLERANCE)
    )

    upper = (
        half_price *
        (1 + HALF_ZONE_TOLERANCE)
    )

    return {
        "half": half_price,
        "lower": lower,
        "upper": upper
    }


# ============================================================
# فحص منطقة نصف الشمعة
# ============================================================

def check_half_zone(
    df,
    zone
):

    if zone is None:

        return {
            "touched": False,
            "holding": False,
            "reclaimed": False
        }

    lower = zone["lower"]

    upper = zone["upper"]

    recent = df.tail(20)

    touched = False

    holding = False

    reclaimed = False

    # هل لمس المنطقة؟
    for low in recent["Low"].dropna():

        if (
            lower
            <= float(low)
            <= upper
        ):

            touched = True

            break

    # هل يوجد إغلاق داخل/فوق المنطقة؟
    for close in recent["Close"].dropna():

        if float(close) >= lower:

            holding = True

    # استعادة المنطقة
    last_close = safe_float(
        df["Close"].iloc[-1]
    )

    if (
        last_close is not None
        and last_close >= upper
    ):

        reclaimed = True

    return {
        "touched": touched,
        "holding": holding,
        "reclaimed": reclaimed
    }


# ============================================================
# تحليل السهم
# ============================================================

def analyze_stock(ticker):

    try:

        stock = yf.Ticker(ticker)

        # ----------------------------------------------------
        # بيانات تاريخية
        # ----------------------------------------------------

        df = stock.history(
            period="6mo",
            interval="1d",
            auto_adjust=False
        )

        if (
            df is None
            or df.empty
            or len(df) < MIN_DATA
        ):

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

        previous = df.iloc[-2]

        price_now = safe_float(
            latest["Close"]
        )

        open_now = safe_float(
            latest["Open"]
        )

        high_now = safe_float(
            latest["High"]
        )

        low_now = safe_float(
            latest["Low"]
        )

        volume_now = safe_float(
            latest["Volume"]
        )

        rsi = safe_float(
            latest["RSI"]
        )

        rsi_previous = safe_float(
            previous["RSI"]
        )

        macd_hist = safe_float(
            latest["MACD_HIST"]
        )

        macd_hist_previous = safe_float(
            previous["MACD_HIST"]
        )

        ma20 = safe_float(
            latest["MA20"]
        )

        ma50 = safe_float(
            latest["MA50"]
        )

        if price_now is None:

            return None

        # ----------------------------------------------------
        # Reverse Split
        # ----------------------------------------------------

        split_date = None
        split_ratio = None

        try:

            splits = stock.splits

            if (
                splits is not None
                and not splits.empty
            ):

                for date, ratio in splits.items():

                    ratio = safe_float(
                        ratio
                    )

                    if (
                        ratio is not None
                        and ratio < 1
                    ):

                        split_date = (
                            pd.Timestamp(date)
                            .date()
                        )

                        split_ratio = ratio

        except Exception:

            pass

        # ----------------------------------------------------
        # إذا لم نجد Reverse Split
        # نستخدم آخر فترة متاحة
        # ----------------------------------------------------

        if split_date is not None:

            split_rows = df[
                df.index.date
                >= split_date
            ]

            if split_rows.empty:

                split_rows = df.tail(40)

        else:

            split_rows = df.tail(40)

        split_open = safe_float(
            split_rows.iloc[0]["Open"]
        )

        split_high = safe_float(
            split_rows["High"].max()
        )

        split_low = safe_float(
            split_rows["Low"].min()
        )

        if split_open is None:

            return None

        # ----------------------------------------------------
        # منطقة نصف الشمعة
        # ----------------------------------------------------

        half_zone = calculate_half_zone(
            split_open
        )

        zone_status = check_half_zone(
            df,
            half_zone
        )

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

        support_confirmed = (
            support_tests
            >= MIN_SUPPORT_TESTS
        )

        # ----------------------------------------------------
        # المسافة من الدعم
        # ----------------------------------------------------

        distance_from_support = None

        near_support = False

        if (
            support is not None
            and support > 0
        ):

            distance_from_support = (
                (
                    price_now
                    - support
                )
                / support
            ) * 100

            near_support = (
                distance_from_support
                <= 15
            )

        # ----------------------------------------------------
        # Volume
        # ----------------------------------------------------

        volume_avg = safe_float(
            df["Volume"]
            .tail(20)
            .mean()
        )

        volume_ratio = None

        if (
            volume_avg is not None
            and volume_avg > 0
        ):

            volume_ratio = (
                volume_now
                / volume_avg
            )

        volume_confirmed = (
            volume_ratio is not None
            and volume_ratio
            >= VOLUME_CONFIRM_RATIO
        )

        volume_strong = (
            volume_ratio is not None
            and volume_ratio
            >= VOLUME_STRONG_RATIO
        )

        # ----------------------------------------------------
        # RSI
        # ----------------------------------------------------

        rsi_improving = (

            rsi is not None

            and rsi_previous is not None

            and rsi
            > rsi_previous
        )

        rsi_ok = (

            rsi is not None

            and rsi <= RSI_MAX_ENTRY
        )

        # ----------------------------------------------------
        # MACD
        # ----------------------------------------------------

        macd_improving = (

            macd_hist is not None

            and macd_hist_previous
            is not None

            and macd_hist
            > macd_hist_previous
        )

        # ----------------------------------------------------
        # شمعة اليوم
        # ----------------------------------------------------

        green_candle = (

            open_now is not None

            and price_now is not None

            and price_now
            > open_now
        )

        # ----------------------------------------------------
        # Breakout
        # ----------------------------------------------------

        recent_high = safe_float(
            df["High"]
            .tail(10)
            .iloc[:-1]
            .max()
        )

        breakout = (

            recent_high is not None

            and price_now
            > recent_high
        )

        # ----------------------------------------------------
        # MA
        # ----------------------------------------------------

        above_ma20 = (

            ma20 is not None

            and price_now
            >= ma20
        )

        above_ma50 = (

            ma50 is not None

            and price_now
            >= ma50
        )

        # ====================================================
        # SCORE
        # ====================================================

        score = 0

        reasons = []

        warnings = []

        # دعم
        if support_confirmed:

            score += 3

            reasons.append(
                "الدعم مؤكد"
            )

        else:

            warnings.append(
                "اختبارات الدعم غير كافية"
            )

        # قريب من الدعم
        if near_support:

            score += 2

            reasons.append(
                "السعر قريب من الدعم"
            )

        # نصف الشمعة
        if zone_status["touched"]:

            score += 2

            reasons.append(
                "تم اختبار منطقة نصف الشمعة"
            )

        else:

            warnings.append(
                "لم يتم اختبار منطقة نصف الشمعة"
            )

        # استعادة المنطقة
        if zone_status["reclaimed"]:

            score += 3

            reasons.append(
                "السعر استعاد منطقة نصف الشمعة"
            )

        # RSI
        if rsi_ok:

            score += 1

            reasons.append(
                f"RSI مناسب ({rsi:.1f})"
            )

        else:

            warnings.append(
                f"RSI مرتفع ({rsi:.1f})"
                if rsi is not None
                else "RSI غير متوفر"
            )

        # RSI يتحسن
        if rsi_improving:

            score += 2

            reasons.append(
                "RSI يتحسن"
            )

        # MACD
        if macd_improving:

            score += 2

            reasons.append(
                "MACD يتحسن"
            )

        else:

            warnings.append(
                "MACD لم يؤكد الصعود"
            )

        # Volume
        if volume_confirmed:

            score += 3

            reasons.append(
                f"Volume Confirmation "
                f"({volume_ratio:.2f}x)"
            )

        else:

            warnings.append(
                f"Volume ضعيف "
                f"({volume_ratio:.2f}x)"
                if volume_ratio is not None
                else "Volume غير متوفر"
            )

        # Volume قوي
        if volume_strong:

            score += 2

            reasons.append(
                "Volume Spike قوي"
            )

        # شمعة صاعدة
        if green_candle:

            score += 1

            reasons.append(
                "شمعة صاعدة"
            )

        # Breakout
        if breakout:

            score += 4

            reasons.append(
                "Breakout مؤكد"
            )

        # MA20
        if above_ma20:

            score += 1

            reasons.append(
                "السعر فوق MA20"
            )

        # MA50
        if above_ma50:

            score += 1

            reasons.append(
                "السعر فوق MA50"
            )

        # ====================================================
        # ENTRY LOGIC
        # ====================================================

        entry_ready = (

            support_confirmed

            and zone_status["touched"]

            and volume_confirmed

            and rsi_ok

            and (
                rsi_improving
                or macd_improving
            )

            and green_candle

        )

        strong_entry = (

            entry_ready

            and zone_status["reclaimed"]

            and volume_strong

            and breakout

        )

        # ====================================================
        # الحالة
        # ====================================================

        if strong_entry:

            status = "🟢 ENTRY"

            action = (
                "تأكيد قوي — دخول محتمل"
            )

        elif entry_ready:

            status = "🟡 READY"

            action = (
                "الشروط جيدة — "
                "انتظر تأكيد الاختراق/الحجم"
            )

        elif (
            support_confirmed
            and (
                zone_status["touched"]
                or near_support
            )
        ):

            status = "🟡 WATCH"

            action = (
                "الدعم موجود — "
                "انتظر حركة صاعدة وحجم"
            )

        else:

            status = "🔴 WAIT"

            action = (
                "لا يوجد تأكيد دخول حاليًا"
            )

        # ====================================================
        # Entry / Stop / Targets
        # ====================================================

        entry = None
        stop = None
        target1 = None
        target2 = None

        risk_reward = None

        if (
            zone_status["reclaimed"]
            and half_zone is not None
        ):

            entry = (
                half_zone["upper"]
            )

        elif price_now is not None:

            entry = price_now

        if support is not None:

            stop = (
                support * 0.97
            )

        if (
            entry is not None
            and stop is not None
            and entry > stop
        ):

            risk = (
                entry - stop
            )

            target1 = (
                entry + risk * 2
            )

            target2 = (
                entry + risk * 3
            )

            risk_reward = "1:2 / 1:3"

        # ====================================================
        # النتيجة
        # ====================================================

        return {

            "ticker": ticker,

            "status": status,

            "action": action,

            "score": score,

            "price": price_now,

            "split_date": split_date,

            "split_open": split_open,

            "split_high": split_high,

            "split_low": split_low,

            "half_zone":
                half_zone,

            "zone_status":
                zone_status,

            "support":
                support,

            "support_tests":
                support_tests,

            "support_confirmed":
                support_confirmed,

            "near_support":
                near_support,

            "volume":
                volume_now,

            "volume_avg":
                volume_avg,

            "volume_ratio":
                volume_ratio,

            "rsi":
                rsi,

            "rsi_improving":
                rsi_improving,

            "macd_improving":
                macd_improving,

            "green_candle":
                green_candle,

            "breakout":
                breakout,

            "above_ma20":
                above_ma20,

            "above_ma50":
                above_ma50,

            "entry":
                entry,

            "stop":
                stop,

            "target1":
                target1,

            "target2":
                target2,

            "risk_reward":
                risk_reward,

            "reasons":
                reasons,

            "warnings":
                warnings
        }

    except Exception as e:

        print(
            f"ERROR {ticker}: {e}"
        )

        return None


# ============================================================
# تشغيل Scanner
# ============================================================

print()

print("=" * 75)

print(
    "CONFIRMATION SCANNER"
)

print(
    "المرحلة الثانية — تأكيد الدخول"
)

print("=" * 75)


tickers = load_candidates()


if not tickers:

    print()

    print(
        "لم يتم العثور على قائمة المرشحين."
    )

    print(
        "تأكد أن ملف "
        "reverse_split_candidates.json "
        "موجود في نفس المجلد."
    )

else:

    print()

    print(
        f"عدد الأسهم للفحص: "
        f"{len(tickers)}"
    )


results = []


for ticker in tickers:

    print()

    print(
        f"تحليل: {ticker}"
    )

    result = analyze_stock(
        ticker
    )

    if result is None:

        print(
            "لا توجد بيانات كافية."
        )

        continue

    results.append(
        result
    )

    print(
        "-" * 75
    )

    print(
        f"الحالة: {result['status']}"
    )

    print(
        f"السعر: "
        f"{price(result['price'])}"
    )

    print(
        f"الدعم: "
        f"{price(result['support'])}"
    )

    print(
        f"اختبارات الدعم: "
        f"{result['support_tests']}"
    )

    print(
        f"Volume: "
        f"{number(result['volume'])}"
    )

    if result["volume_ratio"] is not None:

        print(
            f"Volume Ratio: "
            f"{result['volume_ratio']:.2f}x"
        )

    print(
        f"RSI: "
        f"{result['rsi']:.1f}"
        if result["rsi"] is not None
        else "RSI: N/A"
    )

    if result["half_zone"]:

        print()

        print(
            "منطقة نصف الشمعة:"
        )

        print(
            f"  {price(result['half_zone']['lower'])}"
            f" - "
            f"{price(result['half_zone']['upper'])}"
        )

        print(
            f"اختبار المنطقة: "
            f"{'YES' if result['zone_status']['touched'] else 'NO'}"
        )

        print(
            f"استعادة المنطقة: "
            f"{'YES' if result['zone_status']['reclaimed'] else 'NO'}"
        )

    print()

    print(
        f"Score: {result['score']}"
    )

    print(
        f"الخطوة: {result['action']}"
    )

    if result["entry"] is not None:

        print()

        print(
            f"Entry: "
            f"{price(result['entry'])}"
        )

        print(
            f"Stop: "
            f"{price(result['stop'])}"
        )

        print(
            f"Target 1: "
            f"{price(result['target1'])}"
        )

        print(
            f"Target 2: "
            f"{price(result['target2'])}"
        )

        print(
            f"Risk/Reward: "
            f"{result['risk_reward']}"
        )


# ============================================================
# ترتيب النتائج
# ============================================================

results = sorted(

    results,

    key=lambda x: (

        x["status"] == "🟢 ENTRY",

        x["status"] == "🟡 READY",

        x["status"] == "🟡 WATCH",

        x["score"],

        x["support_tests"],

        x["volume_ratio"]
        if x["volume_ratio"] is not None
        else 0

    ),

    reverse=True
)


# ============================================================
# قائمة الأولوية
# ============================================================

print()

print("=" * 75)

print(
    "قائمة الأولوية للمتابعة"
)

print("=" * 75)


for i, r in enumerate(
    results[:15],
    1
):

    print()

    print(
        f"{i}. {r['ticker']} | "
        f"{r['status']} | "
        f"Score: {r['score']}"
    )

    print(
        f"   السعر: "
        f"{price(r['price'])}"
    )

    print(
        f"   الدعم: "
        f"{price(r['support'])}"
    )

    print(
        f"   الاختبارات: "
        f"{r['support_tests']}"
    )

    if r["volume_ratio"] is not None:

        print(
            f"   Volume Ratio: "
            f"{r['volume_ratio']:.2f}x"
        )

    print(
        f"   الخطوة: "
        f"{r['action']}"
    )


# ============================================================
# ENTRY SIGNALS
# ============================================================

entries = [

    r for r in results

    if r["status"]
    == "🟢 ENTRY"
]


print()

print("=" * 75)

print(
    "🟢 إشارات الدخول المحتملة"
)

print("=" * 75)


if not entries:

    print()

    print(
        "لا توجد حاليًا إشارة دخول مؤكدة."
    )

    print(
        "وهذا طبيعي — الرادار ينتظر اكتمال الشروط."
    )

else:

    for r in entries:

        print()

        print(
            f"🚀 {r['ticker']}"
        )

        print(
            f"Entry: "
            f"{price(r['entry'])}"
        )

        print(
            f"Stop: "
            f"{price(r['stop'])}"
        )

        print(
            f"Target 1: "
            f"{price(r['target1'])}"
        )

        print(
            f"Target 2: "
            f"{price(r['target2'])}"
        )

        print(
            f"Risk/Reward: "
            f"{r['risk_reward']}"
        )


# ============================================================
# الخلاصة
# ============================================================

print()

print("=" * 75)

print(
    "الخلاصة"
)

print("=" * 75)

print(
    "هذا Scanner لا يعتبر مجرد انخفاض السعر إشارة دخول."
)

print(
    "يجب أن يجتمع ثبات الدعم مع الارتداد وتحسن المؤشرات "
    "وتأكيد الحجم قبل إعطاء إشارة ENTRY."
)

print(
    "🟢 ENTRY = شروط قوية مكتملة."
)

print(
    "🟡 READY/WATCH = مراقبة وانتظار التأكيد."
)

print(
    "🔴 WAIT = لا توجد فرصة مؤكدة حاليًا."
)

print()

print(
    "انتهى Confirmation Scanner."
)

print("=" * 75)
