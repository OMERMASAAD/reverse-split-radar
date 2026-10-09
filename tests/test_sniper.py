# -*- coding: utf-8 -*-
"""
اختبارات «رادار قنص الذعر» — تعمل بلا إنترنت على بيانات اصطناعية.
تشغيل: python tests/test_sniper.py   أو   pytest tests/
"""
from __future__ import annotations

import json
import math
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd  # noqa: E402

from sniper import config as C  # noqa: E402
from sniper import float_lookup, indicators, persist, risk, runtime, scoring, tracker, universe  # noqa: E402
from sniper.cli import run_once  # noqa: E402
from sniper.core import evaluate, mtf_confirmation  # noqa: E402
from tests import synthetic  # noqa: E402


# ---------------------------------------------------------------- الشروط الأصلية
def test_pass_complete_signal():
    frame, now = synthetic.make()
    res, why = evaluate(frame, now)
    assert res is not None, why
    assert res["drop_pct"] <= C.DROP_MAX_PCT, res["drop_pct"]
    assert res["hold_min"] >= C.CONS_MIN_MIN, res["hold_min"]
    assert abs(res["target"] / res["price"] - (1 + C.TARGET_PCT / 100.0)) < 1e-3
    assert all(res["checks"].values()), res["checks"]
    assert res["complete"] is True
    assert res["strength_score"] == 100, res["strength_score"]          # نفس معادلة الأصل
    assert res["grade"] in ("A+", "A", "B", "C", "D")
    assert res["risk"]["stop"] < res["base_low"] <= res["price"]
    assert [t["price"] for t in res["risk"]["targets"]] == sorted(t["price"] for t in res["risk"]["targets"])


def test_short_base_is_visible_but_not_complete():
    frame, now = synthetic.make(post_low_bars=8)
    res, why = evaluate(frame, now)
    assert res is not None and why == "ok"
    assert res["checks"]["base"] is False
    assert res["complete"] is False
    assert res["state"] == C.STATE_NEW


def test_no_runup_is_rejected():
    """سهم لم يصعد أولًا بما يكفي لا يدخل الرادار أصلًا."""
    frame, now = synthetic.make(runup_to=0.25)
    res, why = evaluate(frame, now)
    assert res is None and why == "low_runup", why


def test_too_deep_is_rejected():
    """انهيار أعمق من النطاق المستهدف (30–50%) يخرج من الرادار."""
    frame, now = synthetic.make(crash_to=0.30)
    res, why = evaluate(frame, now)
    assert res is None and why == "too_deep", why


def test_drop_band_is_reported():
    frame, now = synthetic.make()
    res, _ = evaluate(frame, now)
    assert res["drop_in_band"] is True
    assert res["drop_band"] == [C.DROP_MIN_PCT, C.DROP_MAX_PCT]
    assert res["runup"]["ok"] is True and res["runup"]["runup_pct"] >= C.RUNUP_MIN_PCT


def test_targets_are_below_vwap_flag():
    frame, now = synthetic.make()
    res, _ = evaluate(frame, now)
    risk = res["risk"]
    assert [t["pct"] for t in risk["targets"]] == list(C.TARGETS_PCT)
    assert risk["vwap"] is not None
    assert risk["targets_below_vwap"] + risk["targets_above_vwap"] == len(risk["targets"])
    assert len(risk["entry_modes"]) == 2
    assert risk["entry_modes"][0]["key"] == "market"
    assert risk["entry_modes"][1]["key"] == "breakout"
    assert risk["entry_modes"][1]["entry"] == risk["breakout_trigger"]
    assert risk["stop"] < res["base_low"]


def test_no_drop():
    frame, now = synthetic.make(crash_to=0.90)
    res, why = evaluate(frame, now)
    assert res is None and why == "no_drop"


def test_stale_data():
    frame, now = synthetic.make()
    res, why = evaluate(frame, now + timedelta(hours=3))
    assert res is None and why == "stale"


def test_insufficient_bars():
    frame, now = synthetic.make()
    last_day = frame.index[-1].date()
    res, why = evaluate(frame[frame.index.date == last_day].head(10), now)
    assert res is None and why == "no_data"


def test_no_warmup_no_confirmation():
    """بلا تاريخ سابق لا يُجزَم بحجم الصعود — لا تأكيد بلا تسخين."""
    frame, now = synthetic.make_no_history()
    res, why = evaluate(frame, now)
    assert res is None and why == "weak_runup_volume", (res, why)


