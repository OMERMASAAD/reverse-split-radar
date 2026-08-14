# -*- coding: utf-8 -*-
"""
History Tracker - Reverse Split Radar
======================================

سكربت مستقل تمامًا عن strategy_scanner.py (لا يعدّل عليه ولا على منطق
القرار الحالي). مهمته فقط:

1) عندما يظهر سهم لأول مرة في نتائج الرادار (reverse_split_dashboard.json)
   يُسجَّل له سجل دائم في stock_history.json، ونقطة المرجع = الدعم
   العام المكتشف (support) في تلك اللحظة (كما تم الاتفاق).

2) كل تشغيل، لكل سهم ما زال "قيد المتابعة" (TRACKING) في السجل - حتى
   لو خرج من نطاق الرادار (20-50 يوم) - نجلب سعره الحالي فقط (بدون
   إعادة التحليل الكامل) ونحسب نسبة الصعود من نقطة المرجع.

3) عندما يصل السهم إلى +70% من الدعم = COMPLETED (حسب الهدف التشغيلي
   المتفق عليه في المشروع). إذا واصل حتى +100% تُسجَّل معلومة إضافية
   دون تغيير حالة الإكمال (تحققت أصلًا عند 70%).

4) إذا مرّ السهم أكثر من EXPIRE_AFTER_DAYS بدون تحقيق +70% => EXPIRED
   (يبقى في السجل لغرض الدراسة، لكن يتوقف عن الجلب اليومي).

5) في النهاية، يُبنى تقرير دراسة حالات مجمّع (case_study.json) من كل
   الأسهم التي أكملت الهدف: متوسط الأيام حتى النجاح، متوسط RSI/Score/
   Core عند الدخول، وأكثر الإشارات (signals) تكرارًا بين الحالات
   الناجحة - لغرض المراجعة اليدوية لاحقًا، دون أي تعديل تلقائي
   للاستراتيجية.
"""

import json
from datetime import datetime, date
from collections import Counter

import yfinance as yf

RADAR_RESULTS_FILE = "reverse_split_dashboard.json"
HISTORY_FILE = "stock_history.json"
CASE_STUDY_FILE = "case_study.json"

# هدف المتابعة الأساسي المعتمد في المشروع (لا تغييره بدون موافقة)
TARGET_GAIN_PERCENT = 70.0

# هدف إضافي اختياري لغرض الدراسة فقط (لا يغيّر حالة الإكمال)
STRETCH_GAIN_PERCENT = 100.0

# إذا لم يتحقق الهدف خلال هذه المدة، يُعتبر السهم منتهي المتابعة
# (رقم تشغيلي جديد لغرض التتبع فقط - وليس جزءًا من استراتيجية القرار)
EXPIRE_AFTER_DAYS = 120


def safe_float(x):
    try:
        if x is None:
            return None
        x = float(x)
        return None if x != x else x  # NaN check بدون الحاجة لـ numpy
    except Exception:
        return None


def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save_json(path, payload):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def load_radar_results():
    """
    يقرأ reverse_split_dashboard.json (مخرجات strategy_scanner.py
    الغنية) بدون أي تعديل عليها.
    """
    data = load_json(RADAR_RESULTS_FILE, {})
    return data.get("results", []) if isinstance(data, dict) else []


def get_live_price(ticker):
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period="5d", auto_adjust=False)

        if df is None or df.empty:
            return None

        price = safe_float(df["Close"].iloc[-1])
        return price

    except Exception as e:
        print(f"ERROR fetching price for {ticker}: {e}")
        return None


def register_new_entries(history, radar_results):
    """
    يضيف سجلًا جديدًا لأي سهم ظهر في نتائج الرادار ولم يُسجَّل من قبل.
    نقطة المرجع = support (الدعم العام المكتشف وقت الدخول).
    """

    today_str = date.today().isoformat()

    added = 0

    for r in radar_results:

        ticker = r.get("ticker")

        if not ticker or ticker in history:
            continue

        reference_price = safe_float(r.get("support"))

        if reference_price is None or reference_price <= 0:
            # لا نسجل سهمًا بلا نقطة دعم صالحة لحساب النسبة منها
            continue

        history[ticker] = {

            "ticker": ticker,

            "first_seen": today_str,

            "reference_type": "support",
            "reference_price": reference_price,

            "target_70_price": round(reference_price * 1.70, 6),
            "target_100_price": round(reference_price * 2.00, 6),

            # لقطة (Snapshot) لحالة السهم عند دخوله السجل - لغرض
            # دراسة الحالات لاحقًا فقط
            "entry_snapshot": {
                "price": safe_float(r.get("price")),
                "rsi": safe_float(r.get("rsi")),
                "score": r.get("score"),
                "score_percent": r.get("score_percent"),
                "core": r.get("core"),
                "rating": r.get("rating"),
                "next_step": r.get("next_step"),
                "support_tests": r.get("support_tests"),
                "signals": r.get("signals") or [],
            },

            "status": "TRACKING",

            "last_checked": today_str,
            "last_price": safe_float(r.get("price")),
            "max_price_since_entry": safe_float(r.get("price")),
            "max_gain_percent": None,

            "completed_70_date": None,
            "days_to_complete_70": None,

            "completed_100_date": None,
            "days_to_complete_100": None,

            "expired_date": None,
        }

        added += 1

    return added


