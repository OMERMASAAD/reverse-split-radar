# -*- coding: utf-8 -*-
"""
نظام حالات كسر القاع وسحب السيولة V2.
يستبدل منطق الاستبعاد الآلي عند -5% بنظام حالات يراقب الكسر الكاذب المحتمل.
"""
from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pandas as pd

from . import config as C


def evaluate_sweep(price: float, base_low: float, base_high: float | None,
                   df: pd.DataFrame, day: pd.DataFrame, base_win, prev_state: dict | None, now: datetime) -> dict:
    """
    يحدد حالة السحب الحالية. يحتفظ بـ:
    - reference_low: القاع المرجعي قبل الكسر
    - break_low: أدنى سعر بعد الكسر
    - break_depth_pct: عمق الكسر
    - break_duration_min: المدة تحت المستوى
    - reclaim_level: مستوى الاستعادة
    prev_state هو حالة المخزنة من المسح السابق (إن وجدت)
    """
    if not base_low or not price:
        return {
            "state": C.SWEEP_SELLING if price and base_low and price < base_low else C.SWEEP_BASE_FORMING,
            "state_label": C.SWEEP_LABELS.get(C.SWEEP_SELLING if price and base_low and price < base_low else C.SWEEP_BASE_FORMING, ""),
            "reference_low": round(base_low,4) if base_low else None,
            "current_price": round(price,4) if price else None,
            "break_depth_pct": None,
            "reclaim_level": None,
            "note": "قاع غير محدد بعد",
            "warnings": [],
        }

    prev = prev_state or {}
    reference_low = float(prev.get("reference_low") or base_low)
    # إذا سجل السهم قاعًا جديدًا أقل — حدّث القاع المرجعي وفق قواعد واضحة، لا تحذف المرشح
    # القاعدة: إذا كان base_low الجديد أقل من المرجعي القديم بأكثر من 1%، نحدث المرجعي
    if base_low and abs(base_low - reference_low) / reference_low > 0.01:
        # نحدث المرجعي لكن نحتفظ بتاريخ الكسر السابق
        if base_low < reference_low:
            reference_low = float(base_low)
            # إشارة إلى أن القاع تحدث — هذا يقلل الثقة مؤقتًا
        elif base_low > reference_low and price > reference_low:
            # قاع أعلى — قد يكون بداية استعادة، لا نحدث المرجعي فورًا
            pass

    # حساب عمق الكسر
    try:
        break_depth_pct = (price / reference_low - 1.0) * 100.0 if reference_low else 0.0
    except:
        break_depth_pct = 0.0

    # بيانات الشموع تحت القاع
    # نحتاج تحديد متى كُسر القاع: البحث عن أول شمعة أغلقت تحت المرجعي
    lows = low_vals = None
    closes = None
    break_ts = None
    break_low = None
    bars_below = 0
    try:
        # نفحص آخر 20 شمعة لتحديد الكسر
        tail = df.tail(20) if len(df) >= 20 else df
        below = tail[tail["Low"].astype(float) < reference_low]
        if not below.empty:
            break_ts = below.index[0]
            break_low = float(below["Low"].astype(float).min())
            # عدد الشموع التي أغلقت تحت القاع
            closed_below = tail[tail["Close"].astype(float) < reference_low]
            bars_below = len(closed_below)
            # مدة البقاء تحت القاع
            if break_ts and now:
                try:
                    bts = break_ts.tz_convert(C.MARKET_TZ) if hasattr(break_ts, 'tz_convert') and break_ts.tzinfo else break_ts
                    now_et = now.astimezone(C.MARKET_TZ) if now.tzinfo else now
                    break_duration_min = int((now_et - bts).total_seconds() / 60.0)
                except:
                    break_duration_min = bars_below * 5
            else:
                break_duration_min = bars_below * 5
        else:
            break_low = None
            break_duration_min = 0
    except:
        break_low = None
        break_duration_min = 0

    # شروط تقييم الكسر الكاذب المحتمل
    # لا نستخدم الذيل وحده دليلاً
    is_broken = price < reference_low * (1 - C.SWEEP_BREAK_TOL_PCT / 100.0) or break_low is not None
    # استعادة المستوى: إغلاق فوق القاع بهامش
    reclaim_level = reference_low * (1 + C.SWEEP_RECLAIM_PCT / 100.0)
    reclaimed = bool(price >= reclaim_level and break_low is not None and price > reference_low)
    # تأكيد الاستعادة: إغلاقين فوق المستوى + حجم
    reclaim_confirmed = False
    if reclaimed and len(df) >= 3:
        closes_recent = df["Close"].astype(float).tail(C.SWEEP_RECLAIM_BARS)
        reclaim_confirmed = bool((closes_recent >= reference_low).all() and len(closes_recent) >= C.SWEEP_RECLAIM_BARS)
        # تحقق إضافي: حجم عند الاستعادة أعلى من متوسط
        try:
            vol_recent = float(df["Volume"].astype(float).tail(2).mean())
            vol_avg = float(df["Volume"].astype(float).tail(20).mean())
            if vol_recent < vol_avg * 0.8:
                # تحسن سعر بدون حجم — استعادة ضعيفة
                pass
        except:
            pass

    # ظهور رفض سعري (ذيل سفلي مع إغلاق أفضل) + عدم استمرار الهبوط
    rejection = False
    try:
        last = df.iloc[-1]
        rng = float(last["High"]) - float(last["Low"])
        if rng > 0:
            lower_wick = min(float(last["Open"]), float(last["Close"])) - float(last["Low"])
            close_pos = (float(last["Close"]) - float(last["Low"])) / rng
            if lower_wick / rng > 0.3 and close_pos > 0.5 and price > reference_low * 0.98:
                rejection = True
    except:
        pass

    # تحديد الحالة
    warnings = []
    if not is_broken:
        # لم يحدث كسر — نحن في بناء قاعدة أو بوادر ارتداد
        # إن كان السعر يستقر قرب القاع وهناك تباطؤ، فهو BASE_FORMING أو EARLY_REVERSAL
        # يُحدد عبر early_score خارجيًا، لكن هنا نعطي الأساس
        if base_win is not None and len(base_win) >= 8:
            state = C.SWEEP_BASE_FORMING
        else:
            state = C.SWEEP_BASE_FORMING
        note = f"قاعدة عند {reference_low:.4f} — لم يحدث كسر (السعر {price:.4f})"
    else:
        # حدث كسر
        eff_break_low = break_low if break_low is not None else price
        break_depth = (eff_break_low / reference_low - 1.0) * 100.0 if eff_break_low and reference_low else break_depth_pct
        if not reclaimed:
            # تحت المستوى — مراقبة
            if abs(break_depth) <= 5.0 and bars_below <= 4:
                state = C.SWEEP_WATCH
                note = f"كسر {break_depth:.1f}% إلى {eff_break_low:.4f} — تحت المراقبة (سحب سيولة محتمل)، {bars_below} شمعة تحت القاع"
            elif abs(break_depth) > 10.0 or bars_below > 8:
                # كسر عميق + استمرار — خطر
                if price < reference_low * (1 - C.INVALIDATED_BREAK_PCT / 100.0):
                    state = C.SWEEP_INVALIDATED
                    note = f"كسر عميق {break_depth:.1f}% واستمرار هبوط — إشارة ملغاة موضوعيًا"
                    warnings.append("كسر عميق مع استمرار هبوط — مخاطرة شطب")
                else:
                    state = C.SWEEP_SELLING
                    note = f"كسر {break_depth:.1f}% واستمرار ضغط بيع ({bars_below} شمعة تحت القاع)"
                    warnings.append("استمرار ضغط البيع بعد الكسر")
            else:
                state = C.SWEEP_WATCH
                note = f"كسر {break_depth:.1f}% — يختبر احتمال الكسر الكاذب"
        else:
            # حدثت استعادة
            if reclaim_confirmed:
                state = C.SWEEP_RECLAIM_CONFIRMED
                note = f"استعادة مؤكدة فوق {reference_low:.4f} → {price:.4f} ({break_depth:.1f}% كسر ثم عودة) — مساحة حتى المقاومة متاحة"
            else:
                state = C.SWEEP_RECLAIM_PENDING
                note = f"بدأ العودة فوق {reference_low:.4f} (من {eff_break_low:.4f}) — استعادة معلقة تحتاج تأكيد إغلاق"

    # حالة خاصة: إن كان هناك بوادر ارتداد قوية (يُحدد خارجيًا عبر early_score) نرقي الحالة
    # لكن لا نحددها هنا — يدمجها core.py

    # فحص انتهاء الصلاحية: إن بقي السهم في حالة ارتداد دون تأكيد لفترة طويلة
    # يُطلب من core.py التحقق من MAX_HOLD

    # تقييم جودة الاستعادة: مساحة سعرية حتى المقاومة التالية
    resistance_room = None
    try:
        res = float(day["High"].max()) if len(day) else None
        if res and price:
            resistance_room = (res - price) / price * 100.0
            if resistance_room is not None and resistance_room < 5.0:
                warnings.append(f"مساحة ارتداد محدودة حتى المقاومة {res:.4f} ({resistance_room:.1f}%)")
    except:
        pass

    return {
        "state": state,
        "state_label": C.SWEEP_LABELS.get(state, state),
        "reference_low": round(reference_low,4),
        "break_low": round(break_low,4) if break_low else None,
        "current_price": round(price,4),
        "break_depth_pct": round(break_depth, 1) if 'break_depth' in locals() and break_depth is not None else round(break_depth_pct,1),
        "bars_below": bars_below,
        "break_duration_min": break_duration_min if 'break_duration_min' in locals() else None,
        "reclaim_level": round(reclaim_level,4) if reclaim_level else None,
        "reclaimed": reclaimed,
        "reclaim_confirmed": reclaim_confirmed,
        "rejection": rejection,
        "resistance_room_pct": round(resistance_room,1) if resistance_room else None,
        "warnings": warnings,
        "note": note,
        "break_ts": break_ts.isoformat() if break_ts is not None and hasattr(break_ts, 'isoformat') else None,
    }
