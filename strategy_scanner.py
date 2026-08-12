import json
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import yfinance as yf

# ============================================================
# REVERSE SPLIT RADAR - CLEAN FINAL
# ============================================================

CANDIDATES_FILE = "reverse_split_candidates.json"

MIN_DAYS = 20
MAX_DAYS = 50
MIN_HISTORY_DAYS = 60

HALF_ZONE_TOLERANCE = 0.15
SUPPORT_TOLERANCE = 0.04
MIN_SUPPORT_TESTS = 2
QUIET_VOLUME_RATIO = 1.50
MAX_SHORT = 50000
MAX_FLOAT = 4000000
MAX_SCORE = 26


def load_tickers():
    try:
        with open(CANDIDATES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        items = data if isinstance(data, list) else data.get("candidates", [])
        return [
            str(x["symbol"]).upper()
            for x in items
            if isinstance(x, dict) and "symbol" in x
        ]
    except Exception as e:
        print(f"ERROR loading candidates: {e}")
        return []


def safe_float(x):
    try:
        if x is None:
            return None
        x = float(x)
        return None if np.isnan(x) else x
    except Exception:
        return None


def fmt_price(x):
    x = safe_float(x)
    return "N/A" if x is None else f"${x:.4f}"


def fmt_num(x):
    x = safe_float(x)
    return "N/A" if x is None else f"{x:,.0f}"


def calculate_rsi(close, period=14):
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def calculate_macd(close):
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    return macd, signal, macd - signal


def get_reverse_split_info(stock):
    try:
        splits = stock.splits
        if splits is None or splits.empty:
            return None

        latest_date = None
        latest_ratio = None

        for date, ratio in splits.items():
            ratio = safe_float(ratio)
            if ratio is None or ratio >= 1:
                continue

            d = pd.Timestamp(date).date()
            if latest_date is None or d > latest_date:
                latest_date = d
                latest_ratio = ratio

        return None if latest_date is None else (latest_date, latest_ratio)
    except Exception:
        return None


def reverse_ratio_text(ratio):
    ratio = safe_float(ratio)
    if ratio is None or ratio <= 0:
        return "Unknown"
    return f"{round(1 / ratio)}:1 Reverse split"


def calculate_support(df):
    if len(df) < 10:
        return None
    lows = df.tail(40)["Low"].dropna()
    return None if lows.empty else float(np.percentile(lows, 15))


def count_support_tests(df, support):
    if support is None:
        return 0

    tolerance = support * SUPPORT_TOLERANCE
    tests = 0
    last_date = None

    for idx, row in df.tail(40).iterrows():
        low = safe_float(row["Low"])
        if low is None or abs(low - support) > tolerance:
            continue

        d = pd.Timestamp(idx).date()
        if last_date is None or (d - last_date).days >= 2:
            tests += 1
            last_date = d

    return tests


def analyze_half_zone(df, split_date):
    result = {
        "split_open": None,
        "half_level": None,
        "zone_low": None,
        "zone_high": None,
        "tests": 0,
        "successful_tests": 0,
        "stable": False,
        "passed": False,
        "status": "FAIL",
        "reason": "",
    }

    try:
        split_rows = df[df.index.date == split_date]
        if split_rows.empty:
            result["reason"] = "ÙØ§ ØªÙØ¬Ø¯ Ø´ÙØ¹Ø© ÙÙÙ Ø§ÙØªÙØ³ÙÙ"
            return result

        split_open = safe_float(split_rows.iloc[0]["Open"])
        if split_open is None or split_open <= 0:
            result["reason"] = "ØªØ¹Ø°Ø± ØªØ­Ø¯ÙØ¯ Ø§ÙØªØªØ§Ø­ ÙÙÙ Ø§ÙØªÙØ³ÙÙ"
            return result

        half = split_open / 2
        low_zone = half * (1 - HALF_ZONE_TOLERANCE)
        high_zone = half * (1 + HALF_ZONE_TOLERANCE)

        result.update({
            "split_open": split_open,
            "half_level": half,
            "zone_low": low_zone,
            "zone_high": high_zone,
        })

        after = df[df.index.date > split_date]
        tests = []

        for idx, row in after.iterrows():
            low = safe_float(row["Low"])
            close = safe_float(row["Close"])
            if low is None:
                continue
            if low_zone <= low <= high_zone:
                rebound = close is not None and close > low * 1.03
                tests.append({"date": idx, "rebound": rebound})

        grouped = []
        for test in tests:
            if not grouped:
                grouped.append(test)
                continue
            gap = (
                pd.Timestamp(test["date"]).date()
                - pd.Timestamp(grouped[-1]["date"]).date()
            ).days
            if gap >= 2:
                grouped.append(test)

        result["tests"] = len(grouped)
        result["successful_tests"] = sum(x["rebound"] for x in grouped)

        if len(grouped) >= 2 and result["successful_tests"] >= 1:
            result["stable"] = True
            result["passed"] = True
            result["status"] = "PASS"
            result["reason"] = "Ø§Ø®ØªØ¨Ø§Ø±Ø§Ù Ø£Ù Ø£ÙØ«Ø± ÙØ¹ Ø«Ø¨Ø§Øª ÙØ§Ø±ØªØ¯Ø§Ø¯"
        elif len(grouped) == 1:
            result["status"] = "WATCH"
            result["reason"] = "Ø§Ø®ØªØ¨Ø§Ø± ÙØ§Ø­Ø¯ ÙÙØ· - ÙÙØªØ¸Ø± Ø¥Ø¹Ø§Ø¯Ø© Ø§ÙØ§Ø®ØªØ¨Ø§Ø±"
        else:
            result["status"] = "WAIT"
            result["reason"] = "ÙÙ ÙØªØ£ÙØ¯ Ø§ÙÙØ§Ø¹ Ø¨Ø¹Ø¯"

        return result
    except Exception as e:
        result["reason"] = f"Ø®Ø·Ø£: {e}"
        return result


def get_catalysts(stock):
    catalysts = []

    try:
        calendar = stock.calendar
        if isinstance(calendar, dict):
            if calendar.get("Earnings Date") is not None:
                catalysts.append("ÙÙØ¹Ø¯ ÙØªØ§Ø¦Ø¬ ÙØ§ÙÙØ©")
        elif isinstance(calendar, pd.DataFrame):
            if not calendar.empty and "Earnings Date" in calendar.index:
                catalysts.append("ÙÙØ¹Ø¯ ÙØªØ§Ø¦Ø¬ ÙØ§ÙÙØ©")
    except Exception:
        pass

    try:
        earnings = stock.get_earnings_dates(limit=4)
        if earnings is not None and not earnings.empty:
            now = pd.Timestamp.now()
            for d in earnings.index:
                try:
                    d = pd.Timestamp(d)
                    if d.tzinfo is not None:
                        d = d.tz_localize(None)
                    if d >= now:
                        catalysts.append("ÙØªØ§Ø¦Ø¬ ÙØ§ÙÙØ© ÙØ§Ø¯ÙØ©")
                        break
                except Exception:
                    continue
    except Exception:
        pass

    return list(dict.fromkeys(catalysts))


def analyze_stock(ticker):
    try:
        stock = yf.Ticker(ticker)
        split_info = get_reverse_split_info(stock)
        if split_info is None:
            return None

        split_date, split_ratio = split_info
        today = datetime.now().date()
        days_since_split = (today - split_date).days

        if not (MIN_DAYS <= days_since_split <= MAX_DAYS):
            return None

        df = stock.history(
            start=split_date - timedelta(days=150),
            end=today + timedelta(days=1),
            auto_adjust=False,
        )

        if df is None or df.empty:
            return None

        df = df.dropna(subset=["Open", "High", "Low", "Close", "Volume"])
        if len(df) < MIN_HISTORY_DAYS:
            return None

        df["RSI"] = calculate_rsi(df["Close"])
        df["MACD"], df["MACD_SIGNAL"], df["MACD_HIST"] = calculate_macd(df["Close"])
        df["MA20"] = df["Close"].rolling(20).mean()
        df["MA50"] = df["Close"].rolling(50).mean()

        latest = df.iloc[-1]
        price = safe_float(latest["Close"])
        volume = safe_float(latest["Volume"])
        rsi = safe_float(latest["RSI"])
        macd = safe_float(latest["MACD"])
        macd_hist = safe_float(latest["MACD_HIST"])
        ma20 = safe_float(latest["MA20"])
        ma50 = safe_float(latest["MA50"])

        if price is None:
            return None

        previous_rsi = safe_float(df["RSI"].iloc[-2]) if len(df) >= 2 else None
        rsi_improving = (
            rsi is not None and previous_rsi is not None and rsi > previous_rsi
        )

        macd_improving = False
        if len(df) >= 3:
            h1 = safe_float(df["MACD_HIST"].iloc[-2])
            h2 = safe_float(df["MACD_HIST"].iloc[-3])
            macd_improving = h1 is not None and h2 is not None and h1 > h2

        volume20 = safe_float(df["Volume"].tail(20).mean())
        volume_ratio = None
        if volume is not None and volume20 and volume20 > 0:
            volume_ratio = volume / volume20
        quiet_volume = volume_ratio is not None and volume_ratio <= QUIET_VOLUME_RATIO

        post = df[df.index.date >= split_date]
        if post.empty:
            return None

        split_open = safe_float(post.iloc[0]["Open"])
        split_high = safe_float(post["High"].max())
        split_low = safe_float(post["Low"].min())
        if split_open is None:
            return None

        post_change = ((price - split_open) / split_open) * 100
        drawdown = ((price - split_high) / split_high) * 100 if split_high and split_high > 0 else None

        half = analyze_half_zone(df, split_date)
        support = calculate_support(df)
        support_tests = count_support_tests(df, support)

        near_support = False
        if support and support > 0:
            distance = (price - support) / support
            near_support = 0 <= distance <= 0.20

        float_shares = None
        short_shares = None
        try:
            info = stock.info
            float_shares = safe_float(info.get("floatShares"))
            short_shares = safe_float(info.get("sharesShort"))
        except Exception:
            pass

        float_ok = float_shares is not None and float_shares <= MAX_FLOAT
        short_ok = short_shares is not None and short_shares <= MAX_SHORT
        ma20_ok = ma20 is not None and price <= ma20 * 1.10
        catalysts = get_catalysts(stock)

        score = 2
        signals = ["Reverse Split Ø­Ø¯ÙØ«"]
        warnings = []

        if half["passed"]:
            score += 4
            signals.append(f"Ø¯Ø¹Ù ÙØµÙ Ø§ÙØ´ÙØ¹Ø© ÙØ¤ÙØ¯ ({half['tests']} Ø§Ø®ØªØ¨Ø§Ø±Ø§Øª)")
        elif half["status"] == "WATCH":
            score += 1
            warnings.append("Ø§Ø®ØªØ¨Ø§Ø± ÙØ§Ø­Ø¯ ÙÙØ· ÙÙØµÙ Ø§ÙØ´ÙØ¹Ø©")
        else:
            warnings.append("ÙÙ ÙØªØ£ÙØ¯ Ø¯Ø¹Ù ÙØµÙ Ø§ÙØ´ÙØ¹Ø©")

        if rsi is not None:
            if rsi < 30:
                score += 3
                if rsi_improving:
                    score += 2
                    signals.append(f"RSI ÙÙØ®ÙØ¶ ÙÙØªØ­Ø³Ù ({previous_rsi:.1f}->{rsi:.1f})")
                else:
                    signals.append(f"RSI ÙÙØ®ÙØ¶ ({rsi:.1f})")
            elif rsi < 35:
                score += 1
                signals.append(f"RSI ÙØ±ÙØ¨ ÙÙ Ø§ÙØªØ´Ø¨Ø¹ Ø§ÙØ¨ÙØ¹Ù ({rsi:.1f})")
            elif rsi < 50:
                signals.append(f"RSI ÙØ­Ø§ÙØ¯ ({rsi:.1f})")
            else:
                warnings.append(f"RSI ÙØ±ØªÙØ¹ ({rsi:.1f})")

        if macd_improving:
            score += 2
            signals.append("MACD ÙØªØ­Ø³Ù")
        else:
            warnings.append("MACD ÙÙ ÙØ¸ÙØ± ØªØ­Ø³ÙÙØ§ ÙØ§ÙÙÙØ§")

        if quiet_volume:
            score += 2
            signals.append(f"Volume ÙØ§Ø¯Ø¦ ({fmt_num(volume)})")
        elif volume_ratio is not None:
            signals.append(f"Volume Ratio {volume_ratio:.2f}x")

        if support_tests >= 2:
            score += 2
            signals.append(f"Ø§ÙØ¯Ø¹Ù Ø§ÙØ¹Ø§Ù Ø§Ø®ØªÙØ¨Ø± {support_tests} ÙØ±Ø§Øª")
        elif support_tests == 1:
            score += 1
            signals.append("ÙÙØ¬Ø¯ Ø§Ø®ØªØ¨Ø§Ø± Ø¯Ø¹Ù ÙØ§Ø­Ø¯")

        if near_support:
            score += 1
            signals.append("Ø§ÙØ³Ø¹Ø± ÙØ±ÙØ¨ ÙÙ Ø§ÙØ¯Ø¹Ù")

        if drawdown is not None:
            if drawdown <= -40:
                score += 3
                signals.append(f"ÙØ¨ÙØ· ÙÙÙ ÙÙ Ø§ÙÙÙØ© ({drawdown:.1f}%)")
            elif drawdown <= -30:
                score += 2
                signals.append(f"ØªØµØ­ÙØ­ Ø¬ÙØ¯ ÙÙ Ø§ÙÙÙØ© ({drawdown:.1f}%)")
            elif drawdown <= -20:
                score += 1
                signals.append(f"ØªØµØ­ÙØ­ ÙØªÙØ³Ø· ({drawdown:.1f}%)")

        if float_ok:
            score += 1
            signals.append(f"Float ÙÙØ®ÙØ¶ ({fmt_num(float_shares)})")

        if short_ok:
            score += 1
            signals.append(f"Short ÙÙØ®ÙØ¶ ({fmt_num(short_shares)})")
        elif short_shares is not None:
            warnings.append(f"Short ÙØ±ØªÙØ¹ ({fmt_num(short_shares)})")

        if ma20_ok:
            score += 1
            signals.append("Ø§ÙØ³Ø¹Ø± ÙØ±ÙØ¨ ÙÙ MA20")

        if catalysts:
            score += 2
            signals.extend(catalysts)

        score_percent = round((score / MAX_SCORE) * 100, 1)

        core = 0
        if half["passed"]:
            core += 2
        elif half["status"] == "WATCH":
            core += 1
        if rsi is not None and rsi < 35:
            core += 1
        if rsi_improving:
            core += 1
        if macd_improving:
            core += 1
        if quiet_volume:
            core += 1
        if support_tests >= 2:
            core += 1
        if near_support:
            core += 1
        if float_ok:
            core += 1
        if catalysts:
            core += 1

        if half["passed"] and rsi_improving and macd_improving and core >= 6:
            next_step = "READY_TRIGGER"
            next_text = "Ø§ÙØ¯Ø¹Ù ÙØ¤ÙØ¯. Ø§ÙØªØ¸Ø± ØªØ£ÙÙØ¯ ØµØ¹ÙØ¯/Ø­Ø¬Ù ÙÙØ¯Ø®ÙÙ."
        elif half["passed"]:
            next_step = "WAIT_TRIGGER"
            next_text = "Ø§ÙØ¯Ø¹Ù ÙØ¤ÙØ¯Ø ÙÙÙ ÙÙØªØ¸Ø± ØªØ­Ø³Ù Ø§ÙÙØ¤Ø´Ø±Ø§Øª Ø£Ù ÙØ­ÙØ²."
        elif half["status"] == "WATCH":
            next_step = "WAIT_RETEST"
            next_text = "ØªÙ Ø§Ø®ØªØ¨Ø§Ø± Ø§ÙÙÙØ·ÙØ© ÙØ±Ø© ÙØ§Ø­Ø¯Ø©. Ø§ÙØªØ¸Ø± Ø¥Ø¹Ø§Ø¯Ø© Ø§ÙØ§Ø®ØªØ¨Ø§Ø± ÙØ§ÙØ«Ø¨Ø§Øª."
        else:
            next_step = "WAIT_SUPPORT"
            next_text = "ÙØ§ ØªØ¯Ø®Ù. Ø§ÙØªØ¸Ø± ØªÙÙÙÙ ÙØ§Ø¹ ÙØ§Ø®ØªØ¨Ø§Ø± Ø¯Ø¹Ù ÙØ§Ø¶Ø­."

        if next_step == "READY_TRIGGER" and score >= 18:
            rating = "MATCH ÙÙÙ Ø¬Ø¯Ø§Ù"
        elif half["passed"] and core >= 5:
            rating = "WATCHLIST ÙÙÙØ©"
        elif core >= 3:
            rating = "WATCHLIST"
        else:
            rating = "ÙØ±Ø§ÙØ¨Ø©"

        return {
            "ticker": ticker,
            "score": score,
            "score_percent": score_percent,
            "rating": rating,
            "next_step": next_step,
            "next_text": next_text,
            "price": price,
            "split_date": split_date,
            "split_ratio": split_ratio,
            "days_since_split": days_since_split,
            "split_open": split_open,
            "split_high": split_high,
            "split_low": split_low,
            "post_change": post_change,
            "drawdown": drawdown,
            "support": support,
            "support_tests": support_tests,
            "volume": volume,
            "volume20": volume20,
            "volume_ratio": volume_ratio,
            "rsi": rsi,
            "previous_rsi": previous_rsi,
            "rsi_improving": rsi_improving,
            "macd": macd,
            "macd_hist": macd_hist,
            "macd_improving": macd_improving,
            "ma20": ma20,
            "ma50": ma50,
            "float_shares": float_shares,
            "short_shares": short_shares,
            "half": half,
            "catalysts": catalysts,
            "signals": signals,
            "warnings": warnings,
            "core": core,
        }

    except Exception as e:
        print(f"ERROR analyzing {ticker}: {e}")
        return None


def main():
    tickers = load_tickers()

    print("\n" + "=" * 75)
    print("REVERSE SPLIT RADAR - FINAL STRATEGY")
    print("=" * 75)
    print(f"Ø§ÙÙØªØ±Ø©: {MIN_DAYS}-{MAX_DAYS} ÙÙÙ Ø¨Ø¹Ø¯ Reverse Split")
    print(f"ÙÙØ·ÙØ© ÙØµÙ Ø§ÙØ§ÙØªØªØ§Ø­: Â±{HALF_ZONE_TOLERANCE * 100:.0f}%")
    print("ØªØ£ÙÙØ¯ Ø§ÙØ¯Ø¹Ù: Ø§Ø®ØªØ¨Ø§Ø±Ø§Ù Ø¹ÙÙ Ø§ÙØ£ÙÙ ÙØ¹ Ø«Ø¨Ø§Øª/Ø§Ø±ØªØ¯Ø§Ø¯")
    print(f"Ø¹Ø¯Ø¯ Ø§ÙØ£Ø³ÙÙ: {len(tickers)}")
    print("=" * 75)

    results = []

    for ticker in tickers:
        print(f"\nØªØ­ÙÙÙ: {ticker}")
        result = analyze_stock(ticker)
        if result is None:
            print("ÙØ§ ØªÙØ¬Ø¯ Ø¨ÙØ§ÙØ§Øª ÙØ§ÙÙØ© Ø£Ù Ø§ÙØ³ÙÙ Ø®Ø§Ø±Ø¬ Ø§ÙÙØªØ±Ø©.")
            continue

        results.append(result)
        h = result["half"]

        print("-" * 75)
        print(f"Ø§ÙØ³Ø¹Ø± Ø§ÙØ­Ø§ÙÙ: {fmt_price(result['price'])}")
        print(f"Reverse Split: {result['split_date']}")
        print(f"Ø§ÙÙØ³Ø¨Ø©: {reverse_ratio_text(result['split_ratio'])}")
        print(f"Ø§ÙØ£ÙØ§Ù ÙÙØ° Ø§ÙØªÙØ³ÙÙ: {result['days_since_split']}")
        print(f"Ø§ÙØªØªØ§Ø­ ÙÙÙ Ø§ÙØªÙØ³ÙÙ: {fmt_price(result['split_open'])}")
        print(f"Ø£Ø¹ÙÙ Ø³Ø¹Ø± ÙÙØ° Ø§ÙØªÙØ³ÙÙ: {fmt_price(result['split_high'])}")
        print(f"Ø£Ø¯ÙÙ Ø³Ø¹Ø± ÙÙØ° Ø§ÙØªÙØ³ÙÙ: {fmt_price(result['split_low'])}")
        print(f"Ø§ÙØ­Ø±ÙØ© ÙÙ Ø§ÙØ§ÙØªØªØ§Ø­: {result['post_change']:.1f}%")
        if result["drawdown"] is not None:
            print(f"Ø§ÙÙØ¨ÙØ· ÙÙ Ø§ÙÙÙØ©: {result['drawdown']:.1f}%")
        print(f"Ø§ÙØ¯Ø¹Ù Ø§ÙØ¹Ø§Ù: {fmt_price(result['support'])}")
        print(f"Ø§Ø®ØªØ¨Ø§Ø±Ø§Øª Ø§ÙØ¯Ø¹Ù Ø§ÙØ¹Ø§Ù: {result['support_tests']}")
        print(f"Volume: {fmt_num(result['volume'])}")
        if result["volume_ratio"] is not None:
            print(f"Volume Ratio: {result['volume_ratio']:.2f}x")
        print(f"RSI: {result['rsi']:.1f}" if result["rsi"] is not None else "RSI: N/A")
        if result["previous_rsi"] is not None:
            print(f"RSI Ø§ÙØ³Ø§Ø¨Ù: {result['previous_rsi']:.1f}")
        print(f"MACD: {result['macd']:.5f}" if result["macd"] is not None else "MACD: N/A")
        print(f"MA20: {fmt_price(result['ma20'])}")
        print(f"MA50: {fmt_price(result['ma50'])}")

        print("\nÙÙØ·ÙØ© ÙØµÙ Ø´ÙØ¹Ø© Ø§ÙØªÙØ³ÙÙ")
        print("-" * 75)
        print(f"ÙØµÙ Ø§ÙØ§ÙØªØªØ§Ø­: {fmt_price(h['half_level'])}")
        print(f"ÙÙØ·ÙØ© Ø§ÙØ¨Ø­Ø« Ø¹Ù Ø§ÙÙØ§Ø¹: {fmt_price(h['zone_low'])} - {fmt_price(h['zone_high'])}")
        print(f"Ø§Ø®ØªØ¨Ø§Ø±Ø§Øª Ø§ÙÙÙØ·ÙØ©: {h['tests']}")
        print(f"Ø§Ø®ØªØ¨Ø§Ø±Ø§Øª ÙØ§Ø¬Ø­Ø©/Ø§Ø±ØªØ¯Ø§Ø¯: {h['successful_tests']}")
        print(f"Ø­Ø§ÙØ© Ø§ÙØ¯Ø¹Ù: {h['status']}")
        print(f"Ø§ÙØªÙØ³ÙØ±: {h['reason']}")

        print("\nØ¥Ø´Ø§Ø±Ø§Øª Ø§ÙØªØ­ÙÙÙ")
        print("-" * 75)
        for s in result["signals"]:
            print(f"OK: {s}")
        for w in result["warnings"]:
            print(f"WARN: {w}")

        print("\nØ§ÙÙØªÙØ¬Ø©")
        print(f"Ø§ÙØªÙÙÙÙ: {result['rating']}")
        print(f"SCORE: {result['score']}/{MAX_SCORE}")
        print(f"SCORE %: {result['score_percent']:.1f}%")
        print(f"CORE: {result['core']}")
        print(f"Ø§ÙØ®Ø·ÙØ© Ø§ÙØªØ§ÙÙØ©: {result['next_step']}")
        print(f">>> {result['next_text']}")

    rating_order = {
        "MATCH ÙÙÙ Ø¬Ø¯Ø§Ù": 4,
        "WATCHLIST ÙÙÙØ©": 3,
        "WATCHLIST": 2,
        "ÙØ±Ø§ÙØ¨Ø©": 1,
    }

    results.sort(
        key=lambda x: (
            rating_order.get(x["rating"], 0),
            x["half"]["passed"],
            x["half"]["tests"],
            x["rsi_improving"],
            x["macd_improving"],
            x["core"],
            x["score"],
        ),
        reverse=True,
    )

    print("\n" + "=" * 75)
    print("Ø£ÙØ¶Ù Ø§ÙØ£Ø³ÙÙ")
    print("=" * 75)

    for title in ["MATCH ÙÙÙ Ø¬Ø¯Ø§Ù", "WATCHLIST ÙÙÙØ©", "WATCHLIST"]:
        group = [r for r in results if r["rating"] == title]
        if not group:
            continue
        print(f"\n{title}\n" + "-" * 75)
        for i, r in enumerate(group[:10], 1):
            rsi_text = f"{r['rsi']:.1f}" if r["rsi"] is not None else "N/A"
            print(
                f"{i}. {r['ticker']} | Score {r['score']}/{MAX_SCORE} "
                f"({r['score_percent']:.1f}%) | RSI {rsi_text} | "
                f"Vol {fmt_num(r['volume'])} | Price {fmt_price(r['price'])} | "
                f"Half {fmt_price(r['half']['half_level'])} | Tests {r['half']['tests']} | {r['next_step']}"
            )

    priority = [
        r for r in results
        if r["next_step"] in {"READY_TRIGGER", "WAIT_TRIGGER", "WAIT_RETEST"}
    ]

    print("\n" + "=" * 75)
    print("ÙØ§Ø¦ÙØ© Ø§ÙØ£ÙÙÙÙØ© ÙÙÙØªØ§Ø¨Ø¹Ø©")
    print("=" * 75)

    if priority:
        for i, r in enumerate(priority[:15], 1):
            print(f"\n{i}. {r['ticker']} | {r['rating']} | Score {r['score']}/{MAX_SCORE} ({r['score_percent']:.1f}%)")
            print(f"   Ø§ÙØ³Ø¹Ø±: {fmt_price(r['price'])}")
            print(f"   ÙÙØ·ÙØ© ÙØµÙ Ø§ÙØ´ÙØ¹Ø©: {fmt_price(r['half']['zone_low'])} - {fmt_price(r['half']['zone_high'])}")
            print(f"   Ø§ÙØ§Ø®ØªØ¨Ø§Ø±Ø§Øª: {r['half']['tests']}")
            print(f"   Ø§ÙØ®Ø·ÙØ©: {r['next_text']}")
    else:
        print("ÙØ§ ÙÙØ¬Ø¯ Ø³ÙÙ Ø­Ø§ÙÙÙØ§ ÙÙ ÙØ±Ø­ÙØ© ØªØ£ÙÙØ¯ Ø§ÙØ¯Ø¹Ù.")

    print("\n" + "=" * 75)
    print("Ø§ÙÙØ­ÙØ²Ø§Øª Ø§ÙÙØ³ØªÙØ¨ÙÙØ©")
    print("=" * 75)

    found = False
    for r in results:
        if not r["catalysts"]:
            continue
        found = True
        print(f"\n{r['ticker']}")
        for c in r["catalysts"]:
            print(f"  - {c}")
    if not found:
        print("ÙØ§ ØªÙØ¬Ø¯ ÙØ­ÙØ²Ø§Øª ÙØ³ØªÙØ¨ÙÙØ© ÙØ§Ø¶Ø­Ø© ÙÙ Ø§ÙØ¨ÙØ§ÙØ§Øª Ø§ÙÙØªØ§Ø­Ø©.")

    dashboard_data = {
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "stocks": [],
    }

    for r in priority:
        dashboard_data["stocks"].append({
            "t": r["ticker"],
            "price": r["price"],
            "half": r["half"]["half_level"],
            "zone_low": r["half"]["zone_low"],
            "zone_high": r["half"]["zone_high"],
            "tests": r["half"]["tests"],
            "successful_tests": r["half"]["successful_tests"],
            "rsi": r["rsi"],
            "previous_rsi": r["previous_rsi"],
            "rsi_improving": r["rsi_improving"],
            "macd": r["macd"],
            "macd_improving": r["macd_improving"],
            "volume": r["volume"],
            "volume20": r["volume20"],
            "volume_ratio": r["volume_ratio"],
            "ma20": r["ma20"],
            "ma50": r["ma50"],
            "score": r["score"],
            "score_percent": r["score_percent"],
            "core": r["core"],
            "status": r["rating"],
            "state": r["next_step"],
            "action": r["next_text"],
            "split_date": str(r["split_date"]),
            "split_ratio": r["split_ratio"],
            "days_since_split": r["days_since_split"],
            "split_open": r["split_open"],
            "split_high": r["split_high"],
            "split_low": r["split_low"],
            "drawdown": r["drawdown"],
            "post_change": r["post_change"],
            "support": r["support"],
            "support_tests": r["support_tests"],
            "float_shares": r["float_shares"],
            "short_shares": r["short_shares"],
            "catalysts": r["catalysts"],
            "signals": r["signals"],
            "warnings": r["warnings"],
        })

    with open("dashboard_data.json", "w", encoding="utf-8") as f:
        json.dump(dashboard_data, f, ensure_ascii=False, indent=2, default=str)

    print("\n" + "=" * 75)
    print("DASHBOARD DATA UPDATED")
    print("=" * 75)
    print(f"ØªÙ ØªØµØ¯ÙØ± {len(priority)} Ø³ÙÙ Ø¥ÙÙ dashboard_data.json")
    print("Ø§ÙØªÙÙ Reverse Split Strategy Scanner.")


if __name__ == "__main__":
    main()