def update_tracking_entries(history):
    """
    لكل سهم status == TRACKING: نجلب سعره الحالي ونحدّث النسبة،
    ونتحقق من تحقق الهدف أو انتهاء المهلة.
    """

    today = date.today()
    today_str = today.isoformat()

    checked = 0
    completed_70_now = []
    expired_now = []

    for ticker, rec in history.items():

        if rec.get("status") != "TRACKING":
            continue

        checked += 1

        price = get_live_price(ticker)

        rec["last_checked"] = today_str

        if price is None:
            # تعذر الجلب هذه المرة - لا نغيّر الحالة، نحاول المرة القادمة
            continue

        rec["last_price"] = price

        ref = rec.get("reference_price")

        if not ref or ref <= 0:
            continue

        gain_percent = ((price - ref) / ref) * 100.0

        prev_max = rec.get("max_price_since_entry")

        if prev_max is None or price > prev_max:
            rec["max_price_since_entry"] = price

        prev_max_gain = rec.get("max_gain_percent")

        if prev_max_gain is None or gain_percent > prev_max_gain:
            rec["max_gain_percent"] = round(gain_percent, 2)

        first_seen = datetime.fromisoformat(
            rec["first_seen"]
        ).date()

        days_since_entry = (today - first_seen).days

        # ---- تحقق هدف +70% (الهدف الأساسي المعتمد) ----
        if (
            gain_percent >= TARGET_GAIN_PERCENT
            and rec.get("completed_70_date") is None
        ):

            rec["completed_70_date"] = today_str
            rec["days_to_complete_70"] = days_since_entry
            rec["status"] = "COMPLETED"

            completed_70_now.append(ticker)

        # ---- هدف إضافي +100% (للدراسة فقط، لا يغيّر الحالة) ----
        if (
            gain_percent >= STRETCH_GAIN_PERCENT
            and rec.get("completed_100_date") is None
        ):

            rec["completed_100_date"] = today_str
            rec["days_to_complete_100"] = days_since_entry

        # ---- انتهاء المهلة بدون تحقيق الهدف ----
        if (
            rec["status"] == "TRACKING"
            and days_since_entry > EXPIRE_AFTER_DAYS
        ):

            rec["status"] = "EXPIRED"
            rec["expired_date"] = today_str

            expired_now.append(ticker)

    return checked, completed_70_now, expired_now


def build_case_study(history):
    """
    تقرير مجمّع من الأسهم التي أكملت الهدف (+70%) فقط - لغرض المراجعة
    اليدوية لاكتشاف الأنماط المتكررة. لا يُستخدم لتعديل أي شيء تلقائيًا.
    """

    completed = [
        rec for rec in history.values()
        if rec.get("status") == "COMPLETED"
    ]

    if not completed:

        return {
            "generated_at": datetime.now().isoformat(),
            "completed_count": 0,
            "note": "لا توجد حالات مكتملة بعد لدراستها.",
        }

    def avg(values):
        values = [v for v in values if v is not None]
        return round(sum(values) / len(values), 2) if values else None

    days_list = [
        rec.get("days_to_complete_70")
        for rec in completed
    ]

    rsi_list = [
        rec.get("entry_snapshot", {}).get("rsi")
        for rec in completed
    ]

    score_list = [
        rec.get("entry_snapshot", {}).get("score_percent")
        for rec in completed
    ]

    core_list = [
        rec.get("entry_snapshot", {}).get("core")
        for rec in completed
    ]

    support_tests_list = [
        rec.get("entry_snapshot", {}).get("support_tests")
        for rec in completed
    ]

    max_gain_list = [
        rec.get("max_gain_percent")
        for rec in completed
    ]

    # أكثر الإشارات (signals) تكرارًا بين الحالات الناجحة
    signal_counter = Counter()

    for rec in completed:

        for s in rec.get("entry_snapshot", {}).get("signals", []):
            signal_counter[s] += 1

    top_signals = [
        {"signal": s, "count": c}
        for s, c in signal_counter.most_common(10)
    ]

    return {

        "generated_at": datetime.now().isoformat(),

        "completed_count": len(completed),

        "avg_days_to_target_70": avg(days_list),

        "avg_entry_rsi": avg(rsi_list),
        "avg_entry_score_percent": avg(score_list),
        "avg_entry_core": avg(core_list),
        "avg_entry_support_tests": avg(support_tests_list),

        "avg_max_gain_percent": avg(max_gain_list),

        "top_recurring_signals_at_entry": top_signals,

        "tickers_completed": [
            rec["ticker"] for rec in completed
        ],
    }


def main():

    print("=" * 60)
    print("HISTORY TRACKER - Reverse Split Radar")
    print("=" * 60)

    history = load_json(HISTORY_FILE, {})

    radar_results = load_radar_results()

    added = register_new_entries(history, radar_results)

    print(f"أسهم جديدة أُضيفت للسجل التاريخي: {added}")

    checked, completed_now, expired_now = update_tracking_entries(
        history
    )

    print(f"أسهم تمت متابعتها هذا التشغيل: {checked}")

    if completed_now:
        print(
            f"🎯 وصلت لهدف +{TARGET_GAIN_PERCENT:.0f}% الآن: "
            f"{', '.join(completed_now)}"
        )

    if expired_now:
        print(
            f"⌛ انتهت مهلة المتابعة بدون تحقيق الهدف: "
            f"{', '.join(expired_now)}"
        )

    save_json(HISTORY_FILE, history)

    print(f"تم حفظ: {HISTORY_FILE}")

    case_study = build_case_study(history)

    save_json(CASE_STUDY_FILE, case_study)

    print(f"تم حفظ: {CASE_STUDY_FILE}")

    print("=" * 60)
    print("انتهى تحديث السجل التاريخي.")
    print("=" * 60)


if __name__ == "__main__":
    main()
