// Arabic (right-to-left) PowerPoint deck: what was done, the results, and what is needed from the client.
//
// Requirements:  npm install pptxgenjs
// Usage:
//   .venv\Scripts\python.exe scripts\export_deck_data.py      (writes reports/deck/deck_data.json)
//   node scripts/build_deck.js
// Output:     reports/deck/alzahraa_results.pptx  (git-ignored, no customer phones)
//
// APPLY_THEME (optional): path to apply_theme.js, bakes the theme colors into the file.
const fs = require("fs");
const path = require("path");
const pptxgen = require("pptxgenjs");

const ROOT = path.resolve(__dirname, "..");
const D = JSON.parse(fs.readFileSync(path.join(ROOT, "reports", "deck", "deck_data.json"), "utf8"));
const OUT = path.join(ROOT, "reports", "deck", "alzahraa_results.pptx");

const THEME = {
  name: "Alzahraa Pharmacy",
  headFontFace: "Arial",
  bodyFontFace: "Arial",
  colors: {
    dk1: "12303B", lt1: "FFFFFF", dk2: "0B5563", lt2: "EEF5F5",
    accent1: "0E7C86", accent2: "02C39A", accent3: "D9482B", accent4: "E9A23B", accent5: "5F6F7A", accent6: "2A78D6",
    hlink: "0E7C86", folHlink: "5F6F7A",
  },
};
const BLUE = "2A78D6", ORANGE = "EB6834", AQUA = "1BAF7A", GRID = "E3E8EA", AXIS = "5F6F7A";   // ألوان الرسومات (hex بس)

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE";                       // 13.33 × 7.5 بوصة
pres.rtlMode = true;
pres.title = "تحليل مبيعات صيدلية الزهراء";
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
const C = pres.SchemeColor;
const n0 = (v) => Math.round(v).toLocaleString("en-US");
const LANG = process.env.DECK_LANG || "ar-MA";   // عربي بأرقام 123 (ar-EG بيقلبها ١٢٣)
const ltr = (t) => `‎${t}‎`;            // يثبّت اتجاه الأرقام اللي فيها + أو % جوه الجملة العربي
const sgn = (v) => ltr(`${v > 0 ? "+" : ""}${v}%`);

// ── layouts ──
pres.defineSlideMaster({
  title: "DARK", background: { color: THEME.colors.dk2 },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.9, y: 2.3, w: 11.5, h: 1.6, fontSize: 44, bold: true,
                                color: C.background1, align: "right", valign: "middle" }, text: "" } },
    { placeholder: { options: { name: "body", type: "body", x: 0.9, y: 4.0, w: 11.5, h: 1.2, fontSize: 20,
                                color: C.background2, align: "right", valign: "top" }, text: "" } },
  ],
});
pres.defineSlideMaster({
  title: "CLOSING", background: { color: THEME.colors.dk2 },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.9, y: 0.8, w: 11.5, h: 1.1, fontSize: 40, bold: true,
                                color: C.background1, align: "right", valign: "middle" }, text: "" } },
  ],
});
pres.defineSlideMaster({
  title: "CONTENT", background: { color: THEME.colors.lt1 },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.6, y: 0.4, w: 12.1, h: 0.95, fontSize: 36, bold: true,
                                color: C.text2, align: "right", valign: "middle" }, text: "" } },
  ],
  slideNumber: { x: 0.6, y: 6.95, w: 0.8, h: 0.3, fontSize: 11, color: C.accent5 },
});

