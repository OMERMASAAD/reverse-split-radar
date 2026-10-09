#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
بناء كون الأسهم منخفضة الفلوت (universe.json) — يُشغَّل مرة يوميًا.

القواعد: السعر $0.50–$10 · Float < 5M · متوسط حجم 20 يومًا ≥ 100k.

الاستخدام:
    python build_universe.py                 # بناء كامل من NASDAQ/NYSE/AMEX
    python build_universe.py --force         # تجاهل نسخة اليوم وأعد البناء
    python build_universe.py --limit 300     # عيّنة للتجربة
    python build_universe.py --tickers A,B   # رموز محددة
"""
import argparse
import sys

from sniper.universe import cli


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="بناء كون الرادار")
    parser.add_argument("--force", action="store_true", help="أعد البناء حتى لو بُني اليوم")
    parser.add_argument("--limit", type=int, help="أقصى عدد رموز تُفحص")
    parser.add_argument("--tickers", help="رموز محددة مفصولة بفاصلة")
    args = parser.parse_args(argv)
    result = cli(force=args.force, limit=args.limit, tickers=args.tickers)
    print("universe count:", len(result.get("tickers") or []))
    return 0


if __name__ == "__main__":
    sys.exit(main())
