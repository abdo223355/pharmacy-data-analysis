"""Short final client report: plain Arabic, printable and mobile friendly.

Numbers are computed from the clean sheet (same computations as the dashboard). The narrative conclusions
(seasons, explanations, recommendations) come from the analysis of June 2025 - September 2026, so they must be
re-checked by hand if the data changes.

Usage:  .venv\Scripts\python.exe scripts\build_report.py
Output: reports/final/final_report.html  (git-ignored, no customer phone numbers)
"""
from pathlib import Path

import pandas as pd

from build_dashboard import BRANCH_AR, DOCTOR_AR, K, M, MONTH_AR, compute, n0

ROOT = Path(__file__).resolve().parents[1]
CLEAN_DIR = ROOT / "data" / "clean"
OUT = ROOT / "reports" / "final"

CSS = """
:root{--ink:#1c2430;--muted:#5b6675;--line:#e2e6ec;--bg:#f6f7f9;--card:#fff;--bad:#b3261e;--badbg:#fdecea;--warn:#6b4700;--warnbg:#fff4dc}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font-family:"Segoe UI",Tahoma,Arial,sans-serif;line-height:1.8}
main{max-width:820px;margin:0 auto;padding:18px;background:var(--card)}
h1{font-size:1.5rem;margin:4px 0 2px} h2{font-size:1.15rem;margin:26px 0 8px;padding-bottom:4px;border-bottom:2px solid var(--line)}
h3{font-size:1rem;margin:16px 0 2px}
.sub{color:var(--muted);margin:0 0 14px} p{margin:4px 0 8px}
ol,ul{padding-inline-start:22px;margin:6px 0} li{margin-bottom:6px}
.box{border-radius:10px;padding:10px 14px;margin:10px 0}
.box.bad{background:var(--badbg);color:var(--bad)} .box.warn{background:var(--warnbg);color:var(--warn)}
.scroll{overflow-x:auto} table{border-collapse:collapse;width:100%;font-size:.92rem;margin:6px 0}
th,td{padding:7px 9px;border-bottom:1px solid var(--line);text-align:right} th{background:#eef1f5;font-weight:600}
.lim{color:var(--muted);font-size:.9rem}
.dec{border:1px solid var(--line);border-radius:10px;padding:8px 14px;margin:10px 0;break-inside:avoid}
.dec h3{margin:4px 0 6px}
.tag{display:inline-block;font-size:.8rem;font-weight:600;border-radius:6px;padding:0 8px;margin-inline-end:6px;background:#eef1f5;color:var(--muted)}
.tag.ok{background:#e6f4ea;color:#1e6b33}
footer{color:var(--muted);font-size:.85rem;margin-top:26px;border-top:1px solid var(--line);padding-top:10px}
@media print{body{background:#fff}main{padding:0;max-width:none}h2{break-after:avoid}table,.box{break-inside:avoid}}
"""


def rows_table(header, rows):
    head = "".join(f"<th>{h}</th>" for h in header)
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return f'<div class="scroll"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def decisions(items):
    """items: [(title, question, our suggestion)]. Stacked blocks so they read well on mobile."""
    return "".join(
        f'<div class="dec"><h3>{i}. {title}</h3><p><span class="tag">السؤال</span> {question}</p>'
        f'<p><span class="tag ok">اقتراحنا</span> {suggestion}</p></div>'
        for i, (title, question, suggestion) in enumerate(items, start=1))


