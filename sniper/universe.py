# -*- coding: utf-8 -*-
"""
بناء «الكون» (Universe): قائمة الرموز منخفضة الفلوت التي يمسحها الرادار كل
15 دقيقة. تُبنى مرة واحدة في اليوم وتُخزَّن في universe.json.

القواعد: السعر $0.50–$10 · Float < 5M · متوسط حجم 20 يومًا ≥ 100k ·
ترتيب حسب أعلى تذبذب (الأسهم الأكثر قابلية للانفجار أولًا).
"""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

import pandas as pd

from . import config as C
from . import float_lookup
from .persist import load, save

NASDAQ_LIST = "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt"
OTHER_LIST = "https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt"


def symbol_directory() -> list[str]:
    """رموز الأسهم المتداولة (بلا صناديق ولا إصدارات تجريبية)."""
    out: set[str] = set()
    for url, column in ((NASDAQ_LIST, "Symbol"), (OTHER_LIST, "ACT Symbol")):
        try:
            table = pd.read_csv(url, sep="|")
        except Exception as exc:                       # noqa: BLE001
            print("universe directory error:", str(exc)[:120])
            continue
        if "Test Issue" in table.columns:
            table = table[table["Test Issue"] == "N"]
        if "ETF" in table.columns:
            table = table[table["ETF"] != "Y"]
        out.update(str(x).strip().upper() for x in table[column].dropna())
    return sorted(x for x in out if x.isalpha() and 1 <= len(x) <= 5)


def pool_record(frame: pd.DataFrame) -> dict | None:
    """سجل خفيف لكل سهم داخل نطاق الكون، من الشموع اليومية المحمّلة أصلًا."""
    if frame is None or frame.empty:
        return None
    price = float(frame["Close"].iloc[-1])
    if not (C.UNIVERSE_MIN_PRICE <= price <= C.UNIVERSE_MAX_PRICE):
        return None
    avg_volume = float(frame["Volume"].tail(20).astype(float).mean())
    if avg_volume < C.UNIVERSE_MIN_AVG_VOLUME:
        return None
    closes = frame["Close"].astype(float)
    highs, lows = frame["High"].astype(float), frame["Low"].astype(float)
    window = min(20, len(frame))
    rng = float(((highs.tail(window) - lows.tail(window)) / closes.tail(window)).mean() * 100.0)
    rally = None
    if window >= 5:
        low20 = float(lows.tail(window).min())
        if low20 > 0:
            rally = round((float(highs.tail(window).max()) / low20 - 1.0) * 100.0, 1)
    return {"price": round(price, 3), "avg_vol": int(avg_volume),
            "range_pct": round(rng, 1), "rally_pct": rally,
            "last_close_date": frame.index[-1].date().isoformat() if hasattr(frame.index[-1], "date") else None}


def build_pool(tickers, downloader=None, chunk: int = C.CHUNK) -> dict:
    """تحميل يومي دفعي واستخراج سجلات الكون."""
    from .market import download_daily
    downloader = downloader or download_daily
    frames = downloader(list(tickers), chunk=chunk)
    pool = {}
    for ticker, frame in frames.items():
        record = pool_record(frame)
        if record:
            pool[ticker] = record
    return pool


def reverse_split_tags() -> dict:
    """وسم اختياري: هل الرمز نفّذ تجزئة عكسية حديثًا؟ (يستخدم ملف المستودع إن وُجد)."""
    rows = load(C.REVERSE_SPLIT_TAG_FILE, []) or []
    tags = {}
    if isinstance(rows, dict):
        rows = rows.get("candidates") or []
    for row in rows:
        if not isinstance(row, dict) or not row.get("ticker"):
            continue
        tags[str(row["ticker"]).upper()] = {
            "reverse_split": True,
            "split_date": row.get("split_date"),
            "split_ratio": row.get("reverse_split"),
            "days_since_split": row.get("days"),
            "company": row.get("company"),
        }
    return tags


