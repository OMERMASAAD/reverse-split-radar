# -*- coding: utf-8 -*-
"""
دورة المسح الكاملة V2: دمج التقييم الجديد مع الحالة السابقة، نظام حالات الكسر الكاذب،
آلة حالات الإشارة، سجل اللقطات، وعدادات القمع التحليلي (funnel) للتشخيص.

V2: استبدال منطق الاستبعاد المبكر (too_deep / purge 5%) بنظام حالات واضح.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from . import config as C
from .core import evaluate
from .persist import push_alert

HISTORY_FIELDS = ("last_bar", "price", "drop_pct", "hold_min", "strength_score", "score",
                  "grade", "complete", "checks", "rvol", "rsi", "relative_volume",
                  "early_score", "liquidity_score", "sweep_state", "composite_score")


def _session_date(now: datetime) -> str:
    return now.astimezone(C.MARKET_TZ).date().isoformat()


def mark_data_missing(item: dict, now: datetime) -> dict:
    """
    سهم كان على الرادار ثم انقطعت بياناته (توقّف/فشل تحميل): لا نحذفه فورًا بل
    نعلّمه، وبعد DEAD_AFTER_MISSES مسوحات متتالية يتحول إلى «متوقف».
    """
    misses = int(item.get("data_misses") or 0) + 1
    item["data_misses"] = misses
    item["data_missing"] = True
    item["last_seen"] = item.get("last_seen") or now.isoformat()
    if misses >= C.DEAD_AFTER_MISSES:
        item["state"] = C.STATE_DEAD
        item["state_label"] = C.STATE_LABELS[C.STATE_DEAD]
    return item



REJECT_LABELS = {
    "no_data": "لا بيانات كافية",
    "stale": "بيانات متقادمة",
    "low_runup": "خارج نطاق الصعود المطلوب",
    "weak_runup_volume": "حجم الصعود ضعيف",
    "no_drop": "الهبوط أقل من 30%",
    "too_deep": "الهبوط أعمق من 50% (V2: لم يعد سبب استبعاد — يُصنف فقط)",
}


def merge(universe: dict, prev: dict, frames: dict, now: datetime) -> dict:
    """
    V2: الدمج + نظام حالات الكسر الكاذب.
    - لا استبعاد لمجرد تجاوز الهبوط 50% (المصنف فقط حسب الفئة).
    - لا شطب آلي عند كسر 5% — يُعاد تقييم الحالة مع تحديث القاع المرجعي.
    - إضافة حالات: BASE_FORMING, LIQUIDITY_SWEEP_WATCH, RECLAIM_PENDING إلخ.
    - الحفاظ على المحرك الأصلي وإشاراته المكتملة.
    """
    today = _session_date(now)
    prev = prev if prev.get("session_date") == today else {}
    items = {x["ticker"]: x for x in prev.get("items", []) if isinstance(x, dict) and x.get("ticker")}
    purged = {x["ticker"]: x for x in prev.get("purged", []) if isinstance(x, dict) and x.get("ticker")}
    meta = {m["ticker"]: m for m in universe.get("tickers", []) if isinstance(m, dict) and m.get("ticker")}

    funnel = {"universe": len(meta), "frames": len(frames), "no_data": 0, "stale": 0,
              "no_runup": 0, "weak_runup_volume": 0, "no_drop": 0, "too_deep": 0,
              "monitored": 0, "near_low": 0, "base_ok": 0, "rsi_ok": 0,
              "obv_ok": 0, "macd_ok": 0, "complete": 0, "purged_new": 0, "weakened": 0,
              "dropped_no_base": 0, "early_candidates": 0, "sweep_watch": 0, "reclaim": 0,
              "liquidity_ok": 0}
    alerts = []

    for ticker, m in meta.items():
        frame = frames.get(ticker)
        if frame is None or getattr(frame, "empty", True):
            funnel["no_data"] += 1
            if ticker in items:
                mark_data_missing(items[ticker], now)
            continue
        px = float(frame["Close"].iloc[-1])
        old = items.get(ticker)

        # V2: إلغاء منطق الشطب الآلي عند 5% — استبداله بنظام حالات
        # فقط في حالة INVALIDATED الموضوعية (كسر >15% مع استمرار البيع) نشطب
        # نفحص الحالة السابقة إن كانت sweep_state == INVALIDATED
        if old and old.get("sweep_state") == C.SWEEP_INVALIDATED:
            # إذا كان قد بلغ INVALIDATED في المسح السابق وبقي تحت القاع المرجعي deeply
            # ننقله إلى purged لكن مع سبب أوضح
            # نتحقق إن كان السعر ما زال تحت القاع المرجعي بعمق
            ref_low = old.get("sweep", {}).get("reference_low") or old.get("base_low")
            if ref_low and px < float(ref_low) * (1 - C.INVALIDATED_BREAK_PCT / 100.0):
                purged[ticker] = {
                    "ticker": ticker, "price": round(px, 4), "base_low": old["base_low"],
                    "purged_at": now.isoformat(), "session_date": today,
                    "drop_pct": old.get("drop_pct"), "grade": old.get("grade"),
                    "reason": f"إشارة ملغاة: كسر عميق >{C.INVALIDATED_BREAK_PCT:g}% مع استمرار ضغط البيع",
                    "minutes_on_radar": old.get("minutes_on_radar"),
                    "sweep_state": C.SWEEP_INVALIDATED,
                }
                items.pop(ticker, None)
                funnel["purged_new"] += 1
                alerts.append({"kind": "purge", "ticker": ticker, "at": now.isoformat(), "price": round(px, 4),
                               "text": f"أُلغيت: كسر عميق >{C.INVALIDATED_BREAK_PCT:g}% مع استمرار البيع"})
                continue
            # إن عاد فوق المرجعي، نعيد تقييمه (لا نشطب)
        # إلغاء فحص الـ purged القديم المبني على 5% — نحتفظ بالقائمة لكن لا نمنع العودة إلا في حالة INVALIDATED
        # إن كان السهم في قائمة purged لكنه الآن يظهر استعادة، نسمح له بالعودة
        if ticker in purged:
            # نتحقق إن كان هناك دليل استعادة — إن لم يكن، نتخطاه
            # للتبسيط: إن كان في purged وليس INVALIDATED حديث، نسمح بإعادة التقييم إذا كان السعر فوق القاع القديم
            old_purged = purged[ticker]
            if old_purged.get("sweep_state") != C.SWEEP_INVALIDATED:
                # حالة شطب قديمة بسبب 5% — نسمح بالعودة (V2)
                del purged[ticker]
            else:
                continue

        res, why = evaluate(frame, now, m, prev_item=old)
        if res is None:
            # معالجة too_deep لم تعد تُرجع None — لكن نحتفظ بعدّها إن حدثت
            funnel[why] = funnel.get(why, 0) + 1
            if ticker in items:
                if items[ticker].get("had_base"):
                    items[ticker]["still_valid"] = False
                    items[ticker]["complete"] = False
                    items[ticker]["checks_stale"] = True
                    items[ticker]["invalidated_reason"] = why
                    items[ticker]["invalidated_label"] = REJECT_LABELS.get(why, why)
                    items[ticker]["price"] = round(px, 4)
                    items[ticker]["state"] = C.STATE_WEAKENED
                    items[ticker]["last_bar"] = now.isoformat()
                    funnel["weakened"] += 1
                else:
                    items.pop(ticker, None)
                    funnel["dropped_no_base"] += 1
            continue

        old = old or {}
        had_base = bool(old.get("had_base") or res["checks"]["base"])
        detected = old.get("detected_at") or now.isoformat()
        price = float(res["price"])
        base = (res.get("levels") or {}).get("base", {}) or {}
        # المقارنة مع قمة الثبات *قبل* الشمعة الحالية، وإلا فشمعة الاختراق ترفع القمة بنفسها
        reference = float(base.get("base_high_prior") or base.get("base_high") or 0.0)
        broke_out = bool(reference and price > reference)
        if res["complete"] and broke_out:
            state = C.STATE_TRIGGERED
        elif res["complete"]:
            state = C.STATE_READY
        elif res["checks"]["base"]:
            state = C.STATE_BUILDING
        elif old.get("had_base"):
            state = C.STATE_WEAKENED
        else:
            state = C.STATE_NEW
        # إذا كان sweep_state هو EARLY_REVERSAL أو RECLAIM_CONFIRMED، نعطي أولوية للعرض
        # لكن نحتفظ بـ state الأصلي للفرز

        res["data_misses"] = 0
        res["data_missing"] = False
        res["checks_stale"] = False
        res["invalidated_reason"] = None
        res["invalidated_label"] = None
        res["last_seen"] = now.isoformat()
        # V2: حفظ القاع المرجعي + تحديثه إن حدث قاع جديد (لا حذف تلقائي)
        # القاع المرجعي الأول يبقى للشطب، لكن إن سجل قاع جديد أقل، نحدث reference_low داخل sweep
        # أما base_low المعروض فيُحدث دائمًا لأحدث قاع
        res.update(
            ticker=ticker,
            float=m.get("float"), float_status=m.get("float_status"), float_source=m.get("float_source"),
            reverse_split=bool(m.get("reverse_split")), company=m.get("company"),
            detected_at=detected, still_valid=True, had_base=had_base,
            base_low=res["base_low"],  # V2: نحتفظ بأحدث قاع، والمرجع داخل sweep.reference_low
            state=state, state_label=C.STATE_LABELS[state],
            session_date=today,
            minutes_on_radar=int((now - pd.Timestamp(detected)).total_seconds() / 60.0),
        )
        # انتهاء صلاحية الإشارة: إن بقيت فترة طويلة دون تأكيد
        # نحتفظ بها لكن نضيف تحذير
        if res.get("minutes_on_radar", 0) > C.SWEEP_EXPIRY_MIN and not res.get("complete") and not res.get("early_is_early"):
            res["expiry_warning"] = f"مراقبة منذ {res['minutes_on_radar']} دقيقة دون تأكيد — قد تنتهي الصلاحية"

        was_complete = bool(old.get("complete"))
        if res["complete"]:
            res["signal_date"] = today
            res["first_complete_at"] = old.get("first_complete_at") or now.isoformat()
            funnel["complete"] += 1
            if not was_complete:
                alerts.append({"kind": "signal", "ticker": ticker, "at": now.isoformat(),
                               "price": res["price"], "grade": res["grade"], "score": res["score"],
                               "drop_pct": res["drop_pct"],
                               "text": "إشارة مكتملة (%s · %d/100)" % (res["grade"], res["score"])})
        if res["near_low"]:
            funnel["near_low"] += 1
        for key, counter in (("base", "base_ok"), ("rsi", "rsi_ok"), ("obv", "obv_ok"), ("macd", "macd_ok")):
            if res["checks"][key]:
                funnel[counter] += 1
        # V2 funnel counters
        if res.get("early_is_early"):
            funnel["early_candidates"] += 1
        if res.get("sweep_state") in (C.SWEEP_WATCH, C.SWEEP_BASE_FORMING):
            if res.get("sweep_state") == C.SWEEP_WATCH:
                funnel["sweep_watch"] += 1
        if res.get("sweep_state") in (C.SWEEP_RECLAIM_CONFIRMED, C.SWEEP_RECLAIM_PENDING):
            funnel["reclaim"] += 1
        if res.get("liquidity_score", 0) >= 55:
            funnel["liquidity_ok"] += 1
        funnel["monitored"] += 1

        history = list(old.get("history") or [])
        snapshot = {key: res.get(key) for key in HISTORY_FIELDS}
        if not history or history[-1].get("last_bar") != snapshot["last_bar"]:
            history.append(snapshot)
        res["history"] = history[-C.HISTORY_KEEP:]
        if state == C.STATE_NEW and not old:
            alerts.append({"kind": "watch", "ticker": ticker, "at": now.isoformat(),
                           "price": res["price"], "drop_pct": res["drop_pct"],
                           "text": "دخل الرادار بعد هبوط %.0f%%" % res["drop_pct"]})
        # تنبيهات إضافية للطبقات الجديدة
        if res.get("early_is_early") and not old.get("early_is_early"):
            alerts.append({"kind": "early", "ticker": ticker, "at": now.isoformat(),
                           "price": res["price"], "early_score": res["early_score"],
                           "text": f"بوادر ارتداد مبكر {res['early_score']}/100 — {res['early_label']}"})
        if res.get("sweep_state") == C.SWEEP_RECLAIM_CONFIRMED and old.get("sweep_state") != C.SWEEP_RECLAIM_CONFIRMED:
            alerts.append({"kind": "reclaim", "ticker": ticker, "at": now.isoformat(),
                           "price": res["price"],
                           "text": "استعادة القاع مؤكدة — كسر كاذب محتمل"})
        items[ticker] = res

    # ترتيب: المكتملة أولاً، ثم بوادر ارتداد، ثم البقية — مع مراعاة composite_score
    order = {C.STATE_READY: 0, C.STATE_TRIGGERED: 1, C.STATE_BUILDING: 2, C.STATE_NEW: 3,
             C.STATE_WEAKENED: 4}
    def sort_key(x):
        #优先: complete, then early strong, then composite
        ord_v = order.get(x.get("state"), 9)
        # إشارة مبكرة قوية ترفع الترتيب
        if x.get("early_is_strong"):
            ord_v = min(ord_v, 1)
        elif x.get("early_is_early"):
            ord_v = min(ord_v, 2)
        return (ord_v, -(x.get("composite_score") or x.get("score") or 0), x.get("drop_pct") or 0)
    ordered = sorted(items.values(), key=sort_key)
    # الرجل الأولى مرحلة فعلية في القمع: كل إطار تجاوز بوابات البيانات والصعود
    funnel["runup_ok"] = max(0, funnel["frames"] - funnel["no_data"] - funnel["stale"]
                             - funnel["no_runup"] - funnel["weak_runup_volume"])
    payload = {
        "updated_at": now.isoformat(),
        "session_date": today,
        "master_count": len(meta),
        "master_built_on": universe.get("built_on"),
        "universe_rules": universe.get("rules"),
        "items": ordered,
        "purged": sorted(purged.values(), key=lambda x: x.get("purged_at") or "", reverse=True),
        "diagnostics": {"funnel": funnel,
                        "coverage_pct": round(len(frames) / len(meta) * 100.0, 1) if meta else None},
    }
    for alert in alerts:
        push_alert(payload, alert)
    return payload


def state_counts(items: list) -> dict:
    counts = {state: sum(1 for item in items if item.get("state") == state) for state in C.STATE_ORDER}
    # أضف عدادات sweep للتحليل
    sweep_counts = {}
    for s in C.LIQUIDITY_SWEEP_STATES:
        sweep_counts[s] = sum(1 for item in items if item.get("sweep_state") == s)
    counts.update(sweep_counts)
    counts["early"] = sum(1 for item in items if item.get("early_is_early"))
    counts["early_strong"] = sum(1 for item in items if item.get("early_is_strong"))
    return counts


def session_summary(payload: dict) -> dict:
    items = payload.get("items") or []
    scores = [item.get("score") for item in items if item.get("score") is not None]
    funnel = (payload.get("diagnostics") or {}).get("funnel") or {}
    return {
        "universe": payload.get("master_count", 0),
        "monitored": len(items),
        "complete": sum(1 for item in items if item.get("complete")),
        "ready": sum(1 for item in items if item.get("state") in (C.STATE_READY, C.STATE_TRIGGERED)),
        "building": sum(1 for item in items if item.get("state") == C.STATE_BUILDING),
        "weakened": sum(1 for item in items if item.get("state") == C.STATE_WEAKENED),
        "purged": len(payload.get("purged") or []),
        "early": sum(1 for item in items if item.get("early_is_early")),
        "early_strong": sum(1 for item in items if item.get("early_is_strong")),
        "reclaim": sum(1 for item in items if item.get("sweep_state") in (C.SWEEP_RECLAIM_CONFIRMED, C.SWEEP_RECLAIM_PENDING)),
        "sweep_watch": sum(1 for item in items if item.get("sweep_state") == C.SWEEP_WATCH),
        "avg_score": round(sum(scores) / len(scores), 1) if scores else None,
        "avg_early_score": round(sum(item.get("early_score") or 0 for item in items)/len(items),1) if items else None,
        "avg_liquidity": round(sum(item.get("liquidity_score") or 0 for item in items)/len(items),1) if items else None,
        "deepest_drop_pct": round(min((item.get("drop_pct") or 0) for item in items), 1) if items else None,
        "grades": {grade: sum(1 for item in items if item.get("grade") == grade)
                   for grade in ("A+", "A", "B", "C", "D")},
        "states": state_counts(items),
        "funnel": funnel,
        "coverage_pct": (payload.get("diagnostics") or {}).get("coverage_pct"),
    }


__all__ = ["merge", "session_summary", "state_counts", "HISTORY_FIELDS"]
