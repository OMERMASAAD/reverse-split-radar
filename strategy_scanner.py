import yfinance as yf
import pandas as pd
import numpy as np
import json
from datetime import datetime, timedelta


# ============================================================
# 📂 الملفات والإعدادات
# ============================================================

CANDIDATES_FILE = "reverse_split_candidates.json"

MIN_AVG_DAYS = 20

# السيولة:
# لا نريد السهم الذي انفجر بالفعل
MAX_VOLUME = 1_000_000

# Float:
MAX_FLOAT = 4_000_000

# Short Interest:
MAX_SHORT = 50_000

# RSI:
RSI_MAX = 35
RSI_IMPROVEMENT = True

# الحد الأقصى لصعود السهم بعد Reverse Split
# نريد حركة هادئة وليس انفجاراً
MAX_GAIN_AFTER_SPLIT = 20


# ============================================================
# 📥 تحميل قائمة المرشحين
# ============================================================

try:

    with open(CANDIDATES_FILE, "r", encoding="utf-8") as f:
        candidates = json.load(f)

except Exception as e:

    print(f"❌ فشل تحميل قائمة المرشحين: {e}")
    candidates = []


TICKERS = [
    item["symbol"]
    for item in candidates
    if "symbol" in item
]


# ============================================================
# 📊 RSI
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
# 📉 MACD
# ============================================================

def calculate_macd(close):

    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()

    macd = ema12 - ema26

    signal = macd.ewm(span=9, adjust=False).mean()

    histogram = macd - signal

    return macd, signal, histogram


# ============================================================
# 📈 المتوسطات
# ============================================================

def calculate_averages(close):

    ma20 = close.rolling(20).mean()
    ma50 = close.rolling(50).mean()

    return ma20, ma50


# ============================================================
# 🔎 فحص السهم
# ============================================================

