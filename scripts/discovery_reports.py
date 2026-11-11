"""Discovery reports: writes an Excel workbook with data-exploration sheets.

Read-only: nothing in data/raw is modified and no cleaning is done. Output goes to reports/discovery/ (git-ignored).
Usage:  .venv\Scripts\python.exe scripts\discovery_reports.py
"""
from pathlib import Path

import numpy as np
import pandas as pd

RAW = Path(r"D:\pharmacy_data\data\raw\alzahraa_pharmacy_sales_2025_2026.csv")
OUT_DIR = Path(r"D:\pharmacy_data\reports\discovery")
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT = OUT_DIR / "discovery_report.xlsx"

df = pd.read_csv(RAW, dtype=str, keep_default_na=False)
COLS = list(df.columns)
rownum = pd.Series(np.arange(2, len(df) + 2), index=df.index, name="csv_row")  # row number in the CSV (header = 1)

NUMERIC = ["line_no", "unit_price", "quantity", "discount_pct", "line_total"]
d = pd.DataFrame(index=df.index)
for c in NUMERIC:
    d[c] = pd.to_numeric(df[c], errors="coerce")
d["sale_dt"] = pd.to_datetime(df["sale_date"], format="%Y-%m-%d", errors="coerce")
d["expiry_dt"] = pd.to_datetime(df["expiry_date"], format="%Y-%m-%d", errors="coerce")
d["hour"] = pd.to_datetime(df["sale_time"], format="%H:%M", errors="coerce").dt.hour
d["month"] = d.sale_dt.dt.to_period("M").astype(str)
d["shift"] = np.select([d.hour.isna(), d.hour < 16], ["?", "morning"], "night")


def mask_phone(s):
    s = s.copy()
    ok = s.str.len() >= 8
    s[ok] = s[ok].str[:4] + "****" + s[ok].str[-3:]
    return s


def rows(idx, extra=None):
    """Rows from the original sheet (with row number, phone masked) plus extra columns."""
    out = pd.concat([rownum.loc[idx], df.loc[idx, COLS]], axis=1)
    out["customer_phone"] = mask_phone(out["customer_phone"])
    if extra is not None:
        out = pd.concat([out, extra.loc[idx]], axis=1)
    return out.reset_index(drop=True)


sheets = {}

# ── 01 columns overview
sheets["01_columns_overview"] = pd.DataFrame({
    "unique": df.nunique(),
    "empty": df.apply(lambda s: s.str.strip().eq("").sum()),
    "edge_spaces": df.apply(lambda s: (s != s.str.strip()).sum()),
    "arabic_rows": df.apply(lambda s: s.str.contains(r"[\u0600-\u06FF]", regex=True).sum()),
    "non_ascii_rows": df.apply(lambda s: s.str.contains(r"[^\x00-\x7F]", regex=True).sum()),
    "min_len": df.apply(lambda s: s.str.len().min()),
    "max_len": df.apply(lambda s: s.str.len().max()),
}).rename_axis("column").reset_index()

# ── 02 value counts for low-cardinality columns (repr reveals hidden spaces and characters)
parts = []
for c in ["pharmacy", "branch", "pharmacist", "category", "payment_method",
          "prescription_required", "discount_pct", "quantity", "line_no"]:
    vc = df[c].value_counts(dropna=False)
    parts.append(pd.DataFrame({"column": c, "value_repr": [repr(v) for v in vc.index],
                               "count": vc.values, "pct": (vc.values / len(df) * 100).round(3)}))
sheets["02_value_counts"] = pd.concat(parts, ignore_index=True)

# ── 03 products
d["period"] = np.where(d.sale_dt >= "2026-01-01", "post_2026-01", "pre_2026-01")
norm = df.product_name.str.lower().str.replace(r"\s+", " ", regex=True).str.strip()
prod = df.assign(norm=norm).groupby("product_name").agg(
    rows=("category", "size"),
    categories=("category", lambda s: " | ".join(sorted(s.unique()))),
    n_categories=("category", "nunique"),
    norm_key=("norm", "first"),
)
prod["median_price_pre"] = d[d.period == "pre_2026-01"].groupby(df.product_name)["unit_price"].median()
prod["median_price_post"] = d[d.period == "post_2026-01"].groupby(df.product_name)["unit_price"].median()
prod["post_vs_pre"] = (prod.median_price_post / prod.median_price_pre).round(3)
prod["spellings_for_same_key"] = prod.groupby("norm_key")["rows"].transform("size")
sheets["03_products"] = prod.reset_index().sort_values(["spellings_for_same_key", "n_categories", "rows"],
                                                      ascending=False)

