# -*- coding: utf-8 -*-
"""
متتبّع النتائج الورقي: بعد اكتمال الإشارة يرصد أقصى حركة إيجابية/سلبية،
تحقق الأهداف، ضرب الوقف، ومدة الرصد — ثم يجمع إحصاءات (نسبة نجاح، توقع رياضي،
Profit Factor، توزيعات حسب الدرجة/الساعة/عمق الهبوط).

ورقي تمامًا: لا أوامر ولا وسيط، فقط قياس أداء الشروط.
"""
from __future__ import annotations

import statistics
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from . import config as C
from .core import to_et

EXIT_STOP = "stop"
EXIT_TARGET = "target"
EXIT_TIMEOUT = "timeout"
EXIT_SESSION = "session_end"
EXIT_BREAK_EVEN = "break_even"      # خرج عند التعادل بعد نقل الوقف

ALIVE_STATUSES = ("open", "pending")     # ما يبقى بين المسوحات

EXIT_LABELS = {
    EXIT_STOP: "ضرب الوقف",
    EXIT_TARGET: "تحقق الهدف",
    EXIT_TIMEOUT: "انتهت مدة الرصد",
    EXIT_SESSION: "إغلاق الجلسة",
    EXIT_BREAK_EVEN: "خروج عند التعادل",
    "open": "ما زالت مفتوحة",
    "pending": "أمر معلّق بانتظار الاختراق",
    "expired": "انتهت صلاحيته دون اختراق",
}

MODE_LABELS = {"market": "دخول فوري أعلى القاع", "breakout": "دخول عند اختراق القاعدة"}


def _signal_id(ticker: str, entry_date: str) -> str:
    return "%s|%s" % (ticker, entry_date)


def _plan_for(item: dict, mode: str) -> dict:
    risk = item.get("risk") or {}
    for candidate in (risk.get("entry_modes") or []):
        if candidate.get("key") == mode:
            return candidate
    return {}


def open_trade(item: dict, now: datetime, mode: str = "market") -> dict | None:
    """
    ينشئ سجل رصد ورقي لإشارة مكتملة.

    - `market`  ← دخول فوري بسعر آخر شمعة، مفتوح مباشرة.
    - `breakout`← **أمر معلّق** عند قمة القاعدة؛ لا يُفتح إلا إذا اخترقها السعر فعلًا.
    """
    risk = item.get("risk") or {}
    if not risk or not risk.get("stop"):
        return None
    plan = _plan_for(item, mode)
    targets = plan.get("targets") or risk.get("targets") or []
    base_id = _signal_id(item["ticker"], item["signal_date"])
    trade = {
        "id": base_id if mode == "market" else base_id + ":bk",
        "signal_id": base_id,
        "ticker": item["ticker"],
        "session_date": item["signal_date"],
        "mode": mode, "mode_label": MODE_LABELS.get(mode, mode),
        "entry_ts": now.isoformat(),
        "entry": float(item["price"]),
        "stop": risk["stop"],
        "current_stop": risk["stop"],
        "stop_at_break_even": False,
        "trail_high": None,
        "targets": [{"label": t["label"], "price": t["price"], "pct": t["pct"], "hit": False, "at": None}
                    for t in targets],
        "grade": item.get("grade"),
        "core_score": item.get("strength_score"),
        "score": item.get("score"),
        "confirm_score": item.get("confirm_score"),
        "drop_pct": item.get("drop_pct"),
        "rvol": item.get("rvol"),
        "float": item.get("float"),
        "reverse_split": bool(item.get("reverse_split")),
        "mfe_pct": 0.0, "mae_pct": 0.0,
        "targets_hit": [], "stop_hit": False,
        "status": "open", "exit_reason": None, "exit_price": None, "exit_ts": None,
        "r_multiple": 0.0, "hold_min": 0, "bars_seen": 0,
        "opened_at": now.isoformat(), "updated_at": now.isoformat(),
    }
    if mode == "market":
        trade["trigger"] = None
        return trade
    trigger = plan.get("entry")
    if not trigger:
        return None
    trade.update({"status": "pending", "entry": None, "entry_ts": None,
                  "trigger": round(float(trigger), 4), "pending_since": now.isoformat(),
                  "mfe_pct": 0.0, "mae_pct": 0.0})
    return trade


