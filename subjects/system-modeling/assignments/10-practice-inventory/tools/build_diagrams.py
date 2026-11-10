"""Builds the two diagrams of the report: UML Activity (reservation process) and ER model.

    python tools/build_diagrams.py

Output: assets/inventory_model.drawio (editable, diagrams.net, one page per diagram) and assets/NN_name.png.
"""

import pathlib
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(pathlib.Path(__file__).parent))

from diagram_lib import Canvas, drawio_file  # noqa: E402

OUT = pathlib.Path(__file__).resolve().parent.parent / "assets"


def d1_process() -> Canvas:
    c = Canvas("1. UML Activity: резервирование запаса", 900, 900)
    c.label(10, 6, 880, 22, "UML Activity Diagram: процесс резервирования запаса (BR-01 – BR-06)", size=14, bold=True, align="left")
    # lanes
    c.rect(10, 36, 140, 840, "", stroke="#666666")
    c.rect(150, 36, 745, 840, "", stroke="#666666")
    c.label(10, 38, 140, 20, "Заявитель", bold=True, size=12)
    c.label(150, 38, 745, 20, "Система резервирования (InventoryService, SQLite)", bold=True, size=12)

    MX, MW = 175, 220          # main column
    cx = MX + MW / 2
    C1X, C1W = 450, 200        # refusals
    C2X, C2W = 690, 170        # repeat result
    COL = 880

    def act(x, y, w, h, text, **kw):
        return c.rect(x, y, w, h, text, rounded=10, size=10, **kw)

    def dec(y, text, w=MW, h=62):
        return c.diamond(MX, y, w, h, text, size=10)

    def arrow(pts, **kw):
        c.line(pts, end="open", **kw)

    def yes_no(x, y, text):
        c.label(x, y, 30, 14, text, size=10, bold=True)

    # lane 1: request
    start = c.circle(80, 76, 8)
    req = act(20, 96, 120, 84, "Сформировать запрос: ключ, товар, склад, количество, заявка", fill="#fff2cc")
    arrow([start.pt("b"), req.pt("t")])

    s1 = act(MX, 96, MW, 40, "Принять запрос с ключом операции", fill="#dae8fc")
    arrow([req.pt("r", 0.25), s1.pt("l")])
    d1 = dec(160, "Роль – заявитель?\n(права)")
    d2 = dec(250, "Количество – целое\nположительное число?")
    s2 = act(MX, 342, MW, 44, "BEGIN IMMEDIATE:\nзахватить блокировку записи", fill="#dae8fc")
    d3 = dec(410, "Ключ уже есть\nв реестре запросов?")
    s3 = act(MX, 506, MW, 40, "Рассчитать A = OH − R − B", fill="#dae8fc")
    d5 = dec(570, "A ≥ запрошенного\nколичества?")
    s4 = act(MX, 664, MW, 60, "Создать резерв и событие CREATE;\nзаписать результат в реестр;\nCOMMIT", fill="#d5e8d4")
    fin = act(MX, 760, MW, 44, "Вернуть результат:\nстатус, количества до и после", fill="#dae8fc")
    arrow([s1.pt("b"), d1.pt("t")])
    arrow([d1.pt("b"), d2.pt("t")])
    arrow([d2.pt("b"), s2.pt("t")])
    arrow([s2.pt("b"), d3.pt("t")])
    arrow([d3.pt("b"), s3.pt("t")])
    arrow([s3.pt("b"), d5.pt("t")])
    arrow([d5.pt("b"), s4.pt("t")])
    arrow([s4.pt("b"), fin.pt("t")])
    yes_no(cx + 4, 224, "да")
    yes_no(cx + 4, 314, "да")
    yes_no(cx + 4, 474, "нет")
    yes_no(cx + 4, 634, "да")

    # refusals (right column 1)
    forb = act(C1X, 168, C1W, 46, "Отказ FORBIDDEN\n(ничего не читается и не пишется)", fill="#f8cecc")
    badq = act(C1X, 258, C1W, 46, "Отказ INVALID_QUANTITY\n(ключ не расходуется)", fill="#f8cecc")
    arrow([d1.pt("r"), forb.pt("l")])
    yes_no(MX + MW + 6, 168, "нет")
    arrow([d2.pt("r"), badq.pt("l")])
    yes_no(MX + MW + 6, 258, "нет")

    # repeated key: compare parameters
    d4 = c.diamond(C1X, 404, C1W, 74, "Параметры запроса\nте же?", size=10)
    arrow([d3.pt("r"), d4.pt("l")])
    yes_no(MX + MW + 6, 408, "да")
    rep = act(C2X, 408, C2W, 66, "Вернуть сохранённый\nрезультат (повтор), без\nновых изменений", fill="#e1d5e7")
    arrow([d4.pt("r"), rep.pt("l")])
    yes_no(C1X + C1W + 6, 408, "да")
    conf = act(C1X, 506, C1W, 46, "Отказ CONFLICT\n(ROLLBACK, запас не меняется)", fill="#f8cecc")
    arrow([d4.pt("b"), conf.pt("t")])
    yes_no(C1X + C1W / 2 + 4, 482, "нет")
    insuf = act(C1X, 578, C1W, 60, "Отказ INSUFFICIENT_STOCK:\nзаписать отказ в реестр,\nCOMMIT, запас не меняется", fill="#f8cecc")
    arrow([d5.pt("r"), insuf.pt("l")])
    yes_no(MX + MW + 6, 578, "нет")

    # merge of all results
    ymid = fin.y + fin.h / 2
    for box in (forb, badq, conf, insuf):
        c.line([box.pt("r"), (COL, box.y + box.h / 2)], end="none")
    c.line([rep.pt("r"), (COL, rep.y + rep.h / 2)], end="none")
    c.line([(COL, forb.y + forb.h / 2), (COL, ymid), fin.pt("r")], end="open")

    # lane 1: result
    got = act(20, 760, 120, 44, "Получить результат", fill="#fff2cc")
    arrow([fin.pt("l"), got.pt("r")])
    end = c.circle(80, 838, 10, final=True)
    arrow([got.pt("b"), (80, 828)])
    c.note(450, 690, 400, 60,
           "Все ветви в одной транзакции записи: либо полный результат и запись в реестре, либо откат. "
           "Техническая ошибка (БД занята после повторных попыток) – отдельное исключение BUSY, не отказ по запасу.",
           size=10)
    return c.fit()


