"""Mini library: one description of a diagram -> draw.io page (XML) and PNG (Pillow).

The same coordinates are used for both outputs, so the picture and the editable
.drawio file match. Not a general drawing tool: only the shapes needed for UML
diagrams of the report (classes, use cases, sequences, states, activities, objects).

Usage: see build_diagrams.py. Requires Pillow; Arial fonts from C:/Windows/Fonts.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from html import escape
from typing import Optional, Sequence

from PIL import Image, ImageDraw, ImageFont

FONT_DIR = "C:/Windows/Fonts/"
_FONTS: dict = {}
SS = 4        # supersampling factor
OUT = 2       # output scale of the PNG relative to logical coordinates
LINE_H = 1.25


def font(size: float, bold=False, italic=False):
    key = (size, bold, italic)
    if key not in _FONTS:
        name = "arialbd.ttf" if bold and not italic else "ariali.ttf" if italic and not bold \
            else "arialbi.ttf" if bold and italic else "arial.ttf"
        _FONTS[key] = ImageFont.truetype(FONT_DIR + name, int(round(size * SS)))
    return _FONTS[key]


def text_width(text: str, size=12, bold=False, italic=False) -> float:
    return font(size, bold, italic).getlength(text) / SS


def wrap_lines(text: str, width: float, size=12, bold=False, italic=False) -> list[str]:
    out = []
    for raw in text.split("\n"):
        words, line = raw.split(" "), ""
        for word in words:
            trial = word if not line else line + " " + word
            if text_width(trial, size, bold, italic) <= width or not line:
                line = trial
            else:
                out.append(line)
                line = word
        out.append(line)
    return out


@dataclass
class Shape:
    id: str
    x: float
    y: float
    w: float
    h: float

    def pt(self, side: str, t: float = 0.5):
        """Point on the border: side l/r/t/b, t = position along the side (0..1)."""
        if side == "l":
            return (self.x, self.y + self.h * t)
        if side == "r":
            return (self.x + self.w, self.y + self.h * t)
        if side == "t":
            return (self.x + self.w * t, self.y)
        return (self.x + self.w * t, self.y + self.h)

    @property
    def cx(self):
        return self.x + self.w / 2

    @property
    def cy(self):
        return self.y + self.h / 2


@dataclass
class Canvas:
    name: str
    w: int
    h: int
    items: list = field(default_factory=list)
    _n: int = 0

    def _id(self, prefix="c") -> str:
        self._n += 1
        return f"{prefix}{self._n}"

    # ------------------------------------------------------------ shapes
    def rect(self, x, y, w, h, text="", *, fill="#ffffff", stroke="#000000", rounded=0, dashed=False,
             size=12, bold=False, italic=False, underline=False, align="center", valign="middle",
             pad=4, sw=1, shape="rect", font_color="#000000") -> Shape:
        s = Shape(self._id(), x, y, w, h)
        self.items.append(dict(kind=shape, s=s, text=text, fill=fill, stroke=stroke, rounded=rounded,
                               dashed=dashed, size=size, bold=bold, italic=italic, underline=underline,
                               align=align, valign=valign, pad=pad, sw=sw, font_color=font_color))
        return s

    def ellipse(self, x, y, w, h, text="", **kw) -> Shape:
        return self.rect(x, y, w, h, text, shape="ellipse", **kw)

    def diamond(self, x, y, w, h, text="", **kw) -> Shape:
        return self.rect(x, y, w, h, text, shape="diamond", **kw)

    def note(self, x, y, w, h, text, **kw) -> Shape:
        kw.setdefault("fill", "#fff2cc")
        kw.setdefault("align", "left")
        kw.setdefault("valign", "top")
        return self.rect(x, y, w, h, text, shape="note", **kw)

    def label(self, x, y, w, h, text, *, size=12, bold=False, italic=False, align="center", valign="middle",
              bg=False, font_color="#000000", underline=False) -> Shape:
        s = Shape(self._id(), x, y, w, h)
        self.items.append(dict(kind="text", s=s, text=text, size=size, bold=bold, italic=italic, align=align,
                               valign=valign, bg=bg, font_color=font_color, underline=underline))
        return s

    def line(self, pts: Sequence[tuple], *, end="none", start="none", dashed=False, color="#000000",
             sw=1, src: Optional[Shape] = None, dst: Optional[Shape] = None) -> str:
        """Polyline with markers; end/start in none, open, filled, hollow, diamond, odiamond."""
        lid = self._id("e")
        self.items.append(dict(kind="line", id=lid, pts=list(pts), end=end, start=start, dashed=dashed,
                               color=color, sw=sw, src=src, dst=dst))
        return lid

    def actor(self, x, y, name, *, size=12) -> Shape:
        s = Shape(self._id(), x, y, 30, 60)
        self.items.append(dict(kind="actor", s=s, text=name, size=size))
        return s

    def bar(self, x, y, w, h, fill="#000000") -> Shape:
        return self.rect(x, y, w, h, fill=fill)

    def circle(self, cx, cy, r, *, fill="#000000", final=False) -> Shape:
        s = Shape(self._id(), cx - r, cy - r, 2 * r, 2 * r)
        self.items.append(dict(kind="final" if final else "initial", s=s))
        return s

    # ------------------------------------------------------------ UML helpers
    def class_box(self, x, y, w, name, attrs=(), ops=(), *, stereotype="", header="#dae8fc",
                  size=11, italic_name=False, min_h_attr=0) -> Shape:
        """Class with three compartments; returns a Shape covering the whole box."""
        lh = size * LINE_H

        def count(lines, bold=False, fsize=size):
            return sum(len(wrap_lines(t, w - 10, fsize, bold)) for t in lines) or 1

        head_lines = ([f"«{stereotype}»"] if stereotype else []) + [name]
        hh = (size + 1) * LINE_H * count(head_lines, True, size + 1) + 8
        self.rect(x, y, w, hh, "\n".join(head_lines), fill=header, bold=True, size=size + 1, italic=italic_name)
        total = hh
        if attrs or not ops:
            ah = max(lh * count(attrs) + 8, min_h_attr)
            self.rect(x, y + hh, w, ah, "\n".join(attrs), align="left", valign="top", size=size, pad=5)
            total += ah
        if ops:  # empty tuple or None: no operation compartment
            oh = lh * count(ops) + 8
            self.rect(x, y + total, w, oh, "\n".join(ops), align="left", valign="top", size=size, pad=5)
            total += oh
        return Shape(self._id("cb"), x, y, w, total)

    def fit(self, margin: int = 24) -> "Canvas":
        """Shrink or grow the page to the drawn content."""
        right = bottom = 0.0
        for it in self.items:
            if it["kind"] == "line":
                for x, y in it["pts"]:
                    right, bottom = max(right, x), max(bottom, y)
            else:
                sh = it["s"]
                right = max(right, sh.x + sh.w)
                bottom = max(bottom, sh.y + sh.h + (45 if it["kind"] == "actor" else 0))
        self.w, self.h = int(right + margin), int(bottom + margin)
        return self

    # ------------------------------------------------------------ rendering: PNG
    def to_png(self, path: str) -> None:
        img = Image.new("RGB", (self.w * SS, self.h * SS), "white")
        d = ImageDraw.Draw(img)
        for it in self.items:
            getattr(self, "_draw_" + it["kind"])(d, it)
        img = img.resize((self.w * OUT, self.h * OUT), Image.LANCZOS)
        img.save(path)

    @staticmethod
    def _p(v):
        return v * SS

    def _text_block(self, d, lines, x, y, w, h, *, size, bold, italic, align, valign, pad, color="#000000",
                    underline=False):
        f = font(size, bold, italic)
        lh = size * LINE_H
        total = lh * len(lines)
        if valign == "top":
            ty = y + pad
        elif valign == "bottom":
            ty = y + h - total - pad
        else:
            ty = y + (h - total) / 2
        for i, line in enumerate(lines):
            lw = text_width(line, size, bold, italic)
            if align == "left":
                tx = x + pad
            elif align == "right":
                tx = x + w - pad - lw
            else:
                tx = x + (w - lw) / 2
            yy = ty + i * lh + (lh - size) / 2 - size * 0.12
            d.text((self._p(tx), self._p(yy)), line, font=f, fill=color)
            if underline:
                uy = yy + size * 1.05
                d.line([self._p(tx), self._p(uy), self._p(tx + lw), self._p(uy)], fill=color, width=SS)

    def _draw_rect(self, d, it, polygon=None):
        s = it["s"]
        P = self._p
        fill = None if it.get("fill") == "none" else it.get("fill")
        if it["kind"] == "rect":
            if it["rounded"]:
                d.rounded_rectangle([P(s.x), P(s.y), P(s.x + s.w), P(s.y + s.h)], radius=P(it["rounded"]),
                                    fill=fill, outline=it["stroke"], width=int(P(it["sw"])))
            else:
                d.rectangle([P(s.x), P(s.y), P(s.x + s.w), P(s.y + s.h)], fill=fill, outline=it["stroke"],
                            width=int(P(it["sw"])))
        if it["text"]:
            lines = wrap_lines(it["text"], s.w - 2 * it["pad"], it["size"], it["bold"], it["italic"])
            self._text_block(d, lines, s.x, s.y, s.w, s.h, size=it["size"], bold=it["bold"], italic=it["italic"],
                             align=it["align"], valign=it["valign"], pad=it["pad"], color=it["font_color"],
                             underline=it["underline"])

    _draw_rect_kind = _draw_rect

    def _dashed_line(self, d, a, b, color, width, dash=6, gap=4):
        P = self._p
        length = math.dist(a, b)
        if length == 0:
            return
        ux, uy = (b[0] - a[0]) / length, (b[1] - a[1]) / length
        pos = 0.0
        while pos < length:
            end = min(pos + dash, length)
            d.line([P(a[0] + ux * pos), P(a[1] + uy * pos), P(a[0] + ux * end), P(a[1] + uy * end)],
                   fill=color, width=width)
            pos += dash + gap

    def _draw_ellipse(self, d, it):
        s, P = it["s"], self._p
        d.ellipse([P(s.x), P(s.y), P(s.x + s.w), P(s.y + s.h)], fill=it["fill"], outline=it["stroke"],
                  width=int(P(it["sw"])))
        self._draw_rect(d, dict(it, kind="ellipse_text"))

    def _draw_ellipse_text(self, d, it):
        self._draw_rect(d, it)

    def _draw_diamond(self, d, it):
        s, P = it["s"], self._p
        pts = [(P(s.cx), P(s.y)), (P(s.x + s.w), P(s.cy)), (P(s.cx), P(s.y + s.h)), (P(s.x), P(s.cy))]
        d.polygon(pts, fill=it["fill"], outline=it["stroke"])
        d.line(pts + [pts[0]], fill=it["stroke"], width=int(P(it["sw"])))
        self._draw_rect(d, dict(it, kind="ellipse_text", pad=max(it["pad"], s.w * 0.18)))

    def _draw_note(self, d, it):
        s, P = it["s"], self._p
        c = 10
        pts = [(s.x, s.y), (s.x + s.w - c, s.y), (s.x + s.w, s.y + c), (s.x + s.w, s.y + s.h), (s.x, s.y + s.h)]
        d.polygon([(P(a), P(b)) for a, b in pts], fill=it["fill"])
        d.line([(P(a), P(b)) for a, b in pts + [pts[0]]], fill=it["stroke"], width=int(P(it["sw"])))
        d.line([(P(s.x + s.w - c), P(s.y)), (P(s.x + s.w - c), P(s.y + c)), (P(s.x + s.w), P(s.y + c))],
               fill=it["stroke"], width=int(P(1)))
        self._draw_rect(d, dict(it, kind="ellipse_text"))

    def _draw_text(self, d, it):
        s, P = it["s"], self._p
        if it["bg"]:
            d.rectangle([P(s.x), P(s.y), P(s.x + s.w), P(s.y + s.h)], fill="#ffffff")
        lines = wrap_lines(it["text"], s.w, it["size"], it["bold"], it["italic"])
        self._text_block(d, lines, s.x, s.y, s.w, s.h, size=it["size"], bold=it["bold"], italic=it["italic"],
                         align=it["align"], valign=it["valign"], pad=0, color=it["font_color"],
                         underline=it["underline"])

    def _draw_initial(self, d, it):
        s, P = it["s"], self._p
        d.ellipse([P(s.x), P(s.y), P(s.x + s.w), P(s.y + s.h)], fill="#000000")

    def _draw_final(self, d, it):
        s, P = it["s"], self._p
        d.ellipse([P(s.x), P(s.y), P(s.x + s.w), P(s.y + s.h)], fill="#ffffff", outline="#000000", width=int(P(1.5)))
        m = s.w * 0.25
        d.ellipse([P(s.x + m), P(s.y + m), P(s.x + s.w - m), P(s.y + s.h - m)], fill="#000000")

    def _draw_actor(self, d, it):
        s, P = it["s"], self._p
        cx = s.cx
        r = 7
        d.ellipse([P(cx - r), P(s.y), P(cx + r), P(s.y + 2 * r)], outline="#000000", width=int(P(1.2)), fill="#ffffff")
        k = int(P(1.2))
        d.line([P(cx), P(s.y + 2 * r), P(cx), P(s.y + 38)], fill="#000000", width=k)
        d.line([P(cx - 14), P(s.y + 25), P(cx + 14), P(s.y + 25)], fill="#000000", width=k)
        d.line([P(cx), P(s.y + 38), P(cx - 12), P(s.y + 58)], fill="#000000", width=k)
        d.line([P(cx), P(s.y + 38), P(cx + 12), P(s.y + 58)], fill="#000000", width=k)
        lines = wrap_lines(it["text"], 120, it["size"])
        self._text_block(d, lines, cx - 60, s.y + 60, 120, 40, size=it["size"], bold=False, italic=False,
                         align="center", valign="top", pad=2)

    def _draw_line(self, d, it):
        P = self._p
        pts, w = it["pts"], int(P(it["sw"]))
        color = it["color"]
        pts = list(pts)
        end, start = it["end"], it["start"]
        # shorten the line under hollow/diamond markers so the line does not poke through
        draw_pts = [tuple(p) for p in pts]

        def shorten(a, b, amount):
            length = math.dist(a, b)
            if length == 0:
                return a
            return (a[0] + (b[0] - a[0]) / length * amount, a[1] + (b[1] - a[1]) / length * amount)

        if end in ("hollow", "filled") and len(draw_pts) >= 2:
            draw_pts[-1] = shorten(draw_pts[-1], draw_pts[-2], 9 if end == "hollow" else 8)
        if start in ("diamond", "odiamond") and len(draw_pts) >= 2:
            draw_pts[0] = shorten(draw_pts[0], draw_pts[1], 14)
        for a, b in zip(draw_pts, draw_pts[1:]):
            if it["dashed"]:
                self._dashed_line(d, a, b, color, w)
            else:
                d.line([P(a[0]), P(a[1]), P(b[0]), P(b[1])], fill=color, width=w)
        self._marker(d, pts[-1], pts[-2], end, color, w)
        self._marker(d, pts[0], pts[1], start, color, w)

    def _marker(self, d, tip, frm, kind, color, w):
        if kind == "none":
            return
        P = self._p
        ang = math.atan2(tip[1] - frm[1], tip[0] - frm[0])
        ux, uy = math.cos(ang), math.sin(ang)
        nx, ny = -uy, ux
        if kind == "open":
            L, H = 10, 5
            for sgn in (1, -1):
                d.line([P(tip[0]), P(tip[1]), P(tip[0] - ux * L + nx * H * sgn), P(tip[1] - uy * L + ny * H * sgn)],
                       fill=color, width=w)
        elif kind in ("filled", "hollow"):
            L, H = (9, 6) if kind == "hollow" else (10, 5)
            pts = [(P(tip[0]), P(tip[1])), (P(tip[0] - ux * L + nx * H), P(tip[1] - uy * L + ny * H)),
                   (P(tip[0] - ux * L - nx * H), P(tip[1] - uy * L - ny * H))]
            d.polygon(pts, fill=color if kind == "filled" else "#ffffff", outline=color)
            d.line(pts + [pts[0]], fill=color, width=w)
        elif kind in ("diamond", "odiamond"):
            L, H = 14, 5
            pts = [(P(tip[0]), P(tip[1])), (P(tip[0] + ux * L / 2 + nx * H), P(tip[1] + uy * L / 2 + ny * H)),
                   (P(tip[0] + ux * L), P(tip[1] + uy * L)),
                   (P(tip[0] + ux * L / 2 - nx * H), P(tip[1] + uy * L / 2 - ny * H))]
            d.polygon(pts, fill=color if kind == "diamond" else "#ffffff", outline=color)
            d.line(pts + [pts[0]], fill=color, width=w)

    # ------------------------------------------------------------ rendering: draw.io
    def to_drawio_page(self, index: int) -> str:
        cells = ['<mxCell id="0"/>', '<mxCell id="1" parent="0"/>']
        pid = f"p{index}_"
        for it in self.items:
            cells.append(self._cell(pid, it))
        body = "".join(cells)
        return (f'<diagram id="{pid}d" name="{escape(self.name)}"><mxGraphModel dx="1000" dy="700" grid="1" '
                f'gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" '
                f'pageWidth="{self.w}" pageHeight="{self.h}" math="0" shadow="0"><root>{body}</root>'
                f'</mxGraphModel></diagram>')

    @staticmethod
    def _html(text: str) -> str:
        return escape(text, quote=True).replace("\n", "&lt;br&gt;")

    def _cell(self, pid: str, it: dict) -> str:
        kind = it["kind"]
        if kind == "line":
            return self._edge(pid, it)
        s: Shape = it["s"]
        geo = f'<mxGeometry x="{s.x:g}" y="{s.y:g}" width="{s.w:g}" height="{s.h:g}" as="geometry"/>'
        cid = pid + s.id
        if kind in ("rect", "ellipse", "diamond", "note"):
            base = {"rect": "rounded=%d;arcSize=20;" % (1 if it["rounded"] else 0), "ellipse": "ellipse;",
                    "diamond": "rhombus;", "note": "shape=note;size=10;"}[kind]
            style = (f"{base}whiteSpace=wrap;html=1;fillColor={it['fill']};strokeColor={it['stroke']};"
                     f"strokeWidth={it['sw']};fontSize={it['size']};align={it['align']};verticalAlign={it['valign']};"
                     f"spacingLeft={it['pad']};spacingRight={it['pad']};fontColor={it['font_color']};"
                     f"fontStyle={(1 if it['bold'] else 0) + (2 if it['italic'] else 0) + (4 if it['underline'] else 0)};"
                     + ("dashed=1;" if it["dashed"] else ""))
            return (f'<mxCell id="{cid}" value="{self._html(it["text"])}" style="{style}" vertex="1" parent="1">'
                    f'{geo}</mxCell>')
        if kind == "text":
            style = (f"text;html=1;whiteSpace=wrap;fontSize={it['size']};align={it['align']};"
                     f"verticalAlign={it['valign']};fontColor={it['font_color']};"
                     f"fontStyle={(1 if it['bold'] else 0) + (2 if it['italic'] else 0) + (4 if it['underline'] else 0)};"
                     + ("fillColor=#ffffff;" if it["bg"] else "fillColor=none;") + "strokeColor=none;spacing=0;")
            return (f'<mxCell id="{cid}" value="{self._html(it["text"])}" style="{style}" vertex="1" parent="1">'
                    f'{geo}</mxCell>')
        if kind == "actor":
            style = ("shape=umlActor;verticalLabelPosition=bottom;verticalAlign=top;html=1;outlineConnect=0;"
                     f"fontSize={it['size']};")
            return (f'<mxCell id="{cid}" value="{self._html(it["text"])}" style="{style}" vertex="1" parent="1">'
                    f'{geo}</mxCell>')
        if kind in ("initial", "final"):
            style = ("ellipse;html=1;shape=startState;fillColor=#000000;strokeColor=#000000;" if kind == "initial"
                     else "ellipse;html=1;shape=endState;fillColor=#000000;strokeColor=#000000;")
            return f'<mxCell id="{cid}" value="" style="{style}" vertex="1" parent="1">{geo}</mxCell>'
        raise ValueError(kind)

    def _edge(self, pid: str, it: dict) -> str:
        end_map = {"none": ("none", 0), "open": ("open", 0), "filled": ("block", 1), "hollow": ("block", 0)}
        start_map = {"none": ("none", 0), "diamond": ("diamondThin", 1), "odiamond": ("diamondThin", 0),
                     "open": ("open", 0), "filled": ("block", 1), "hollow": ("block", 0)}
        ea, ef = end_map[it["end"]]
        sa, sf = start_map[it["start"]]
        style = (f"edgeStyle=none;html=1;rounded=0;endArrow={ea};endFill={ef};startArrow={sa};startFill={sf};"
                 f"strokeColor={it['color']};strokeWidth={it['sw']};endSize=8;startSize=10;"
                 + ("dashed=1;" if it["dashed"] else ""))
        pts = it["pts"]
        src, dst = it["src"], it["dst"]
        attrs = ""
        if src is not None:
            attrs += f' source="{pid}{src.id}"'
            style += self._constraint("exit", pts[0], src)
        if dst is not None:
            attrs += f' target="{pid}{dst.id}"'
            style += self._constraint("entry", pts[-1], dst)
        mid = "".join(f'<mxPoint x="{x:g}" y="{y:g}"/>' for x, y in pts[1:-1])
        arr = f'<Array as="points">{mid}</Array>' if mid else ""
        geo = (f'<mxGeometry relative="1" as="geometry"><mxPoint x="{pts[0][0]:g}" y="{pts[0][1]:g}" as="sourcePoint"/>'
               f'<mxPoint x="{pts[-1][0]:g}" y="{pts[-1][1]:g}" as="targetPoint"/>{arr}</mxGeometry>')
        return f'<mxCell id="{pid}{it["id"]}" value="" style="{style}" edge="1" parent="1"{attrs}>{geo}</mxCell>'

    @staticmethod
    def _constraint(prefix: str, p, shape: Shape) -> str:
        fx = min(max((p[0] - shape.x) / shape.w, 0), 1) if shape.w else 0.5
        fy = min(max((p[1] - shape.y) / shape.h, 0), 1) if shape.h else 0.5
        return f"{prefix}X={fx:.3f};{prefix}Y={fy:.3f};{prefix}Dx=0;{prefix}Dy=0;"


def drawio_file(canvases: list[Canvas]) -> str:
    pages = "".join(c.to_drawio_page(i + 1) for i, c in enumerate(canvases))
    return f'<mxfile host="app.diagrams.net" agent="Claude" version="24.7.0">{pages}</mxfile>'
