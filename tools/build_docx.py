"""Build a .docx report from an assignment's work.md.

Usage:
    python tools/build_docx.py subjects/<subject>/assignments/<NN-name>/work.md
    python tools/build_docx.py --all

Output goes to ``<assignment>/output/<assignment-name>.docx``.

Formatting (see CLAUDE.md): A4, margins 1 cm, Times New Roman 12 (tables 10),
justified, first-line indent in body paragraphs, no spacing between
paragraphs, line spacing 1.0. No title page.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pypandoc
from docx import Document
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

ROOT = Path(__file__).resolve().parent.parent

# --- Formatting rules -------------------------------------------------------
FONT = "Times New Roman"
BODY_PT = 12
TABLE_PT = 10
MARGIN_CM = 1
FIRST_LINE_INDENT_CM = 1.25
CODE_FONT = "Courier New"
CODE_PT = 10
PAGE_W_CM, PAGE_H_CM = 21.0, 29.7
CENTER_STYLES = {"Figure", "Captioned Figure", "Image Caption"}
# Pandoc paragraph styles that carry running text (they get the indent).
INDENTED_STYLES = {"First Paragraph", "Body Text"}


# --- Low-level docx helpers -------------------------------------------------
def force_font(rpr, name: str = FONT) -> None:
    """Set the font for all scripts and drop theme font references."""
    rfonts = rpr.get_or_add_rFonts()
    for attr in ("ascii", "hAnsi", "eastAsia", "cs"):
        rfonts.set(qn(f"w:{attr}"), name)
    for attr in ("asciiTheme", "hAnsiTheme", "eastAsiaTheme", "cstheme"):
        rfonts.attrib.pop(qn(f"w:{attr}"), None)


def plain_paragraph_format(pf, first_line_cm: float = 0) -> None:
    pf.first_line_indent = Cm(first_line_cm)
    pf.left_indent = Cm(0)
    pf.right_indent = Cm(0)
    pf.space_before = Pt(0)
    pf.space_after = Pt(0)
    pf.line_spacing = 1.0


def set_style_defaults(doc: Document) -> None:
    defaults = doc.styles.element.find(qn("w:docDefaults"))
    if defaults is not None:
        rpr = defaults.find(qn("w:rPrDefault") + "/" + qn("w:rPr"))
        if rpr is not None:
            force_font(rpr)

    for style in doc.styles:
        if style.type not in (WD_STYLE_TYPE.PARAGRAPH, WD_STYLE_TYPE.CHARACTER):
            continue
        force_font(style.element.get_or_add_rPr())
        style.font.size = Pt(BODY_PT)
        style.font.color.rgb = RGBColor(0, 0, 0)
        if style.name.startswith(("Heading", "Title")):
            style.font.bold = True
            style.font.italic = False
        if style.type == WD_STYLE_TYPE.PARAGRAPH:
            plain_paragraph_format(
                style.paragraph_format,
                FIRST_LINE_INDENT_CM if style.name in INDENTED_STYLES else 0,
            )
            style.paragraph_format.alignment = (
                WD_ALIGN_PARAGRAPH.CENTER if style.name in CENTER_STYLES
                else WD_ALIGN_PARAGRAPH.JUSTIFY
            )

    try:
        force_font(doc.styles["Verbatim Char"].element.get_or_add_rPr(), CODE_FONT)
        doc.styles["Verbatim Char"].font.size = Pt(CODE_PT)
        doc.styles["Source Code"].paragraph_format.alignment = WD_ALIGN_PARAGRAPH.LEFT
    except KeyError:
        pass  # no code blocks style in this document


def set_page(doc: Document) -> None:
    for s in doc.sections:
        s.page_width, s.page_height = Cm(PAGE_W_CM), Cm(PAGE_H_CM)
        s.left_margin = s.right_margin = Cm(MARGIN_CM)
        s.top_margin = s.bottom_margin = Cm(MARGIN_CM)
        s.header_distance = s.footer_distance = Cm(0.5)


def _insert_in_tblpr(tbl_pr, element) -> None:
    """Insert element keeping the CT_TblPr child order required by Word."""
    successors = ("shd", "tblLayout", "tblCellMar", "tblLook", "tblCaption", "tblDescription")
    for child in tbl_pr:
        if child.tag in {qn(f"w:{n}") for n in successors}:
            child.addprevious(element)
            return
    tbl_pr.append(element)


def format_tables(doc: Document) -> None:
    for table in doc.tables:
        tbl_pr = table._tbl.tblPr
        old = tbl_pr.find(qn("w:tblBorders"))
        if old is not None:
            tbl_pr.remove(old)
        borders = OxmlElement("w:tblBorders")
        for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
            el = OxmlElement(f"w:{edge}")
            el.set(qn("w:val"), "single")
            el.set(qn("w:sz"), "4")
            el.set(qn("w:space"), "0")
            el.set(qn("w:color"), "000000")
            borders.append(el)
        _insert_in_tblpr(tbl_pr, borders)

        for row in table.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    # Table text never gets the paragraph indent.
                    p.paragraph_format.first_line_indent = Cm(0)
                    for run in p.runs:
                        run.font.size = Pt(TABLE_PT)


def format_images(doc: Document) -> None:
    max_w = Cm(PAGE_W_CM - 2 * MARGIN_CM)
    for shape in doc.inline_shapes:
        if shape.width > max_w:
            ratio = max_w / shape.width
            shape.width, shape.height = int(max_w), int(shape.height * ratio)
    for p in doc.paragraphs:
        if p._p.find(".//" + qn("w:drawing")) is not None:
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.first_line_indent = Cm(0)


# --- Build ------------------------------------------------------------------
def build(work_md: Path) -> Path:
    folder = work_md.resolve().parent
    out = folder / "output" / f"{folder.name}.docx"
    out.parent.mkdir(parents=True, exist_ok=True)

    text = work_md.read_text(encoding="utf-8-sig")
    pypandoc.convert_text(
        text, "docx", format="markdown", outputfile=str(out),
        extra_args=[f"--resource-path={folder}"],
    )

    doc = Document(str(out))
    set_style_defaults(doc)
    set_page(doc)
    format_tables(doc)
    format_images(doc)
    doc.save(str(out))
    return out


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("work_md", nargs="*", type=Path)
    parser.add_argument("--all", action="store_true", help="build every assignment")
    args = parser.parse_args()

    files = list(args.work_md)
    if args.all:
        files += sorted((ROOT / "subjects").glob("*/assignments/*/work.md"))
    if not files:
        parser.error("specify work.md path(s) or --all")

    failed = 0
    for f in files:
        try:
            print(f"OK: {f} -> {build(f)}")
        except Exception as exc:
            failed += 1
            print(f"ОШИБКА: {f}: {exc}", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