# ---------------------------------------------------------------- التطويرات
def test_extra_layers_present():
    frame, now = synthetic.make()
    res, _ = evaluate(frame, now)
    for key in ("risk", "levels", "volume", "mtf", "indicators_now", "chart",
                "confirmations", "confirmation_details", "missing_conditions"):
        assert key in res, key
    assert res["levels"]["day_high"] >= res["levels"]["day_low"] > 0
    assert res["volume"]["rvol"] is not None
    assert len(res["chart"]) <= C.CHART_BARS
    assert res["risk"]["shares"] > 0
    assert res["risk"]["rr_t2"] is not None
    assert res["levels"]["base"]["base_touches"] >= 1
    assert res["score"] == scoring.combine(res["strength_score"], res["confirm_score"])


def test_mtf_returns_dict_without_enough_bars():
    frame, _ = synthetic.make(post_low_bars=2)
    out = mtf_confirmation(frame.head(20))
    assert out["aligned"] is False and "note" in out


def test_round_numbers_and_gap():
    frame, now = synthetic.make()
    res, _ = evaluate(frame, now)
    lv = res["levels"]
    assert lv["round_number_below"] <= lv["price"] <= lv["round_number_above"]
    assert "gap_pct" in lv and "phase" in lv


# ---------------------------------------------------------------- محرك المخاطر
def test_risk_plan_math():
    plan = risk.risk_plan(price=1.00, base_low=0.90, base_high=1.06, atr_value=0.03)
    assert plan["stop"] < 0.90
    assert plan["risk_pct"] > 0
    assert [t["pct"] for t in plan["targets"]] == list(C.TARGETS_PCT)
    assert plan["targets"][0]["pct"] == C.TARGET_PCT
    assert plan["stop"] == round(0.90 * (1 - C.STOP_BUFFER_PCT / 100.0), 4)
    assert plan["rr_t1"] < plan["rr_t2"]
    assert plan["rr_t3"] is None, "الأهداف هدفان فقط (+20% و+30%)"
    assert plan["shares"] == int(math.floor(C.ACCOUNT_EQUITY * C.RISK_PER_TRADE_PCT / 100
                                            / plan["risk_per_share"]))
    assert plan["measured_projection"] > plan["entry"]


def test_risk_plan_never_stops_above_price():
    plan = risk.risk_plan(price=1.00, base_low=1.02, base_high=1.05, atr_value=None)
    assert plan["stop"] < plan["entry"]


# ---------------------------------------------------------------- الدمج والشطب
def _run(frames, prev, universe_obj, now):
    return runtime.merge(universe_obj, prev, frames, now)


def test_purge_on_base_break():
    frame, now = synthetic.make()
    uni = synthetic.universe_stub(("AAA",))
    first = _run({"AAA": frame}, {}, uni, now)
    assert len(first["items"]) == 1
    base_low = first["items"][0]["base_low"]

    broken = frame.copy()
    broken.iloc[-1, broken.columns.get_loc("Close")] = base_low * 0.94      # -6% أعمق من وقف 5%
    second = _run({"AAA": broken}, first, uni, now + timedelta(minutes=15))
    assert not second["items"]
    assert second["purged"][0]["ticker"] == "AAA"
    assert "5%" in second["purged"][0]["reason"], second["purged"][0]["reason"]
    assert second["diagnostics"]["funnel"]["purged_new"] == 1

    third = _run({"AAA": frame}, second, uni, now + timedelta(minutes=30))  # لا يعود
    assert not third["items"]


def test_weakened_keeps_item():
    """سهم كان ثابتًا ثم ارتد فوق -30%: يبقى في القائمة بعلامة «ضعفت»."""
    frame, now = synthetic.make()
    uni = synthetic.universe_stub(("AAA",))
    first = _run({"AAA": frame}, {}, uni, now)
    assert first["items"][0]["had_base"] is True
    recovered, later = synthetic.make_recovered()
    assert evaluate(recovered, later)[1] == "no_drop"
    second = _run({"AAA": recovered}, first, uni, later)
    assert len(second["items"]) == 1
    item = second["items"][0]
    assert item["still_valid"] is False and item["state"] == C.STATE_WEAKENED
    assert item["complete"] is False
    assert second["diagnostics"]["funnel"]["weakened"] == 1


def test_item_without_base_is_dropped():
    """ارتد فوق -30% قبل أن يكوّن قاعدة ⇒ لم يعد مرشحًا ويُحذف."""
    frame, now = synthetic.make(post_low_bars=4)
    uni = synthetic.universe_stub(("AAA",))
    first = _run({"AAA": frame}, {}, uni, now)
    assert len(first["items"]) == 1 and first["items"][0]["had_base"] is False
    recovered, later = synthetic.make_recovered()
    second = _run({"AAA": recovered}, first, uni, later)
    assert not second["items"]
    assert second["diagnostics"]["funnel"]["dropped_no_base"] == 1


