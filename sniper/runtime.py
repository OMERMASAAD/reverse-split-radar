# -*- coding: utf-8 -*-
"""
دورة المسح الكاملة: دمج التقييم الجديد مع الحالة السابقة، الشطب الآلي، آلة
حالات الإشارة، سجل اللقطات، وعدادات القمع التحليلي (funnel) للتشخيص.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from . import config as C
from .core import evaluate
from .persist import push_alert

HISTORY_FIELDS = ("last_bar", "price", "drop_pct", "hold_min", "strength_score", "score",
                  "grade", "complete", "checks", "rvol", "rsi", "relative_volume")


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



def merge(universe: dict, prev: dict, frames: dict, now: datetime) -> dict:
    """
    الدمج + التنظيف الآلي. أي هابط ≤ -30% يظهر؛ والشطب لمن ثبت فعلًا ثم كسر
    قاعه بـ PURGE_BREAK_PCT% ولا يعود في نفس الجلسة (كما في الأصل).
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
              "dropped_no_base": 0}
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

        # 🧹 التنظيف الآلي — نفس قاعدة الأصل
        if old and old.get("had_base") and px < float(old["base_low"]) * (1.0 - C.PURGE_BREAK_PCT / 100.0):
            purged[ticker] = {
                "ticker": ticker, "price": round(px, 4), "base_low": old["base_low"],
                "purged_at": now.isoformat(), "session_date": today,
                "drop_pct": old.get("drop_pct"), "grade": old.get("grade"),
                "reason": "كسر قاع الثبات بـ -%g%%" % C.PURGE_BREAK_PCT,
                "minutes_on_radar": old.get("minutes_on_radar"),
            }
            items.pop(ticker, None)
            funnel["purged_new"] += 1
            alerts.append({"kind": "purge", "ticker": ticker, "at": now.isoformat(), "price": round(px, 4),
                           "text": "شُطب: كسر قاع الثبات بـ -%g%%" % C.PURGE_BREAK_PCT})
            continue
        if ticker in purged:
            continue

        res, why = evaluate(frame, now, m)
        if res is None:
            funnel[why] = funnel.get(why, 0) + 1
            if ticker in items:
                if items[ticker].get("had_base"):
                    items[ticker]["still_valid"] = False
                    items[ticker]["complete"] = False
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

        res["data_misses"] = 0
        res["data_missing"] = False
        res["last_seen"] = now.isoformat()
        res.update(
            ticker=ticker,
            float=m.get("float"), float_status=m.get("float_status"), float_source=m.get("float_source"),
            reverse_split=bool(m.get("reverse_split")), company=m.get("company"),
            detected_at=detected, still_valid=True, had_base=had_base,
            # قاع الثبات الأول هو مرجع الشطب — لا يتغير مع تمدد القاعدة
            base_low=old["base_low"] if old.get("had_base") else res["base_low"],
            state=state, state_label=C.STATE_LABELS[state],
            session_date=today,
            minutes_on_radar=int((now - pd.Timestamp(detected)).total_seconds() / 60.0),
        )
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
        items[ticker] = res

    order = {C.STATE_READY: 0, C.STATE_TRIGGERED: 1, C.STATE_BUILDING: 2, C.STATE_NEW: 3,
             C.STATE_WEAKENED: 4}
    ordered = sorted(items.values(),
                     key=lambda x: (order.get(x.get("state"), 9), -(x.get("score") or 0),
                                    x.get("drop_pct") or 0))
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
    return {state: sum(1 for item in items if item.get("state") == state) for state in C.STATE_ORDER}


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
        "avg_score": round(sum(scores) / len(scores), 1) if scores else None,
        "deepest_drop_pct": round(min((item.get("drop_pct") or 0) for item in items), 1) if items else None,
        "grades": {grade: sum(1 for item in items if item.get("grade") == grade)
                   for grade in ("A+", "A", "B", "C", "D")},
        "states": state_counts(items),
        "funnel": funnel,
        "coverage_pct": (payload.get("diagnostics") or {}).get("coverage_pct"),
    }


__all__ = ["merge", "session_summary", "state_counts", "HISTORY_FIELDS"]
