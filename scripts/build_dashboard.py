"""Arabic single-page HTML dashboard for the pharmacy: mobile friendly and works offline.

Reads the clean sheet and writes reports/dashboard/dashboard.html (git-ignored).
No customer phone numbers appear on the page.

Usage:  .venv\Scripts\python.exe scripts\build_dashboard.py
"""
from html import escape
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CLEAN = ROOT / "data" / "clean" / "alzahraa_sales_clean.csv"
OUT = ROOT / "reports" / "dashboard"

K, M = "Kharga", "Mut - Dakhla"
BRANCH_AR = {K: "الخارجة", M: "موط - الداخلة"}
BRANCH_COLOR = {K: "var(--s1)", M: "var(--s2)"}          # color follows the branch in every chart
from config import DOCTOR_AR  # noqa: E402  (real names live in config_local.py, git-ignored)
SHIFT_AR = {"morning": "صبح", "night": "ليل"}
RAMADAN = ("2026-02-18", "2026-03-19")
WINTER_MONTHS = [10, 11, 12, 1, 2, 3]
OVERLAP_MONTHS, FORECAST_MONTHS = [6, 7, 8, 9], [10, 11, 12]
MONTH_AR = {1: "يناير", 2: "فبراير", 3: "مارس", 4: "أبريل", 5: "مايو", 6: "يونيو", 7: "يوليو",
            8: "أغسطس", 9: "سبتمبر", 10: "أكتوبر", 11: "نوفمبر", 12: "ديسمبر"}


# ───────────────────────── number and chart helpers ─────────────────────────
def n0(v):
    return f"{v:,.0f}"


def compact(v):
    return f"{v / 1000:.0f}K" if abs(v) >= 10000 else f"{v:,.0f}"


def nice_ticks(vmax, n=4):
    if vmax <= 0:
        return [0, 1]
    raw = vmax / n
    mag = 10 ** np.floor(np.log10(raw))
    step = next(s for s in (1, 2, 2.5, 5, 10) if s * mag >= raw) * mag
    top = np.ceil(vmax / step) * step
    return list(np.arange(0, top + step / 2, step))


def month_label(p):
    return f"{p.month:02d}/{str(p.year)[2:]}"


def month_long(p):
    return f"{MONTH_AR[p.month]} {p.year}"


def legend(items):
    """items: [(name, color)]"""
    return '<div class="legend">' + "".join(
        f'<span><i style="background:{c}"></i>{escape(n)}</span>' for n, c in items) + "</div>"


def table(frame, cls=""):
    head = "".join(f"<th>{escape(str(c))}</th>" for c in frame.columns)
    body = "".join("<tr>" + "".join(f"<td>{escape(str(v))}</td>" for v in r) + "</tr>"
                   for r in frame.itertuples(index=False))
    return f'<div class="scroll {cls}"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def details(frame, label="عرض الجدول"):
    return f"<details><summary>{label}</summary>{table(frame)}</details>"


W, H = 360, 200
ML, MR, MT, MB = 34, 14, 10, 22


def line_chart(labels, long_labels, series, fmt=n0, unit="", end_label=False, tick_fmt=compact):
    """series: [(name, color, values)]. Single axis that starts at zero."""
    n = len(labels)
    vmax = max(max(v) for _, _, v in series)
    ticks = nice_ticks(vmax)
    top = ticks[-1]
    pw, ph = W - ML - MR, H - MT - MB
    x = lambda i: ML + (pw * i / (n - 1) if n > 1 else pw / 2)
    y = lambda v: MT + ph * (1 - v / top)
    out = [f'<svg viewBox="0 0 {W} {H}" role="img" class="chart" direction="ltr">']
    for t in ticks:
        cls = "base" if t == 0 else "grid"
        out.append(f'<line class="{cls}" x1="{ML}" x2="{W - MR}" y1="{y(t):.1f}" y2="{y(t):.1f}"/>')
        out.append(f'<text class="tick" x="{ML - 5}" y="{y(t) + 3:.1f}" text-anchor="end">{tick_fmt(t)}</text>')
    step = max(1, round(n / 5))
    for i in range(0, n, step):
        out.append(f'<text class="tick" x="{x(i):.1f}" y="{H - 6}" text-anchor="middle">{labels[i]}</text>')
    out.append(f'<line class="xh" x1="0" x2="0" y1="{MT}" y2="{MT + ph}"/>')
    for name, color, vals in series:
        pts = " ".join(f"{x(i):.1f},{y(v):.1f}" for i, v in enumerate(vals))
        out.append(f'<polyline class="ln" style="stroke:{color}" points="{pts}"/>')
        out.append(f'<circle class="dot" style="fill:{color}" cx="{x(n - 1):.1f}" cy="{y(vals[-1]):.1f}" r="4"/>')
        if end_label:
            out.append(f'<text class="val" x="{x(n - 1) - 7:.1f}" y="{y(vals[-1]) - 8:.1f}" '
                       f'text-anchor="end">{fmt(vals[-1])}{unit}</text>')
    slot = pw / max(n - 1, 1)
    for i in range(n):
        tip = long_labels[i] + "\n" + "\n".join(f"{name}: {fmt(vals[i])}{unit}" for name, _, vals in series)
        out.append(f'<rect class="hit" x="{x(i) - slot / 2:.1f}" y="{MT}" width="{slot:.1f}" height="{ph}" '
                   f'data-x="{x(i):.1f}" data-tip="{escape(tip, quote=True)}"/>')
    out.append("</svg>")
    return "".join(out)