def update_trade(trade: dict, df: pd.DataFrame, now: datetime) -> dict:
    """
    محاكاة الصفقة **شمعة بشمعة** من لحظة الدخول.

    الشمعة‑بشمعة ضرورية هنا: نقل الوقف إلى التعادل بعد T1 حدث زمني، ولا يصح حسابه
    على كامل النافذة مرة واحدة. داخل الشمعة الواحدة نفترض **ضرب الوقف أولًا** (افتراض
    محافظ). تُعاد المحاكاة من الصفر في كل مسح فهي حتمية ولا تتراكم.
    """
    df = to_et(df)
    if trade.get("status") == "pending":
        trade = _activate_pending(trade, df, now)
        if trade.get("status") != "open":
            return trade
    if trade.get("status") != "open" or not trade.get("entry"):
        return trade
    try:
        entry_ts = pd.Timestamp(trade["entry_ts"]).tz_convert(C.MARKET_TZ)
    except (TypeError, ValueError):
        return trade

    future = df[df.index > entry_ts]
    if future.empty:
        trade["updated_at"] = now.isoformat()
        return trade

    entry = float(trade["entry"])
    risk_stop = float(trade["stop"])          # مخاطرة البداية — مرجع R لا يتغير
    targets = trade.get("targets") or []

    # ── إعادة المحاكاة من الصفر (حتمية)
    for target in targets:
        target["hit"] = False
        target["at"] = None
    trade["targets_hit"] = []
    trade["stop_hit"] = False
    trade["stop_at_break_even"] = False
    trade["trail_high"] = None

    highs = future["High"].astype(float)
    lows = future["Low"].astype(float)
    closes = future["Close"].astype(float)
    trade["bars_seen"] = int(len(future))
    trade["mfe_pct"] = round((float(highs.max()) / entry - 1.0) * 100.0, 2)
    trade["mae_pct"] = round((float(lows.min()) / entry - 1.0) * 100.0, 2)
    trade["last_price"] = round(float(closes.iloc[-1]), 4)
    trade["unrealized_pct"] = round((float(closes.iloc[-1]) / entry - 1.0) * 100.0, 2)
    trade["max_price"] = round(float(highs.max()), 4)

    main_target = (float(targets[1]["price"]) if len(targets) > 1
                   else float(targets[-1]["price"])) if targets else None
    current_stop = risk_stop
    trail_high = entry

    for ts, row in future.iterrows():
        high, low, close = float(row["High"]), float(row["Low"]), float(row["Close"])
        trade["hold_min"] = int((ts - entry_ts).total_seconds() / 60.0)

        # 1) الوقف أولًا — إن تحرّك إلى التعادل فالخروج يصبح بلا خسارة
        if low <= current_stop:
            trade["stop_hit"] = True
            trade["stop_at"] = ts.isoformat()
            close_trade(trade, EXIT_BREAK_EVEN if current_stop >= entry else EXIT_STOP,
                        current_stop, now, risk_stop=risk_stop)
            return trade

        # 2) الأهداف
        for target in targets:
            if not target["hit"] and high >= float(target["price"]):
                target["hit"] = True
                target["at"] = ts.isoformat()
                trade["targets_hit"].append({"label": target["label"], "at": target["at"]})
        trade["hit_labels"] = [t["label"] for t in targets if t["hit"]]

        # 3) تحقق الهدف الرئيسي ⇒ إغلاق رابح
        if main_target is not None and high >= main_target:
            close_trade(trade, EXIT_TARGET, main_target, now, risk_stop=risk_stop)
            return trade

        # 4) بعد T1: الوقف إلى التعادل، ثم وقف متحرك إن فُعّل
        if targets and targets[0]["hit"]:
            if C.MOVE_STOP_TO_BREAK_EVEN and not trade["stop_at_break_even"]:
                current_stop = max(current_stop, entry)
                trade["stop_at_break_even"] = True
                trade["be_at"] = ts.isoformat()
            if C.TRAIL_AFTER_T1_PCT:
                trail_high = max(trail_high, high)
                current_stop = max(current_stop,
                                   trail_high * (1.0 - float(C.TRAIL_AFTER_T1_PCT) / 100.0))
                trade["trail_high"] = round(trail_high, 4)

        # 5) انتهت مدة الرصد
        if trade["hold_min"] >= C.MAX_HOLD_MIN:
            close_trade(trade, EXIT_TIMEOUT, close, now, risk_stop=risk_stop)
            return trade

    trade["current_stop"] = round(current_stop, 4)
    trade["updated_at"] = now.isoformat()
    return trade