def test_missing_frame_is_flagged_then_dead():
    """انقطاع البيانات لا يحذف السهم فورًا، بل يعلّمه ثم يحوّله إلى «متوقف»."""
    frame, now = synthetic.make()
    uni = synthetic.universe_stub(("AAA",))
    state = _run({"AAA": frame}, {}, uni, now)
    assert state["items"][0]["data_missing"] is False
    for step in range(1, C.DEAD_AFTER_MISSES + 1):
        state = _run({}, state, uni, now + timedelta(minutes=15 * step))
        assert len(state["items"]) == 1, step
        assert state["items"][0]["data_misses"] == step
    assert state["items"][0]["state"] == C.STATE_DEAD
    assert state["items"][0]["state_label"] == C.STATE_LABELS[C.STATE_DEAD]


def test_data_returns_resets_misses():
    frame, now = synthetic.make()
    uni = synthetic.universe_stub(("AAA",))
    state = _run({"AAA": frame}, {}, uni, now)
    state = _run({}, state, uni, now + timedelta(minutes=15))
    assert state["items"][0]["data_misses"] == 1
    state = _run({"AAA": frame}, state, uni, now + timedelta(minutes=30))
    assert state["items"][0]["data_misses"] == 0
    assert state["items"][0]["data_missing"] is False


def test_session_reset_clears_previous_day():
    frame, now = synthetic.make()
    uni = synthetic.universe_stub(("AAA",))
    yesterday = {"session_date": "2020-01-01", "items": [{"ticker": "ZZZ", "had_base": True,
                                                          "base_low": 1.0}], "purged": []}
    out = _run({"AAA": frame}, yesterday, uni, now)
    assert [i["ticker"] for i in out["items"]] == ["AAA"]
    assert out["purged"] == []


def test_funnel_counts():
    frame, now = synthetic.make()
    uni = synthetic.universe_stub(("AAA", "BBB"))
    out = _run({"AAA": frame}, {}, uni, now)
    funnel = out["diagnostics"]["funnel"]
    assert funnel["universe"] == 2 and funnel["frames"] == 1 and funnel["no_data"] == 1
    assert funnel["monitored"] == 1 and funnel["complete"] == 1
    assert funnel["base_ok"] == 1 and funnel["rsi_ok"] == 1


def test_summary_and_states():
    frame, now = synthetic.make()
    out = _run({"AAA": frame}, {}, synthetic.universe_stub(("AAA",)), now)
    summary = runtime.session_summary(out)
    assert summary["complete"] == 1 and summary["ready"] == 1
    assert summary["states"][C.STATE_READY] + summary["states"][C.STATE_TRIGGERED] >= 1
    assert summary["grades"]


# ---------------------------------------------------------------- سجل المسح
def test_heartbeat_and_scan_log():
    now = datetime.now(timezone.utc)
    prev = {"items": [], "purged": [], "scan_log": []}
    beat = persist.heartbeat(now, ok=True, coverage_pct=80, frames=10, master=12,
                             items=1, complete=0, duration_s=42.5)
    out = persist.stamp_scan_log({"items": prev["items"], "purged": []}, beat, prev)
    assert out["scan_log"][-1]["ok"] is True
    assert out["scan_log"][-1]["duration_s"] == 42.5
    skipped = persist.heartbeat(now + timedelta(minutes=15), ok=False, skipped="low_coverage", items=1)
    out2 = persist.stamp_scan_log(out, skipped, out)
    assert out2["scan_log"][-1]["skipped"] == "low_coverage"
    assert len(out2["scan_log"]) == 2
    up = persist.uptime(out2["scan_log"])
    assert up["runs"] == 2 and up["ok_runs"] == 1 and up["failed"] == 1
    assert up["ok_rate_pct"] == 50.0


def test_alerts_are_deduped():
    payload = {}
    alert = {"ticker": "AAA", "kind": "signal", "at": "2026-10-06T14:00:00+00:00"}
    persist.push_alert(payload, alert)
    persist.push_alert(payload, alert)
    assert len(payload["alerts"]) == 1


# ---------------------------------------------------------------- متتبّع النتائج
def _complete_item(frame, now, ticker="AAA"):
    res, _ = evaluate(frame, now)
    res.update(ticker=ticker, signal_date=now.astimezone(C.MARKET_TZ).date().isoformat())
    return res


