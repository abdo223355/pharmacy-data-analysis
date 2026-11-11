"""Exports the deck numbers to JSON (same computations as the dashboard) for scripts/build_deck.js.

Usage:  .venv\Scripts\python.exe scripts\export_deck_data.py
Output: reports/deck/deck_data.json  (git-ignored, no customer phones)
"""
import json
from pathlib import Path

import pandas as pd

from build_dashboard import BRANCH_AR, DOCTOR_AR, K, M, MONTH_AR, compute, month_label

ROOT = Path(__file__).resolve().parents[1]
CLEAN_DIR = ROOT / "data" / "clean"
OUT = ROOT / "reports" / "deck"


def main():
    d = compute()
    raw_rows = sum(1 for _ in open(ROOT / "data" / "raw" / "alzahraa_pharmacy_sales_2025_2026.csv", encoding="utf-8")) - 1
    removed = pd.read_csv(CLEAN_DIR / "removed_rows.csv", dtype=str, keep_default_na=False)
    changes = pd.read_csv(CLEAN_DIR / "cleaning_changes.csv", dtype=str, keep_default_na=False)
    review = pd.read_csv(CLEAN_DIR / "client_review.csv", dtype=str, keep_default_na=False)
    flags = review.review_flags.str.split(" | ", regex=False).explode().value_counts()
    flag = lambda text: int(flags[[i for i in flags.index if text in i]].sum())

    rev, tot, months, fc, pay, p, exp = d["rev"], d["rev_total"], d["months"], d["fc"], d["pay"], d["price"], d["exp"]
    doc = d["doc"].sort_values("disc_rate", ascending=False)
    hi, rest = doc.iloc[0], doc.iloc[1:]
    base_rate = rest.disc_cost.sum() / rest.gross.sum()
    q = fc.groupby("branch")[["low", "mid", "high"]].sum()
    elec = pay["InstaPay"] + pay["Wallet"]
    low_month = (rev[M] / rev[K]).idxmin()
    fm = fc[fc.branch == M]
    others = fm[fm.m != low_month.month]
    adj_quarter = (others.last_year.sum() + others.last_year.mean()) * fm.growth.iloc[0] if len(others) < len(fm) else q.loc[M, "mid"]
    by_doc = exp["by_doc"].reset_index(name="n")

    data = {
        "period": {"start": f"{MONTH_AR[months[0].month]} {months[0].year}", "end": f"{MONTH_AR[months[-1].month]} {months[-1].year}",
                   "n_months": d["n_months"]},
        "cleaning": {"raw_rows": raw_rows, "clean_rows": int(d["lines"]), "removed": len(removed), "changes": len(changes)},
        "totals": {"revenue": round(d["revenue"]), "invoices": int(d["invoices"]), "avg_invoice": round(d["avg_invoice"])},
        "branches": {"labels": [month_label(m) for m in months], "kharga": [round(v) for v in rev[K]], "mut": [round(v) for v in rev[M]],
                     "total_k": round(tot[K]), "total_m": round(tot[M]), "pct_more": round((tot[K] / tot[M] - 1) * 100),
                     "inv_k": int(d["inv_by_branch"][K]), "inv_m": int(d["inv_by_branch"][M]),
                     "avg_k": round(tot[K] / d["inv_by_branch"][K]), "avg_m": round(tot[M] / d["inv_by_branch"][M]),
                     "wins": d["k_wins"], "n": len(months)},
        "expiry": {"rows": exp["rows"], "units": exp["units"], "value": round(exp["value"]), "missing": exp["missing"],
                   "doctors": [DOCTOR_AR[x] for x in by_doc.pharmacist], "cases": [int(x) for x in by_doc.n]},
        "doctors": {"names": [DOCTOR_AR[x] for x in doc.pharmacist], "disc_rate": [round(float(x), 1) for x in doc.disc_rate],
                    "disc_year": [round(x) for x in doc.disc_year], "top_name": DOCTOR_AR[hi.pharmacist],
                    "top_rate": round(float(hi.disc_rate), 1), "base_rate": round(base_rate * 100, 1),
                    "top_year": round(hi.disc_year),
                    "excess_year": round((hi.disc_cost - hi.gross * base_rate) * 12 / d["n_months"])},
        "season": {"labels": [month_label(m) for m in months],
                   "series": {k: [int(v) for v in d["season"][k]] for k in d["season"].columns}},
        "price": {"y0": int(p["y0"]), "y1": int(p["y1"]), "units_pct": round((p["u1"] / p["u0"] - 1) * 100, 1),
                  "rev_pct": round((p["rev1"] / p["rev0"] - 1) * 100, 1)},
        "payment": {"labels": [month_label(m) for m in months], "electronic": [round(float(v), 1) for v in elec],
                    "first": round(float(elec.iloc[0])), "last": round(float(elec.iloc[-1]))},
        "forecast": {"rows": [{"branch": BRANCH_AR[r.branch], "month": f"{MONTH_AR[r.m]} {r.year}", "low": round(r.low),
                               "mid": round(r.mid), "high": round(r.high)} for r in fc.itertuples()],
                     "totals": [{"branch": BRANCH_AR[b], "low": round(q.loc[b, "low"]), "mid": round(q.loc[b, "mid"]),
                                 "high": round(q.loc[b, "high"])} for b in (K, M)]},
        "decisions": {"returns": flag("مرتجع"), "totals": flag("الإجمالي كان"), "payment": flag("طريقة دفع"),
                      "expiry": flag("صلاحية"), "low_month": f"{MONTH_AR[low_month.month]} {low_month.year}",
                      "adj_quarter": round(adj_quarter), "mut_quarter": round(q.loc[M, "mid"])},
    }
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "deck_data.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print("saved:", path)


if __name__ == "__main__":
    main()