def analyze_stock(ticker, split_info):

    print("\n" + "=" * 65)
    print(f"🔎 تحليل الاستراتيجية: {ticker}")
    print("=" * 65)

    try:

        stock = yf.Ticker(ticker)

        # ----------------------------------------------------
        # البيانات اليومية
        # ----------------------------------------------------

        df = stock.history(
            period="6mo",
            interval="1d",
            auto_adjust=False
        )

        if df.empty or len(df) < 50:

            print("❌ بيانات تاريخية غير كافية")
            return None

        close = df["Close"]
        volume = df["Volume"]

        current_price = float(close.iloc[-1])

        # ----------------------------------------------------
        # المؤشرات
        # ----------------------------------------------------

        rsi = calculate_rsi(close)

        macd, signal, histogram = calculate_macd(close)

        ma20, ma50 = calculate_averages(close)

        current_rsi = float(rsi.iloc[-1])
        previous_rsi = float(rsi.iloc[-2])

        current_macd = float(macd.iloc[-1])
        previous_macd = float(macd.iloc[-2])

        current_hist = float(histogram.iloc[-1])
        previous_hist = float(histogram.iloc[-2])

        current_ma20 = float(ma20.iloc[-1])
        current_ma50 = float(ma50.iloc[-1])

        current_volume = int(volume.iloc[-1])

        avg_volume_20 = float(volume.tail(20).mean())

        # ----------------------------------------------------
        # Reverse Split
        # ----------------------------------------------------

        split_date = datetime.strptime(
            split_info["split_date"],
            "%Y-%m-%d"
        ).date()

        split_ratio_text = split_info["reverse_split"]

        split_index = df.index

        # البحث عن سعر قريب من تاريخ التقسيم
        split_price = None

        for index in split_index:

            index_date = index.date()

            if index_date >= split_date:

                split_price = float(df.loc[index]["Open"])

                break

        if split_price is None:

            split_price = float(df["Open"].iloc[-1])

        # ----------------------------------------------------
        # مقدار الحركة منذ التقسيم
        # ----------------------------------------------------

        gain_after_split = (
            (current_price - split_price)
            / split_price
        ) * 100

        # ----------------------------------------------------
        # الهبوط من أعلى سعر بعد التقسيم
        # ----------------------------------------------------

        post_split_df = df[df.index.date >= split_date]

        if post_split_df.empty:

            print("❌ لا توجد بيانات بعد التقسيم")
            return None

        post_split_high = float(
            post_split_df["High"].max()
        )

        drawdown_from_high = (
            (current_price - post_split_high)
            / post_split_high
        ) * 100

        # ----------------------------------------------------
        # البحث عن دعم قريب
        # ----------------------------------------------------

        recent_lows = post_split_df["Low"].tail(20)

        support = float(recent_lows.min())

        distance_from_support = (
            (current_price - support)
            / current_price
        ) * 100

        # ----------------------------------------------------
        # اختبار الدعم عدة مرات
        # ----------------------------------------------------

        support_tolerance = current_price * 0.03

        support_tests = int(
            (
                abs(
                    post_split_df["Low"] - support
                )
                <= support_tolerance
            ).sum()
        )

        # ----------------------------------------------------
        # السيولة
        # ----------------------------------------------------

        volume_condition = (
            current_volume <= MAX_VOLUME
        )

        volume_building = (
            current_volume > avg_volume_20 * 0.8
        )

        # ----------------------------------------------------
        # RSI
        # ----------------------------------------------------

        rsi_condition = (
            current_rsi <= RSI_MAX
        )

        rsi_improving = (
            current_rsi > previous_rsi
        )

        # ----------------------------------------------------
        # MACD
        # ----------------------------------------------------

        macd_improving = (
            current_macd > previous_macd
            or current_hist > previous_hist
        )

        # ----------------------------------------------------
        # المتوسطات
        # ----------------------------------------------------

        averages_condition = (
            len(df) >= MIN_AVG_DAYS
        )

        # ----------------------------------------------------
        # الحركة الهادئة بعد التقسيم
        # ----------------------------------------------------

        quiet_move = (
            gain_after_split <= MAX_GAIN_AFTER_SPLIT
        )

        # ----------------------------------------------------
        # معلومات الشركة
        # ----------------------------------------------------

        try:

            info = stock.info

        except Exception:

            info = {}

        float_shares = info.get(
            "floatShares"
        )

        short_shares = info.get(
            "sharesShort"
        )

        # ----------------------------------------------------
        # Float
        # ----------------------------------------------------

        if float_shares is not None:

            float_condition = (
                float_shares <= MAX_FLOAT
            )

        else:

            float_condition = False

        # ----------------------------------------------------
        # Short Interest
        # ----------------------------------------------------

        if short_shares is not None:

            short_condition = (
                short_shares <= MAX_SHORT
            )

        else:

            short_condition = False

        # ====================================================
        # 📰 المحفزات المستقبلية
        # ====================================================

        catalysts = []

        # Earnings
        try:

            calendar = stock.calendar

            if calendar is not None:

                if isinstance(calendar, dict):

                    earnings_dates = calendar.get(
                        "Earnings Date"
                    )

                    if earnings_dates:

                        catalysts.append(
                            "📅 موعد نتائج مالية"
                        )

        except Exception:

            pass

        # ----------------------------------------------------
        # Analyst / company events
        # ----------------------------------------------------

        try:

            events = stock.get_shares_full(
                start=datetime.now() - timedelta(days=30),
                end=datetime.now()
            )

            # مجرد التأكد أن بيانات الشركة متاحة
            if events is not None:

                pass

        except Exception:

            pass

        # ====================================================
        # 🎯 حساب النقاط
        # ====================================================

        score = 0

        signals = []

        # Reverse Split
        score += 2
        signals.append("✅ Reverse Split")

        # RSI
        if rsi_condition:

            score += 2
            signals.append(
                f"✅ RSI منخفض ({current_rsi:.1f})"
            )

        if rsi_improving:

            score += 2
            signals.append(
                f"✅ RSI يتحسن ({previous_rsi:.1f} → {current_rsi:.1f})"
            )

        # MACD
        if macd_improving:

            score += 1
            signals.append(
                "✅ MACD يتحسن"
            )

        else:

            signals.append(
                "⚠️ MACD ما زال ضعيف"
            )

        # Volume
        if volume_condition:

            score += 1
            signals.append(
                f"✅ حجم هادئ ({current_volume:,})"
            )

        else:

            signals.append(
                f"⚠️ حجم مرتفع ({current_volume:,})"
            )

        if volume_building:

            score += 1
            signals.append(
                "🟢 توجد سيولة مقارنة بالمتوسط"
            )

        # Support
        if support_tests >= 2:

            score += 2
            signals.append(
                f"✅ اختبار دعم عدة مرات ({support_tests})"
            )

        elif support_tests == 1:

            score += 1
            signals.append(
                "🟡 يوجد اختبار دعم"
            )

        else:

            signals.append(
                "⚠️ لا يوجد اختبار دعم واضح"
            )

        # Quiet move
        if quiet_move:

            score += 2
            signals.append(
                f"✅ الحركة بعد التقسيم هادئة ({gain_after_split:.1f}%)"
            )

        else:

            signals.append(
                f"❌ السهم تحرك بقوة ({gain_after_split:.1f}%)"
            )

        # Drawdown
        if drawdown_from_high <= -20:

            score += 2
            signals.append(
                f"✅ هبوط قوي من القمة ({drawdown_from_high:.1f}%)"
            )

        elif drawdown_from_high <= -10:

            score += 1
            signals.append(
                f"🟡 تصحيح جيد ({drawdown_from_high:.1f}%)"
            )

        else:

            signals.append(
                f"⚠️ التصحيح ضعيف ({drawdown_from_high:.1f}%)"
            )

        # Float
        if float_condition:

            score += 2
            signals.append(
                f"✅ Float منخفض ({float_shares:,})"
            )

        elif float_shares is not None:

            signals.append(
                f"⚠️ Float مرتفع ({float_shares:,})"
            )

        else:

            signals.append(
                "⚠️ Float غير متوفر"
            )

        # Short
        if short_condition:

            score += 2
            signals.append(
                f"✅ Short منخفض ({short_shares:,})"
            )

        elif short_shares is not None:

            signals.append(
                f"⚠️ Short مرتفع ({short_shares:,})"
            )

        else:

            signals.append(
                "⚠️ Short Interest غير متوفر"
            )

        # Future catalyst
        if catalysts:

            score += 2

            for catalyst in catalysts:

                signals.append(
                    f"🚀 {catalyst}"
                )

        else:

            signals.append(
                "⚪ لا يوجد محفز مستقبلي واضح من بيانات Yahoo"
            )

        # ====================================================
        # 📊 النتيجة
        # ====================================================

        print("\n📊 بيانات السهم")
        print("-" * 65)

        print(
            f"💰 السعر الحالي: ${current_price:.4f}"
        )

        print(
            f"📅 Reverse Split: {split_date}"
        )

        print(
            f"📌 نسبة التقسيم: {split_ratio_text}"
        )

        print(
            f"📈 الحركة منذ التقسيم: "
            f"{gain_after_split:.1f}%"
        )

        print(
            f"📉 الهبوط من أعلى سعر: "
            f"{drawdown_from_high:.1f}%"
        )

        print(
            f"🟢 الدعم: ${support:.4f}"
        )

        print(
            f"🔄 اختبارات الدعم: {support_tests}"
        )

        print(
            f"📊 Volume اليوم: {current_volume:,}"
        )

        print(
            f"📊 متوسط Volume 20: "
            f"{avg_volume_20:,.0f}"
        )

        print(
            f"📉 RSI: {current_rsi:.1f}"
        )

        print(
            f"📉 MACD: {current_macd:.5f}"
        )

        print(
            f"📊 MA20: ${current_ma20:.4f}"
        )

        print(
            f"📊 MA50: ${current_ma50:.4f}"
        )

        print("\n🔍 إشارات التحليل")
        print("-" * 65)

        for signal_text in signals:

            print(signal_text)

        print("\n" + "-" * 65)

        print(
            f"🎯 SCORE: {score}"
        )

        # ====================================================
        # 🚦 تصنيف السهم
        # ====================================================

        if score >= 15:

            rating = "🔥🔥 WATCHLIST قوية"

        elif score >= 11:

            rating = "🟢 WATCHLIST جيدة"

        elif score >= 8:

            rating = "🟡 مراقبة"

        else:

            rating = "⚪ ضعيف حالياً"

        print(
            f"🚦 التقييم: {rating}"
        )

        # ====================================================
        # النتيجة
        # ====================================================

        return {
            "symbol": ticker,
            "price": current_price,
            "rsi": current_rsi,
            "volume": current_volume,
            "avg_volume_20": avg_volume_20,
            "support": support,
            "support_tests": support_tests,
            "gain_after_split": gain_after_split,
            "drawdown_from_high": drawdown_from_high,
            "float": float_shares,
            "short": short_shares,
            "score": score,
            "rating": rating,
            "catalysts": catalysts
        }

    except Exception as e:

        print(
            f"❌ خطأ في تحليل {ticker}: {e}"
        )

        return None


