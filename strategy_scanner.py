# -*- coding: utf-8 -*-
import json
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import yfinance as yf

CANDIDATES_FILE = "reverse_split_candidates.json"
DASHBOARD_FILE = "reverse_split_dashboard.json"

# ملف بيانات الداشبورد الفعلي الذي يقرأه index.html
# (تمت إضافته لأن index.html كان يقرأ ملفًا لا يكتبه أي سكربت)
DASHBOARD_DATA_FILE = "dashboard_data.json"

MIN_DAYS = 20
MAX_DAYS = 50
MIN_HISTORY_DAYS = 60

HALF_ZONE_TOLERANCE = 0.15
SUPPORT_TOLERANCE = 0.04
MIN_SUPPORT_TESTS = 2
QUIET_VOLUME_RATIO = 1.50

MAX_SHORT = 50000
MAX_FLOAT = 4000000
MAX_SCORE = 26


def load_tickers():
    try:
        with open(CANDIDATES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        items = data if isinstance(data, list) else data.get("candidates", [])

        return [
            str(x["symbol"]).upper()
            for x in items
            if isinstance(x, dict) and "symbol" in x
        ]

    except Exception as e:
        print(f"ERROR loading candidates: {e}")
        return []


def safe_float(x):
    try:
        if x is None:
            return None

        x = float(x)

        return None if np.isnan(x) else x

    except Exception:
        return None


def fmt_price(x):
    x = safe_float(x)
    return "N/A" if x is None else f"${x:.4f}"


def fmt_num(x):
    x = safe_float(x)
    return "N/A" if x is None else f"{x:,.0f}"


def calculate_rsi(close, period=14):
    delta = close.diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)

    return 100 - (100 / (1 + rs))


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

    return f"{round(1 / ratio)}:1 Reverse Split"


def calculate_support(df):
    if len(df) < 10:
        return None

    lows = df.tail(40)["Low"].dropna()

    if lows.empty:
        return None

    return float(np.percentile(lows, 15))


