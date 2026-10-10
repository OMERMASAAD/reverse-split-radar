# -*- coding: utf-8 -*-
"""
مؤشرات فنية خالصة (بلا أي طلبات شبكة) مكتوبة لتكون مطابقة لما يظهر في
منصات التداول: RSI بطريقة Wilder، EMA، MACD، ATR، OBV، CMF، VWAP مرتكز، CLV،
وميل الانحدار الخطي.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import (ATR_PERIOD, CMF_PERIOD, EMA_FAST, EMA_SLOW, MACD_FAST, MACD_SIGNAL,
                     MACD_SLOW, OBV_LOOK)


def _series(x) -> pd.Series:
    if isinstance(x, pd.Series):
        return x.astype(float)
    return pd.Series(np.asarray(x, dtype=float))


def rsi(close, period: int = 14) -> pd.Series:
    """RSI بطريقة Wilder (بذرة SMA ثم تنعيم تكراري) — مطابق لـ TradingView/Yahoo."""
    s = _series(close)
    x = s.to_numpy(dtype=float)
    n = len(x)
    out = np.full(n, np.nan)
    if n <= period or np.isnan(x[:period + 1]).any():
        return pd.Series(out, index=s.index)
    delta = np.diff(x)
    gain = np.where(delta > 0, delta, 0.0)
    loss = np.where(delta < 0, -delta, 0.0)
    avg_gain = float(gain[:period].mean())
    avg_loss = float(loss[:period].mean())
    out[period] = 100.0 if avg_loss == 0 else 100.0 - 100.0 / (1.0 + avg_gain / avg_loss)
    for i in range(period, n - 1):
        avg_gain = (avg_gain * (period - 1) + gain[i]) / period
        avg_loss = (avg_loss * (period - 1) + loss[i]) / period
        out[i + 1] = 100.0 if avg_loss == 0 else 100.0 - 100.0 / (1.0 + avg_gain / avg_loss)
    return pd.Series(out, index=s.index)


def ema(close, period: int) -> pd.Series:
    return _series(close).ewm(span=period, adjust=False).mean()


def macd(close, fast: int = MACD_FAST, slow: int = MACD_SLOW, signal: int = MACD_SIGNAL):
    """يعيد (الخط، خط الإشارة، الهيستوجرام)."""
    s = _series(close)
    line = ema(s, fast) - ema(s, slow)
    sig = line.ewm(span=signal, adjust=False).mean()
    return line, sig, line - sig


def true_range(df: pd.DataFrame) -> pd.Series:
    high = df["High"].astype(float)
    low = df["Low"].astype(float)
    prev_close = df["Close"].astype(float).shift(1)
    parts = pd.concat([(high - low), (high - prev_close).abs(), (low - prev_close).abs()], axis=1)
    return parts.max(axis=1)


def atr(df: pd.DataFrame, period: int = ATR_PERIOD) -> pd.Series:
    """ATR بطريقة Wilder."""
    tr = true_range(df)
    return tr.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()


def obv(close, volume) -> pd.Series:
    s, v = _series(close), _series(volume)
    return (np.sign(s.diff().fillna(0.0)) * v).cumsum()


def vwap(df: pd.DataFrame, start: int | None = None) -> pd.Series:
    """VWAP متراكم من `start` (افتراضيًا من أول شمعة في الإطار الممرر)."""
    x = df if start is None else df.iloc[max(0, int(start)):]
    if x.empty:
        return pd.Series(dtype=float)
    typical = (x["High"].astype(float) + x["Low"].astype(float) + x["Close"].astype(float)) / 3.0
    vol = x["Volume"].astype(float)
    cum_pv = (typical * vol).cumsum()
    cum_v = vol.cumsum().replace(0.0, np.nan)
    return cum_pv / cum_v


def anchored_vwap_value(df: pd.DataFrame, start: int | None = None) -> float | None:
    s = vwap(df, start)
    if s.empty:
        return None
    val = float(s.iloc[-1])
    return None if not np.isfinite(val) else val


def clv(df: pd.DataFrame) -> pd.Series:
    """Close Location Value: موقع الإغلاق داخل نطاق الشمعة بين -1 و +1."""
    high, low = df["High"].astype(float), df["Low"].astype(float)
    close = df["Close"].astype(float)
    rng = (high - low).replace(0.0, np.nan)
    return ((close - low) - (high - close)) / rng


def cmf(df: pd.DataFrame, period: int = CMF_PERIOD) -> pd.Series:
    """Chaikin Money Flow: مجموع (CLV × الحجم) ÷ مجموع الحجم على `period` شمعة.

    القيمة بين −1 و +1: فوق الصفر = ضغط شراء / تجميع سيولة (إيجابي)،
    وتحت الصفر = ضغط بيع / توزيع (سلبي) — مطابق لـ TradingView/Yahoo."""
    vol = df["Volume"].astype(float)
    mfv = clv(df).fillna(0.0) * vol          # Money Flow Volume
    denom = vol.rolling(period, min_periods=period).sum()
    return mfv.rolling(period, min_periods=period).sum() / denom.replace(0.0, np.nan)


def volume_delta(df: pd.DataFrame, look: int = OBV_LOOK) -> float:
    """دلتا حجم تقريبية: CLV × الحجم على النافذة (بديل تدفق الصفقات)."""
    tail = df.tail(look)
    if tail.empty:
        return 0.0
    return float((clv(tail).fillna(0.0) * tail["Volume"].astype(float)).sum())


def rolling_slope(values, look: int = 5) -> float | None:
    """ميل انحدار خطي بسيط (لكل شمعة) — يُستخدم لميل OBV والقاعدة."""
    s = _series(values).tail(look).to_numpy(dtype=float)
    s = s[~np.isnan(s)]
    n = len(s)
    if n < 3:
        return None
    xs = np.arange(n, dtype=float)
    denom = float(((xs - xs.mean()) ** 2).sum())
    if denom == 0:
        return None
    return float(((xs - xs.mean()) * (s - s.mean())).sum() / denom)


def stdev_pct(df: pd.DataFrame) -> float | None:
    """تشتّت العوائد داخل النافذة — مقياس ضيق القاعدة."""
    closes = df["Close"].astype(float)
    if len(closes) < 3:
        return None
    rets = closes.pct_change().dropna()
    if rets.empty:
        return None
    val = float(rets.std(ddof=0)) * 100.0
    return None if not np.isfinite(val) else val


def resample_bars(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    """إعادة تجميع شموع إلى فريم أعلى (مثل 15min) مع تجاهل الشموع الفارغة."""
    if df is None or df.empty:
        return pd.DataFrame()
    out = df.resample(rule, label="left", closed="left").agg(
        {"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"}
    )
    out = out.dropna(subset=["Open", "High", "Low", "Close"])
    return out[out["Volume"] > 0] if "Volume" in out else out


def indicators_frame(df: pd.DataFrame) -> pd.DataFrame:
    """إضافة كل المؤشرات المطلوبة على نسخة من الإطار (للرسم والتحليل)."""
    out = df.copy()
    close = out["Close"].astype(float)
    out["rsi"] = rsi(close)
    out["ema_fast"] = ema(close, EMA_FAST)
    out["ema_slow"] = ema(close, EMA_SLOW)
    line, sig, hist = macd(close)
    out["macd"], out["macd_signal"], out["macd_hist"] = line, sig, hist
    out["obv"] = obv(close, out["Volume"].astype(float))
    out["cmf"] = cmf(out)
    out["atr"] = atr(out)
    out["vwap"] = vwap(out)
    return out


__all__ = [
    "rsi", "ema", "macd", "atr", "true_range", "obv", "cmf", "vwap", "anchored_vwap_value",
    "clv", "volume_delta", "rolling_slope", "stdev_pct", "resample_bars", "indicators_frame",
]
