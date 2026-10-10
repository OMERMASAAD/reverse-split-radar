# -*- coding: utf-8 -*-
"""
إعدادات «رادار قنص الذعر» — مصدر الحقيقة الوحيد لكل الأرقام.

الأرقام في قسم «الشروط الأصلية» مطابقة حرفيًا لمنطق قنص الذعر في stouk-bot
(panic_scanner.py) حتى تبقى الإشارة نفسها. كل ما بعد قسم «التطويرات» إضافات
تحليلية لا تغيّر تعريف الإشارة المكتملة (complete).
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

DROP_MAX_PCT = -30.0      # هبوط ≥ 30% من قمة اليوم
DROP_MIN_PCT = float(_env("DROP_MIN_PCT", -50.0))         # ولا أعمق من 50% (النموذج المستهدف 30–50%)
CONS_RANGE_PCT = 5.0      # أقصى تذبذب مسموح داخل الثبات الأفقي
CONS_MIN_MIN = 60         # أقل مدة ثبات (دقيقة)
NEAR_LOW_PCT = 5.0        # قاع الثبات ضمن 5% من أدنى قاع اليوم
RSI_PERIOD = 14
RSI_OVERSOLD = 30.0       # RSI لامس ≤ 30 خلال النافذة
RSI_EXIT = 25.0           # RSI الآن ≥ 25 (خرج من التشبع)
RSI_LOOK = 24             # آخر 24 شمعة 5m = ساعتان
RSI_RECOVERY_MIN = 3.0    # تحسّن RSI ≥ 3 نقاط
# في هذا النموذج (صعود 100–400% ثم هبوط) لا يلامس RSI(14) غالبًا مستوى 30، لأن
# متوسط المكاسب ما زال مرتفعًا. لذلك يُقبل أيضًا «تراجع RSI من قمة اليوم» كدليل ضعف،
# وهذا مطابق لطلب «راقب هل بدأ RSI يتحسن».
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
# الشطب محاذٍ للوقف: يتوقف الرصد حين يُضرب الوقف فعلًا لا قبله
PURGE_BREAK_PCT = float(_env("PURGE_BREAK_PCT", STOP_BUFFER_PCT))
TARGETS_PCT = (20.0, 30.0)

# إدارة الصفقة بعد تحقق الهدف الأول
MOVE_STOP_TO_BREAK_EVEN = True    # بعد T1 ينتقل الوقف إلى سعر الدخول (بلا مخاطرة)
TRAIL_AFTER_T1_PCT = None         # رقم (مثلاً 5.0) يفعّل وقفًا متحركًا تحت أعلى قمة — None = معطّل
TRACK_BREAKOUT_ENTRY = True       # رصد وضع «اختراق قمة القاعدة» كصفقة ورقية مستقلة            # T1 = +20% · T2 = +30% (كلاهما قبل خط VWAP)
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
    Condition("drop", "هبوط ضمن النطاق المستهدف", 0,
              f"هبوط بين {abs(DROP_MIN_PCT):g}% و{abs(DROP_MAX_PCT):g}% من قمة اليوم (بوابة الدخول للرصد)",
              core=False),
    Condition("base", "ثبات أفقي قرب القاع", WEIGHTS["base"],
              f"تذبذب ≤ {CONS_RANGE_PCT:g}% لمدة ≥ {CONS_MIN_MIN} دقيقة وقاعه ضمن {NEAR_LOW_PCT:g}% من قاع اليوم"),
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
              "حجم الثبات أقل من حجم موجة الهبوط — إشارة امتصاص لا توزيع", core=False),
    Condition("quality", "جودة القاعدة", 0,
              "ضيق النطاق، قيعان صاعدة، ولمسات متعددة لقاع الثبات", core=False),
    Condition("risk", "عائد/مخاطرة ≥ 2", 0,
              "المسافة للهدف الثاني ≥ ضعفي المسافة للوقف", core=False),
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


# حالات دورة حياة الإشارة
STATE_NEW = "NEW"
STATE_BUILDING = "BUILDING"
STATE_READY = "READY"
STATE_TRIGGERED = "TRIGGERED"
STATE_WEAKENED = "WEAKENED"
STATE_PURGED = "PURGED"
STATE_DEAD = "DEAD"

STATE_LABELS = {
    STATE_NEW: "جديد على الرادار",
    STATE_BUILDING: "يبني قاعدة",
    STATE_READY: "إشارة مكتملة",
    STATE_TRIGGERED: "انطلق فوق القاعدة",
    STATE_WEAKENED: "ضعفت الإشارة",
    STATE_PURGED: "مشطوب (كسر القاع)",
    STATE_DEAD: "متوقف (لا بيانات)",
}

STATE_ORDER = [STATE_READY, STATE_TRIGGERED, STATE_BUILDING, STATE_NEW,
               STATE_WEAKENED, STATE_PURGED, STATE_DEAD]

def thresholds() -> dict:
    """نسخة قابلة للتسلسل من كل الأرقام — تعرضها الواجهة في تبويب «القواعد»."""
    return {
        "drop_max_pct": DROP_MAX_PCT, "cons_range_pct": CONS_RANGE_PCT,
        "cons_min_min": CONS_MIN_MIN, "near_low_pct": NEAR_LOW_PCT,
        "rsi_period": RSI_PERIOD, "rsi_oversold": RSI_OVERSOLD, "rsi_exit": RSI_EXIT,
        "rsi_look": RSI_LOOK, "rsi_recovery_min": RSI_RECOVERY_MIN, "obv_look": OBV_LOOK,
        "macd": [MACD_FAST, MACD_SLOW, MACD_SIGNAL], "macd_cross_look": MACD_CROSS_LOOK,
        "cmf_period": CMF_PERIOD,
        "purge_break_pct": PURGE_BREAK_PCT, "target_pct": TARGET_PCT, "stale_min": STALE_MIN,
        "weights": dict(WEIGHTS), "near_low_bonus": NEAR_LOW_BONUS,
        "targets_pct": list(TARGETS_PCT), "atr_stop_mult": ATR_STOP_MULT,
        "stop_min_buffer_pct": STOP_MIN_BUFFER_PCT, "atr_period": ATR_PERIOD,
        "account_equity": ACCOUNT_EQUITY, "risk_per_trade_pct": RISK_PER_TRADE_PCT,
        "max_hold_min": MAX_HOLD_MIN, "mtf_resample": MTF_RESAMPLE,
        "universe": {"price": [UNIVERSE_MIN_PRICE, UNIVERSE_MAX_PRICE],
                     "max_float": UNIVERSE_MAX_FLOAT,
                     "min_avg_volume": UNIVERSE_MIN_AVG_VOLUME},
    }
