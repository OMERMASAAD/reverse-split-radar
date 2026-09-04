import os
import json
import requests
from datetime import datetime, timedelta


# ==========================================
# إعدادات الدراسة
# ==========================================

LOOKBACK_DAYS = 90

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

    print("=" * 70)
    print("🧠 REVERSE SPLIT HISTORICAL RESEARCH")
    print("=" * 70)

    api_key = os.getenv("BUSINESSQUANT_API_KEY")

    if not api_key:

        print(
            "❌ لم يتم العثور على "
            "BUSINESSQUANT_API_KEY"
        )

        return []

    today = datetime.now().date()

    # ======================================
    # آخر 90 يوم
    # ======================================

    start_date = today - timedelta(
        days=LOOKBACK_DAYS
    )

    end_date = today

    print(
        f"📅 فترة الدراسة: آخر "
        f"{LOOKBACK_DAYS} يوم"
    )

    print(
        f"📅 من: {start_date}"
    )

    print(
        f"📅 إلى: {end_date}"
    )

    params = {

        "action": "split",

        "from_date":
            str(start_date),

        "till_date":
            str(end_date),

        "limit":
            10000,

        "api_key":
            api_key,
    }

    try:

        response = requests.get(
            API_URL,
            params=params,
            timeout=30
        )

        response.raise_for_status()

        result = response.json()

        data = result.get(
            "data",
            []
        )

        print(
            f"📊 إجمالي عمليات التقسيم "
            f"من المصدر: {len(data)}"
        )

        candidates = []

        # ======================================
        # فحص البيانات
        # ======================================

        for item in data:

            ticker = str(
                item.get(
                    "ticker",
                    ""
                )
            ).strip().upper()

            action = str(
                item.get(
                    "action",
                    ""
                )
            ).strip().lower()

            notes = str(
                item.get(
                    "notes",
                    ""
                )
            ).strip()

            date_text = str(
                item.get(
                    "date",
                    ""
                )
            ).strip()

            company = str(
                item.get(
                    "name",
                    ""
                )
            ).strip()

            # ----------------------------------
            # التأكد من الرمز
            # ----------------------------------

            if not valid_symbol(ticker):
                continue

            # ----------------------------------
            # نريد Split فقط
            # ----------------------------------

            if action != "split":
                continue

            # ----------------------------------
            # نريد Reverse Split فقط
            # ----------------------------------

            if (
                "reverse split"
                not in notes.lower()
            ):
                continue

            # ----------------------------------
            # تحويل التاريخ
            # ----------------------------------

            try:

                split_date = datetime.strptime(
                    date_text,
                    "%Y-%m-%d"
                ).date()

            except Exception:

                continue

            # ----------------------------------
            # حساب عمر التقسيم
            # ----------------------------------

            days_passed = (
                today - split_date
            ).days

            # ----------------------------------
            # التأكد أنه داخل آخر 90 يوم
            # ----------------------------------

            if (
                days_passed < 0
                or days_passed > LOOKBACK_DAYS
            ):
                continue

            # ----------------------------------
            # إضافة السهم
            # ----------------------------------

            candidates.append({

                "ticker":
                    ticker,

                "symbol":
                    ticker,

                "split_date":
                    str(split_date),

                "days":
                    days_passed,

                "reverse_split":
                    notes,

                "company":
                    company,

            })

        # ======================================
        # إزالة التكرار
        # ======================================

        unique = {}

        for stock in candidates:

            key = (
                stock["ticker"],
                stock["split_date"]
            )

            unique[key] = stock

        candidates = list(
            unique.values()
        )

        # ======================================
        # ترتيب حسب تاريخ التقسيم
        # الأقدم أولاً للدراسة التاريخية
        # ======================================

        candidates.sort(
            key=lambda x: (
                x["split_date"],
                x["ticker"]
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
        print("=" * 70)
        print("📚 Reverse Splits داخل آخر 90 يوم")
        print("=" * 70)

        if not candidates:

            print(
                "⚪ لم يتم العثور على "
                "Reverse Splits"
            )

        else:

            for stock in candidates:

                print(
                    f"🟢 {stock['ticker']} | "
                    f"التقسيم: "
                    f"{stock['split_date']} | "
                    f"العمر: "
                    f"{stock['days']} يوم | "
                    f"{stock['reverse_split']}"
                )

        print()
        print("=" * 70)

        print(
            f"📌 عدد Reverse Splits للدراسة: "
            f"{len(candidates)}"
        )

        print(
            f"💾 تم حفظ البيانات في: "
            f"{OUTPUT_FILE}"
        )

        print("=" * 70)

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