def _activate_pending(trade: dict, df: pd.DataFrame, now: datetime) -> dict:
    """يحوّل أمر الاختراق المعلّق إلى صفقة مفتوحة عند أول شمعة تخترق القمة."""
    trigger = float(trade.get("trigger") or 0.0)
    if trigger <= 0:
        return trade
    # الأمر وُلد الآن — لا يجوز أن «يُنفَّذ» بشمعة سبقت إنشاءه
    if trade.get("pending_since"):
        try:
            born = pd.Timestamp(trade["pending_since"]).tz_convert(C.MARKET_TZ)
            df = df[df.index > born]
        except (TypeError, ValueError):
            pass
    crossed = df[df["High"].astype(float) >= trigger]
    if crossed.empty:
        trade["updated_at"] = now.isoformat()
        return trade
    ts = crossed.index[0]
    trade.update({"status": "open", "entry": trigger, "entry_ts": ts.isoformat(),
                  "current_stop": trade["stop"], "activated_at": now.isoformat(),
                  "wait_min": int((ts - pd.Timestamp(trade["pending_since"]).tz_convert(
                      C.MARKET_TZ)).total_seconds() / 60.0)
                  if trade.get("pending_since") else 0})
    return trade


def close_trade(trade: dict, reason: str, price: float, now: datetime,
                risk_stop: float | None = None) -> dict:
    entry = float(trade["entry"])
    stop = float(risk_stop if risk_stop is not None else trade["stop"])
    risk = entry - stop
    trade["status"] = "closed"
    trade["exit_reason"] = reason
    trade["exit_label"] = EXIT_LABELS.get(reason, reason)
    trade["exit_price"] = round(float(price), 4)
    trade["exit_ts"] = now.isoformat()
    trade["r_multiple"] = round((float(price) - entry) / risk, 2) if risk > 0 else 0.0
    trade["result_pct"] = round((float(price) / entry - 1.0) * 100.0, 2)
    return trade


def expire_open(trades: list, session_date: str, now: datetime) -> list:
    """يغلق إشارات جلسة سابقة بسعرها الأخير المسجّل، ويُسقِط الأوامر المعلّقة."""
    for trade in trades:
        if trade.get("session_date") == session_date:
            continue
        if trade.get("status") == "pending":
            trade["status"] = "expired"          # لم يُنفَّذ فلا يُحسب في النتائج
            trade["exit_label"] = EXIT_LABELS["expired"]
            trade["updated_at"] = now.isoformat()
        elif trade.get("status") == "open":
            price = trade.get("last_price") or trade["entry"]
            close_trade(trade, EXIT_SESSION, float(price), now)
    return trades


def _bucket_drop(value) -> str:
    if value is None:
        return "غير معروف"
    v = float(value)
    if v <= -70:
        return "-70% أو أكثر"
    if v <= -50:
        return "-50% إلى -70%"
    if v <= -40:
        return "-40% إلى -50%"
    return "-30% إلى -40%"


