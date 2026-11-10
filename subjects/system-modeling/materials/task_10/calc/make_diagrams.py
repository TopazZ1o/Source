"""Генератор диаграмм СРМ №10: BPMN AS-IS / TO-BE (4 страницы) и ER-модель.

НАЗНАЧЕНИЕ
    Из одного описания (координаты и связи) строит
      - inventory_model.drawio  (diagrams.net, по странице на диаграмму);
      - assets/<имя>.png        (Pillow, те же координаты; может чуть отличаться от экспорта diagrams.net).
ЗАПУСК (из папки task_10)
    python calc/make_diagrams.py
ОГРАНИЧЕНИЯ
    Линии связей ломаные, трассируются по простым правилам (h, vh, hv, явные точки).
"""
import sys
from pathlib import Path
from xml.sax.saxutils import escape

from PIL import Image, ImageDraw, ImageFont

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent))
ROOT = Path(__file__).resolve().parent.parent
FONT = "C:/Windows/Fonts/arial.ttf"
FONT_B = "C:/Windows/Fonts/arialbd.ttf"
CW, LANE_H, X0, LANE_LABEL = 128, 128, 44, 34
TASK_W, TASK_H, EV, GW = 112, 60, 34, 48
SCALE = 2


def font(size, bold=False):
    return ImageFont.truetype(FONT_B if bold else FONT, size)


def wrap(draw, text, fnt, width):
    lines = []
    for para in text.split("\n"):
        cur = ""
        for word in para.split():
            test = (cur + " " + word).strip()
            if draw.textlength(test, font=fnt) <= width or not cur:
                cur = test
            else:
                lines.append(cur)
                cur = word
        lines.append(cur)
    return lines


