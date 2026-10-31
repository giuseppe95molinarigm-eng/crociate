"""Render the concept-and-outline Markdown files as Elite Publishing styled PDFs.

Usage: python3 build.py   (needs pandoc, node + playwright, the Inter and Poppins fonts installed)
"""
import html
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from pypdf import PdfReader, PdfWriter

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

LOGO = ('<div class="logo"><svg width="22" height="28" viewBox="0 0 22 28">'
        '<rect x="0" y="0" width="22" height="28" rx="2" fill="#e18935"/>'
        '<rect x="0" y="0" width="5" height="28" rx="1.5" fill="#b86a22"/></svg>'
        '<div><span class="e">Elite</span>Publishing</div></div>')

BOOKS = [
    {
        "md": "Your-Insecurity-Is-Showing_Book-1-Concept-and-Outline.md",
        "title": ("Your Insecurity", "Is Showing"),
        "label": "Book 1 · Concept &amp; Outline",
        "short": "Your Insecurity Is Showing · Concept &amp; Outline",
        "series": "Book 1 of the “Showing” series",
        "lede": "Concept, positioning, voice guide and a detailed chapter-by-chapter outline for "
                "the first book in a bold, witty, tough-love self-worth series for women, with "
                "Reality Checks, a word plan and the map of how Book 1 and Book 2 fit together.",
        "check": r"(?:Final )?Reality Check",
    },
    {
        "md": "Your-Power-Is-Showing_Book-2-Concept-and-Outline.md",
        "title": ("Your Power", "Is Showing"),
        "label": "Book 2 · Concept &amp; Outline",
        "short": "Your Power Is Showing · Concept &amp; Outline",
        "series": "Book 2 of the “Showing” series",
        "lede": "Concept, positioning, voice guide and a detailed chapter-by-chapter outline for "
                "the second book in the series: standards, ambition, money, presence and "
                "relationships, with Power Checks, a word plan and a topic-by-topic map against Book 1.",
        "check": r"(?:Final )?Power Check",
    },
]

NUM_WORDS = {"ONE": "One", "TWO": "Two", "THREE": "Three"}


def transform(body, book):
    # Title block is replaced by the cover; the intro becomes an overview page.
    body = re.sub(r"<h1[^>]*>.*?</h1>\s*<p>.*?</p>", "", body, count=1, flags=re.S)
    body = body.replace("<hr />", "")
    body = re.sub(r"<p><strong>Contents</strong></p>\s*<ol[^>]*>",
                  '<h3>Contents</h3><div class="contents"><ol>', body, count=1)
    body = re.sub(r'(<div class="contents"><ol>.*?</ol>)', r"\1</div>", body, count=1, flags=re.S)
    body = '<div class="eyebrow">Overview</div><h2>About this document</h2>' + body

    # Numbered sections: eyebrow + title on a new page.
    body = re.sub(r'<h2 id="[^"]*">(\d+)\. (.*?)</h2>',
                  lambda m: f'<div class="eyebrow pb">Section {int(m[1]):02d}</div><h2>{m[2]}</h2>', body)

    # Part dividers.
    def part(m):
        return (f'<div class="part"><div class="eyebrow">Part {NUM_WORDS[m[1]]}</div>'
                f'<div class="ptitle">{m[2].title()}</div><p class="psub">{m[3]}</p></div>')
    body = re.sub(r'<h3 id="[^"]*">PART (ONE|TWO|THREE): (.*?)</h3>\s*<p><em>(.*?)</em></p>', part, body)

    # Chapters, introduction and conclusion start on a new page (unless right after a part divider).
    def chap(m):
        kind, num, title = m[1], m[2], m[3]
        label = f"Chapter {int(num):02d}" if num else kind
        return f'<div class="eyebrow pb">{label}</div><h3 class="chap">{title}</h3>'
    body = re.sub(r'<h3 id="[^"]*">(Introduction|Conclusion|Chapter) ?(\d+)?: (.*?)</h3>', chap, body)
    body = re.sub(r'(</div>\s*)<div class="eyebrow pb">(Chapter)', r'\1<div class="eyebrow">\2', body)

    body = re.sub(r"<p><strong>Planned length:</strong> (.*?)</p>",
                  r'<div class="meta"><span>Planned length</span>\1</div>', body)
    body = body.replace("<p><strong>Your story (optional).</strong>",
                        '<p class="story"><strong>Your story (optional).</strong>')

    # End-of-chapter exercise boxes.
    body = re.sub(
        rf"<p><strong>({book['check']})</strong></p>(.*?<p><strong>(?:This week|Final (?:action|move)).*?</p>)",
        r'<div class="check"><div class="eyebrow">\1</div>\2</div>', body, flags=re.S)
    return body


