"""Expiry report: question 8 (the client's top priority).

Reads the clean sheet and writes:
  reports/expiry/expiry_report.xlsx   details (for the client; includes customer phones for follow-up)
  reports/expiry/expiry_report.html   plain Arabic summary that opens on mobile (no phones)

Usage:  .venv\Scripts\python.exe scripts\expiry_report.py
"""
from html import escape
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CLEAN = ROOT / "data" / "clean" / "alzahraa_sales_clean.csv"
OUT = ROOT / "reports" / "expiry"

BRANCH_AR = {"Kharga": "الخارجة", "Mut - Dakhla": "موط - الداخلة"}
from config import DOCTOR_AR  # noqa: E402  (real names live in config_local.py, git-ignored)
SHIFT_AR = {"morning": "صبح", "night": "ليل"}
NEAR_DAYS = 90


def build():
    c = pd.read_csv(CLEAN, dtype={"customer_phone": str})
    sales = c[~c.is_return]
    exp = sales[sales.sold_after_expiry].copy()
    exp["days_late"] = (-exp.days_to_expiry).astype(int)
    missing = sales[sales.expiry_date.isna()]
    near = sales[(sales.days_to_expiry >= 0) & (sales.days_to_expiry <= NEAR_DAYS)]
    checked = sales[sales.expiry_date.notna()]

    def rate_table(by):
        t = checked.groupby(by).size().rename("سطور اتفحصت").to_frame()
        t["اتباع منتهي"] = exp.groupby(by).size()
        t["اتباع منتهي"] = t["اتباع منتهي"].fillna(0).astype(int)
        t["لكل 1000 سطر"] = (t["اتباع منتهي"] / t["سطور اتفحصت"] * 1000).round(2)
        t["قيمة البيع (جنيه)"] = exp.groupby(by)["line_total"].sum()
        t["قيمة البيع (جنيه)"] = t["قيمة البيع (جنيه)"].fillna(0).round(2)
        t["صلاحية مش متسجلة"] = missing.groupby(by).size()
        t["صلاحية مش متسجلة"] = t["صلاحية مش متسجلة"].fillna(0).astype(int)
        return t.reset_index()

    by_branch = rate_table("branch")
    by_doctor = rate_table(["branch", "pharmacist", "shift"])
    by_product = (exp.groupby(["product_name", "category"])
                  .agg(مرات=("invoice_id", "size"), علب=("quantity", "sum"), قيمة=("line_total", "sum"),
                       أقصى_تأخير_يوم=("days_late", "max")).reset_index()
                  .sort_values(["مرات", "قيمة"], ascending=False))
    by_month = exp.groupby(exp.sale_date.str[:7]).size().rename("سطور").rename_axis("الشهر").reset_index()

    detail_cols = ["invoice_id", "line_no", "sale_date", "sale_time", "branch", "pharmacist", "shift",
                   "product_name", "category", "prescription_required", "quantity", "unit_price", "line_total",
                   "expiry_date", "days_late", "customer_phone", "csv_row"]
    detail = exp.sort_values("sale_date")[detail_cols]
    miss_detail = missing.sort_values("sale_date")[[
        "invoice_id", "line_no", "sale_date", "sale_time", "branch", "pharmacist", "product_name",
        "quantity", "line_total", "customer_phone", "csv_row"]]
    near_detail = near.sort_values("days_to_expiry")[[
        "invoice_id", "sale_date", "branch", "pharmacist", "product_name", "quantity", "expiry_date", "days_to_expiry"]]

    k = {
        "rows": len(exp), "invoices": exp.invoice_id.nunique(), "units": int(exp.quantity.sum()),
        "value": float(exp.line_total.sum()), "rx": int((exp.prescription_required == "Yes").sum()),
        "with_phone": int(exp.customer_phone.notna().sum()), "max_late": int(exp.days_late.max()),
        "min_late": int(exp.days_late.min()), "median_late": int(exp.days_late.median()),
        "mean_late": int(round(exp.days_late.mean())),
        "missing": len(missing), "missing_value": float(missing.line_total.sum()),
        "checked": len(checked), "near": len(near),
        "first": exp.sale_date.min(), "last": exp.sale_date.max(),
        "period_start": c.sale_date.min(), "period_end": c.sale_date.max(),
    }
    return k, detail, by_branch, by_doctor, by_product, by_month, miss_detail, near_detail


