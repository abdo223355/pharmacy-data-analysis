"""Project documentation PDF: screenshots (dashboard, deck slides) + excerpts of the core code + how to run it.

No customer data inside: screenshots show totals and branch/pharmacist names only; the code is excerpted from the scripts.
Needs Microsoft Edge (screenshots and PDF printing), pymupdf and Pillow. Run after building the dashboard and the deck:
    .venv\Scripts\python.exe scripts\build_project_pdf.py
Output: reports/submission/project_documentation.pdf
"""
import ast
import base64
import io
import subprocess
import time
from html import escape
from pathlib import Path

import pymupdf
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports" / "submission"
TMP = OUT / "_tmp"
EDGE = next(p for p in [r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"] if Path(p).exists())


def edge(*args):
    subprocess.run([EDGE, "--headless", "--disable-gpu", "--no-pdf-header-footer", *args],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
    time.sleep(2)


def b64(img: Image.Image, fmt="PNG"):
    buf = io.BytesIO()
    img.convert("RGB").save(buf, fmt, optimize=True) if fmt == "PNG" else img.convert("RGB").save(buf, fmt, quality=82)
    return f"data:image/{fmt.lower()};base64," + base64.b64encode(buf.getvalue()).decode()


def figure(img, caption, width="100%", fmt="PNG"):
    return f'<figure style="width:{width}"><img src="{b64(img, fmt)}"><figcaption>{caption}</figcaption></figure>'


def code(src, title):
    return f'<div class="code"><div class="ct">{escape(title)}</div><pre>{escape(src.rstrip())}</pre></div>'


def method_src(path, cls, name):
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text)
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == cls:
            for f in node.body:
                if isinstance(f, ast.FunctionDef) and f.name == name:
                    import textwrap
                    return textwrap.dedent(ast.get_source_segment(text, f))
    raise KeyError(name)


def slice_between(path, start, end):
    t = path.read_text(encoding="utf-8")
    i = t.index(start)
    return t[i:t.index(end, i)]


def main():
    TMP.mkdir(parents=True, exist_ok=True)

    # ── dashboard screenshots: each group of cards goes in a temporary light-mode page, cropped to the content height
    import re
    from PIL import ImageChops
    dash = (ROOT / "reports" / "dashboard" / "dashboard.html").read_text(encoding="utf-8")
    css_d = re.search(r"<style>(.*?)</style>", dash, re.S).group(1).replace("prefers-color-scheme:dark", "prefers-color-scheme:never")
    js_d = re.search(r"<script>(.*?)</script>", dash, re.S).group(1)
    cards = re.findall(r'<section class="card.*?</section>', dash, re.S)

    def shot(idx, width, name, scale=1.5):
        body = "".join(cards[i] for i in idx)
        page = (f'<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">'
                f'<style>{css_d}</style></head><body><main><div class="grid">{body}</div></main><div id="tip" hidden></div><script>{js_d}</script></body></html>')
        f = TMP / f"{name}.html"
        f.write_text(page, encoding="utf-8")
        edge(f"--screenshot={TMP / (name + '.png')}", f"--window-size={width},3200", f"--force-device-scale-factor={scale}", f.as_uri())
        im = Image.open(TMP / f"{name}.png").convert("RGB")
        bg = Image.new("RGB", im.size, im.getpixel((2, im.height - 2)))
        box = ImageChops.difference(im, bg).getbbox()
        return im.crop((0, 0, im.width, min(im.height, (box[3] + 14) if box else im.height)))

    m1 = shot([0, 1], 400, "m1")
    m2 = shot([4], 400, "m2")
    m3 = shot([10], 400, "m3")
    dd = shot([0, 1], 1000, "d1", scale=1)

    # ── deck slides
    pdf_path = ROOT / "reports" / "deck" / "alzahraa_results.pdf"
    if not pdf_path.exists():
        raise SystemExit("export the deck to PDF first (reports/deck/alzahraa_results.pdf)")
    doc = pymupdf.open(pdf_path)
    slides = {}
    for n in (3, 4, 6, 9, 10):
        pix = doc[n - 1].get_pixmap(dpi=72)
        slides[n] = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)

    # ── code
    cp = ROOT / "scripts" / "clean_pipeline.py"
    snip = {
        "standardize": method_src(cp, "Cleaner", "dedupe"),
        "dates": method_src(cp, "Cleaner", "fix_dates"),
        "forecast": slice_between(ROOT / "scripts" / "build_dashboard.py", "    # 10) التوقع", '    d["fc"]'),
    }

    css = """
@page{size:A4;margin:13mm}
*{box-sizing:border-box}
body{font-family:"Segoe UI",Tahoma,Arial,sans-serif;color:#1c2430;line-height:1.7;font-size:11pt}
h1{font-size:20pt;margin:0 0 2px} h2{font-size:14pt;margin:18px 0 6px;border-bottom:2px solid #e2e6ec;padding-bottom:3px;break-after:avoid}
.sub{color:#5b6675;margin:0 0 10px} p{margin:4px 0 8px}
figure{margin:8px auto;break-inside:avoid;text-align:center} figure img{max-width:100%;border:1px solid #e2e6ec;border-radius:6px}
figcaption{color:#5b6675;font-size:9.5pt;margin-top:2px}
.row{display:flex;gap:10px;align-items:flex-start} .row figure{flex:1;margin:4px 0}
.code{direction:ltr;text-align:left;margin:8px 0;break-inside:auto}
.ct{unicode-bidi:plaintext;background:#0b5563;color:#fff;font:600 9.5pt Consolas,monospace;padding:3px 10px;border-radius:6px 6px 0 0}
pre{margin:0;background:#f5f7f9;border:1px solid #e2e6ec;border-top:0;border-radius:0 0 6px 6px;padding:8px 10px;
font:8.2pt/1.45 Consolas,"Courier New",monospace;white-space:pre-wrap;overflow-wrap:anywhere}
ol,ul{padding-inline-start:20px;margin:4px 0} li{margin-bottom:3px}
code.i{font-family:Consolas,monospace;direction:ltr;unicode-bidi:isolate;background:#eef1f5;padding:0 4px;border-radius:4px;font-size:9.5pt}
.note{background:#fff4dc;color:#6b4700;border-radius:8px;padding:6px 10px;margin:8px 0;font-size:10pt}
"""
    html = f"""<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8"><title>توثيق مشروع صيدلية الزهراء</title>
<style>{css}</style></head><body>

<h1>توثيق مشروع تحليل مبيعات صيدلية الزهراء</h1>
<p class="sub">لقطات من التسليمات + مقتطفات من الكود الأساسي + طريقة التشغيل</p>
<div class="note">اللقطات من الداشبورد والعرض (إجماليات وأسماء فروع ودكاترة). مفيش أرقام موبايلات عملاء في الملف ده.</div>

<h2>1) الداشبورد (بيفتح على الموبايل)</h2>
<p>صفحة واحدة بتشتغل من غير إنترنت، فيها الأسئلة العشرة، وكل رسمة تحتها «عرض الجدول» بالأرقام، ودوس على أي نقطة بيطلع الرقم.</p>
<div class="row">
{figure(m1, "الموبايل: الملخص وإيراد الفرعين", fmt="JPEG")}
{figure(m2, "الموبايل: خصومات الدكاترة", fmt="JPEG")}
{figure(m3, "الموبايل: توقع الشهور الجاية بمدى", fmt="JPEG")}
</div>
{figure(dd, "الديسكتوب: نفس الصفحة بتتمدد على عرض الشاشة", fmt="JPEG")}

<h2>2) عرض النتايج (12 شريحة)</h2>
<div class="row">{figure(slides[3], "أهم خمس حاجات")}{figure(slides[4], "الصلاحية: الأولوية الأولى")}</div>
<div class="row">{figure(slides[6], "الخصومات")}{figure(slides[9], "التوقع بمدى")}</div>
{figure(slides[10], "القرارات المطلوبة من العميل واقتراحنا لكل واحدة")}

<h2>3) الكود: التنضيف</h2>
<p>التنضيف في <code class="i">scripts/clean_pipeline.py</code>، ومقسوم لخطوات صغيرة بالترتيب: توحيد الصيغ، إزالة التكرار، تصليح التواريخ، التصنيف والدكتور والفرع، الدفع، المعادلة، المرتجعات والصلاحية.
أي سطر بيتشال بيتسجل في <code class="i">removed_rows.csv</code>، وأي خانة بتتغير بتتسجل في <code class="i">cleaning_changes.csv</code> بالقيمة القديمة والجديدة والسبب.</p>
{code(snip["standardize"], "clean_pipeline.py: dedupe()  (التكرار: نسخة كاملة، ثم نفس المفتاح بنسخة بوقت افتراضي)")}
{code(snip["dates"], "clean_pipeline.py: fix_dates()  (التواريخ الشاذة من رقم الفاتورة المتسلسل)")}

<h2>4) الكود: التوقع بمدى</h2>
<p>إيراد نفس الشهر السنة اللي فاتت × معدل النمو السنوي (من الشهور الموجودة في السنتين). المدى = النمو ± تذبذبه من شهر لشهر.</p>
{code(snip["forecast"], "build_dashboard.py: compute()  (سؤال 10)")}

<h2>5) إزاي تشغّل الكود على شيت جديد</h2>
<ol>
<li>ركّب المكتبات: <code class="i">pip install pandas openpyxl</code></li>
<li>حط الشيت الخام (بنفس الـ 17 عمود) في <code class="i">data/raw/</code></li>
<li><code class="i">python scripts/clean_pipeline.py</code> ← الشيت النضيف وورقة التنضيف في <code class="i">data/clean/</code></li>
<li><code class="i">python scripts/expiry_report.py</code> ← تقرير الصلاحية</li>
<li><code class="i">python scripts/build_dashboard.py</code> ← الداشبورد</li>
<li><code class="i">python scripts/build_report.py</code> ← التقرير النهائي</li>
</ol>
<div class="note">الكلام التفسيري في التقرير النهائي (المواسم والتوصيات) بيتراجع باليد لو الفترة اتغيرت. والأسماء الجديدة اللي الكود ما يعرفهاش بيعلّم عليها ومبيخمّنش.</div>

</body></html>"""
    htm = TMP / "project_documentation.html"
    htm.write_text(html, encoding="utf-8")
    out = OUT / "project_documentation.pdf"
    edge(f"--print-to-pdf={out}", htm.as_uri())
    d = pymupdf.open(out)
    print("saved", out, "| pages", len(d))
    for i, p in enumerate(d):
        pix = p.get_pixmap(dpi=45)
        Image.frombytes("RGB", (pix.width, pix.height), pix.samples).save(TMP / f"p{i + 1}.png")


if __name__ == "__main__":
    main()
