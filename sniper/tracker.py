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

EXIT_LABELS = {
    EXIT_STOP: "ضرب الوقف",
    EXIT_TARGET: "تحقق الهدف",
    EXIT_TIMEOUT: "انتهت مدة الرصد",
    EXIT_SESSION: "إغلاق الجلسة",
    "open": "ما زالت مفتوحة",
}


def _signal_id(ticker: str, entry_date: str) -> str:
    return "%s|%s" % (ticker, entry_date)


def open_trade(item: dict, now: datetime) -> dict | None:
    """ينشئ سجل رصد ورقي لإشارة مكتملة (مرة واحدة لكل سهم في الجلسة)."""
    risk = item.get("risk") or {}
    if not risk or not risk.get("stop"):
        return None
    entry = float(item["price"])
    targets = risk.get("targets") or []
    return {
        "id": _signal_id(item["ticker"], item["signal_date"]),
        "ticker": item["ticker"],
        "session_date": item["signal_date"],
        "entry_ts": now.isoformat(),
        "entry": entry,
        "stop": risk["stop"],
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


def update_trade(trade: dict, df: pd.DataFrame, now: datetime) -> dict:
    """يعيد حساب MFE/MAE والأهداف من الشموع نفسها — آمن ضد التكرار."""
    df = to_et(df)
    try:
        entry_ts = pd.Timestamp(trade["entry_ts"]).tz_convert(C.MARKET_TZ)
    except (TypeError, ValueError):
        return trade
    entry = float(trade["entry"])
    stop = float(trade["stop"])
    future = df[df.index > entry_ts]
    if future.empty:
        return trade
    highs = future["High"].astype(float)
    lows = future["Low"].astype(float)
    closes = future["Close"].astype(float)
    trade["bars_seen"] = int(len(future))
    trade["hold_min"] = int((future.index[-1] - entry_ts).total_seconds() / 60.0)
    trade["mfe_pct"] = round(max(trade.get("mfe_pct") or 0.0, (float(highs.max()) / entry - 1.0) * 100.0), 2)
    trade["mae_pct"] = round(min(trade.get("mae_pct") or 0.0, (float(lows.min()) / entry - 1.0) * 100.0), 2)
    trade["last_price"] = round(float(closes.iloc[-1]), 4)
    trade["unrealized_pct"] = round((float(closes.iloc[-1]) / entry - 1.0) * 100.0, 2)
    risk = entry - stop

    for target in trade["targets"]:
        if not target["hit"]:
            hit_rows = future[highs >= float(target["price"])]
            if not hit_rows.empty:
                target["hit"] = True
                target["at"] = hit_rows.index[0].isoformat()
                trade["targets_hit"].append({"label": target["label"], "at": target["at"]})

    stop_rows = future[lows <= stop]
    if not stop_rows.empty and not trade["stop_hit"]:
        trade["stop_hit"] = True
        trade["stop_at"] = stop_rows.index[0].isoformat()

    hit_labels = [t["label"] for t in trade["targets"] if t["hit"]]
    main_target = trade["targets"][1]["price"] if len(trade["targets"]) > 1 else trade["targets"][-1]["price"]
    if trade["stop_hit"]:
        close_trade(trade, EXIT_STOP, stop, now)
    elif float(highs.max()) >= float(main_target):
        close_trade(trade, EXIT_TARGET, float(main_target), now)
    elif trade["hold_min"] >= C.MAX_HOLD_MIN:
        close_trade(trade, EXIT_TIMEOUT, float(closes.iloc[-1]), now)
    trade["hit_labels"] = hit_labels
    trade["updated_at"] = now.isoformat()
    return trade


def close_trade(trade: dict, reason: str, price: float, now: datetime) -> dict:
    entry, stop = float(trade["entry"]), float(trade["stop"])
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
    """يغلق إشارات جلسة سابقة بسعرها الأخير المسجّل (نهاية الجلسة)."""
    for trade in trades:
        if trade.get("status") == "open" and trade.get("session_date") != session_date:
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
    still_open = [t for t in open_trades if t.get("status") == "open"]
    closed_trades += [t for t in open_trades if t.get("status") == "closed"]
    open_trades = still_open

    by_ticker = {t["ticker"]: t for t in open_trades}
    for item in items:
        if not item.get("complete"):
            continue
        key = _signal_id(item["ticker"], item.get("signal_date") or session_date)
        item["signal_id"] = key
        if key in open_ids or any(t["id"] == key for t in closed_trades):
            continue
        if len(open_trades) >= C.MAX_OPEN_TRACKED:
            continue
        trade = open_trade(item, now)
        if trade is None:
            continue
        trade["signal_date"] = item.get("signal_date") or session_date
        open_trades.append(trade)
        by_ticker[trade["ticker"]] = trade
        open_ids.add(key)
        alerts.append({"kind": "signal", "ticker": item["ticker"], "at": now.isoformat(),
                       "price": item.get("price"), "grade": item.get("grade"),
                       "score": item.get("score"), "text": "إشارة مكتملة — بدأ الرصد الورقي"})

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
    open_trades = [t for t in open_trades if t.get("status") == "open"]
    closed_trades = closed_trades[-C.KEEP_TRADES:]

    return {
        "updated_at": now.isoformat(),
        "session_date": session_date,
        "open": open_trades,
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