class Diagram:
    def __init__(self, name, title, lanes, cols, top=30):
        self.name, self.title, self.lanes, self.cols, self.top = name, title, lanes, cols, top
        self.shapes, self.edges = {}, []
        self.width = X0 + LANE_LABEL + cols * CW + 30
        self.height = top + len(lanes) * LANE_H + 20

    def pos(self, col, lane):
        return X0 + LANE_LABEL + col * CW + CW / 2, self.top + lane * LANE_H + LANE_H / 2

    def add(self, sid, kind, col, lane, text):
        cx, cy = self.pos(col, lane)
        w, h = {"task": (TASK_W, TASK_H), "start": (EV, EV), "end": (EV, EV), "gw": (GW, GW)}[kind]
        self.shapes[sid] = dict(kind=kind, cx=cx, cy=cy, w=w, h=h, text=text)

    def link(self, a, b, label=None, route="h", via=None):
        self.edges.append(dict(a=a, b=b, label=label, route=route, via=via))

    def points(self, e):
        a, b = self.shapes[e["a"]], self.shapes[e["b"]]
        if e["via"]:
            pts = [(a["cx"] + a["w"] / 2, a["cy"])] if e["route"] == "r" else [(a["cx"], a["cy"] + a["h"] / 2 * (1 if e["via"][0][1] > a["cy"] else -1))]
            return pts + list(e["via"]) + [(b["cx"] - b["w"] / 2, b["cy"])]
        r = e["route"]
        if abs(a["cy"] - b["cy"]) < 1 and r == "h":
            return [(a["cx"] + a["w"] / 2, a["cy"]), (b["cx"] - b["w"] / 2, b["cy"])]
        if r == "h":
            sx, ex = a["cx"] + a["w"] / 2, b["cx"] - b["w"] / 2
            mx = (sx + ex) / 2
            return [(sx, a["cy"]), (mx, a["cy"]), (mx, b["cy"]), (ex, b["cy"])]
        if r == "vh":
            sy = a["cy"] + a["h"] / 2 * (1 if b["cy"] > a["cy"] else -1)
            return [(a["cx"], sy), (a["cx"], b["cy"]), (b["cx"] - b["w"] / 2, b["cy"])]
        if r == "hv":
            ey = b["cy"] - b["h"] / 2 * (1 if b["cy"] > a["cy"] else -1)
            return [(a["cx"] + a["w"] / 2, a["cy"]), (b["cx"], a["cy"]), (b["cx"], ey)]
        raise ValueError(r)

    def label_below(self, sid):
        sh = self.shapes[sid]
        return any(e["a"] == sid and e["route"] == "vh" and self.shapes[e["b"]]["cy"] < sh["cy"] for e in self.edges)

    # ---------- PNG ----------
    def png(self, path):
        W, H = int(self.width * SCALE), int(self.height * SCALE)
        img = Image.new("RGB", (W, H), "white")
        d = ImageDraw.Draw(img)
        s = SCALE
        f, fb, fs = font(11 * s), font(12 * s, True), font(10 * s)
        d.text((X0 * s, 6 * s), self.title, fill="#222", font=fb)
        for i, name in enumerate(self.lanes):
            y = self.top + i * LANE_H
            d.rectangle([X0 * s, y * s, (self.width - 20) * s, (y + LANE_H) * s], outline="#555", width=s)
            d.rectangle([X0 * s, y * s, (X0 + LANE_LABEL) * s, (y + LANE_H) * s], fill="#dfe8f3", outline="#555", width=s)
            lab = Image.new("RGBA", (LANE_H * s, LANE_LABEL * s), (0, 0, 0, 0))
            ld = ImageDraw.Draw(lab)
            lines = wrap(ld, name, fs, LANE_H * s - 10 * s)
            th = len(lines) * 12 * s
            for k, ln in enumerate(lines):
                tw = ld.textlength(ln, font=fs)
                ld.text(((LANE_H * s - tw) / 2, (LANE_LABEL * s - th) / 2 + k * 12 * s), ln, fill="#111", font=fs)
            lab = lab.rotate(90, expand=True)
            img.paste(lab, (X0 * s, y * s), lab)
        for e in self.edges:
            pts = [(x * s, y * s) for x, y in self.points(e)]
            d.line(pts, fill="#333", width=int(1.4 * s))
            (x1, y1), (x2, y2) = pts[-2], pts[-1]
            dx, dy = (x2 - x1), (y2 - y1)
            n = max((dx * dx + dy * dy) ** 0.5, 1)
            ux, uy = dx / n, dy / n
            ah = 8 * s
            d.polygon([(x2, y2), (x2 - ux * ah - uy * ah / 2.2, y2 - uy * ah + ux * ah / 2.2),
                       (x2 - ux * ah + uy * ah / 2.2, y2 - uy * ah - ux * ah / 2.2)], fill="#333")
            if e["label"]:
                px, py = pts[0] if len(pts) < 3 else pts[0]
                lx, ly = (pts[0][0] + pts[1][0]) / 2, (pts[0][1] + pts[1][1]) / 2
                if pts[0][0] == pts[1][0]:
                    d.text((lx + 4 * s, ly - 6 * s), e["label"], fill="#a02020", font=fs)
                else:
                    d.text((lx - 8 * s, ly - 14 * s), e["label"], fill="#a02020", font=fs)
        for sid, sh in self.shapes.items():
            cx, cy, w, h = sh["cx"] * s, sh["cy"] * s, sh["w"] * s, sh["h"] * s
            k = sh["kind"]
            if k == "task":
                d.rounded_rectangle([cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2], 6 * s, fill="#fffbe6",
                                    outline="#333", width=s)
                lines = wrap(d, sh["text"], f, w - 8 * s)
                y0 = cy - len(lines) * 13 * s / 2
                for i, ln in enumerate(lines):
                    d.text((cx - d.textlength(ln, font=f) / 2, y0 + i * 13 * s), ln, fill="#111", font=f)
            elif k in ("start", "end"):
                d.ellipse([cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2], fill="#e6f4e6" if k == "start" else "#f9e3e3",
                          outline="#333", width=s if k == "start" else 3 * s)
                lines = wrap(d, sh["text"], fs, 118 * s)
                for i, ln in enumerate(lines):
                    d.text((cx - d.textlength(ln, font=fs) / 2, cy + h / 2 + 3 * s + i * 11 * s), ln, fill="#111", font=fs)
            else:
                d.polygon([(cx, cy - h / 2), (cx + w / 2, cy), (cx, cy + h / 2), (cx - w / 2, cy)], fill="#eaf1fb",
                          outline="#333")
                d.line([(cx - 6 * s, cy - 6 * s), (cx + 6 * s, cy + 6 * s)], fill="#333", width=2 * s)
                d.line([(cx - 6 * s, cy + 6 * s), (cx + 6 * s, cy - 6 * s)], fill="#333", width=2 * s)
                lines = wrap(d, sh["text"], fs, 120 * s)
                for i, ln in enumerate(lines):
                    ty = (cy + h / 2 + 2 * s + i * 11 * s) if self.label_below(sid) else (cy - h / 2 - (len(lines) - i) * 11 * s - 2 * s)
                    d.text((cx - d.textlength(ln, font=fs) / 2, ty), ln, fill="#111", font=fs)
        img = img.resize((int(W / SCALE * 1.5), int(H / SCALE * 1.5)), Image.LANCZOS)
        img.save(path)

    # ---------- drawio ----------
    def drawio_cells(self, start_id):
        cells, n = [], [start_id]

        def nid():
            n[0] += 1
            return f"c{n[0]}"

        ids = {}
        for i, name in enumerate(self.lanes):
            y = self.top + i * LANE_H
            cells.append(f'<mxCell id="{nid()}" value="{escape(name)}" style="swimlane;horizontal=0;startSize={LANE_LABEL};'
                         f'fillColor=#dfe8f3;fontSize=11;html=1;whiteSpace=wrap;" vertex="1" parent="1"><mxGeometry x="{X0}" '
                         f'y="{y}" width="{self.width - 20 - X0}" height="{LANE_H}" as="geometry"/></mxCell>')
        cells.append(f'<mxCell id="{nid()}" value="{escape(self.title)}" style="text;html=1;fontStyle=1;fontSize=13;" vertex="1" '
                     f'parent="1"><mxGeometry x="{X0}" y="4" width="700" height="22" as="geometry"/></mxCell>')
        for sid, sh in self.shapes.items():
            cid = nid()
            ids[sid] = cid
            x, y = sh["cx"] - sh["w"] / 2, sh["cy"] - sh["h"] / 2
            k = sh["kind"]
            if k == "task":
                style = "rounded=1;whiteSpace=wrap;html=1;fillColor=#fffbe6;strokeColor=#333333;fontSize=11;"
                val = escape(sh["text"])
            elif k in ("start", "end"):
                style = (f"ellipse;html=1;fillColor={'#e6f4e6' if k == 'start' else '#f9e3e3'};strokeColor=#333333;"
                         f"strokeWidth={1 if k == 'start' else 3};verticalLabelPosition=bottom;verticalAlign=top;"
                         "labelWidth=118;whiteSpace=wrap;fontSize=10;")
                val = escape(sh["text"])
            else:
                pos = "verticalLabelPosition=bottom;verticalAlign=top;" if self.label_below(sid) else "verticalLabelPosition=top;verticalAlign=bottom;"
                style = "rhombus;html=1;fillColor=#eaf1fb;strokeColor=#333333;" + pos + "labelWidth=120;whiteSpace=wrap;fontSize=10;"
                val = escape(sh["text"])
            cells.append(f'<mxCell id="{cid}" value="{val}" style="{style}" vertex="1" parent="1"><mxGeometry x="{x}" '
                         f'y="{y}" width="{sh["w"]}" height="{sh["h"]}" as="geometry"/></mxCell>')
        for e in self.edges:
            pts = self.points(e)
            mid = "".join(f'<mxPoint x="{x}" y="{y}"/>' for x, y in pts[1:-1])
            style = "edgeStyle=none;html=1;endArrow=block;endFill=1;strokeColor=#333333;fontSize=10;fontColor=#a02020;"
            cells.append(f'<mxCell id="{nid()}" value="{escape(e["label"] or "")}" style="{style}" edge="1" parent="1" '
                         f'source="{ids[e["a"]]}" target="{ids[e["b"]]}"><mxGeometry relative="1" as="geometry">'
                         f'<Array as="points">{mid}</Array></mxGeometry></mxCell>')
        return cells


