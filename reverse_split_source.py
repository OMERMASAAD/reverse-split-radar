import os
import json
import requests
from datetime import datetime, timedelta


# ==========================================
# إعدادات الرادار
# ==========================================

MIN_DAYS = 20
MAX_DAYS = 50

API_URL = "https://data.businessquant.com/corporate_actions"

OUTPUT_FILE = "reverse_split_candidates.json"


# ==========================================
# الرموز التي لا نريدها
# ==========================================

def valid_symbol(symbol):

    symbol = symbol.strip().upper()

    if not symbol:
        return False

    # استبعاد رموز OTC التي تنتهي بـ F
    if symbol.endswith("F"):
        return False

    # نسمح فقط بحروف وأرقام
    if not symbol.isalnum():
        return False

    return True


# ==========================================
# جلب Reverse Splits
# ==========================================

def get_reverse_splits():

    print("=" * 60)
    print("🚨 REVERSE SPLIT RADAR")
    print("=" * 60)

    api_key = os.getenv("BUSINESSQUANT_API_KEY")

    if not api_key:

        print(
            "❌ لم يتم العثور على "
            "BUSINESSQUANT_API_KEY"
        )

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
        # فحص البيانات
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
            ).strip()

            date_text = str(
                item.get("date", "")
            ).strip()

            # -------------------------------
            # التأكد من الرمز
            # -------------------------------

            if not valid_symbol(ticker):
                continue

            # -------------------------------
            # نريد Split فقط
            # -------------------------------

            if action != "split":
                continue

            # -------------------------------
            # نريد Reverse Split فقط
            # -------------------------------

            if "reverse split" not in notes.lower():
                continue

            # -------------------------------
            # تحويل التاريخ
            # -------------------------------

            try:

                split_date = datetime.strptime(
                    date_text,
                    "%Y-%m-%d"
                ).date()

            except Exception:

                continue

            # -------------------------------
            # حساب عمر التقسيم
            # -------------------------------

            days_passed = (
                today - split_date
            ).days

            if not (
                MIN_DAYS
                <= days_passed
                <= MAX_DAYS
            ):
                continue

            # -------------------------------
            # إضافة السهم
            # -------------------------------

            candidates.append({

                "symbol": ticker,

                "split_date": str(
                    split_date
                ),

                "days": days_passed,

                "reverse_split": notes,

                "company": str(
                    item.get("name", "")
                ),

            })

        # ======================================
        # إزالة التكرار
        # ======================================

        unique = {}

        for stock in candidates:

            unique[
                stock["symbol"]
            ] = stock

        candidates = list(
            unique.values()
        )

        # ترتيب حسب عمر التقسيم
        candidates.sort(
            key=lambda x: (
                x["days"],
                x["symbol"]
            )
        )

        # ======================================
        # حفظ القائمة
        # ======================================

        with open(
            OUTPUT_FILE,
            "w",
            encoding="utf-8"
        ) as file:

            json.dump(
                candidates,
                file,
                ensure_ascii=False,
                indent=2
            )

        # ======================================
        # عرض النتائج
        # ======================================

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
                    f"التقسيم: "
                    f"{stock['split_date']} | "
                    f"العمر: "
                    f"{stock['days']} يوم | "
                    f"{stock['reverse_split']}"
                )

        print()
        print("=" * 60)

        print(
            f"📌 عدد الأسهم المؤهلة: "
            f"{len(candidates)}"
        )

        print(
            f"💾 تم حفظ القائمة في: "
            f"{OUTPUT_FILE}"
        )

        print("=" * 60)

        return candidates

    except Exception as e:

        print(
            f"❌ حدث خطأ أثناء جلب البيانات: "
            f"{e}"
        )

        return []


# ==========================================
# التشغيل
# ==========================================

if __name__ == "__main__":

    get_reverse_splits()
