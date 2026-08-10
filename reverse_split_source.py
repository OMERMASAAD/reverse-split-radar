import requests
import pandas as pd
from datetime import datetime, timedelta
from io import StringIO


# ==========================================
# إعدادات الرادار
# ==========================================

MIN_DAYS = 20
MAX_DAYS = 50

URL = "https://stockanalysis.com/actions/2026/"


# ==========================================
# جلب عمليات الشركات
# ==========================================

def get_reverse_splits():

    print("=" * 60)
    print("🚨 البحث عن Reverse Stock Splits")
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

        # قراءة الجداول الموجودة في الصفحة
        tables = pd.read_html(
            StringIO(response.text)
        )

        if not tables:

            print("❌ لم يتم العثور على جدول")
            return []

        print(f"📊 عدد الجداول الموجودة: {len(tables)}")

        reverse_splits = []

        # ==========================================
        # البحث داخل الجداول
        # ==========================================

        for table in tables:

            print(
                f"🔎 فحص جدول يحتوي على "
                f"{len(table)} صف"
            )

            # تحويل أسماء الأعمدة إلى نص
            table.columns = [
                str(col).strip()
                for col in table.columns
            ]

            for _, row in table.iterrows():

                row_text = " ".join(
                    str(value)
                    for value in row.values
                ).lower()

                # البحث عن Reverse Stock Split
                if (
                    "reverse stock split" in row_text
                    or "reverse split" in row_text
                ):

                    reverse_splits.append(row)

        # ==========================================
        # لا توجد نتائج
        # ==========================================

        if not reverse_splits:

            print(
                "❌ لم يتم العثور على Reverse Stock Split"
            )

            return []

        # ==========================================
        # عرض النتائج
        # ==========================================

        print("\n🟢 Reverse Splits المكتشفة:")
        print("-" * 60)

        for row in reverse_splits:

            print(row.to_string())

            print("-" * 60)

        return reverse_splits

    except Exception as e:

        print(
            f"❌ حدث خطأ أثناء جلب البيانات: {e}"
        )

        return []


# ==========================================
# تشغيل البرنامج
# ==========================================

if __name__ == "__main__":

    results = get_reverse_splits()

    print("\n")
    print("=" * 60)
    print("✅ انتهى البحث")
    print("=" * 60)

    print(
        f"📌 عدد عمليات Reverse Split المكتشفة: "
        f"{len(results)}"
    )