def _win(trade: dict) -> bool:
    return float(trade.get("r_multiple") or 0.0) > 0


def summarize(closed: list) -> dict:
    """إحصاءات أداء الشروط على الإشارات المكتملة (ورقي)."""
    if not closed:
        return {"trades": 0}
    results = [float(t.get("r_multiple") or 0.0) for t in closed]
    wins = [r for r in results if r > 0]
    losses = [r for r in results if r <= 0]
    gross_win = sum(wins)
    gross_loss = abs(sum(losses))
    per_target = {}
    for label in ("T1", "T2", "T3"):
        hits = sum(1 for t in closed if label in (t.get("hit_labels") or []))
        per_target[label] = {"hits": hits, "rate_pct": round(hits / len(closed) * 100.0, 1)}
    by_grade, by_hour, by_drop = {}, {}, {}
    for trade in closed:
        for store, key in ((by_grade, str(trade.get("grade") or "?")),
                           (by_hour, "%02d:00" % pd.Timestamp(trade["entry_ts"]).hour
                            if pd.Timestamp(trade["entry_ts"]).tzinfo else "?"),
                           (by_drop, _bucket_drop(trade.get("drop_pct")))):
            row = store.setdefault(key, {"trades": 0, "wins": 0, "r_sum": 0.0})
            row["trades"] += 1
            row["wins"] += 1 if _win(trade) else 0
            row["r_sum"] = round(row["r_sum"] + float(trade.get("r_multiple") or 0.0), 2)
    for store in (by_grade, by_hour, by_drop):
        for row in store.values():
            row["win_rate_pct"] = round(row["wins"] / row["trades"] * 100.0, 1) if row["trades"] else None
            row["avg_r"] = round(row["r_sum"] / row["trades"], 2) if row["trades"] else None
    exits = {}
    for trade in closed:
        key = trade.get("exit_reason") or "unknown"
        exits[key] = exits.get(key, 0) + 1
    return {
        "trades": len(closed),
        "wins": len(wins), "losses": len(losses),
        "win_rate_pct": round(len(wins) / len(closed) * 100.0, 1),
        "avg_r": round(statistics.fmean(results), 2),
        "median_r": round(statistics.median(results), 2),
        "best_r": round(max(results), 2), "worst_r": round(min(results), 2),
        "expectancy_pct": round(statistics.fmean([float(t.get("result_pct") or 0.0) for t in closed]), 2),
        "profit_factor": round(gross_win / gross_loss, 2) if gross_loss > 0 else None,
        "avg_mfe_pct": round(statistics.fmean([float(t.get("mfe_pct") or 0.0) for t in closed]), 2),
        "avg_mae_pct": round(statistics.fmean([float(t.get("mae_pct") or 0.0) for t in closed]), 2),
        "avg_hold_min": round(statistics.fmean([float(t.get("hold_min") or 0.0) for t in closed]), 1),
        "targets": per_target,
        "by_grade": dict(sorted(by_grade.items())),
        "by_hour": dict(sorted(by_hour.items())),
        "by_drop": dict(sorted(by_drop.items())),
        "exits": {EXIT_LABELS.get(k, k): v for k, v in exits.items()},
    }


