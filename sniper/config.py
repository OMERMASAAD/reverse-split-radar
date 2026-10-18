# -*- coding: utf-8 -*-
"""
إعدادات «رادار قنص الذعر» — مصدر الحقيقة الوحيد لكل الأرقام.

الأرقام في قسم «الشروط الأصلية» مطابقة حرفيًا لمنطق قنص الذعر في stouk-bot
(panic_scanner.py) حتى تبقى الإشارة نفسها. كل ما بعد قسم «التطويرات» إضافات
تحليلية لا تغيّر تعريف الإشارة المكتملة (complete).
V2: تعديل فلتر الهبوط + كشف موجة الصعود + إشارة مبكرة + نظام حالات الكسر الكاذب
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from zoneinfo import ZoneInfo


def _env(name: str, default: float) -> float:
    """قراءة رقم من متغير بيئة مع الرجوع للقيمة الافتراضية."""
    try:
        return float(os.environ[name])
    except (KeyError, TypeError, ValueError):
        return float(default)

# ---------------------------------------------------------------- الملفات
UNIVERSE_FILE = "universe.json"
OUT_FILE = "panic_data.json"
STATS_FILE = "panic_stats.json"
FLOAT_CACHE_FILE = "float_cache.json"
REVERSE_SPLIT_TAG_FILE = "reverse_split_candidates.json"  # اختياري: وسم التجزئة العكسية

MARKET_TZ = ZoneInfo("America/New_York")

# =============================================== الشروط الأصلية (ثابتة)
# ── الرجل الأولى: السهم يجب أن يكون قد صعد أولًا بحجم عالي قبل أن ينهار
RUNUP_MIN_PCT = float(_env("RUNUP_MIN_PCT", 100.0))       # من قاع ما قبل القمة إلى قمة اليوم
RUNUP_VOLUME_MIN = float(_env("RUNUP_VOLUME_MIN", 1.5))   # حجم الصعود ÷ حجم ما قبله

# ── فلتر الهبوط V2: لا استبعاد لمجرد العمق — الهبوط العميق 30-80% جزء من الاستراتيجية
DROP_MAX_PCT = -30.0      # هبوط ≥ 30% من قمة الموجة (القمة الصحيحة للحركة)
DROP_MIN_PCT = float(_env("DROP_MIN_PCT", -100.0))   # V2: إلغاء حد الاستبعاد الثابت (كان -50%) — لا استبعاد بسبب العمق وحده
# تصنيف عمق التراجع للتحليل فقط (ليست شروط استبعاد)
DROP_CATEGORIES = [
    (30, 40, "30–40%"),
    (40, 60, "40–60%"),
    (60, 80, "60–80%"),
    (80, 100, "80%+"),
]
DROP_CATEGORY_LABELS = ["30–40%", "40–60%", "60–80%", "80%+"]

def drop_category(abs_drop: float) -> str:
    """تصنيف الهبوط للتحليل — لا يؤثر على الاستبعاد."""
    if abs_drop is None:
        return "غير معروف"
    v = abs(float(abs_drop))
    if v < 30:
        return "<30% (اكتشاف مبكر)"
    if v <= 40:
        return "30–40%"
    if v <= 60:
        return "40–60%"
    if v <= 80:
        return "60–80%"
    return "80%+"

CONS_RANGE_PCT = 5.0      # أقصى تذبذب مسموح داخل الثبات الأفقي
CONS_MIN_MIN = 60         # أقل مدة ثبات (دقيقة)
NEAR_LOW_PCT = 5.0        # قاع الثبات ضمن 5% من أدنى قاع اليوم
RSI_PERIOD = 14
RSI_OVERSOLD = 30.0       # RSI لامس ≤ 30 خلال النافذة
RSI_EXIT = 25.0           # RSI الآن ≥ 25 (خرج من التشبع)
RSI_LOOK = 24             # آخر 24 شمعة 5m = ساعتان
RSI_RECOVERY_MIN = 3.0    # تحسّن RSI ≥ 3 نقاط
RSI_PULLBACK_MIN = 25.0   # تراجع RSI ≥ 25 نقطة من قمته خلال اليوم
RSI_STRENGTH_MAX = 60.0   # ولا يكون قد عاد إلى منطقة القوة
OBV_LOOK = 12
MACD_FAST, MACD_SLOW, MACD_SIGNAL = 12, 26, 9
MACD_CROSS_LOOK = 3       # تقاطع خلال آخر 3 شموع
CMF_PERIOD = 20           # نافذة Chaikin Money Flow (تدفق المال) — فوق الصفر = تجميع سيولة
TARGET_PCT = 20.0         # الهدف الأول المعروض
STALE_MIN = 60            # آخر شمعة أقدم من ساعة ⇒ سهم متوقف
DEAD_AFTER_MISSES = 3     # انقطاع بيانات 3 مسوحات متتالية ⇒ حالة «متوقف»
CHUNK = 100               # حجم الدفعة في التحميل الجماعي
MIN_BARS = 30             # أقل عدد شموع 5m للتحليل
MIN_DAY_BARS = 12         # أقل عدد شموع داخل جلسة اليوم

# أوزان درجة القوة (مجموعها 100) — مطابقة للأصل
WEIGHTS = {"base": 35, "rsi": 20, "obv": 20, "macd": 15}
NEAR_LOW_BONUS = 10

# =============================================== التطويرات (إضافية)
ATR_PERIOD = 14
EMA_FAST, EMA_SLOW = 9, 20
VWAP_ANCHOR_BASE = True        # VWAP مرتكز من بداية الثبات
BASE_VOLUME_LOOK = 24          # شموع ما قبل القاع لمقارنة جفاف الحجم
FLOW_LOOK = 18                 # نافذة تحليل التدفق (دلتا الحجم / CLV)
MTF_RESAMPLE = "15min"         # الفريم الأعلى للتأكيد
MTF_HIGHER_LOW_LOOK = 6
BASE_TOUCH_TOL_PCT = 0.6       # اعتبار اللمسة ضمن 0.6% من قاع الثبات
ROUND_NUMBER_STEP = 0.5        # خطوة الأرقام المستديرة (مغناطيس سعري)
GAP_MIN_PCT = 1.0              # أقل فجوة تُعدّ فجوة

# --- محرك المخاطر (ورقي)
ATR_STOP_MULT = float(_env("ATR_STOP_MULT", 1.0))
STOP_BUFFER_PCT = float(_env("STOP_BUFFER_PCT", 5.0))    # الوقف = قاع الثبات − 5% (حسب الطلب)
STOP_MIN_BUFFER_PCT = STOP_BUFFER_PCT
# V2: الشطب لم يعد آليًا عند كسر القاع بـ 5% — يُستبدل بنظام حالات السحب الكاذب
PURGE_BREAK_PCT = float(_env("PURGE_BREAK_PCT", STOP_BUFFER_PCT))
# المسافة القصوى المسموحة تحت القاع قبل اعتبار الحالة INVALIDATED موضوعيًا (افتراضي 15% تحت القاع المرجعي + استمرار البيع)
INVALIDATED_BREAK_PCT = float(_env("INVALIDATED_BREAK_PCT", 15.0))
SWEEP_EXPIRY_MIN = int(_env("SWEEP_EXPIRY_MIN", 390))  # انتهاء صلاحية مراقبة الكسر إن لم يحدث استعادة
TARGETS_PCT = (10.0, 20.0, 30.0)  # V2: إضافة +10% كهـدف أول ورقي، مع الحفاظ على +20% و+30%

# إدارة الصفقة بعد تحقق الهدف الأول
MOVE_STOP_TO_BREAK_EVEN = True    # بعد T1 ينتقل الوقف إلى سعر الدخول (بلا مخاطرة)
TRAIL_AFTER_T1_PCT = None         # رقم (مثلاً 5.0) يفعّل وقفًا متحركًا تحت أعلى قمة — None = معطّل
TRACK_BREAKOUT_ENTRY = True       # رصد وضع «اختراق قمة القاعدة» كصفقة ورقية مستقلة
ACCOUNT_EQUITY = 25_000.0      # حساب ورقي مرجعي لحجم المركز
RISK_PER_TRADE_PCT = 1.0       # مخاطرة 1% لكل إشارة

# --- متتبع النتائج (Paper)
MAX_HOLD_MIN = 390             # أقصى مدة لرصد الإشارة (جلسة كاملة)
MAX_OPEN_TRACKED = 200         # أقصى عدد إشارات مفتوحة تُتابع
KEEP_TRADES = 400              # عدد الصفقات المغلقة المحفوظة

# --- الماسح
COVERAGE_MIN = 0.30            # أقل تغطية بيانات لقبول المسح
DOWNLOAD_RETRIES = 2
DOWNLOAD_RETRY_SLEEP_S = 5
SCAN_LOG_KEEP = 96
HISTORY_KEEP = 48
CHART_BARS = 96
ALERTS_KEEP = 60

# =============================================== الكون (Universe)
UNIVERSE_MIN_PRICE, UNIVERSE_MAX_PRICE = 0.50, 10.00
UNIVERSE_MAX_FLOAT = 5_000_000
UNIVERSE_MIN_AVG_VOLUME = 100_000
UNIVERSE_POOL_MAX = 700
UNIVERSE_UNVERIFIED_MAX = 120
UNIVERSE_MIN_COUNT = 20
UNIVERSE_TIME_BUDGET_S = 600
UNIVERSE_MAX_AGE_DAYS = 5         # كون أقدم من هذا ⇒ يُعاد بناؤه داخل المسح
FLOAT_CACHE_TTL_DAYS = 21
FLOAT_MISS_TTL_HOURS = 6
FLOAT_UNKNOWN_CAP = 30_000_000     # أسهم مُصدَرة أكبر من هذا بلا Float دقيق ⇒ استبعاد

# =============================================== EARLY REVERSAL DETECTION V2
# طبقة جديدة منفصلة عن الإشارة المكتملة — الأوزان قابلة للاختبار من ملف إعدادات واحد
EARLY_WEIGHTS = {
    "slowdown": 15,          # تباطؤ سرعة الهبوط
    "volume_dry": 12,        # انخفاض حجم البيع مقارنة بموجة الهبوط
    "volatility_shrink": 8,  # تقلص مدى الشموع الهابطة / انخفاض التقلب السلبي
    "wicks": 10,             # شموع بذيول سفلية مع إغلاق أفضل
    "higher_lows": 12,       # توقف قيعان أدنى / بداية قيعان أعلى
    "volume_price": 10,      # ارتفاع الحجم مع تحسن السعر
    "rsi_recovery": 8,       # تحسن RSI من مستويات منخفضة
    "obv_improve": 7,        # تحسن OBV أو توقف تدهوره
    "cmf_improve": 7,        # تحسن CMF
    "macd_helper": 4,        # تحسن MACD كعامل مساعد
    "vwap_distance": 3,      # المسافة إلى VWAP (قريبة أفضل للارتداد)
    "resistance_room": 4,    # المسافة إلى مقاومة قريبة (مساحة متاحة)
}
# مجموعها 100

EARLY_THRESHOLD = 55         # حد اعتباره بوادر ارتداد
EARLY_STRONG_THRESHOLD = 70  # بوادر قوية

# عوامل سلبية تخفض الدرجة
EARLY_PENALTIES = {
    "break_without_reclaim": -15,  # كسر القاع دون استعادة
    "lower_lows_with_volume": -12,  # قيعان أدنى مع حجم مرتفع
    "weak_liquidity": -10,         # سيولة ضعيفة
    "near_resistance": -8,         # قرب مقاومة قوية
}

# --- كشف موجة الصعود V2: آلية تحديد القاع/القمة + تحليل بيانات كافية
RUNUP_MIN_BARS = 6            # أقل عدد شموع للصعود ذي معنى
RUNUP_DOLLAR_VOLUME_MIN = 500_000  # أقل قيمة تداول بالدولار أثناء الصعود لتكون ذات معنى (قابلة للتعديل)
RUNUP_TIME_MIN_MIN = 30       # أقل مدة صعود (دقيقة) لتكون موجة حقيقية

# --- معالجة كسر القاع وسحب السيولة V2
SWEEP_BREAK_TOL_PCT = 2.0     # حد اعتبار الكسر (افتراضي 2%)
SWEEP_RECLAIM_PCT = 0.5       # استعادة = إغلاق فوق القاع + هامش
SWEEP_RECLAIM_BARS = 2        # عدد الشموع المؤكدة للاستعادة
LIQUIDITY_SWEEP_STATES = [
    "BASE_FORMING",
    "LIQUIDITY_SWEEP_WATCH",
    "RECLAIM_PENDING",
    "RECLAIM_CONFIRMED",
    "EARLY_REVERSAL",
    "REVERSAL_CONFIRMED",
    "SELLING_CONTINUES",
    "INVALIDATED",
]

# =============================================== درجات وتنصيف
GRADE_BANDS = ((90, "A+"), (80, "A"), (65, "B"), (50, "C"), (0, "D"))


@dataclass(frozen=True)
class Condition:
    """شرط واحد قابل للعرض في الواجهة: مفتاح + اسم عربي + وزن + وصف."""
    key: str
    label: str
    weight: int
    hint: str
    core: bool = True


CORE_CONDITIONS: tuple[Condition, ...] = (
    Condition("runup", "رجل أولى: صعود قوي بحجم عالي", 0,
              f"صعود ≥ {RUNUP_MIN_PCT:g}% من قاع ما قبل القمة إلى قمة اليوم، بحجم ≥ {RUNUP_VOLUME_MIN:g}× مما قبله",
              core=False),
    Condition("drop", "هبوط ضمن النطاق المستهدف (للتحليل)", 0,
              f"هبوط ≥ {abs(DROP_MAX_PCT):g}% من قمة الموجة — التصنيف: 30–40% · 40–60% · 60–80% · 80%+ (فئات تحليلية لا استبعاد)",
              core=False),
    Condition("base", "ثبات أفقي قرب القاع", WEIGHTS["base"],
              f"تذبذب ≤ {CONS_RANGE_PCT:g}% لمدة ≥ {CONS_MIN_MIN} دقيقة وقاعه ضمن {NEAR_LOW_PCT:g}% من قاع ما بعد القمة"),
    Condition("rsi", "RSI يخرج من التشبع البيعي", WEIGHTS["rsi"],
              f"لامس ≤ {RSI_OVERSOLD:g} خلال ساعتين، والآن ≥ {RSI_EXIT:g} بتحسن ≥ {RSI_RECOVERY_MIN:g} نقاط"),
    Condition("obv", "ضغط شراء (OBV)", WEIGHTS["obv"],
              f"OBV صاعد على {OBV_LOOK} شمعة أو انحراف إيجابي (قيعان سعرية أدنى وOBV أعلى)"),
    Condition("macd", "زخم MACD", WEIGHTS["macd"],
              f"تقاطع خلال {MACD_CROSS_LOOK} شموع أو هيستوجرام أخضر"),
)

EXTRA_CONDITIONS: tuple[Condition, ...] = (
    Condition("mtf", "تأكيد الفريم الأعلى (15m)", 0,
              "قاع أعلى من قاع على 15m وإغلاق فوق EMA9 — طبقة تأكيد إضافية", core=False),
    Condition("vwap", "استعادة VWAP", 0,
              "الإغلاق فوق VWAP المرتكز من بداية الثبات", core=False),
    Condition("flow", "تدفق شرائي صافٍ", 0,
              "دلتا الحجم موجبة ونسبة الإغلاق داخل النطاق (CLV) إيجابية", core=False),
    Condition("dryup", "جفاف حجم داخل الثبات", 0,
              "حجم الثبات أقل من حجم موجة الهبوط — إشارة امتصاص محتمل لا توزيع", core=False),
    Condition("quality", "جودة القاعدة", 0,
              "ضيق النطاق، قيعان صاعدة، ولمسات متعددة لقاع الثبات", core=False),
    Condition("risk", "عائد/مخاطرة ≥ 2", 0,
              "المسافة للهدف الثاني ≥ ضعفي المسافة للوقف", core=False),
    Condition("early", "بوادر ارتداد مبكر", 0,
              "درجة الإشارة المبكرة (تباطؤ بيع · تحسن حجم · ذيول · RSI/OBV/CMF) ≥ 55", core=False),
    Condition("liquidity", "سيولة حقيقية", 0,
              "RVOL · قيمة تداول · دوران الفلوت · جودة بيانات الفلوت", core=False),
)


def all_conditions() -> tuple[Condition, ...]:
    return CORE_CONDITIONS + EXTRA_CONDITIONS


def grade_for(score: int) -> str:
    for floor, grade in GRADE_BANDS:
        if score >= floor:
            return grade
    return "D"


def score_label_for(score: int) -> str:
    if score >= 80:
        return "مكتمل وقوي"
    if score >= 55:
        return "قريب من الاكتمال"
    return "يحتاج متابعة"


# حالات دورة حياة الإشارة (الأصلية + V2)
STATE_NEW = "NEW"
STATE_BUILDING = "BUILDING"
STATE_READY = "READY"
STATE_TRIGGERED = "TRIGGERED"
STATE_WEAKENED = "WEAKENED"
STATE_PURGED = "PURGED"
STATE_DEAD = "DEAD"
# V2: حالات الكسر والاستعادة (تُستخدم داخل sweep_state)
SWEEP_BASE_FORMING = "BASE_FORMING"
SWEEP_WATCH = "LIQUIDITY_SWEEP_WATCH"
SWEEP_RECLAIM_PENDING = "RECLAIM_PENDING"
SWEEP_RECLAIM_CONFIRMED = "RECLAIM_CONFIRMED"
SWEEP_EARLY = "EARLY_REVERSAL"
SWEEP_CONFIRMED = "REVERSAL_CONFIRMED"
SWEEP_SELLING = "SELLING_CONTINUES"
SWEEP_INVALIDATED = "INVALIDATED"

STATE_LABELS = {
    STATE_NEW: "جديد على الرادار",
    STATE_BUILDING: "يبني قاعدة",
    STATE_READY: "إشارة مكتملة",
    STATE_TRIGGERED: "انطلق فوق القاعدة",
    STATE_WEAKENED: "ضعفت الإشارة",
    STATE_PURGED: "مشطوب (كسر القاع)",
    STATE_DEAD: "متوقف (لا بيانات)",
    SWEEP_BASE_FORMING: "قاعدة قيد التكوين",
    SWEEP_WATCH: "كسر قاع تحت المراقبة",
    SWEEP_RECLAIM_PENDING: "استعادة معلّقة",
    SWEEP_RECLAIM_CONFIRMED: "استعادة القاع ✓",
    SWEEP_EARLY: "بوادر ارتداد",
    SWEEP_CONFIRMED: "ارتداد مؤكد",
    SWEEP_SELLING: "استمرار ضغط البيع",
    SWEEP_INVALIDATED: "إشارة ملغاة",
}

STATE_ORDER = [STATE_READY, STATE_TRIGGERED, STATE_BUILDING, STATE_NEW,
               STATE_WEAKENED, STATE_PURGED, STATE_DEAD]

SWEEP_LABELS = {
    SWEEP_BASE_FORMING: "قاعدة قيد التكوين",
    SWEEP_WATCH: "كسر قاع تحت المراقبة",
    SWEEP_RECLAIM_PENDING: "استعادة القاع",
    SWEEP_RECLAIM_CONFIRMED: "استعادة القاع ✓",
    SWEEP_EARLY: "بوادر ارتداد",
    SWEEP_CONFIRMED: "ارتداد مؤكد",
    SWEEP_SELLING: "استمرار ضغط البيع",
    SWEEP_INVALIDATED: "إشارة ملغاة",
}

def thresholds() -> dict:
    """نسخة قابلة للتسلسل من كل الأرقام — تعرضها الواجهة في تبويب «القواعد»."""
    return {
        "drop_max_pct": DROP_MAX_PCT, "drop_min_pct": DROP_MIN_PCT,
        "drop_categories": DROP_CATEGORIES,
        "cons_range_pct": CONS_RANGE_PCT,
        "cons_min_min": CONS_MIN_MIN, "near_low_pct": NEAR_LOW_PCT,
        "rsi_period": RSI_PERIOD, "rsi_oversold": RSI_OVERSOLD, "rsi_exit": RSI_EXIT,
        "rsi_look": RSI_LOOK, "rsi_recovery_min": RSI_RECOVERY_MIN, "obv_look": OBV_LOOK,
        "macd": [MACD_FAST, MACD_SLOW, MACD_SIGNAL], "macd_cross_look": MACD_CROSS_LOOK,
        "cmf_period": CMF_PERIOD,
        "purge_break_pct": PURGE_BREAK_PCT, "invalidated_break_pct": INVALIDATED_BREAK_PCT,
        "sweep_break_tol_pct": SWEEP_BREAK_TOL_PCT, "sweep_reclaim_pct": SWEEP_RECLAIM_PCT,
        "target_pct": TARGET_PCT, "targets_pct": list(TARGETS_PCT),
        "stale_min": STALE_MIN,
        "weights": dict(WEIGHTS), "near_low_bonus": NEAR_LOW_BONUS,
        "early_weights": dict(EARLY_WEIGHTS), "early_threshold": EARLY_THRESHOLD,
        "early_strong_threshold": EARLY_STRONG_THRESHOLD,
        "atr_stop_mult": ATR_STOP_MULT,
        "stop_min_buffer_pct": STOP_MIN_BUFFER_PCT, "atr_period": ATR_PERIOD,
        "account_equity": ACCOUNT_EQUITY, "risk_per_trade_pct": RISK_PER_TRADE_PCT,
        "max_hold_min": MAX_HOLD_MIN, "mtf_resample": MTF_RESAMPLE,
        "runup_min_pct": RUNUP_MIN_PCT, "runup_volume_min": RUNUP_VOLUME_MIN,
        "universe": {"price": [UNIVERSE_MIN_PRICE, UNIVERSE_MAX_PRICE],
                     "max_float": UNIVERSE_MAX_FLOAT,
                     "min_avg_volume": UNIVERSE_MIN_AVG_VOLUME},
    }
