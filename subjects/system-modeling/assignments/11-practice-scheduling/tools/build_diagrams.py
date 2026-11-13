"""Builds the figures of the report: two Gantt charts, the ER diagram and the approval sequence diagram.

    python tools/build_diagrams.py

Output: assets/allocation_model.drawio (editable, diagrams.net, one page per figure) and assets/NN_name.png.
Plans come from prototype/planning.py (single source of truth).
"""

import pathlib
import sys

sys.stdout.reconfigure(encoding="utf-8")
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "prototype"))

from diagram_lib import Canvas, drawio_file, text_width, wrap_lines  # noqa: E402
from planning import (MACHINES, STEP, base_calendar, best_schedule, calendar_with_r4_repair, duration_of,  # noqa: E402
                      hhmm, hm, makespan, preparations)


class Seq:
    """Sequence diagram builder: lifelines, numbered messages, alt fragments (after task 9 tools)."""
    SZ = 10

    def __init__(self, name, participants, step=135, x0=70):
        self.c = Canvas(name, 100, 100)
        self.px = {i: x0 + step * i for i in range(len(participants))}
        self.step = step
        self.n = 0
        self.heads = []
        for i, t in enumerate(participants):
            actor = t.startswith("@")
            text = t[1:] if actor else t
            self.heads.append(self.c.rect(self.px[i] - step / 2 + 4, 36, step - 8, 40, text,
                                          fill="#fff2cc" if actor else "#dae8fc", bold=True, size=self.SZ, pad=2))
        self.y = 82
        self.left, self.right = self.px[0] - step / 2 + 4, self.px[len(participants) - 1] + step / 2 - 4

    def msg(self, a, b, text, *, ret=False, num=True):
        xa, xb = self.px[a], self.px[b]
        if num and not ret:
            self.n += 1
            text = f"{self.n}: {text}"
        w = max(abs(xb - xa) - 14, 80)
        lines = wrap_lines(text, w, self.SZ)
        h = 12.5 * len(lines)
        y = self.y + h + 4
        self.c.line([(xa, y), (xb, y)], end="open" if ret else "filled", dashed=ret)
        lw = min(w, max(max(text_width(t, self.SZ) for t in lines) + 6, 20))
        self.c.label((xa + xb) / 2 - lw / 2, y - h - 3, lw, h, text, size=self.SZ, italic=ret, bg=True)
        self.y = y + 12
        return y

    def self_msg(self, a, text, *, num=True):
        x = self.px[a]
        if num:
            self.n += 1
            text = f"{self.n}: {text}"
        lines = wrap_lines(text, self.step + 30, self.SZ)
        h = 12.5 * len(lines)
        y = self.y + 8
        loop = max(h, 18)
        self.c.line([(x, y), (x + 26, y), (x + 26, y + loop), (x, y + loop)], end="filled")
        self.c.label(x + 30, y + loop / 2 - h / 2, self.step + 30, h, text, size=self.SZ, align="left")
        self.y = y + loop + 10

    # alt fragments
    def alt_begin(self, label="alt", inset=0):
        return dict(y1=self.y + 4, inset=inset, label=label, first=True)

    def operand(self, f, guard):
        x1, x2 = self.left - 8 + f["inset"], self.right + 8 - f["inset"]
        if f["first"]:
            f["first"] = False
            self.c.label(x1 + 46, f["y1"] + 3, x2 - x1 - 50, 15, f"[{guard}]", size=self.SZ + 1, bold=True, align="left")
            self.y = f["y1"] + 24
        else:
            y = self.y + 4
            self.c.line([(x1, y), (x2, y)], dashed=True, color="#555555")
            self.c.label(x1 + 6, y + 3, x2 - x1 - 12, 15, f"[{guard}]", size=self.SZ + 1, bold=True, align="left")
            self.y = y + 22

    def alt_end(self, f):
        x1, x2 = self.left - 8 + f["inset"], self.right + 8 - f["inset"]
        y2 = self.y + 4
        self.c.rect(x1, f["y1"], x2 - x1, y2 - f["y1"], "", fill="none", stroke="#444444")
        self.c.rect(x1, f["y1"], 40, 17, f["label"], fill="#ffffff", stroke="#444444", bold=True, size=self.SZ + 1)
        self.y = y2 + 8

    def finish(self):
        bottom = self.y + 8
        lifelines = [dict(kind="line", id=self.c._id("e"), pts=[(self.px[i], h.y + h.h), (self.px[i], bottom)],
                          end="none", start="none", dashed=True, color="#777777", sw=1, src=None, dst=None)
                     for i, h in enumerate(self.heads)]
        self.c.items[0:0] = lifelines
        return self.c.fit()