# ---------------------------------------------------------------- BPMN
def as_is_1():
    d = Diagram("as_is_1", "AS-IS (1/2): определение потребности, заказ поставщику, приёмка",
                ["Кладовщик", "Специалист по запчастям", "Поставщик"], 11)
    d.add("s", "start", 0, 0, "Ежемесячный обход склада")
    d.add("t1", "task", 1, 0, "Сверить остаток на стеллаже и в журнале «на глаз»")
    d.add("g1", "gw", 2, 0, "Мало по ощущению?")
    d.add("e1", "end", 3, 0, "Заказ не нужен")
    d.add("t2", "task", 3, 1, "Получить сообщение в чате, составить заказ в Excel")
    d.add("t3", "task", 4, 1, "Отправить заказ поставщику по e-mail")
    d.add("t4", "task", 5, 2, "Подтвердить заказ и срок по телефону")
    d.add("t5", "task", 6, 2, "Отгрузить деталь с накладной и сертификатом")
    d.add("t6", "task", 7, 0, "Принять по накладной, сверить сертификат на бумаге")
    d.add("g2", "gw", 8, 0, "Количество, срок и сертификат в порядке?")
    d.add("t7", "task", 8, 1, "Составить акт, позвонить поставщику")
    d.add("e2", "end", 9, 1, "Вопрос решён вне системы")
    d.add("t8", "task", 9, 0, "Внести приход в журнал на следующий день")
    d.add("e3", "end", 10, 0, "Деталь на стеллаже, остаток с задержкой")
    d.link("s", "t1"); d.link("t1", "g1")
    d.link("g1", "e1", "нет"); d.link("g1", "t2", "да", "vh")
    d.link("t2", "t3"); d.link("t3", "t4"); d.link("t4", "t5"); d.link("t5", "t6")
    d.link("t6", "g2"); d.link("g2", "t8", "да"); d.link("g2", "t7", "нет", "vh")
    d.link("t7", "e2"); d.link("t8", "e3")
    return d