// ── helpers ──
// numbers go into their own runs with lang en-US so they render as 123 and not Arabic-Indic digits, whatever the device settings
const NUM = /(‎?[+\-]?\d[\d,.]*%?‎?)/;
const R = (text, base = {}) => {
  const items = Array.isArray(text) ? text : [{ text, options: {} }];
  const out = [];
  items.forEach((it) => {
    const { breakLine, ...rest } = it.options || {};
    const parts = String(it.text).split(NUM).filter((t) => t !== "");
    parts.forEach((t, i) => out.push({ text: t, options: { rtlMode: true, align: "right", ...base, ...rest, lang: NUM.test(t) ? "en-US" : LANG,
                                                          ...(breakLine && i === parts.length - 1 ? { breakLine: true } : {}) } }));
  });
  return out;
};
const T = (slide, text, x, y, w, h, o = {}) =>
  slide.addText(R(text, o.align ? { align: o.align } : {}), { x, y, w, h, isTextBox: true, rtlMode: true, align: "right", valign: "top", margin: 0,
                        fontSize: 16, color: C.text1, lang: LANG, ...o });
const card = (slide, x, y, w, h, name, color = C.background2) =>
  slide.addShape(pres.ShapeType.roundRect, { x, y, w, h, rectRadius: 0.14, fill: { color }, line: { color, width: 0 }, objectName: name });
const badge = (slide, label, x, y, color = C.accent1, size = 0.62) =>
  slide.addText(String(label), { x, y, w: size, h: size, shape: pres.ShapeType.ellipse, fill: { color }, color: C.background1,
                                 bold: true, fontSize: 18, align: "center", valign: "middle", margin: 0, isTextBox: true,
                                 objectName: `badge ${label}` });
const stat = (slide, value, label, x, y, w, color = C.text2) => {
  slide.addText(String(value), { x, y, w, h: 0.95, isTextBox: true, margin: 0, fontSize: 40, bold: true, color, align: "center",
                                  valign: "middle", lang: "en-US" });
  T(slide, label, x, y + 0.95, w, 0.6, { fontSize: 14, color: C.accent5, align: "center" });
};
const chartBase = () => ({
  catAxisLabelFontSize: 11, valAxisLabelFontSize: 11, catAxisLabelColor: AXIS, valAxisLabelColor: AXIS,
  catAxisLabelFontFace: "+mn-lt", valAxisLabelFontFace: "+mn-lt", legendFontFace: "+mn-lt", dataLabelFontFace: "+mn-lt",
  valGridLine: { color: GRID, size: 0.5 }, catGridLine: { style: "none" }, legendFontSize: 12, legendColor: AXIS,
  dataLabelColor: THEME.colors.dk1, dataLabelFontSize: 11,
});
const content = (section, title) => {
  const s = pres.addSlide({ masterName: "CONTENT", sectionTitle: section });
  s.addText(R(title), { placeholder: "title", rtlMode: true });
  return s;
};

// ═════════ 1) title ═════════
pres.addSection({ title: "المقدمة" });
{
  const s = pres.addSlide({ masterName: "DARK", sectionTitle: "المقدمة" });
  s.addText(R("تحليل مبيعات صيدلية الزهراء"), { placeholder: "title", rtlMode: true });
  s.addText(R(`النتايج والقرارات المطلوبة، للفرعين، من ${D.period.start} إلى ${D.period.end}`), { placeholder: "body", rtlMode: true });
}

// ═════════ 2) what we did ═════════
{
  const s = content("المقدمة", "عملنا إيه في تلات خطوات");
  const steps = [
    ["1", "نضّفنا الشيت", `شلنا ${D.cleaning.removed} سطر مكرر وصلّحنا ${n0(D.cleaning.changes)} خانة. الشيت الأصلي ما اتلمسش، وكل تغيير متسجل بسببه.`],
    ["2", "جاوبنا على أسئلتك العشرة", "إيراد الفرعين، الأصناف، المواسم، الدكاترة، الزحمة، الأسعار، الدفع، الصلاحية، المضادات، والتوقع."],
    ["3", "جهّزنا التقارير", "تقرير نهائي قصير، تقرير صلاحية، وداشبورد بيفتح على الموبايل. والكود بيتشغل على شيت كل شهر."],
  ];
  const w = 3.85, gap = 0.3, x0 = 0.6;
  steps.forEach(([n, head, body], i) => {
    const x = 13.33 - x0 - w - i * (w + gap);            // من اليمين للشمال
    card(s, x, 1.7, w, 3.3, `step ${n}`);
    badge(s, n, x + w - 0.62 - 0.3, 2.0);
    T(s, head, x + 0.3, 2.85, w - 0.6, 0.5, { fontSize: 20, bold: true, color: C.text2 });
    T(s, body, x + 0.3, 3.45, w - 0.6, 1.4, { fontSize: 14 });
  });
  stat(s, n0(D.cleaning.raw_rows), "سطر في الشيت الأصلي", 9.0, 5.4, 3.7);
  stat(s, n0(D.cleaning.clean_rows), "سطر بعد التنضيف", 4.8, 5.4, 3.7);
  stat(s, n0(D.totals.revenue), "جنيه إجمالي المبيعات", 0.6, 5.4, 3.7);
}

