# -*- coding: utf-8 -*-
"""
توليد بيانات عرض (Demo) للداشبورد عبر **نفس مسار الكود الحقيقي**.

لا بيانات مختلَقة يدويًا: نبني شموع 5m اصطناعية ثم نمرّرها على
`sniper.cli.run_once` نفسها التي يستخدمها المسح الحي، فيُنتج panic_data.json
وpanic_stats.json بالمخطط نفسه تمامًا — مع علم `demo: true` حتى تميّزه الواجهة.

الاستخدام:  python tools/make_demo.py
"""
from __future__ import annotations

import sys
from datetime import timedelta, timezone

import pandas as pd
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sniper import config as C                       # noqa: E402
from sniper import persist                           # noqa: E402
from sniper.cli import run_once                      # noqa: E402
from tests import synthetic                          # noqa: E402

OUT_DIR = Path(__file__).resolve().parents[1]
END_TS = pd.Timestamp("2026-10-06 09:30", tz="America/New_York")   # آخر شمعة موحّدة لكل الرموز
PASSES = 4

# (الرمز، الشركة،Float، معامل الشموع، نمط الذيل بعد التمريرة الأولى)
# tail: (عدد الشموع، نسبة الخطوة) — خطوة سالبة = كسر، موجبة = انطلاق
CAST = [
    ("MULN", "Mullen Automotive", 4_120_000,
     dict(post_low_bars=40, crash_to=0.52, flat_noise=0.0022, seed=11, pad_bars=5), (14, 0.021)),
    ("NCI", "Nuvectis Pharma", 2_830_000,
     dict(post_low_bars=38, crash_to=0.47, flat_noise=0.0028, seed=12, pad_bars=7), (12, 0.006)),
    ("HCAI", "Huachen Ai Parking", 1_940_000,
     dict(post_low_bars=45, crash_to=0.35, flat_noise=0.0018, seed=13, pad_bars=0), None),
    ("LIXT", "Lixte Biotech", 3_450_000,
     dict(post_low_bars=40, crash_to=0.58, flat_noise=0.0011, seed=14, pad_bars=5), (12, 0.0025)),
    ("BSFC", "Blue Star Foods", 4_650_000,
     dict(post_low_bars=34, crash_to=0.44, flat_noise=0.0026, seed=19, pad_bars=11), (12, 0.0025)),
    ("AKAN", "Akanda Corp", 4_880_000,
     dict(post_low_bars=12, crash_to=0.60, flat_noise=0.0015, seed=15, pad_bars=33), None),
    ("CTNT", "Cheetah Net Supply", 1_333_000,
     dict(post_low_bars=10, crash_to=0.66, flat_noise=0.0018, seed=16, pad_bars=35), None),
    ("RETO", "ReTo Eco-Solutions", 2_369_000,
     dict(post_low_bars=5, crash_to=0.70, flat_noise=0.0020, seed=18, pad_bars=28,
          extra_tail=[None]), None),
    ("PIXY", "ShiftPixy", 1_120_000,
     dict(post_low_bars=30, crash_to=0.63, flat_noise=0.0031, seed=20, pad_bars=15), (4, -0.012)),
    ("SOPA", "Society Pass", 3_900_000,
     dict(post_low_bars=6, crash_to=0.90, flat_noise=0.0030, seed=17, pad_bars=39), None),
    # ── حالات إضافية لإظهار كل حالات النظام في الواجهة
    ("SNGX", "Soligenix", 2_700_000,
     dict(post_low_bars=28, crash_to=0.49, flat_noise=0.0040, seed=22), "breakout"),
    ("ONCT", "Oncternal Therapeutics", 1_500_000,
     dict(post_low_bars=44, crash_to=0.42, flat_noise=0.0016, seed=24, pad_bars=1), None),
    ("BRTX", "BioRestorative", 2_050_000,
     dict(post_low_bars=26, crash_to=0.57, flat_noise=0.0033, seed=25, pad_bars=9), (10, 0.004)),
    ("KALA", "Kala Bio", 3_200_000,
     dict(post_low_bars=36, crash_to=0.55, flat_noise=0.0024, seed=23, pad_bars=6), "vanish"),
]

REVERSE_SPLIT = {"AKAN": "30:1 Reverse split", "HCAI": "59.99:1 Reverse split",
                 "RETO": "4.5:1 Reverse split", "SNGX": "10:1 Reverse split",
                 "KALA": "15:1 Reverse split"}
DECLINE_BARS = 12      # شموع هابطة حادة تُبقي RETO في حالة «جديد» (قاعدة غير مكتملة)
DECLINE_STEP = -0.005


