#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
⚡ رادار قنص الذعر — نقطة الدخول (يُستدعى كل 15 دقيقة).

الاستخدام:
    python panic_sniper.py                       # مسح كامل للكون
    python panic_sniper.py --tickers MULN,NCI    # رموز محددة للتجربة
    python panic_sniper.py --limit 50            # عيّنة صغيرة (أسرع)
    python panic_sniper.py --rebuild-universe    # أعد بناء الكون ثم امسح
    python panic_sniper.py --dry-run             # بلا كتابة ملفات
"""
import sys

from sniper.cli import main

if __name__ == "__main__":
    sys.exit(main())