def write_excel(k, detail, by_branch, by_doctor, by_product, by_month, miss_detail, near_detail):
    summary = pd.DataFrame([
        ("الفترة", f"{k['period_start']} → {k['period_end']}"),
        ("سطور بيع اتفحصت (فيها تاريخ صلاحية)", k["checked"]),
        ("سطور اتباعت بعد انتهاء الصلاحية", k["rows"]),
        ("عدد الفواتير", k["invoices"]),
        ("عدد العلب", k["units"]),
        ("قيمة البيع (جنيه)", round(k["value"], 2)),
        ("منهم أدوية بروشتة", k["rx"]),
        ("أقل / وسيط / أقصى تأخير (يوم)", f"{k['min_late']} / {k['median_late']} / {k['max_late']}"),
        ("عملاء معروف موبايلهم (ممكن التواصل)", k["with_phone"]),
        ("سطور من غير تاريخ صلاحية (مقدرناش نحكم عليها)", k["missing"]),
        (f"سطور اتباعت وفاضل على صلاحيتها {NEAR_DAYS} يوم أو أقل", k["near"]),
    ], columns=["البند", "القيمة"])
    sheets = {"الملخص": summary, "التفاصيل": detail, "حسب الفرع": by_branch, "حسب الدكتور": by_doctor,
              "حسب الصنف": by_product, "حسب الشهر": by_month, "صلاحية مش متسجلة": miss_detail,
              "قرب الانتهاء": near_detail}
    path = OUT / "expiry_report.xlsx"
    with pd.ExcelWriter(path, engine="openpyxl") as xw:
        for name, frame in sheets.items():
            frame.to_excel(xw, sheet_name=name, index=False)
            ws = xw.sheets[name]
            ws.sheet_view.rightToLeft = True
            ws.freeze_panes = "A2"
            for i, col in enumerate(frame.columns, start=1):
                w = max([len(str(col))] + [len(str(v)) for v in frame[col].head(300)])
                ws.column_dimensions[ws.cell(row=1, column=i).column_letter].width = min(max(w + 3, 10), 50)
    return path


