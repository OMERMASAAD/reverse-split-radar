import requests
import pandas as pd
from datetime import datetime
from io import StringIO


# ==========================================
# إعدادات الرادار
# ==========================================

MIN_DAYS = 20
MAX_DAYS = 50

URL = "https://stockanalysis.com/actions/2026/"


# ==========================================
# جلب Reverse Splits
# ==========================================

def get_reverse_splits():

    print("=" * 60)
    print("🚨 REVERSE SPLIT RADAR")
    print("=" * 60)

    headers = {
        "User-Agent": (
            "Mozilla/5.0 "
            "(Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) "
            "Chrome/120 Safari/537.36"
        )
    }

    try:

        response = requests.get(
            URL,
            headers=headers,
            timeout=30
        )

        response.raise_for_status()

        tables = pd.read_html(
            StringIO(response.text)
        )

        if not tables:
            print("❌ لم يتم العثور على جدول")
            return []

        table = tables[0]

        print(
            f"📊 تم العثور على {len(table)} عملية في المصدر"
        )

        candidates = []

        today = datetime.now().date()

        # ==========================================
        # فحص العمليات
        # ==========================================

        for _, row in table.iterrows():

            symbol = str(row.get("Symbol", "")).strip()
            action = str(row.get("Action", "")).strip()
            date_value = row.get("Date", "")

            # نتأكد أنها Reverse Split
            if "reverse stock split" not in action.lower():
                continue

            # ======================================
            # تحويل التاريخ
            # ======================================

            try:

                split_date = pd.to_datetime(
                    date_value
                ).date()

            except Exception:

                continue

            # ======================================
            # حساب عمر التقسيم
            # ======================================

            days_passed = (
                today - split_date
            ).days

            # ======================================
            # استخراج النسبة
            # مثال: 1 for 8
            # ======================================

            ratio = ""

            if ":" in action:
                ratio = action.split(":")[-1].strip()

            elif "for" in action.lower():

                parts = action.lower().split("for")

                if len(parts) > 1:
                    ratio = parts[-1].strip()

            # ======================================
            # شرط 20 - 50 يوم
            # ======================================

            if MIN_DAYS <= days_passed <= MAX_DAYS:

                candidates.append({
                    "symbol": symbol,
                    "split_date": str(split_date),
                    "days": days_passed,
                    "ratio": ratio
                })

        # ==========================================
        # عرض الأسهم المؤهلة
        # ==========================================

        print("\n")
        print("=" * 60)
        print("🎯 الأسهم المؤهلة للرادار")
        print("=" * 60)

        if not candidates:

            print(
                "⚪ لا توجد أسهم حاليًا "
                "بين 20 و50 يوم"
            )

        else:

            for stock in candidates:

                print(
                    f"🟢 {stock['symbol']} | "
                    f"التقسيم: {stock['split_date']} | "
                    f"العمر: {stock['days']} يوم | "
                    f"النسبة: {stock['ratio']}"
                )

        print("\n")
        print("=" * 60)
        print(
            f"📌 عدد الأسهم المؤهلة: "
            f"{len(candidates)}"
        )
        print("=" * 60)

        return candidates

    except Exception as e:

        print(
            f"❌ حدث خطأ أثناء جلب البيانات: {e}"
        )

        return []


# ==========================================
# تشغيل البرنامج
# ==========================================

if __name__ == "__main__":

    get_reverse_splits()