def as_is_2():
    d = Diagram("as_is_2", "AS-IS (2/2): резервирование и отпуск, инвентаризация",
                ["Техник", "Инженер-планировщик", "Кладовщик", "Комиссия по инвентаризации"], 10)
    d.add("s", "start", 0, 0, "Нужна деталь для заказ-наряда")
    d.add("t1", "task", 1, 1, "Принять запрос техника, уточнить наличие")
    d.add("t2", "task", 2, 2, "Посмотреть журнал и стеллаж, ответить по телефону")
    d.add("g1", "gw", 3, 1, "Деталь есть?")
    d.add("e1", "end", 4, 0, "Ждать поставку, ВС в простое")
    d.add("t3", "task", 4, 1, "Договориться об откладывании устно")
    d.add("t4", "task", 5, 2, "Отложить деталь, записать в блокнот")
    d.add("g2", "gw", 6, 2, "Техник пришёл за деталью в срок?")
    d.add("t5", "task", 7, 2, "Выдать по требованию-накладной")
    d.add("t6", "task", 8, 2, "Списать в журнале в конце смены")
    d.add("e2", "end", 9, 2, "Выдача оформлена")
    d.add("t7", "task", 7, 1, "Снять откладывание устно, запись остаётся")
    d.add("e3", "end", 8, 1, "Деталь «висит» отложенной")
    d.add("s2", "start", 0, 3, "Раз в квартал")
    d.add("i1", "task", 1, 3, "Остановить выдачу, пересчитать вручную")
    d.add("i2", "task", 2, 3, "Сверить с журналом")
    d.add("g3", "gw", 3, 3, "Есть расхождения?")
    d.add("i3", "task", 4, 3, "Исправить журнал без акта и причины")
    d.add("e4", "end", 5, 3, "Остаток исправлен")
    d.link("s", "t1", route="hv"); d.link("t1", "t2"); d.link("t2", "g1", route="h")
    d.link("g1", "e1", "нет", "vh"); d.link("g1", "t3", "да"); d.link("t3", "t4"); d.link("t4", "g2")
    d.link("g2", "t5", "да"); d.link("g2", "t7", "нет", "vh"); d.link("t5", "t6"); d.link("t6", "e2")
    d.link("t7", "e3")
    d.link("s2", "i1"); d.link("i1", "i2"); d.link("i2", "g3"); d.link("g3", "i3", "да")
    d.link("i3", "e4")
    return d