def table_html(frame):
    head = "".join(f"<th>{escape(str(c))}</th>" for c in frame.columns)
    body = "".join("<tr>" + "".join(f"<td>{escape(str(v))}</td>" for v in row) + "</tr>"
                   for row in frame.itertuples(index=False))
    return f'<div class="scroll"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def write_html(k, detail, by_branch, by_doctor, by_product):
    d = detail.copy()
    d["branch"] = d.branch.map(BRANCH_AR)
    d["pharmacist"] = d.pharmacist.map(DOCTOR_AR)
    d = d[["sale_date", "sale_time", "branch", "pharmacist", "product_name", "quantity", "expiry_date", "days_late", "invoice_id"]]
    d.columns = ["تاريخ البيع", "الوقت", "الفرع", "الدكتور", "الصنف", "الكمية", "انتهاء الصلاحية", "متأخر (يوم)", "الفاتورة"]

    b = by_branch.copy()
    b["branch"] = b.branch.map(BRANCH_AR)
    b = b.rename(columns={"branch": "الفرع"})

    doc = by_doctor.copy()
    doc["branch"] = doc.branch.map(BRANCH_AR)
    doc["pharmacist"] = doc.pharmacist.map(DOCTOR_AR)
    doc["shift"] = doc["shift"].map(SHIFT_AR)
    doc = doc.rename(columns={"branch": "الفرع", "pharmacist": "الدكتور", "shift": "الشيفت"})

    p = by_product.rename(columns={"product_name": "الصنف", "category": "التصنيف", "قيمة": "القيمة (جنيه)",
                                   "أقصى_تأخير_يوم": "أقصى تأخير (يوم)"}).copy()
    p["القيمة (جنيه)"] = p["القيمة (جنيه)"].round(2)

    html = f"""<!doctype html>
<html lang="ar" dir="rtl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>تقرير الصلاحية - صيدلية الزهراء</title>
<style>
:root{{--bg:#f6f7f9;--card:#fff;--ink:#1c2430;--muted:#5b6675;--line:#e2e6ec;--bad:#b3261e;--warn:#8a5a00;--badbg:#fdecea;--warnbg:#fff4dc}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--ink);font-family:"Segoe UI",Tahoma,Arial,sans-serif;line-height:1.7}}
main{{max-width:900px;margin:0 auto;padding:16px}}
h1{{font-size:1.5rem;margin:8px 0 4px}} h2{{font-size:1.15rem;margin:28px 0 10px}}
.sub{{color:var(--muted);margin:0 0 16px}}
.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px}}
.card b{{display:block;font-size:1.7rem;line-height:1.2}} .card span{{color:var(--muted);font-size:.9rem}}
.card.bad b{{color:var(--bad)}}
.note{{border-radius:12px;padding:12px 14px;margin:14px 0}}
.note.bad{{background:var(--badbg);color:var(--bad)}} .note.warn{{background:var(--warnbg);color:var(--warn)}}
.scroll{{overflow-x:auto;background:var(--card);border:1px solid var(--line);border-radius:12px}}
table{{border-collapse:collapse;width:100%;font-size:.92rem;white-space:nowrap}}
th,td{{padding:8px 10px;border-bottom:1px solid var(--line);text-align:right}}
th{{background:#eef1f5;font-weight:600}} tr:last-child td{{border-bottom:0}}
ol{{padding-inline-start:22px}} li{{margin-bottom:6px}}
footer{{color:var(--muted);font-size:.85rem;margin:28px 0 12px}}
</style></head><body><main>
<h1>تقرير الأدوية اللي اتباعت بعد انتهاء صلاحيتها</h1>
<p class="sub">صيدلية الزهراء · الفرعين · من {k['period_start']} إلى {k['period_end']}</p>

<div class="note bad"><b>الخلاصة:</b> لقينا <b>{k['rows']}</b> مرة اتباع فيها دوا بعد تاريخ انتهاء صلاحيته،
بإجمالي <b>{k['units']}</b> علبة وقيمة <b>{k['value']:,.0f}</b> جنيه. منهم <b>{k['rx']}</b> أدوية بروشتة.</div>

<div class="cards">
<div class="card bad"><b>{k['rows']}</b><span>مرة بيع بعد الانتهاء</span></div>
<div class="card"><b>{k['units']}</b><span>علبة</span></div>
<div class="card"><b>{k['value']:,.0f}</b><span>جنيه قيمة البيع</span></div>
<div class="card"><b>{k['mean_late']}</b><span>يوم متوسط التأخير (من {k['min_late']} إلى {k['max_late']})</span></div>
<div class="card"><b>{k['with_phone']}</b><span>عميل معروف رقمه</span></div>
</div>

<div class="note warn"><b>مهم:</b> فيه <b>{k['missing']}</b> سطر بيع تاريخ الصلاحية فيهم مش متسجل،
فمقدرناش نحكم عليهم. يعني الرقم {k['rows']} هو <b>الحد الأدنى</b>، والحقيقي ممكن يبقى أكتر.</div>

<h2>فين؟ (حسب الفرع)</h2>
{table_html(b)}

<h2>مع مين؟ (حسب الدكتور)</h2>
<p class="sub">عمود "لكل 1000 سطر" بيخلّي المقارنة عادلة، لأن كل دكتور بيبيع عدد مختلف.</p>
{table_html(doc)}
<div class="note warn"><b>تنبيه للإنصاف:</b> الأعداد صغيرة (من 3 إلى 6 حالات لكل دكتور)، فالفرق بين الدكاترة
مش كفاية نحكم بيه إن حد أسوأ من حد. الحالات موزعة على الأربعة وعلى الفرعين، وده معناه إن المشكلة
في <b>نظام متابعة الصلاحية</b> مش في شخص بعينه.</div>

<h2>أنهي أصناف؟</h2>
{table_html(p)}

<h2>إمتى؟ (كل الحالات بالتفصيل)</h2>
{table_html(d)}

<h2>نقترح إيه</h2>
<ol>
<li><b>التواصل مع العملاء:</b> {k['with_phone']} من الحالات رقم موبايل العميل متسجل. الأرقام في ملف Excel المرفق.</li>
<li><b>جرد فوري للرفوف</b> في الفرعين على الأصناف اللي في الجدول، وسحب أي علبة منتهية.</li>
<li><b>تاريخ الصلاحية يبقى خانة إجبارية</b> في السيستم، عشان مفيش بيعة تعدّي من غيره.</li>
<li><b>تنبيه في السيستم</b> يمنع أو يحذّر عند بيع صنف منتهي.</li>
<li><b>جرد شهري</b> للأصناف اللي فاضل على صلاحيتها 3 شهور أو أقل.</li>
</ol>

<footer>الأرقام دي من الشيت بعد التنضيف (إزالة السطور المكررة وتصحيح تواريخ البيع الغلط).
المرتجعات مش محسوبة. التفاصيل الكاملة في ملف expiry_report.xlsx.</footer>
</main></body></html>"""
    path = OUT / "expiry_report.html"
    path.write_text(html, encoding="utf-8")
    return path


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    k, detail, by_branch, by_doctor, by_product, by_month, miss_detail, near_detail = build()
    x = write_excel(k, detail, by_branch, by_doctor, by_product, by_month, miss_detail, near_detail)
    h = write_html(k, detail, by_branch, by_doctor, by_product)
    pd.set_option("display.width", 250)
    print(k)
    print(by_branch.to_string(index=False))
    print(by_doctor.to_string(index=False))
    print(by_product.to_string(index=False))
    print(by_month.to_string(index=False))
    print("saved:", x, h)


if __name__ == "__main__":
    main()