def count_support_tests(df, support):
    if support is None:
        return 0

    tolerance = support * SUPPORT_TOLERANCE

    tests = 0
    last_date = None

    for idx, row in df.tail(40).iterrows():

        low = safe_float(row["Low"])

        if low is None:
            continue

        if abs(low - support) > tolerance:
            continue

        d = pd.Timestamp(idx).date()

        if last_date is None or (d - last_date).days >= 2:
            tests += 1
            last_date = d

    return tests


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
        "reason": "",
    }

    try:

        split_rows = df[df.index.date == split_date]

        if split_rows.empty:
            result["reason"] = "لا توجد شمعة في يوم التقسيم"
            return result

        split_open = safe_float(
            split_rows.iloc[0]["Open"]
        )

        if split_open is None or split_open <= 0:
            result["reason"] = "تعذر تحديد افتتاح يوم التقسيم"
            return result

        half = split_open / 2

        low_zone = half * (
            1 - HALF_ZONE_TOLERANCE
        )

        high_zone = half * (
            1 + HALF_ZONE_TOLERANCE
        )

        result.update({
            "split_open": split_open,
            "half_level": half,
            "zone_low": low_zone,
            "zone_high": high_zone,
        })

        after = df[
            df.index.date > split_date
        ]

        tests = []

        for idx, row in after.iterrows():

            low = safe_float(row["Low"])
            close = safe_float(row["Close"])

            if low is None:
                continue

            if low_zone <= low <= high_zone:

                rebound = (
                    close is not None
                    and close > low * 1.03
                )

                tests.append({
                    "date": idx,
                    "rebound": rebound,
                })

        grouped = []

        for test in tests:

            if not grouped:
                grouped.append(test)
                continue

            gap = (
                pd.Timestamp(test["date"]).date()
                -
                pd.Timestamp(
                    grouped[-1]["date"]
                ).date()
            ).days

            if gap >= 2:
                grouped.append(test)

        result["tests"] = len(grouped)

        result["successful_tests"] = sum(
            x["rebound"]
            for x in grouped
        )

        if (
            len(grouped) >= MIN_SUPPORT_TESTS
            and result["successful_tests"] >= 1
        ):

            result.update({
                "stable": True,
                "passed": True,
                "status": "PASS",
                "reason": "اختباران أو أكثر مع ثبات وارتداد",
            })

        elif len(grouped) == 1:

            result["status"] = "WATCH"

            result["reason"] = (
                "اختبار واحد فقط - ننتظر إعادة الاختبار"
            )

        else:

            result["status"] = "WAIT"

            result["reason"] = "لم يتأكد القاع بعد"

        return result

    except Exception as e:

        result["reason"] = f"خطأ: {e}"

        return result


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

        earnings = stock.get_earnings_dates(
            limit=4
        )

        if earnings is not None and not earnings.empty:

            now = pd.Timestamp.now()

            for d in earnings.index:

                try:

                    d = pd.Timestamp(d)

                    if d.tzinfo is not None:
                        d = d.tz_localize(None)

                    if d >= now:

                        catalysts.append(
                            "نتائج مالية قادمة"
                        )

                        break

                except Exception:
                    continue

    except Exception:
        pass

    return list(
        dict.fromkeys(catalysts)
    )


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
            MIN_DAYS
            <= days_since_split
            <= MAX_DAYS
        ):
            return None

        df = stock.history(
            start=split_date - timedelta(days=150),
            end=today + timedelta(days=1),
            auto_adjust=False,
        )

        if df is None or df.empty:
            return None

        required = [
            "Open",
            "High",
            "Low",
            "Close",
            "Volume",
        ]

        if any(
            c not in df.columns
            for c in required
        ):
            return None

        df = df.dropna(
            subset=required
        )

        if len(df) < MIN_HISTORY_DAYS:
            return None

        df["RSI"] = calculate_rsi(
            df["Close"]
        )

        (
            df["MACD"],
            df["MACD_SIGNAL"],
            df["MACD_HIST"],
        ) = calculate_macd(
            df["Close"]
        )

        df["MA20"] = (
            df["Close"].rolling(20).mean()
        )

        df["MA50"] = (
            df["Close"].rolling(50).mean()
        )

        latest = df.iloc[-1]

        price = safe_float(
            latest["Close"]
        )

        volume = safe_float(
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

        previous_rsi = (
            safe_float(
                df["RSI"].iloc[-2]
            )
            if len(df) >= 2
            else None
        )

        rsi_improving = (
            rsi is not None
            and previous_rsi is not None
            and rsi > previous_rsi
        )

        macd_improving = False

        if len(df) >= 3:

            h1 = safe_float(
                df["MACD_HIST"].iloc[-2]
            )

            h2 = safe_float(
                df["MACD_HIST"].iloc[-3]
            )

            macd_improving = (
                h1 is not None
                and h2 is not None
                and h1 > h2
            )

        volume20 = safe_float(
            df["Volume"].tail(20).mean()
        )

        volume_ratio = None

        if (
            volume is not None
            and volume20 is not None
            and volume20 > 0
        ):
            volume_ratio = (
                volume / volume20
            )

        quiet_volume = (
            volume_ratio is not None
            and volume_ratio <= QUIET_VOLUME_RATIO
        )

        post = df[
            df.index.date >= split_date
        ]

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

        if split_open is None or split_open <= 0:
            return None

        post_change = (
            (price - split_open)
            / split_open
        ) * 100

        drawdown = None

        if (
            split_high is not None
            and split_high > 0
        ):

            drawdown = (
                (price - split_high)
                / split_high
            ) * 100

        half = analyze_half_zone(
            df,
            split_date
        )

        support = calculate_support(df)

        support_tests = count_support_tests(
            df,
            support
        )

        near_support = False

        if (
            support is not None
            and support > 0
        ):

            distance = (
                price - support
            ) / support

            near_support = (
                0 <= distance <= 0.20
            )

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

        ma20_ok = (
            ma20 is not None
            and price <= ma20 * 1.10
        )

        catalysts = get_catalysts(
            stock
        )

        # ====================================================
        # SCORE
        # ====================================================

        score = 2

        signals = [
            "Reverse Split حديث"
        ]

        warnings = []

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

        if macd_improving:

            score += 2

            signals.append(
                "MACD يتحسن"
            )

        else:

            warnings.append(
                "MACD لم يظهر تحسنًا كافيًا"
            )

        if quiet_volume:

            score += 2

            signals.append(
                f"Volume هادئ ({fmt_num(volume)})"
            )

        elif volume_ratio is not None:

            signals.append(
                f"Volume Ratio {volume_ratio:.2f}x"
            )

        if support_tests >= 2:

            score += 2

            signals.append(
                f"الدعم العام اختُبر "
                f"{support_tests} مرات"
            )

        elif support_tests == 1:

            score += 1

            signals.append(
                "يوجد اختبار دعم واحد"
            )

        if near_support:

            score += 1

            signals.append(
                "السعر قريب من الدعم"
            )

        if drawdown is not None:

            if drawdown <= -40:

                score += 3

                signals.append(
                    f"هبوط قوي من القمة "
                    f"({drawdown:.1f}%)"
                )

            elif drawdown <= -30:

                score += 2

                signals.append(
                    f"تصحيح جيد من القمة "
                    f"({drawdown:.1f}%)"
                )

            elif drawdown <= -20:

                score += 1

                signals.append(
                    f"تصحيح متوسط "
                    f"({drawdown:.1f}%)"
                )

        if float_ok:

            score += 1

            signals.append(
                f"Float منخفض "
                f"({fmt_num(float_shares)})"
            )

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

        if ma20_ok:

            score += 1

            signals.append(
                "السعر قريب من MA20"
            )

        if catalysts:

            score += 2

            signals.extend(
                catalysts
            )

        score_percent = round(
            (score / MAX_SCORE) * 100,
            1
        )

        # ====================================================
        # CORE
        # ====================================================

        core = 0

        if half["passed"]:
            core += 2

        elif half["status"] == "WATCH":
            core += 1

        if (
            rsi is not None
            and rsi < 35
        ):
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
                "الدعم مؤكد. "
                "انتظر تأكيد صعود/حجم للدخول."
            )

        elif half["passed"]:

            next_step = "WAIT_TRIGGER"

            next_text = (
                "الدعم مؤكد، "
                "لكن ننتظر تحسن المؤشرات أو محفز."
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
                "لا تدخل. "
                "انتظر تكوين قاع واختبار دعم واضح."
            )

        # ====================================================
        # Rating
        # ====================================================

        if (
            next_step == "READY_TRIGGER"
            and score >= 18
        ):

            rating = "MATCH قوي جدًا"

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

            "score_percent": score_percent,

            "rating": rating,

            "next_step": next_step,

            "next_text": next_text,

            "price": price,

            "split_date": split_date.isoformat(),

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

            "macd_hist": macd_hist,

            "macd_improving": macd_improving,

            "ma20": ma20,

            "ma50": ma50,

            "float_shares": float_shares,

            "short_shares": short_shares,

            "half": half,

            "catalysts": catalysts,

            "signals": signals,

            "warnings": warnings,

            "core": core,
        }

    except Exception as e:

        print(
            f"ERROR analyzing {ticker}: {e}"
        )

        return None


