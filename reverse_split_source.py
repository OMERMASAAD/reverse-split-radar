import os
import requests
from datetime import datetime, timedelta


# ==========================================
# إعدادات الرادار
# ==========================================

MIN_DAYS = 20
MAX_DAYS = 50

API_URL = "https://data.businessquant.com/corporate_actions"


# ==========================================
# جلب Reverse Splits من BusinessQuant
# ==========================================

def get_reverse_splits():

    print("=" * 60)
    print("🚨 REVERSE SPLIT RADAR")
    print("=" * 60)

    api_key = os.getenv("BUSINESSQUANT_API_KEY")

    if not api_key:
        print("❌ لم يتم العثور على BUSINESSQUANT_API_KEY")
        return []

    today = datetime.now().date()

    start_date = today - timedelta(days=MAX_DAYS)
    end_date = today - timedelta(days=MIN_DAYS)

    print(f"📅 البحث من: {start_date}")
    print(f"📅 إلى:     {end_date}")

    params = {
        "action": "split",
        "from_date": str(start_date),
        "till_date": str(end_date),
        "limit": 10000,
        "api_key": api_key,
    }

    try:

        response = requests.get(
            API_URL,
            params=params,
            timeout=30
        )

        response.raise_for_status()

        result = response.json()

        data = result.get("data", [])

        print(
            f"📊 عدد عمليات التقسيم التي رجعها المصدر: "
            f"{len(data)}"
        )

        candidates = []

        # ======================================
        # فحص العمليات
        # ======================================

        for item in data:

            ticker = str(
                item.get("ticker", "")
            ).strip().upper()

            action = str(
                item.get("action", "")
            ).strip().lower()

            notes = str(
                item.get("notes", "")
            ).strip().lower()

            date_text = str(
                item.get("date", "")
            ).strip()

            # ==================================
            # نريد فقط عمليات Split
            # ==================================

            if action != "split":
                continue

            # ==================================
            # التمييز بين Reverse Split
            # ==================================

            if "reverse split" not in notes:
                continue

            # ==================================
            # التاريخ
            # ==================================

            try:

                split_date = datetime.strptime(
                    date_text,
                    "%Y-%m-%d"
                ).date()

            except Exception:

                continue

            days_passed = (
                today - split_date
            ).days

            # ==================================
            # التأكد من شرط 20 - 50 يوم
            # ==================================

            if MIN_DAYS <= days_passed <= MAX_DAYS:

                candidates.append({
                    "symbol": ticker,
                    "split_date": str(split_date),
                    "days": days_passed,
                    "notes": item.get("notes", ""),
                    "company": item.get("name", "")
                })

        # ==========================================
        # إزالة التكرار
        # ==========================================

        unique = {}

        for stock in candidates:

            unique[stock["symbol"]] = stock

        candidates = list(
            unique.values()
        )

        # ==========================================
        # عرض النتائج
        # ==========================================

        print()
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
                    f"{stock['notes']}"
                )

        print()
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
# التشغيل
# ==========================================

if __name__ == "__main__":

    get_reverse_splits()