def build_universe(pool: dict, now: datetime | None = None, force: bool = False,
                   resolver=None, workers: int = 8, path: str = C.UNIVERSE_FILE,
                   unknown_policy: str = "watch") -> dict:
    """يبني الكون من السجلات + حلّ الـ Float، ويكتب universe.json."""
    now = now or datetime.now(timezone.utc)
    resolver = resolver or float_lookup.resolve
    today = now.astimezone(C.MARKET_TZ).date().isoformat()
    old = load(path, {})
    if not force and old.get("built_on") == today and old.get("tickers"):
        print("universe already built today:", len(old["tickers"]))
        return old

    ranked = sorted(pool, key=lambda t: -(pool[t].get("range_pct") or 0))[:C.UNIVERSE_POOL_MAX]
    float_lookup.load_cache()
    deadline = time.time() + C.UNIVERSE_TIME_BUDGET_S
    infos: dict = {}

    def one(ticker):
        return None if time.time() > deadline else resolver(ticker)

    with ThreadPoolExecutor(max_workers=workers) as pool_exec:
        futures = {pool_exec.submit(one, ticker): ticker for ticker in ranked}
        for future in as_completed(futures):
            ticker = futures[future]
            try:
                infos[ticker] = future.result()
            except Exception as exc:                   # noqa: BLE001
                print("float error", ticker, type(exc).__name__)
    float_lookup.save_cache()

    tags = reverse_split_tags()
    confirmed, unverified = [], []
    for ticker in ranked:
        info = infos.get(ticker)
        if info is None:
            continue                                   # انتهت الميزانية — يكمل غدًا من الكاش
        ok, status = float_lookup.classify(info, C.UNIVERSE_MAX_FLOAT, unknown_policy)
        if not ok:
            continue
        row = dict(pool[ticker])
        row.update(ticker=ticker, float=info.get("value") if info else None,
                   float_status=status, float_source=(info or {}).get("source"))
        row.update(tags.get(ticker) or {"reverse_split": False})
        (confirmed if status in ("exact", "bound") else unverified).append(row)

    tickers = confirmed + unverified[:C.UNIVERSE_UNVERIFIED_MAX]
    if len(tickers) < C.UNIVERSE_MIN_COUNT and old.get("tickers"):
        print("::warning title=Universe small::الكون الجديد صغير جدًا — أُبقيت القائمة السابقة")
        return old
    payload = {
        "built_on": today, "built_at": now.isoformat(), "count": len(tickers),
        "confirmed": len(confirmed), "unverified": min(len(unverified), C.UNIVERSE_UNVERIFIED_MAX),
        "reverse_split_tagged": sum(1 for row in tickers if row.get("reverse_split")),
        "rules": {"price": [C.UNIVERSE_MIN_PRICE, C.UNIVERSE_MAX_PRICE],
                  "max_float": C.UNIVERSE_MAX_FLOAT,
                  "min_avg_volume": C.UNIVERSE_MIN_AVG_VOLUME,
                  "pool_max": C.UNIVERSE_POOL_MAX},
        "tickers": tickers,
    }
    save(path, payload)
    print("universe built: %d (confirmed %d, unverified %d)"
          % (len(tickers), len(confirmed), min(len(unverified), C.UNIVERSE_UNVERIFIED_MAX)))
    return payload


def load_universe(path: str = C.UNIVERSE_FILE) -> dict:
    return load(path, {"tickers": []})


def cli(force: bool = False, limit: int | None = None, tickers: str | None = None,
        path: str = C.UNIVERSE_FILE) -> dict:
    """نقطة تشغيل بناء الكون (تُستدعى من build_universe.py)."""
    now = datetime.now(timezone.utc)
    if tickers:
        symbols = [t.strip().upper() for t in tickers.split(",") if t.strip()]
    else:
        symbols = symbol_directory()
    if limit:
        symbols = symbols[:limit]
    print("symbols:", len(symbols))
    pool = build_pool(symbols)
    print("pool in range:", len(pool))
    return build_universe(pool, now=now, force=force, path=path)


__all__ = ["symbol_directory", "pool_record", "build_pool", "build_universe",
           "load_universe", "reverse_split_tags", "cli"]
