# -*- coding: utf-8 -*-
"""
نقطة تشغيل «رادار قنص الذعر» — تُنفَّذ كل 15 دقيقة من GitHub Actions.

الخطوات: تحميل الكون ← تحميل شموع 5m دفعيًا ← تقييم الشروط ← دمج الحالة
والشطب الآلي ← تحديث متابعة النتائج الورقية ← كتابة panic_data.json وpanic_stats.json.
"""
from __future__ import annotations

import argparse
import os
import time
from datetime import datetime, timezone

from . import config as C
from .market import download, market_clock
from .persist import heartbeat, load, now_utc, save, stamp_scan_log, uptime
from .runtime import merge, session_summary
from .tracker import update_stats
from .universe import load_universe


def thresholds_payload() -> dict:
    return C.thresholds()


def _universe_age_days(universe: dict, now) -> int:
    """عمر الكون بالأيام (يعيد رقمًا كبيرًا إذا لم يُبنَ بعد)."""
    try:
        built = datetime.fromisoformat(str(universe.get("built_on")))
    except (TypeError, ValueError):
        return 10_000
    return (now.astimezone(C.MARKET_TZ).date() - built.date()).days


def run_once(tickers=None, limit: int | None = None, force_universe: bool = False,
             downloader=None, universe_path: str = C.UNIVERSE_FILE,
             out_path: str = C.OUT_FILE, stats_path: str = C.STATS_FILE,
             now: datetime | None = None, allow_demo_universe: bool = False,
             rebuild_universe: bool = True) -> dict:
    """دورة مسح واحدة — قابلة للاستدعاء من الاختبارات مع حقن البيانات."""
    started = time.time()
    now = now or now_utc()
    downloader = downloader or download
    universe = load_universe(universe_path)
    prev = load(out_path, {})          # الحالة السابقة تُقرأ أولًا: كل مسارات التخطي تحتاجها

    demo_universe = bool(universe.get("demo")) and not allow_demo_universe
    stale = demo_universe or _universe_age_days(universe, now) > C.UNIVERSE_MAX_AGE_DAYS
    if rebuild_universe and (force_universe or not universe.get("tickers") or stale):
        if stale and universe.get("tickers"):
            print("::warning title=Universe stale::الكون عمره %d يومًا — محاولة إعادة البناء"
                  % _universe_age_days(universe, now))
        try:
            from .universe import cli as build_cli
            rebuilt = build_cli(force=force_universe, limit=limit, path=universe_path)
            if rebuilt.get("tickers") and not rebuilt.get("demo"):
                universe = rebuilt
        except Exception as exc:                        # noqa: BLE001
            print("::warning title=Universe build failed::%s" % str(exc)[:160])

    if universe.get("demo") and not allow_demo_universe:
        # حماية: لا نمسح أبدًا رموزًا تجريبية في التشغيل الحي
        print("::warning title=Demo universe::universe.json تجريبي — شغّل build_universe.py")
        beat = heartbeat(now, ok=False, skipped="demo_universe",
                         items=len(prev.get("items") or []))
        return save_all(prev, beat, None, out_path, stats_path, prev=prev)

    meta = [row for row in universe.get("tickers", [])
            if not tickers or row.get("ticker") in set(tickers)]
    if limit:
        meta = meta[:limit]
    total = len(meta)
    if not total:
        print("::warning title=No universe::universe.json فارغ — شغّل build_universe.py أولًا")
        beat = heartbeat(now, ok=False, skipped="no_universe",
                         items=len(prev.get("items") or []))
        return save_all(prev, beat, None, out_path, stats_path, prev=prev)

    frames = downloader([row["ticker"] for row in meta])
    coverage = len(frames) / max(1, total)
    print("5m coverage: %.0f%% (%d/%d)" % (coverage * 100.0, len(frames), total))
    if coverage < C.COVERAGE_MIN:
        print("::warning title=Scan skipped::تغطية بيانات 5m ضعيفة — يُحدَّث سجل المسح فقط")
        beat = heartbeat(now, ok=False, coverage_pct=round(coverage * 100.0, 1),
                         frames=len(frames), master=total,
                         items=len(prev.get("items") or []),
                         complete=sum(1 for x in prev.get("items") or [] if x.get("complete")),
                         skipped="low_coverage", duration_s=time.time() - started)
        return save_all(prev, beat, None, out_path, stats_path, prev=prev)

    payload = merge(universe, prev, frames, now)
    carried = list(prev.get("alerts") or [])
    payload["alerts"] = (carried + list(payload.get("alerts") or []))[-C.ALERTS_KEEP:]
    today = payload["session_date"]
    stats = update_stats(load(stats_path, {}), payload["items"], frames, now, today)
    for alert in stats.get("alerts") or []:
        from .persist import push_alert
        push_alert(payload, alert)

    beat = heartbeat(now, ok=True, coverage_pct=round(coverage * 100.0, 1),
                     frames=len(frames), master=total, items=len(payload["items"]),
                     complete=sum(1 for x in payload["items"] if x.get("complete")),
                     duration_s=time.time() - started)
    return save_all(payload, beat, stats, out_path, stats_path, prev=prev)


def save_all(payload: dict, beat: dict, stats: dict | None,
             out_path: str = C.OUT_FILE, stats_path: str = C.STATS_FILE,
             prev: dict | None = None) -> dict:
    """يختم سجل المسح ويضيف الملخص والساعة والقواعد ثم يكتب الملفين."""
    payload = stamp_scan_log(payload or {"items": [], "purged": []}, beat, prev)
    payload["summary"] = session_summary(payload)
    payload["clock"] = market_clock(datetime.fromisoformat(beat["at"]))
    payload["uptime"] = uptime(payload.get("scan_log") or [])
    payload["rules"] = thresholds_payload()
    payload["conditions"] = [
        {"key": c.key, "label": c.label, "weight": c.weight, "hint": c.hint, "core": c.core}
        for c in C.all_conditions()
    ]
    payload["states"] = C.STATE_LABELS
    size = save(out_path, payload)
    if stats is not None:
        stats["uptime"] = payload["uptime"]
        save(stats_path, stats)
    print("items: %d (complete %d) | purged: %d | %.0fkb"
          % (len(payload.get("items") or []), payload["summary"]["complete"],
             len(payload.get("purged") or []), size // 1024))
    return payload


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="رادار قنص الذعر — مسح كل 15 دقيقة")
    parser.add_argument("--tickers", help="رموز محددة (مفصولة بفاصلة) للتجربة")
    parser.add_argument("--limit", type=int, help="أقصى عدد رموز")
    parser.add_argument("--rebuild-universe", action="store_true", help="أعد بناء الكون الآن")
    parser.add_argument("--dry-run", action="store_true", help="لا تكتب الملفات")
    args = parser.parse_args(argv)

    if args.dry_run:
        out_path, stats_path = "/tmp/panic_data_dryrun.json", "/tmp/panic_stats_dryrun.json"
    else:
        out_path, stats_path = C.OUT_FILE, C.STATS_FILE

    selected = None
    if args.tickers:
        selected = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]
    run_once(tickers=selected, limit=args.limit, force_universe=args.rebuild_universe,
             out_path=out_path, stats_path=stats_path)
    return 0


__all__ = ["run_once", "save_all", "main", "thresholds_payload"]