def test_tracker_target_hit():
    frame, now = synthetic.make()
    item = _complete_item(frame, now)
    trade = tracker.open_trade(item, now)
    assert trade is not None and trade["status"] == "open"

    entry = trade["entry"]
    rally = [entry * (1 + 0.02 * i) for i in range(1, 20)]
    up_frame, later = synthetic.make(extra_tail=rally)
    updated = tracker.update_trade(trade, up_frame, later)
    assert updated["mfe_pct"] > 0
    assert updated["hit_labels"], updated["targets"]
    assert updated["status"] in ("open", "closed")


def test_tracker_stop_hit():
    frame, now = synthetic.make()
    item = _complete_item(frame, now)
    trade = tracker.open_trade(item, now)
    stop = trade["stop"]
    dump = [trade["entry"] * 0.99, stop * 0.98, stop * 0.97, stop * 0.96]
    down_frame, later = synthetic.make(extra_tail=dump)
    updated = tracker.update_trade(trade, down_frame, later)
    assert updated["status"] == "closed"
    assert updated["exit_reason"] == tracker.EXIT_STOP
    assert updated["r_multiple"] < 0
    assert updated["mae_pct"] < 0


def test_tracker_expires_previous_session():
    frame, now = synthetic.make()
    item = _complete_item(frame, now)
    trade = tracker.open_trade(item, now)
    trade["session_date"] = "2020-01-01"
    trade["last_price"] = trade["entry"] * 1.1
    tracker.expire_open([trade], "2026-10-06", now)
    assert trade["status"] == "closed" and trade["exit_reason"] == tracker.EXIT_SESSION


def test_summarize_stats():
    closed = [
        {"r_multiple": 2.0, "result_pct": 20.0, "mfe_pct": 25.0, "mae_pct": -3.0, "hold_min": 60,
         "grade": "A", "entry_ts": "2026-10-06T14:00:00-04:00", "drop_pct": -45,
         "hit_labels": ["T1", "T2"], "exit_reason": tracker.EXIT_TARGET},
        {"r_multiple": -1.0, "result_pct": -8.0, "mfe_pct": 4.0, "mae_pct": -9.0, "hold_min": 120,
         "grade": "C", "entry_ts": "2026-10-06T15:00:00-04:00", "drop_pct": -60,
         "hit_labels": [], "exit_reason": tracker.EXIT_STOP},
    ]
    stats = tracker.summarize(closed)
    assert stats["trades"] == 2 and stats["wins"] == 1 and stats["win_rate_pct"] == 50.0
    assert stats["profit_factor"] == 2.0
    assert stats["targets"]["T2"]["hits"] == 1
    assert stats["by_grade"]["A"]["win_rate_pct"] == 100.0
    assert stats["by_drop"]["-50% إلى -70%"]["trades"] == 1
    assert tracker.summarize([]) == {"trades": 0}


def test_update_stats_opens_once_per_signal():
    frame, now = synthetic.make()
    item = _complete_item(frame, now)
    stats = tracker.update_stats({}, [item], {"AAA": frame}, now, item["signal_date"])
    # إشارة واحدة ⇒ صفقة فورية مفتوحة + أمر اختراق معلّق، ولا تكرار
    assert len(stats["open"]) == 2, len(stats["open"])
    assert len([t for t in stats["open"] if t["status"] == "open"]) == 1
    assert len(stats["pending"]) == 1 and stats["pending"][0]["mode"] == "breakout"
    assert len(stats["alerts"]) == 2
    again = tracker.update_stats(stats, [item], {"AAA": frame}, now + timedelta(minutes=15),
                                 item["signal_date"])
    assert len(again["open"]) == 2, "لا يجوز فتح الصفقة نفسها مرتين"
    assert len({t["id"] for t in again["open"]}) == 2
    assert again["summary"]["trades"] == 0


# ---------------------------------------------------------------- المؤشرات
def test_indicator_sanity():
    frame, _ = synthetic.make()
    close = frame["Close"].astype(float)
    r = indicators.rsi(close, 14)
    valid = r.dropna()
    assert len(valid) and float(valid.min()) >= 0 and float(valid.max()) <= 100
    line, signal, hist = indicators.macd(close)
    assert abs(float((line - signal).iloc[-1]) - float(hist.iloc[-1])) < 1e-9
    a = indicators.atr(frame, 14).dropna()
    assert len(a) and float(a.min()) > 0
    v = indicators.vwap(frame).dropna()
    assert float(v.min()) >= float(frame["Low"].min()) * 0.999
    assert float(v.max()) <= float(frame["High"].max()) * 1.001
    o = indicators.obv(close, frame["Volume"].astype(float))
    assert len(o) == len(frame)
    higher = indicators.resample_bars(frame, C.MTF_RESAMPLE)
    assert len(higher) < len(frame) and len(higher) > 0


