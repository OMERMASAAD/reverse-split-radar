# -*- coding: utf-8 -*-
"""أدوات إدخال/إخراج آمنة: تسلسل JSON صارم، تحميل، حفظ، سجل المسح، والتنبيهات."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from .config import ALERTS_KEEP, SCAN_LOG_KEEP


def json_safe(value):
    """يحوّل قيم NumPy/Pandas والأعداد غير المنتهية إلى JSON صارم (بلا NaN)."""
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [json_safe(item) for item in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, (np.integer, int)):
        return int(value)
    if isinstance(value, (float, np.floating)):
        val = float(value)
        return val if np.isfinite(val) else None
    if isinstance(value, str) or value is None:
        return value
    if isinstance(value, (datetime,)):
        return value.isoformat()
    return str(value)


def load(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return default if default is not None else {}


def save(path, payload) -> int:
    """كتابة ذرية: ملف مؤقت ثم استبدال — يحمي القارئ لو انقطع التشغيل."""
    text = json.dumps(json_safe(payload), ensure_ascii=False, indent=1, allow_nan=False)
    tmp = Path(str(path) + ".tmp")
    tmp.write_text(text + "\n", encoding="utf-8")
    os.replace(tmp, path)
    return len(text)


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def heartbeat(at: datetime, *, ok: bool, coverage_pct=None, frames=0, master=0,
              items=0, complete=0, duration_s=None, skipped=None, error=None) -> dict:
    row = {
        "at": at.isoformat(),
        "ok": bool(ok),
        "coverage_pct": coverage_pct,
        "frames": int(frames),
        "master": int(master),
        "items": int(items),
        "complete": int(complete),
        "duration_s": round(float(duration_s), 1) if duration_s is not None else None,
    }
    if skipped:
        row["skipped"] = skipped
    if error:
        row["error"] = str(error)[:200]
    return row


def stamp_scan_log(payload: dict, beat: dict, prev: dict | None = None) -> dict:
    """يُبقي سجل المسح حتى لو لم تتغير الأسهم — هذا ما تقرأه الواجهة كل 15 دقيقة."""
    log = list((prev or payload or {}).get("scan_log") or [])
    if not log or log[-1].get("at") != beat.get("at"):
        log.append(beat)
    payload["scan_log"] = log[-SCAN_LOG_KEEP:]
    payload["last_scan"] = beat
    payload["updated_at"] = beat["at"]
    return payload


def push_alert(payload: dict, alert: dict) -> dict:
    """يضيف تنبيهًا (إشارة جديدة/اكتمال/شطب) ويحافظ على آخر N فقط."""
    feed = list(payload.get("alerts") or [])
    key = (alert.get("ticker"), alert.get("kind"), alert.get("at"))
    if not any((a.get("ticker"), a.get("kind"), a.get("at")) == key for a in feed):
        feed.append(alert)
    payload["alerts"] = feed[-ALERTS_KEEP:]
    return payload


def uptime(scan_log: list) -> dict:
    """إحصاء صحة التشغيل من سجل المسح: نجاح/فشل/تخطّي ومتوسط المدة."""
    if not scan_log:
        return {"runs": 0, "ok_runs": 0, "skipped": 0, "failed": 0, "ok_rate_pct": None,
                "avg_duration_s": None}
    ok = sum(1 for row in scan_log if row.get("ok"))
    skipped = sum(1 for row in scan_log if row.get("skipped"))
    durations = [row["duration_s"] for row in scan_log if row.get("duration_s") is not None]
    return {
        "runs": len(scan_log),
        "ok_runs": ok,
        "skipped": skipped,
        "failed": sum(1 for row in scan_log if not row.get("ok")),
        "ok_rate_pct": round(ok / len(scan_log) * 100.0, 1),
        "avg_duration_s": round(sum(durations) / len(durations), 1) if durations else None,
        "first_at": scan_log[0].get("at"),
        "last_at": scan_log[-1].get("at"),
    }


__all__ = ["json_safe", "load", "save", "now_utc", "heartbeat", "stamp_scan_log",
           "push_alert", "uptime"]
