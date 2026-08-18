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
PATTERN_ANALYSIS_FILE = "pattern_analysis.json"

# هدف المتابعة الأساسي المعتمد في المشروع (لا تغييره بدون موافقة)
TARGET_GAIN_PERCENT = 70.0

# أهداف إضافية اختيارية لغرض الدراسة فقط (لا تغيّر حالة الإكمال)
STRETCH_GAIN_PERCENT_100 = 100.0
STRETCH_GAIN_PERCENT_200 = 200.0

# سقف المتابعة: شهران (60 يومًا). إذا لم يحقق +70% خلالها = فشل
# (يُدرَس لاحقًا ضمن صفحة "ما الذي يتكرر؟")
EXPIRE_AFTER_DAYS = 60

# أقصى عدد نقاط يومية تُحفظ لكل سهم (يطابق سقف المتابعة + هامش)
MAX_DAILY_LOG_POINTS = 65


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

    يحفظ بطاقة كاملة لحالة السهم لحظة الرصد (كل ما هو متاح من
    strategy_scanner.py) لغرض دراسة الحالات لاحقًا - دون التأثير
    على أي قرار حي.
    """

    now = datetime.now()
    today_str = now.date().isoformat()

    added = 0

    for r in radar_results:

        ticker = r.get("ticker")

        if not ticker or ticker in history:
            continue

        reference_price = safe_float(r.get("support"))

        if reference_price is None or reference_price <= 0:
            # لا نسجل سهمًا بلا نقطة دعم صالحة لحساب النسبة منها
            continue

        entry_price = safe_float(r.get("price"))

        distance_from_support_pct = None

        if entry_price is not None and reference_price > 0:
            distance_from_support_pct = round(
                ((entry_price - reference_price) / reference_price) * 100,
                2
            )

        top_signals = (r.get("signals") or [])[:3]

        entry_reason = (
            " / ".join(top_signals)
            if top_signals
            else "لا توجد إشارات دخول محددة مسجّلة"
        )

        entry_snapshot = {

            "price": entry_price,
            "distance_from_support_pct": distance_from_support_pct,

            "split_date": r.get("split_date"),
            "split_ratio": r.get("split_ratio"),
            "days_since_split": r.get("days_since_split"),

            "float_shares": r.get("float_shares"),
            "short_shares": r.get("short_shares"),

            "rsi": safe_float(r.get("rsi")),
            "previous_rsi": safe_float(r.get("previous_rsi")),
            "rsi_improving": r.get("rsi_improving"),

            "macd": safe_float(r.get("macd")),
            "macd_improving": r.get("macd_improving"),

            "ma20": safe_float(r.get("ma20")),
            "ma50": safe_float(r.get("ma50")),

            "volume": safe_float(r.get("volume")),
            "volume_ratio": safe_float(r.get("volume_ratio")),

            "support_tests": r.get("support_tests"),

            "half_tests": (r.get("half") or {}).get("tests"),
            "half_successful_tests":
                (r.get("half") or {}).get("successful_tests"),

            "score": r.get("score"),
            "score_percent": r.get("score_percent"),
            "core": r.get("core"),

            "rating": r.get("rating"),
            "next_step": r.get("next_step"),

            "signals": r.get("signals") or [],
            "warnings": r.get("warnings") or [],

            "entry_reason": entry_reason,
        }

        history[ticker] = {

            "ticker": ticker,

            "first_seen": today_str,
            "first_seen_datetime": now.isoformat(timespec="minutes"),

            "reference_type": "support",
            "reference_price": reference_price,

            "target_70_price": round(reference_price * 1.70, 6),
            "target_100_price": round(reference_price * 2.00, 6),
            "target_200_price": round(reference_price * 3.00, 6),

            "entry_snapshot": entry_snapshot,

            # سجل يومي زمني (يوم 1 -> يوم 2 -> ...) - نقطة واحدة
            # في اليوم كحد أقصى (آخر قراءة في نفس اليوم)
            "daily_log": [
                {
                    "date": today_str,
                    "price": entry_price,
                    "gain_pct": 0.0,
                }
            ],

            "status": "TRACKING",

            "last_checked": today_str,
            "last_price": entry_price,
            "max_price_since_entry": entry_price,
            "max_gain_percent": None,
            "days_to_peak": None,

            "reached_70": False,
            "completed_70_date": None,
            "days_to_complete_70": None,

            "reached_100": False,
            "completed_100_date": None,
            "days_to_complete_100": None,

            "reached_200": False,
            "completed_200_date": None,
            "days_to_complete_200": None,

            "expired_date": None,
            "failure_reason": None,

            "behavior_note": None,
        }

        added += 1

    return added


def generate_failure_reason(rec):
    """
    تشخيص مبسّط قائم على قواعد بسيطة (وليس ذكاءً معقدًا) لسبب
    عدم تحقيق الهدف - لغرض الدراسة اليدوية لاحقًا فقط.
    """

    gain = rec.get("max_gain_percent") or 0

    if gain < 10:
        return "لم يتحرك السهم عمليًا عن نقطة الدعم طوال فترة المتابعة (60 يومًا)."

    if gain < 40:
        return f"تحرك محدود فقط (أعلى صعود {gain:.1f}%) ولم يقترب من الهدف."

    return (
        f"اقترب من الهدف (أعلى صعود {gain:.1f}%) لكنه لم يكمله "
        f"خلال مهلة 60 يومًا."
    )


def generate_behavior_note(rec):
    """
    ملاحظة سلوكية نصية مبسّطة تُبنى من بيانات الدخول والنتيجة
    النهائية - لغرض القراءة اليدوية السريعة، وليست تحليلًا استنتاجيًا.
    """

    snap = rec.get("entry_snapshot", {})

    parts = []

    tests = snap.get("support_tests")

    if tests:
        parts.append(f"اختُبر الدعم {tests} مرة/مرات عند الدخول")

    rsi = snap.get("rsi")

    if rsi is not None:

        rsi_txt = f"RSI عند الدخول {rsi:.1f}"

        if snap.get("rsi_improving"):
            rsi_txt += " (كان يتحسن)"

        parts.append(rsi_txt)

    if snap.get("macd_improving"):
        parts.append("MACD كان يتحسن عند الدخول")

    gain = rec.get("max_gain_percent")

    if gain is not None:

        peak_txt = f"وصل لأعلى ارتفاع {gain:.1f}%"

        days_peak = rec.get("days_to_peak")

        if days_peak is not None:
            peak_txt += f" خلال {days_peak} يوم"

        parts.append(peak_txt)

    if not parts:
        return "بيانات غير كافية لصياغة ملاحظة سلوكية."

    return "، ".join(parts) + "."


def update_tracking_entries(history):
    """
    لكل سهم status == TRACKING: نجلب سعره الحالي، نحدّث النسبة
    والسجل اليومي الزمني، ونتحقق من تحقق الأهداف (+70/+100/+200%)
    أو انتهاء مهلة المتابعة (60 يومًا = فشل يُدرَس لاحقًا).
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

        first_seen = datetime.fromisoformat(
            rec["first_seen"]
        ).date()

        days_since_entry = (today - first_seen).days

        # ---- تحديث السجل اليومي الزمني (نقطة واحدة كحد أقصى/يوم) ----

        daily_log = rec.setdefault("daily_log", [])

        if daily_log and daily_log[-1]["date"] == today_str:

            daily_log[-1]["price"] = price
            daily_log[-1]["gain_pct"] = round(gain_percent, 2)

        else:

            daily_log.append({
                "date": today_str,
                "price": price,
                "gain_pct": round(gain_percent, 2),
            })

        if len(daily_log) > MAX_DAILY_LOG_POINTS:
            rec["daily_log"] = daily_log[-MAX_DAILY_LOG_POINTS:]

        # ---- أعلى سعر / أعلى نسبة صعود / يوم القمة ----

        prev_max = rec.get("max_price_since_entry")

        if prev_max is None or price > prev_max:
            rec["max_price_since_entry"] = price

        prev_max_gain = rec.get("max_gain_percent")

        if prev_max_gain is None or gain_percent > prev_max_gain:

            rec["max_gain_percent"] = round(gain_percent, 2)
            rec["days_to_peak"] = days_since_entry

        # ---- تحقق هدف +70% (الهدف الأساسي المعتمد) ----
        if (
            gain_percent >= TARGET_GAIN_PERCENT
            and rec.get("completed_70_date") is None
        ):

            rec["reached_70"] = True
            rec["completed_70_date"] = today_str
            rec["days_to_complete_70"] = days_since_entry
            rec["status"] = "COMPLETED"

            completed_70_now.append(ticker)

        # ---- هدف إضافي +100% (للدراسة فقط) ----
        if (
            gain_percent >= STRETCH_GAIN_PERCENT_100
            and rec.get("completed_100_date") is None
        ):

            rec["reached_100"] = True
            rec["completed_100_date"] = today_str
            rec["days_to_complete_100"] = days_since_entry

        # ---- هدف إضافي +200% (للدراسة فقط) ----
        if (
            gain_percent >= STRETCH_GAIN_PERCENT_200
            and rec.get("completed_200_date") is None
        ):

            rec["reached_200"] = True
            rec["completed_200_date"] = today_str
            rec["days_to_complete_200"] = days_since_entry

        # ---- انتهاء المهلة بدون تحقيق الهدف (فشل يُدرَس لاحقًا) ----
        if (
            rec["status"] == "TRACKING"
            and days_since_entry >= EXPIRE_AFTER_DAYS
        ):

            rec["status"] = "EXPIRED"
            rec["expired_date"] = today_str
            rec["failure_reason"] = generate_failure_reason(rec)

            expired_now.append(ticker)

        # ---- الملاحظة السلوكية تُحدَّث دائمًا عند أي تغيير حالة ----
        if rec["status"] in ("COMPLETED", "EXPIRED"):
            rec["behavior_note"] = generate_behavior_note(rec)

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