def update_stats(stats: dict, items: list, frames: dict, now: datetime, session_date: str) -> dict:
    """دورة كاملة: إغلاق القديم، فتح الجديد، تحديث المفتوح، ثم التجميع."""
    open_trades = [t for t in (stats.get("open") or [])]
    closed_trades = [t for t in (stats.get("closed") or [])]
    open_ids = {t["id"] for t in open_trades}
    alerts = []

    expire_open(open_trades, session_date, now)
    expired_pending = [t for t in open_trades if t.get("status") == "expired"]
    # «حيّ» تشمل الأوامر المعلّقة وإلا سقطت قبل أن تُختبر
    still_open = [t for t in open_trades if t.get("status") in ALIVE_STATUSES]
    closed_trades += [t for t in open_trades if t.get("status") == "closed"]
    open_trades = still_open

    by_ticker = {t["ticker"]: t for t in open_trades if t.get("status") == "open"}
    for item in items:
        if not item.get("complete"):
            continue
        key = _signal_id(item["ticker"], item.get("signal_date") or session_date)
        item["signal_id"] = key
        if any(t.get("signal_id") == key for t in open_trades) \
                or any(t.get("signal_id") == key or t["id"] == key for t in closed_trades):
            continue
        if sum(1 for t in open_trades if t.get("status") == "open") >= C.MAX_OPEN_TRACKED:
            continue
        for mode in (("market", "breakout") if C.TRACK_BREAKOUT_ENTRY else ("market",)):
            trade = open_trade(item, now, mode=mode)
            if trade is None:
                continue
            trade["signal_date"] = item.get("signal_date") or session_date
            open_trades.append(trade)
            open_ids.add(trade["id"])
            if mode == "market":
                by_ticker[trade["ticker"]] = trade
                alerts.append({"kind": "signal", "ticker": item["ticker"], "at": now.isoformat(),
                               "price": item.get("price"), "grade": item.get("grade"),
                               "score": item.get("score"),
                               "text": "إشارة مكتملة — بدأ الرصد الورقي"})
            else:
                alerts.append({"kind": "order", "ticker": item["ticker"], "at": now.isoformat(),
                               "price": trade.get("trigger"), "grade": item.get("grade"),
                               "text": "أمر معلّق عند اختراق القاعدة %.4f" % (trade.get("trigger") or 0)})

    for trade in open_trades:
        frame = frames.get(trade["ticker"])
        if frame is None:
            continue
        before = trade.get("status")
        update_trade(trade, frame, now)
        if before == "open" and trade.get("status") == "closed":
            alerts.append({"kind": "closed", "ticker": trade["ticker"], "at": now.isoformat(),
                           "price": trade.get("exit_price"), "reason": trade.get("exit_label"),
                           "r": trade.get("r_multiple"),
                           "text": "أُغلق الرصد: %s (%sR)" % (trade.get("exit_label"), trade.get("r_multiple"))})

    newly_closed = [t for t in open_trades if t.get("status") == "closed"]
    closed_trades += newly_closed
    open_trades = [t for t in open_trades if t.get("status") in ALIVE_STATUSES]
    # أمر معلّق نُفّذ خلال هذه الدورة ← تنبيه
    for trade in open_trades:
        if trade.get("status") == "open" and trade.get("mode") == "breakout" \
                and not trade.get("announced"):
            trade["announced"] = True
            alerts.append({"kind": "filled", "ticker": trade["ticker"], "at": now.isoformat(),
                           "price": trade.get("entry"), "grade": trade.get("grade"),
                           "text": "نُفّذ أمر الاختراق عند %.4f" % (trade.get("entry") or 0)})
    closed_trades = closed_trades[-C.KEEP_TRADES:]

    return {
        "updated_at": now.isoformat(),
        "session_date": session_date,
        "open": open_trades,
        "pending": [t for t in open_trades if t.get("status") == "pending"],
        "expired_pending": len(expired_pending),
        "closed": closed_trades,
        "summary": summarize(closed_trades),
        "open_summary": {
            "count": len(open_trades),
            "avg_unrealized_pct": round(statistics.fmean(
                [float(t.get("unrealized_pct") or 0.0) for t in open_trades]), 2) if open_trades else None,
            "targets_hit": sum(len(t.get("hit_labels") or []) for t in open_trades),
        },
        "alerts": alerts,
    }


__all__ = ["open_trade", "update_trade", "close_trade", "expire_open", "summarize",
           "update_stats", "EXIT_LABELS"]
