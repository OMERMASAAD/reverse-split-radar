# -*- coding: utf-8 -*-
"""
جلب Float / عدد الأسهم المُصدَرة من مصادر مجانية (بلا مفاتيح).

الأولوية:
  1) Yahoo `floatShares`        → Float دقيق (status = exact)
  2) Yahoo `sharesOutstanding`  → حد أعلى (status = bound)
  3) yfinance `get_shares_full` → حد أعلى
  4) SEC EDGAR (XBRL)           → حد أعلى

القاعدة: Float ≤ الأسهم المُصدَرة دائمًا، فإذا كانت الأسهم المُصدَرة ≤ الحد فالمسهم
منخفض الفلوت بالضرورة (قبول آمن). الدقة تُعلَن عبر `status` و`source`.
"""
from __future__ import annotations

import gzip
import json
import os
import threading
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import config as C

SEC_CONTACT = os.environ.get("SEC_CONTACT", "radar@example.com")
USER_AGENT = "panic-radar/1.0 (%s)" % SEC_CONTACT
FLOAT_MODE = os.environ.get("FLOAT_MODE", "auto")

SOURCE_YAHOO_FLOAT = "yahoo_float"
SOURCE_YAHOO_OUTSTANDING = "yahoo_outstanding"
SOURCE_YAHOO_SHARES = "yahoo_shares_full"
SOURCE_SEC = "sec_edgar"

SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_CONCEPT_URLS = (
    "https://data.sec.gov/api/xbrl/companyconcept/CIK{cik}/dei/EntityCommonStockSharesOutstanding.json",
    "https://data.sec.gov/api/xbrl/companyconcept/CIK{cik}/us-gaap/CommonStockSharesOutstanding.json",
    "https://data.sec.gov/api/xbrl/companyconcept/CIK{cik}/us-gaap/WeightedAverageNumberOfSharesOutstandingBasic.json",
)

_cache: dict = {}
_dirty = False
_lock = threading.Lock()
_sec_lock = threading.Lock()
_last_sec = [0.0]
_cik_map = None
_cik_tries = 0


def cache_path() -> str:
    return os.environ.get("FLOAT_CACHE_FILE", C.FLOAT_CACHE_FILE)


def load_cache() -> dict:
    global _cache
    try:
        _cache = json.loads(Path(cache_path()).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        _cache = {}
    return _cache


def save_cache() -> None:
    global _dirty
    with _lock:
        snapshot = dict(_cache)
        _dirty = False
    Path(cache_path()).write_text(json.dumps(snapshot, ensure_ascii=False, indent=1), encoding="utf-8")


def _http_json(url: str, timeout: int = 15):
    if "sec.gov" in url:                     # حد SEC ≈ 10 طلبات/ثانية
        with _sec_lock:
            wait = 0.125 - (time.time() - _last_sec[0])
            if wait > 0:
                time.sleep(wait)
            _last_sec[0] = time.time()
    req = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT, "Accept": "application/json",
        "Accept-Encoding": "gzip, deflate",
    })
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
        if resp.headers.get("Content-Encoding") == "gzip":
            raw = gzip.decompress(raw)
    return json.loads(raw.decode("utf-8", "replace"))


def cik_map() -> dict:
    global _cik_map, _cik_tries
    if _cik_map is not None:
        return _cik_map
    _cik_tries += 1
    try:
        data = _http_json(SEC_TICKERS_URL)
        _cik_map = {str(v.get("ticker", "")).upper(): int(v.get("cik_str"))
                    for v in data.values() if v.get("ticker") and v.get("cik_str")}
    except Exception as exc:                  # noqa: BLE001
        print("SEC cik map error (%d/3):" % _cik_tries, str(exc)[:120])
        if _cik_tries >= 3:
            _cik_map = {}
    return _cik_map


def sec_shares(ticker: str):
    cik = cik_map().get(str(ticker).upper())
    if not cik:
        return None
    for template in SEC_CONCEPT_URLS:
        try:
            payload = _http_json(template.format(cik="%010d" % cik))
        except Exception:                     # noqa: BLE001
            continue
        rows = [u for u in ((payload.get("units") or {}).get("shares") or []) if u.get("val")]
        if not rows:
            continue
        rows.sort(key=lambda u: (str(u.get("end") or ""), str(u.get("filed") or "")))
        value = int(rows[-1]["val"])
        if value > 0:
            return value
    return None