def print_stock_result(result):

    h = result["half"]

    print("-" * 75)

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
        f"الحركة من الافتتاح: "
        f"{result['post_change']:.1f}%"
    )

    if result["drawdown"] is not None:

        print(
            f"الهبوط من القمة: "
            f"{result['drawdown']:.1f}%"
        )

    print(
        f"الدعم العام: "
        f"{fmt_price(result['support'])}"
    )

    print(
        f"اختبارات الدعم العام: "
        f"{result['support_tests']}"
    )

    print(
        f"Volume: "
        f"{fmt_num(result['volume'])}"
    )

    if result["volume_ratio"] is not None:

        print(
            f"Volume Ratio: "
            f"{result['volume_ratio']:.2f}x"
        )

    if result["rsi"] is not None:

        print(
            f"RSI: "
            f"{result['rsi']:.1f}"
        )

    else:

        print("RSI: N/A")

    if result["previous_rsi"] is not None:

        print(
            f"RSI السابق: "
            f"{result['previous_rsi']:.1f}"
        )

    if result["macd"] is not None:

        print(
            f"MACD: "
            f"{result['macd']:.5f}"
        )

    else:

        print("MACD: N/A")

    print(
        f"MA20: "
        f"{fmt_price(result['ma20'])}"
    )

    print(
        f"MA50: "
        f"{fmt_price(result['ma50'])}"
    )

    print(
        "\nمنطقة نصف شمعة التقسيم"
    )

    print("-" * 75)

    print(
        f"نصف الافتتاح: "
        f"{fmt_price(h['half_level'])}"
    )

    print(
        f"منطقة البحث عن القاع: "
        f"{fmt_price(h['zone_low'])} - "
        f"{fmt_price(h['zone_high'])}"
    )

    print(
        f"اختبارات المنطقة: "
        f"{h['tests']}"
    )

    print(
        f"اختبارات ناجحة/ارتداد: "
        f"{h['successful_tests']}"
    )

    print(
        f"حالة الدعم: "
        f"{h['status']}"
    )

    print(
        f"التفسير: "
        f"{h['reason']}"
    )

    print(
        "\nإشارات التحليل"
    )

    print("-" * 75)

    for s in result["signals"]:
        print(
            f"OK: {s}"
        )

    for w in result["warnings"]:
        print(
            f"WARN: {w}"
        )

    print(
        "\nالنتيجة"
    )

    print("-" * 75)

    print(
        f"التقييم: "
        f"{result['rating']}"
    )

    print(
        f"SCORE الداخلي: "
        f"{result['score']}/{MAX_SCORE}"
    )

    print(
        f"SCORE %: "
        f"{result['score_percent']:.1f}%"
    )

    print(
        f"CORE: "
        f"{result['core']}"
    )

    print(
        f"الخطوة التالية: "
        f"{result['next_step']}"
    )

    print(
        f">>> {result['next_text']}"
    )