def universe() -> dict:
    from datetime import datetime
    rows = []
    for ticker, company, float_value, _, _ in CAST:
        row = {"ticker": ticker, "company": company, "price": 1.8, "avg_vol": 850_000,
               "range_pct": 42.0, "rally_pct": 130.0, "float": float_value,
               "float_status": "bound", "float_source": "yahoo_outstanding",
               "reverse_split": ticker in REVERSE_SPLIT}
        if ticker in REVERSE_SPLIT:
            row.update(split_date="2026-04-13", split_ratio=REVERSE_SPLIT[ticker],
                       days_since_split=179)
        rows.append(row)
    now = datetime.now(timezone.utc)
    return {"demo": True,
            "built_on": now.astimezone(C.MARKET_TZ).date().isoformat(),
            "built_at": now.isoformat(), "count": len(rows), "confirmed": len(rows),
            "unverified": 0, "reverse_split_tagged": len(REVERSE_SPLIT),
            "rules": {"price": [C.UNIVERSE_MIN_PRICE, C.UNIVERSE_MAX_PRICE],
                      "max_float": C.UNIVERSE_MAX_FLOAT,
                      "min_avg_volume": C.UNIVERSE_MIN_AVG_VOLUME},
            "tickers": rows}


def build_frames(pass_index: int) -> dict:
    frames = {}
    for ticker, _, _, params, tail in CAST:
        if tail == "vanish" and pass_index >= 1:
            continue                                   # انقطاع بيانات ⇒ حالة «متوقف»
        params = dict(params)
        # كل تمريرة تُنهي الشموع 15 دقيقة بعد السابقة، فتتكوّن حركة «بعد الدخول»
        # تسمح لمتتبّع النتائج بحساب MFE/MAE وتحقيق الأهداف.
        params["end_ts"] = END_TS + pd.Timedelta(minutes=15 * pass_index)
        if tail == "breakout":
            frames[ticker] = synthetic.make_breakout(**params)[0]
            continue
        if ticker == "RETO":                          # هبوط حاد في آخر الشموع
            params.pop("extra_tail", None)
            last = None
            probe, _ = synthetic.make(**params)
            last = float(probe["Close"].iloc[-1])
            params["extra_tail"] = [last * (1 + DECLINE_STEP) ** i
                                    for i in range(1, DECLINE_BARS + 1)]
            params["pad_bars"] = max(0, params["pad_bars"] - DECLINE_BARS)
        extra_tail = params.pop("extra_tail", None)
        if tail and pass_index >= 1:
            steps, step_pct = tail
            probe, _ = synthetic.make(extra_tail=extra_tail, **params)
            start = float(probe["Close"].iloc[-1])
            extra_tail = (extra_tail or []) + [start * (1 + step_pct) ** i
                                               for i in range(1, steps * pass_index + 1)]
        frames[ticker] = synthetic.make(extra_tail=extra_tail, **params)[0]
    return frames


def main() -> int:
    universe_path = OUT_DIR / "universe.json"
    out_path = OUT_DIR / "panic_data.json"
    stats_path = OUT_DIR / "panic_stats.json"
    persist.save(universe_path, universe())
    for stale in (out_path, stats_path):          # ابدأ من جلسة نظيفة
        stale.unlink(missing_ok=True)

    # «الآن» = آخر شمعة في البيانات الاصطناعية، وإلا عُدّت كل الشموع متقادمة (stale).
    start = max(frame.index[-1] for frame in build_frames(0).values()).to_pydatetime()
    start = start.astimezone(timezone.utc) if start.tzinfo else start.replace(tzinfo=timezone.utc)
    assert start == END_TS.to_pydatetime().astimezone(timezone.utc), start

    payload = None
    for index in range(PASSES):
        frames = build_frames(index)
        payload = run_once(downloader=lambda tickers, f=frames: {t: f[t] for t in tickers if t in f},
                           universe_path=str(universe_path), out_path=str(out_path),
                           stats_path=str(stats_path), now=start + timedelta(minutes=15 * index),
                           allow_demo_universe=True)

    payload = persist.load(str(out_path), payload)
    payload["demo"] = True
    payload["demo_note"] = ("بيانات تجريبية مولّدة من شموع اصطناعية عبر محرك المسح نفسه — "
                            "تُستبدل تلقائيًا بأول مسح حي على سوق نيويورك.")
    persist.save(out_path, payload)
    stats = persist.load(str(stats_path), {})
    stats["demo"] = True
    persist.save(stats_path, stats)

    summary = payload["summary"]
    print("\nDemo ready →", out_path)
    for item in payload["items"]:
        print("  %-6s %-12s score=%-3d grade=%-2s drop=%6.1f%% hold=%3dm checks=%d/4"
              % (item["ticker"], item["state"], item["score"], item["grade"],
                 item["drop_pct"], item["hold_min"], sum(item["checks"].values())))
    print("purged:", [p["ticker"] for p in payload["purged"]])
    print("monitored %d · complete %d · open trades %d · closed %d"
          % (summary["monitored"], summary["complete"],
             stats.get("open_summary", {}).get("count", 0),
             stats.get("summary", {}).get("trades", 0)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