def test_rolling_slope_and_stdev():
    assert indicators.rolling_slope([1, 2, 3, 4], 4) > 0
    assert indicators.rolling_slope([4, 3, 2, 1], 4) < 0
    assert indicators.rolling_slope([1, 2], 4) is None


# ---------------------------------------------------------------- الكون والـ Float
def test_pool_record_filters():
    good = synthetic.daily_frame(price=2.0, volume=400_000)
    assert universe.pool_record(good) is not None
    expensive = synthetic.daily_frame(price=2.0, volume=400_000)
    expensive.loc[:, "Close"] = 50.0
    expensive.loc[:, "High"] = 52.0
    expensive.loc[:, "Low"] = 48.0
    assert universe.pool_record(expensive) is None
    illiquid = synthetic.daily_frame(price=2.0, volume=1_000)
    assert universe.pool_record(illiquid) is None


def test_classify_float():
    assert float_lookup.classify({"value": 2_000_000, "status": "exact"}) == (True, "exact")
    assert float_lookup.classify({"value": 4_000_000, "status": "bound"}) == (True, "bound")
    assert float_lookup.classify({"value": 40_000_000, "status": "bound"})[0] is False
    assert float_lookup.classify({"value": None, "status": "missing"}, unknown_policy="watch") == (True, "unverified")
    assert float_lookup.classify({"value": None, "status": "missing"}, unknown_policy="exclude")[0] is False


def test_build_universe_writes_file(tmpdir=None):
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "universe.json")
        cache = os.path.join(tmp, "float_cache.json")
        os.environ["FLOAT_CACHE_FILE"] = cache
        try:
            pool = {"AAA": {"price": 1.5, "avg_vol": 500_000, "range_pct": 40.0, "rally_pct": 120.0},
                    "BIG": {"price": 1.5, "avg_vol": 500_000, "range_pct": 30.0, "rally_pct": 80.0}}

            def resolver(ticker):
                if ticker == "BIG":
                    return {"value": 900_000_000, "status": "bound", "source": "yahoo_outstanding"}
                return {"value": 2_000_000, "status": "bound", "source": "yahoo_outstanding"}

            out = universe.build_universe(pool, resolver=resolver, path=path, force=True)
            assert [row["ticker"] for row in out["tickers"]] == ["AAA"]
            assert json.loads(Path(path).read_text(encoding="utf-8"))["count"] == 1
        finally:
            os.environ.pop("FLOAT_CACHE_FILE", None)


def test_reverse_split_tags_optional():
    tags = universe.reverse_split_tags()
    assert isinstance(tags, dict)
    for value in tags.values():
        assert value["reverse_split"] is True


# ---------------------------------------------------------------- التسلسل
def test_json_safe_removes_nan():
    import numpy as np
    payload = {"a": float("nan"), "b": np.float64(1.5), "c": np.int64(3),
               "d": [float("inf"), None], "e": {"f": np.bool_(True)}}
    cleaned = persist.json_safe(payload)
    text = json.dumps(cleaned, allow_nan=False)
    assert cleaned["a"] is None and cleaned["d"][0] is None
    assert cleaned["b"] == 1.5 and cleaned["e"]["f"] is True
    assert "NaN" not in text


# ---------------------------------------------------------------- دورة كاملة
def test_run_once_end_to_end():
    frame, now = synthetic.make()
    with tempfile.TemporaryDirectory() as tmp:
        uni_path = os.path.join(tmp, "universe.json")
        out_path = os.path.join(tmp, "panic_data.json")
        stats_path = os.path.join(tmp, "panic_stats.json")
        persist.save(uni_path, synthetic.universe_stub(("AAA", "BBB")))

        payload = run_once(downloader=lambda tickers, **kw: {"AAA": frame},
                           universe_path=uni_path, out_path=out_path,
                           stats_path=stats_path, now=now)

        assert Path(out_path).exists() and Path(stats_path).exists()
        on_disk = json.loads(Path(out_path).read_text(encoding="utf-8"))
        for key in ("summary", "clock", "rules", "conditions", "states", "scan_log",
                    "items", "purged", "diagnostics", "uptime", "session_date"):
            assert key in on_disk, key
        assert on_disk["summary"]["complete"] == 1
        assert on_disk["items"][0]["ticker"] == "AAA"
        assert on_disk["items"][0]["chart"], "الشموع مطلوبة للرسم"
        assert on_disk["diagnostics"]["coverage_pct"] == 50.0
        stats = json.loads(Path(stats_path).read_text(encoding="utf-8"))
        # صفقة فورية + أمر اختراق معلّق لإشارة واحدة
        assert len(stats["open"]) == 2, len(stats["open"])
        assert len(stats["pending"]) == 1
        assert sorted(t["mode"] for t in stats["open"]) == ["breakout", "market"]
        assert payload["summary"]["complete"] == 1