# ── 04 branch × pharmacist × shift
sheets["04_branch_doctor_shift"] = (
    pd.crosstab([df.branch.map(repr), df.pharmacist.map(repr)], d["shift"]).reset_index())

# ── 05 numeric columns summary
num_rows = []
for c in NUMERIC:
    s = df[c]
    r = {"column": c, "not_numeric": int((d[c].isna() & s.str.strip().ne("")).sum()),
         "empty": int(s.str.strip().eq("").sum()), "negative": int((d[c] < 0).sum()),
         "zero": int((d[c] == 0).sum()), "mean": d[c].mean()}
    for q in [0, .001, .01, .05, .25, .5, .75, .95, .99, .999, 1]:
        r[f"q{q}"] = d[c].quantile(q)
    num_rows.append(r)
sheets["05_numeric_summary"] = pd.DataFrame(num_rows)

# ── 06 equation check: line_total = qty × price × (1 - disc/100)
expected = (d.quantity * d.unit_price * (1 - d.discount_pct / 100)).round(2)
diff = (d.line_total - expected)
chk = pd.DataFrame({"expected": expected, "diff": diff.round(2), "abs_diff": diff.abs().round(2)})
bad = chk[(chk.abs_diff > 0.02) | chk.abs_diff.isna()].sort_values("abs_diff", ascending=False)
sheets["06_line_total_check"] = rows(bad.index[:2000], chk)
sheets["06a_line_total_summary"] = pd.DataFrame({
    "metric": ["rows_total", "match_within_0.02", "mismatch", "not_computable"],
    "count": [len(df), int((chk.abs_diff <= 0.02).sum()), int((chk.abs_diff > 0.02).sum()),
              int(chk.abs_diff.isna().sum())]})

# ── 07 dates: shapes + parse failures + range
def shape_of(s):
    return (s.str.replace(r"[0-9]", "9", regex=True).str.replace(r"[A-Za-z]", "A", regex=True)
             .str.replace(r"[\u0600-\u06FF]", "ع", regex=True))

parts = []
for c in ["sale_date", "sale_time", "expiry_date"]:
    vc = shape_of(df[c]).value_counts()
    parts.append(pd.DataFrame({"column": c, "shape": vc.index, "count": vc.values}))
sheets["07_date_shapes"] = pd.concat(parts, ignore_index=True)
fail = []
for c, parsed in [("sale_date", d.sale_dt), ("expiry_date", d.expiry_dt)]:
    m = df[c].str.strip().ne("") & parsed.isna()
    fail.append(pd.DataFrame({"column": c, "csv_row": rownum[m], "value": df.loc[m, c]}))
m = df.sale_time.str.strip().ne("") & d.hour.isna()
fail.append(pd.DataFrame({"column": "sale_time", "csv_row": rownum[m], "value": df.loc[m, "sale_time"]}))
oow = d.sale_dt.notna() & ((d.sale_dt < "2025-06-01") | (d.sale_dt > "2026-09-30"))
fail.append(pd.DataFrame({"column": "sale_date_out_of_range", "csv_row": rownum[oow], "value": df.loc[oow, "sale_date"]}))
sheets["07a_date_failures"] = pd.concat(fail, ignore_index=True)

# ── 08 time: month × branch, weekday, hour
g = d.assign(branch=df.branch, invoice=df.invoice_id).groupby(["month", "branch"]).agg(
    lines=("line_total", "size"), invoices=("invoice", "nunique"), revenue_raw=("line_total", "sum"))
sheets["08_month_branch"] = g.round(2).reset_index()
sheets["08a_weekday_branch"] = pd.crosstab(d.sale_dt.dt.day_name(), df.branch).reset_index()
sheets["08b_hour_branch"] = pd.crosstab(d.hour, df.branch).reset_index()

