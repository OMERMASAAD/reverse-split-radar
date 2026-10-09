# -*- coding: utf-8 -*-
"""
محرك المخاطرة الورقي.

- **الوقف**: قاع الثبات − 5% (أو ATR إذا كان أوسع).
- **الدخول**: وضعان — فوري أعلى القاع، أو عند اختراق قمة القاعدة.
- **الأهداف**: +20% و+30%، مع فحص أن كليهما **قبل خط VWAP** (السقف المقاوم).

لا تنفيذ أوامر — أرقام للتخطيط والقياس فقط.
"""
from __future__ import annotations

import math

from .config import (ACCOUNT_EQUITY, ATR_STOP_MULT, RISK_PER_TRADE_PCT,
                     STOP_BUFFER_PCT, TARGETS_PCT)

ENTRY_MARKET = "market"
ENTRY_BREAKOUT = "breakout"

ENTRY_LABELS = {
    ENTRY_MARKET: "دخول فوري أعلى القاع",
    ENTRY_BREAKOUT: "دخول عند اختراق قمة القاعدة",
}


def stop_price(price: float, base_low: float, atr_value: float | None) -> tuple[float, str]:
    """الوقف = قاع الثبات − 5% (أو − ATR×المعامل إذا كان أوسع)."""
    buffer_pct = STOP_BUFFER_PCT
    method = "قاع الثبات − %g%%" % STOP_BUFFER_PCT
    if atr_value and price > 0:
        atr_pct = float(atr_value) / float(price) * 100.0 * ATR_STOP_MULT
        if atr_pct > STOP_BUFFER_PCT:
            buffer_pct = atr_pct
            method = "قاع الثبات − %.1f%% (ATR×%g أوسع)" % (atr_pct, ATR_STOP_MULT)
    stop = float(base_low) * (1.0 - buffer_pct / 100.0)
    if stop >= price:                      # القاعدة ملاصقة للسعر: وقفة نسبية آمنة
        stop = float(price) * (1.0 - max(STOP_BUFFER_PCT, 5.0) / 100.0)
        method = "نسبة ثابتة من السعر (القاعدة قرب السعر)"
    return round(stop, 4), method


VWAP_MARGIN_PCT = 0.5      # هامش أمان قبل خط VWAP عند اعتباره سقفًا


def _targets(entry: float, stop: float, vwap: float | None,
             vwap_is_ceiling: bool = False) -> list[dict]:
    """
    أهداف نسبةً من سعر الدخول (+20% و+30%).

    إذا كان VWAP فوق السعر فهو **سقف مقاوم** → أي هدف يخترقه يُعرض أيضًا بسعر
    مُقيَّد قبل الخط بهامش أمان، مع R:R الخاص به. وإذا كان السعر فوق VWAP فالخط
    دعم سفلي والأهداف حرة.
    """
    risk = entry - stop
    out = []
    for i, pct in enumerate(TARGETS_PCT, start=1):
        price = round(entry * (1.0 + pct / 100.0), 4)
        row = {
            "number": i, "label": "T%d" % i, "pct": pct, "price": price,
            "rr": round((price - entry) / risk, 2) if risk > 0 else None,
            "before_vwap": (bool(price < vwap) if vwap else None),
            "dist_to_vwap_pct": round((vwap / price - 1.0) * 100.0, 2) if vwap else None,
            "capped": False, "capped_price": None, "capped_rr": None,
        }
        if vwap_is_ceiling and vwap and price >= vwap and vwap > entry:
            capped = round(vwap * (1.0 - VWAP_MARGIN_PCT / 100.0), 4)
            row.update({"capped": True, "capped_price": capped,
                        "capped_pct": round((capped / entry - 1.0) * 100.0, 2),
                        "capped_rr": round((capped - entry) / risk, 2) if risk > 0 else None})
        out.append(row)
    return out


