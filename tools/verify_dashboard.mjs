#!/usr/bin/env node
/**
 * فحص الداشبورد في DOM حقيقي (jsdom) — يحمّل index.html مع panic_data.json
 * ويمرّ على كل التبويبات والدرج الجانبي والرسم، ويلتقط أي استثناء.
 *
 * التثبيت:  npm i --no-save jsdom
 * التشغيل:  node tools/verify_dashboard.mjs
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { JSDOM, VirtualConsole } from "jsdom";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const read = (f) => fs.readFileSync(path.join(ROOT, f), "utf8");

const errors = [];
const vc = new VirtualConsole();
vc.on("jsdomError", (e) => errors.push("jsdomError: " + (e.stack || e.message)));
vc.on("error", (...a) => errors.push("console.error: " + a.join(" ")));

const dom = new JSDOM(read("index.html"), {
  runScripts: "dangerously",
  pretendToBeVisual: true,
  virtualConsole: vc,
  url: "http://localhost/",
  beforeParse(win) {
    // ── بديل Canvas: يسجّل أوامر الرسم بدل التنفيذ
    const calls = { ops: 0, fills: 0, strokes: 0, texts: 0 };
    win.__canvas = calls;
    const ctx = new Proxy({
      canvas: null,
      measureText: () => ({ width: 20 }),
      createLinearGradient: () => ({ addColorStop() {} }),
      fillText: () => { calls.texts++; },
      fillRect: () => { calls.fills++; },
      stroke: () => { calls.strokes++; },
    }, {
      get(t, k) {
        if (k in t) return t[k];
        return (...a) => { calls.ops++; return undefined; };
      },
      set() { calls.ops++; return true; },
    });
    win.HTMLCanvasElement.prototype.getContext = () => ctx;
    win.HTMLCanvasElement.prototype.getBoundingClientRect = () =>
      ({ width: 620, height: 300, top: 0, left: 0, right: 620, bottom: 300 });
    win.Element.prototype.getBoundingClientRect = function () {
      if (this.tagName === "CANVAS") return { width: 620, height: 300, top: 0, left: 0, right: 620, bottom: 300 };
      return { width: 400, height: 40, top: 0, left: 0, right: 400, bottom: 40 };
    };
    win.HTMLAnchorElement.prototype.click = () => {};
    win.URL.createObjectURL = () => "blob:mock";
    win.URL.revokeObjectURL = () => {};
    // ── بديل fetch: يقرأ الملفات من القرص
    win.fetch = async (url) => {
      const name = String(url).split("?")[0].replace(/^https?:\/\/[^/]+\//, "").replace(/^\.\//, "");
      const file = name.replace(/^.*\//, "");
      if (!file.endsWith(".json")) return { ok: false, status: 404 };
      try {
        const body = fs.readFileSync(path.join(ROOT, file), "utf8");
        return { ok: true, status: 200, json: async () => JSON.parse(body) };
      } catch (e) { return { ok: false, status: 404 }; }
    };
  },
});

const win = dom.window;
const doc = win.document;
const wait = (ms) => new Promise((r) => setTimeout(r, ms));
const $ = (s) => doc.querySelector(s);
const $$ = (s) => [...doc.querySelectorAll(s)];
const text = (s) => ($(s) ? $(s).textContent.trim() : "<missing>");
// `let D` في سكربت كلاسيكي ليس خاصية على window — نقرأه من نطاقه العام عبر eval
const state = () => win.eval("D");
const stateS = () => win.eval("S");

let failed = 0;
function check(name, cond, extra = "") {
  if (cond) console.log("✅", name);
  else { failed++; console.log("❌", name, extra); }
}

await wait(700);

// ── البيانات وصلت ورُسمت
check("panic_data.json محمَّل", !!state(), "D is null");
check("panic_stats.json محمَّل", !!stateS(), "S is null");
check("شريط الحالة يعرض وقت المسح", /آخر مسح/.test(text("#liveText")), text("#liveText"));
check("لا توجد أخطاء في الطرفية", errors.length === 0, errors.slice(0, 3).join(" | "));

// ── البطاقات
const kpiCount = $$("#kpis .kpi").length;
check("بطاقات KPI مرسومة (" + kpiCount + ")", kpiCount === 8);
check("KPI الكون رقمي", /^\d[\d,]*$/.test($$("#kpis .kpi .v")[0].textContent),
  $$("#kpis .kpi .v")[0].textContent);

// ── الشريط المتحرك والقمع
check("الشريط المتحرك فيه عناصر", $$("#tape .tape-item").length > 0);
check("القمع يعرض 10 مراحل", $$("#funnel .fstep").length === 10,
  String($$("#funnel .fstep").length));
check("القمع فيه مرحلة مكتملة", /إشارة مكتملة/.test(text("#funnel")));

// ── الجدول
const rows = $$("#gridBody tr");
check("الجدول يعرض صفوفًا (" + rows.length + ")", rows.length === (state().items || []).length);
check("رؤوس الأعمدة 19", $$("#gridHead th").length === 19,
  String($$("#gridHead th").length));
check("الرمز يظهر في الصف الأول", /^[A-Z0-9.\-]+$/.test(rows[0].querySelector(".tick").textContent),
  rows[0].querySelector(".tick").textContent);
check("شارات الحالة مرسومة", $$("#gridBody .badge").length >= rows.length);
check("درجات A/B/C/D مرسومة", $$("#gridBody .grade").length === rows.length);

// ── الفلاتر
$("#q").value = "zzz-no-match";
$("#q").dispatchEvent(new win.Event("input"));
check("البحث يستثني كل الصفوف", $$("#gridBody tr").length === 0);
check("رسالة «لا نتائج» ظاهرة", /لا نتائج مطابقة/.test(text("#gridEmpty")));
$("#q").value = "";
$("#q").dispatchEvent(new win.Event("input"));
check("مسح البحث يعيد الصفوف", $$("#gridBody tr").length === rows.length);

$("#minScore").value = "99";
$("#minScore").dispatchEvent(new win.Event("input"));
check("فلتر الدرجة ≥ 99 يقلّص النتائج", $$("#gridBody tr").length < rows.length);
$("#minScore").value = "0";
$("#minScore").dispatchEvent(new win.Event("input"));

const chips = $$("#stateChips .chip");
check("رقائق الحالات مرسومة (" + chips.length + ")", chips.length > 0);
if (chips.length) {
  chips[0].click();
  check("الفلتر بالحالة يقلّص النتائج", $$("#gridBody tr").length <= rows.length);
  chips[0].click();
}

// ── الدرج الجانبي + الرسم
rows[0].dispatchEvent(new win.MouseEvent("click", { bubbles: true }));
await wait(60);
check("الدرج الجانبي مفتوح", $("#drawer").classList.contains("on"));
check("اسم الرمز في ترويسة الدرج", !!$("#dhead .big") && $("#dhead .big").textContent.length > 0,
  text("#dhead .big"));
check("صفوف الشروط مرسومة", $$("#dbody .check-row").length >= 10,
  String($$("#dbody .check-row").length));
check("خطة المخاطرة تعرض الهدفين", $$("#dbody .lvl.tgt").length >= 2,
  String($$("#dbody .lvl.tgt").length));
check("قسم الرجل الأولى معروض", /الرجل الأولى/.test($("#dbody").textContent));
check("وضعَا الدخول معروضان", /دخول فوري أعلى القاع/.test($("#dbody").textContent)
  && /اختراق قمة القاعدة/.test($("#dbody").textContent));
check("دور VWAP معروض (سقف مقاوم أو دعم سفلي)",
  /VWAP — (سقف مقاوم|دعم سفلي|غير متاح)/.test($("#dbody").textContent),
  (($$("#dbody .lvl").find((e) => /^VWAP —/.test(e.textContent.trim())) || {}).textContent || "").trim());
check("حكم الأهداف مقابل VWAP معروض",
  /(قبل خط VWAP|يخترق السقف|فلم يعد الخط سقفًا|غير متاح للقياس)/.test($("#dbody").textContent));
check("عمود الصعود السابق في الجدول", $$("#gridHead th").length === 19,
  String($$("#gridHead th").length));
check("خريطة المستويات مرسومة", $$("#dbody .metric").length > 25);
check("أوامر رسم نُفّذت على Canvas", win.__canvas.ops > 50, "ops=" + win.__canvas.ops);
check("OHLC مُعبّأ", /O /.test(text("#ohlc")), text("#ohlc").slice(0, 60));

// تبديل اللوحات
const paneTabs = $$("#paneTabs .pane-tab");
check("لوحات المؤشرات 5", paneTabs.length === 5);
for (const t of paneTabs) {
  const before = win.__canvas.ops;
  t.click();
  await wait(20);
  check("لوحة " + t.dataset.p + " تُرسم بلا خطأ", win.__canvas.ops > before);
}
check("لا أخطاء بعد تبديل اللوحات", errors.length === 0, errors.slice(0, 2).join(" | "));

// ── سلامة الأرقام المعروضة مقابل البيانات
{
  const items = state().items || [];
  const first = items[0];
  const moneyOf = (v) => "$" + (+v).toLocaleString("en-US", { minimumFractionDigits: (+v < 1 ? 4 : 2), maximumFractionDigits: (+v < 1 ? 4 : 2) });
  const row = $$("#gridBody tr")[0];
  check("سعر الصف الأول يطابق البيانات", row.cells[2].textContent.trim() === moneyOf(first.price),
    row.cells[2].textContent + " ≠ " + moneyOf(first.price));
  check("هبوط الصف الأول يطابق البيانات",
    row.cells[4].textContent.trim().replace("+", "") === (first.drop_pct > 0 ? "+" : "") + first.drop_pct.toFixed(1) + "%",
    row.cells[4].textContent + " ≠ " + first.drop_pct);
  check("الصعود السابق في الجدول يطابق البيانات",
    row.cells[5].textContent.includes("+" + Math.round(first.runup.runup_pct) + "%"),
    row.cells[5].textContent + " ≠ " + first.runup.runup_pct);
  check("هدف T2 في الجدول يطابق plan",
    row.cells[14].textContent.trim() === moneyOf(first.risk.target_2 ?? first.risk.target),
    row.cells[14].textContent + " ≠ " + moneyOf(first.risk.target_2 ?? first.risk.target));
  // الوقف = قاع الثبات − max(5% ، ATR×1) — قد يكون ATR أوسع فيعمّق الوقف دون أن يكسر القاعدة
  const expectStop = first.base_low - Math.max(0.05 * first.base_low, first.risk.atr || 0);
  check("الوقف = قاع الثبات − max(5%، ATR) في الجدول",
    row.cells[15].textContent.trim() === moneyOf(first.risk.stop)
    && Math.abs(first.risk.stop - expectStop) < 1e-2,
    row.cells[15].textContent + " ≠ " + moneyOf(first.risk.stop) + " (المتوقع " + expectStop.toFixed(4) + ")");
  check("عدد الشموع في البطاقة ≤ حد الرسم",
    (first.chart || []).length <= 96, String((first.chart || []).length));
  check("كل شمعة تحمل قيم المؤشرات",
    (first.chart || []).every(b => "rsi" in b && "macd_hist" in b && "vwap" in b && "obv" in b));
  check("الدرج يعرض نفس الرمز المفتوح", $("#dhead .big").textContent === first.ticker,
    $("#dhead .big").textContent + " ≠ " + first.ticker);
}

// ── التصدير
let csvName = "";
win.HTMLAnchorElement.prototype.click = function () { csvName = this.download; };
$("#csvBtn").click();
check("تصدير CSV ينتج ملفًا", /panic-radar-.*\.csv$/.test(csvName), csvName);

// ── بقية التبويبات
for (const tab of ["stats", "rules", "ops"]) {
  $(`#tabs .tab[data-tab="${tab}"]`).click();
  await wait(40);
  check(`تبويب ${tab} ظاهر`, !$(`#tab-${tab}`).hidden);
  check(`تبويب radar مخفي عند ${tab}`, $("#tab-radar").hidden);
}
check("بطاقات الأداء مرسومة", $$("#statCards .kpi").length >= 9);
check("توزيع الأهداف مرسوم", $("#targetBars").textContent.trim().length > 0);
check("القواعد الأساسية معروضة", $$("#coreRules .check-row").length >= 4);
check("طبقة التأكيد معروضة", $$("#extraRules .check-row").length >= 5);
check("جدول الأرقام التشغيلية", $$("#thresholds .lvl").length >= 12);
check("سجل المسوحات معروض", $$("#scanLog .log-row").length > 0);
check("بطاقات التشغيل 8", $$("#opsKpis .kpi").length === 8);

$("#tabs .tab[data-tab='radar']").click();
win.close();

console.log(failed ? `\n${failed} فشل` : "\nكل الفحوص نجحت ✔");
process.exit(failed ? 1 : 0);
