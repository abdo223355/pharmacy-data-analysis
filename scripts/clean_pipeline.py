"""Cleaning pipeline for the pharmacy sales sheet.

Implements the cleaning decisions recorded during discovery, in order.
- data/raw is read-only and never modified.
- Every removed row is logged to data/clean/removed_rows.csv with a reason.
- Every changed cell is logged to data/clean/cleaning_changes.csv (old value, new value, rule).
- Decisions with more than one interpretation are flagged in `review_flags` and exported to client_review.csv.

Usage:
    .venv\Scripts\python.exe scripts\clean_pipeline.py
    .venv\Scripts\python.exe scripts\clean_pipeline.py --raw <file.csv> --out <dir> --start 2025-06-01 --end 2026-09-30
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RAW = ROOT / "data" / "raw" / "alzahraa_pharmacy_sales_2025_2026.csv"
DEFAULT_OUT = ROOT / "data" / "clean"

# ───────────────────────── mapping tables (phase 1 decisions) ─────────────────────────
MISSING = {"", "N/A"}

BRANCH_MAP = {
    "Kharga": "Kharga", "kharga": "Kharga", "KHARGA": "Kharga", "El Kharga": "Kharga", "الخارجة": "Kharga",
    "Mut - Dakhla": "Mut - Dakhla", "Mut-Dakhla": "Mut - Dakhla", "Mut": "Mut - Dakhla",
    "mout": "Mut - Dakhla", "موط": "Mut - Dakhla", "الداخلة": "Mut - Dakhla",
}
PAYMENT_MAP = {
    "Cash": "Cash", "cash": "Cash", "CASH": "Cash", "كاش": "Cash", "نقدي": "Cash",
    "InstaPay": "InstaPay", "Insta Pay": "InstaPay", "instapay": "InstaPay", "انستاباي": "InstaPay",
    "Wallet": "Wallet", "wallet": "Wallet", "Vodafone Cash": "Wallet", "E-Wallet": "Wallet",
}
RX_MAP = {
    "Yes": "Yes", "yes": "Yes", "Y": "Yes", "1": "Yes", "True": "Yes", "نعم": "Yes",
    "No": "No", "no": "No", "N": "No", "0": "No", "False": "No", "لا": "No",
}
CATEGORY_MAP = {
    "painkillers": "Painkillers", "Pain Killers": "Painkillers", "antibiotic": "Antibiotics",
    "vitamin": "Vitamins", "Baby care": "Baby Care",
}
# spelling typos (key and value in lower case), approved manually
PRODUCT_TYPOS = {
    "glucofage 1000mg 30 tab": "glucophage 1000mg 30 tab",
    "bruffen 400mg 30tab": "brufen 400mg 30 tab",
    "augmentine 1g 14 tab": "augmentin 1g 14 tab",
    "panadool extra 24 tab": "panadol extra 24 tab",
    "nexuim 40mg 14 tab": "nexium 40mg 14 tab",
    "rehydrane ors": "rehydran ors sachet",
}
from config import HOME_BRANCH, SHIFT_DOCTOR  # noqa: E402  (real names live in config_local.py, git-ignored)
ALLOWED_DISCOUNTS = [0, 5, 10, 15]
DATE_FORMATS = ["%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y", "%B %d, %Y"]   # DD/MM confirmed during discovery
DEFAULT_TIME = "23:59"
PRICE_CHANGE_DATE = "2026-01-01"
TOL = 0.02

RAW_COLS = ["pharmacy", "invoice_id", "line_no", "sale_date", "sale_time", "branch", "pharmacist",
            "product_name", "category", "unit_price", "quantity", "discount_pct", "line_total",
            "payment_method", "prescription_required", "customer_phone", "expiry_date"]


class Cleaner:
    def __init__(self, raw_path, start, end):
        self.raw = pd.read_csv(raw_path, dtype=str, keep_default_na=False)
        missing_cols = [c for c in RAW_COLS if c not in self.raw.columns]
        if missing_cols:
            raise ValueError(f"أعمدة ناقصة في الشيت: {missing_cols}")
        self.raw.insert(0, "csv_row", np.arange(2, len(self.raw) + 2))   # row number in the file (header = 1)
        self.df = self.raw.copy()
        self.start, self.end = pd.Timestamp(start), pd.Timestamp(end)
        self.changes = []      # log of every changed cell
        self.removed = []      # removed rows
        self.summary = []      # per-step summary
        self.df["review_flags"] = ""

    # ── helpers ──
    def set(self, mask, col, new, rule, decision):
        """Change the cells selected by mask and log the change. new: a single value or a Series."""
        mask = pd.Series(mask, index=self.df.index).fillna(False).astype(bool)
        idx = self.df.index[mask]
        if len(idx) == 0:
            self.summary.append((col, rule, decision, 0))
            return
        new_vals = new.loc[idx] if isinstance(new, pd.Series) else pd.Series(new, index=idx)
        old_vals = self.df.loc[idx, col]
        differs = ~((old_vals == new_vals) | (old_vals.isna() & new_vals.isna()))
        idx = idx[differs.values]
        self.changes.append(pd.DataFrame({
            "csv_row": self.df.loc[idx, "csv_row"].values, "invoice_id": self.df.loc[idx, "invoice_id"].values,
            "column": col, "old_value": old_vals.loc[idx].values, "new_value": new_vals.loc[idx].values,
            "rule": rule, "decision": decision}))
        self.df.loc[idx, col] = new_vals.loc[idx]
        self.summary.append((col, rule, decision, len(idx)))

    def flag(self, mask, text):
        idx = self.df.index[mask]
        cur = self.df.loc[idx, "review_flags"]
        self.df.loc[idx, "review_flags"] = np.where(cur.eq(""), text, cur + " | " + text)
        self.summary.append(("review_flags", text, "🔴/للعلم", len(idx)))

    def remove(self, mask, reason, kept_row=None):
        idx = self.df.index[mask]
        out = self.raw.loc[idx].copy()          # original values exactly as they were in the raw sheet
        out["removed_reason"] = reason
        out["kept_csv_row"] = kept_row.loc[idx].values if kept_row is not None else ""
        self.removed.append(out)
        self.df = self.df.drop(index=idx)
        self.summary.append(("(row)", reason, "حذف مسجّل", len(idx)))

    # ── 1) standardize spelling and formats ──
    def standardize(self):
        df = self.df
        # product_name
        raw_name = df.product_name
        stripped = raw_name.str.strip()
        self.set(raw_name != stripped, "product_name", stripped, "إزالة مسافات الأطراف", "🟢")
        key = df.product_name.str.lower().str.replace(r"\s+", " ", regex=True)
        key_fixed = key.replace(PRODUCT_TYPOS)
        canon_by_key = (df.assign(k=key)[key == key_fixed].groupby("k")["product_name"]
                        .agg(lambda s: s.value_counts().idxmax()))
        canon = key_fixed.map(canon_by_key)
        unknown = canon.isna()
        if unknown.any():
            self.flag(unknown, "اسم صنف مش معروف")
            canon = canon.fillna(df.product_name)
        self.set((key != key_fixed), "product_name", canon, "تصحيح خطأ إملائي (جدول مطابقة)", "🟡")
        self.set((key == key_fixed) & (df.product_name != canon), "product_name", canon, "توحيد حالة الحروف", "🟢")

        # categorical columns via mapping tables
        for col, mp, label in [("branch", BRANCH_MAP, "توحيد اسم الفرع"),
                               ("payment_method", PAYMENT_MAP, "توحيد طريقة الدفع"),
                               ("prescription_required", RX_MAP, "توحيد Yes/No")]:
            s = df[col]
            is_missing = s.isin(MISSING)
            unmapped = ~is_missing & ~s.isin(mp.keys())
            if unmapped.any():
                self.flag(unmapped, f"قيمة جديدة في {col}")
            self.set(~is_missing & ~unmapped & (s != s.map(mp)), col, s.map(mp), label, "🟢")
            self.set(is_missing, col, np.nan, f"{col}: فاضي/N/A ← ناقص", "🟢")

        s = df.category
        self.set(s.isin(CATEGORY_MAP.keys()), "category", s.replace(CATEGORY_MAP), "توحيد اسم التصنيف", "🟢")
        self.set(df.category.isin(MISSING), "category", np.nan, "category: فاضي/N/A ← ناقص", "🟢")

        # unit_price: currency symbols and decimal comma
        p = df.unit_price
        has_sym = p.str.contains(r"EGP|ج", regex=True)
        self.set(has_sym, "unit_price", p.str.replace(r"EGP|ج", "", regex=True).str.strip(), "إزالة رمز العملة", "🟢")
        p = df.unit_price
        comma = p.str.match(r"^\d+,\d{1,2}$")
        self.set(comma, "unit_price", p.str.replace(",", ".", regex=False), "فاصلة عشرية ← نقطة", "🟢")
        for col in ["line_no", "unit_price", "quantity", "discount_pct", "line_total"]:
            num = pd.to_numeric(df[col].replace("", np.nan), errors="coerce")
            bad = num.isna() & df[col].ne("")
            if bad.any():
                self.flag(bad, f"{col} مش رقم")
            df[col] = num
        frac = df.discount_pct.isin([0.05, 0.1, 0.15])
        self.set(frac, "discount_pct", (df.discount_pct * 100).round(0), "خصم ككسر عشري ← ×100", "🟢")

        # sale_date: 4 explicit formats tried in order (no guessing)
        parsed = pd.Series(pd.NaT, index=df.index)
        for fmt in DATE_FORMATS:
            parsed = parsed.fillna(pd.to_datetime(df.sale_date, format=fmt, errors="coerce"))
        iso = parsed.dt.strftime("%Y-%m-%d")
        df["sale_date_raw"] = df.sale_date
        self.set(parsed.notna() & (df.sale_date != iso), "sale_date", iso, "توحيد صيغة التاريخ", "🟢")
        df["sale_dt"] = parsed
        df["expiry_dt"] = pd.to_datetime(df.expiry_date.replace("", np.nan), format="%Y-%m-%d", errors="coerce")
        bad_exp = df.expiry_dt.isna() & df.expiry_date.ne("")
        if bad_exp.any():
            self.flag(bad_exp, "expiry_date بصيغة مش مفهومة")

        # customer_phone
        ph = df.customer_phone
        digits = ph.str.replace(r"\D", "", regex=True)
        norm = digits.copy()
        cc = (norm.str.len() == 12) & norm.str.startswith("20")
        norm[cc] = "0" + norm[cc].str[2:]
        lost0 = (norm.str.len() == 10) & norm.str.startswith("1")
        norm[lost0] = "0" + norm[lost0]
        self.set(cc & (ph != norm), "customer_phone", norm, "موبايل: إزالة كود الدولة", "🟢")
        self.set(lost0 & (ph != norm), "customer_phone", norm, "موبايل: إرجاع الصفر الأول", "🟢")
        rest = ~cc & ~lost0 & (ph != norm)
        self.set(rest, "customer_phone", norm, "موبايل: إزالة الشرطات", "🟢")
        ph = df.customer_phone
        df["phone_type"] = np.select(
            [ph.eq(""), ph.str.match(r"^01[0125]\d{8}$"), ph.str.len() == 7], ["none", "mobile", "landline"], "other")
        self.summary.append(("phone_type", "رقم أرضي 7 خانات: يتساب ويتعلّم", "🟡", int((df.phone_type == "landline").sum())))

    # ── 2) duplicates ──
    def dedupe(self):
        df = self.df
        cols = [c for c in RAW_COLS if c != "sale_date"] + ["sale_dt"]
        cmp = df[cols].astype(str)
        first = cmp.groupby(cols, sort=False)["invoice_id"].transform(lambda s: s.index[0])
        dup = cmp.duplicated(keep="first")
        self.remove(dup, "تكرار كامل", kept_row=df.loc[first, "csv_row"].set_axis(df.index))

        df = self.df
        key = ["invoice_id", "line_no"]
        grp = df.groupby(key)["sale_time"]
        size = grp.transform("size")
        has_real = grp.transform(lambda s: (s != DEFAULT_TIME).any())
        drop = (size > 1) & has_real & (df.sale_time == DEFAULT_TIME)
        keeper = df[(size > 1) & ~drop].groupby(key)["csv_row"].first()
        kept = pd.Series(list(zip(df.invoice_id, df.line_no)), index=df.index).map(keeper)
        self.remove(drop, f"تكرار مفتاح: نسخة بوقت افتراضي {DEFAULT_TIME}", kept_row=kept)
        left = self.df.duplicated(key, keep=False)
        if left.any():
            self.flag(left, "مفتاح مكرر مش محسوم")

    # ── 3) abnormal sale_date ──
    def fix_dates(self):
        df = self.df
        valid = df.sale_dt.notna() & df.sale_dt.between(self.start, self.end)
        inv_date = df[valid].groupby("invoice_id")["sale_dt"].agg(lambda s: s.mode().iloc[0])
        num = df.invoice_id.str.extract(r"(\d+)$")[0].astype(float)
        by_num = (pd.DataFrame({"n": num[valid], "d": df.sale_dt[valid]}).groupby("n")["d"].min().sort_index())
        new = pd.Series(pd.NaT, index=df.index)
        rule = pd.Series("", index=df.index)
        for i in df.index[~valid]:
            inv = df.at[i, "invoice_id"]
            if inv in inv_date.index:
                new[i], rule[i] = inv_date[inv], "تاريخ شاذ ← من باقي سطور الفاتورة"
                continue
            prev, nxt = by_num[by_num.index < num[i]], by_num[by_num.index > num[i]]
            if len(prev) and len(nxt) and prev.iloc[-1] == nxt.iloc[0]:
                new[i], rule[i] = prev.iloc[-1], "تاريخ شاذ ← الفاتورتين المجاورتين في نفس اليوم"
            elif len(prev):
                new[i], rule[i] = prev.iloc[-1], "تاريخ شاذ ← الفاتورة السابقة (المجاورتين في يومين مختلفين)"
                df.at[i, "review_flags"] = (df.at[i, "review_flags"] + " | " if df.at[i, "review_flags"] else "") + "تاريخ مستنتج تقريبي"
        for r in sorted(set(rule) - {""}):
            m = rule == r
            df.loc[m, "sale_dt"] = new[m]
            self.set(m, "sale_date", new.dt.strftime("%Y-%m-%d"), r, "🟡")
        still = df.sale_dt.isna()
        if still.any():
            self.flag(still, "تاريخ بيع مش معروف")
        multi = df.groupby("invoice_id")["sale_dt"].transform("nunique") > 1
        if multi.any():
            self.flag(multi, "فاتورة بأكتر من تاريخ")

    # ── 4) category / pharmacist / branch / payment ──
    def fix_categories(self):
        df = self.df
        counts = df.dropna(subset=["category"]).groupby(["product_name", "category"]).size()
        top = counts.groupby(level=0).idxmax().map(lambda t: t[1])
        share = counts.groupby(level=0).max() / counts.groupby(level=0).sum()
        safe = share[share >= 0.9].index
        target = df.product_name.map(top)
        ok = df.product_name.isin(safe)
        self.set(ok & df.category.isna(), "category", target, "تصنيف ناقص ← من اسم الصنف", "🟡")
        self.set(ok & df.category.notna() & (df.category != target), "category", target,
                 "تصنيف مخالف ← تصنيف الأغلبية للصنف", "🟡")
        left = df.category.isna() | (~ok)
        if left.any():
            self.flag(left, "تصنيف محتاج مراجعة يدوية")

    def fix_pharmacist_branch(self):
        df = self.df
        hour = pd.to_datetime(df.sale_time, format="%H:%M", errors="coerce").dt.hour
        df["shift"] = np.where(hour < 16, "morning", "night")
        expected = pd.Series([SHIFT_DOCTOR.get(k) for k in zip(df.branch, df["shift"])], index=df.index)

        # (a) invoice with more than one pharmacist
        n_doc = df.groupby("invoice_id")["pharmacist"].transform("nunique")
        new = pd.Series(index=df.index, dtype=object)
        rule = pd.Series("", index=df.index)
        for inv, g in df[n_doc > 1].groupby("invoice_id"):
            vc = g.pharmacist.value_counts()
            if vc.iloc[0] > vc.iloc[1]:
                pick, why = vc.index[0], "دكتور مخالف ← دكتور أغلبية سطور الفاتورة"
            else:
                br = g.branch.dropna()
                cand = [d for d in vc.index if len(br) and HOME_BRANCH.get(d) == br.mode().iloc[0]]
                if len(cand) == 1:
                    pick, why = cand[0], "دكتور مخالف (تعادل) ← الدكتور اللي تبع فرع الفاتورة"
                else:
                    e = expected.loc[g.index].dropna()
                    pick = e.mode().iloc[0] if len(e) else None
                    why = "دكتور مخالف (تعادل) ← دكتور الفرع + الشيفت"
            if pick is not None:
                m = g.index[g.pharmacist != pick]
                new[m], rule[m] = pick, why
        for r in sorted(set(rule) - {""}):
            self.set(rule == r, "pharmacist", new, r, "🟡")

        # (b) pharmacist does not belong to the stated branch (single-line invoice, or the same pharmacist throughout)
        home = df.pharmacist.map(HOME_BRANCH)
        wrong = df.branch.notna() & (home != df.branch) & expected.notna()
        self.set(wrong, "pharmacist", expected, "دكتور مش تبع الفرع ← دكتور الفرع + الشيفت", "🟡")
        self.flag(wrong, "دكتور مستنتج من الفرع والشيفت (للعلم)")

        # (c) missing branch: from the invoice first, then from the pharmacist
        inv_branch = df.dropna(subset=["branch"]).groupby("invoice_id")["branch"].agg(lambda s: s.mode().iloc[0])
        from_inv = df.invoice_id.map(inv_branch)
        self.set(df.branch.isna() & from_inv.notna(), "branch", from_inv, "فرع ناقص ← من باقي سطور الفاتورة", "🟡")
        from_doc = df.pharmacist.map(HOME_BRANCH)
        self.set(df.branch.isna() & from_doc.notna(), "branch", from_doc, "فرع ناقص ← من فرع الدكتور", "🟡")
        if df.branch.isna().any():
            self.flag(df.branch.isna(), "فرع مش معروف")

        # informational only: pharmacist in their own branch but outside their usual shift (not a fix)
        exp2 = pd.Series([SHIFT_DOCTOR.get(k) for k in zip(df.branch, df["shift"])], index=df.index)
        self.flag(exp2.notna() & (exp2 != df.pharmacist), "دكتور بره شيفته المعتاد (للعلم، متصلّحش)")

    def fix_payment(self):
        df = self.df
        known = df.dropna(subset=["payment_method"]).groupby("invoice_id")["payment_method"]
        single = known.agg(lambda s: s.iloc[0] if s.nunique() == 1 else np.nan)
        from_inv = df.invoice_id.map(single)
        self.set(df.payment_method.isna() & from_inv.notna(), "payment_method", from_inv,
                 "دفع ناقص ← من باقي سطور الفاتورة", "🟡")
        left = df.payment_method.isna()
        self.set(left, "payment_method", "Unknown", "دفع ناقص ← Unknown (بره مقام نسبة سؤال 7)", "🔴")
        self.flag(df.payment_method.eq("Unknown"), "طريقة دفع مش متسجلة")

    # ── 5) equation: line_total = quantity × unit_price × (1 − discount/100) ──
    def fix_amounts(self):
        df = self.df
        df["line_total_raw"] = df.line_total
        period = np.where(df.sale_dt >= pd.Timestamp(PRICE_CHANGE_DATE), "post", "pre")
        ref = df.assign(period=period).groupby(["product_name", "period"])["unit_price"].transform("median")

        # price multiplied by 100
        ratio = df.unit_price / ref
        x100 = ratio.between(90, 115)
        self.set(x100, "unit_price", (df.unit_price / 100).round(2), "سعر مضروب في 100 ← ÷100", "🟡")

        # impossible discount <- the discount actually implied by the total
        bad_d = ~df.discount_pct.isin(ALLOWED_DISCOUNTS)
        implied = (1 - df.line_total / (df.quantity * df.unit_price)) * 100
        snapped = implied.apply(lambda v: min(ALLOWED_DISCOUNTS, key=lambda a: abs(a - v)) if pd.notna(v) else np.nan)
        good = bad_d & snapped.notna() & ((implied - snapped).abs() <= 0.5)
        self.set(good, "discount_pct", snapped.astype(float), "خصم مستحيل ← الخصم الفعلي من الإجمالي", "🟡")
        if (bad_d & ~good).any():
            self.flag(bad_d & ~good, "خصم مستحيل ومش محسوم")

        factor = 1 - df.discount_pct / 100
        # abnormal or empty quantity <- invert the equation
        q_calc = df.line_total / (df.unit_price * factor)
        q_int = q_calc.round(0)
        q_ok = (q_calc - q_int).abs() <= 0.02
        big = df.quantity >= 100
        self.set(big & q_ok, "quantity", q_int, "كمية شاذة ← عكس المعادلة", "🟡")
        self.set(df.quantity.isna() & q_ok, "quantity", q_int, "كمية فاضية ← عكس المعادلة", "🟡")
        unresolved = (df.quantity.isna()) | (df.quantity >= 100)
        if unresolved.any():
            self.flag(unresolved, "كمية مش محسومة (الإجمالي نفسه مش راكب)")

        # empty price <- invert the equation, confirmed against the product price in the same period (base or +5%)
        p_calc = (df.line_total / (df.quantity * factor)).round(2)
        base = df.assign(period=period).groupby(["product_name", "period"])["unit_price"].transform("min")
        near = ((p_calc / base - 1).abs() <= 0.01) | ((p_calc / base - 1.05).abs() <= 0.01)
        miss_p = df.unit_price.isna()
        self.set(miss_p & near, "unit_price", p_calc, "سعر فاضي ← عكس المعادلة (متأكد بسعر الصنف)", "🟡")
        still = df.unit_price.isna()
        self.set(still & p_calc.notna(), "unit_price", ref.round(2), "سعر فاضي ← سعر الصنف المعتاد (المعادلة مركبتش)", "🟡")
        if still.any():
            self.flag(still, "سعر مستنتج من سعر الصنف مش من السطر")

        # line_total mismatch <- recompute
        expected = (df.quantity * df.unit_price * (1 - df.discount_pct / 100)).round(2)
        mism = (df.line_total - expected).abs() > TOL
        lt_ratio = (df.line_total / expected).round(2)
        df["line_total_ratio"] = np.where(mism, lt_ratio, np.nan)
        self.flag(mism & lt_ratio.isin([2.0, 3.0]), "الإجمالي كان ضعف/3 أضعاف المحسوب: الكمية ولا الإجمالي؟")
        self.set(mism, "line_total", expected, "إجمالي مش مطابق ← إعادة حساب من المعادلة", "🟡")

    # ── 6) returns and expiry ──
    def returns_and_expiry(self):
        df = self.df
        df["is_return"] = df.quantity < 0
        df["return_candidates"] = np.nan
        df["return_suggested_invoice"] = ""
        sales = df[df.quantity > 0]
        for i in df.index[df.is_return]:
            r = df.loc[i]
            c = sales[(sales.product_name == r.product_name) & (sales.branch == r.branch)
                      & (sales.quantity >= -r.quantity) & (sales.sale_dt <= r.sale_dt)
                      & (sales.sale_dt >= r.sale_dt - pd.Timedelta(days=14))]
            if r.customer_phone != "":
                c = c[c.customer_phone == r.customer_phone]
            else:
                c = c[(c.unit_price - r.unit_price).abs() <= TOL]
            df.at[i, "return_candidates"] = c.invoice_id.nunique()
            if r.customer_phone != "" and c.invoice_id.nunique() == 1:
                df.at[i, "return_suggested_invoice"] = c.invoice_id.iloc[0]
        linked = df.is_return & df.return_suggested_invoice.ne("")
        self.summary.append(("quantity", "مرتجع اتوصل بفاتورة أصلية (نفس الموبايل والصنف والفرع خلال 14 يوم)", "🟡", int(linked.sum())))
        self.flag(df.is_return & ~linked, "مرتجع مش متوصل بفاتورة أصلية (قرار العميل)")

        df["days_to_expiry"] = (df.expiry_dt - df.sale_dt).dt.days
        df["sold_after_expiry"] = df.days_to_expiry < 0
        self.flag(df.expiry_dt.isna(), "تاريخ صلاحية مش متسجل")
        self.summary.append(("expiry_date", "بيع بعد انتهاء الصلاحية (نتيجة، مش تصليح)", "⚪", int(df.sold_after_expiry.sum())))

    # ── run and save ──
    def run(self):
        self.standardize()
        self.dedupe()
        self.fix_dates()
        self.fix_categories()
        self.fix_pharmacist_branch()
        self.fix_payment()
        self.fix_amounts()
        self.returns_and_expiry()
        return self

    def save(self, out_dir):
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        df = self.df.copy()
        df["line_no"] = df.line_no.astype("Int64")
        df["quantity"] = df.quantity.round(0).astype("Int64")
        df["discount_pct"] = df.discount_pct.astype("Int64")
        cols = (["csv_row"] + RAW_COLS + ["shift", "phone_type", "is_return", "return_suggested_invoice",
                                           "days_to_expiry", "sold_after_expiry", "line_total_raw", "review_flags"])
        clean = df[cols].sort_values(["sale_date", "sale_time", "invoice_id", "line_no"])
        removed = pd.concat(self.removed, ignore_index=True) if self.removed else pd.DataFrame()
        changes = pd.concat(self.changes, ignore_index=True) if self.changes else pd.DataFrame()
        summary = pd.DataFrame(self.summary, columns=["column", "rule", "decision", "rows"])
        summary = summary.groupby(["column", "rule", "decision"], sort=False)["rows"].sum().reset_index()
        review = clean[clean.review_flags.ne("")].copy()
        extra = df.loc[review.index, ["line_total_ratio", "return_candidates"]]
        review = pd.concat([review, extra], axis=1)

        enc = dict(index=False, encoding="utf-8-sig")
        clean.to_csv(out_dir / "alzahraa_sales_clean.csv", **enc)
        removed.to_csv(out_dir / "removed_rows.csv", **enc)
        changes.to_csv(out_dir / "cleaning_changes.csv", **enc)
        summary.to_csv(out_dir / "cleaning_summary.csv", **enc)
        review.to_csv(out_dir / "client_review.csv", **enc)
        return clean, removed, changes, summary, review


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default=str(DEFAULT_RAW))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--start", default="2025-06-01")
    ap.add_argument("--end", default="2026-09-30")
    a = ap.parse_args()
    c = Cleaner(a.raw, a.start, a.end).run()
    clean, removed, changes, summary, review = c.save(a.out)
    pd.set_option("display.width", 250, "display.max_rows", 200, "display.max_colwidth", 80)
    print(f"raw rows: {len(c.raw)} | clean rows: {len(clean)} | removed: {len(removed)} | changed cells: {len(changes)}")
    print(summary.to_string(index=False))
    print("saved to:", a.out)


if __name__ == "__main__":
    main()