def cover(book):
    t1, t2 = book["title"]
    return f"""<section class="cover">
  {LOGO}
  <div class="byline">BY ELITE PUBLISHING AGENCY</div>
  <div class="mid">
    <div class="eyebrow">Women's empowerment · {book['label']}</div>
    <h1>{t1}<span class="o">{t2}</span></h1>
    <p class="lede">{book['lede']}</p>
    <div class="pills"><span class="pill"><b>01</b>Concept &amp; positioning</span>
      <span class="pill"><b>02</b>Voice guide</span><span class="pill"><b>03</b>Chapter-by-chapter outline</span></div>
  </div>
  <div class="foot"><div>Prepared for<b>Mijke</b></div><div>Series<b>{book['series']}</b></div>
    <div>Date<b>October 2026</b></div></div>
</section>"""


def page(content, css):
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
            f"<style>{css}</style></head><body>{content}</body></html>")


HEADER = """<div style="-webkit-print-color-adjust:exact;position:absolute;top:0;left:0;right:0;height:15mm;
background:#0c0e12;display:flex;align-items:center;justify-content:space-between;padding:0 18mm;margin:0">
<span style="font-family:'Poppins';font-weight:700;font-size:11px;color:#fff"><span style="color:#e18935">Elite</span>Publishing</span>
<span style="font-family:'Inter';font-size:7px;letter-spacing:3px;color:#9a9ca2;text-transform:uppercase">{label}</span></div>"""

FOOTER = """<div style="width:100%;margin:0 18mm;border-top:1px solid #e6e6e8;padding-top:6px;display:flex;
justify-content:space-between;font-family:'Inter';font-size:7px;color:#9a9ca2">
<span>{short} · Prepared for Mijke</span>
<span><span style="color:#e18935">Elite</span> Publishing · <span class="pageNumber"></span></span></div>"""

PDF_JS = r"""
const { chromium } = require('playwright');
const [cover, body, outCover, outBody, header, footer] = process.argv.slice(2);
(async () => {
  const b = await chromium.launch(); const p = await b.newPage();
  await p.goto('file://' + cover); await p.evaluate(() => document.fonts.ready);
  await p.pdf({ path: outCover, width: '210mm', height: '297mm', printBackground: true,
                margin: { top: 0, bottom: 0, left: 0, right: 0 } });
  await p.goto('file://' + body); await p.evaluate(() => document.fonts.ready);
  await p.pdf({ path: outBody, format: 'A4', printBackground: true, displayHeaderFooter: true,
                headerTemplate: header, footerTemplate: footer,
                margin: { top: '27mm', bottom: '20mm', left: '18mm', right: '18mm' } });
  await b.close();
})();
"""


def build(book, tmp):
    css = (HERE / "style.css").read_text()
    md = ROOT / book["md"]
    body = subprocess.run(["pandoc", str(md), "-f", "gfm", "-t", "html5", "--wrap=none"],
                          check=True, capture_output=True, text=True).stdout
    # The spacer page makes the body's page numbers start at 2, after the cover.
    body_html = page('<div class="spacer"></div>' + transform(body, book), css)
    stem = md.stem
    (tmp / f"{stem}-cover.html").write_text(page(cover(book), css))
    (tmp / f"{stem}-body.html").write_text(body_html)
    js = tmp / "pdf.js"
    js.write_text(PDF_JS)
    subprocess.run(["node", str(js), str(tmp / f"{stem}-cover.html"), str(tmp / f"{stem}-body.html"),
                    str(tmp / f"{stem}-cover.pdf"), str(tmp / f"{stem}-body.pdf"),
                    HEADER.format(label=book["label"]), FOOTER.format(short=book["short"])],
                   check=True)
    out = PdfWriter()
    out.append(PdfReader(tmp / f"{stem}-cover.pdf"))
    out.append(PdfReader(tmp / f"{stem}-body.pdf"), pages=(1, len(PdfReader(tmp / f"{stem}-body.pdf").pages)))
    out.add_metadata({"/Title": html.unescape(book["short"]), "/Author": "Elite Publishing"})
    with open(ROOT / f"{stem}.pdf", "wb") as f:
        out.write(f)
    print("wrote", ROOT / f"{stem}.pdf")


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as d:
        for book in BOOKS:
            build(book, Path(d))
    sys.exit(0)