OUT = HERE.parent / "assets"
LEFT, TOP, CELL, ROW = 80, 80, 56, 56
T0, T1 = hm("09:00"), hm("17:00")


def x_of(minutes: int) -> float:
    return LEFT + (minutes - T0) / STEP * CELL


def gantt(name: str, title: str, cal, plan: dict) -> Canvas:
    slots = (T1 - T0) // STEP
    c = Canvas(name, 1100, 460)
    c.label(10, 6, 1000, 22, title, size=13, bold=True, align="left")
    for t in range(slots + 1):
        x = LEFT + t * CELL
        c.line([(x, TOP - 6), (x, TOP + ROW * len(MACHINES))], color="#999999" if t % 2 else "#666666")
        if t % 2 == 0:
            c.label(x - 22, TOP - 28, 44, 18, hhmm(T0 + t * STEP), size=10)
    for i, r in enumerate(MACHINES):
        y = TOP + i * ROW
        c.label(10, y, 60, ROW, r, size=13, bold=True)
        c.rect(LEFT, y, slots * CELL, ROW, "", stroke="#666666")
        # closed time = outside the open intervals
        free = sorted(cal.open.get(r, []))
        cursor = T0
        for s, e in free + [(T1, T1)]:
            if s > cursor:
                c.rect(x_of(cursor), y, x_of(s) - x_of(cursor), ROW, "закрыто", fill="#e0e0e0", stroke="#999999",
                       size=9, font_color="#555555")
            cursor = max(cursor, e)
        for s, e in cal.repairs.get(r, []):
            c.rect(x_of(s), y, x_of(e) - x_of(s), ROW, f"ремонт\n{hhmm(s)}–{hhmm(e)}", fill="#f8cecc",
                   stroke="#b85450", size=9)
        for s, e, label in cal.bookings.get(r, []):
            c.rect(x_of(s), y, x_of(e) - x_of(s), ROW, f"{label}\n{hhmm(s)}–{hhmm(e)}", fill="#ffe6cc",
                   stroke="#d79b00", size=9)
    for r, s, e, before in preparations(cal, plan):
        y = TOP + MACHINES.index(r) * ROW
        c.rect(x_of(s), y + 4, x_of(e) - x_of(s), ROW - 8, "подг.", fill="#fff2cc", stroke="#d6b656", size=8, pad=1)
    for j, (r, s) in plan.items():
        y = TOP + MACHINES.index(r) * ROW
        dur = duration_of(j)
        c.rect(x_of(s) + 1, y + 4, x_of(s + dur) - x_of(s) - 2, ROW - 8,
               f"{j} {hhmm(s)}–{hhmm(s + dur)}", fill="#dae8fc", stroke="#6c8ebf", size=9, sw=1.5)
    end = makespan(plan)
    c.line([(x_of(end), TOP - 10), (x_of(end), TOP + ROW * len(MACHINES) + 14)], color="#b85450", dashed=True, sw=2)
    c.label(x_of(end) - 120, TOP + ROW * len(MACHINES) + 12, 240, 18,
            f"окончание последней работы {hhmm(end)}", size=10, bold=True, font_color="#b85450")
    y = TOP + ROW * len(MACHINES) + 40
    lx = 10
    for fill, label in (("#dae8fc", "работа"), ("#fff2cc", "подготовка 30 мин"), ("#ffe6cc", "бронь"),
                        ("#f8cecc", "ремонт"), ("#e0e0e0", "машина закрыта")):
        c.rect(lx, y + 2, 22, 14, "", fill=fill)
        c.label(lx + 26, y, 150, 18, label, size=10, align="left")
        lx += 190
    return c.fit()