def d2_er() -> Canvas:
    c = Canvas("2. ER-модель", 900, 900)
    c.label(10, 6, 880, 22, "ER-модель базы данных inventory.db (SQLite)", size=14, bold=True, align="left")
    S = 10
    A, B, Cx, W = 10, 340, 670, 260

    def table(x, y, name, attrs, header="#dae8fc"):
        return c.class_box(x, y, W, name, attrs, None, size=S, header=header)

    product = table(A, 40, "product", ["PK  code", "name  NOT NULL"])
    stock = table(B, 40, "stock (остаток)", [
        "PK, FK  product_code", "PK, FK  warehouse_code", "on_hand  INTEGER ≥ 0   (OH)", "blocked_qty  INTEGER ≥ 0   (B)",
        "CHECK blocked_qty ≤ on_hand"], header="#fff2cc")
    wh = table(Cx, 40, "warehouse", ["PK  code", "name  NOT NULL"])
    y2 = stock.y + stock.h + 55
    plan = table(A, y2, "planning_param (параметры планирования)", [
        "PK, FK  product_code", "annual_demand  > 0   (D)", "order_cost  > 0   (S)", "holding_cost  > 0   (H)",
        "lead_days  > 0   (L)", "safety_stock  ≥ 0   (SS)", "pack_size  > 0   (p)", "on_order  ≥ 0   (OO)",
        "backorder  ≥ 0   (BO)"])
    mov = table(B, y2, "movement (движение)", [
        "PK  id", "FK  (product_code, warehouse_code)", "kind  OPENING | RECEIPT | ISSUE", "qty  > 0",
        "document  UNIQUE  (ключ запроса)", "created_at"])
    res = table(Cx, y2, "reservation (резерв)", [
        "PK  code  (= ключ запроса)", "FK  (product_code, warehouse_code)", "request_id  (заявка)", "initial_qty  > 0",
        "remaining_qty  ≥ 0", "status  ACTIVE | FULFILLED | RELEASED", "CHECK remaining_qty ≤ initial_qty",
        "CHECK ACTIVE только при remaining_qty > 0", "created_at"])
    y3 = max(plan.y + plan.h, mov.y + mov.h, res.y + res.h) + 55
    req = table(B, y3, "processed_request (обработанный запрос)", [
        "PK  request_key", "operation  RESERVE | RELEASE | ISSUE | RECEIVE | OPENING", "params  (JSON)",
        "status", "result  (JSON)", "created_at"], header="#d5e8d4")
    ev = table(Cx, y3, "reserve_event (история резерва)", [
        "PK  id", "FK  reservation_code", "kind  CREATE | ISSUE | RELEASE", "qty  > 0",
        "request_key  UNIQUE", "created_at"])
    c.note(A, y3, W, 140,
           "Представления: v_stock_position (OH, R, B, A = OH − R − B), v_stock_check (OH и сумма движений), "
           "v_reserve_check (история резерва).\nR не хранится: сумма remaining_qty резервов ACTIVE.\n"
           "Триггеры: запрет перерезервирования и отрицательного A.", size=9)

    def tag(x, y, text, w=30):
        c.label(x - w / 2, y, w, 14, text, size=10)

    # product 1 -- 0..* stock
    y = product.y + 22
    c.line([product.pt("r", 0.3), (B, product.y + product.h * 0.3)])
    tag(A + W + 12, y - 16, "1")
    tag(B - 22, y - 16, "0..*")
    # warehouse 1 -- 0..* stock
    c.line([(Cx, wh.y + 24), (B + W, wh.y + 24)])
    tag(Cx - 12, wh.y + 8, "1")
    tag(B + W + 22, wh.y + 8, "0..*")
    # product 1 -- 1 planning_param
    c.line([(product.cx, product.y + product.h), (product.cx, plan.y)])
    tag(product.cx + 14, product.y + product.h + 2, "1")
    tag(product.cx + 14, plan.y - 16, "1")
    # stock 1 -- 0..* movement
    c.line([(stock.cx, stock.y + stock.h), (stock.cx, mov.y)])
    tag(stock.cx + 16, stock.y + stock.h + 2, "1")
    tag(stock.cx + 18, mov.y - 16, "0..*")
    # stock 1 -- 0..* reservation (via the right side below the warehouse box)
    ys = stock.y + stock.h - 12
    c.line([(B + W, ys), (res.cx, ys), (res.cx, res.y)])
    tag(B + W + 14, ys - 16, "1")
    tag(res.cx + 20, res.y - 16, "0..*")
    # reservation 1 -- 1..* event
    c.line([(res.cx, res.y + res.h), (res.cx, ev.y)])
    tag(res.cx + 14, res.y + res.h + 2, "1")
    tag(res.cx + 20, ev.y - 16, "1..*")
    # logical links by request key (no FK)
    c.line([(mov.cx, mov.y + mov.h), (mov.cx, req.y)], dashed=True)
    c.label(mov.cx + 6, mov.y + mov.h + 14, 120, 14, "document = ключ", size=9, italic=True, align="left")
    c.line([(req.x + W, req.y + 40), (ev.x, ev.y + 40)], dashed=True)
    c.label(req.x + W + 2, req.y + 24, 50, 14, "по ключу", size=9, italic=True)
    return c.fit()


PAGES = [("01_process_reservation", d1_process), ("02_er_model", d2_er)]


def main():
    OUT.mkdir(exist_ok=True)
    canvases = []
    for name, fn in PAGES:
        canvas = fn()
        canvases.append(canvas)
        canvas.to_png(str(OUT / f"{name}.png"))
        print("png", name, canvas.w, "x", canvas.h)
    (OUT / "inventory_model.drawio").write_text(drawio_file(canvases), encoding="utf-8")


if __name__ == "__main__":
    main()
