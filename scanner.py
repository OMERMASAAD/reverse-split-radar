import yfinance as yf
import pandas as pd
from datetime import datetime


# ==========================================
# الأسهم التي نريد فحصها
# ==========================================

TICKERS = [
    "JZ",
    "CANF",
]


# ==========================================
# إعدادات رادار Reverse Split
# ==========================================

MIN_DAYS = 20
MAX_DAYS = 50


# ==========================================
# فحص السهم
# ==========================================

def check_stock(ticker):

    print("\n" + "=" * 50)
    print(f"🔎 فحص السهم: {ticker}")
    print("=" * 50)

    try:

        stock = yf.Ticker(ticker)

        # الحصول على بيانات التقسيمات
        splits = stock.splits

        # إذا لم توجد أي تقسيمات
        if splits is None or splits.empty:
            print("❌ لا توجد تقسيمات مسجلة")
            return

        found_reverse = False

        latest_reverse_date = None
        latest_reverse_ratio = None

        # ==========================================
        # البحث عن آخر Reverse Split فقط
        # ==========================================

        for date, ratio in splits.items():

            # Reverse Split عادة تكون النسبة أقل من 1
            # مثال:
            # 1 مقابل 10 = 0.1
            # 1 مقابل 20 = 0.05

            if ratio < 1:

                split_date = date.to_pydatetime().date()

                # نأخذ أحدث Reverse Split فقط
                if (
                    latest_reverse_date is None
                    or split_date > latest_reverse_date
                ):
                    latest_reverse_date = split_date
                    latest_reverse_ratio = ratio

        # ==========================================
        # لا يوجد Reverse Split
        # ==========================================

        if latest_reverse_date is None:

            print("❌ لا يوجد Reverse Split")
            return

        # ==========================================
        # حساب عدد الأيام منذ آخر Reverse Split
        # ==========================================

        today = datetime.now().date()

        days_passed = (
            today - latest_reverse_date
        ).days

        print(f"📌 نوع التقسيم: Reverse Split")
        print(f"📅 تاريخ آخر تقسيم: {latest_reverse_date}")
        print(f"📊 نسبة التقسيم: {latest_reverse_ratio}")
        print(f"⏱️ عدد الأيام منذ التقسيم: {days_passed}")

        # ==========================================
        # شرط الرادار
        # من 20 إلى 50 يوم فقط
        # ==========================================

        if MIN_DAYS <= days_passed <= MAX_DAYS:

            found_reverse = True

            print(
                f"🟢 داخل الرادار "
                f"(بين {MIN_DAYS} و {MAX_DAYS} يوم)"
            )

            print(
                f"🚨 SIGNAL: {ticker} "
                f"Reverse Split حديث"
            )

        else:

            print(
                f"⚪ خارج الرادار "
                f"(مطلوب {MIN_DAYS}-{MAX_DAYS} يوم)"
            )

        # ==========================================
        # النتيجة النهائية
        # ==========================================

        if not found_reverse:

            print(
                "❌ السهم لا يطابق شروط Reverse Split الحالية"
            )

    except Exception as e:

        print(
            f"❌ خطأ في السهم {ticker}: {e}"
        )


# ==========================================
# تشغيل الفحص على جميع الأسهم
# ==========================================

print("\n")
print("🚨 REVERSE SPLIT RADAR")
print("=" * 50)

print(
    f"🎯 شرط الرادار: "
    f"{MIN_DAYS} إلى {MAX_DAYS} يوم"
)

print(
    f"📋 عدد الأسهم للفحص: {len(TICKERS)}"
)

print("=" * 50)


for ticker in TICKERS:

    try:

        check_stock(ticker)

    except Exception as e:

        print(
            f"❌ خطأ أثناء فحص {ticker}: {e}"
        )


print("\n")
print("=" * 50)
print("✅ انتهى الفحص")
print("=" * 50)
