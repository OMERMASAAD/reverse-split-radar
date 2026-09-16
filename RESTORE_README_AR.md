# استرجاع ملفات reverse-split-radar

الملفات هنا **ليست إعادة كتابة** — هي النسخ الأصلية المستخرجة من تاريخ Git
قبل كوميتات الحذف الأخيرة. كلها تمر من `python -m py_compile` بنجاح.

---

## مهم: يوجد جيلان في المستودع

| | الجيل القديم | الجيل الحالي |
|---|---|---|
| السكربت | `strategy_scanner.py` | `daily_signal_scanner.py` |
| ملف البيانات | `dashboard_data.json` | `daily_signals.json` |
| الـ workflow | `scan.yml` (محذوف) | `daily_monitor.yml` (موجود) |
| الحالة | نمط Score/Core/Rating | Paper Signals — يطابق `strategy_spec_ar.md` |

`daily_monitor.yml` الموجود حالياً في المستودع مبني على **الجيل الحالي**،
و`index.html` المُسترجَع هنا يقرأ `daily_signals.json` +
`research/statistical_analysis.json` (الأخير موجود أصلاً ولم يُحذف).

لذلك: ارفع `repo-root/` فقط. مجلد `legacy-optional/` للأرشيف.

---

## repo-root/ — ارفعها إلى جذر المستودع

**التشغيل الأساسي**
- `requirements.txt` — yfinance, pandas, numpy, requests, pandas-ta-classic, scipy
- `reverse_split_source.py` — يجلب كون التجزئات العكسية (يحتاج `BUSINESSQUANT_API_KEY`)
- `daily_signal_scanner.py` — يطبّق شروط المراقبة والانفجار، يكتب `daily_signals.json`

**الواجهة**
- `index.html` — الداشبورد الكامل (يستبدل الصفحة الثابتة الحالية)
- `manifest.json` — يربط الأيقونات الثلاث الموجودة في المستودع

**بيانات البذرة** (حتى لا تُفتح الصفحة فارغة قبل أول تشغيل)
- `reverse_split_candidates.json` — ٣٦٤ مرشحاً
- `daily_signals.json` — آخر مسح: ٩ تحت المراقبة، ٠ إشارة دخول
- `paper_signal_history.json` — سجل فارغ `[]`

**محركات البحث** (خطوات التحقق في الـ workflows تعمل `assert` على وجودها)
- `research_engine.py`, `phase3_engine.py`, `phase4_engine.py` ← يستدعيها `daily_monitor.yml`
- `phase2_engine.py` ← يستدعيه `phase2_discovery.yml`
- `phase5_engine.py` ← يستدعيه `phase5_blind_validation.yml`

---

## خطوات الرفع

1. ارفع محتويات `repo-root/` إلى جذر المستودع (استبدل `index.html` الحالي).
2. تأكد أن `BUSINESSQUANT_API_KEY` معرّف في
   Settings ← Secrets and variables ← Actions.
3. فعّل GitHub Pages من Settings ← Pages ← Branch: `main` / `root`.
4. شغّل `Daily Paper Signal Monitor` يدوياً من تبويب Actions
   (`workflow_dispatch`) وتابع الخطوات.

## ماذا تتوقع

الصفحة ستعرض ٩ أسهم تحت المراقبة و**صفر إشارة دخول** — هذا هو الوضع
الصحيح لا خطأ. `research/phase5_report.json` يسجّل
`INSUFFICIENT NEW OOS DATA` و`blind_rows: 0`، والخطوة التالية المسجّلة
هي مرحلة جمع بيانات. الإشارات تظهر فقط عند تحقق الشرطين ٨ و٩ معاً.

## ملاحظة على `reverse_split_source.py`

يعتمد على BusinessQuant كمصدر وحيد لكون التجزئات. إن كان الاشتراك منتهياً
ستفشل الخطوة الأولى في الثلاث workflows. هذه أول نقطة تتحقق منها إن فشل التشغيل.