# ============================================================
# 🚨 تشغيل الرادار
# ============================================================

print("\n")
print("🚨 REVERSE SPLIT + ACCUMULATION STRATEGY")
print("=" * 65)

print(
    "🎯 الهدف: العثور على سهم هادئ بعد Reverse Split "
    "وقريب من دعم مع تحسن تدريجي"
)

print(
    f"📋 عدد المرشحين: {len(TICKERS)}"
)

print("=" * 65)


results = []


for item in candidates:

    ticker = item.get("symbol")

    if not ticker:
        continue

    result = analyze_stock(
        ticker,
        item
    )

    if result:

        results.append(result)


# ============================================================
# 🏆 ترتيب النتائج
# ============================================================

print("\n")
print("=" * 65)
print("🏆 أفضل الأسهم حسب الاستراتيجية")
print("=" * 65)


if results:

    results_sorted = sorted(
        results,
        key=lambda x: x["score"],
        reverse=True
    )

    for i, result in enumerate(
        results_sorted[:20],
        start=1
    ):

        print(
            f"{i:02d}. {result['symbol']} | "
            f"Score: {result['score']} | "
            f"RSI: {result['rsi']:.1f} | "
            f"Volume: {result['volume']:,} | "
            f"الدعم: ${result['support']:.4f} | "
            f"{result['rating']}"
        )

else:

    print("❌ لم يتم العثور على نتائج")


print("\n")
print("=" * 65)
print("✅ انتهى Strategy Scanner")
print("=" * 65)
