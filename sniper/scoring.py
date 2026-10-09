# -*- coding: utf-8 -*-
"""
الترقيم والتصنيف.

1) `core_score` — مطابقة حرفية لدرجة قنص الذعر الأصلية (35+20+20+15 + 10 قرب القاع).
2) `confirmations` — طبقة تأكيد إضافية (6 فحوص) لا تغيّر تعريف الإشارة المكتملة،
   لكنها تنتج درجة تأكيد وتصنيفًا A+/A/B/C/D كما في برامج التحليل الجاهزة.
"""
from __future__ import annotations

from .config import (BASE_TOUCH_TOL_PCT, EXTRA_CONDITIONS, NEAR_LOW_BONUS, WEIGHTS,
                     grade_for, score_label_for)

# أوزان طبقة التأكيد (مجموعها 100)
CONFIRM_WEIGHTS = {"mtf": 20, "vwap": 15, "flow": 20, "dryup": 15, "quality": 15, "risk": 15}


def core_score(checks: dict, near_low: bool) -> tuple[int, str]:
    """نفس معادلة الأصل: مجموع أوزان الشروط المحققة + مكافأة قرب القاع."""
    score = sum(weight for key, weight in WEIGHTS.items() if checks.get(key))
    score += NEAR_LOW_BONUS if near_low else 0
    return int(score), score_label_for(int(score))


def confirmations(base: dict, price: float, vwap_value, mtf: dict, flow: dict,
                  risk: dict) -> tuple[dict, dict]:
    """
    يفحص الطبقة الإضافية ويعيد (حالة الفحوص، تفاصيلها النصية).
    كل فحص مستقل ولا يؤثر على `complete` الأساسية.
    """
    tight = base.get("base_tightness_pct")
    touches = int(base.get("base_touches") or 0)
    range_pct = base.get("base_range_pct")
    quality_ok = bool(
        (tight is not None and tight <= 1.2)
        and base.get("base_higher_lows")
        and touches >= 2
        and (range_pct is not None and range_pct <= 5.0)
    )
    dry = base.get("_dry_up") or {}
    checks = {
        "mtf": bool(mtf.get("aligned")),
        "vwap": bool(vwap_value is not None and price > float(vwap_value)),
        "flow": bool(flow.get("net_buying")),
        "dryup": bool(dry.get("dried_up")),
        "quality": quality_ok,
        "risk": bool((risk.get("rr_t2") or 0) >= 2.0),
    }
    details = {
        "mtf": mtf.get("note") or ("تأكيد على 15m" if checks["mtf"] else "لا يوجد تأكيد على الفريم الأعلى"),
        "vwap": (f"السعر فوق VWAP {float(vwap_value):.4f}" if checks["vwap"]
                 else (f"السعر تحت VWAP {float(vwap_value):.4f}" if vwap_value is not None else "VWAP غير متاح")),
        "flow": (f"دلتا {flow.get('volume_delta'):+,} · CLV {flow.get('clv_mean')}"
                 if flow.get("volume_delta") is not None else "بيانات تدفق غير كافية"),
        "dryup": (f"حجم القاعدة {dry.get('base_vs_drop_ratio')}× من حجم الهبوط"
                  if dry.get("base_vs_drop_ratio") is not None else "لا توجد موجة هبوط قابلة للمقارنة"),
        "quality": (f"ضيق {tight}% · {touches} لمسات · قيعان {'صاعدة' if base.get('base_higher_lows') else 'هابطة'}"
                    if tight is not None else "القاعدة قصيرة جدًا للحكم"),
        "risk": (f"عائد/مخاطرة {risk.get('rr_t2')}:1 للهدف الثاني" if risk.get("rr_t2") is not None
                 else "الوقف قريب جدًا من السعر"),
    }
    return checks, details


def confirm_score(confirm_checks: dict) -> int:
    return int(sum(weight for key, weight in CONFIRM_WEIGHTS.items() if confirm_checks.get(key)))


def combine(core: int, confirm: int) -> int:
    """الدرجة النهائية المعروضة: 70% من الشروط الأصلية + 30% من طبقة التأكيد."""
    return int(round(core * 0.70 + confirm * 0.30))


def grade_payload(core: int, confirm_checks: dict) -> dict:
    """حزمة الدرجات للبطاقة: الأصلية + التأكيد + المجمّعة + التصنيف."""
    confirm = confirm_score(confirm_checks)
    total = combine(core, confirm)
    return {
        "score": total,
        "grade": grade_for(total),
        "core_score": core,
        "core_label": score_label_for(core),
        "confirm_score": confirm,
        "confirmations_met": int(sum(1 for value in confirm_checks.values() if value)),
        "confirmations_total": len(confirm_checks),
    }


def missing_conditions(checks: dict, confirm_checks: dict) -> list[str]:
    labels = {c.key: c.label for c in EXTRA_CONDITIONS}
    out = []
    from .config import CORE_CONDITIONS
    for cond in CORE_CONDITIONS:
        if cond.key in checks and not checks.get(cond.key):
            out.append(cond.label)
    for key, label in labels.items():
        if not confirm_checks.get(key):
            out.append(f"{label} (تأكيد إضافي)")
    return out


def touch_tolerance(price: float) -> float:
    return abs(price) * BASE_TOUCH_TOL_PCT / 100.0


__all__ = ["core_score", "confirmations", "confirm_score", "combine", "grade_payload",
           "missing_conditions", "CONFIRM_WEIGHTS"]
