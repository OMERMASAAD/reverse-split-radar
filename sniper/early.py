# -*- coding: utf-8 -*-
"""
EARLY REVERSAL DETECTION — الطبقة الجديدة المستقلة عن الإشارة المكتملة.

تبحث عن تغير سلوك السهم أثناء الهبوط قبل اكتمال نموذج الثبات أو استعادة VWAP.
كل عامل يمنح نقاطًا، والسالب يخفض — الدرجة قابلة للتفسير.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config as C
from .indicators import atr, cmf, obv, rsi, macd, clv, vwap, anchored_vwap_value


def _safe(v, d=0.0):
    try:
        if v is None: return d
        fv = float(v)
        return fv if np.isfinite(fv) else d
    except:
        return d

def early_reversal_score(df: pd.DataFrame, day: pd.DataFrame, base_win=None, indicators_now=None, volume_payload=None, vwap_value=None, base_metrics_dict=None) -> dict:
    """
    يحسب درجة بوادر الارتداد المبكر (0-100) + تفصيل كل عامل.
    لا يشترط تحقق جميع العوامل — الدرجة تراكمية مع عقوبات.
    """
    factors = {}
    scores = {}
    reasons = []

    if df is None or df.empty or day is None or day.empty:
        return {"score": 0, "label": "بيانات غير كافية", "factors": {}, "reasons": ["لا توجد بيانات كافية"], "is_early": False, "is_strong": False, "warnings": []}

    close = df["Close"].astype(float)
    high = df["High"].astype(float)
    low = df["Low"].astype(float)
    vol = df["Volume"].astype(float)
    price = float(close.iloc[-1])

    # 1) تباطؤ سرعة الهبوط
    try:
        # قارن ميل آخر 6 شموع vs 6 قبلها
        recent = close.tail(6)
        prior = close.tail(12).head(6)
        if len(recent) >= 3 and len(prior) >= 3:
            recent_slope = (recent.iloc[-1] - recent.iloc[0]) / len(recent)
            prior_slope = (prior.iloc[-1] - prior.iloc[0]) / len(prior) if len(prior) else 0
            # الهبوط يعني ميل سالب — تباطؤ يعني recent_slope أقل سلبية من prior_slope
            if prior_slope < -0.001 and recent_slope > prior_slope:
                diff = recent_slope - prior_slope
                # normalized by price
                pct = (diff / price * 100) if price else 0
                pts = min(15, max(5, int(pct * 200 + 5)))
                scores["slowdown"] = pts
                factors["slowdown"] = {"value": round(pct,3), "pts": pts, "desc": f"تباطؤ هبوط: الميل تحسن من {prior_slope:.4f} إلى {recent_slope:.4f}"}
                reasons.append(f"تباطؤ البيع (+{pts})")
            elif recent_slope >= -0.002:
                # شبه ثبات
                scores["slowdown"] = 8
                factors["slowdown"] = {"pts": 8, "desc": "شبه ثبات في آخر 6 شموع"}
                reasons.append("تباطؤ البيع: شبه ثبات (+8)")
            else:
                scores["slowdown"] = 0
                factors["slowdown"] = {"pts": 0, "desc": f"استمرار هبوط سريع (ميل {recent_slope:.4f})"}
        else:
            scores["slowdown"] = 0
            factors["slowdown"] = {"pts": 0, "desc": "بيانات غير كافية للميل"}
    except Exception as e:
        scores["slowdown"] = 0
        factors["slowdown"] = {"pts": 0, "desc": "خطأ حساب الميل"}

    # 2) انخفاض حجم البيع مقارنة بموجة الهبوط السابقة
    try:
        # حدد موجة الهبوط: من القمة إلى بداية القاعدة أو إلى الآن
        high_ts = day["High"].astype(float).idxmax()
        after = day.loc[high_ts:]
        if base_metrics_dict and base_metrics_dict.get("base_start"):
            try:
                start_ts = pd.Timestamp(base_metrics_dict["base_start"]).tz_convert(df.index.tz) if df.index.tz else pd.Timestamp(base_metrics_dict["base_start"])
                drop_phase = day.loc[high_ts:start_ts].iloc[:-1] if start_ts > high_ts else after.head(len(after)//2)
            except:
                drop_phase = after.head(max(1, len(after)//2))
        else:
            drop_phase = after.head(max(1, len(after)//2))
        # قارن متوسط حجم الهبوط vs حجم الثبات/الآخر
        if len(drop_phase) and base_win is not None and len(base_win):
            drop_vol = float(drop_phase["Volume"].astype(float).mean())
            base_vol = float(base_win["Volume"].astype(float).mean())
            ratio = base_vol / drop_vol if drop_vol > 0 else 1.0
            if ratio <= 0.85:
                pts = 12 if ratio <= 0.6 else 8
                scores["volume_dry"] = pts
                factors["volume_dry"] = {"ratio": round(ratio,2), "pts": pts, "desc": f"جفاف حجم: {ratio:.2f}× حجم الهبوط — امتصاص محتمل للبيع"}
                reasons.append(f"انخفاض حجم البيع ({ratio:.2f}×) (+{pts})")
            elif ratio <= 1.0:
                scores["volume_dry"] = 5
                factors["volume_dry"] = {"ratio": round(ratio,2), "pts": 5, "desc": f"حجم مستقر: {ratio:.2f}×"}
            else:
                scores["volume_dry"] = 0
                factors["volume_dry"] = {"ratio": round(ratio,2), "pts": 0, "desc": f"حجم مرتفع أثناء الثبات: {ratio:.2f}×"}
        else:
            # بديل: قارن آخر 6 vs قبلها
            r6 = float(vol.tail(6).mean())
            p6 = float(vol.tail(12).head(6).mean()) if len(vol) >= 12 else r6
            ratio2 = r6 / p6 if p6 else 1.0
            if ratio2 < 0.8:
                scores["volume_dry"] = 7
                factors["volume_dry"] = {"ratio": round(ratio2,2), "pts": 7, "desc": f"انخفاض حجم حديث: {ratio2:.2f}×"}
            else:
                scores["volume_dry"] = 0
                factors["volume_dry"] = {"ratio": round(ratio2,2) if ratio2 else None, "pts": 0, "desc": "حجم لم ينخفض"}
    except:
        scores["volume_dry"] = 0
        factors["volume_dry"] = {"pts": 0, "desc": "غير قابل للحساب"}

    # 3) انخفاض التقلب السلبي / تقلص مدى الشموع الهابطة
    try:
        atr_series = atr(df)
        atr_now = float(atr_series.iloc[-1]) if len(atr_series) and np.isfinite(atr_series.iloc[-1]) else None
        atr_prev = float(atr_series.iloc[-6]) if len(atr_series) >= 7 and np.isfinite(atr_series.iloc[-6]) else None
        if atr_now and atr_prev and atr_prev > 0:
            atr_change = (atr_now - atr_prev) / atr_prev * 100
            # انخفاض التقلب إيجابي في هذه المرحلة (تهدئة)
            if atr_change < -10:
                pts = 8
                scores["volatility_shrink"] = pts
                factors["volatility_shrink"] = {"change": round(atr_change,1), "pts": pts, "desc": f"تقلص تقلب ATR {atr_change:.1f}%"}
                reasons.append(f"تقلص التقلب ({atr_change:.1f}%) (+{pts})")
            elif atr_change < 0:
                pts = 4
                scores["volatility_shrink"] = pts
                factors["volatility_shrink"] = {"change": round(atr_change,1), "pts": pts, "desc": f"تهدئة طفيفة {atr_change:.1f}%"}
            else:
                scores["volatility_shrink"] = 0
                factors["volatility_shrink"] = {"change": round(atr_change,1), "pts": 0, "desc": f"تقلب لم ينخفض {atr_change:.1f}%"}
        else:
            # بديل: قياس مدى الشموع الهابطة
            down_bars = df.tail(6)[df.tail(6)["Close"].astype(float) < df.tail(6)["Open"].astype(float)]
            if len(down_bars) >= 2:
                ranges = (down_bars["High"].astype(float) - down_bars["Low"].astype(float)) / down_bars["Close"].astype(float) * 100
                avg_range_recent = float(ranges.tail(3).mean()) if len(ranges) >=3 else float(ranges.mean())
                avg_range_prior = float(ranges.head(3).mean()) if len(ranges) >=3 else avg_range_recent
                if avg_range_recent < avg_range_prior:
                    scores["volatility_shrink"] = 5
                    factors["volatility_shrink"] = {"pts": 5, "desc": f"تقلص مدى الشموع الهابطة {avg_range_prior:.2f}%→{avg_range_recent:.2f}%"}
                else:
                    scores["volatility_shrink"] = 0
                    factors["volatility_shrink"] = {"pts": 0, "desc": "مدى الشموع لم يتقلص"}
            else:
                scores["volatility_shrink"] = 2
                factors["volatility_shrink"] = {"pts": 2, "desc": "لا شموع هابطة كثيرة — تهدئة"}
    except:
        scores["volatility_shrink"] = 0
        factors["volatility_shrink"] = {"pts": 0, "desc": "خطأ حساب التقلب"}

    # 4) شموع بذيول سفلية مع إغلاق أفضل
    try:
        tail = df.tail(6)
        wick_count = 0
        for _, row in tail.iterrows():
            h,l,o,c = float(row["High"]), float(row["Low"]), float(row["Open"]), float(row["Close"])
            rng = h - l
            if rng <= 0:
                continue
            lower_wick = min(o,c) - l
            body = abs(c - o)
            # ذيل سفلي > 40% من المدى وإغلاق في النصف العلوي
            close_pos = (c - l) / rng if rng else 0
            if lower_wick / rng > 0.35 and close_pos > 0.5:
                wick_count += 1
        if wick_count >= 2:
            pts = 10
            scores["wicks"] = pts
            factors["wicks"] = {"count": wick_count, "pts": pts, "desc": f"{wick_count} شموع بذيول سفلية مع إغلاق محسن — رفض سعري محتمل"}
            reasons.append(f"ذيول سفلية ({wick_count}) (+{pts})")
        elif wick_count == 1:
            pts = 5
            scores["wicks"] = pts
            factors["wicks"] = {"count": wick_count, "pts": pts, "desc": "ذيل سفلي واحد"}
        else:
            scores["wicks"] = 0
            factors["wicks"] = {"count": 0, "pts": 0, "desc": "لا ذيول سفلية واضحة"}
    except:
        scores["wicks"] = 0
        factors["wicks"] = {"pts": 0, "desc": "خطأ حساب الذيول"}

    # 5) توقف قيعان أدنى / بداية قيعان أعلى
    try:
        lows = df["Low"].astype(float).tail(10).to_numpy()
        if len(lows) >= 5:
            # check last 3 lows vs prior 3
            last3_min = float(np.min(lows[-3:]))
            prev3_min = float(np.min(lows[-6:-3])) if len(lows) >=6 else float(np.min(lows[:-3]))
            last3_trend = lows[-1] - lows[-3]
            if last3_min >= prev3_min - 0.001 * price:  # توقف هبوط
                if last3_trend > 0:
                    pts = 12
                    desc = f"قيعان أعلى: {prev3_min:.4f}→{last3_min:.4f} واتجاه صاعد"
                    reasons.append(f"قيعان أعلى (+{pts})")
                else:
                    pts = 7
                    desc = f"توقف قيعان أدنى: استقرار عند {last3_min:.4f}"
                    reasons.append(f"استقرار قيعان (+{pts})")
                scores["higher_lows"] = pts
                factors["higher_lows"] = {"pts": pts, "desc": desc}
            else:
                scores["higher_lows"] = 0
                factors["higher_lows"] = {"pts": 0, "desc": f"قيعان أدنى مستمرة {prev3_min:.4f}→{last3_min:.4f}"}
        else:
            scores["higher_lows"] = 0
            factors["higher_lows"] = {"pts": 0, "desc": "بيانات غير كافية"}
    except:
        scores["higher_lows"] = 0
        factors["higher_lows"] = {"pts": 0, "desc": "خطأ"}

    # 6) ارتفاع الحجم مع تحسن السعر
    try:
        # up volume vs down volume in last 10
        recent = df.tail(10)
        up_vol = float(recent[recent["Close"].astype(float) > recent["Open"].astype(float)]["Volume"].astype(float).sum())
        down_vol = float(recent[recent["Close"].astype(float) < recent["Open"].astype(float)]["Volume"].astype(float).sum())
        total = up_vol + down_vol
        if total > 0:
            bal = (up_vol - down_vol) / total
            if bal > 0.15 and close.iloc[-1] > close.iloc[-3]:
                pts = 10
                scores["volume_price"] = pts
                factors["volume_price"] = {"balance": round(bal,2), "pts": pts, "desc": f"حجم شرائي صافٍ {bal:.0%} مع تحسن سعر"}
                reasons.append(f"حجم مع تحسن سعر (+{pts})")
            elif bal > 0:
                pts = 5
                scores["volume_price"] = pts
                factors["volume_price"] = {"balance": round(bal,2), "pts": pts, "desc": f"ميزان حجم إيجابي {bal:.0%}"}
            else:
                scores["volume_price"] = 0
                factors["volume_price"] = {"balance": round(bal,2), "pts": 0, "desc": f"ميزان حجم سلبي {bal:.0%}"}
        else:
            scores["volume_price"] = 0
            factors["volume_price"] = {"pts": 0, "desc": "لا تباين حجمي"}
    except:
        scores["volume_price"] = 0
        factors["volume_price"] = {"pts": 0, "desc": "خطأ"}

    # 7) تحسن RSI من مستويات منخفضة
    try:
        r = rsi(close, C.RSI_PERIOD)
        if len(r.dropna()) >= C.RSI_LOOK:
            r_now = float(r.iloc[-1]) if np.isfinite(r.iloc[-1]) else None
            r_min = float(r.iloc[-C.RSI_LOOK:].min()) if np.isfinite(r.iloc[-C.RSI_LOOK:].min()) else None
            if r_now is not None and r_min is not None:
                imp = r_now - r_min
                if imp >= 5 and r_now >= 30 and r_min <= 35:
                    pts = 8
                    scores["rsi_recovery"] = pts
                    factors["rsi_recovery"] = {"rsi": round(r_now,1), "rsi_min": round(r_min,1), "imp": round(imp,1), "pts": pts, "desc": f"RSI تحسن {r_min:.1f}→{r_now:.1f} (+{imp:.1f})"}
                    reasons.append(f"تحسن RSI (+{pts})")
                elif imp >= 3:
                    pts = 4
                    scores["rsi_recovery"] = pts
                    factors["rsi_recovery"] = {"r_now": round(r_now,1), "imp": round(imp,1), "pts": pts, "desc": f"تحسن RSI طفيف +{imp:.1f}"}
                else:
                    scores["rsi_recovery"] = 0
                    factors["rsi_recovery"] = {"pts": 0, "desc": f"RSI لم يتحسن {r_min:.1f}→{r_now:.1f}"}
            else:
                scores["rsi_recovery"] = 0
                factors["rsi_recovery"] = {"pts": 0, "desc": "RSI غير متاح"}
        else:
            scores["rsi_recovery"] = 0
            factors["rsi_recovery"] = {"pts": 0, "desc": "نافذة RSI غير كافية"}
    except:
        scores["rsi_recovery"] = 0
        factors["rsi_recovery"] = {"pts": 0, "desc": "خطأ RSI"}

    # 8) تحسن OBV أو توقف تدهوره
    try:
        o = obv(close, vol)
        if len(o) >= C.OBV_LOOK + 2:
            o_now = float(o.iloc[-1])
            o_prev = float(o.iloc[-C.OBV_LOOK])
            slope_recent = float(o.iloc[-1] - o.iloc[-3])
            if o_now > o_prev:
                pts = 7
                scores["obv_improve"] = pts
                factors["obv_improve"] = {"pts": pts, "desc": f"OBV صاعد {o_prev:.0f}→{o_now:.0f}"}
                reasons.append(f"تحسن OBV (+{pts})")
            elif slope_recent >= 0:
                pts = 3
                scores["obv_improve"] = pts
                factors["obv_improve"] = {"pts": pts, "desc": "OBV توقف تدهوره (ميل ≥0)"}
            else:
                scores["obv_improve"] = 0
                factors["obv_improve"] = {"pts": 0, "desc": "OBV ما زال هابطًا"}
        else:
            scores["obv_improve"] = 0
            factors["obv_improve"] = {"pts": 0, "desc": "بيانات OBV غير كافية"}
    except:
        scores["obv_improve"] = 0
        factors["obv_improve"] = {"pts": 0, "desc": "خطأ OBV"}

    # 9) تحسن CMF
    try:
        cs = cmf(df, C.CMF_PERIOD)
        if len(cs.dropna()) >= 3:
            c_now = float(cs.iloc[-1]) if np.isfinite(cs.iloc[-1]) else None
            c_prev = float(cs.iloc[-3]) if np.isfinite(cs.iloc[-3]) else None
            if c_now is not None and c_prev is not None:
                if c_now > c_prev and c_now > -0.05:
                    pts = 7
                    scores["cmf_improve"] = pts
                    factors["cmf_improve"] = {"cmf": round(c_now,3), "pts": pts, "desc": f"CMF يتحسن {c_prev:.3f}→{c_now:.3f} — تدفق سيولة محتمل"}
                    reasons.append(f"تحسن CMF (+{pts})")
                elif c_now > c_prev:
                    pts = 4
                    scores["cmf_improve"] = pts
                    factors["cmf_improve"] = {"pts": pts, "desc": f"CMF يتحسن هامشيًا {c_prev:.3f}→{c_now:.3f}"}
                else:
                    scores["cmf_improve"] = 0
                    factors["cmf_improve"] = {"pts": 0, "desc": f"CMF لم يتحسن {c_now:.3f}"}
            else:
                scores["cmf_improve"] = 0
                factors["cmf_improve"] = {"pts": 0, "desc": "CMF غير متاح"}
        else:
            scores["cmf_improve"] = 0
            factors["cmf_improve"] = {"pts": 0, "desc": "نافذة CMF غير كافية"}
    except:
        scores["cmf_improve"] = 0
        factors["cmf_improve"] = {"pts": 0, "desc": "خطأ CMF"}

    # 10) تحسن MACD كعامل مساعد
    try:
        ml, ms, mh = macd(close)
        if len(mh.dropna()) >= 3:
            mh_now = float(mh.iloc[-1]) if np.isfinite(mh.iloc[-1]) else 0
            mh_prev = float(mh.iloc[-3]) if np.isfinite(mh.iloc[-3]) else 0
            cross = bool(((ml.shift(1) <= ms.shift(1)) & (ml > ms)).iloc[-3:].any())
            if cross:
                pts = 4
                scores["macd_helper"] = pts
                factors["macd_helper"] = {"pts": pts, "desc": "MACD تقاطع إيجابي (مساعد)"}
                reasons.append(f"MACD تقاطع (+{pts})")
            elif mh_now > mh_prev and mh_now > -0.01:
                pts = 2
                scores["macd_helper"] = pts
                factors["macd_helper"] = {"pts": pts, "desc": f"MACD هيستوجرام يتحسن {mh_prev:.4f}→{mh_now:.4f}"}
            else:
                scores["macd_helper"] = 0
                factors["macd_helper"] = {"pts": 0, "desc": "MACD لم يتحسن"}
        else:
            scores["macd_helper"] = 0
            factors["macd_helper"] = {"pts": 0, "desc": "MACD غير كاف"}
    except:
        scores["macd_helper"] = 0
        factors["macd_helper"] = {"pts": 0, "desc": "خطأ MACD"}

    # 11) المسافة إلى VWAP
    try:
        if vwap_value and price:
            dist = (price - vwap_value) / vwap_value * 100
            # قرب VWAP إيجابي للارتداد السريع — لكن إن كان بعيدًا جدًا تحته فمخاطرة
            if -5 <= dist <= 5:
                pts = 3
                scores["vwap_distance"] = pts
                factors["vwap_distance"] = {"dist": round(dist,1), "pts": pts, "desc": f"قريب من VWAP {dist:.1f}% — مقاومة قريبة للاختبار"}
            elif dist > 0:
                pts = 2
                scores["vwap_distance"] = pts
                factors["vwap_distance"] = {"dist": round(dist,1), "pts": pts, "desc": f"فوق VWAP {dist:.1f}% — دعم"}
            elif dist < -15:
                pts = 0
                scores["vwap_distance"] = pts
                factors["vwap_distance"] = {"dist": round(dist,1), "pts": pts, "desc": f"بعيد تحت VWAP {dist:.1f}% — مقاومة بعيدة"}
            else:
                scores["vwap_distance"] = 1
                factors["vwap_distance"] = {"dist": round(dist,1), "pts": 1, "desc": f"تحت VWAP {dist:.1f}%"}
        else:
            scores["vwap_distance"] = 0
            factors["vwap_distance"] = {"pts": 0, "desc": "VWAP غير متاح"}
    except:
        scores["vwap_distance"] = 0
        factors["vwap_distance"] = {"pts": 0, "desc": "خطأ VWAP"}

    # 12) المسافة إلى مقاومة قريبة (نستخدم قمة اليوم أو base_high)
    try:
        resistance = None
        if base_metrics_dict and base_metrics_dict.get("base_high"):
            resistance = float(base_metrics_dict["base_high"])
        else:
            resistance = float(day["High"].max()) if len(day) else None
        if resistance and price:
            room = (resistance - price) / price * 100
            if room >= 10:
                pts = 4
                scores["resistance_room"] = pts
                factors["resistance_room"] = {"room": round(room,1), "pts": pts, "desc": f"مساحة حتى المقاومة {room:.1f}% — مجال ارتداد جيد"}
            elif room >= 5:
                pts = 2
                scores["resistance_room"] = pts
                factors["resistance_room"] = {"room": round(room,1), "pts": pts, "desc": f"مساحة متوسطة {room:.1f}%"}
            elif room < 2:
                pts = -3  # عقوبة صغيرة قرب المقاومة
                scores["resistance_room"] = pts
                factors["resistance_room"] = {"room": round(room,1), "pts": pts, "desc": f"قرب مقاومة {room:.1f}% — مساحة محدودة"}
            else:
                scores["resistance_room"] = 0
                factors["resistance_room"] = {"room": round(room,1), "pts": 0, "desc": f"مساحة {room:.1f}%"}
        else:
            scores["resistance_room"] = 0
            factors["resistance_room"] = {"pts": 0, "desc": "مقاومة غير معروفة"}
    except:
        scores["resistance_room"] = 0
        factors["resistance_room"] = {"pts": 0, "desc": "خطأ مقاومة"}

    # 13) موقع السعر من قاع الموجة والقاع المرجعي
    try:
        post_peak_low = base_metrics_dict.get("post_peak_low") if base_metrics_dict else None
        if post_peak_low is None:
            post_peak_low = float(day.loc[day["High"].astype(float).idxmax():, "Low"].astype(float).min()) if len(day) else None
        if post_peak_low and price:
            dist_low = (price / post_peak_low - 1) * 100
            if 0 <= dist_low <= 5:
                pts = 3
                scores["position"] = pts
                factors["position"] = {"dist": round(dist_low,1), "pts": pts, "desc": f"قرب قاع الموجة {dist_low:.1f}% — قاعدة محتملة"}
            elif dist_low <= 10:
                pts = 1
                scores["position"] = pts
                factors["position"] = {"dist": round(dist_low,1), "pts": pts, "desc": f"فوق القاع {dist_low:.1f}%"}
            else:
                scores["position"] = 0
                factors["position"] = {"dist": round(dist_low,1), "pts": 0, "desc": f"بعيد عن القاع {dist_low:.1f}%"}
        else:
            scores["position"] = 0
            factors["position"] = {"pts": 0, "desc": "قاع غير معروف"}
    except:
        scores["position"] = 0
        factors["position"] = {"pts": 0, "desc": "خطأ موقع"}

    # 14) قيمة التداول بالدولار والسيولة الفعلية
    try:
        dollar_vol = price * float(vol.iloc[-1]) if len(vol) else 0
        avg_dollar = float((close.tail(20) * vol.tail(20)).mean()) if len(close) >= 20 else dollar_vol
        # سيولة ضعيفة = خطر
        if dollar_vol < 200_000:
            # تحذير وليس استبعاد — سجل كعامل خطر
            scores["dollar_liquidity"] = -5
            factors["dollar_liquidity"] = {"dollar": int(dollar_vol), "pts": -5, "desc": f"سيولة ضعيفة ${dollar_vol:,.0f} — خطر تنفيذ"}
        elif dollar_vol > 1_000_000:
            pts = 3
            scores["dollar_liquidity"] = pts
            factors["dollar_liquidity"] = {"dollar": int(dollar_vol), "pts": pts, "desc": f"سيولة جيدة ${dollar_vol:,.0f}"}
        else:
            scores["dollar_liquidity"] = 0
            factors["dollar_liquidity"] = {"dollar": int(dollar_vol), "pts": 0, "desc": f"سيولة متوسطة ${dollar_vol:,.0f}"}
    except:
        scores["dollar_liquidity"] = 0
        factors["dollar_liquidity"] = {"pts": 0, "desc": "خطأ سيولة"}

    # تجميع الدرجة
    total = sum(max(0, v) for v in scores.values())
    # عقوبات سلبية منفصلة
    penalties = 0
    warnings = []
    # كسر القاع دون استعادة — يفحص عبر sweep_state إن وُجد
    # هنا نكتشف بشكل مستقل: إن كان السعر تحت القاع المرجعي بلا ذيول
    try:
        if base_metrics_dict and base_metrics_dict.get("base_low"):
            base_low = float(base_metrics_dict["base_low"])
            if price < base_low * 0.95:  # كسر >5% بدون استعادة واضحة
                # تحقق إن كان هناك ذيل استعادة — إن لم يوجد، عقوبة
                last_low = float(low.iloc[-1])
                last_close = float(close.iloc[-1])
                if last_close < base_low and last_low < base_low:
                    penalties += 8
                    warnings.append(f"كسر القاع دون استعادة واضحة ({(price/base_low-1)*100:.1f}%)")
    except:
        pass

    # استمرار قيعان أدنى مع حجم مرتفع — عقوبة
    try:
        if scores.get("higher_lows", 0) == 0 and scores.get("volume_dry", 0) == 0:
            # لم يحدث تباطؤ ولا جفاف — بيع مستمر
            recent_vol_avg = float(vol.tail(6).mean())
            if recent_vol_avg > float(vol.tail(20).mean()) * 1.2 if len(vol) >=20 else 0:
                penalties += 5
                warnings.append("قيعان أدنى مع حجم مرتفع — ضغط بيع مستمر")
    except:
        pass

    # قرب مقاومة قوية — إن كانت النقاط سالبة فهي عقوبة بالفعل
    # ضعف سيولة — تحذير
    if scores.get("dollar_liquidity", 0) < 0:
        warnings.append(factors["dollar_liquidity"]["desc"])

    # اقتراب مقاومة
    if scores.get("resistance_room", 0) < 0:
        warnings.append(factors["resistance_room"]["desc"])

    raw_score = total  # قبل العقوبات
    adjusted = max(0, min(100, raw_score - penalties))

    # تطبيع إلى 0-100 بناءً على الأوزان القصوى (حوالي 100)
    # raw_score بالفعل مجموع نقاط بحد أقصى ~100
    final_score = int(round(adjusted))

    label = "بيانات غير كاملة"
    is_early = False
    is_strong = False
    if final_score >= C.EARLY_STRONG_THRESHOLD:
        label = "بوادر ارتداد قوية"
        is_early = True
        is_strong = True
    elif final_score >= C.EARLY_THRESHOLD:
        label = "بوادر ارتداد"
        is_early = True
    elif final_score >= 35:
        label = "يبني قاعدة"
    elif final_score >= 15:
        label = "مراقبة"
    else:
        label = "ضغط بيع مستمر"

    return {
        "score": final_score,
        "raw_score": raw_score,
        "label": label,
        "is_early": is_early,
        "is_strong": is_strong,
        "factors": factors,
        "factor_scores": scores,
        "reasons": reasons,
        "warnings": warnings,
        "penalties": penalties,
        "max_possible": sum(C.EARLY_WEIGHTS.values()),
    }
