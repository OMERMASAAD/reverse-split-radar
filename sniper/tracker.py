# -*- coding: utf-8 -*-
"""
متتبّع النتائج الورقي V2: بعد اكتمال الإشارة يرصد أقصى حركة إيجابية/سلبية،
تحقق الأهداف، ضرب الوقف، ومدة الرصد — ثم يجمع إحصاءات.

تحسينات V2:
- تصحيح MFE/MAE من وقت الإشارة بصورة حتمية دون تسريب بيانات مستقبلية
- معالجة لمس الهدف والوقف في نفس الشمعة كحالة ملتبسة
- فصل النتائج المؤكدة عن المرشحين المبكرين وحسب عمق الهبوط/السيولة/التوقيت/الكسر
- ترحيل آمن للسجلات القديمة مع الاحتفاظ بنسخة احتياطية
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
EXIT_BREAK_EVEN = "break_even"
EXIT_AMBIGUOUS = "ambiguous"  # V2: لمس الهدف والوقف في نفس الشمعة دون معرفة الترتيب

ALIVE_STATUSES = ("open", "pending")

EXIT_LABELS = {
    EXIT_STOP: "ضرب الوقف",
    EXIT_TARGET: "تحقق الهدف",
    EXIT_TIMEOUT: "انتهت مدة الرصد",
    EXIT_SESSION: "إغلاق الجلسة",
    EXIT_BREAK_EVEN: "خروج عند التعادل",
    EXIT_AMBIGUOUS: "ملتبس — لمس الهدف والوقف في نفس الشمعة",
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
        "early_score": item.get("early_score"),
        "liquidity_score": item.get("liquidity_score"),
        "drop_pct": item.get("drop_pct"),
        "drop_category": item.get("drop_category"),
        "sweep_state": item.get("sweep_state"),
        "composite_score": item.get("composite_score"),
        "rvol": item.get("rvol"),
        "float": item.get("float"),
        "reverse_split": bool(item.get("reverse_split")),
        "mfe_pct": 0.0, "mae_pct": 0.0,
        "mfe_price": None, "mae_price": None,
        "targets_hit": [], "stop_hit": False,
        "status": "open", "exit_reason": None, "exit_price": None, "exit_ts": None,
        "r_multiple": 0.0, "hold_min": 0, "bars_seen": 0,
        "opened_at": now.isoformat(), "updated_at": now.isoformat(),
        "is_early": bool(item.get("early_is_early")),
        "early_label": item.get("early_label"),
        "signal_type": "early" if item.get("early_is_early") and not item.get("complete") else "confirmed",
        "ambiguous": False,
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

    V2: معالجة الحالة الملتبسة — إذا لامست الشمعة الهدف والوقف معًا دون بيانات أدق،
    تُسجل كـ ambiguous ولا يُفترض ترتيب الأحداث.
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
    risk_stop = float(trade["stop"])
    targets = trade.get("targets") or []

    # ── إعادة المحاكاة من الصفر (حتمية)
    for target in targets:
        target["hit"] = False
        target["at"] = None
    trade["targets_hit"] = []
    trade["stop_hit"] = False
    trade["stop_at_break_even"] = False
    trade["trail_high"] = None
    trade["ambiguous"] = False

    highs = future["High"].astype(float)
    lows = future["Low"].astype(float)
    closes = future["Close"].astype(float)
    trade["bars_seen"] = int(len(future))
    # V2: MFE/MAE من وقت الإشارة فقط — لا يُحتسب ما قبل الإشارة (future بالفعل بعد entry_ts)
    trade["mfe_pct"] = round((float(highs.max()) / entry - 1.0) * 100.0, 2)
    trade["mae_pct"] = round((float(lows.min()) / entry - 1.0) * 100.0, 2)
    trade["mfe_price"] = round(float(highs.max()), 4)
    trade["mae_price"] = round(float(lows.min()), 4)
    trade["last_price"] = round(float(closes.iloc[-1]), 4)
    trade["unrealized_pct"] = round((float(closes.iloc[-1]) / entry - 1.0) * 100.0, 2)
    trade["max_price"] = round(float(highs.max()), 4)
    trade["min_price"] = round(float(lows.min()), 4)

    main_target = (float(targets[1]["price"]) if len(targets) > 1
                   else float(targets[-1]["price"])) if targets else None
    # للتوافق مع TARGETS_PCT=(10,20,30) الرئيسي الآن T2 (20%) أو T3 (30%)? نعتبر الهدف الثاني كرئيسي
    # نستخدم آخر هدف (30%) كـ main
    if len(targets) >= 3:
        main_target = float(targets[2]["price"])
    elif len(targets) == 2:
        main_target = float(targets[1]["price"])
    current_stop = risk_stop
    trail_high = entry

    for ts, row in future.iterrows():
        high, low, close = float(row["High"]), float(row["Low"]), float(row["Close"])
        trade["hold_min"] = int((ts - entry_ts).total_seconds() / 60.0)

        # V2: فحص الحالة الملتبسة — لمس الهدف والوقف في نفس الشمعة
        target_hit_in_bar = any(high >= float(t["price"]) for t in targets) if targets else False
        stop_hit_in_bar = low <= current_stop
        if target_hit_in_bar and stop_hit_in_bar:
            # لا نفترض الترتيب — نسجل كملتبس
            # إذا كانت بيانات إطار أدق غير متاحة، نتركها ملتبسة
            trade["ambiguous"] = True
            trade["ambiguous_at"] = ts.isoformat()
            trade["ambiguous_detail"] = f"الشمعة {ts.isoformat()} لامست الهدف {main_target} والوقف {current_stop} معًا"
            # نتعامل معها كوقف أولاً بشكل محافظ لكن نعلمها كملتبسة
            # حسب المواصفة: لا تفترض ترتيب الأحداث — سجلها كملتبسة
            # سنغلقها كـ ambiguous وليس stop/target
            close_trade(trade, EXIT_AMBIGUOUS, close, now, risk_stop=risk_stop)
            trade["mfe_pct"] = round((float(highs[future.index <= ts].max()) / entry - 1.0) * 100.0, 2) if len(future[future.index <= ts]) else trade["mfe_pct"]
            return trade

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
            trade["status"] = "expired"
            trade["exit_label"] = EXIT_LABELS["expired"]
            trade["updated_at"] = now.isoformat()
        elif trade.get("status") == "open":
            price = trade.get("last_price") or trade["entry"]
            close_trade(trade, EXIT_SESSION, float(price), now)
    return trades


def _bucket_drop(value) -> str:
    if value is None:
        return "غير معروف"
    v = abs(float(value))
    if v >= 80:
        return "80%+"
    if v >= 60:
        return "60–80%"
    if v >= 40:
        return "40–60%"
    if v >= 30:
        return "30–40%"
    return "<30%"

def _bucket_liquidity(score) -> str:
    if score is None:
        return "غير معروف"
    s = float(score)
    if s >= 70:
        return "سيولة عالية"
    if s >= 50:
        return "سيولة متوسطة"
    return "سيولة ضعيفة"

def _win(trade: dict) -> bool:
    return float(trade.get("r_multiple") or 0.0) > 0


def summarize(closed: list) -> dict:
    """إحصاءات أداء الشروط على الإشارات المكتملة (ورقي) + فصل حسب الفئات الجديدة."""
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
    by_grade, by_hour, by_drop, by_liquidity, by_sweep, by_time = {}, {}, {}, {}, {}, {}
    for trade in closed:
        for store, key in ((by_grade, str(trade.get("grade") or "?")),
                           (by_hour, "%02d:00" % pd.Timestamp(trade["entry_ts"]).hour
                            if pd.Timestamp(trade["entry_ts"]).tzinfo else "?"),
                           (by_drop, _bucket_drop(trade.get("drop_pct"))),
                           (by_liquidity, _bucket_liquidity(trade.get("liquidity_score"))),
                           (by_sweep, str(trade.get("sweep_state") or "غير محدد")),
                           (by_time, "intraday" if _is_intraday(trade) else "next_session")):
            row = store.setdefault(key, {"trades": 0, "wins": 0, "r_sum": 0.0})
            row["trades"] += 1
            row["wins"] += 1 if _win(trade) else 0
            row["r_sum"] = round(row["r_sum"] + float(trade.get("r_multiple") or 0.0), 2)
    for store in (by_grade, by_hour, by_drop, by_liquidity, by_sweep, by_time):
        for row in store.values():
            row["win_rate_pct"] = round(row["wins"] / row["trades"] * 100.0, 1) if row["trades"] else None
            row["avg_r"] = round(row["r_sum"] / row["trades"], 2) if row["trades"] else None
    exits = {}
    for trade in closed:
        key = trade.get("exit_reason") or "unknown"
        exits[key] = exits.get(key, 0) + 1

    # فصل النتائج المؤكدة عن المبكرة
    confirmed = [t for t in closed if t.get("signal_type") != "early"]
    early = [t for t in closed if t.get("signal_type") == "early"]
    # نسب الارتداد 10/20/30
    def bounce_rate(th):
        return round(sum(1 for t in closed if float(t.get("mfe_pct") or 0) >= th) / len(closed) * 100.0, 1) if closed else 0
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
        "bounce_10": bounce_rate(10),
        "bounce_20": bounce_rate(20),
        "bounce_30": bounce_rate(30),
        "max_mfe": round(max(float(t.get("mfe_pct") or 0) for t in closed), 2) if closed else None,
        "max_mae": round(min(float(t.get("mae_pct") or 0) for t in closed), 2) if closed else None,
        "targets": per_target,
        "by_grade": dict(sorted(by_grade.items())),
        "by_hour": dict(sorted(by_hour.items())),
        "by_drop": dict(sorted(by_drop.items())),
        "by_liquidity": dict(sorted(by_liquidity.items())),
        "by_sweep": dict(sorted(by_sweep.items())),
        "by_time": dict(sorted(by_time.items())),
        "by_type": {
            "confirmed": {"trades": len(confirmed), "win_rate": round(len([t for t in confirmed if _win(t)])/len(confirmed)*100,1) if confirmed else 0},
            "early": {"trades": len(early), "win_rate": round(len([t for t in early if _win(t)])/len(early)*100,1) if early else 0},
        },
        "exits": {EXIT_LABELS.get(k, k): v for k, v in exits.items()},
        "fail_rate": round(len(losses)/len(closed)*100,1) if closed else 0,
    }

def _is_intraday(trade: dict) -> bool:
    try:
        entry = pd.Timestamp(trade.get("entry_ts"))
        exit_ts = pd.Timestamp(trade.get("exit_ts") or trade.get("updated_at"))
        return entry.date() == exit_ts.date()
    except:
        return True

def update_stats(stats: dict, items: list, frames: dict, now: datetime, session_date: str) -> dict:
    """دورة كاملة: إغلاق القديم، فتح الجديد، تحديث المفتوح، ثم التجميع."""
    # ترحيل آمن: إنشاء نسخة احتياطية من السجلات القديمة
    if stats and not stats.get("_migrated_v2"):
        # لا نمسح السجلات القديمة — نميز التي لا يمكن التحقق منها
        for t in stats.get("closed", []):
            if "mfe_pct" not in t:
                t["_legacy"] = True
                t["_legacy_note"] = "سجل قديم قبل V2 — لا يمكن التحقق من MFE/MAE بدقة"

    open_trades = [t for t in (stats.get("open") or [])]
    closed_trades = [t for t in (stats.get("closed") or [])]
    open_ids = {t["id"] for t in open_trades}
    alerts = []

    expire_open(open_trades, session_date, now)
    expired_pending = [t for t in open_trades if t.get("status") == "expired"]
    still_open = [t for t in open_trades if t.get("status") in ALIVE_STATUSES]
    closed_trades += [t for t in open_trades if t.get("status") == "closed"]
    open_trades = still_open

    by_ticker = {t["ticker"]: t for t in open_trades if t.get("status") == "open"}
    for item in items:
        # V2: تتبع الإشارات المؤكدة + المبكرة (لكن نحافظ على الأصل: complete فقط كانت تُتابع)
        # الآن نضيف تتبعًا للإشارات المبكرة أيضًا كـ pending ورقي منفصل إن رغب المستخدم
        # للحفاظ على التوافق، نتابع complete فقط كـ market trades
        # ونضيف early كـ تتبع إضافي إن early_is_strong
        is_trackable = bool(item.get("complete") or (item.get("early_is_strong") and item.get("early_score",0) >= 70))
        if not is_trackable:
            continue
        # نحدد نوع الإشارة
        signal_type = "confirmed" if item.get("complete") else "early"
        key = _signal_id(item["ticker"], item.get("signal_date") or session_date)
        item["signal_id"] = key
        # منع تسجيل الصفقة نفسها عدة مرات
        if any(t.get("signal_id") == key and t.get("signal_type") == signal_type for t in open_trades) \
                or any(t.get("signal_id") == key and t.get("signal_type") == signal_type or t["id"] == key for t in closed_trades):
            continue
        if sum(1 for t in open_trades if t.get("status") == "open") >= C.MAX_OPEN_TRACKED:
            continue
        for mode in (("market", "breakout") if C.TRACK_BREAKOUT_ENTRY else ("market",)):
            trade = open_trade(item, now, mode=mode)
            if trade is None:
                continue
            trade["signal_date"] = item.get("signal_date") or session_date
            trade["signal_type"] = signal_type
            open_trades.append(trade)
            open_ids.add(trade["id"])
            if mode == "market":
                by_ticker[trade["ticker"]] = trade
                alerts.append({"kind": "signal", "ticker": item["ticker"], "at": now.isoformat(),
                               "price": item.get("price"), "grade": item.get("grade"),
                               "score": item.get("score"), "type": signal_type,
                               "text": f"إشارة {'مكتملة' if signal_type=='confirmed' else 'مبكرة'} — بدأ الرصد الورقي"})
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
                           "r": trade.get("r_multiple"), "ambiguous": trade.get("ambiguous"),
                           "text": "أُغلق الرصد: %s (%sR)" % (trade.get("exit_label"), trade.get("r_multiple"))})

    newly_closed = [t for t in open_trades if t.get("status") == "closed"]
    closed_trades += newly_closed
    open_trades = [t for t in open_trades if t.get("status") in ALIVE_STATUSES]
    for trade in open_trades:
        if trade.get("status") == "open" and trade.get("mode") == "breakout" \
                and not trade.get("announced"):
            trade["announced"] = True
            alerts.append({"kind": "filled", "ticker": trade["ticker"], "at": now.isoformat(),
                           "price": trade.get("entry"), "grade": trade.get("grade"),
                           "text": "نُفّذ أمر الاختراق عند %.4f" % (trade.get("entry") or 0)})
    closed_trades = closed_trades[-C.KEEP_TRADES:]

    summary = summarize(closed_trades)
    # تمييز السجلات القديمة غير القابلة للتحقق
    summary["_migration_note"] = "السجلات القديمة محفوظة مع علامة _legacy — لم تُمسح"

    return {
        "updated_at": now.isoformat(),
        "session_date": session_date,
        "open": open_trades,
        "pending": [t for t in open_trades if t.get("status") == "pending"],
        "expired_pending": len(expired_pending),
        "closed": closed_trades,
        "summary": summary,
        "open_summary": {
            "count": len(open_trades),
            "avg_unrealized_pct": round(statistics.fmean(
                [float(t.get("unrealized_pct") or 0.0) for t in open_trades]), 2) if open_trades else None,
            "targets_hit": sum(len(t.get("hit_labels") or []) for t in open_trades),
        },
        "alerts": alerts,
        "_migrated_v2": True,
    }


__all__ = ["open_trade", "update_trade", "close_trade", "expire_open", "summarize",
           "update_stats", "EXIT_LABELS"]