def test_run_once_low_coverage_only_logs():
    frame, now = synthetic.make()
    with tempfile.TemporaryDirectory() as tmp:
        uni_path = os.path.join(tmp, "universe.json")
        out_path = os.path.join(tmp, "panic_data.json")
        stats_path = os.path.join(tmp, "panic_stats.json")
        many = synthetic.universe_stub(tuple("T%03d" % i for i in range(20)))
        persist.save(uni_path, many)
        payload = run_once(downloader=lambda tickers, **kw: {"T000": frame},
                           universe_path=uni_path, out_path=out_path,
                           stats_path=stats_path, now=now)
        assert payload["last_scan"]["ok"] is False
        assert payload["last_scan"]["skipped"] == "low_coverage"
        assert payload["scan_log"]


def test_run_once_without_universe():
    with tempfile.TemporaryDirectory() as tmp:
        out_path = os.path.join(tmp, "panic_data.json")
        payload = run_once(downloader=lambda tickers, **kw: {},
                           universe_path=os.path.join(tmp, "missing.json"),
                           out_path=out_path, stats_path=os.path.join(tmp, "s.json"),
                           now=datetime.now(timezone.utc))
        assert payload["last_scan"]["skipped"] == "no_universe"


def test_demo_universe_is_never_scanned_live():
    """حماية: كون تجريبي لا يُمسح في التشغيل الحي، ولا يُنزَّل له أي بيانات."""
    frame, now = synthetic.make()
    calls = []

    def downloader(tickers, **kwargs):
        calls.append(list(tickers))
        return {"AAA": frame}

    with tempfile.TemporaryDirectory() as tmp:
        uni_path = os.path.join(tmp, "universe.json")
        stub = synthetic.universe_stub(("AAA",))
        stub["demo"] = True
        persist.save(uni_path, stub)
        kwargs = dict(downloader=downloader, universe_path=uni_path,
                      out_path=os.path.join(tmp, "panic_data.json"),
                      stats_path=os.path.join(tmp, "panic_stats.json"), now=now)

        payload = run_once(**kwargs)
        assert payload["last_scan"]["ok"] is False
        assert payload["last_scan"]["skipped"] == "demo_universe"
        assert calls == [], "لا يجوز تنزيل بيانات لرموز تجريبية"

        live = run_once(allow_demo_universe=True, **kwargs)
        assert live["summary"]["monitored"] == 1
        assert len(calls) == 1


def test_scan_log_accumulates_across_runs():
    """سجل المسح والتنبيهات تتراكم بين التشغيلات — أساس تبويب «سجل التشغيل»."""
    frame, now = synthetic.make()
    with tempfile.TemporaryDirectory() as tmp:
        kwargs = dict(downloader=lambda tickers, **kw: {"AAA": frame},
                      universe_path=os.path.join(tmp, "universe.json"),
                      out_path=os.path.join(tmp, "panic_data.json"),
                      stats_path=os.path.join(tmp, "panic_stats.json"))
        persist.save(kwargs["universe_path"], synthetic.universe_stub(("AAA",)))

        first = run_once(now=now, **kwargs)
        assert len(first["scan_log"]) == 1, len(first["scan_log"])
        second = run_once(now=now + timedelta(minutes=15), **kwargs)
        assert len(second["scan_log"]) == 2, len(second["scan_log"])
        third = run_once(now=now + timedelta(minutes=30), **kwargs)
        assert len(third["scan_log"]) == 3, len(third["scan_log"])
        assert third["uptime"]["runs"] == 3 and third["uptime"]["ok_runs"] == 3
        assert third["uptime"]["ok_rate_pct"] == 100.0
        assert third["alerts"], "التنبيهات ضاعت بين المسوحات"
        on_disk = json.loads(Path(kwargs["out_path"]).read_text(encoding="utf-8"))
        assert len(on_disk["scan_log"]) == 3


def test_breakout_marks_triggered():
    """اختراق قمة الثبات مع اكتمال الشروط ⇒ حالة «انطلق فوق القاعدة»."""
    frame, now = synthetic.make_breakout()
    res, why = evaluate(frame, now)
    assert res is not None and res["complete"], (res, why)
    assert res["levels"]["base"]["broke_base"] is True
    assert res["price"] > res["levels"]["base"]["base_high_prior"]
    out = _run({"AAA": frame}, {}, synthetic.universe_stub(("AAA",)), now)
    assert out["items"][0]["state"] == C.STATE_TRIGGERED
    assert out["items"][0]["state_label"] == C.STATE_LABELS[C.STATE_TRIGGERED]