def to_be_1():
    d = Diagram("to_be_1", "TO-BE (1/2): потребность, заказ поставщику, приёмка",
                ["Информационная система", "Специалист по запчастям", "Поставщик", "Кладовщик"], 11)
    d.add("s", "start", 0, 0, "Остаток ≤ точки заказа (ежедневная проверка)")
    d.add("t1", "task", 1, 0, "Рассчитать позицию запаса, предложить заказ Q = EOQ")
    d.add("t2", "task", 2, 1, "Проверить и утвердить заказ")
    d.add("g1", "gw", 3, 1, "Утверждён?")
    d.add("e1", "end", 4, 1, "Отклонён, причина в журнале")
    d.add("t3", "task", 4, 0, "Сформировать и отправить заказ, ждать подтверждения")
    d.add("t4", "task", 5, 2, "Подтвердить срок и количество")
    d.add("t5", "task", 6, 3, "Принять деталь, отсканировать партию, сертификат и S/N")
    d.add("g2", "gw", 7, 0, "Расхождение, нет сертификата или срок нарушен?")
    d.add("t6", "task", 8, 1, "Принять по факту, в карантин или вернуть")
    d.add("t7", "task", 9, 0, "Провести приход: остаток и движение в одной транзакции")
    d.add("e2", "end", 10, 0, "Остаток виден сразу")
    d.link("s", "t1"); d.link("t1", "t2"); d.link("t2", "g1")
    d.link("g1", "e1", "нет"); d.link("g1", "t3", "да", "vh")
    d.link("t3", "t4"); d.link("t4", "t5"); d.link("t5", "g2")
    d.link("g2", "t7", "нет"); d.link("g2", "t6", "да", "vh"); d.link("t6", "t7", route="hv")
    d.link("t7", "e2")
    return d


def to_be_2():
    d = Diagram("to_be_2", "TO-BE (2/2): резервирование и отпуск, инвентаризация",
                ["Планировщик", "Информационная система", "Кладовщик", "Комиссия и система (инвентаризация)"], 10)
    d.add("s", "start", 0, 0, "Заказ-наряду нужна деталь")
    d.add("t1", "task", 1, 0, "Запросить резерв под WO-NNNN (с ключом запроса)")
    d.add("t2", "task", 2, 1, "Проверить доступное и записать резерв в одной транзакции")
    d.add("g1", "gw", 3, 1, "Хватает годного запаса?")
    d.add("e1", "end", 4, 0, "Отказ: «доступно N», пополнить или заменить")
    d.add("t3", "task", 4, 1, "Закрепить резерв за заказ-нарядом")
    d.add("t4", "task", 5, 2, "Подготовить деталь по резерву")
    d.add("g2", "gw", 6, 2, "Партия годна (не в карантине, не просрочена)?")
    d.add("t5", "task", 7, 2, "Выдать, отсканировать партию или S/N")
    d.add("t6", "task", 8, 1, "Провести выдачу: остаток и резерв уменьшены")
    d.add("e2", "end", 9, 1, "Выдача в истории и в заказ-наряде")
    d.add("t7", "task", 7, 1, "Снять резерв: заказ-наряд отменён или партия в карантине")
    d.add("e3", "end", 8, 0, "Запас снова доступен")
    d.add("s2", "start", 0, 3, "Плановая инвентаризация по ABC")
    d.add("i1", "task", 1, 3, "Создать ведомость из остатков системы")
    d.add("i2", "task", 2, 3, "Пересчитать, ввести факт")
    d.add("g3", "gw", 3, 3, "Расхождение выше допуска?")
    d.add("i3", "task", 4, 3, "Согласовать корректировку: причина, руководитель")
    d.add("i4", "task", 5, 3, "Провести корректировку движением")
    d.add("e4", "end", 6, 3, "Остаток подтверждён")
    d.link("s", "t1"); d.link("t1", "t2"); d.link("t2", "g1")
    d.link("g1", "e1", "нет", "vh"); d.link("g1", "t3", "да"); d.link("t3", "t4"); d.link("t4", "g2")
    d.link("g2", "t5", "да"); d.link("g2", "t7", "нет", "vh"); d.link("t5", "t6"); d.link("t6", "e2")
    d.link("t7", "e3", route="vh")
    d.link("s2", "i1"); d.link("i1", "i2"); d.link("i2", "g3"); d.link("g3", "i3", "да"); d.link("i3", "i4")
    d.link("i4", "e4")
    return d


