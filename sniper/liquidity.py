# -*- coding: utf-8 -*-
"""
نظام درجة السيولة والتجميع المحتمل V2.
يضمن أن CMF/OBV وغيرها تؤثر فعلًا في الترتيب والدرجة، مع توضيح المحدوديات.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config as C
from .indicators import cmf, obv


def liquidity_score(df: pd.DataFrame, day: pd.DataFrame, meta: dict, volume_payload: dict, indicators_now: dict, base_win=None) -> dict:
    """
    يعيد درجة سيولة 0-100 + تفصيل كل عامل.
    """
    factors = {}
    pts = {}
    warnings = []
    reasons = []

    if df is None or df.empty:
        return {"score": 0, "label": "بيانات غير كافية", "factors": {}, "warnings": ["لا توجد بيانات حجم"]}

    price = float(df["Close"].astype(float).iloc[-1]) if len(df) else 0
    vol_last = float(df["Volume"].astype(float).iloc[-1]) if len(df) else 0

    # 1) Relative Volume vs متوسط 20 شمعة
    try:
        rvol = volume_payload.get("rvol") if volume_payload else None
        if rvol is None and len(df) >= 21:
            avg20 = float(df["Volume"].astype(float).tail(20).mean())
            rvol = vol_last / avg20 if avg20 else None
        if rvol is not None:
            if rvol >= 2.0:
                pts["rvol"] = 20
                factors["rvol"] = {"value": round(rvol,2), "pts": 20, "desc": f"RVOL {rvol:.2f}× — نشاط غير اعتيادي"}
                reasons.append(f"RVOL عالي {rvol:.2f}×")
            elif rvol >= 1.3:
                pts["rvol"] = 12
                factors["rvol"] = {"value": round(rvol,2), "pts": 12, "desc": f"RVOL {rvol:.2f}× — فوق المتوسط"}
            elif rvol >= 0.8:
                pts["rvol"] = 5
                factors["rvol"] = {"value": round(rvol,2), "pts": 5, "desc": f"RVOL {rvol:.2f}× — طبيعي"}
            else:
                pts["rvol"] = 0
                factors["rvol"] = {"value": round(rvol,2), "pts": 0, "desc": f"RVOL ضعيف {rvol:.2f}× — سيولة منخفضة"}
                warnings.append(f"RVOL ضعيف {rvol:.2f}×")
        else:
            pts["rvol"] = 0
            factors["rvol"] = {"pts": 0, "desc": "RVOL غير متاح"}
    except:
        pts["rvol"] = 0
        factors["rvol"] = {"pts": 0, "desc": "خطأ RVOL"}

    # 2) قيمة التداول بالدولار
    try:
        dollar_vol = price * vol_last
        day_dollar = float((day["Close"].astype(float) * day["Volume"].astype(float)).sum()) if day is not None and len(day) else dollar_vol
        if day_dollar >= 2_000_000:
            p = 15
            factors["dollar"] = {"value": int(day_dollar), "pts": p, "desc": f"قيمة تداول عالية ${day_dollar:,.0f}"}
        elif day_dollar >= 500_000:
            p = 10
            factors["dollar"] = {"value": int(day_dollar), "pts": p, "desc": f"قيمة تداول جيدة ${day_dollar:,.0f}"}
        elif day_dollar >= 100_000:
            p = 4
            factors["dollar"] = {"value": int(day_dollar), "pts": p, "desc": f"قيمة تداول متوسطة ${day_dollar:,.0f}"}
        else:
            p = 0
            factors["dollar"] = {"value": int(day_dollar), "pts": p, "desc": f"قيمة تداول ضعيفة ${day_dollar:,.0f} — خطر سيولة"}
            warnings.append(f"قيمة تداول ضعيفة ${day_dollar:,.0f}")
        pts["dollar"] = p
    except:
        pts["dollar"] = 0
        factors["dollar"] = {"pts": 0, "desc": "خطأ قيمة التداول"}

    # 3) دوران الفلوت
    try:
        float_shares = meta.get("float") if meta else None
        if float_shares and float_shares > 0 and day is not None and len(day):
            day_vol = float(day["Volume"].astype(float).sum())
            turnover = day_vol / float(float_shares) * 100
            ft = volume_payload.get("float_turnover") if volume_payload else None
            # turnover already computed there
            if turnover >= 100:
                p = 15
                desc = f"دوران فلوت {turnover:.1f}% — تداول الفلوت كاملاً (وقود عالي)"
            elif turnover >= 50:
                p = 10
                desc = f"دوران فلوت {turnover:.1f}% — نشط"
            elif turnover >= 20:
                p = 6
                desc = f"دوران فلوت {turnover:.1f}% — متوسط"
            else:
                p = 2
                desc = f"دوران فلوت {turnover:.1f}% — ضعيف"
                if turnover < 10:
                    warnings.append(f"دوران فلوت ضعيف {turnover:.1f}%")
            pts["turnover"] = p
            factors["turnover"] = {"value": round(turnover,1), "pts": p, "desc": desc, "float": int(float_shares)}
        else:
            pts["turnover"] = 3
            factors["turnover"] = {"pts": 3, "desc": "بيانات الفلوت غير متاحة — تقييم محدود", "warning": "جودة بيانات الفلوت ضعيفة"}
            warnings.append("بيانات الفلوت غير متاحة/قديمة — تقييم السيولة محدود")
    except:
        pts["turnover"] = 0
        factors["turnover"] = {"pts": 0, "desc": "خطأ دوران الفلوت"}

    # 4) سلوك الحجم خلال الهبوط vs خلال الاستقرار/الاستعادة
    try:
        dry = (volume_payload.get("dry_up") if volume_payload else {}) or {}
        ratio = dry.get("base_vs_drop_ratio")
        if ratio is not None:
            if ratio <= 0.6:
                p = 12
                desc = f"جفاف حجم قوي {ratio:.2f}× — امتصاص محتمل للبيع (لا تجميع مؤكد)"
                reasons.append("جفاف حجم — امتصاص محتمل")
            elif ratio <= 0.85:
                p = 8
                desc = f"جفاف حجم {ratio:.2f}× — هدوء بيع"
            elif ratio <= 1.0:
                p = 3
                desc = f"حجم مستقر {ratio:.2f}×"
            else:
                p = 0
                desc = f"حجم مرتفع {ratio:.2f}× — توزيع محتمل"
                warnings.append("حجم مرتفع في الثبات — قد يكون توزيعًا")
            pts["dryup_behavior"] = p
            factors["dryup_behavior"] = {"ratio": round(ratio,2), "pts": p, "desc": desc}
        else:
            pts["dryup_behavior"] = 0
            factors["dryup_behavior"] = {"pts": 0, "desc": "لا توجد بيانات مقارنة للهبوط"}
    except:
        pts["dryup_behavior"] = 0
        factors["dryup_behavior"] = {"pts": 0, "desc": "خطأ سلوك حجم"}

    # 5) تحسن السعر بالتزامن مع تحسن الحجم (Volume Balance)
    try:
        flow = volume_payload.get("flow_metrics") if volume_payload else volume_payload  # volume_payload contains flow fields directly
        # flow_metrics in volume_payload: volume_delta, up_volume etc.
        up_vol = volume_payload.get("up_volume") if volume_payload else None
        down_vol = volume_payload.get("down_volume") if volume_payload else None
        if up_vol is not None and down_vol is not None and (up_vol + down_vol) > 0:
            bal = (up_vol - down_vol) / (up_vol + down_vol)
            if bal > 0.3:
                p = 10
                desc = f"ميزان حجم شرائي {bal:.0%} — تحسن حجم مع سعر"
                reasons.append(f"ميزان حجم +{bal:.0%}")
            elif bal > 0:
                p = 5
                desc = f"ميزان حجم إيجابي طفيف {bal:.0%}"
            elif bal < -0.3:
                p = 0
                desc = f"ميزان حجم بيعي {bal:.0%} — ضغط بيع مستمر"
                warnings.append(f"ميزان حجم بيعي {bal:.0%}")
            else:
                p = 2
                desc = f"ميزان حجم محايد {bal:.0%}"
            pts["volume_balance"] = p
            factors["volume_balance"] = {"balance": round(bal,2), "pts": p, "desc": desc}
        else:
            # بديل: دلتا
            delta = volume_payload.get("volume_delta") if volume_payload else None
            if delta is not None:
                if delta > 0:
                    p = 6
                    factors["volume_balance"] = {"delta": delta, "pts": p, "desc": f"دلتا حجم إيجابية {delta:+,}"}
                else:
                    p = 0
                    factors["volume_balance"] = {"delta": delta, "pts": p, "desc": f"دلتا حجم سلبية {delta:+,}"}
                pts["volume_balance"] = p
            else:
                pts["volume_balance"] = 0
                factors["volume_balance"] = {"pts": 0, "desc": "ميزان حجم غير متاح"}
    except:
        pts["volume_balance"] = 0
        factors["volume_balance"] = {"pts": 0, "desc": "خطأ ميزان حجم"}

    # 6) CMF — مع ذكر محدوديته (تقريبي بلا Order Flow حقيقي)
    try:
        cmf_val = indicators_now.get("cmf") if indicators_now else None
        if cmf_val is None and df is not None:
            cs = cmf(df)
            cmf_val = float(cs.iloc[-1]) if len(cs) and np.isfinite(cs.iloc[-1]) else None
        if cmf_val is not None:
            if cmf_val > 0.05:
                p = 10
                desc = f"CMF {cmf_val:.3f} إيجابي قوي — تجميع سيولة محتمل (مؤشر تقريبي، لا يثبت تجميعًا حقيقيًا)"
                reasons.append(f"CMF إيجابي {cmf_val:.3f}")
            elif cmf_val > 0:
                p = 6
                desc = f"CMF {cmf_val:.3f} إيجابي طفيف — تحسن تدفق السيولة المحتمل"
            elif cmf_val < -0.1:
                p = 0
                desc = f"CMF {cmf_val:.3f} سلبي قوي — توزيع محتمل"
                warnings.append(f"CMF سلبي {cmf_val:.3f}")
            else:
                p = 2
                desc = f"CMF {cmf_val:.3f} محايد"
            pts["cmf"] = p
            factors["cmf"] = {"value": round(cmf_val,3), "pts": p, "desc": desc, "note": "مؤشر تقريبي قائم على الحجم والسعر — لا يتوفر Order Flow فعلي"}
        else:
            pts["cmf"] = 0
            factors["cmf"] = {"pts": 0, "desc": "CMF غير متاح — بيانات غير كافية"}
    except:
        pts["cmf"] = 0
        factors["cmf"] = {"pts": 0, "desc": "خطأ CMF"}

    # 7) OBV — نفس المحدودية
    try:
        # استخدم obv_now_slope already in indicators_now? لا، نحسبه
        close = df["Close"].astype(float)
        vol = df["Volume"].astype(float)
        o = obv(close, vol)
        if len(o) >= C.OBV_LOOK + 1:
            o_now = float(o.iloc[-1])
            o_prev = float(o.iloc[-C.OBV_LOOK])
            if o_now > o_prev:
                p = 8
                desc = f"OBV صاعد — توقف تدهور الحجم المرجح بالسعر"
                reasons.append("OBV يتحسن")
            elif o_now == o_prev:
                p = 4
                desc = "OBV مستقر — توقف تدهور"
            else:
                # تحقق انحراف إيجابي
                lows = df["Low"].astype(float)
                low_now = float(lows.iloc[-C.OBV_LOOK:].min())
                low_prev = float(lows.iloc[-2*C.OBV_LOOK:-C.OBV_LOOK].min()) if len(lows) >= 2*C.OBV_LOOK else low_now
                obv_now_min = float(o.iloc[-C.OBV_LOOK:].min())
                obv_prev_min = float(o.iloc[-2*C.OBV_LOOK:-C.OBV_LOOK].min()) if len(o) >= 2*C.OBV_LOOK else obv_now_min
                if low_now <= low_prev and obv_now_min > obv_prev_min:
                    p = 6
                    desc = "OBV انحراف إيجابي — قيعان سعرية أدنى مع OBV أعلى (امتصاص محتمل)"
                else:
                    p = 0
                    desc = "OBV هابط — ضغط بيع مستمر"
                    warnings.append("OBV هابط")
            pts["obv"] = p
            factors["obv"] = {"pts": p, "desc": desc, "note": "مؤشر تقريبي — لا يثبت نية المشترين"}
        else:
            pts["obv"] = 0
            factors["obv"] = {"pts": 0, "desc": "بيانات OBV غير كافية"}
    except:
        pts["obv"] = 0
        factors["obv"] = {"pts": 0, "desc": "خطأ OBV"}

    # 8) جودة بيانات الفلوت وحداثتها
    try:
        source = meta.get("float_source") if meta else None
        status = meta.get("float_status") if meta else None
        # استنبط جودة: إذا المصدر yahoo_outstanding أو sec فجيد، otherwise ضعيف
        if source and "sec" in source.lower() or source and "yahoo" in source.lower():
            p = 5
            desc = f"مصدر فلوت: {source} ({status}) — موثوق نسبيًا"
        elif source:
            p = 2
            desc = f"مصدر فلوت: {source} — جودة متوسطة"
            warnings.append(f"مصدر فلوت غير مثالي: {source}")
        else:
            p = 0
            desc = "مصدر الفلوت غير متاح — التقييم محدود"
            warnings.append("بيانات الفلوت مفقودة — لا يمكن تقدير دوران الفلوت بدقة")
        pts["float_quality"] = p
        factors["float_quality"] = {"pts": p, "desc": desc, "source": source, "status": status}
    except:
        pts["float_quality"] = 0
        factors["float_quality"] = {"pts": 0, "desc": "خطأ جودة الفلوت"}

    # 9) سيولة السهم الفعلية (البعد عن عدد الأسهم وحده)
    try:
        # نستخدم dollar volume بالفعل — لكن نضيف تحقق السبريد التقريبي إن وجد ATR
        atr_v = indicators_now.get("atr") if indicators_now else None
        if atr_v and price:
            atr_pct = atr_v / price * 100
            if atr_pct > 5:
                warnings.append(f"تذبذب عالي ATR {atr_pct:.1f}% — خطر تقلب شديد")
                # لا عقوبة مباشرة لكن تحذير
                pts["volatility_risk"] = -2
                factors["volatility_risk"] = {"atr_pct": round(atr_pct,1), "pts": -2, "desc": f"ATR {atr_pct:.1f}% — تذبذب شديد"}
            else:
                pts["volatility_risk"] = 0
                factors["volatility_risk"] = {"atr_pct": round(atr_pct,1), "pts": 0, "desc": f"ATR {atr_pct:.1f}% طبيعي"}
        else:
            pts["volatility_risk"] = 0
            factors["volatility_risk"] = {"pts": 0, "desc": "ATR غير متاح"}
    except:
        pts["volatility_risk"] = 0
        factors["volatility_risk"] = {"pts": 0, "desc": "خطأ تقلب"}

    total = sum(max(0, v) for v in pts.values())
    # العقوبات السالبة
    penalties = sum(v for v in pts.values() if v < 0)
    raw = total + penalties  # penalties سالبة
    # تطبيع إلى 0-100 — الحد الأقصى النظري ~80-90
    max_possible = 85  # تقديري
    score = int(round(max(0, min(100, raw / max_possible * 100))))
    # تسمية
    if score >= 75:
        label = "سيولة ممتازة"
    elif score >= 55:
        label = "سيولة جيدة"
    elif score >= 35:
        label = "سيولة متوسطة"
    elif score >= 15:
        label = "سيولة ضعيفة — خطر"
    else:
        label = "سيولة ضعيفة جدًا"

    # ملاحظة هامة: ارتفاع درجة السيولة لا يلغي تحذير خطر ناتج عن استمرار الهبوط
    # هذا يُطبق في core.py عند الدمج النهائي

    return {
        "score": score,
        "raw_points": raw,
        "max_possible": max_possible,
        "label": label,
        "factors": factors,
        "points": pts,
        "reasons": reasons,
        "warnings": warnings,
        "note": "CMF/OBV مؤشرات تقريبية قائمة على الحجم والسعر فقط — لا تثبت نية المشترين أو تجميعًا حقيقيًا بلا بيانات Order Flow",
    }
