"""UML-диаграммы СРМ №10: Use Case, Class, две Sequence, State Machine.

Подключается из make_diagrams.py: функция uml_pages() рисует PNG в assets/ и возвращает страницы для drawio.
Сцена описывается примитивами (прямоугольник, эллипс, актёр, линия, текст), из неё строятся и PNG (Pillow), и drawio.
"""
from xml.sax.saxutils import escape

from PIL import Image, ImageDraw, ImageFont

FONT = "C:/Windows/Fonts/arial.ttf"
FONT_B = "C:/Windows/Fonts/arialbd.ttf"
S = 2


def fnt(size, bold=False):
    return ImageFont.truetype(FONT_B if bold else FONT, int(size * S))


def wrap(d, text, f, width):
    out = []
    for para in str(text).split("\n"):
        cur = ""
        for w in para.split():
            t = (cur + " " + w).strip()
            if d.textlength(t, font=f) <= width * S or not cur:
                cur = t
            else:
                out.append(cur)
                cur = w
        out.append(cur)
    return out


class Scene:
    def __init__(self, name, title, w, h):
        self.name, self.title, self.w, self.h, self.items = name, title, w, h, []

    # примитивы
    def box(self, x, y, w, h, text, fill="#fffbe6", bold=False, rounded=True, align="center", size=10.5):
        self.items.append(("box", x, y, w, h, text, fill, bold, rounded, align, size))

    def ellipse(self, cx, cy, w, h, text):
        self.items.append(("ellipse", cx, cy, w, h, text))

    def actor(self, cx, y, name):
        self.items.append(("actor", cx, y, name))

    def text(self, x, y, txt, size=10, bold=False, color="#111"):
        self.items.append(("text", x, y, txt, size, bold, color))

    def line(self, pts, label=None, dashed=False, arrow="open", lpos=None, lalign="center"):
        self.items.append(("line", pts, label, dashed, arrow, lpos, lalign))

    def frame(self, x, y, w, h, label, dashed=False):
        self.items.append(("frame", x, y, w, h, label, dashed))

    def classbox(self, x, y, w, name, attrs, ops, stereotype=None):
        self.items.append(("class", x, y, w, name, attrs, ops, stereotype))

    def dot(self, cx, cy, r, ring=False):
        self.items.append(("dot", cx, cy, r, ring))

    # ---------- PNG ----------
    def png(self, path):
        img = Image.new("RGB", (int(self.w * S), int(self.h * S)), "white")
        d = ImageDraw.Draw(img)
        d.text((10 * S, 6 * S), self.title, fill="#222", font=fnt(12, True))
        for it in self.items:
            k = it[0]
            if k == "frame":
                _, x, y, w, h, label, dashed = it
                self._rect(d, x, y, w, h, "#555", dashed)
                if label:
                    tw = d.textlength(label, font=fnt(9.5, True)) / S + 10
                    d.rectangle([x * S, y * S, (x + tw) * S, (y + 16) * S], fill="#eee", outline="#555")
                    d.text(((x + 5) * S, (y + 2) * S), label, fill="#111", font=fnt(9.5, True))
            elif k == "box":
                _, x, y, w, h, text, fill, bold, rounded, align, size = it
                if rounded:
                    d.rounded_rectangle([x * S, y * S, (x + w) * S, (y + h) * S], 8 * S, fill=fill, outline="#333", width=S)
                else:
                    d.rectangle([x * S, y * S, (x + w) * S, (y + h) * S], fill=fill, outline="#333", width=S)
                f = fnt(size, bold)
                lines = wrap(d, text, f, w - 10)
                y0 = y * S + (h * S - len(lines) * (size + 3) * S) / 2
                for i, ln in enumerate(lines):
                    tx = x * S + 5 * S if align == "left" else x * S + (w * S - d.textlength(ln, font=f)) / 2
                    d.text((tx, y0 + i * (size + 3) * S), ln, fill="#111", font=f)
            elif k == "ellipse":
                _, cx, cy, w, h, text = it
                d.ellipse([(cx - w / 2) * S, (cy - h / 2) * S, (cx + w / 2) * S, (cy + h / 2) * S], fill="#eaf1fb", outline="#333", width=S)
                f = fnt(10)
                lines = wrap(d, text, f, w - 30)
                y0 = cy * S - len(lines) * 13 * S / 2
                for i, ln in enumerate(lines):
                    d.text((cx * S - d.textlength(ln, font=f) / 2, y0 + i * 13 * S), ln, fill="#111", font=f)
            elif k == "actor":
                _, cx, y, name = it
                c = cx * S
                d.ellipse([c - 7 * S, y * S, c + 7 * S, (y + 14) * S], outline="#333", width=S)
                d.line([c, (y + 14) * S, c, (y + 36) * S], fill="#333", width=S)
                d.line([c - 13 * S, (y + 22) * S, c + 13 * S, (y + 22) * S], fill="#333", width=S)
                d.line([c, (y + 36) * S, c - 11 * S, (y + 52) * S], fill="#333", width=S)
                d.line([c, (y + 36) * S, c + 11 * S, (y + 52) * S], fill="#333", width=S)
                f = fnt(9.5, True)
                for i, ln in enumerate(wrap(d, name, f, 90)):
                    d.text((c - d.textlength(ln, font=f) / 2, (y + 55 + i * 12) * S), ln, fill="#111", font=f)
            elif k == "text":
                _, x, y, txt, size, bold, color = it
                d.text((x * S, y * S), txt, fill=color, font=fnt(size, bold))
            elif k == "dot":
                _, cx, cy, r, ring = it
                if ring:
                    d.ellipse([(cx - r) * S, (cy - r) * S, (cx + r) * S, (cy + r) * S], outline="#111", width=S)
                    d.ellipse([(cx - r + 4) * S, (cy - r + 4) * S, (cx + r - 4) * S, (cy + r - 4) * S], fill="#111")
                else:
                    d.ellipse([(cx - r) * S, (cy - r) * S, (cx + r) * S, (cy + r) * S], fill="#111")
            elif k == "class":
                _, x, y, w, name, attrs, ops, st = it
                hh = 24 + (12 if st else 0)
                h1 = max(len(attrs), 1) * 14 + 6
                h2 = max(len(ops), 1) * 14 + 6
                d.rectangle([x * S, y * S, (x + w) * S, (y + hh + h1 + h2) * S], fill="#fffef5", outline="#333", width=S)
                d.rectangle([x * S, y * S, (x + w) * S, (y + hh) * S], fill="#dfe8f3", outline="#333", width=S)
                if st:
                    f2 = fnt(9)
                    d.text((x * S + (w * S - d.textlength(st, font=f2)) / 2, (y + 2) * S), st, fill="#111", font=f2)
                f = fnt(11, True)
                d.text((x * S + (w * S - d.textlength(name, font=f)) / 2, (y + hh - 19) * S), name, fill="#111", font=f)
                d.line([x * S, (y + hh + h1) * S, (x + w) * S, (y + hh + h1) * S], fill="#333", width=S)
                for i, a in enumerate(attrs):
                    d.text(((x + 5) * S, (y + hh + 3 + i * 14) * S), a, fill="#111", font=fnt(9.5))
                for i, o in enumerate(ops):
                    d.text(((x + 5) * S, (y + hh + h1 + 3 + i * 14) * S), o, fill="#111", font=fnt(9.5))
            elif k == "line":
                _, pts, label, dashed, arrow, lpos, lalign = it
                P = [(a * S, b * S) for a, b in pts]
                if dashed:
                    for (x1, y1), (x2, y2) in zip(P, P[1:]):
                        n = max(((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5, 1)
                        t = 0
                        while t < n:
                            e = min(t + 6 * S, n)
                            d.line([(x1 + (x2 - x1) * t / n, y1 + (y2 - y1) * t / n), (x1 + (x2 - x1) * e / n, y1 + (y2 - y1) * e / n)],
                                   fill="#333", width=S)
                            t += 11 * S
                else:
                    d.line(P, fill="#333", width=S)
                if arrow != "none":
                    (x1, y1), (x2, y2) = P[-2], P[-1]
                    n = max(((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5, 1)
                    ux, uy = (x2 - x1) / n, (y2 - y1) / n
                    a = 9 * S
                    p1 = (x2 - ux * a - uy * a / 2.4, y2 - uy * a + ux * a / 2.4)
                    p2 = (x2 - ux * a + uy * a / 2.4, y2 - uy * a - ux * a / 2.4)
                    if arrow == "filled":
                        d.polygon([(x2, y2), p1, p2], fill="#333")
                    else:
                        d.line([p1, (x2, y2), p2], fill="#333", width=S)
                if label:
                    f = fnt(9.5)
                    lx, ly = lpos if lpos else ((pts[0][0] + pts[-1][0]) / 2, (pts[0][1] + pts[-1][1]) / 2 - 12)
                    for j, part in enumerate(label.split(chr(10))):
                        tw = d.textlength(part, font=f)
                        x = lx * S - tw / 2 if lalign == "center" else lx * S
                        d.text((x, (ly + j * 12) * S), part, fill="#a02020", font=f)
        img = img.resize((int(self.w * 1.5), int(self.h * 1.5)), Image.LANCZOS)
        img.save(path)

    @staticmethod
    def _rect(d, x, y, w, h, color, dashed):
        if not dashed:
            d.rectangle([x * S, y * S, (x + w) * S, (y + h) * S], outline=color, width=S)
            return
        for (x1, y1, x2, y2) in [(x, y, x + w, y), (x + w, y, x + w, y + h), (x + w, y + h, x, y + h), (x, y + h, x, y)]:
            n = max(((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5, 1)
            t = 0
            while t < n:
                e = min(t + 6, n)
                d.line([((x1 + (x2 - x1) * t / n) * S, (y1 + (y2 - y1) * t / n) * S),
                        ((x1 + (x2 - x1) * e / n) * S, (y1 + (y2 - y1) * e / n) * S)], fill=color, width=S)
                t += 11

    # ---------- drawio ----------
    def cells(self, base):
        out, n = [], [base]

        def nid():
            n[0] += 1
            return f"u{n[0]}"

        out.append(f'<mxCell id="{nid()}" value="{escape(self.title)}" style="text;html=1;fontStyle=1;fontSize=13;" vertex="1" '
                   f'parent="1"><mxGeometry x="10" y="2" width="800" height="22" as="geometry"/></mxCell>')
        for it in self.items:
            k = it[0]
            if k == "frame":
                _, x, y, w, h, label, dashed = it
                out.append(f'<mxCell id="{nid()}" value="{escape(label or "")}" style="rounded=0;html=1;fillColor=none;strokeColor=#555555;'
                           f'verticalAlign=top;align=left;spacingLeft=6;fontStyle=1;fontSize=10;{"dashed=1;" if dashed else ""}" vertex="1" '
                           f'parent="1"><mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry"/></mxCell>')
            elif k == "box":
                _, x, y, w, h, text, fill, bold, rounded, align, size = it
                out.append(f'<mxCell id="{nid()}" value="{escape(text)}" style="{"rounded=1;" if rounded else "rounded=0;"}html=1;whiteSpace=wrap;'
                           f'fillColor={fill};strokeColor=#333333;fontSize={int(size)};{"fontStyle=1;" if bold else ""}align={align};" vertex="1" '
                           f'parent="1"><mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry"/></mxCell>')
            elif k == "ellipse":
                _, cx, cy, w, h, text = it
                out.append(f'<mxCell id="{nid()}" value="{escape(text)}" style="ellipse;html=1;whiteSpace=wrap;fillColor=#eaf1fb;strokeColor=#333333;'
                           f'fontSize=10;" vertex="1" parent="1"><mxGeometry x="{cx - w / 2}" y="{cy - h / 2}" width="{w}" height="{h}" as="geometry"/></mxCell>')
            elif k == "actor":
                _, cx, y, name = it
                out.append(f'<mxCell id="{nid()}" value="{escape(name)}" style="shape=umlActor;verticalLabelPosition=bottom;verticalAlign=top;html=1;'
                           f'fontSize=10;fontStyle=1;" vertex="1" parent="1"><mxGeometry x="{cx - 14}" y="{y}" width="28" height="52" as="geometry"/></mxCell>')
            elif k == "text":
                _, x, y, txt, size, bold, color = it
                out.append(f'<mxCell id="{nid()}" value="{escape(txt)}" style="text;html=1;fontSize={int(size)};fontColor={color};'
                           f'{"fontStyle=1;" if bold else ""}" vertex="1" parent="1"><mxGeometry x="{x}" y="{y}" width="{max(len(txt) * size * 0.6, 20)}" '
                           f'height="{size + 6}" as="geometry"/></mxCell>')
            elif k == "dot":
                _, cx, cy, r, ring = it
                style = "ellipse;html=1;fillColor=#111111;strokeColor=#111111;" if not ring else "ellipse;html=1;shape=endState;fillColor=#111111;strokeColor=#111111;"
                out.append(f'<mxCell id="{nid()}" value="" style="{style}" vertex="1" parent="1"><mxGeometry x="{cx - r}" y="{cy - r}" '
                           f'width="{2 * r}" height="{2 * r}" as="geometry"/></mxCell>')
            elif k == "class":
                _, x, y, w, name, attrs, ops, st = it
                title = (f"«{st}»<br>" if st else "") + f"<b>{escape(name)}</b>"
                hh = 24 + (12 if st else 0)
                h1 = max(len(attrs), 1) * 14 + 6
                h2 = max(len(ops), 1) * 14 + 6
                cid = nid()
                out.append(f'<mxCell id="{cid}" value="{escape(title)}" style="swimlane;fontStyle=1;childLayout=stackLayout;horizontal=1;'
                           f'startSize={hh};horizontalStack=0;resizeParent=1;fillColor=#dfe8f3;html=1;fontSize=11;" vertex="1" parent="1">'
                           f'<mxGeometry x="{x}" y="{y}" width="{w}" height="{hh + h1 + h2}" as="geometry"/></mxCell>')
                out.append(f'<mxCell id="{nid()}" value="{escape("<br>".join(attrs) or " ")}" style="text;html=1;align=left;verticalAlign=top;'
                           f'fontSize=10;spacingLeft=4;strokeColor=#333333;fillColor=#fffef5;" vertex="1" parent="{cid}"><mxGeometry y="{hh}" '
                           f'width="{w}" height="{h1}" as="geometry"/></mxCell>')
                out.append(f'<mxCell id="{nid()}" value="{escape("<br>".join(ops) or " ")}" style="text;html=1;align=left;verticalAlign=top;'
                           f'fontSize=10;spacingLeft=4;strokeColor=#333333;fillColor=#fffef5;" vertex="1" parent="{cid}"><mxGeometry y="{hh + h1}" '
                           f'width="{w}" height="{h2}" as="geometry"/></mxCell>')
            elif k == "line":
                _, pts, label, dashed, arrow, lpos, lalign = it
                mid = "".join(f'<mxPoint x="{a}" y="{b}"/>' for a, b in pts[1:-1])
                end = {"none": "none", "open": "open", "filled": "block"}[arrow]
                out.append(f'<mxCell id="{nid()}" value="{escape(label or "")}" style="edgeStyle=none;html=1;endArrow={end};endFill={1 if arrow == "filled" else 0};'
                           f'{"dashed=1;" if dashed else ""}strokeColor=#333333;fontSize=10;fontColor=#a02020;" edge="1" parent="1">'
                           f'<mxGeometry relative="1" as="geometry"><mxPoint x="{pts[0][0]}" y="{pts[0][1]}" as="sourcePoint"/>'
                           f'<mxPoint x="{pts[-1][0]}" y="{pts[-1][1]}" as="targetPoint"/><Array as="points">{mid}</Array></mxGeometry></mxCell>')
        return out


# ------------------------------------------------------------------ Use Case
def use_case():
    sc = Scene("uml_use_case", "Диаграмма вариантов использования: система управления запасами авиатехнической базы", 1060, 700)
    sc.frame(210, 34, 640, 650, "Система управления запасами")
    L, R = 70, 990
    for n, y in (("Планировщик", 90), ("Техник", 250), ("Руководитель / инспектор качества", 420)):
        sc.actor(L, y, n)
    for n, y in (("Реестр сертификатов", 56), ("Кладовщик", 250), ("Специалист по запчастям", 510), ("Поставщик", 600)):
        sc.actor(R, y, n)
    uc = {
        "04": (320, 100, "UC-04 Зарезервировать деталь под заказ-наряд"), "05": (320, 190, "UC-05 Снять резерв"),
        "07": (320, 280, "UC-07 Посмотреть остаток и историю движений"),
        "11": (320, 370, "UC-11 Снять карантин с партии"),
        "03": (730, 80, "UC-03 Проверить сертификат и S/N"), "02": (730, 170, "UC-02 Принять товар"),
        "01": (730, 260, "UC-01 Зарегистрировать номенклатуру"), "06": (730, 350, "UC-06 Выдать деталь по резерву"),
        "10": (730, 440, "UC-10 Провести инвентаризацию"), "08": (730, 530, "UC-08 Сформировать предложение о пополнении"),
        "09": (730, 620, "UC-09 Утвердить и отправить заказ"),
    }
    for cx, cy, t in uc.values():
        sc.ellipse(cx, cy, 190, 56, t)

    def side(k, s):
        cx, cy, _ = uc[k]
        return (cx + (-95 if s == "l" else 95), cy)

    def link(a, k, s):
        sc.line([a, side(k, s)], arrow="none")

    for k in ("04", "05", "07"):
        link((L + 14, 116), k, "l")
    link((L + 14, 276), "07", "l")
    for k in ("04", "05", "11", "10"):
        link((L + 14, 446), k, "l")
    for k in ("02", "01", "06", "10"):
        link((R - 14, 276), k, "r")
    link((R - 14, 82), "03", "r")
    for k in ("08", "09"):
        link((R - 14, 536), k, "r")
    link((R - 14, 626), "09", "r")
    sc.line([(730, 142), (730, 108)], "«include»", True, "open", (736, 118), "left")
    sc.line([(730, 592), (730, 558)], "«include»", True, "open", (736, 568), "left")
    return sc


# ------------------------------------------------------------------ Class
def class_diagram():
    sc = Scene("uml_class", "Диаграмма классов: основные программные классы и обязанности", 1180, 740)
    sc.classbox(20, 40, 210, "Item (номенклатура, P/N)", ["pn: str {уникален}", "name: str", "baseUom: str", "isSerial: bool"],
                ["unitFactor(uom): int"])
    sc.classbox(290, 40, 220, "Batch (партия)", ["batchNo: str", "expiryDate: date?", "certNo: str?", "status: ok | quarantine"],
                ["isUsable(today): bool"])
    sc.classbox(570, 40, 230, "StockBalance (остаток)", ["onHand: int ≥ 0", "reserved: int ≥ 0", "{reserved ≤ onHand}"],
                ["available(): int"])
    sc.classbox(860, 40, 290, "StockMovement (движение)", ["kind: RECEIPT | RESERVE | UNRESERVE | ISSUE | REVERSAL",
                                                           "qtyDelta, reservedDelta: int", "docRef: str, ts: datetime", "reversesId: int?"],
                ["{только добавление}"])
    sc.classbox(20, 250, 210, "Receipt (приходный документ)", ["docNo: str {уникален}", "status: posted | reversed", "createdBy: User"],
                ["reverse()"])
    sc.classbox(290, 250, 220, "Reservation (резерв)", ["requestId: str {уникален}", "qty: int > 0", "workOrder: WO-NNNN",
                                                      "status: active | released | issued"],
                ["release()", "markIssued()"])
    sc.classbox(570, 250, 230, "ReservationLine", ["batch: Batch", "location: Location", "qty: int > 0"], [])
    sc.classbox(860, 250, 290, "User (пользователь)", ["name: str", "role: admin | storekeeper | planner | technician | manager", "blocked: bool"],
                ["can(action): bool"])
    sc.classbox(20, 470, 330, "StockService (сервис учёта)", [],
                ["registerItem(user, pn, name, uom, packs)", "receive(user, docNo, lines): Receipt", "reverseReceipt(user, docNo)",
                 "reserve(user, requestId, pn, qty, workOrder): Reservation", "release(user, reservationId)", "issue(user, reservationId)",
                 "quarantineBatch(user, pn, batch)", "certifyBatch(user, pn, batch, certNo)", "availability(user, pn)", "history(user, pn)", "checkConsistency()"], "service")
    sc.classbox(430, 470, 330, "ReplenishmentPlanner (планировщик)", [],
                ["classifyAbcXyz(items)", "eoq(D, S, H): float", "reorderPoint(d, L, σ, z): int", "proposeOrder(item): Order?"], "service")
    sc.classbox(840, 470, 310, "Database (SQLite)", ["CHECK onHand ≥ 0, reserved ≤ onHand", "UNIQUE requestId, docNo, (pn, S/N), pn"],
                ["transaction(): BEGIN IMMEDIATE"], "storage")
    red = "#a02020"

    def card(x, y, t):
        sc.text(x, y, t, 9, False, red)

    sc.line([(230, 100), (290, 100)], arrow="none"); card(234, 84, "1"); card(264, 84, "0..*")
    sc.line([(510, 100), (570, 100)], arrow="none"); card(514, 84, "1"); card(544, 84, "0..*")
    sc.line([(800, 100), (860, 100)], arrow="none"); card(804, 84, "1"); card(834, 84, "0..*")
    sc.line([(230, 125), (260, 125), (260, 300), (290, 300)], arrow="none"); card(234, 109, "1"); card(264, 284, "0..*")
    sc.line([(510, 330), (570, 330)], arrow="none"); card(514, 314, "1"); card(542, 314, "1..*")
    sc.line([(400, 132), (400, 200), (620, 200), (620, 250)], arrow="none"); card(404, 136, "1"); card(626, 232, "0..*")
    sc.line([(1000, 146), (1000, 250)], arrow="none"); card(1006, 150, "1"); card(1006, 232, "0..*")
    sc.line([(185, 470), (185, 342)], dashed=True, arrow="open", label="создаёт", lpos=(192, 410), lalign="left")
    sc.line([(350, 520), (400, 520), (400, 370)], dashed=True, arrow="open", label="создаёт", lpos=(406, 440), lalign="left")
    sc.line([(430, 540), (350, 540)], dashed=True, arrow="open", label="ROP, Q", lpos=(370, 524))
    sc.line([(350, 650), (1000, 650), (1000, 560)], dashed=True, arrow="open", label="транзакции и ограничения", lpos=(600, 634))
    return sc


# ------------------------------------------------------------------ Sequence
def sequence(name, title, parts, msgs, frames, h):
    """parts: [(имя, x)], msgs: [(from_idx, to_idx, text, kind)], frames: [(label, row_from, row_to, else_row|None)]."""
    sc = Scene(name, title, 1100, h)
    top, step = 40, 40
    for nm, x in parts:
        sc.box(x - 80, top, 160, 34, nm, "#dfe8f3", True, True, "center", 10.5)
        sc.line([(x, top + 34), (x, h - 20)], dashed=True, arrow="none")
    y0 = top + 34 + 30
    for label, a, b, el in frames:
        fy, fh = y0 + a * step - 22, (b - a + 1) * step
        sc.frame(60, fy, 980, fh, f"opt  [{label}]", False)
        if el is not None:
            ey = y0 + el * step - 22
            sc.line([(60, ey), (1040, ey)], dashed=True, arrow="none")
            sc.text(66, ey + 2, "[иначе]", 9.5, True)
    for i, (a, b, text, kind) in enumerate(msgs):
        y = y0 + i * step
        xa, xb = parts[a][1], parts[b][1]
        if a == b:
            sc.line([(xa, y - 8), (xa + 50, y - 8), (xa + 50, y + 8), (xa, y + 8)], arrow="filled")
            sc.text(xa + 56, y - 8, text, 9.5)
        else:
            lx = min(xa, xb) + 8
            sc.line([(xa, y), (xb, y)], dashed=(kind == "ret"), arrow="open" if kind == "ret" else "filled")
            sc.text(lx if xb > xa else lx, y - 15, text, 9.5, False, "#111")
    return sc


def seq_reserve():
    parts = [("Планировщик", 150), ("StockService", 520), ("База данных", 900)]
    msgs = [
        (0, 1, "reserve(requestId, pn, qty, workOrder)", "call"),
        (1, 2, "BEGIN IMMEDIATE; роль «planner / manager»; формат WO-NNNN", "call"),
        (1, 2, "найти резерв по requestId", "call"),
        (2, 1, "резерв найден", "ret"),
        (1, 0, "тот же резерв (duplicate = true), новых записей нет", "ret"),
        (1, 2, "выбрать годные партии по FEFO: доступно = остаток − резерв", "call"),
        (2, 1, "доступно N", "ret"),
        (1, 2, "ROLLBACK", "call"),
        (1, 0, "отказ INSUFFICIENT_STOCK: «запрошено qty, доступно N»", "ret"),
        (1, 2, "UPDATE резерв += q WHERE остаток − резерв ≥ q (по каждой партии)", "call"),
        (1, 2, "INSERT резерв, строки резерва, движения RESERVE", "call"),
        (1, 2, "COMMIT", "call"),
        (1, 0, "резерв создан (active)", "ret"),
    ]
    frames = [("запрос с этим requestId уже обработан", 2, 4, None),
              ("доступно меньше запрошенного", 6, 8, None)]
    return sequence("uml_seq_reserve", "Sequence: резервирование товара", parts, msgs, frames, 40 + 34 + 30 + 13 * 40 + 20)


def seq_receive():
    parts = [("Кладовщик", 150), ("StockService", 520), ("База данных", 900)]
    msgs = [
        (0, 1, "receive(docNo, строки прихода)", "call"),
        (1, 2, "BEGIN IMMEDIATE; проверить роль «storekeeper»; найти документ по docNo", "call"),
        (2, 1, "документ найден", "ret"),
        (1, 0, "duplicate = true, остаток не изменён", "ret"),
        (1, 2, "INSERT приходный документ", "call"),
        (1, 1, "перевести в базовую единицу: qty × factor; проверить срок годности и S/N", "call"),
        (1, 2, "найти или создать партию (без certNo – карантин); INSERT строка прихода", "call"),
        (1, 2, "UPSERT остаток += qty; INSERT движение RECEIPT", "call"),
        (1, 2, "ROLLBACK (строка неверна: единица, срок, S/N)", "call"),
        (1, 0, "ошибка VALIDATION, документ не сохранён", "ret"),
        (1, 2, "COMMIT", "call"),
        (1, 0, "приход проведён, остаток доступен", "ret"),
    ]
    frames = [("документ с этим номером уже проведён", 2, 3, None),
              ("строка документа неверна", 8, 9, None)]
    return sequence("uml_seq_receive", "Sequence: приёмка товара", parts, msgs, frames, 40 + 34 + 30 + 12 * 40 + 20)


# ------------------------------------------------------------------ State
def state_machine():
    sc = Scene("uml_state", "Диаграмма состояний резерва", 900, 360)
    sc.dot(50, 150, 9)
    sc.box(160, 110, 170, 80, "Активен (active)\nentry: резерв записан, доступное уменьшено", "#fffbe6", True)
    sc.box(560, 30, 170, 70, "Снят (released)\nentry: доступное возвращено", "#fffbe6", True)
    sc.box(560, 200, 170, 70, "Выдан (issued)\nentry: остаток и резерв уменьшены", "#fffbe6", True)
    sc.dot(830, 65, 11, True)
    sc.dot(830, 235, 11, True)
    sc.line([(59, 150), (160, 150)], "reserve(requestId, qty, WO-NNNN)\n[доступно ≥ qty]", False, "filled", (60, 112), "left")
    sc.line([(330, 130), (450, 130), (450, 65), (560, 65)], "release() [владелец или руководитель]", False, "filled", (330, 40), "left")
    sc.line([(330, 170), (450, 170), (450, 235), (560, 235)], "issue() [партия годна: не в карантине, не просрочена]", False, "filled", (330, 262), "left")
    sc.line([(730, 65), (819, 65)], "", False, "filled")
    sc.line([(730, 235), (819, 235)], "", False, "filled")
    sc.line([(200, 110), (200, 80), (290, 80), (290, 110)], "issue() [партия в карантине или просрочена]: отказ, остаётся Активен", False, "filled", (60, 60), "left")
    sc.text(60, 310, "Повторные release() и issue() для снятого или выданного резерва отклоняются (INVALID_STATE).", 10)
    return sc


def uml_pages():
    pages = []
    for i, sc in enumerate([use_case(), class_diagram(), seq_reserve(), seq_receive(), state_machine()]):
        sc.png(__import__("pathlib").Path(__file__).resolve().parent.parent / f"assets/{sc.name}.png")
        pages.append((sc.title, sc.w, sc.h, sc.cells(20000 + i * 1000)))
    return pages
