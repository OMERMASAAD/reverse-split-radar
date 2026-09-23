# -*- coding: utf-8 -*-
"""Four-stage paper radar for post reverse-split double-bottom setups."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import pandas as pd
import yfinance as yf

CANDIDATES = "reverse_split_candidates.json"
OUTPUT = "daily_signals.json"
HISTORY = "paper_signal_history.json"
STAGES = {"WATCHLIST": "قائمة مرصودة", "FOLLOW_UP": "مرحلة متابعة", "ALMOST_READY": "شبه جاهزة", "READY_ENTRY": "جاهزة فنيًا · فرصة دخول"}

def num(value):
    try:
        value = float(value)
        return None if np.isnan(value) else value
    except (TypeError, ValueError):
        return None

def candle_rows(data, limit):
    rows = []
    for stamp, row in data.tail(limit).iterrows():
        values = {"date": stamp.isoformat(), "open": num(row.get("Open")), "high": num(row.get("High")), "low": num(row.get("Low")), "close": num(row.get("Close"))}
        if all(values[key] is not None for key in ("open", "high", "low", "close")):
            rows.append(values)
    return rows

def rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(period, min_periods=period).mean()
    loss = (-delta.clip(upper=0)).rolling(period, min_periods=period).mean()
    return 100 - 100 / (1 + gain / loss.replace(0, np.nan))

def fetch_data(ticker, split_date):
    data = yf.Ticker(ticker).history(start=pd.Timestamp(split_date)-pd.Timedelta(days=5), end=pd.Timestamp.now(tz="UTC").tz_localize(None)+pd.Timedelta(days=1), interval="1d", auto_adjust=False, actions=False)
    if data is None or data.empty:
        return pd.DataFrame()
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    data.index = pd.to_datetime(data.index).tz_localize(None)
    return data[data.index >= pd.Timestamp(split_date)].copy()

def fetch_4h_data(ticker, split_date):
    data = yf.Ticker(ticker).history(start=pd.Timestamp(split_date), end=pd.Timestamp.now(tz="UTC").tz_localize(None)+pd.Timedelta(days=1), interval="4h", auto_adjust=False, actions=False)
    if data is None or data.empty:
        return pd.DataFrame()
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    data.index = pd.to_datetime(data.index).tz_localize(None)
    return data

def support_info(data):
    recent = data.tail(min(20, len(data)))
    support = float(recent.Low.min())
    tol = max(abs(support) * 0.05, 0.0001)
    touches = int((recent.Low <= support + tol).sum())
    last5 = data.tail(5)
    # ثبات الدعم يعني أن السعر أمضى 5 جلسات متتالية فوق أرضية الدعم
    # حتى لو ارتفعت القمم؛ لا نقارن نطاق القمم/القيعان ببعضه.
    stable = len(last5) >= 5 and bool((last5.Low >= support - tol).all()) and bool((last5.Close >= support - tol).all())
    return support, touches, stable

def find_double_bottom(data):
    if len(data) < 9:
        return {"formed": False, "breakout": False, "neckline": None}
    lows, highs, closes = data.Low.astype(float).to_numpy(), data.High.astype(float).to_numpy(), data.Close.astype(float).to_numpy()
    best = None
    start = max(0, len(data) - 30)
    for left in range(start, len(data)-4):
        for right in range(left+3, len(data)-1):
            a, b = lows[left], lows[right]
            if a <= 0 or abs(a-b)/min(a,b) > 0.12:
                continue
            neckline = float(highs[left+1:right].max())
            if neckline < max(a,b) * 1.05:
                continue
            if best is None or right > best[0]:
                best = (right, a, b, neckline)
    if best is None:
        return {"formed": False, "breakout": False, "neckline": None}
    right, left_low, right_low, neckline = best
    breakout = right < len(closes)-1 and len(closes) >= 2 and bool((closes[-2:] > neckline).all())
    return {"formed": True, "breakout": breakout, "neckline": neckline, "left_trough": left_low, "right_trough": right_low}

def resistance_targets(daily, entry_price, split_day_high, max_levels=4):
    """Return ascending resistance levels, ending at the split-day high."""
    if entry_price is None:
        return []
    levels = []
    highs = daily.High.astype(float).tail(60).to_numpy()
    for level in sorted(set(round(float(x), 4) for x in highs if float(x) > entry_price * 1.03)):
        if not levels or level > levels[-1] * 1.03:
            levels.append(level)
    final = float(split_day_high)
    levels = [x for x in levels if x < final * 0.995]
    # نحتفظ بأوضح المستويات فقط، ثم نضيف قمة يوم التقسيم كهدف نهائي.
    levels = levels[-max(1, max_levels - 1):]
    levels.append(round(final, 4))
    return [{"number": i + 1, "price": level, "type": "split_day_high" if level == round(final, 4) else "resistance"} for i, level in enumerate(levels)]

def analyze(row):
    ticker, split_date = row["ticker"], row["split_date"]
    try:
        data = fetch_data(ticker, split_date)
        if data.empty:
            return {"ticker": ticker, "status": "unavailable", "reason": "no_daily_data"}
        if len(data) < 20:
            return {"ticker": ticker, "status": "insufficient", "reason": "أقل من 20 جلسة بعد التقسيم"}
        data["rsi"] = rsi(data.Close)
        for period in (20, 30, 50):
            data[f"ema{period}"] = data.Close.ewm(span=period, adjust=False, min_periods=period).mean()
        data["volume_ratio"] = data.Volume / data.Volume.rolling(20, min_periods=5).mean()
        age, first, last = len(data)-1, data.iloc[0], data.iloc[-1]
        if float(last.Close) < 1.0:
            return {"ticker": ticker, "company": row.get("company"), "status": "excluded", "reason": "السعر الحالي أقل من 1.00 دولار", "price": num(last.Close)}
        split_open, split_gain = float(first.Open), (float(first.High)/float(first.Open)-1)*100
        drawdown = (float(last.Close)/split_open-1)*100 if split_open else 0
        support, touches, stable = support_info(data)
        oversold = pd.notna(last.rsi) and float(last.rsi) < 30
        below_emas = all(pd.notna(last[f"ema{p}"]) and float(last.Close) < float(last[f"ema{p}"]) for p in (20,30,50))
        intraday = fetch_4h_data(ticker, split_date)
        pattern_daily = find_double_bottom(data)
        pattern_4h = find_double_bottom(intraday) if not intraday.empty else {"formed": False, "breakout": False, "neckline": None}
        pattern = pattern_4h if pattern_4h["formed"] else pattern_daily
        age_ok, split_ok, drop_ok = 20 <= age <= 50, split_gain <= 20, -60 <= drawdown <= -40
        follow = age_ok and split_ok and drop_ok
        multi_tf_pattern = pattern_daily["formed"] and pattern_4h["formed"]
        multi_tf_breakout = pattern_daily["breakout"] and pattern_4h["breakout"]
        almost = follow and stable and oversold and below_emas and multi_tf_pattern
        ready = almost and multi_tf_breakout
        stage = "READY_ENTRY" if ready else "ALMOST_READY" if almost else "FOLLOW_UP" if follow else "WATCHLIST"
        missing = [label for ok,label in [(age_ok,"العمر 20–50 جلسة"),(split_ok,"صعود يوم التقسيم <=20%"),(drop_ok,"هبوط 40–60% من افتتاح التقسيم"),(stable,"ثبات فوق الدعم 5 جلسات"),(oversold,"RSI تحت 30"),(below_emas,"السعر تحت EMA20/30/50"),(pattern_daily["formed"],"قاع مزدوج على اليومي"),(pattern_4h["formed"],"قاع مزدوج على 4 ساعات"),(multi_tf_breakout,"اختراق خط العنق والثبات على الفريمين")] if not ok]
        entry_price = num(last.Close) if ready else num(pattern.get("neckline"))
        daily_targets = resistance_targets(data, entry_price, float(first.High), 4) if entry_price is not None else []
        four_hour_targets = resistance_targets(intraday, entry_price, float(first.High), 5) if entry_price is not None and not intraday.empty else []
        return {"ticker":ticker,"company":row.get("company"),"split_date":split_date,"status":"ok","stage":stage,"stage_label":STAGES[stage],"paper_signal":ready,"signal_date":last.name.date().isoformat() if ready else None,"signal_price":num(last.Close) if ready else None,"price":num(last.Close),"days_since_split":age,"split_day_open":num(split_open),"split_day_high":num(first.High),"split_day_gain_percent":round(split_gain,2),"drawdown_from_split_open_percent":round(drawdown,2),"support_price":num(support),"support_touches":touches,"support_stable_5_sessions":stable,"rsi":num(last.rsi),"oversold_under_30":bool(oversold),"below_ema20":bool(pd.notna(last.ema20) and last.Close < last.ema20),"below_ema30":bool(pd.notna(last.ema30) and last.Close < last.ema30),"below_ema50":bool(pd.notna(last.ema50) and last.Close < last.ema50),"below_all_ema":bool(below_emas),"volume_ratio":num(last.volume_ratio),"daily_double_bottom_formed":pattern_daily["formed"],"four_hour_double_bottom_formed":pattern_4h["formed"],"double_bottom_formed":multi_tf_pattern,"neckline_price":num(pattern.get("neckline")),"left_trough":num(pattern.get("left_trough")),"right_trough":num(pattern.get("right_trough")),"daily_breakout_confirmed":pattern_daily["breakout"],"four_hour_breakout_confirmed":pattern_4h["breakout"],"neckline_breakout_confirmed":multi_tf_breakout,"resistance_targets":daily_targets,"daily_resistance_targets":daily_targets,"four_hour_resistance_targets":four_hour_targets,"daily_candles":candle_rows(data,60),"four_hour_candles":candle_rows(intraday,96),"missing_conditions":missing,"research_note":"التحليل اليومي للأهلية و4 ساعات لتأكيد النموذج، مع عرض 4 مقاومات يومية و5 مقاومات على 4 ساعات كحد أقصى. المتوسطات EMA20/30/50. آخر هدف قمة يوم التقسيم."}
    except Exception as exc:
        return {"ticker":ticker,"status":"error","reason":str(exc)[:180]}

def main():
    rows = json.loads(Path(CANDIDATES).read_text(encoding="utf-8"))
    results = [analyze(row) for row in rows]
    ok = {item["ticker"]: item for item in results if item.get("status") == "ok"}
    ok = list(ok.values())
    groups = {key: [item for item in ok if item.get("stage") == key] for key in STAGES}
    try: history = json.loads(Path(HISTORY).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError): history = []
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    by_id = {item.get("id"): item for item in history if isinstance(item,dict) and item.get("id")}
    for item in groups["READY_ENTRY"]:
        key = f"{item['ticker']}|{item['signal_date']}"
        old = by_id.get(key, {"id":key,"ticker":item["ticker"],"signal_date":item["signal_date"],"signal_price":item["signal_price"],"first_seen":now,"status":"monitoring","success":False})
        old.update({"last_seen":now,"latest_price":item["price"],"latest_stage":item["stage"]})
        by_id[key] = old
    history = list(by_id.values())
    excluded = sum(item.get("status") == "excluded" for item in results)
    unavailable = sum(item.get("status") in {"unavailable", "insufficient", "error"} for item in results)
    payload = {"generated_at":now,"methodology":{"purpose":"مراقبة تجريبية فقط بلا تنفيذ صفقات","stages":STAGES,"entry":"قاع مزدوج مكتمل ثم اختراق خط العنق مع الثبات بإغلاقين متتاليين فوقه","rules":"Reverse Split بعمر 20–50 جلسة، السعر الحالي >= 1.00 دولار، ارتفاع يوم التقسيم <=20%، هبوط 40–60% من افتتاحه، ثبات فوق الدعم 5 جلسات، RSI<30، والسعر تحت EMA20/30/50"},"summary":{"candidates":len(rows),"ok":len(ok),"ready_entry":len(groups["READY_ENTRY"]),"almost_ready":len(groups["ALMOST_READY"]),"follow_up":len(groups["FOLLOW_UP"]),"watchlist":len(groups["WATCHLIST"]),"paper_entries":len(groups["READY_ENTRY"]),"base_watches":len(groups["FOLLOW_UP"]),"unavailable":unavailable,"excluded_under_1":excluded,"history_records":len(history)},"ready_entry":groups["READY_ENTRY"],"almost_ready":groups["ALMOST_READY"],"follow_up":groups["FOLLOW_UP"],"watchlist":groups["WATCHLIST"],"signals":groups["READY_ENTRY"],"history":history,"all":results}
    Path(HISTORY).write_text(json.dumps(history,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    Path(OUTPUT).write_text(json.dumps(payload,ensure_ascii=False,indent=2,default=str)+"\n",encoding="utf-8")
    print(json.dumps(payload["summary"],ensure_ascii=False))

if __name__ == "__main__": main()

# deterministic test hook
analyze_row_for_test = find_double_bottom