def to_dashboard_record(r):
    """
    يحوّل نتيجة سهم واحدة (كما ينتجها analyze_stock) إلى الصيغة
    المختصرة التي يقرأها index.html فعليًا من dashboard_data.json.

    لا يغيّر أي قيمة أو حساب - فقط يعيد تسمية/تسطيح الحقول:
      ticker      -> t
      rating      -> status
      next_step   -> state
      next_text   -> action
      half (dict) -> half / zone_low / zone_high / tests / successful_tests
    باقي الحقول (score, score_percent, core, rsi, macd, ...)
    تُنسخ بنفس الاسم لأنها متطابقة أصلًا مع ما يقرأه Dashboard.
    """

    half = r.get("half") or {}

    return {
        "t": r.get("ticker"),
        "price": r.get("price"),

        "half": half.get("half_level"),
        "zone_low": half.get("zone_low"),
        "zone_high": half.get("zone_high"),
        "tests": half.get("tests"),
        "successful_tests": half.get("successful_tests"),

        "rsi": r.get("rsi"),
        "previous_rsi": r.get("previous_rsi"),
        "rsi_improving": r.get("rsi_improving"),

        "macd": r.get("macd"),
        "macd_hist": r.get("macd_hist"),
        "macd_improving": r.get("macd_improving"),

        "volume": r.get("volume"),
        "volume20": r.get("volume20"),
        "volume_ratio": r.get("volume_ratio"),

        "ma20": r.get("ma20"),
        "ma50": r.get("ma50"),

        "score": r.get("score"),
        "score_percent": r.get("score_percent"),
        "core": r.get("core"),

        "status": r.get("rating"),
        "state": r.get("next_step"),
        "action": r.get("next_text"),

        "split_date": r.get("split_date"),
        "split_ratio": r.get("split_ratio"),
        "days_since_split": r.get("days_since_split"),
        "split_open": r.get("split_open"),
        "split_high": r.get("split_high"),
        "split_low": r.get("split_low"),

        "drawdown": r.get("drawdown"),
        "post_change": r.get("post_change"),

        "support": r.get("support"),
        "support_tests": r.get("support_tests"),

        "float_shares": r.get("float_shares"),
        "short_shares": r.get("short_shares"),

        "catalysts": r.get("catalysts") or [],
        "signals": r.get("signals") or [],
        "warnings": r.get("warnings") or [],
    }


def save_dashboard_data(results):
    """
    يكتب dashboard_data.json - وهو الملف الذي يقرأه index.html
    فعليًا عبر fetch(). قبل هذا التعديل لم يكن أي سكربت في
    الـRepository يكتب هذا الملف، لذلك كان Dashboard يعرض بيانات
    قديمة/ثابتة من مصدر غير معروف.
    """

    try:

        payload = {
            "updated_at":
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),

            "stocks":
                [to_dashboard_record(r) for r in results],
        }

        with open(
            DASHBOARD_DATA_FILE,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                payload,
                f,
                ensure_ascii=False,
                indent=2,
            )

        print(
            f"\nتم حفظ بيانات الداشبورد الفعلية: "
            f"{DASHBOARD_DATA_FILE}"
        )

    except Exception as e:

        print(
            f"\nERROR saving dashboard_data.json: {e}"
        )