# ---------------------------------------------------------------- ER
ER = {  # имя: (x, y, [(атрибут, метка)]) метка: pk / fk / uk / ""
    "Номенклатура": (20, 150, [("item_id", "pk"), ("pn", "uk"), ("name", ""), ("base_uom", ""), ("is_serial", "")]),
    "Единица измерения": (20, 20, [("item_id", "pk"), ("uom", "pk"), ("factor", "")]),
    "Партия": (270, 150, [("batch_id", "pk"), ("item_id", "fk"), ("batch_no", "uk"), ("expiry_date", ""), ("cert_no", ""), ("status", "")]),
    "Серийная единица (S/N)": (270, 20, [("item_id", "pk"), ("serial_no", "pk"), ("receipt_id", "fk"), ("batch_id", "fk"), ("status", "")]),
    "Склад": (1020, 330, [("warehouse_id", "pk"), ("code", "uk"), ("name", "")]),
    "Место хранения": (770, 330, [("location_id", "pk"), ("warehouse_id", "fk"), ("code", "uk")]),
    "Остаток": (520, 330, [("item_id", "pk"), ("batch_id", "pk"), ("location_id", "pk"), ("on_hand", ""), ("reserved", "")]),
    "Поставщик": (1020, 20, [("supplier_id", "pk"), ("name", ""), ("lead_time_days", "")]),
    "Заказ поставщику": (770, 20, [("order_id", "pk"), ("supplier_id", "fk"), ("doc_no", "uk"), ("status", ""), ("expected_date", "")]),
    "Строка заказа": (770, 150, [("order_id", "pk"), ("line_no", "pk"), ("item_id", "fk"), ("qty", ""), ("price", "")]),
    "Приходный документ": (520, 20, [("receipt_id", "pk"), ("doc_no", "uk"), ("order_id", "fk"), ("status", ""), ("created_by", "fk")]),
    "Строка прихода": (520, 150, [("line_id", "pk"), ("receipt_id", "fk"), ("item_id", "fk"), ("batch_id", "fk"), ("location_id", "fk"), ("qty_base", "")]),
    "Движение запасов": (270, 520, [("movement_id", "pk"), ("kind", ""), ("item_id", "fk"), ("batch_id", "fk"), ("location_id", "fk"), ("qty_delta", ""), ("reserved_delta", ""), ("doc_ref", ""), ("user_id", "fk"), ("reverses_id", "fk")]),
    "Резерв": (20, 330, [("reservation_id", "pk"), ("request_id", "uk"), ("item_id", "fk"), ("work_order", ""), ("qty", ""), ("status", ""), ("created_by", "fk")]),
    "Строка резерва": (270, 330, [("reservation_id", "pk"), ("batch_id", "pk"), ("location_id", "pk"), ("qty", "")]),
    "Инвентаризация": (770, 500, [("count_id", "pk"), ("location_id", "fk"), ("status", ""), ("created_by", "fk")]),
    "Строка инвентаризации": (1020, 500, [("count_id", "pk"), ("item_id", "pk"), ("batch_id", "pk"), ("qty_book", ""), ("qty_fact", "")]),
    "Пользователь": (20, 520, [("user_id", "pk"), ("name", "uk"), ("role", ""), ("blocked", "")]),
}
# (A, B, кратность у A, кратность у B); one / zeroone / many / zeromany
ER_LINKS = [
    ("Номенклатура", "Единица измерения", "one", "many"), ("Номенклатура", "Партия", "one", "zeromany"),
    ("Партия", "Серийная единица (S/N)", "one", "zeromany"), ("Приходный документ", "Серийная единица (S/N)", "one", "zeromany"),
    ("Склад", "Место хранения", "one", "many"), ("Партия", "Остаток", "one", "zeromany"),
    ("Место хранения", "Остаток", "one", "zeromany"), ("Остаток", "Движение запасов", "one", "zeromany"),
    ("Поставщик", "Заказ поставщику", "one", "zeromany"), ("Заказ поставщику", "Строка заказа", "one", "many"),
    ("Заказ поставщику", "Приходный документ", "zeroone", "zeromany"), ("Приходный документ", "Строка прихода", "one", "many"),
    ("Партия", "Строка прихода", "one", "zeromany"), ("Резерв", "Строка резерва", "one", "many"),
    ("Партия", "Строка резерва", "one", "zeromany"), ("Номенклатура", "Резерв", "one", "zeromany"),
    ("Место хранения", "Инвентаризация", "one", "zeromany"), ("Инвентаризация", "Строка инвентаризации", "one", "many"),
    ("Пользователь", "Резерв", "one", "zeromany"), ("Пользователь", "Движение запасов", "one", "zeromany"),
]
ER_W, ER_ROW = 200, 17
ARROW = {"one": "ERmandOne", "zeroone": "ERzeroToOne", "many": "ERoneToMany", "zeromany": "ERzeroToMany"}
CARD = {"one": "1", "zeroone": "0..1", "many": "1..*", "zeromany": "0..*"}