def column_chart(labels, series, top=None, fmt=lambda v: f"{v:.1f}", x_title=""):
    """Grouped columns (one or two series) from a single baseline."""
    n, k = len(labels), len(series)
    vmax = top or max(max(v) for _, _, v in series)
    ticks = nice_ticks(vmax, 3)
    top = ticks[-1]
    pw, ph = W - ML - MR, H - MT - MB
    slot = pw / n
    bw = min(24, (slot - 4 - 2 * (k - 1)) / k)
    y = lambda v: MT + ph * (1 - v / top)
    out = [f'<svg viewBox="0 0 {W} {H}" role="img" class="chart" direction="ltr">']
    for t in ticks:
        cls = "base" if t == 0 else "grid"
        out.append(f'<line class="{cls}" x1="{ML}" x2="{W - MR}" y1="{y(t):.1f}" y2="{y(t):.1f}"/>')
        out.append(f'<text class="tick" x="{ML - 5}" y="{y(t) + 3:.1f}" text-anchor="end">{fmt(t)}</text>')
    for i, lab in enumerate(labels):
        x0 = ML + slot * i + (slot - (bw * k + 2 * (k - 1))) / 2
        for j, (name, color, vals) in enumerate(series):
            v = vals[i]
            h = max(ph * v / top, 0)
            bx = x0 + j * (bw + 2)
            r = min(4, h)
            if h > 0:
                out.append(f'<path style="fill:{color}" d="M{bx:.1f},{MT + ph:.1f} v{-(h - r):.1f} '
                           f'q0,{-r:.1f} {r:.1f},{-r:.1f} h{bw - 2 * r:.1f} q{r:.1f},0 {r:.1f},{r:.1f} v{h - r:.1f} z"/>')
        out.append(f'<text class="tick" x="{ML + slot * (i + .5):.1f}" y="{H - 6}" text-anchor="middle">{lab}</text>')
        tip = f"{x_title} {lab}\n" + "\n".join(f"{name}: {fmt(vals[i])}" for name, _, vals in series)
        out.append(f'<rect class="hit" x="{ML + slot * i:.1f}" y="{MT}" width="{slot:.1f}" height="{ph}" '
                   f'data-tip="{escape(tip, quote=True)}"/>')
    out.append("</svg>")
    return "".join(out)


def bars_h(rows, color="var(--s1)", fmt=n0, unit=""):
    """rows: [(name, value, optional second line)]. Horizontal bars with the value at the tip."""
    vmax = max(v for _, v, *_ in rows)
    out = ['<div class="bars">']
    for name, v, *rest in rows:
        sub = f"<small>{escape(rest[0])}</small>" if rest else ""
        tip = f"{name}\n{fmt(v)}{unit}" + (f"\n{rest[0]}" if rest else "")
        out.append(f'<div class="bar-row" data-tip="{escape(tip, quote=True)}"><div class="bar-name">{escape(name)}{sub}</div>'
                   f'<div class="bar-track"><span style="width:{max(v / vmax * 100, 1):.1f}%;background:{color}"></span>'
                   f'<b>{fmt(v)}{unit}</b></div></div>')
    out.append("</div>")
    return "".join(out)


def range_rows(rows, scale_max):
    """rows: [(title, color, low, forecast, high)]"""
    out = ['<div class="ranges">']
    for title, color, lo, mid, hi in rows:
        l, w, p = lo / scale_max * 100, (hi - lo) / scale_max * 100, mid / scale_max * 100
        tip = f"{title}\nالمتوقع: {n0(mid)} جنيه\nمن {n0(lo)} إلى {n0(hi)}"
        out.append(f'<div class="range-row" data-tip="{escape(tip, quote=True)}"><div class="range-head"><span>{escape(title)}</span>'
                   f'<b>{n0(mid)}</b></div><div class="range-track">'
                   f'<span class="band" style="right:{l:.1f}%;width:{w:.1f}%;background:{color}"></span>'
                   f'<span class="pt" style="right:{p:.1f}%;background:{color}"></span></div>'
                   f'<div class="range-foot">من {n0(lo)} إلى {n0(hi)}</div></div>')
    out.append("</div>")
    return "".join(out)