// ═════════ 3) top 5 findings ═════════
pres.addSection({ title: "النتايج" });
{
  const s = content("النتايج", "أهم خمس حاجات لازم تعرفها");
  const items = [
    [`${D.expiry.rows} مرة اتباع دوا بعد انتهاء صلاحيته`, `${D.expiry.units} علبة، موزعين على الفرعين والأربع دكاترة`, C.accent3],
    [`${D.doctors.top_name} خصوماته 3 أضعاف زمايله`, `${ltr(D.doctors.top_rate + "%")} من بيعه مقابل ${ltr(D.doctors.base_rate + "%")}، بتكلفة حوالي ${n0(D.doctors.top_year)} جنيه في السنة`, C.accent4],
    [`الخارجة بتبيع أكتر من موط بحوالي ${ltr(D.branches.pct_more + "%")}`, "السبب عدد العملاء، مش قيمة الفاتورة", C.accent1],
    [`زيادة الأسعار ${ltr("12%")} ما قللتش البيع`, `الكميات ${sgn(D.price.units_pct)} والإيراد ${sgn(D.price.rev_pct)}`, C.accent1],
    [`المتوقع لآخر 3 شهور في ${D.price.y1}`, `الخارجة حوالي ${n0(D.forecast.totals[0].mid)} وموط حوالي ${n0(D.forecast.totals[1].mid)} جنيه`, C.accent1],
  ];
  items.forEach(([head, sub, color], i) => {
    const y = 1.65 + i * 1.04;
    card(s, 0.6, y, 12.13, 0.9, `finding ${i + 1}`);
    badge(s, i + 1, 11.9, y + 0.14, color);
    T(s, head, 0.9, y + 0.1, 10.8, 0.4, { fontSize: 18, bold: true, color: C.text2 });
    T(s, sub, 0.9, y + 0.5, 10.8, 0.35, { fontSize: 14, color: C.accent5 });
  });
}

// ═════════ 4) expiry ═════════
{
  const s = content("النتايج", "الصلاحية: الأولوية الأولى");
  card(s, 7.4, 1.65, 5.33, 4.9, "expiry stats");
  stat(s, String(D.expiry.rows), "مرة بيع بعد انتهاء الصلاحية", 7.6, 1.85, 4.93, C.accent3);
  stat(s, String(D.expiry.units), "علبة", 10.1, 3.55, 2.4);
  stat(s, n0(D.expiry.value), "جنيه قيمة البيع", 7.6, 3.55, 2.4);
  T(s, `فيه ${D.expiry.missing} سطر تاريخ الصلاحية فيهم مش متسجل، فالرقم ده هو الحد الأدنى.`, 7.7, 5.35, 4.73, 1.0, { fontSize: 14, color: C.accent5 });
  T(s, "عدد الحالات عند كل دكتور", 0.6, 1.65, 6.4, 0.4, { fontSize: 16, bold: true, color: C.text2 });
  s.addChart(pres.ChartType.bar, [{ name: "حالات", labels: D.expiry.doctors, values: D.expiry.cases }], {
    x: 0.6, y: 2.1, w: 6.4, h: 3.2, barDir: "bar", chartColors: [THEME.colors.accent3], showLegend: false,
    showValue: true, dataLabelPosition: "outEnd", valAxisHidden: true, barGapWidthPct: 70, ...chartBase(),
    valGridLine: { style: "none" }, altText: "عدد حالات البيع بعد انتهاء الصلاحية عند كل دكتور",
  });
  T(s, "الحالات عند الأربعة وفي الفرعين، يعني المطلوب نظام متابعة للصلاحية مش محاسبة شخص.", 0.6, 5.45, 6.4, 1.0, { fontSize: 14 });
}