# ── 09 duplicates
key = ["invoice_id", "line_no"]
m_full = df.duplicated(keep=False)
m_key = df.duplicated(key, keep=False)
m_prod = df.duplicated(["invoice_id", "product_name"], keep=False)
flag = pd.DataFrame({"full_dup": m_full, "key_dup": m_key, "same_invoice_same_product": m_prod})
idx = flag[flag.any(axis=1)].index
dup = rows(idx, flag)
sheets["09_duplicates"] = dup.sort_values(["invoice_id", "line_no", "csv_row"])
sheets["09a_duplicates_summary"] = pd.DataFrame({
    "check": ["full duplicate rows (extra copies)", "key (invoice_id+line_no) extra copies",
              "same invoice+product extra copies", "all cols except line_no",
              "all cols except invoice_id+line_no"],
    "count": [int(df.duplicated().sum()), int(df.duplicated(key).sum()),
              int(df.duplicated(["invoice_id", "product_name"]).sum()),
              int(df.drop(columns="line_no").duplicated().sum()),
              int(df.drop(columns=key).duplicated().sum())]})

# ── 10 consistency within a single invoice
inv = df.groupby("invoice_id").agg(
    lines=("line_no", "count"), dates=("sale_date", "nunique"), times=("sale_time", "nunique"),
    branches=("branch", "nunique"), doctors=("pharmacist", "nunique"),
    pays=("payment_method", "nunique"), phones=("customer_phone", "nunique"))
conf = inv[(inv.drop(columns="lines") > 1).any(axis=1)]
sheets["10_invoice_conflicts"] = conf.reset_index()
ln = d.assign(inv=df.invoice_id).groupby("inv")["line_no"].agg(["count", "min", "max"])
sheets["10a_line_no_sequence"] = ln[(ln["min"] != 1) | (ln["max"] != ln["count"])].reset_index()
nums = pd.to_numeric(df.invoice_id.str.extract(r"ZH-(\d+)")[0], errors="coerce").dropna().astype(int).unique()
sheets["10b_invoice_ids"] = pd.DataFrame({
    "metric": ["bad_format", "min_number", "max_number", "present", "missing_in_range"],
    "value": [int((~df.invoice_id.str.match(r"^ZH-\d{5}$")).sum()), nums.min(), nums.max(), len(nums),
              nums.max() - nums.min() + 1 - len(nums)]})

# ── 11 price vs the median of the same product and period
d["price_med"] = d.groupby([df.product_name, d.period])["unit_price"].transform("median")
d["price_ratio"] = (d.unit_price / d.price_med).round(3)
far = (d.price_ratio - 1).abs().sort_values(ascending=False).head(500).index
sheets["11_price_vs_median"] = rows(far, d[["price_med", "price_ratio"]])

# ── 12 outliers: IQR + largest values
def iqr_count(s, k):
    s = s.dropna()
    q1, q3 = s.quantile([.25, .75])
    i = q3 - q1
    return int(((s < q1 - k * i) | (s > q3 + k * i)).sum())

sheets["12_outlier_counts"] = pd.DataFrame(
    [{"column": c, "iqr_1.5": iqr_count(d[c], 1.5), "iqr_3": iqr_count(d[c], 3)}
     for c in ["unit_price", "quantity", "discount_pct", "line_total"]])
tops = []
for name, idx in [("largest_quantity", d.quantity.nlargest(100).index),
                  ("smallest_quantity", d.quantity.nsmallest(100).index),
                  ("largest_line_total", d.line_total.nlargest(100).index),
                  ("smallest_line_total", d.line_total.nsmallest(100).index)]:
    t = rows(idx)
    t.insert(0, "which", name)
    tops.append(t)
sheets["12a_extreme_rows"] = pd.concat(tops, ignore_index=True)
sheets["12b_quantity_by_category"] = (d.groupby(df.category)["quantity"]
                                      .describe().round(2).reset_index())

# ── 13 expiry (distribution only; the full report is phase 2)
days = (d.expiry_dt - d.sale_dt).dt.days
bins = [-np.inf, -365, -30, 0, 30, 90, 180, 365, 730, np.inf]
sheets["13_expiry_gap_days"] = (pd.cut(days, bins).value_counts(sort=False)
                                .rename_axis("days_expiry_minus_sale").reset_index(name="rows"))