def yahoo_float(ticker: str):
    """(float_dقيق, أسهم_مُصدَرة) من Yahoo — أيهما غير متاح يكون None."""
    try:
        import yfinance as yf
        info = yf.Ticker(ticker).info or {}
    except Exception:                         # noqa: BLE001
        return None, None
    fl = info.get("floatShares")
    so = info.get("sharesOutstanding")
    return (int(fl) if fl else None), (int(so) if so else None)


def yahoo_shares_full(ticker: str):
    try:
        import yfinance as yf
        series = yf.Ticker(ticker).get_shares_full()
    except Exception:                         # noqa: BLE001
        return None
    if series is None or len(series) == 0:
        return None
    try:
        return int(series.dropna().iloc[-1])
    except Exception:                         # noqa: BLE001
        return None


def resolve(ticker: str, mode: str | None = None, now: datetime | None = None) -> dict:
    """قيمة Float/الحد الأعلى مع المصدر والحالة. يستخدم الكاش مع TTL."""
    global _dirty
    mode = mode or FLOAT_MODE
    now = now or datetime.now(timezone.utc)
    ticker = str(ticker).upper()
    if not _cache:
        load_cache()
    entry = _cache.get(ticker)
    if entry and _fresh(entry, now):
        return entry

    fl, so = yahoo_float(ticker)
    if fl:
        record = _record(ticker, fl, "exact", SOURCE_YAHOO_FLOAT, now)
    elif so:
        record = _record(ticker, so, "bound", SOURCE_YAHOO_OUTSTANDING, now)
    else:
        shares = yahoo_shares_full(ticker)
        source = SOURCE_YAHOO_SHARES
        if not shares:
            shares = sec_shares(ticker)
            source = SOURCE_SEC
        record = (_record(ticker, shares, "bound", source, now) if shares
                  else _record(ticker, None, "missing", "none", now, miss=True))
    with _lock:
        _cache[ticker] = record
        _dirty = True
    return record


def _record(ticker: str, value, status: str, source: str, now: datetime, miss: bool = False) -> dict:
    expiry = now + (timedelta(hours=C.FLOAT_MISS_TTL_HOURS) if miss
                    else timedelta(days=C.FLOAT_CACHE_TTL_DAYS))
    return {"ticker": ticker, "value": int(value) if value else None, "status": status,
            "source": source, "as_of": now.date().isoformat(), "expires": expiry.isoformat()}


def _fresh(entry: dict, now: datetime) -> bool:
    try:
        return datetime.fromisoformat(str(entry.get("expires"))).replace(
            tzinfo=timezone.utc) > now
    except (TypeError, ValueError):
        return False


def classify(info: dict, max_float: int = C.UNIVERSE_MAX_FLOAT,
             unknown_policy: str = "watch") -> tuple[bool, str]:
    """
    هل السهم منخفض الفلوت؟
      exact/bound ≤ الحد  ⇒ (True, الحالة)
      bound > الحد        ⇒ (False, 'too_big')
      missing             ⇒ حسب السياسة: watch ⇒ (True, 'unverified') / exclude ⇒ (False, 'unknown')
      bound > سقف المجهول ⇒ (False, 'unknown')
    """
    if not info:
        return (True, "unverified") if unknown_policy == "watch" else (False, "unknown")
    value, status = info.get("value"), info.get("status")
    if not value:
        return (True, "unverified") if unknown_policy == "watch" else (False, "unknown")
    if value <= max_float:
        return True, status
    if status == "bound" and value > C.FLOAT_UNKNOWN_CAP:
        return False, "unknown"
    if mode_strict():
        return False, "too_big"
    return (True, "unverified") if unknown_policy == "watch" else (False, "too_big")


def mode_strict() -> bool:
    return (os.environ.get("FLOAT_MODE", "auto") == "strict")


__all__ = ["resolve", "classify", "load_cache", "save_cache", "sec_shares", "yahoo_float",
           "yahoo_shares_full", "mode_strict"]