def er_box(name):
    x, y, attrs = ER[name]
    return x, y, ER_W, 22 + ER_ROW * len(attrs)


def clip(box, tx, ty):
    x, y, w, h = box
    cx, cy = x + w / 2, y + h / 2
    dx, dy = tx - cx, ty - cy
    if dx == 0 and dy == 0:
        return cx, cy
    k = min((w / 2) / abs(dx) if dx else 1e9, (h / 2) / abs(dy) if dy else 1e9)
    return cx + dx * k, cy + dy * k


def er_png(path):
    s = 2
    W, H = 1230, 780
    img = Image.new("RGB", (W * s, H * s), "white")
    d = ImageDraw.Draw(img)
    f, fb, fs = font(10 * s), font(11 * s, True), font(9 * s)
    d.text((20 * s, 2 * s), "ER-модель системы учёта запасов авиатехнической базы (PK – ключ, FK – внешний ключ, UK – уникальность; часть связей по item_id и location_id не показана)",
           fill="#222", font=fb)
    for a, b, ca, cb in ER_LINKS:
        ba, bb = er_box(a), er_box(b)
        ca_c = (ba[0] + ba[2] / 2, ba[1] + ba[3] / 2)
        cb_c = (bb[0] + bb[2] / 2, bb[1] + bb[3] / 2)
        p1, p2 = clip(ba, *cb_c), clip(bb, *ca_c)
        d.line([(p1[0] * s, p1[1] * s), (p2[0] * s, p2[1] * s)], fill="#555", width=s)
        for (px, py), (qx, qy), card in ((p1, p2, ca), (p2, p1, cb)):
            ux, uy = qx - px, qy - py
            n = max((ux * ux + uy * uy) ** 0.5, 1)
            tx, ty = px + ux / n * 16, py + uy / n * 16
            d.text((tx * s - 6 * s, ty * s - 6 * s), CARD[card], fill="#a02020", font=fs)
    for name, (x, y, attrs) in ER.items():
        bx, by, bw, bh = er_box(name)
        d.rectangle([bx * s, by * s, (bx + bw) * s, (by + bh) * s], fill="#fffef5", outline="#333", width=s)
        d.rectangle([bx * s, by * s, (bx + bw) * s, (by + 22) * s], fill="#dfe8f3", outline="#333", width=s)
        d.text(((bx + 6) * s, (by + 4) * s), name, fill="#111", font=fb)
        for i, (attr, tag) in enumerate(attrs):
            ty = by + 22 + i * ER_ROW
            label = {"pk": "PK ", "fk": "FK ", "uk": "UK "}.get(tag, "     ")
            d.text(((bx + 6) * s, (ty + 2) * s), f"{label}{attr}", fill="#111", font=font(10 * s, tag == "pk"))
    img.resize((int(W * 1.5), int(H * 1.5)), Image.LANCZOS).save(path)