def er() -> Canvas:
    c = Canvas("ER-модель", 1000, 900)
    c.label(10, 6, 960, 22, "ER-диаграмма системы распределения ресурсов", size=14, bold=True, align="left")
    S, W = 10, 300
    A, B, C = 10, 400, 790

    def table(x, y, name, attrs, header="#dae8fc"):
        return c.class_box(x, y, W, name, attrs, None, size=S, header=header)

    req = table(A, 40, "Request (Заявка)", [
        "PK  id  (J1 … J4)", "name  NOT NULL", "earliest_min  NOT NULL  (раннее начало)",
        "deadline_min  NOT NULL  (крайний срок)", "duration_min  NOT NULL, > 0, кратно 30",
        "CHECK deadline − earliest ≥ duration"])
    elig = table(B, 40, "Eligibility (Пригодность)", [
        "PK, FK  request_id  → Request", "PK, FK  resource_id  → Resource", "cost_kt  NOT NULL, > 0  (тыс. тенге)",
        "пары нет в таблице = пара недопустима"], header="#ffe6cc")
    res = table(C, 40, "Resource (Ресурс)", ["PK  id  (R1 … R4)", "name  NOT NULL"])
    y2 = max(req.y + req.h, elig.y + elig.h, res.y + res.h) + 70
    plan = table(A, y2, "Plan (План)", [
        "PK  id", "scenario  NOT NULL", "status  NOT NULL: DRAFT | APPROVED | REJECTED",
        "calendar_version  NOT NULL  (версия данных расчёта)", "created_by  NOT NULL"], header="#d5e8d4")
    alloc = table(B, y2, "Allocation (Назначение)", [
        "PK  id", "FK  plan_id  → Plan  NOT NULL", "request_id, resource_id  NOT NULL",
        "start_min, end_min  NOT NULL, end > start", "status  NOT NULL: PLANNED | ACTIVE | CANCELLED",
        "FK (request_id, resource_id) → Eligibility", "UNIQUE (plan_id, request_id)",
        "UNIQUE (request_id) WHERE status = ACTIVE"], header="#d5e8d4")
    win = table(C, y2, "AvailabilityWindow (Окно доступности)", [
        "PK  id", "FK  resource_id  → Resource  NOT NULL", "start_min, end_min  NOT NULL, end > start",
        "kind  NOT NULL: OPEN | REPAIR | BOOKING", "label  (B01 для брони)"], header="#fff2cc")
    y3 = max(plan.y + plan.h, alloc.y + alloc.h, win.y + win.h) + 60
    log = table(A, y3, "ApprovalLog (Журнал утверждения)", [
        "PK  id", "FK  plan_id  → Plan  NOT NULL", "idempotency_key  NOT NULL, UNIQUE",
        "dispatcher  NOT NULL", "outcome  NOT NULL: APPROVED | REJECTED_STALE |\n    REJECTED_INVALID | REJECTED_CONFLICT",
        "message, calendar_version  NOT NULL"], header="#d5e8d4")
    slot = table(B, y3, "BookingSlot (Слот брони, служебная)", [
        "PK, FK  resource_id  → Resource", "PK  slot_start  (шаг 30 минут)", "FK  allocation_id  → Allocation  NOT NULL",
        "PK исключает двойную бронь слота"], header="#e1d5e7")
    cal = table(C, y3, "CalendarState (Версия данных, служебная)", [
        "PK  id  (одна строка, = 1)", "version  NOT NULL  (растёт при каждом\n    изменении календаря)"],
        header="#e1d5e7")

    def tag(x, y, text, w=34):
        c.label(x - w / 2, y, w, 14, text, size=10)

    # Request 1 -- 0..* Eligibility
    ye = elig.y + 30
    c.line([(A + W, ye), (B, ye)])
    tag(A + W + 14, ye - 16, "1")
    tag(B - 20, ye - 16, "0..*")
    # Eligibility 0..* -- 1 Resource
    c.line([(B + W, ye), (C, ye)])
    tag(B + W + 20, ye - 16, "0..*")
    tag(C - 12, ye - 16, "1")
    # Request 1 -- 0..* Allocation (elbow through the gap between rows)
    g1 = y2 - 24
    xr = A + W - 60
    c.line([(xr, req.y + req.h), (xr, g1), (B + 60, g1), (B + 60, alloc.y)], end="none")
    tag(xr + 14, req.y + req.h + 2, "1")
    tag(B + 80, alloc.y - 16, "0..*")
    # Resource 1 -- 0..* Allocation
    g2 = y2 - 40
    c.line([(B + W - 60, alloc.y), (B + W - 60, g2), (C + 60, g2), (C + 60, res.y + res.h)])
    tag(B + W - 40, alloc.y - 16, "0..*")
    tag(C + 74, res.y + res.h + 2, "1")
    # Resource 1 -- 0..* AvailabilityWindow
    xw = C + W - 60
    c.line([(xw, res.y + res.h), (xw, win.y)])
    tag(xw + 14, res.y + res.h + 2, "1")
    tag(xw + 20, win.y - 16, "0..*")
    # Plan 1 -- 1..* Allocation
    ya = alloc.y + 40
    c.line([(A + W, ya), (B, ya)])
    tag(A + W + 14, ya - 16, "1")
    tag(B - 20, ya - 16, "1..*")
    # Plan 1 -- 0..* ApprovalLog
    c.line([(plan.cx, plan.y + plan.h), (plan.cx, log.y)])
    tag(plan.cx + 14, plan.y + plan.h + 2, "1")
    tag(plan.cx + 20, log.y - 16, "0..*")
    # Allocation 1 -- 0..* BookingSlot
    c.line([(alloc.cx, alloc.y + alloc.h), (alloc.cx, slot.y)])
    tag(alloc.cx + 14, alloc.y + alloc.h + 2, "1")
    tag(alloc.cx + 20, slot.y - 16, "0..*")
    return c.fit()