def save_dashboard(results):

    try:

        payload = {

            "generated_at":
                datetime.now().isoformat(),

            "strategy":
                "REVERSE SPLIT RADAR",

            "max_score":
                MAX_SCORE,

            "min_days":
                MIN_DAYS,

            "max_days":
                MAX_DAYS,

            "results_count":
                len(results),

            "results":
                results,
        }

        with open(
            DASHBOARD_FILE,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                payload,
                f,
                ensure_ascii=False,
                indent=2,
            )

        print(
            f"\nتم حفظ بيانات الداشبورد: "
            f"{DASHBOARD_FILE}"
        )

    except Exception as e:

        print(
            f"\nERROR saving dashboard: {e}"
        )


def main():

    tickers = load_tickers()

    print(
        "\n" + "=" * 75
    )

    print(
        "REVERSE SPLIT RADAR - FINAL STRATEGY"
    )

    print(
        "=" * 75
    )

    print(
        f"الفترة: {MIN_DAYS}-{MAX_DAYS} "
        f"يوم بعد Reverse Split"
    )

    print(
        f"منطقة نصف الافتتاح: "
        f"±{HALF_ZONE_TOLERANCE * 100:.0f}%"
    )

    print(
        "تأكيد الدعم: اختباران على الأقل "
        "مع ثبات/ارتداد"
    )

    print(
        f"عدد الأسهم: {len(tickers)}"
    )

    print(
        "=" * 75
    )

    if not tickers:

        print(
            f"\nلا توجد أسهم في ملف "
            f"{CANDIDATES_FILE}"
        )

        return

    results = []

    for ticker in tickers:

        print(
            f"\nتحليل: {ticker}"
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

        results.append(result)

        print_stock_result(
            result
        )

    rating_order = {

        "MATCH قوي جدًا": 4,

        "WATCHLIST قوية": 3,

        "WATCHLIST": 2,

        "مراقبة": 1,
    }

    results.sort(

        key=lambda x: (

            rating_order.get(
                x["rating"],
                0
            ),

            x["half"]["passed"],

            x["half"]["tests"],

            x["rsi_improving"],

            x["macd_improving"],

            x["core"],

            x["score"],
        ),

        reverse=True,
    )

    print(
        "\n" + "=" * 75
    )

    print(
        "أفضل الأسهم"
    )

    print(
        "=" * 75
    )

    for title in [

        "MATCH قوي جدًا",

        "WATCHLIST قوية",

        "WATCHLIST",
    ]:

        group = [

            r
            for r in results
            if r["rating"] == title
        ]

        if not group:
            continue

        print(
            f"\n{title}\n"
            + "-" * 75
        )

        for i, r in enumerate(
            group[:10],
            1
        ):

            if r["rsi"] is not None:

                rsi_text = (
                    f"{r['rsi']:.1f}"
                )

            else:

                rsi_text = "N/A"

            print(

                f"{i}. {r['ticker']} | "

                f"Score {r['score']}/{MAX_SCORE} "

                f"({r['score_percent']:.1f}%) | "

                f"CORE {r['core']} | "

                f"RSI {rsi_text} | "

                f"Vol {fmt_num(r['volume'])} | "

                f"Price {fmt_price(r['price'])} | "

                f"{r['next_step']}"
            )

    print(
        "\n" + "=" * 75
    )

    print(
        "SUMMARY"
    )

    print(
        "=" * 75
    )

    print(
        f"الأسهم التي تم تحليلها: "
        f"{len(results)}"
    )

    ready = [

        r
        for r in results
        if r["next_step"] == "READY_TRIGGER"
    ]

    confirmed = [

        r
        for r in results
        if r["half"]["passed"]
    ]

    print(
        f"READY_TRIGGER: "
        f"{len(ready)}"
    )

    print(
        f"دعم نصف الشمعة مؤكد: "
        f"{len(confirmed)}"
    )

    if ready:

        print(
            "\nأفضل فرص تحتاج تأكيد Trigger:"
        )

        for r in ready[:10]:

            print(

                f"- {r['ticker']} | "

                f"Score {r['score']}/{MAX_SCORE} | "

                f"{r['next_text']}"
            )

    else:

        print(
            "\nلا توجد حاليًا أسهم وصلت إلى "
            "READY_TRIGGER."
        )

    save_dashboard(
        results
    )

    save_dashboard_data(
        results
    )

    print(
        "\n" + "=" * 75
    )

    print(
        "تم إنهاء التحليل بنجاح."
    )

    print(
        "=" * 75
    )


if __name__ == "__main__":
    main()