# ───────────────────────── computations ─────────────────────────
def compute():
    c = pd.read_csv(CLEAN, dtype={"customer_phone": str}, parse_dates=["sale_date"])
    c["month"] = c.sale_date.dt.to_period("M")
    s = c[~c.is_return].copy()
    s["gross"] = s.quantity * s.unit_price
    s["disc_cost"] = s.gross - s.line_total
    months = sorted(c.month.unique())
    n_months = len(months)
    d = {"months": months, "start": c.sale_date.min(), "end": c.sale_date.max(), "n_months": n_months}

    # summary
    d["revenue"] = c.line_total.sum()
    d["invoices"] = c.invoice_id.nunique()
    d["avg_invoice"] = d["revenue"] / d["invoices"]
    d["lines"] = len(c)

    # 1) monthly revenue
    rev = c.pivot_table(index="month", columns="branch", values="line_total", aggfunc="sum").reindex(months)
    d["rev"] = rev
    d["rev_total"] = rev.sum()
    d["inv_by_branch"] = c.groupby("branch").invoice_id.nunique()
    d["ratio_min"], d["ratio_max"] = (rev[K] / rev[M]).min(), (rev[K] / rev[M]).max()
    d["k_wins"] = int((rev[K] > rev[M]).sum())

    # 2) products
    prod = s.groupby(["branch", "product_name"]).agg(revenue=("line_total", "sum"), units=("quantity", "sum"),
                                                     last=("sale_date", "max")).reset_index()
    d["prod"] = prod
    d["top_all"] = s.groupby("product_name").agg(revenue=("line_total", "sum"), units=("quantity", "sum")) \
        .sort_values("revenue", ascending=False)
    d["max_idle_days"] = int((d["end"] - prod["last"]).dt.days.max())

    # 3) seasons
    groups = {"أدوية البرد": s.category == "Cold & Flu", "محلول الجفاف ORS": s.product_name.str.contains("ORS"),
              "واقي الشمس": s.product_name.str.contains("Nivea Sun")}
    d["season"] = pd.DataFrame({k: s[m].groupby("month").quantity.sum() for k, m in groups.items()}) \
        .reindex(months).fillna(0).astype(int)

    # 4) pharmacists
    doc = s.groupby(["branch", "pharmacist", "shift"]).agg(
        revenue=("line_total", "sum"), invoices=("invoice_id", "nunique"), gross=("gross", "sum"),
        disc_cost=("disc_cost", "sum"), pct_disc=("discount_pct", lambda x: (x > 0).mean() * 100)).reset_index()
    doc["avg_invoice"] = doc.revenue / doc.invoices
    doc["disc_rate"] = doc.disc_cost / doc.gross * 100
    doc["disc_year"] = doc.disc_cost * 12 / n_months
    d["doc"] = doc

    # 5) busy hours
    inv = s.groupby("invoice_id").agg(date=("sale_date", "first"), time=("sale_time", "first"),
                                      branch=("branch", "first")).reset_index()
    inv["hour"] = inv.time.str[:2].astype(int)
    inv["ramadan"] = inv.date.between(*RAMADAN)
    hours = list(range(int(inv.hour.min()), int(inv.hour.max()) + 1))

    def per_hour(x):
        t = x.groupby(["hour", "branch"]).size().unstack().reindex(hours).fillna(0)
        return t / x.groupby("branch").date.nunique()

    d["hours"], d["hour_normal"], d["hour_ramadan"] = hours, per_hour(inv[~inv.ramadan]), per_hour(inv[inv.ramadan])
    days = inv.groupby(["branch", "date"]).size().rename("n").reset_index()
    days["friday"] = days.date.dt.dayofweek == 4
    d["per_day"] = days.groupby(["branch", "friday"]).n.mean().unstack()

    # 6) price increase
    summer = s[s.sale_date.dt.month.isin(OVERLAP_MONTHS)]
    y0, y1 = summer.sale_date.dt.year.min(), summer.sale_date.dt.year.max()
    a, b = summer[summer.sale_date.dt.year == y0], summer[summer.sale_date.dt.year == y1]
    d["price"] = {"y0": y0, "y1": y1, "rev0": a.line_total.sum(), "rev1": b.line_total.sum(),
                  "u0": a.quantity.sum(), "u1": b.quantity.sum()}

    # 7) payment
    pay = s.groupby("invoice_id").agg(month=("month", "first"), pay=("payment_method", "first")).reset_index()
    d["pay_unknown"] = int((pay.pay == "Unknown").sum())
    pay = pay[pay.pay != "Unknown"]
    d["pay"] = (pd.crosstab(pay.month, pay.pay, normalize="index") * 100).reindex(months)

    # 8) expiry
    exp = s[s.sold_after_expiry]
    d["exp"] = {"rows": len(exp), "units": int(exp.quantity.sum()), "value": exp.line_total.sum(),
                "missing": int(s.expiry_date.isna().sum()),
                "by_doc": exp.groupby(["branch", "pharmacist"]).size()}

    # 9) antibiotics
    s["is_ab"] = s.category == "Antibiotics"
    d["ab_month"] = (s.groupby("month").is_ab.mean() * 100).reindex(months)
    d["ab_branch"] = s.groupby("branch").is_ab.mean() * 100
    winter = s.sale_date.dt.month.isin(WINTER_MONTHS)
    d["ab_winter"], d["ab_rest"] = s[winter].is_ab.mean() * 100, s[~winter].is_ab.mean() * 100

    # 10) forecast
    P = pd.Period
    fc = []
    for b_ in [K, M]:
        x = rev[b_]
        mg = pd.Series({m: x[P(f"{y1}-{m:02d}")] / x[P(f"{y0}-{m:02d}")] for m in OVERLAP_MONTHS})
        g = sum(x[P(f"{y1}-{m:02d}")] for m in OVERLAP_MONTHS) / sum(x[P(f"{y0}-{m:02d}")] for m in OVERLAP_MONTHS)
        sp = mg.std()
        for m in FORECAST_MONTHS:
            ly = x[P(f"{y0}-{m:02d}")]
            fc.append({"branch": b_, "m": m, "year": y1, "last_year": ly, "low": ly * (g - sp),
                       "mid": ly * g, "high": ly * (g + sp), "growth": g, "spread": sp})
    d["fc"] = pd.DataFrame(fc)
    return d