// ═════════ 5) branches ═════════
{
  const s = content("النتايج", "الخارجة أعلى في كل الشهور");
  s.addChart(pres.ChartType.line, [
    { name: "الخارجة", labels: D.branches.labels, values: D.branches.kharga },
    { name: "موط - الداخلة", labels: D.branches.labels, values: D.branches.mut },
  ], {
    x: 0.6, y: 1.6, w: 8.3, h: 4.9, chartColors: [BLUE, ORANGE], lineSize: 2, lineDataSymbolSize: 5,
    showLegend: true, legendPos: "t", valAxisNumFmt: "#,##0", valAxisMinVal: 0, ...chartBase(),
    altText: "إيراد كل فرع شهر بشهر",
  });
  card(s, 9.2, 1.65, 3.53, 4.85, "branch notes");
  stat(s, `+${D.branches.pct_more}%`, "إيراد الخارجة عن موط", 9.35, 1.8, 3.23);
  T(s, [
    { text: `أعلى في ${D.branches.wins} شهر من ${D.branches.n}.`, options: { breakLine: true } },
    { text: `الفواتير: ${n0(D.branches.inv_k)} مقابل ${n0(D.branches.inv_m)}.`, options: { breakLine: true } },
    { text: `متوسط الفاتورة متقارب: ${D.branches.avg_k} و${D.branches.avg_m} جنيه.`, options: { breakLine: true } },
    { text: "يعني الفرق في عدد العملاء." },
  ], 9.45, 3.55, 3.03, 2.8, { fontSize: 14, paraSpaceAfter: 6 });
}

// ═════════ 6) discounts ═════════
{
  const s = content("النتايج", "الخصومات: دكتور واحد مختلف عن الباقي");
  T(s, "الخصم كنسبة من بيع كل دكتور", 6.3, 1.65, 6.43, 0.4, { fontSize: 16, bold: true, color: C.text2 });
  s.addChart(pres.ChartType.bar, [{ name: "الخصم %", labels: D.doctors.names, values: D.doctors.disc_rate }], {
    x: 6.3, y: 2.1, w: 6.43, h: 3.3, barDir: "bar", chartColors: [THEME.colors.accent1], showLegend: false, showValue: true,
    dataLabelPosition: "outEnd", dataLabelFormatCode: '0.0"%"', valAxisHidden: true, barGapWidthPct: 70, catAxisOrientation: "maxMin",
    ...chartBase(), valGridLine: { style: "none" }, altText: "الخصم كنسبة من بيع كل دكتور",
  });
  T(s, "متوسط الفاتورة واحد تقريباً عند الأربعة. والإيراد بيفرق حسب الفرع والشيفت، فالمقارنة العادلة صبح بصبح وليل بليل.",
    6.3, 5.5, 6.43, 1.0, { fontSize: 14 });
  card(s, 0.6, 1.65, 5.3, 4.85, "discount stats");
  stat(s, n0(D.doctors.top_year), "جنيه تكلفة خصوماته في السنة", 0.8, 1.9, 4.9, C.accent3);
  stat(s, n0(D.doctors.excess_year), "جنيه منهم زيادة عن معدل زمايله", 0.8, 3.6, 4.9);
  T(s, "النمط ثابت في كل الشهور والأصناف. السؤال ليك: ده بتعليمات منك؟", 0.9, 5.4, 4.7, 0.9, { fontSize: 14, color: C.accent5 });
}

