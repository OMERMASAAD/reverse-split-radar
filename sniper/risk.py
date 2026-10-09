# -*- coding: utf-8 -*-
"""
محرك المخاطر الورقي: وقف مبني على ATR وقاع القاعدة، ثلاثة أهداف، عائد/مخاطرة،
وحجم مركز على حساب ورقي مرجعي. لا تنفيذ أوامر — أرقام للتخطيط فقط.
"""
from __future__ import annotations

import math

from .config import (ACCOUNT_EQUITY, ATR_STOP_MULT, RISK_PER_TRADE_PCT,
                     STOP_MIN_BUFFER_PCT, TARGETS_PCT)


def stop_price(price: float, base_low: float, atr_value: float | None) -> tuple[float, str]:
    """الوقف = قاع الثبات − max(3%, 1.0 × ATR). يُعيد (السعر، طريقة الحساب)."""
    buffer_pct = STOP_MIN_BUFFER_PCT
    method = "قاع الثبات − %g%%" % STOP_MIN_BUFFER_PCT
    if atr_value and price > 0:
        atr_pct = float(atr_value) / float(price) * 100.0 * ATR_STOP_MULT
        if atr_pct > STOP_MIN_BUFFER_PCT:
            buffer_pct = atr_pct
            method = "قاع الثبات − %.1f%% (ATR×%g)" % (atr_pct, ATR_STOP_MULT)
    stop = float(base_low) * (1.0 - buffer_pct / 100.0)
    # لا نسمح بوقف أعلى من السعر الحالي (قاعدة مكسورة نظريًا)
    if stop >= price:
        stop = float(price) * (1.0 - max(STOP_MIN_BUFFER_PCT, 5.0) / 100.0)
        method = "نسبة ثابتة من السعر (القاعدة قرب السعر)"
    return round(stop, 4), method


def risk_plan(price: float, base_low: float, base_high: float | None,
              atr_value: float | None, equity: float = ACCOUNT_EQUITY) -> dict:
    """خطة مخاطرة كاملة: وقف، أهداف، R:R، حجم المركز الورقي."""
    price = float(price)
    if price <= 0:
        return {}
    stop, stop_method = stop_price(price, base_low, atr_value)
    risk_per_share = price - stop
    risk_pct = risk_per_share / price * 100.0 if price else 0.0
    targets = []
    for i, pct in enumerate(TARGETS_PCT, start=1):
        target = round(price * (1.0 + pct / 100.0), 4)
        reward = target - price
        targets.append({
            "number": i,
            "label": "T%d" % i,
            "pct": pct,
            "price": target,
            "rr": round(reward / risk_per_share, 2) if risk_per_share > 0 else None,
        })
    rr_t1 = targets[0]["rr"] if targets else None
    rr_t2 = targets[1]["rr"] if len(targets) > 1 else None
    rr_t3 = targets[2]["rr"] if len(targets) > 2 else None
    shares = 0
    position_value = 0.0
    risk_amount = equity * RISK_PER_TRADE_PCT / 100.0
    if risk_per_share > 0:
        shares = int(math.floor(risk_amount / risk_per_share))
        position_value = round(shares * price, 2)
    projection = None
    if base_high and base_low and base_high > base_low:
        projection = round(base_low + 2.0 * (base_high - base_low), 4)
    return {
        "entry": round(price, 4),
        "stop": stop,
        "stop_method": stop_method,
        "risk_per_share": round(risk_per_share, 4),
        "risk_pct": round(risk_pct, 2),
        "targets": targets,
        "target_pct": TARGETS_PCT[1],
        "target": targets[1]["price"] if len(targets) > 1 else None,
        "rr_t1": rr_t1, "rr_t2": rr_t2, "rr_t3": rr_t3,
        "measured_projection": projection,
        "atr": round(float(atr_value), 4) if atr_value else None,
        "atr_pct": round(float(atr_value) / price * 100.0, 2) if atr_value else None,
        "breakout_trigger": round(float(base_high), 4) if base_high else None,
        "equity": equity,
        "risk_amount": round(risk_amount, 2),
        "shares": shares,
        "position_value": position_value,
        "position_pct_of_equity": round(position_value / equity * 100.0, 2) if equity else None,
        "disclaimer": "حساب ورقي تعليمي — لا يوجد تنفيذ أوامر ولا توصية استثمارية.",
    }


__all__ = ["stop_price", "risk_plan"]
