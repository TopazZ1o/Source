"""Build a conference-thesis .docx from a work.md (rules of the info letter).

Usage:
    python tools/build_thesis_docx.py subjects/<subject>/assignments/<NN-name>/work.md

Formatting follows the conference information letter, NOT the general
assignment rules in build_docx.py: A4, margins top/bottom 2 cm, left 3 cm,
right 1.5 cm, Times New Roman 14, single spacing, justified, automatic
hyphenation, 1.25 cm first-line indent in body text.

work.md layout: UDC line, "# TITLE", two fully italic paragraphs (author and
affiliation, right aligned), then body with "## Heading" sections, a table and
a reference list.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH as AL
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt

FONT, SIZE = "Times New Roman", 14
INDENT_CM = 1.25
INLINE = re.compile(r"(\*\*.+?\*\*|\*.+?\*)")


def setup(doc: Document) -> None:
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Cm(21.0), Cm(29.7)
    sec.top_margin = sec.bottom_margin = Cm(2)
    sec.left_margin, sec.right_margin = Cm(3), Cm(1.5)
    st = doc.styles["Normal"]
    st.font.name, st.font.size = FONT, Pt(SIZE)
    rfonts = st.element.get_or_add_rPr().get_or_add_rFonts()
    for a in ("ascii", "hAnsi", "eastAsia", "cs"):
        rfonts.set(qn(f"w:{a}"), FONT)
    pf = st.paragraph_format
    pf.space_before = pf.space_after = Pt(0)
    pf.line_spacing = 1.0
    # automatic hyphenation
    settings = doc.settings.element
    hyph = OxmlElement("w:autoHyphenation")
    settings.append(hyph)


def runs(par, text: str, bold=False, italic=False) -> None:
    for part in INLINE.split(text):
        if not part:
            continue
        b, i = bold, italic
        if part.startswith("**") and part.endswith("**") and len(part) > 4:
            part, b = part[2:-2], True
        elif part.startswith("*") and part.endswith("*") and len(part) > 2:
            part, i = part[1:-1], True
        r = par.add_run(part)
        r.bold, r.italic = b, i
        r.font.name, r.font.size = FONT, Pt(SIZE)


def para(doc, text="", align=AL.JUSTIFY, indent=0.0, **kw):
    p = doc.add_paragraph()
    p.alignment = align
    p.paragraph_format.first_line_indent = Cm(indent)
    if text:
        runs(p, text, **kw)
    return p


def table(doc, rows: list[list[str]]) -> None:
    t = doc.add_table(rows=len(rows), cols=len(rows[0]))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for ri, row in enumerate(rows):
        for ci, cell in enumerate(row):
            c = t.cell(ri, ci)
            p = c.paragraphs[0]
            p.alignment = AL.LEFT
            runs(p, cell)
    para(doc)  # spacer after the table


def build(src: Path) -> Path:
    lines = src.read_text(encoding="utf-8").split("\n")
    doc = Document()
    setup(doc)
    first_body = True
    i = 0
    while i < len(lines):
        ln = lines[i].rstrip()
        i += 1
        if not ln.strip():
            continue
        if ln.startswith("УДК"):
            para(doc, ln, AL.LEFT)
        elif ln.startswith("# "):
            para(doc, ln[2:].upper(), AL.CENTER, bold=True)
        elif re.fullmatch(r"\*[^*].*[^*]\*", ln):
            para(doc)  # one blank line before author / affiliation
            para(doc, ln, AL.RIGHT)
        elif ln.startswith("## "):
            para(doc, ln[3:], AL.LEFT, bold=True)
        elif ln.startswith("|"):
            rows = []
            while True:
                if not re.fullmatch(r"\|[\s|:-]+\|", ln):
                    rows.append([c.strip() for c in ln.strip("|").split("|")])
                if i >= len(lines) or not lines[i].startswith("|"):
                    break
                ln = lines[i].rstrip()
                i += 1
            rows = [r for r in rows if any(r)]
            table(doc, rows)
        elif ln.startswith("**Таблица"):
            para(doc, ln, AL.LEFT)
        elif re.match(r"\[\d+\]", ln):
            para(doc, ln)
        else:
            if first_body:
                para(doc)
                para(doc)  # two blank lines before the main text
                first_body = False
            para(doc, ln, indent=INDENT_CM)
    out = src.parent / "output" / (src.parent.name + ".docx")
    out.parent.mkdir(exist_ok=True)
    doc.save(out)
    return out


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    print("OK:", build(Path(sys.argv[1])))
