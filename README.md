# Pharmacy sales data analysis

Cleaning, analysis, and reporting pipeline for a two-branch pharmacy sales sheet (about 10k invoice lines,
June 2025 - September 2026). It turns a dirty sales export into a clean sheet, a cleaning log, an expiry report,
an Arabic mobile dashboard, an Arabic client report, and a slide deck.

> **No data is included in this repository.** The raw sheet, the cleaned sheet and every generated report contain
> customer phone numbers and business figures, so `data/` and `reports/` are git-ignored. Pharmacist names live in a
> git-ignored `scripts/config_local.py`.

## Layout

```
scripts/
  clean_pipeline.py      cleaning pipeline (reads data/raw, writes data/clean)
  discovery_reports.py   read-only profiling workbook of the raw sheet
  expiry_report.py       items sold after their expiry date (Excel + Arabic HTML summary)
  build_dashboard.py     Arabic, mobile-friendly, offline HTML dashboard
  build_report.py        short Arabic client report (HTML)
  export_deck_data.py    numbers for the slide deck (JSON)
  build_deck.js          Arabic right-to-left PowerPoint deck (pptxgenjs)
  build_project_pdf.py   documentation PDF: screenshots + code excerpts
  config.py              pharmacist / branch / shift configuration (placeholders)
notebooks/
  02_analysis.ipynb      the ten business questions on the clean sheet
```

## Setup

```bash
python -m venv .venv
.venv\Scripts\pip install pandas numpy openpyxl matplotlib jupyterlab pymupdf Pillow   # Windows
npm install pptxgenjs                                                                  # only for the deck
```

Put the raw CSV at `data/raw/alzahraa_pharmacy_sales_2025_2026.csv` (17 columns, read as text so phone numbers keep
their leading zero). Copy `scripts/config_local.example.py` to `scripts/config_local.py` and fill in the real
pharmacists (name as written in the sheet, Arabic display name, branch, shift).

## Run order

```bash
python scripts/clean_pipeline.py      # -> data/clean/  (clean sheet, removed_rows, cleaning_changes, summary, client_review)
python scripts/expiry_report.py       # -> reports/expiry/
python scripts/build_dashboard.py     # -> reports/dashboard/dashboard.html
python scripts/build_report.py        # -> reports/final/final_report.html
python scripts/export_deck_data.py && node scripts/build_deck.js   # -> reports/deck/*.pptx
```

## How the cleaning works

- The raw sheet is never modified.
- Every removed row is written to `removed_rows.csv` with its reason; every changed cell to `cleaning_changes.csv`
  (old value, new value, rule). Nothing is deleted silently.
- Decisions with more than one reasonable interpretation (for example returns with negative quantities) are flagged in
  `review_flags` and exported to `client_review.csv` instead of being guessed.
- Rules are ordered so that each one only depends on earlier ones: standardize spelling and formats, remove duplicates,
  repair abnormal dates from the sequential invoice numbers, repair category / pharmacist / branch / payment, then
  re-derive amounts from `line_total = quantity x unit_price x (1 - discount/100)`.
- Rules that infer a value from other columns state the rule used, so every inference can be audited.

## Notes

- The narrative parts of the Arabic report and deck (seasons, recommendations) were written from the analysis of this
  specific period and must be reviewed by hand when the data changes. The numbers update automatically.
- Notebook outputs can contain data. `.gitattributes` strips them on commit if you register the filter:
  `git config filter.nbstrip.clean "jupyter nbconvert --ClearOutputPreprocessor.enabled=True --to notebook --stdin --stdout --log-level=ERROR"`.
- Built with the help of an AI coding assistant (Claude Code); the analysis decisions were reviewed by the author.