def risk_plan(price: float, base_low: float, base_high: float | None,
              atr_value: float | None, vwap: float | None = None,
              equity: float = ACCOUNT_EQUITY) -> dict:
    """خطة مخاطرة كاملة: وقف، وضعان للدخول، أهداف، R:R، حجم مركز ورقي، وسقف VWAP."""
    price = float(price)
    if price <= 0:
        return {}
    stop, stop_method = stop_price(price, base_low, atr_value)
    vwap_is_ceiling = bool(vwap and vwap > price)   # السعر تحت الخط ← الخط مقاومة
    modes = []
    for key in (ENTRY_MARKET, ENTRY_BREAKOUT):
        entry = price if key == ENTRY_MARKET else float(base_high or price)
        if key == ENTRY_BREAKOUT and (not base_high or entry <= stop):
            continue
        targets = _targets(entry, stop, vwap, vwap_is_ceiling and entry <= float(vwap))
        risk_per_share = entry - stop
        risk_amount = equity * RISK_PER_TRADE_PCT / 100.0
        shares = int(math.floor(risk_amount / risk_per_share)) if risk_per_share > 0 else 0
        modes.append({
            "key": key, "label": ENTRY_LABELS[key],
            "entry": round(entry, 4),
            "stop": stop,
            "risk_per_share": round(risk_per_share, 4),
            "risk_pct": round(risk_per_share / entry * 100.0, 2) if entry else None,
            "targets": targets,
            "rr_t1": targets[0]["rr"] if targets else None,
            "rr_t2": targets[1]["rr"] if len(targets) > 1 else None,
            "shares": shares,
            "position_value": round(shares * entry, 2),
            "distance_pct": round((entry / price - 1.0) * 100.0, 2) if key == ENTRY_BREAKOUT else 0.0,
        })
    primary = modes[0] if modes else {}
    targets = primary.get("targets") or []
    below = [t for t in targets if t.get("before_vwap") is True]
    above = [t for t in targets if t.get("before_vwap") is False]
    capped = [t for t in targets if t.get("capped")]
    projection = None
    if base_high and base_low and base_high > base_low:
        projection = round(base_low + 2.0 * (base_high - base_low), 4)
    return {
        "entry": primary.get("entry"), "stop": stop, "stop_method": stop_method,
        "risk_per_share": primary.get("risk_per_share"), "risk_pct": primary.get("risk_pct"),
        "targets": targets,
        "target_pct": TARGETS_PCT[0],
        "target": targets[0]["price"] if targets else None,
        "target_2": targets[1]["price"] if len(targets) > 1 else None,
        "rr_t1": primary.get("rr_t1"), "rr_t2": primary.get("rr_t2"),
        "rr_t3": targets[2]["rr"] if len(targets) > 2 else None,
        "entry_modes": modes,
        "breakout_trigger": round(float(base_high), 4) if base_high else None,
        "measured_projection": projection,
        "vwap": _round(vwap),
        "vwap_role": ("سقف مقاوم — الأهداف قبله" if vwap_is_ceiling else
                      "دعم سفلي — السعر فوقه" if vwap else "غير متاح"),
        "vwap_is_ceiling": vwap_is_ceiling,
        "targets_below_vwap": len(below),
        "targets_above_vwap": len(above),
        "targets_capped": len(capped),
        "vwap_note": _vwap_note(targets, below, capped, vwap),
        "dist_to_vwap_pct": round((float(vwap) / price - 1.0) * 100.0, 2) if vwap else None,
        "atr": _round(atr_value),
        "atr_pct": round(float(atr_value) / price * 100.0, 2) if atr_value else None,
        "equity": equity,
        "risk_amount": round(equity * RISK_PER_TRADE_PCT / 100.0, 2),
        "shares": primary.get("shares", 0),
        "position_value": primary.get("position_value", 0.0),
        "position_pct_of_equity": round(primary.get("position_value", 0.0) / equity * 100.0, 2) if equity else None,
        "disclaimer": "حساب ورقي تعليمي — لا يوجد تنفيذ أوامر ولا توصية استثمارية.",
    }


def _vwap_note(targets: list[dict], below: list[dict], capped: list[dict],
               vwap: float | None) -> str:
    """جملة صريحة عن علاقة الأهداف بخط VWAP — بلا مجاملة."""
    if not targets:
        return "—"
    if not vwap:
        return "خط VWAP غير متاح للقياس"
    if capped:
        return ("%d هدف يخترق السقف — السعر المُقيَّد قبل الخط معروض" % len(capped)
                if len(capped) > 1 else
                "هدف واحد يخترق السقف — السعر المُقيَّد قبل الخط معروض")
    if len(below) == len(targets):
        return "كل الأهداف تقع قبل خط VWAP ✓"
    return "السعر فوق VWAP فلم يعد الخط سقفًا؛ الأهداف حرة فوقه"


def _round(value, digits=4):
    if value is None:
        return None
    try:
        return round(float(value), digits)
    except (TypeError, ValueError):
        return None


__all__ = ["stop_price", "risk_plan", "ENTRY_MARKET", "ENTRY_BREAKOUT", "ENTRY_LABELS"]