// ═════════ 7) seasons ═════════
{
  const s = content("النتايج", "المواسم: اطلب البضاعة قبلها بشهر");
  const names = Object.keys(D.season.series);
  s.addChart(pres.ChartType.line, names.map((k) => ({ name: k, labels: D.season.labels, values: D.season.series[k] })), {
    x: 0.6, y: 1.6, w: 7.6, h: 4.9, chartColors: [BLUE, ORANGE, AQUA], lineSize: 2, lineDataSymbolSize: 5,
    showLegend: true, legendPos: "t", valAxisMinVal: 0, ...chartBase(), altText: "عدد العلب المباعة كل شهر للأصناف الموسمية",
  });
  const rows = [
    ["أدوية البرد", "أكتوبر ← مارس", "سبتمبر"],
    ["ORS و Antinal", "مايو ← سبتمبر", "أبريل"],
    ["واقي الشمس", "يونيو ← سبتمبر", "مايو"],
  ];
  rows.forEach(([name, season, order], i) => {
    const y = 1.65 + i * 1.65;
    card(s, 8.5, y, 4.23, 1.5, `season ${i + 1}`);
    T(s, name, 8.7, y + 0.15, 3.83, 0.4, { fontSize: 18, bold: true, color: C.text2 });
    T(s, `الموسم: ${season}`, 8.7, y + 0.6, 3.83, 0.35, { fontSize: 14 });
    T(s, `اطلب في: ${order}`, 8.7, y + 0.98, 3.83, 0.35, { fontSize: 14, bold: true, color: C.accent1 });
  });
}

// ═════════ 8) prices and payment ═════════
{
  const s = content("النتايج", "الأسعار عدّت، والدفع الإلكتروني بيزيد");
  card(s, 7.0, 1.65, 5.73, 4.85, "price stats");
  T(s, `أثر زيادة ${ltr("12%")}: صيف ${D.price.y1} مقابل صيف ${D.price.y0}`, 7.2, 1.85, 5.33, 0.45, { fontSize: 16, bold: true, color: C.text2 });
  stat(s, `${D.price.units_pct > 0 ? "+" : ""}${D.price.units_pct}%`, "عدد العلب", 9.95, 2.55, 2.6);
  stat(s, `+${D.price.rev_pct}%`, "الإيراد", 7.2, 2.55, 2.6, C.accent1);
  T(s, "العملاء كملوا يشتروا بنفس الكمية، فالزيادة دخلت كلها في الإيراد.", 7.3, 4.5, 5.13, 0.9, { fontSize: 14 });
  T(s, "قارنّا صيف بصيف عشان موسم البرد ما يدخلش في المقارنة.", 7.3, 5.45, 5.13, 0.8, { fontSize: 14, color: C.accent5 });
  T(s, `الدفع الإلكتروني من ${ltr(D.payment.first + "%")} إلى ${ltr(D.payment.last + "%")} من الفواتير`, 0.6, 1.65, 6.1, 0.45, { fontSize: 16, bold: true, color: C.text2 });
  s.addChart(pres.ChartType.line, [{ name: "إلكتروني %", labels: D.payment.labels, values: D.payment.electronic }], {
    x: 0.6, y: 2.15, w: 6.1, h: 3.55, chartColors: [BLUE], lineSize: 2, lineDataSymbolSize: 5, showLegend: false,
    valAxisMinVal: 0, valAxisNumFmt: '0"%"', ...chartBase(), altText: "نسبة الدفع الإلكتروني من الفواتير شهر بشهر",
  });
  T(s, "InstaPay والمحافظ مع بعض. مفيش فرق بين الفرعين.", 0.6, 5.8, 6.1, 0.6, { fontSize: 14 });
}

