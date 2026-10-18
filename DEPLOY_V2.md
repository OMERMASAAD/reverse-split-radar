# دليل النشر PANIC SNIPER V2 على GitHub Pages

## المتطلبات

- Python 3.11+ · pandas, numpy, yfinance
- GitHub repo: `OMERMASAAD/reverse-split-radar`
- GitHub Pages يقرأ من فرع `main` (الجذر)

## 1) نشر الكود

```bash
git checkout arena/d14ee810-reverse-split-radar
git add sniper/config.py sniper/core.py sniper/levels.py sniper/early.py sniper/sweep.py sniper/liquidity.py sniper/runtime.py sniper/tracker.py sniper/risk.py index.html tests/test_sniper.py tests/test_v2.py docs/PERFORMANCE_V2.md tools/verify_dashboard.mjs
git commit -m "⚡ V2: EARLY REVERSAL + SWEEP STATES + LIQUIDITY SCORE + MFE/MAE fix"
git push origin arena/d14ee810-reverse-split-radar
# افتح PR إلى main عبر: gh pr create --fill
```

## 2) GitHub Actions — المسح كل 15 دقيقة

الملف: `.github/workflows/panic_sniper.yml`

```yaml
schedule:
  - cron: "*/15 8-21 * * 1-5"  # 08:00–21:45 UTC = 04:00–17:45 ET
```

- لا يعتمد على بقاء المتصفح مفتوحًا — يعمل على GitHub Actions فقط.
- الأخطاء لا تُخفى: كل مسح يختم `scan_log` مع `ok`, `skipped`, `error`, `duration_s`.
- `coverage_pct` و `frames/master` ظاهرة في الداشبورد وداخل `panic_data.json/diagnostics`.
- إعادة المحاولة: `git pull --rebase && git push` مع 3 محاولات.
- حدود الطلبات: `DOWNLOAD_RETRIES=2` + `sleep 5s`.

### التحقق من أن المسح يعمل

1. افتح تبويب **التشغيل** في الداشبورد — يعرض `scan_log` و `uptime`.
2. افتح `https://raw.githubusercontent.com/OMERMASAAD/reverse-split-radar/main/panic_data.json` وتحقق من `updated_at` يتغير كل 15 دقيقة.
3. في Actions → Panic Sniper (15m) → شغّل يدويًا `workflow_dispatch`.

### الأسرار المطلوبة

- **لا مفاتيح API سرية في JS** — Yahoo Finance بلا مفتاح.
- اختياري: `Settings → Variables → SEC_CONTACT` = بريدك لـ SEC EDGAR (مطلوب من SEC).
- اختياريًا `FLOAT_MODE=auto` (افتراضي).

## 3) تحديث الكون (Universe)

```yaml
# .github/workflows/universe_build.yml
schedule:
  - cron: "20 12 * * 1-5" # 08:20 ET يوميًا
```

- يبني `universe.json` (سعر $0.5-$10 · Float <5M · حجم ≥100k).
- يدوم حتى 5 أيام؛ المسح يعيد بناءه تلقائيًا إذا كان stale.

## 4) العرض التجريبي المحلي

```bash
pip install --break-system-packages -r requirements.txt
python tools/make_demo.py   # يولد panic_data.json عبر المحرك نفسه
python -m http.server 8000
# افتح http://localhost:8000
```

## 5) مراجعة أول إشارات ورقية بعد النشر

1. انتظر أول مسح ناجح (تحقق من `last_scan.ok`).
2. في تبويب **الأداء** راجع `panic_stats.json`: `open` و `closed`.
3. تفحص `MFE/mfe_pct` و `MAE/mae_pct` — يجب أن تكون من سعر الإشارة فقط.
4. تحقق من `ambiguous: true` للحالات الملتبسة.
5. قارن `by_drop`, `by_liquidity`, `by_sweep` في ملخص الأداء.

## 6) الاستعادة من أخطاء البيانات

- البيانات القديمة تُعلم كـ `stale` (last_bar >60m قديم) ولا تُعرض كـ لحظية.
- انقطاع التحميل يُسجل في `scan_log` مع `skipped="low_coverage"` ويحافظ على `items` السابقة.
- لا تُعرض بيانات قديمة على أنها لحظية — كل سعر مع `last_bar` و `last_update`.

## 7) تغيير الأوزان

كل الأرقام في `sniper/config.py` (قسم EARLY/MTF/RUNUP). غيّرها وأعد تشغيل الاختبارات:

```bash
python tests/test_sniper.py && python tests/test_v2.py
```

## الأمان

- لا تضع مفاتيح في `index.html` أو JSON المنشور.
- Yahoo Finance قد يتأخر 15 دقيقة — يُعرض كـ `stale`.
- الفلوت من Yahoo + SEC — يظهر مصدره وتاريخه في كل بطاقة.

## الدعم

افتح Issue في GitHub مع لقطة من `panic_data.json/diagnostics` و `scan_log`.
