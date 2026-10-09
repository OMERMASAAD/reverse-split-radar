#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
تحقّق من **فرضية** الاستراتيجية على حالات تاريخية حقيقية.

⚠️ حدود صريحة: `research/raw_historical_cases.json` بيانات **يومية** (لا شموع 5m)،
لذلك هذه الأداة تتحقق من premise الاستراتيجية — «هل تصعد هذه الأسهم فعلًا 100%+ قبل
أن تنهار؟» — ولا تُعيد اختبار محرك الـ5m نفسه. اختبار المحرك في `tests/`.

الاستخدام:  python tools/validate_premise.py [--min-runup 100]
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "research" / "raw_historical_cases.json"


def load_cases(path: Path = DATA) -> list[dict]:
    if not path.exists():
        raise SystemExit("لا يوجد ملف حالات: %s" % path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    return list(payload.get("success_cases") or [])


def summarize(cases: list[dict], min_runup: float) -> dict:
    """يقيس كم حالة حقيقية تنطبق عليها رجل الصعود الأولى."""
    gains = [float(c.get("maximum_gain_percent") or 0.0) for c in cases]
    jumps = [float(c.get("max_single_day_jump_percent") or 0.0) for c in cases]
    qualifying = [c for c in cases
                  if float(c.get("maximum_gain_percent") or 0.0) >= min_runup]
    by_class: dict[str, int] = {}
    for case in qualifying:
        key = str(case.get("classification") or "غير مصنّف")
        by_class[key] = by_class.get(key, 0) + 1
    return {
        "cases": len(cases),
        "min_runup_pct": min_runup,
        "qualifying": len(qualifying),
        "qualifying_pct": round(len(qualifying) / len(cases) * 100.0, 1) if cases else None,
        "median_gain_pct": round(statistics.median(gains), 1) if gains else None,
        "mean_gain_pct": round(statistics.fmean(gains), 1) if gains else None,
        "max_gain_pct": round(max(gains), 1) if gains else None,
        "median_single_day_jump_pct": round(statistics.median(jumps), 1) if jumps else None,
        "by_classification": dict(sorted(by_class.items(), key=lambda kv: -kv[1])),
        "tickers": sorted({str(c.get("ticker")) for c in qualifying}),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="تحقّق من فرضية الرجل الأولى على حالات حقيقية")
    parser.add_argument("--min-runup", type=float, default=100.0,
                        help="أدنى صعود يُعدّ رجلًا أولى (افتراضيًا 100%%)")
    args = parser.parse_args()

    cases = load_cases()
    out = summarize(cases, args.min_runup)
    print("الحالات الحقيقية المتاحة : %d" % out["cases"])
    print("عتبة الرجل الأولى        : ≥ %g%%" % out["min_runup_pct"])
    print("تنطبق عليها              : %d (%s%%)" % (out["qualifying"], out["qualifying_pct"]))
    print("وسيط الصعود الأقصى       : %s%%" % out["median_gain_pct"])
    print("متوسط الصعود الأقصى      : %s%%" % out["mean_gain_pct"])
    print("أعلى صعود مسجّل          : %s%%" % out["max_gain_pct"])
    print("وسيط قفزة اليوم الواحد   : %s%%" % out["median_single_day_jump_pct"])
    print("\nتصنيف الحالات المنطبقة:")
    for key, value in out["by_classification"].items():
        print("  %-22s %d" % (key, value))
    print("\nالرموز: %s" % ", ".join(out["tickers"][:40]))
    print("\nملاحظة: بيانات يومية — تتحقق من الفرضية لا من محرك الـ5m.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