# حد أدنى لحجم كل مجموعة (ناجحة/فاشلة) قبل توليد أي توصية - لتفادي
# استنتاجات مضلِّلة من عينة صغيرة جدًا
MIN_SAMPLE_FOR_RECOMMENDATION = 8

# أقل فارق نسبة مئوية بين المجموعتين ليُعتبر "فرقًا حقيقيًا يستحق الذكر"
MIN_PERCENT_GAP = 30.0

# أقل فارق نسبي (%) بين متوسطين رقميين ليُعتبر ملحوظًا
MIN_RELATIVE_DIFF = 25.0


def generate_recommendations(success, failure):
    """
    يقارن كل مقياس بين المجموعة الناجحة والفاشلة، ويولّد جملًا
    نصية بسيطة عند وجود فرق حقيقي وملحوظ فقط.

    مهم جدًا: هذه توصيات نصية للمراجعة اليدوية فقط - لا تُطبَّق
    تلقائيًا على أي شرط أو معادلة في الاستراتيجية.
    """

    if not success or not failure:
        return {
            "ready": False,
            "reason": "لا توجد بيانات كافية بعد (يحتاج حالات ناجحة وفاشلة معًا).",
            "items": [],
        }

    if (
        success["count"] < MIN_SAMPLE_FOR_RECOMMENDATION
        or failure["count"] < MIN_SAMPLE_FOR_RECOMMENDATION
    ):
        return {
            "ready": False,
            "reason": (
                f"العينة ما زالت صغيرة (ناجحة: {success['count']}، "
                f"فاشلة: {failure['count']}) - يحتاج {MIN_SAMPLE_FOR_RECOMMENDATION} "
                f"على الأقل من كل نوع لتوصية موثوقة. استمر بالتشغيل."
            ),
            "items": [],
        }

    items = []

    # ---- مقاييس نسبة مئوية (RSI/MACD يتحسن، وصل +100%/+200%) ----

    percent_metrics = [
        ("rsi_improving_percent", "RSI يتحسن عند الدخول"),
        ("macd_improving_percent", "MACD يتحسن عند الدخول"),
        ("reached_100_percent", "الوصول لاحقًا إلى +100%"),
        ("reached_200_percent", "الوصول لاحقًا إلى +200%"),
    ]

    for key, label in percent_metrics:

        s_val = success.get(key)
        f_val = failure.get(key)

        if s_val is None or f_val is None:
            continue

        gap = s_val - f_val

        if abs(gap) >= MIN_PERCENT_GAP:

            direction = "أعلى بكثير" if gap > 0 else "أقل بكثير"

            items.append({
                "metric": label,
                "text": (
                    f"«{label}» {direction} في الحالات الناجحة "
                    f"({s_val}%) مقارنة بالفاشلة ({f_val}%) - "
                    f"فرق {abs(round(gap,1))} نقطة مئوية."
                ),
            })

    # ---- مقاييس رقمية (متوسطات) ----

    numeric_metrics = [
        ("avg_entry_rsi", "RSI عند الدخول"),
        ("avg_entry_support_tests", "عدد اختبارات الدعم"),
        ("avg_entry_rebounds", "عدد الارتدادات الناجحة"),
        ("avg_entry_volume_ratio", "نسبة الحجم عند الدخول"),
    ]

    for key, label in numeric_metrics:

        s_val = success.get(key)
        f_val = failure.get(key)

        if s_val is None or f_val is None or f_val == 0:
            continue

        relative_diff = ((s_val - f_val) / abs(f_val)) * 100

        if abs(relative_diff) >= MIN_RELATIVE_DIFF:

            direction = "أعلى" if relative_diff > 0 else "أقل"

            items.append({
                "metric": label,
                "text": (
                    f"متوسط «{label}» في الحالات الناجحة ({s_val}) "
                    f"{direction} من الفاشلة ({f_val}) بفارق نسبي "
                    f"{abs(round(relative_diff,1))}%."
                ),
            })

    # ---- إشارات (signals) متكررة بفارق واضح بين المجموعتين ----

    success_signals = {
        s["signal"]: s["percent"]
        for s in success.get("top_signals", [])
    }

    failure_signals = {
        s["signal"]: s["percent"]
        for s in failure.get("top_signals", [])
    }

    for signal, s_pct in success_signals.items():

        f_pct = failure_signals.get(signal, 0)

        if s_pct >= 60 and (s_pct - f_pct) >= MIN_PERCENT_GAP:

            items.append({
                "metric": f"إشارة: {signal}",
                "text": (
                    f"إشارة «{signal}» ظهرت في {s_pct}% من الحالات "
                    f"الناجحة مقابل {f_pct}% فقط من الفاشلة - "
                    f"يستحق دراسة إعطائها وزنًا أعلى في Score."
                ),
            })

    return {
        "ready": True,
        "reason": None,
        "items": items,
        "disclaimer": (
            "هذه ملاحظات إحصائية وصفية للمراجعة اليدوية فقط - لا "
            "تُطبَّق تلقائيًا على أي شرط أو معادلة في الاستراتيجية."
        ),
    }