// ═════════ 9) forecast ═════════
{
  const s = content("النتايج", `توقع أكتوبر–ديسمبر ${D.price.y1}`);
  const hdr = (t) => ({ text: t, options: { bold: true, color: "FFFFFF", fill: { color: THEME.colors.dk2 }, align: "center", fontSize: 14 } });
  const cell = (t, o = {}) => ({ text: t, options: { align: "center", fontSize: 14, color: THEME.colors.dk1, ...o } });
  // columns are written in reverse so the table reads right to left
  const body = [[hdr("أعلى"), hdr("المتوقع"), hdr("أقل"), hdr("الشهر"), hdr("الفرع")]];
  D.forecast.rows.forEach((r) => body.push([cell(n0(r.high)), cell(n0(r.mid), { bold: true }), cell(n0(r.low)), cell(r.month.split(" ")[0]), cell(r.branch.split(" ")[0])]));
  s.addTable(body, { x: 4.9, y: 1.7, w: 7.83, colW: [1.45, 1.55, 1.45, 1.78, 1.6], rowH: 0.52,
                     border: { type: "solid", pt: 0.75, color: GRID }, fontFace: THEME.bodyFontFace, objectName: "forecast table" });
  D.forecast.totals.forEach((t, i) => {
    const y = 1.7 + i * 2.45;
    card(s, 0.6, y, 3.95, 2.25, `quarter ${i + 1}`);
    T(s, `${t.branch}: إجمالي الربع`, 0.8, y + 0.15, 3.55, 0.4, { fontSize: 16, bold: true, color: C.text2 });
    s.addText(n0(t.mid), { x: 0.8, y: y + 0.6, w: 3.55, h: 0.85, isTextBox: true, margin: 0, fontSize: 40, bold: true,
                           color: i === 0 ? BLUE : ORANGE, align: "center", valign: "middle", lang: "en-US" });
    T(s, `من ${n0(t.low)} إلى ${n0(t.high)} جنيه`, 0.8, y + 1.5, 3.55, 0.5, { fontSize: 14, color: C.accent5, align: "center" });
  });
  T(s, `توقع تقريبي للتخطيط: مبني على ${D.period.n_months} شهر بس. استخدم المدى، مش الرقم اللي في النص لوحده.`,
    4.9, 5.75, 7.83, 0.8, { fontSize: 14, color: C.accent5 });
}

// ═════════ 10) decisions ═════════
pres.addSection({ title: "المطلوب" });
{
  const s = content("المطلوب", "محتاجين منك سبع قرارات");
  const dc = D.decisions;
  const items = [
    [`مرتجعات (${dc.returns})`, "تفضل مخصومة من الإيراد، ومن النهارده يتكتب عليها رقم الفاتورة الأصلية"],
    [`إجمالي ضعف المحسوب (${dc.totals})`, "نعتمد الإجمالي المحسوب، وراجع أكبر 5 سطور على الجرد"],
    [`دفع مش متسجل (${dc.payment})`, "يفضل «غير معروف»، والخانة تبقى إجبارية"],
    [`صلاحية مش متسجلة (${dc.expiry})`, "تفضل فاضية، والخانة تبقى إجبارية"],
    [`سعرين لنفس الصنف (فرق ${ltr("5%")})`, "لو تشغيلات يتساب، ولو لأ قايمة أسعار واحدة"],
    [`خصومات ${D.doctors.top_name}`, "سياسة خصم واحدة مكتوبة للأربعة، ومتابعة شهرية"],
    [`موط في ${dc.low_month}`, `لو كان نقص مخزون: حد أدنى للأصناف الغالية، والتوقع يبقى ${n0(dc.adj_quarter)}`],
  ];
  const w = 5.9, h = 0.98, gapY = 0.14;
  items.forEach(([head, sug], i) => {
    const col = i < 4 ? 0 : 1, row = i < 4 ? i : i - 4;
    const x = 13.33 - 0.6 - w - col * (w + 0.33), y = 1.6 + row * (h + gapY);
    card(s, x, y, w, h, `decision ${i + 1}`);
    badge(s, i + 1, x + w - 0.72, y + 0.18, C.accent1, 0.56);
    T(s, head, x + 0.2, y + 0.1, w - 1.05, 0.38, { fontSize: 16, bold: true, color: C.text2 });
    T(s, sug, x + 0.2, y + 0.5, w - 1.05, 0.42, { fontSize: 14, color: C.text1 });
  });
  card(s, 0.6, 1.6 + 3 * (h + gapY), w, h, "decision note", C.text2);
  T(s, "ده اقتراحنا لكل بند. القرار النهائي ليك، والتفاصيل في التقرير النهائي.", 0.8, 1.6 + 3 * (h + gapY) + 0.12, w - 0.4, h - 0.24,
    { fontSize: 14, color: C.background1, valign: "middle" });
}

