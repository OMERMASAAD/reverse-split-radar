# Reverse Split Explosion Radar

هذا المستودع يضم **بحثًا تاريخيًا إحصائيًا** ولوحة GitHub Pages للمراقبة التجريبية فقط. لا ينفذ أوامر، ولا يتصل بمنصة تداول، ولا يقدم توصية استثمارية.

## التسلسل البحثي

Reverse Splits خلال 180 يومًا تقويميًا → تعريف أهداف +20/+50/+70/+100/+200 → مقارنة حالات +70% مع نوافذ غير ناجحة → RSI14 واتجاهه → بنية السعر والدعم والحجم وMACD والمتوسطات → اختبار التركيبات → Backtest دخول الشمعة التالية → فصل زمني Train/OOS.

## مخرجات البحث

- `research/statistical_analysis.json`: العينة، تغطية البيانات، عتبات الحركة، RSI، الإحصاءات، التركيبات، والـBacktest.
- `research/research_report.md`: تقرير قابل للقراءة والنقاش.
- `research/strategy_backtest.json`: نتائج الأهداف والوقف والفصل خارج العينة.
- `research/enriched_cases.json`: الحالات مع لقطات RSI السابقة للحدث حيث تتوفر بيانات OHLCV.
- `research/raw_historical_cases.json`: نسخة مصدرية من الحالات التاريخية المستخدمة.
- `research_engine.py`: محرك البحث القابل لإعادة التشغيل.

## تعريف الحالة

الحالة الناجحة هي نافذة وصلت إلى +70% في البيانات التاريخية. هذا تعريف حدث بحثي، وليس وعدًا بأن دخولًا قابلًا للتنفيذ كان ممكنًا. ميزات التنبؤ يجب أن تكون قبل الحدث، والـBacktest يستخدم افتتاح الجلسة التالية مع وقف -20% وأهداف متعددة، ويعرض النتيجة خارج العينة.

## حدود البيانات

لا تتوفر Float وShort Interest تاريخيًا بشكل موثوق في هذه النسخة، لذلك لا تُستخدم القيم الحالية كبديل. كما أن بعض الرموز لا تتوفر لها OHLCV في Yahoo Finance. كل نقص مسجل في تغطية البيانات ولا يتم تعويضه بقيم مختلقة.

## Paper Signals اليومية

`daily_signal_scanner.py` و`daily_signals.json` يمثلان طبقة المراقبة الحالية. نافذة التشغيل من أول جلسة بعد التقسيم وحتى 40 جلسة، لكنها ليست نتيجة نهائية مثبتة؛ يجب أن تعتمد الشروط النهائية على نتائج OOS وتراكم Paper Signals جديدة.

## التشغيل

```bash
python research_engine.py
python daily_signal_scanner.py
```

ويشغّل `.github/workflows/daily_monitor.yml` تحديث الكون، الماسح اليومي، ومحرك البحث في GitHub Actions. جميع النتائج قابلة للمراجعة داخل مجلد `research/`.

## Phase 2: First Explosion Start Discovery

تمت إضافة مرحلة اكتشاف مستقلة لاختيار نقطة بداية الحركة قبل معرفة أن السهم سيصل إلى +70%. تختبر المرحلة خمس تعريفات مستقلة: التعافي +10% من القاع، التعافي +20% من القاع، +20% خلال 1–3 جلسات، توسع سريع للسعر والحجم، وكسر قاعدة/تماسك.

هذه المرحلة **Discovery Only**. لا تختار Entry أو Stop أو Take Profit، ولا تنشئ Research Score، ولا تشغل OOS Strategy. تقيس النتائج المستقبلية من تاريخ الإشارة فقط، وتحفظ RSI عند S وS-1 وS-2 وS-3 وS-4 وS-5 وS-6 وS-7 وS-10 وS-15 وS-20.

المخرجات هي `research/research_phase2_report.md` و`explosion_start_cases.csv` و`explosion_start_cases.json` و`rsi_timing_analysis.csv` و`rsi_distribution.csv` و`feature_timing_analysis.csv` و`success_vs_failure.csv` و`hypotheses_phase2.json` و`oos_results.json`. يشغّلها Workflow مستقل باسم `Phase 2 Explosion Start Discovery` يدويًا أو مرة شهريًا.