def build_pattern_analysis(history):
    """
    صفحة "ما الذي يتكرر؟" - تقارن مجموعتين: الناجحة (COMPLETED)
    مقابل الفاشلة (EXPIRED)، وتبحث عن الفروقات الإحصائية بينهما.

    مهم: هذا تقرير وصفي للمراجعة اليدوية فقط - لا يُستخدم لتعديل
    أي شرط أو معادلة في الاستراتيجية تلقائيًا (بحسب الاتفاق:
    "نخلي النظام يعمل شهر إلى شهرين ويسجل، بعدها نستخدم البيانات
    الفعلية لتطوير الشروط يدويًا").
    """

    completed = [
        rec for rec in history.values()
        if rec.get("status") == "COMPLETED"
    ]

    expired = [
        rec for rec in history.values()
        if rec.get("status") == "EXPIRED"
    ]

    def avg(values):
        values = [v for v in values if v is not None]
        return round(sum(values) / len(values), 2) if values else None

    def pct(count, total):
        return round((count / total) * 100, 1) if total else None

    def cohort_stats(group):

        if not group:
            return None

        rsi_list = [
            r.get("entry_snapshot", {}).get("rsi") for r in group
        ]

        score_list = [
            r.get("entry_snapshot", {}).get("score_percent")
            for r in group
        ]

        core_list = [
            r.get("entry_snapshot", {}).get("core") for r in group
        ]

        support_tests_list = [
            r.get("entry_snapshot", {}).get("support_tests")
            for r in group
        ]

        rebound_list = [
            r.get("entry_snapshot", {}).get("half_successful_tests")
            for r in group
        ]

        volume_ratio_list = [
            r.get("entry_snapshot", {}).get("volume_ratio")
            for r in group
        ]

        rsi_improving_count = sum(
            1 for r in group
            if r.get("entry_snapshot", {}).get("rsi_improving")
        )

        macd_improving_count = sum(
            1 for r in group
            if r.get("entry_snapshot", {}).get("macd_improving")
        )

        max_gain_list = [r.get("max_gain_percent") for r in group]

        reached_100_count = sum(
            1 for r in group if r.get("reached_100")
        )

        reached_200_count = sum(
            1 for r in group if r.get("reached_200")
        )

        signal_counter = Counter()

        for r in group:
            for s in r.get("entry_snapshot", {}).get("signals", []):
                signal_counter[s] += 1

        top_signals = [
            {
                "signal": s,
                "count": c,
                "percent": pct(c, len(group)),
            }
            for s, c in signal_counter.most_common(8)
        ]

        return {

            "count": len(group),

            "avg_entry_rsi": avg(rsi_list),
            "avg_entry_score_percent": avg(score_list),
            "avg_entry_core": avg(core_list),
            "avg_entry_support_tests": avg(support_tests_list),
            "avg_entry_rebounds": avg(rebound_list),
            "avg_entry_volume_ratio": avg(volume_ratio_list),

            "rsi_improving_percent":
                pct(rsi_improving_count, len(group)),

            "macd_improving_percent":
                pct(macd_improving_count, len(group)),

            "avg_max_gain_percent": avg(max_gain_list),

            "reached_100_percent":
                pct(reached_100_count, len(group)),

            "reached_200_percent":
                pct(reached_200_count, len(group)),

            "top_signals": top_signals,
        }

    success_stats = cohort_stats(completed)
    failure_stats = cohort_stats(expired)

    total_finished = len(completed) + len(expired)

    recommendations = generate_recommendations(
        success_stats, failure_stats
    )

    return {

        "generated_at": datetime.now().isoformat(),

        "completed_count": len(completed),
        "expired_count": len(expired),

        "success_rate_percent": pct(len(completed), total_finished),

        "success": success_stats,
        "failure": failure_stats,

        "recommendations": recommendations,

        "note": (
            "تقرير وصفي للمراجعة اليدوية فقط - لا يُستخدم لتعديل "
            "أي شرط في الاستراتيجية تلقائيًا."
        ),
    }