def er_cells(start):
    cells, n, ids = [], [start], {}

    def nid():
        n[0] += 1
        return f"c{n[0]}"

    for name in ER:
        x, y, attrs = ER[name]
        cid = nid()
        ids[name] = cid
        rows = "<br>".join(f"{'<b>PK</b> ' if t == 'pk' else ('FK ' if t == 'fk' else ('UK ' if t == 'uk' else '&nbsp;&nbsp;&nbsp;&nbsp;'))}{a}" for a, t in attrs)
        cells.append(f'<mxCell id="{cid}" value="&lt;b&gt;{escape(name)}&lt;/b&gt;" style="swimlane;fontStyle=1;fillColor=#dfe8f3;'
                     f'fontSize=11;html=1;startSize=22;" vertex="1" parent="1"><mxGeometry x="{x}" y="{y + 30}" width="{ER_W}" '
                     f'height="{22 + ER_ROW * len(attrs)}" as="geometry"/></mxCell>')
        cells.append(f'<mxCell id="{nid()}" value="{escape(rows)}" style="text;html=1;align=left;verticalAlign=top;fontSize=10;'
                     f'spacingLeft=4;" vertex="1" parent="{cid}"><mxGeometry y="22" width="{ER_W}" height="{ER_ROW * len(attrs)}" '
                     f'as="geometry"/></mxCell>')
    for a, b, ca, cb in ER_LINKS:
        cells.append(f'<mxCell id="{nid()}" style="edgeStyle=none;html=1;startArrow={ARROW[ca] if ca != "many" else "ERmandOne"};'
                     f'endArrow={ARROW[cb]};startFill=0;endFill=0;strokeColor=#555555;" edge="1" parent="1" source="{ids[a]}" '
                     f'target="{ids[b]}"><mxGeometry relative="1" as="geometry"/></mxCell>')
    return cells


def main():
    (ROOT / "assets").mkdir(exist_ok=True)
    diagrams = [as_is_1(), as_is_2(), to_be_1(), to_be_2()]
    pages = []
    for i, dg in enumerate(diagrams):
        dg.png(ROOT / f"assets/bpmn_{dg.name}.png")
        cells = dg.drawio_cells(i * 1000)
        pages.append((dg.title, dg.width, dg.height, cells))
    er_png(ROOT / "assets/er_model.png")
    pages.append(("ER-модель", 1250, 780, er_cells(9000)))
    from make_uml import uml_pages
    pages.extend(uml_pages())
    xml = ['<mxfile host="app.diagrams.net">']
    for i, (title, w, h, cells) in enumerate(pages):
        xml.append(f'<diagram id="p{i}" name="{escape(title)}"><mxGraphModel dx="{int(w)}" dy="{int(h)}" grid="1" '
                   f'gridSize="10" guides="1" page="1" pageWidth="{int(w)}" pageHeight="{int(h)}"><root><mxCell id="0"/>'
                   f'<mxCell id="1" parent="0"/>' + "".join(cells) + "</root></mxGraphModel></diagram>")
    xml.append("</mxfile>")
    (ROOT / "inventory_model.drawio").write_text("".join(xml), encoding="utf-8")
    print("ok:", [p[0] for p in pages])


if __name__ == "__main__":
    main()
