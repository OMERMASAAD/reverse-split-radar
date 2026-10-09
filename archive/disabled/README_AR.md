# الأرشيف — ملفات النظام القديم (معطَّلة)

هذه الملفات كانت تشغّل **رادار التجزئة العكسية اليومي** (V1.0).
عُطّلت بالكامل عند اعتماد **رادار قنص الذعر اللحظي (V2)**، ونُقلت إلى هنا بدل حذفها
حتى تبقى قابلة للاستعادة والمراجعة.

## لماذا هي معطَّلة؟

GitHub Actions لا يقرأ أي ملف خارج `.github/workflows/`، وبما أن هذه الملفات نُقلت
من ذلك المجلد فقد **توقفت كل جدولاتها تلقائيًا**:

| الملف الأصلي | الوضع الآن |
|---|---|
| `.github/workflows/daily_monitor.yml` | `archive/disabled/workflows/` — توقفت الجدولة (كانت 4 مرات يوميًا) |
| `.github/workflows/phase2_discovery.yml` | `archive/disabled/workflows/` — توقفت الجدولة الشهرية |
| `.github/workflows/phase5_blind_validation.yml` | `archive/disabled/workflows/` — توقف التشغيل اليدوي |
| `daily_signal_scanner.py` | `archive/disabled/scripts/` — لم يعد يُستدعى من أي مسار |
| `reverse_split_source.py` | `archive/disabled/scripts/` — لم يعد يُستدعى من أي مسار |
| `daily_signals.json` (13.9MB) | `archive/disabled/data/` — لا تقرأه الواجهة الجديدة |
| `daily_signals_summary.json` | `archive/disabled/data/` — لا تقرأه الواجهة الجديدة |
| `paper_signal_history.json` | `archive/disabled/data/` — لا تقرأه الواجهة الجديدة |
| `strategy_spec_ar.md` | `archive/disabled/docs/` — استُبدل بـ `docs/STRATEGY_AR.md` |
| `MANUS_IMPLEMENTATION_PROMPT_AR.txt` | `archive/disabled/docs/` — مهمّة التنفيذ الأصلية |

## ما الذي بقي يعمل من النظام القديم؟

- **`reverse_split_candidates.json`** (في الجذر): ما زال يُستخدم، لكن بصفة **مرجعية ثابتة**
  فقط — النظام الجديد يقرأه لوسم الأسهم التي نفّذت تجزئة عكسية حديثًا بعلامة
  «تجزئة عكسية» داخل الرادار. إن غاب الملف يعمل النظام بشكل طبيعي بلا وسم.
  لتحديثه يدويًا: `python archive/disabled/scripts/reverse_split_source.py`
  (يحتاج `BUSINESSQUANT_API_KEY`).
- **`research/`**: نتائج الدراسة الإحصائية السابقة (Phase 2 → Phase 5) محفوظة كما هي
  في مكانها، وهي مرجع بحثي ولا يقرأها النظام الجديد.

## كيف أعيد تشغيل النظام القديم؟

```bash
git mv archive/disabled/workflows/daily_monitor.yml .github/workflows/daily_monitor.yml
git mv archive/disabled/scripts/daily_signal_scanner.py daily_signal_scanner.py
git mv archive/disabled/scripts/reverse_split_source.py reverse_split_source.py
git mv archive/disabled/data/daily_signals.json daily_signals.json
git mv archive/disabled/data/daily_signals_summary.json daily_signals_summary.json
git mv archive/disabled/data/paper_signal_history.json paper_signal_history.json
```

⚠️ لا تشغّل النظامين معًا: كلاهما يعمل بـ `git push` إلى نفس الفرع، وستتعارض
الكوميتات. اختر واحدًا.