# ───────────────────────── page ─────────────────────────
CSS = """
:root{color-scheme:light;--page:#f9f9f7;--surface:#fcfcfb;--ink:#0b0b0b;--ink2:#52514e;--muted:#898781;
--grid:#e1e0d9;--base:#c3c2b7;--border:rgba(11,11,11,.10);--s1:#2a78d6;--s2:#eb6834;--s3:#1baf7a;
--critical:#d03b3b;--critbg:#fdecea;--warnbg:#fff4dc;--warnink:#6b4700}
@media (prefers-color-scheme:dark){:root{color-scheme:dark;--page:#0d0d0d;--surface:#1a1a19;--ink:#f0efec;--ink2:#c3c2b7;
--grid:#2c2c2a;--base:#383835;--border:rgba(255,255,255,.10);--s1:#3987e5;--s2:#d95926;--s3:#199e70;
--critical:#e66767;--critbg:#3a1d1c;--warnbg:#3a2f14;--warnink:#f3d38a}}
*{box-sizing:border-box}
body{margin:0;background:var(--page);color:var(--ink);font-family:system-ui,-apple-system,"Segoe UI",Tahoma,sans-serif;line-height:1.65}
main{max-width:1080px;margin:0 auto;padding:16px}
h1{font-size:1.35rem;margin:6px 0 2px} .sub{color:var(--ink2);margin:0 0 14px;font-size:.92rem}
h2{font-size:1.05rem;margin:0 0 2px} .q{color:var(--muted);font-size:.8rem;margin:0}
.take{margin:6px 0 10px;color:var(--ink2);font-size:.93rem} .take b{color:var(--ink)}
.grid{display:grid;gap:12px;grid-template-columns:1fr}
@media (min-width:820px){.grid{grid-template-columns:1fr 1fr}.wide{grid-column:1/-1}}
.card{background:var(--surface);border:1px solid var(--border);border-radius:14px;padding:14px;min-width:0}
.hero b{display:block;font-size:3rem;line-height:1.1;font-weight:650} .hero span{color:var(--ink2)}
.tiles{display:grid;grid-template-columns:repeat(2,1fr);gap:10px;margin-top:12px}
@media (min-width:820px){.tiles{grid-template-columns:repeat(4,1fr)}}
.tile{border:1px solid var(--border);border-radius:12px;padding:10px 12px}
.tile b{display:block;font-size:1.45rem;line-height:1.25;font-weight:650} .tile span{color:var(--ink2);font-size:.85rem}
.tile.crit b{color:var(--critical)}
.legend{display:flex;flex-wrap:wrap;gap:6px 16px;font-size:.85rem;color:var(--ink2);margin:4px 0 6px}
.legend i{display:inline-block;width:14px;height:3px;border-radius:2px;margin-inline-end:6px;vertical-align:middle}
.chart{width:100%;height:auto;max-height:300px;display:block;overflow:visible}
.chart .grid{stroke:var(--grid);stroke-width:1} .chart .base{stroke:var(--base);stroke-width:1}
.chart .tick{fill:var(--muted);font-size:9.5px;font-variant-numeric:tabular-nums}
.chart .val{fill:var(--ink);font-size:10.5px;font-weight:600}
.chart .ln{fill:none;stroke-width:2;stroke-linejoin:round;stroke-linecap:round}
.chart .dot{stroke:var(--surface);stroke-width:2}
.chart .hit{fill:transparent;cursor:crosshair} .chart .xh{stroke:var(--base);stroke-width:1;visibility:hidden}
.mini{display:grid;grid-template-columns:1fr;gap:10px}
@media (min-width:560px){.mini{grid-template-columns:1fr 1fr}} .mini h3{font-size:.85rem;margin:0 0 2px;color:var(--ink2);font-weight:600}
.bars{display:grid;gap:9px} .bar-name{font-size:.86rem;line-height:1.3} .bar-name small{display:block;color:var(--muted);font-size:.76rem}
.bar-track{display:flex;align-items:center;gap:8px;margin-top:3px}
.bar-track span{height:12px;border-start-end-radius:4px;border-end-end-radius:4px;min-width:3px}
.bar-track b{font-size:.82rem;font-weight:600;white-space:nowrap;font-variant-numeric:tabular-nums}
.ranges{display:grid;gap:12px} .range-head{display:flex;justify-content:space-between;font-size:.88rem}
.range-head b{font-weight:650} .range-foot{color:var(--muted);font-size:.78rem}
.range-track{position:relative;height:14px;margin:4px 0 2px;border-inline-start:1px solid var(--base)}
.range-track .band{position:absolute;top:4px;height:6px;border-radius:3px;opacity:.35}
.range-track .pt{position:absolute;top:1px;width:12px;height:12px;border-radius:50%;margin-right:-6px;border:2px solid var(--surface)}
.note{border-radius:10px;padding:9px 12px;margin:8px 0 0;font-size:.88rem}
.note.crit{background:var(--critbg);color:var(--critical)} .note.warn{background:var(--warnbg);color:var(--warnink)}
details{margin-top:8px} summary{cursor:pointer;color:var(--ink2);font-size:.85rem}
.scroll{overflow-x:auto;margin-top:6px}
table{border-collapse:collapse;width:100%;font-size:.84rem;white-space:nowrap}
th,td{padding:6px 9px;border-bottom:1px solid var(--grid);text-align:right;font-variant-numeric:tabular-nums}
th{color:var(--ink2);font-weight:600}
#tip{position:fixed;z-index:9;pointer-events:none;background:var(--ink);color:var(--surface);padding:6px 9px;border-radius:8px;
font-size:.8rem;line-height:1.5;white-space:pre-line;max-width:240px;direction:rtl}
footer{color:var(--muted);font-size:.8rem;margin:18px 0 10px}
"""