def test_no_breakout_stays_ready():
    """قاعدة مكتملة بلا اختراق تبقى «إشارة مكتملة» لا «انطلق»."""
    frame, now = synthetic.make(base_trend=0.0)
    out = _run({"AAA": frame}, {}, synthetic.universe_stub(("AAA",)), now)
    assert out["items"][0]["state"] == C.STATE_READY


def test_vwap_acts_as_ceiling_when_price_below_it():
    """السعر تحت VWAP ← الخط سقف مقاوم والأهداف تُقيَّد قبله."""
    from sniper.risk import risk_plan
    plan = risk_plan(2.00, 1.90, 2.05, 0.05, vwap=2.30)
    assert plan["vwap_is_ceiling"] is True
    assert plan["vwap_role"].startswith("سقف مقاوم")
    assert plan["targets_capped"] == 2
    for t in plan["targets"]:
        assert t["capped"] is True
        assert t["capped_price"] < 2.30, "الهدف المُقيَّد يجب أن يبقى قبل الخط"
        assert t["capped_rr"] < t["rr"], "التقييد يقلّص العائد"
    assert "يخترق السقف" in plan["vwap_note"]


def test_vwap_is_support_when_price_above_it():
    """السعر فوق VWAP ← الخط دعم، والأهداف حرة فوقه (لا تقييد)."""
    from sniper.risk import risk_plan
    plan = risk_plan(3.06, 2.98, 3.07, 0.05, vwap=3.02)
    assert plan["vwap_is_ceiling"] is False
    assert plan["vwap_role"].startswith("دعم سفلي")
    assert plan["targets_capped"] == 0
    assert all(t["capped"] is False for t in plan["targets"])
    assert "فلم يعد الخط سقفًا" in plan["vwap_note"], plan["vwap_note"]


def _bar_frame(rows, start="2026-10-06 10:00", tz="America/New_York"):
    """شموع 5m من قوائم (high, low, close)."""
    idx = pd.date_range(start, periods=len(rows), freq="5min", tz=tz)
    return pd.DataFrame({"Open": [r[2] for r in rows], "High": [r[0] for r in rows],
                         "Low": [r[1] for r in rows], "Close": [r[2] for r in rows],
                         "Volume": [100_000] * len(rows)}, index=idx)


def test_stop_moves_to_break_even_after_t1():
    """بعد تحقق T1 ينتقل الوقف إلى الدخول، فالهبوط اللاحق يخرج عند الصفر لا عند −1R."""
    entry, stop = 2.00, 1.90
    t1, t2 = 2.40, 2.60
    trade = {"id": "BE", "ticker": "AAA", "session_date": "2026-10-06", "mode": "market",
             "entry": entry, "entry_ts": "2026-10-06T09:55:00-04:00", "stop": stop,
             "current_stop": stop, "status": "open",
             "targets": [{"label": "T1", "price": t1, "pct": 20.0, "hit": False, "at": None},
                         {"label": "T2", "price": t2, "pct": 30.0, "hit": False, "at": None}],
             "targets_hit": [], "stop_hit": False}
    # يصعد إلى T1 ثم يرتد إلى الدخول (فوق الوقف الأصلي 1.90 وتحت 2.00)
    df = _bar_frame([(2.10, 1.99, 2.05), (2.45, 2.30, 2.42), (2.44, 2.20, 2.30),
                     (2.30, 1.95, 1.98)])
    now = datetime(2026, 10, 6, 14, 30, tzinfo=timezone.utc)
    out = tracker.update_trade(trade, df, now)
    assert out["status"] == "closed", out
    assert out["stop_at_break_even"] is True
    assert out["exit_reason"] == tracker.EXIT_BREAK_EVEN, out["exit_reason"]
    assert out["exit_price"] == entry, out["exit_price"]
    assert out["r_multiple"] == 0.0, out["r_multiple"]
    assert out["result_pct"] == 0.0