def build():
    d = compute()
    raw_rows = sum(1 for _ in open(ROOT / "data" / "raw" / "alzahraa_pharmacy_sales_2025_2026.csv", encoding="utf-8")) - 1
    removed = pd.read_csv(CLEAN_DIR / "removed_rows.csv", dtype=str, keep_default_na=False)
    changes = pd.read_csv(CLEAN_DIR / "cleaning_changes.csv", dtype=str, keep_default_na=False)
    review = pd.read_csv(CLEAN_DIR / "client_review.csv", dtype=str, keep_default_na=False)
    flags = review.review_flags.str.split(" | ", regex=False).explode().value_counts()
    flag = lambda text: int(flags[[i for i in flags.index if text in i]].sum())

    rev, tot, months = d["rev"], d["rev_total"], d["months"]
    doc = d["doc"].sort_values("disc_rate", ascending=False)
    hi, rest = doc.iloc[0], doc.iloc[1:]
    base_rate = rest.disc_cost.sum() / rest.gross.sum()
    excess_year = (hi.disc_cost - hi.gross * base_rate) * 12 / d["n_months"]
    exp, p, pay, fc = d["exp"], d["price"], d["pay"], d["fc"]
    elec = pay["InstaPay"] + pay["Wallet"]
    q = fc.groupby("branch")[["low", "mid", "high"]].sum()
    pct = lambda b: (q.loc[b, "high"] - q.loc[b, "mid"]) / q.loc[b, "mid"] * 100
    top6 = d["top_all"].head(6).index.tolist()
    peak_normal = d["hour_normal"].sum(axis=1).idxmax()
    peak_rate = max(d["hour_normal"].values.max(), d["hour_ramadan"].values.max())
    ru, rr = (p["u1"] / p["u0"] - 1) * 100, (p["rev1"] / p["rev0"] - 1) * 100
    low_month = (rev[M] / rev[K]).idxmin()
    # adjusted Mut forecast: if the weakest month was an exception, replace it with the mean of the other quarter months of the same year
    fm = fc[fc.branch == M]
    low_in_q = fm[fm.m == low_month.month]
    if len(low_in_q):
        others = fm[fm.m != low_month.month]
        adj_quarter = (others.last_year.sum() + others.last_year.mean()) * fm.growth.iloc[0]
    else:
        adj_quarter = q.loc[M, "mid"]

    doc_rows = [(DOCTOR_AR[r.pharmacist], BRANCH_AR[r.branch], "صبح" if r["shift"] == "morning" else "ليل", n0(r.revenue),
                 n0(r.invoices), n0(r.avg_invoice), f"{r.disc_rate:.1f}%", n0(r.disc_year))
                for _, r in d["doc"].sort_values(["shift", "branch"]).iterrows()]
    fc_rows = [(BRANCH_AR[r.branch], f"{MONTH_AR[r.m]} {r.year}", n0(r.low), f"<b>{n0(r.mid)}</b>", n0(r.high)) for r in fc.itertuples()]
    fc_rows += [(f"<b>{BRANCH_AR[b]}</b>", "<b>إجمالي الربع</b>", n0(q.loc[b, "low"]), f"<b>{n0(q.loc[b, 'mid'])}</b>", n0(q.loc[b, "high"]))
                for b in (K, M)]

    return f"""<!doctype html>
<html lang="ar" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>التقرير النهائي - صيدلية الزهراء</title><style>{CSS}</style></head><body><main>

<h1>تقرير تحليل مبيعات صيدلية الزهراء</h1>
<p class="sub">الفرعين: الخارجة وموط - الداخلة · من {d['start']:%Y-%m-%d} إلى {d['end']:%Y-%m-%d} ({d['n_months']} شهر)</p>

<h2>أهم 5 حاجات</h2>
<ol>
<li><b>{exp['rows']} مرة اتباع دوا بعد انتهاء صلاحيته</b> ({exp['units']} علبة). موزعين على الفرعين والأربع دكاترة،
يعني محتاجين نظام متابعة للصلاحية مش محاسبة شخص. التفاصيل في تقرير الصلاحية.</li>
<li><b>{DOCTOR_AR[hi.pharmacist]} بيدّي خصومات 3 أضعاف زمايله</b>: {hi.disc_rate:.1f}% من بيعه مقابل حوالي {base_rate * 100:.1f}%.
ده بيكلّف حوالي <b>{n0(hi.disc_year)} جنيه في السنة</b>، منهم حوالي {n0(excess_year)} زيادة عن معدل الباقي. هل ده بتعليمات منك؟</li>
<li><b>الخارجة بتبيع أكتر من موط بحوالي {(tot[K] / tot[M] - 1) * 100:.0f}%</b> ({n0(tot[K])} مقابل {n0(tot[M])} جنيه)،
والسبب إن عملاءها أكتر، مش إن الفاتورة أكبر.</li>
<li><b>زيادة الأسعار 12% في يناير ما قللتش البيع</b>: الكميات {ru:+.1f}% والإيراد {rr:+.1f}% (صيف {p['y1']} مقابل صيف {p['y0']}).</li>
<li><b>المتوقع لأكتوبر–ديسمبر {p['y1']}</b>: الخارجة حوالي {n0(q.loc[K, 'mid'])} جنيه، وموط حوالي {n0(q.loc[M, 'mid'])} جنيه.</li>
</ol>

<h2>إجابات أسئلتك العشرة</h2>

<h3>1) إيراد كل فرع</h3>
<p>الخارجة أعلى في <b>{d['k_wins']} شهر من {len(months)}</b>. الفرق مش ثابت: الخارجة بين {d['ratio_min']:.2f} و{d['ratio_max']:.2f} مرة قد موط.
عدد فواتير الخارجة {n0(d['inv_by_branch'][K])} وموط {n0(d['inv_by_branch'][M])}، ومتوسط الفاتورة متقارب
({n0(tot[K] / d['inv_by_branch'][K])} و{n0(tot[M] / d['inv_by_branch'][M])} جنيه).
أضعف شهر لموط كان {MONTH_AR[low_month.month]} {low_month.year} ({n0(rev[M][low_month])} جنيه): عدد العملاء ما قلّش، بس بيع الأصناف الغالية نزل.</p>
<p class="lim">ملحوظة: ده إيراد مش ربح. عشان نعرف أنهي فرع بيكسب أكتر محتاجين تكلفة البضاعة والإيجار والمرتبات.</p>

<h3>2) أعلى الأصناف والراكد</h3>
<p>أعلى 6 أصناف بالفلوس هم نفسهم في الفرعين: {"، ".join(top6)}.
أكتر صنف بيتباع بالعدد هو محلول الجفاف ORS، بس فلوسه قليلة لأنه رخيص.
<b>مفيش ولا صنف راكد</b>: كل الأصناف اتباعت في الفرعين خلال آخر {d['max_idle_days']} يوم. أقل الأصناف حركة موجودة في الداشبورد للمتابعة.</p>

<h3>3) المواسم</h3>
{rows_table(["الصنف", "الموسم", "اطلب البضاعة في"], [
    ("أدوية البرد", "أكتوبر إلى مارس، والقمة يناير", "سبتمبر"),
    ("محلول الجفاف ORS و Antinal", "مايو إلى سبتمبر", "أبريل"),
    ("واقي الشمس", "يونيو إلى سبتمبر", "مايو")])}

<h3>4) أداء الدكاترة</h3>
<p>الإيراد بيفرق حسب <b>الفرع والشيفت</b> مش حسب الدكتور: الليل بيبيع أكتر من ضعف الصبح في الفرعين.
فالمقارنة العادلة صبح بصبح وليل بليل. ومتوسط الفاتورة واحد تقريباً عند الأربعة. الفرق الوحيد الواضح هو الخصومات.</p>
{rows_table(["الدكتور", "الفرع", "الشيفت", "الإيراد", "الفواتير", "متوسط الفاتورة", "الخصم من البيع", "تكلفة الخصم في السنة"], doc_rows)}

<h3>5) الزحمة، رمضان، والأعياد</h3>
<p>الزحمة العادية حوالين الساعة {peak_normal} بالليل. في رمضان النهار بيهدى جداً والبيع بيتنقل لبعد الفطار (8 إلى 11 بالليل).
الجمعة والأعياد أهدى من باقي الأيام.
<b>مش محتاج دكتور زيادة</b>: أعلى معدل في أي ساعة {peak_rate:.1f} فاتورة. الأنسب تعديل مواعيد الشيفت في رمضان.</p>

<h3>6) أثر زيادة يناير</h3>
<p>الزيادة 12% اتطبقت على كل الأصناف. مقارنة يونيو–سبتمبر في السنتين: عدد العلب من {n0(p['u0'])} لـ {n0(p['u1'])} ({ru:+.1f}%)،
والإيراد من {n0(p['rev0'])} لـ {n0(p['rev1'])} جنيه ({rr:+.1f}%). يعني العملاء كملوا يشتروا بنفس الكمية.</p>

<h3>7) الدفع الإلكتروني</h3>
<p>InstaPay والمحافظ طلعوا من <b>{elec.iloc[0]:.0f}%</b> من الفواتير في أول شهر لـ <b>{elec.iloc[-1]:.0f}%</b> في آخر شهر
(InstaPay {pay['InstaPay'].iloc[-1]:.1f}% ومحافظ {pay['Wallet'].iloc[-1]:.1f}%). مفيش فرق بين الفرعين.</p>

<h3>8) الصلاحية</h3>
<div class="box bad">⚠ {exp['rows']} مرة بيع بعد انتهاء الصلاحية، {exp['units']} علبة بقيمة {n0(exp['value'])} جنيه. اتسلّم فيها تقرير لوحده.</div>
<div class="box warn">ℹ فيه {exp['missing']} سطر تاريخ الصلاحية فيهم مش متسجل، فالرقم ده هو الحد الأدنى.</div>

<h3>9) المضادات الحيوية</h3>
<p>{d['ab_branch'][K]:.1f}% من سطور البيع في الخارجة و{d['ab_branch'][M]:.1f}% في موط (مفيش فرق).
بتزيد في الشتا: {d['ab_winter']:.1f}% من أكتوبر لمارس مقابل {d['ab_rest']:.1f}% باقي السنة. كل المضادات متسجلة "بروشتة" في الشيت.</p>

<h3>10) توقع أكتوبر–ديسمبر {p['y1']}</h3>
{rows_table(["الفرع", "الشهر", "أقل", "المتوقع", "أعلى"], fc_rows)}
<p class="lim">التوقع = إيراد نفس الشهر السنة اللي فاتت × معدل النمو. مدى موط أوسع (±{pct(M):.0f}% مقابل ±{pct(K):.0f}%) لأن مبيعاتها متذبذبة أكتر.
ده توقع تقريبي للتخطيط، مبني على {d['n_months']} شهر بس.</p>

<h2>اللي عملناه في الشيت</h2>
<ul>
<li>الشيت كان <b>{n0(raw_rows)} سطر</b>، وبقى <b>{n0(d['lines'])}</b> بعد ما شلنا <b>{len(removed)} سطر مكرر</b>. السطور المكررة كانت مكبّرة الإيراد بحوالي 38,850 جنيه.</li>
<li>صلّحنا <b>{n0(len(changes))} خانة</b>: أسماء فروع وأصناف مكتوبة بأكتر من شكل، تواريخ بصيغ مختلفة، أسعار وكميات وإجماليات مش راكبة على بعض.</li>
<li>الشيت الأصلي ما اتلمسش. وكل سطر اتشال وكل خانة اتغيرت متسجلين بالسبب في ورقة التنضيف.</li>
</ul>

<h2>محتاجين منك قرار</h2>
<p>لكل بند: السؤال، واقتراحنا لو مفيش عندك معلومة تانية. القرار النهائي ليك.</p>
{decisions([
    (f"مرتجعات ({flag('مرتجع')} سطر)",
     "مقدرناش نوصلهم بفواتير البيع الأصلية. نحسبهم إزاي؟",
     "يفضلوا مخصومين من الإيراد زي ما هم دلوقتي. ومن النهارده أي مرتجع يتكتب عليه رقم فاتورة البيع الأصلية."),
    (f"إجمالي كان ضعف أو 3 أضعاف المحسوب ({flag('الإجمالي كان')} سطر)",
     "الكمية كانت غلط ولا الإجمالي؟",
     "نعتمد الإجمالي المحسوب من السعر والكمية (ده اللي في الشيت النضيف). ولو حابب تتأكد، راجع أكبر 5 سطور منهم على جرد المخزون."),
    (f"طريقة دفع مش متسجلة ({flag('طريقة دفع')} فاتورة)",
     "مفيش طريقة نعرفها بيها دلوقتي.",
     "تفضل «غير معروف» ومتدخلش في نسبة الدفع الإلكتروني. وخانة طريقة الدفع تبقى إجبارية في السيستم."),
    (f"تاريخ صلاحية مش متسجل ({flag('صلاحية')} سطر)",
     "مقدرناش نعرف الأصناف دي كانت سليمة ولا منتهية.",
     "تفضل فاضية (مينفعش نخمّنها). وخانة تاريخ الصلاحية تبقى إجبارية في السيستم."),
    ("سعرين لنفس الصنف، بفرق 5% (حوالي ربع السطور)",
     "ده بسبب تشغيلات مختلفة بأسعار مختلفة؟",
     "لو آه: يتساب زي ما هو. لو لأ: قايمة أسعار واحدة في السيستم للفرعين، والسعر ميتكتبش باليد."),
    (f"خصومات {DOCTOR_AR[hi.pharmacist]} ({hi.disc_rate:.1f}% من بيعه مقابل حوالي {base_rate * 100:.1f}% عند الباقي)",
     "ده بتعليمات منك؟",
     f"سياسة خصم واحدة ومكتوبة للأربع دكاترة: الخصم لمين وبكام. ومتابعتها كل شهر من الداشبورد. "
     f"لو خصوماته رجعت لمعدل زمايله، التوفير حوالي {n0(excess_year)} جنيه في السنة."),
    (f"موط في {MONTH_AR[low_month.month]} {low_month.year} ({n0(rev[M][low_month])} جنيه)",
     "كان فيه نقص في الأصناف الغالية (السكر، الفيتامينات، مستلزمات الأطفال)؟",
     f"لو آه: حد أدنى للمخزون من الأصناف دي في موط قبل الشتا، وساعتها المتوقع لربع موط يبقى حوالي {n0(adj_quarter)} جنيه "
     f"بدل {n0(q.loc[M, 'mid'])}. لو لأ: التوقع يفضل زي ما هو."),
])}
<p class="lim">السطور نفسها في ملف client_review.csv.</p>

<h2>نقترح إيه</h2>
<ol>
<li><b>الصلاحية:</b> جرد فوري للفرعين، وتنبيه في السيستم يمنع بيع صنف منتهي، وجرد شهري للي فاضل عليه 3 شهور.</li>
<li><b>الخصومات:</b> سياسة مكتوبة وواحدة للأربع دكاترة.</li>
<li><b>السيستم:</b> تاريخ الصلاحية وطريقة الدفع خانات إجبارية، والفرع والصنف من قايمة اختيار مش كتابة باليد.</li>
<li><b>المخزون:</b> طلب أدوية البرد في سبتمبر، وORS في أبريل، وواقي الشمس في مايو.</li>
<li><b>رمضان:</b> تعديل مواعيد الشيفت بدل دكتور زيادة.</li>
<li><b>الدفع:</b> QR لـ InstaPay ورقم محفظة ظاهرين في الفرعين، والتقفيل اليومي يشمل الإلكتروني.</li>
</ol>

<h2>حدود التقرير</h2>
<ul class="lim">
<li>الداتا {d['n_months']} شهر: شتا واحد كامل ورمضان واحد. المواسم واضحة، بس مش مضمون تتكرر بنفس الأرقام.</li>
<li>الشيت فيه مبيعات بس. مفيش تكلفة ولا مخزون، فمقدرناش نحسب ربح ولا نعرف سبب نقص صنف.</li>
<li>الأرقام بتقول إيه اللي حصل، ومبتقولش ليه. الأسباب عندك إنت والدكاترة.</li>
</ul>

<h2>اللي اتسلّم</h2>
<ul>
<li>الشيت النضيف: alzahraa_sales_clean.csv</li>
<li>ورقة التنضيف: cleaning_summary.csv و cleaning_changes.csv و removed_rows.csv و client_review.csv</li>
<li>تقرير الصلاحية: expiry_report.html و expiry_report.xlsx</li>
<li>الداشبورد: dashboard.html (بيفتح على الموبايل ومن غير إنترنت)</li>
<li>الكود: بيتشغل على شيت كل شهر ويطلّع نفس الملفات.</li>
</ul>

<footer>الأرقام من شيت المبيعات بعد التنضيف. المرتجعات مخصومة من الإيراد.</footer>
</main></body></html>"""


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "final_report.html"
    path.write_text(build(), encoding="utf-8")
    print("saved:", path, f"({path.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