JS = """
const tip=document.getElementById('tip');let cur=null;
function hide(){tip.hidden=true;if(cur){const l=cur.closest('svg')?.querySelector('.xh');if(l)l.style.visibility='hidden';cur=null}}
function show(el,x,y){cur=el;tip.textContent=el.dataset.tip;tip.hidden=false;
 const r=tip.getBoundingClientRect();let L=Math.min(Math.max(8,x+12),innerWidth-r.width-8),T=y-r.height-12;if(T<8)T=y+16;
 tip.style.left=L+'px';tip.style.top=T+'px';
 const l=el.closest('svg')?.querySelector('.xh');if(l&&el.dataset.x){l.setAttribute('x1',el.dataset.x);l.setAttribute('x2',el.dataset.x);l.style.visibility='visible'}}
function on(e){const el=e.target.closest('[data-tip]');if(!el){hide();return}if(cur&&cur!==el)hide();show(el,e.clientX,e.clientY)}
document.addEventListener('pointermove',on);document.addEventListener('pointerdown',on);
document.addEventListener('scroll',hide,{passive:true});
"""


def card(title, question, takeaway, body, wide=False):
    return (f'<section class="card{" wide" if wide else ""}"><p class="q">{question}</p><h2>{title}</h2>'
            f'<p class="take">{takeaway}</p>{body}</section>')