def test_break_even_disabled_keeps_original_stop():
    """مع تعطيل النقل يبقى الوقف الأصلي فيخرج بـ −1R."""
    original = C.MOVE_STOP_TO_BREAK_EVEN
    C.MOVE_STOP_TO_BREAK_EVEN = False
    try:
        entry, stop = 2.00, 1.90
        trade = {"id": "NOBE", "ticker": "AAA", "session_date": "2026-10-06", "mode": "market",
                 "entry": entry, "entry_ts": "2026-10-06T09:55:00-04:00", "stop": stop,
                 "current_stop": stop, "status": "open",
                 "targets": [{"label": "T1", "price": 2.40, "pct": 20.0, "hit": False, "at": None},
                             {"label": "T2", "price": 2.60, "pct": 30.0, "hit": False, "at": None}],
                 "targets_hit": [], "stop_hit": False}
        df = _bar_frame([(2.10, 1.99, 2.05), (2.45, 2.30, 2.42), (2.30, 1.88, 1.89)])
        out = tracker.update_trade(trade, df, datetime(2026, 10, 6, 14, 30, tzinfo=timezone.utc))
        assert out["exit_reason"] == tracker.EXIT_STOP, out["exit_reason"]
        assert out["r_multiple"] == -1.0, out["r_multiple"]
    finally:
        C.MOVE_STOP_TO_BREAK_EVEN = original


def test_breakout_order_waits_then_fills():
    """أمر الاختراق يبقى معلّقًا حتى يخترق السعر قمة القاعدة، ثم يُنفَّذ عند القمة."""
    frame, now = synthetic.make(base_trend=0.0)
    item = _complete_item(frame, now)
    pending = tracker.open_trade(item, now, mode="breakout")
    assert pending["status"] == "pending" and pending["entry"] is None
    trigger = pending["trigger"]
    assert abs(trigger - item["risk"]["breakout_trigger"]) < 1e-9

    # شمعة لم تصل القمة ← يبقى معلّقًا
    flat = _bar_frame([(trigger * 0.99, trigger * 0.97, trigger * 0.98)] * 3)
    still = tracker.update_trade(dict(pending), flat, now + timedelta(minutes=15))
    assert still["status"] == "pending"

    # شمعة تخترق ← يُنفَّذ عند سعر القمة لا عند الإغلاق
    cross = _bar_frame([(trigger * 0.99, trigger * 0.97, trigger * 0.98),
                        (trigger * 1.05, trigger * 0.99, trigger * 1.03)])
    filled = tracker.update_trade(dict(pending), cross, now + timedelta(minutes=20))
    assert filled["status"] in ("open", "closed")
    assert filled["entry"] == trigger, filled["entry"]
    assert filled["mode"] == "breakout"


def test_pending_order_expires_without_counting_as_trade():
    """أمر لم يُنفَّذ في جلسته يسقط ولا يدخل في نسبة النجاح."""
    now = datetime(2026, 10, 6, 14, 30, tzinfo=timezone.utc)
    trade = {"id": "AAA#2026-10-06:bk", "signal_id": "AAA#2026-10-06", "ticker": "AAA",
             "session_date": "2026-10-06", "mode": "breakout", "status": "pending",
             "entry": None, "stop": 1.9, "trigger": 2.10, "targets": []}
    out = tracker.expire_open([trade], "2026-10-07", now)
    assert out[0]["status"] == "expired"
    stats = tracker.update_stats({"open": out, "closed": []}, [], {}, now, "2026-10-07")
    assert stats["expired_pending"] == 1
    assert stats["summary"]["trades"] == 0, "الأمر غير المُنفَّذ لا يُحسب صفقة"


def test_validate_premise_on_real_cases():
    """فرضية الرجل الأولى على الحالات التاريخية الحقيقية (بيانات يومية)."""
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
    import validate_premise
    if not validate_premise.DATA.exists():
        return                                    # research/ غير متاحة في هذه البيئة
    cases = validate_premise.load_cases()
    assert cases, "يجب أن توجد حالات حقيقية"
    out = validate_premise.summarize(cases, 100.0)
    assert out["cases"] == len(cases)
    assert out["qualifying"] > 0, "لا حالة حقيقية صعدت 100%؟"
    assert out["min_runup_pct"] == 100.0
    # عتبة أعلى ⇒ عدد أقل (اتساق داخلي)
    assert validate_premise.summarize(cases, 500.0)["qualifying"] <= out["qualifying"]
    assert 0 <= out["qualifying_pct"] <= 100
    assert out["by_classification"], out


TESTS = [value for key, value in sorted(globals().items()) if key.startswith("test_") and callable(value)]

if __name__ == "__main__":
    failures = 0
    for fn in TESTS:
        try:
            fn()
            print("✅", fn.__name__)
        except Exception as exc:                              # noqa: BLE001
            failures += 1
            print("❌", fn.__name__, repr(exc)[:400])
    print("\n%d/%d passed" % (len(TESTS) - failures, len(TESTS)))
    raise SystemExit(1 if failures else 0)