sheets["13a_expiry_quantiles"] = days.quantile([0, .01, .05, .25, .5, .75, .95, 1]).rename("days").reset_index()

# ── 14 customers (phone masked)
ph = df.customer_phone
sheets["14_phone_shapes"] = (shape_of(ph).value_counts().rename_axis("shape").reset_index(name="count"))
known = ph[ph.str.strip().ne("")]
freq = known.value_counts()
sheets["14a_visits_distribution"] = (freq.value_counts().sort_index()
                                     .rename_axis("visits").reset_index(name="customers"))
top = freq.head(50)
sheets["14b_top_customers_masked"] = pd.DataFrame({"phone_masked": mask_phone(pd.Series(top.index)), "rows": top.values})

# ── 15 payment methods month by month
cnt = pd.crosstab(d.month, df.payment_method)
pct = (cnt.div(cnt.sum(axis=1), axis=0) * 100).round(2).add_suffix("_pct")
sheets["15_payment_by_month"] = pd.concat([cnt, pct], axis=1).reset_index()

# ── 16 values with non-ASCII characters or edge spaces
parts = []
for c in [c for c in COLS if c != "customer_phone"]:
    m = df[c].str.contains(r"[^\x00-\x7F]", regex=True) | (df[c] != df[c].str.strip())
    if m.any():
        vc = df.loc[m, c].value_counts()
        parts.append(pd.DataFrame({"column": c, "value_repr": [repr(v) for v in vc.index], "count": vc.values}))
sheets["16_text_oddities"] = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()

# ── README
guide = [
    ("01_columns_overview", "نظرة عامة على كل عمود: فاضي، مسافات، عربي، أطوال"),
    ("02_value_counts", "قيم الأعمدة القليلة القيم بالظبط زي ما هي مكتوبة"),
    ("03_products", "كل صنف: تصنيفاته، أسعاره قبل/بعد يناير، وأشكال كتابته"),
    ("04_branch_doctor_shift", "مين اشتغل في أنهي فرع وشيفت"),
    ("05_numeric_summary", "ملخص الأعمدة الرقمية (quantiles، سالب، صفر)"),
    ("06_line_total_check / 06a", "سطور line_total فيها مش مطابق للمعادلة + العدد"),
    ("07_date_shapes / 07a", "أشكال التواريخ والأوقات وأي قيمة فشلت أو خارج النطاق"),
    ("08_month_branch / 08a / 08b", "الحجم والإيراد الأولي شهر × فرع، يوم الأسبوع، الساعة"),
    ("09_duplicates / 09a", "السطور المكررة بأنواعها"),
    ("10_invoice_conflicts / 10a / 10b", "اتساق الفاتورة الواحدة، تسلسل line_no، أرقام الفواتير"),
    ("11_price_vs_median", "أبعد 500 سطر عن ميديان سعر صنفهم"),
    ("12_outlier_counts / 12a / 12b", "الأوتلاير بـ IQR وأكبر وأصغر القيم"),
    ("13_expiry_gap_days / 13a", "الفرق بين الصلاحية والبيع (توزيع بس)"),
    ("14_phone_shapes / 14a / 14b", "شكل الموبايلات وعدد زيارات العميل (متخبّية)"),
    ("15_payment_by_month", "طرق الدفع شهر بشهر"),
    ("16_text_oddities", "أي قيمة فيها حروف غير ASCII أو مسافات على الأطراف"),
]
readme = pd.DataFrame(guide, columns=["sheet", "ايه جواه"])
sheets = {"00_README": readme, **sheets}

with pd.ExcelWriter(OUT, engine="openpyxl") as xw:
    for name, frame in sheets.items():
        frame.to_excel(xw, sheet_name=name[:31], index=False)
        ws = xw.sheets[name[:31]]
        ws.freeze_panes = "A2"
        for i, col in enumerate(frame.columns, start=1):
            width = max([len(str(col))] + [len(str(v)) for v in frame[col].head(200)])
            ws.column_dimensions[ws.cell(row=1, column=i).column_letter].width = min(max(width + 2, 8), 60)

print("saved:", OUT)
for n, f in sheets.items():
    print(f"{n:28s} {len(f):>6} rows")
