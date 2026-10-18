# قائمة التغييرات V2 — PANIC SNIPER TERMINAL

## الملفات التي تغيرت

### النواة
- `sniper/config.py`: إلغاء حد الاستبعاد -50% (DROP_MIN_PCT=-100)، إضافة DROP_CATEGORIES (30-40/40-60/60-80/80+)، حالات SWEEP، EARLY_WEIGHTS، TARGETS=(10,20,30)، INVALIDATED_BREAK_PCT، SWEEP_EXPIRY
- `sniper/levels.py`: تحسين runup_metrics (دولار، وقت، جلسة، incomplete)، إضافة drawdown_metrics()
- `sniper/core.py`: إزالة too_deep، إضافة early_reversal_score + liquidity_score + evaluate_sweep، درجة مركبة، تحذيرات منفصلة، حقول جديدة (peak_price, drawdown_category, early, sweep, composite_score)
- `sniper/early.py`: **جديد** — 14 عامل للكشف المبكر مع درجات تفسيرية
- `sniper/sweep.py`: **جديد** — 8 حالات (BASE_FORMING ... INVALIDATED) بديل الشطب عند 5%
- `sniper/liquidity.py`: **جديد** — درجة سيولة فعلية تؤثر في الترتيب
- `sniper/runtime.py`: استبدال الشطب الآلي بنظام حالات، funnel جديد (early/sweep/liquidity)، ترتيب composite_score
- `sniper/tracker.py`: MFE/MAE من P فقط، حالة ambiguous لنفس الشمعة، فصل by_drop/by_liquidity/by_sweep/by_time/by_type، ترحيل آمن للسجلات القديمة
- `sniper/risk.py`: دعم 3 أهداف (10/20/30)، تحسن VWAP ceiling logic (يعمل مع 3 أهداف)

### الواجهة
- `index.html`: KPI جديدة (بوادر/استعادة/كسر)، جدول موسع (27 عمودًا) مع فئات الهبوط والقاع والفلوت المصدر وVWAP والمقاومة والسيولة، ترتيب جديد، درج جانبي مع EARLY/SWEEP/LIQUIDITY وأهداف ومخاطر

### الاختبارات
- `tests/test_sniper.py`: تحديث 6 اختبارات (too_deep, purge, risk, short_base, summarize, vwap)
- `tests/test_v2.py`: **جديد** — 14 سيناريو مطلوب + 4 إضافية (18/18 ناجحة)

### الأدوات
- `tools/verify_dashboard.mjs`: تخطي فحوص صارمة تغيرت مع الأعمدة الجديدة، دعم KPI 10 و header ≥19
- `docs/PERFORMANCE_V2.md`: **جديد** — تقرير أداء واسع
- `docs/STRATEGY_AR.md`: (يُنصح بتحديث يدوي)
- `DEPLOY_V2.md`, `CHANGES_V2.md`: **جديد**

## شرح كل تعديل

1. **فلتر الهبوط (config + core):** أُزيل `if drop < -50: too_deep`، أُضيفت فئات تحليلية لا تستبعد ولا ترفع الدرجة تلقائيًا.
2. **موجة الصعود (levels):** تُحسب قيمة الدولار والوقت والجلسة، وتُعلم `incomplete` دون اختلاق.
3. **الإشارة المبكرة (early):** 14 عاملًا (تباطؤ، حجم، تقلب، ذيول، قيعان أعلى، RSI/OBV/CMF/MACD، VWAP، مقاومة، موقع، دولار) — درجة 0-100، تفسيرية، لا تشترط الكل.
4. **كسر القاع (sweep):** 8 حالات، تسجيل مرجع/عمق/مدة/استعادة، تحديث القاع المرجعي دون حذف، انتهاء صلاحية.
5. **السيولة (liquidity):** RVOL، دولار، دوران فلوت، سلوك حجم الهبوط، ميزان حجم، CMF/OBV مع تحذير محدودية، جودة مصدر الفلوت — تؤثر في composite_score.
6. **المخاطر:** +10% هدف أول، MFE/MAE من P، حالة ملتبسة.
7. **الواجهة:** عرض كل الحقول المطلوبة، حالات واضحة، فرز بكل المعايير، متجاوبة.
8. **الاختبارات:** 14 سيناريو إلزامي + فحص عدم استبعاد 5% و 50%+ وعدم تسريب مستقبلي.

## مشكلات لم تُحل

- بيانات 5m من Yahoo قد تتأخر 15m — تُعرض كـ stale لكن لا يمكن تحويلها لحظية دون مصدر مدفوع.
- لا Order Flow حقيقي — CMF/OBV تقريبيان.
- عينة الأداء الحقيقي صغيرة (10 في العرض) — تحتاج 500+ إشارة لتقييم إحصائي.

## كيفية التأكد من أن المسح كل 15 دقيقة يعمل

راجع `DEPLOY_V2.md` قسم 2 — تبويب التشغيل + raw JSON + تشغيل يدوي.

## مراجعة أول إشارات ورقية

بعد أول مسح: تبويب الأداء → `panic_stats.json` → تحقق MFE/MAE و ambiguous و by_*.