def build_html(d):
    months = d["months"]
    labels, long_labels = [month_label(p) for p in months], [month_long(p) for p in months]
    branch_legend = legend([(BRANCH_AR[K], BRANCH_COLOR[K]), (BRANCH_AR[M], BRANCH_COLOR[M])])
    cards = []

    # ── summary
    exp, pay = d["exp"], d["pay"]
    elec_last = 100 - pay["Cash"].iloc[-1]
    summary = (f'<section class="card wide"><div class="hero"><b>{n0(d["revenue"])}</b>'
               f'<span>جنيه إجمالي المبيعات من {month_long(months[0])} إلى {month_long(months[-1])} (الفرعين)</span></div>'
               f'<div class="tiles"><div class="tile"><b>{n0(d["invoices"])}</b><span>فاتورة</span></div>'
               f'<div class="tile"><b>{n0(d["avg_invoice"])}</b><span>جنيه متوسط الفاتورة</span></div>'
               f'<div class="tile"><b>{elec_last:.0f}%</b><span>دفع إلكتروني في آخر شهر</span></div>'
               f'<div class="tile crit"><b>⚠ {exp["rows"]}</b><span>مرة بيع بعد انتهاء الصلاحية</span></div></div></section>')
    cards.append(summary)

    # ── 1) monthly revenue
    rev = d["rev"]
    t = pd.DataFrame({"الشهر": labels, BRANCH_AR[K]: rev[K].map(n0).values, BRANCH_AR[M]: rev[M].map(n0).values})
    take = (f'الخارجة أعلى في <b>{d["k_wins"]} شهر من {len(months)}</b>. إجمالي الخارجة <b>{n0(d["rev_total"][K])}</b> '
            f'وموط <b>{n0(d["rev_total"][M])}</b> جنيه. الفرق مش ثابت: الخارجة بين {d["ratio_min"]:.2f} و{d["ratio_max"]:.2f} مرة قد موط.')
    cards.append(card("إيراد كل فرع شهر بشهر", "سؤال 1", take, branch_legend + line_chart(
        labels, long_labels, [(BRANCH_AR[b], BRANCH_COLOR[b], rev[b].tolist()) for b in (K, M)], unit=" جنيه") + details(t), wide=True))

    # ── 2) products
    top = d["top_all"].head(10)
    rows = [(name, r.revenue, f"{n0(r.units)} علبة") for name, r in top.iterrows()]
    share = top.revenue.sum() / d["top_all"].revenue.sum() * 100
    prod = d["prod"]
    tabs = []
    for b in (K, M):
        x = prod[prod.branch == b]
        byrev = x.nlargest(10, "revenue")
        byunits = x.nlargest(10, "units")
        slow = x.nsmallest(5, "units")
        tabs.append(details(pd.DataFrame({"أعلى 10 بالفلوس": byrev.product_name.values, "جنيه": byrev.revenue.map(n0).values,
                                          "أعلى 10 بالكمية": byunits.product_name.values, "علبة": byunits.units.map(n0).values}),
                            f"أعلى 10 في {BRANCH_AR[b]} (فلوس وكمية)"))
        tabs.append(details(pd.DataFrame({"الصنف": slow.product_name.values, "علبة": slow.units.map(n0).values,
                                          "جنيه": slow.revenue.map(n0).values}), f"أقل 5 أصناف حركة في {BRANCH_AR[b]}"))
    take = (f'أعلى 10 أصناف بيجيبوا <b>{share:.0f}%</b> من المبيعات. مفيش صنف راكد: كل الأصناف اتباعت في الفرعين '
            f'خلال آخر <b>{d["max_idle_days"]} يوم</b>.')
    cards.append(card("أعلى 10 أصناف بالفلوس (الفرعين)", "سؤال 2", take, bars_h(rows, unit=" جنيه") + "".join(tabs)))

    # ── 3) seasons
    se = d["season"]
    colors = ["var(--s1)", "var(--s2)", "var(--s3)"]
    peak = {k: months[int(np.argmax(se[k].values))] for k in se.columns}
    take = " · ".join(f'{k}: القمة في <b>{MONTH_AR[peak[k].month]}</b>' for k in se.columns) + ". اطلب البضاعة قبل الموسم بشهر."
    t = pd.DataFrame({"الشهر": labels, **{k: se[k].values for k in se.columns}})
    cards.append(card("مواسم الأصناف (عدد العلب في الشهر)", "سؤال 3", take,
                      legend(list(zip(se.columns, colors))) + line_chart(
                          labels, long_labels, [(k, colors[i], se[k].tolist()) for i, k in enumerate(se.columns)],
                          unit=" علبة") + details(t)))

    # ── 4) pharmacists
    doc = d["doc"].copy()
    doc["name"] = doc.pharmacist.map(DOCTOR_AR)
    doc["where"] = doc.branch.map(BRANCH_AR) + " · " + doc["shift"].map(SHIFT_AR)
    doc = doc.sort_values("disc_rate", ascending=False)
    rows = [(r["name"], r.disc_rate, f'{r["where"]} · حوالي {n0(r.disc_year)} جنيه في السنة') for _, r in doc.iterrows()]
    hi = doc.iloc[0]
    others = doc.iloc[1:].disc_rate.mean()
    take = (f'<b>{hi["name"]}</b> خصوماته <b>{hi.disc_rate:.1f}%</b> من البيع، والباقي حوالي <b>{others:.1f}%</b>. '
            f'متوسط الفاتورة متقارب عند الأربعة ({n0(doc.avg_invoice.min())} إلى {n0(doc.avg_invoice.max())} جنيه). '
            f'الإيراد بيفرق حسب الفرع والشيفت، فالمقارنة العادلة صبح بصبح وليل بليل.')
    t = doc.sort_values(["shift", "branch"])
    t = pd.DataFrame({"الدكتور": t["name"].values, "الفرع والشيفت": t["where"].values, "الإيراد": t.revenue.map(n0).values,
                      "الفواتير": t.invoices.map(n0).values, "متوسط الفاتورة": t.avg_invoice.map(n0).values,
                      "سطور عليها خصم": t.pct_disc.map(lambda v: f"{v:.0f}%").values,
                      "الخصم من البيع": t.disc_rate.map(lambda v: f"{v:.1f}%").values,
                      "تكلفة الخصم في السنة": t.disc_year.map(n0).values})
    cards.append(card("الخصومات كنسبة من بيع كل دكتور", "سؤال 4", take,
                      bars_h(rows, fmt=lambda v: f"{v:.1f}", unit="%") + details(t, "عرض جدول الأداء الكامل")))

    # ── 5) busy hours
    hn, hr = d["hour_normal"], d["hour_ramadan"]
    top_val = max(hn.values.max(), hr.values.max())
    hl = [str(h) for h in d["hours"]]
    mk = lambda tb: column_chart(hl, [(BRANCH_AR[b], BRANCH_COLOR[b], tb[b].tolist()) for b in (K, M)], top=top_val, x_title="الساعة")
    peak_h = int(hn.sum(axis=1).idxmax())
    pd_ = d["per_day"]
    take = (f'الزحمة العادية حوالين الساعة <b>{peak_h}</b>. في رمضان النهار بيهدى والبيع بيتنقل لبعد الفطار. '
            f'أعلى معدل في أي ساعة <b>{top_val:.1f} فاتورة</b>. الجمعة أهدى يوم '
            f'({pd_.loc[K, True]:.1f} فاتورة في الخارجة مقابل {pd_.loc[K, False]:.1f} باقي الأيام).')
    t = pd.DataFrame({"الساعة": hl, "الخارجة عادي": hn[K].round(2).values, "موط عادي": hn[M].round(2).values,
                      "الخارجة رمضان": hr[K].round(2).values, "موط رمضان": hr[M].round(2).values})
    body = (branch_legend + f'<div class="mini"><div><h3>يوم عادي</h3>{mk(hn)}</div><div><h3>رمضان</h3>{mk(hr)}</div></div>' + details(t))
    cards.append(card("متوسط الفواتير في كل ساعة", "سؤال 5", take, body, wide=True))

    # ── 6) price increase
    p = d["price"]
    ru, rr = (p["u1"] / p["u0"] - 1) * 100, (p["rev1"] / p["rev0"] - 1) * 100
    take = (f'مقارنة يونيو–سبتمبر {p["y0"]} بنفس الشهور في {p["y1"]}: الكميات اتغيرت <b>{ru:+.1f}%</b> '
            f'والإيراد <b>{rr:+.1f}%</b>. يعني الزيادة ما قللتش البيع.')
    body = (f'<div class="tiles" style="grid-template-columns:1fr 1fr"><div class="tile"><b><bdi dir="ltr">{ru:+.1f}%</bdi></b><span>عدد العلب '
            f'({n0(p["u0"])} ← {n0(p["u1"])})</span></div><div class="tile"><b><bdi dir="ltr">{rr:+.1f}%</bdi></b><span>الإيراد '
            f'({n0(p["rev0"])} ← {n0(p["rev1"])})</span></div></div>')
    cards.append(card("أثر زيادة الأسعار 12% في يناير 2026", "سؤال 6", take, body))

    # ── 7) payment
    elec = (pay["InstaPay"] + pay["Wallet"]).round(1)
    take = (f'الدفع الإلكتروني (InstaPay + محافظ) طلع من <b>{elec.iloc[0]:.0f}%</b> لـ <b>{elec.iloc[-1]:.0f}%</b> من الفواتير. '
            f'في آخر شهر: InstaPay {pay["InstaPay"].iloc[-1]:.1f}% ومحافظ {pay["Wallet"].iloc[-1]:.1f}%.')
    t = pd.DataFrame({"الشهر": labels, "كاش %": pay["Cash"].round(1).values, "InstaPay %": pay["InstaPay"].round(1).values,
                      "محافظ %": pay["Wallet"].round(1).values, "إلكتروني %": elec.values})
    cards.append(card("نسبة الدفع الإلكتروني من الفواتير", "سؤال 7", take, line_chart(
        labels, long_labels, [("إلكتروني", "var(--s1)", elec.tolist())], fmt=lambda v: f"{v:.1f}", unit="%",
        end_label=True, tick_fmt=lambda v: f"{v:.0f}%") + details(t)))

    # ── 8) expiry
    bd = exp["by_doc"].reset_index(name="n")
    t = pd.DataFrame({"الفرع": bd.branch.map(BRANCH_AR).values, "الدكتور": bd.pharmacist.map(DOCTOR_AR).values, "حالات": bd.n.values})
    take = (f'<b>{exp["rows"]}</b> مرة اتباع فيها دوا بعد انتهاء صلاحيته (<b>{exp["units"]}</b> علبة بقيمة {n0(exp["value"])} جنيه). '
            f'الحالات موزعة على الأربع دكاترة والفرعين، يعني المشكلة في متابعة الصلاحية مش في شخص.')
    body = (table(t) + f'<div class="note crit">⚠ محتاج جرد فوري للرفوف في الفرعين.</div>'
            f'<div class="note warn">ℹ فيه {exp["missing"]} سطر تاريخ الصلاحية فيهم مش متسجل، فالرقم ده هو الحد الأدنى.</div>')
    cards.append(card("بيع بعد انتهاء الصلاحية", "سؤال 8 · الأولوية الأولى", take, body))

    # ── 9) antibiotics
    ab = d["ab_month"].round(1)
    take = (f'المضادات الحيوية <b>{d["ab_branch"][K]:.1f}%</b> من سطور البيع في الخارجة و<b>{d["ab_branch"][M]:.1f}%</b> في موط. '
            f'في الشتا (أكتوبر–مارس) <b>{d["ab_winter"]:.1f}%</b> مقابل <b>{d["ab_rest"]:.1f}%</b> باقي السنة.')
    t = pd.DataFrame({"الشهر": labels, "النسبة %": ab.values})
    cards.append(card("نسبة المضادات الحيوية من سطور البيع", "سؤال 9", take, line_chart(
        labels, long_labels, [("المضادات الحيوية", "var(--s1)", ab.tolist())], fmt=lambda v: f"{v:.1f}", unit="%",
        tick_fmt=lambda v: f"{v:.0f}%") + details(t)))

    # ── 10) forecast
    fc = d["fc"]
    q = fc.groupby("branch")[["low", "mid", "high"]].sum()
    scale = fc.high.max() * 1.05
    rows = [(f'{BRANCH_AR[r.branch]} · {MONTH_AR[r.m]} {r.year}', BRANCH_COLOR[r.branch], r.low, r.mid, r.high)
            for r in fc.itertuples()]
    take = (f'المتوقع للربع (أكتوبر–ديسمبر): الخارجة <b>{n0(q.loc[K, "mid"])}</b> (من {n0(q.loc[K, "low"])} إلى {n0(q.loc[K, "high"])}) '
            f'وموط <b>{n0(q.loc[M, "mid"])}</b> (من {n0(q.loc[M, "low"])} إلى {n0(q.loc[M, "high"])}) جنيه.')
    t = pd.DataFrame({"الفرع": fc.branch.map(BRANCH_AR).values, "الشهر": fc.m.map(MONTH_AR).values,
                      "السنة اللي فاتت": fc.last_year.map(n0).values, "أقل": fc.low.map(n0).values,
                      "المتوقع": fc.mid.map(n0).values, "أعلى": fc.high.map(n0).values})
    body = (branch_legend + range_rows(rows, scale) + details(t) +
            f'<div class="note warn">ℹ توقع تقريبي للتخطيط: مبني على {d["n_months"]} شهر بس. النقطة هي المتوقع والشريط هو المدى.</div>')
    cards.append(card("توقع الإيراد للشهور الجاية", "سؤال 10", take, body, wide=True))

    return f"""<!doctype html>
<html lang="ar" dir="rtl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>لوحة صيدلية الزهراء</title><style>{CSS}</style></head>
<body><main>
<h1>لوحة متابعة صيدلية الزهراء</h1>
<p class="sub">الفرعين: الخارجة وموط - الداخلة · من {d['start']:%Y-%m-%d} إلى {d['end']:%Y-%m-%d}</p>
<div class="grid">{''.join(cards)}</div>
<footer>الأرقام من شيت المبيعات بعد التنضيف ({n0(d['lines'])} سطر). المرتجعات مخصومة من الإيراد.
{d['pay_unknown']} فاتورة طريقة الدفع فيها مش متسجلة ومش داخلة في نسبة الدفع. دوس على أي رسمة تشوف الرقم.</footer>
</main><div id="tip" hidden></div><script>{JS}</script></body></html>"""


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    d = compute()
    path = OUT / "dashboard.html"
    path.write_text(build_html(d), encoding="utf-8")
    print("saved:", path, f"({path.stat().st_size / 1024:.0f} KB)")
    print("revenue", round(d["revenue"], 2), "| invoices", d["invoices"], "| expired", d["exp"]["rows"])
    print(d["fc"].groupby("branch")[["low", "mid", "high"]].sum().round(0).to_dict())


if __name__ == "__main__":
    main()