// ═════════ 11) files ═════════
{
  const s = content("المطلوب", "الملفات اللي معاك وإزاي تستخدمها");
  const files = [
    ["التقرير النهائي", "final_report", "ابدأ بيه. أول قسم فيه بياخد دقيقتين."],
    ["الداشبورد", "dashboard", "رسومات الأسئلة العشرة. بيفتح على الموبايل ومن غير إنترنت. ابعته للدكاترة."],
    ["تقرير الصلاحية", "expiry_report", "الملخص للكل، وملف Excel فيه أرقام العملاء للتواصل (ليك إنت بس)."],
    ["الشيت النضيف", "alzahraa_sales_clean", "شيت المبيعات بعد التصليح، بنفس أعمدتك."],
    ["ورقة التنضيف", "cleaning_summary, cleaning_changes", "كل تغيير اتعمل: فين، كام، وليه. والسطور اللي محتاجة قرارك."],
    ["دليل الاستخدام", "user_guide", "شرح كل ملف خطوة بخطوة."],
  ];
  const w = 3.85, h = 2.1, gap = 0.29;
  files.forEach(([name, file, use], i) => {
    const col = i % 3, row = Math.floor(i / 3);
    const x = 13.33 - 0.6 - w - col * (w + gap), y = 1.65 + row * (h + 0.3);
    card(s, x, y, w, h, `file ${i + 1}`);
    T(s, name, x + 0.25, y + 0.2, w - 0.5, 0.42, { fontSize: 18, bold: true, color: C.text2 });
    s.addText(file, { x: x + 0.25, y: y + 0.65, w: w - 0.5, h: 0.32, isTextBox: true, margin: 0, fontSize: 12, color: C.accent1, align: "right", lang: "en-US" });
    T(s, use, x + 0.25, y + 1.05, w - 0.5, 1.05, { fontSize: 14 });
  });
  T(s, "الملفات اللي فيها أرقام موبايلات العملاء ما تتبعتش على جروبات.", 0.6, 6.45, 12.13, 0.35, { fontSize: 14, color: C.accent3 });
}

// ═════════ 12) next steps ═════════
{
  const s = pres.addSlide({ masterName: "CLOSING", sectionTitle: "المطلوب" });
  s.addText(R("الخطوات الجاية"), { placeholder: "title", rtlMode: true });
  const steps = [
    ["1", "جرد الصلاحية في الفرعين", "وسحب أي علبة منتهية من الرف"],
    ["2", "ردّك على القرارات السبعة", "عشان نقفل الأرقام النهائية"],
    ["3", "شيت الشهر الجاي", "بنفس الأعمدة، والملفات كلها تتحدّث"],
  ];
  const w = 3.75, gap = 0.3;
  steps.forEach(([n, head, sub], i) => {
    const x = 13.33 - 0.9 - w - i * (w + gap);
    card(s, x, 2.5, w, 3.0, `next ${n}`, C.background1);
    badge(s, n, x + w - 0.92, 2.8, C.accent2);
    T(s, head, x + 0.3, 3.65, w - 0.6, 0.85, { fontSize: 20, bold: true, color: C.text2 });
    T(s, sub, x + 0.3, 4.5, w - 0.6, 0.8, { fontSize: 14 });
  });
}

(async () => {
  await pres.writeFile({ fileName: OUT });
  if (process.env.APPLY_THEME) {
    const { applyTheme } = require(process.env.APPLY_THEME);
    await applyTheme(OUT, THEME);
  }
  console.log("saved:", OUT);
})();