def sequence() -> Canvas:
    s = Seq("Диаграмма последовательности утверждения плана",
            ["@Диспетчер", ":Сервис утверждения", ":База данных (SQLite)"], step=330, x0=170)
    D, SV, DB = range(3)
    s.c.label(10, 6, 960, 22, "Диаграмма последовательности: утверждение плана (транзакция, блокировка, повтор)",
              size=14, bold=True, align="left")
    s.msg(D, SV, "approve(plan_id, idempotency_key)")
    s.msg(SV, DB, "BEGIN IMMEDIATE – блокировка записи: параллельные утверждения идут по очереди")
    s.msg(SV, DB, "SELECT … FROM approval_log WHERE idempotency_key = ?")
    f0 = s.alt_begin()
    s.operand(f0, "ключ уже есть в журнале – повторный запрос")
    s.msg(DB, SV, "прежний результат", ret=True)
    s.msg(SV, DB, "COMMIT (ничего не изменено)")
    s.msg(SV, D, "прежний результат, без новой брони", ret=True)
    s.operand(f0, "ключа нет – новый запрос")
    s.msg(SV, DB, "SELECT calendar_version FROM calendar_state; SELECT calendar_version, status FROM plan")
    f1 = s.alt_begin(inset=10)
    s.operand(f1, "версия плана ≠ текущей версии (план устарел)")
    s.msg(SV, DB, "INSERT approval_log (REJECTED_STALE); UPDATE plan → REJECTED; COMMIT")
    s.msg(SV, D, "REJECTED_STALE: план не утверждён", ret=True)
    s.operand(f1, "версии совпадают")
    s.msg(SV, DB, "SELECT окна доступности и назначения плана")
    s.self_msg(SV, "повторная проверка календаря: окна, ремонт, брони, пересечения, подготовка 30 мин")
    f2 = s.alt_begin(inset=20)
    s.operand(f2, "есть нарушения")
    s.msg(SV, DB, "INSERT approval_log (REJECTED_INVALID); COMMIT")
    s.msg(SV, D, "REJECTED_INVALID + список нарушений", ret=True)
    s.operand(f2, "нарушений нет")
    s.msg(SV, DB, "SAVEPOINT; UPDATE allocation → ACTIVE; INSERT booking_slot для каждого слота")
    f3 = s.alt_begin(inset=30)
    s.operand(f3, "слот уже занят (нарушение PRIMARY KEY или UNIQUE по активной заявке)")
    s.msg(DB, SV, "IntegrityError", ret=True)
    s.msg(SV, DB, "ROLLBACK TO SAVEPOINT; INSERT approval_log (REJECTED_CONFLICT); COMMIT")
    s.msg(SV, D, "REJECTED_CONFLICT: план не утверждён, бронь не сохранена", ret=True)
    s.operand(f3, "все слоты свободны")
    s.msg(SV, DB, "UPDATE plan → APPROVED; INSERT approval_log (APPROVED); COMMIT")
    s.msg(SV, D, "APPROVED: назначения сохранены одной транзакцией", ret=True)
    s.alt_end(f3)
    s.alt_end(f2)
    s.alt_end(f1)
    s.alt_end(f0)
    return s.finish()


def main():
    OUT.mkdir(exist_ok=True)
    cal0 = base_calendar()
    plan0, _ = best_schedule(cal0)
    cal1 = calendar_with_r4_repair()
    plan1, _ = best_schedule(cal1, plan0)
    pages = [
        ("01_gantt_S0", lambda: gantt("Gantt S0", "Диаграмма Ганта 1: исходное расписание, последняя работа "
                                      f"заканчивается в {hhmm(makespan(plan0))}", cal0, plan0)),
        ("02_gantt_S1", lambda: gantt("Gantt S1", "Диаграмма Ганта 2: расписание после ремонта R4 [11:30, 12:30), "
                                      f"последняя работа заканчивается в {hhmm(makespan(plan1))}", cal1, plan1)),
        ("03_er_model", er),
        ("04_sequence_approval", sequence),
    ]
    canvases = []
    for name, fn in pages:
        canvas = fn()
        canvases.append(canvas)
        canvas.to_png(str(OUT / f"{name}.png"))
        print("png", name, canvas.w, "x", canvas.h)
    (OUT / "allocation_model.drawio").write_text(drawio_file(canvases), encoding="utf-8")


if __name__ == "__main__":
    main()