def main():

    print("=" * 60)
    print("HISTORY TRACKER - Reverse Split Radar")
    print("=" * 60)

    history = load_json(HISTORY_FILE, {})

    radar_results = load_radar_results()

    # ملاحظة مهمة: نتحقق من الأسهم الموجودة مسبقًا أولًا، ثم نسجّل
    # الجديدة بعدها. بهذا الترتيب لا يُفحص أي سهم جديد لتحقيق الهدف
    # في نفس تشغيل تسجيله (كان هذا يُنتج "تحقق الهدف خلال 0 يوم"
    # بشكل كاذب لأن السهم غالبًا يكون قد بدأ التعافي فعلًا قبل أن
    # يرصده النظام لأول مرة - يشوّه متوسط "الأيام حتى الهدف").

    checked, completed_now, expired_now = update_tracking_entries(
        history
    )

    print(f"أسهم تمت متابعتها هذا التشغيل: {checked}")

    added = register_new_entries(history, radar_results)

    print(f"أسهم جديدة أُضيفت للسجل التاريخي: {added}")

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

    pattern_analysis = build_pattern_analysis(history)

    save_json(PATTERN_ANALYSIS_FILE, pattern_analysis)

    print(f"تم حفظ: {PATTERN_ANALYSIS_FILE}")

    print("=" * 60)
    print("انتهى تحديث السجل التاريخي.")
    print("=" * 60)


if __name__ == "__main__":
    main()
