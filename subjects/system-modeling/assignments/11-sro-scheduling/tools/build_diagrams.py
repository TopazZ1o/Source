"""Builds the figures of the report: three Gantt charts (S0-S2) and the ER diagram.

    python tools/build_diagrams.py

Output: assets/scheduling_model.drawio (editable, diagrams.net, one page per figure)
and assets/NN_name.png. Plans come from prototype/scheduling.py (single source of truth).
"""

import pathlib
import sys

sys.stdout.reconfigure(encoding="utf-8")
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "prototype"))

from diagram_lib import Canvas, drawio_file  # noqa: E402
from scheduling import N_SLOTS, RESOURCES, hhmm, make_scenario, optimise  # noqa: E402

OUT = HERE.parent / "assets"

LEFT, TOP, CELL, ROW = 70, 70, 56, 52
FILL = {True: "#dae8fc", False: "#d5e8d4"}


def gantt(code: str) -> Canvas:
    sc = make_scenario(code)
    plan = optimise(sc)
    c = Canvas(f"Gantt {code}", 1000, 400)
    c.label(10, 6, 960, 22, f"Диаграмма Ганта оптимального плана {code}: {sc.title} "
            f"(затраты {plan.run_cost()}, штрафы {plan.penalty()}, итого {plan.total()} тыс. тенге)",
            size=13, bold=True, align="left")
    # time axis
    for t in range(N_SLOTS + 1):
        x = LEFT + t * CELL
        c.line([(x, TOP - 6), (x, TOP + ROW * 3)], color="#999999" if t % 2 else "#666666")
        if t % 2 == 0:
            c.label(x - 22, TOP - 28, 44, 18, hhmm(t), size=10)
    for i, r in enumerate(RESOURCES):
        y = TOP + i * ROW
        c.label(10, y, 50, ROW, r, size=13, bold=True)
        c.rect(LEFT, y, N_SLOTS * CELL, ROW, "", stroke="#666666")
        # unavailable slots
        run = [t for t in range(N_SLOTS) if not sc.free(r, t)]
        groups = []
        for t in run:
            if groups and groups[-1][-1] == t - 1:
                groups[-1].append(t)
            else:
                groups.append([t])
        for g in groups:
            c.rect(LEFT + g[0] * CELL, y, len(g) * CELL, ROW,
                   "недоступна\n" + f"{hhmm(g[0])}-{hhmm(g[-1] + 1)}" if len(g) > 1 else "нед.",
                   fill="#e0e0e0", stroke="#999999", size=9, font_color="#555555")
    for j in sc.jobs:
        if j.code not in plan.assign:
            continue
        r, s = plan.assign[j.code]
        y = TOP + RESOURCES.index(r) * ROW
        fill = "#f8cecc" if j.code == "J7" else FILL[j.mandatory]
        c.rect(LEFT + s * CELL + 1, y + 4, j.dur * CELL - 2, ROW - 8,
               f"{j.code} {j.name}\n{hhmm(s)}-{hhmm(s + j.dur)}, {j.cost[r]}", fill=fill, size=9, sw=1.5)
    y = TOP + 3 * ROW + 14
    postponed = [j for j in sc.jobs if j.code not in plan.assign]
    text = ("Перенесены: " + "; ".join(f"{j.code} {j.name} (штраф {j.penalty})" for j in postponed)
            if postponed else "Перенесённых заявок нет.")
    c.label(10, y, 960, 18, text, size=11, align="left")
    lx = 10
    for fill, name in (("#dae8fc", "обязательная"), ("#d5e8d4", "необязательная"),
                       ("#f8cecc", "срочная J7"), ("#e0e0e0", "бригада недоступна")):
        c.rect(lx, y + 26, 22, 14, "", fill=fill)
        c.label(lx + 26, y + 24, 130, 18, name, size=10, align="left")
        lx += 170
    c.label(lx, y + 24, 300, 18, "в блоке: затраты, тыс. тенге", size=10, align="left", italic=True)
    return c.fit()


def er() -> Canvas:
    c = Canvas("ER-модель", 900, 900)
    c.label(10, 6, 880, 22, "ER-модель данных системы распределения работ", size=14, bold=True, align="left")
    S, W = 10, 280
    A, B, C = 10, 340, 670

    def table(x, y, name, attrs, header="#dae8fc"):
        return c.class_box(x, y, W, name, attrs, None, size=S, header=header)

    av = table(C, 40, "interval_availability (Интервал доступности)", [
        "PK  id", "FK  resource_id", "start_at, end_at  (интервал [start, end))",
        "kind  AVAILABLE | UNAVAILABLE", "reason  (поломка, ТО, график)", "calendar_version"], header="#fff2cc")
    y1 = av.y + av.h + 50
    plan = table(A, y1, "plan (План)", [
        "PK  id", "scenario  (S0 | S1 | S2)", "method  GREEDY | OPTIMAL", "calendar_version  (снимок на момент расчёта)",
        "status  DRAFT | CHECKED | APPROVED | OBSOLETE", "run_cost, penalty, total", "created_at, approved_at"],
        header="#d5e8d4")
    asg = table(B, y1, "assignment (Назначение)", [
        "PK  id", "FK  plan_id", "FK  request_id", "FK  resource_id  (NULL при переносе)",
        "start_at, end_at  (NULL при переносе)", "run_cost  ≥ 0, penalty  ≥ 0",
        "status  SCHEDULED | POSTPONED", "reason  (причина переноса)",
        "UNIQUE (plan_id, request_id)"], header="#d5e8d4")
    res = table(C, y1, "resource (Ресурс)", ["PK  id  (R1, R2, R3)", "name  (бригада)", "shift_start, shift_end"])
    y2 = max(plan.y + plan.h, asg.y + asg.h, res.y + res.h) + 50
    req = table(B, y2, "request (Заявка)", [
        "PK  id  (J1 … J7)", "name", "window_start, window_end", "duration_min  > 0",
        "mandatory  BOOLEAN", "postpone_penalty  ≥ 0  (0 при mandatory)",
        "CHECK window_end − window_start ≥ duration"])
    rr = table(C, y2, "request_resource (Совместимость)", [
        "PK, FK  request_id", "PK, FK  resource_id", "run_cost  > 0  (тыс. тенге)"], header="#ffe6cc")
    c.note(A, y2, W, 150,
           "Правила целостности:\n• назначение в одном плане: интервалы одной бригады не пересекаются "
           "(проверка при сохранении);\n• пара (request_id, resource_id) назначения обязана быть в request_resource;\n"
           "• интервал назначения лежит в окне заявки и вне UNAVAILABLE;\n• обязательная заявка (mandatory) всегда имеет status = SCHEDULED.", size=9)

    def tag(x, y, text, w=34):
        c.label(x - w / 2, y, w, 14, text, size=10)

    # plan 1 -- 1..* assignment
    ya = y1 + 30
    c.line([(A + W, ya), (B, ya)])
    tag(A + W + 14, ya - 16, "1")
    tag(B - 20, ya - 16, "1..*")
    # assignment 0..* -- 1 resource
    c.line([(B + W, ya), (C, ya)])
    tag(B + W + 20, ya - 16, "0..*")
    tag(C - 12, ya - 16, "1")
    # resource 1 -- 0..* availability
    c.line([(res.cx, res.y), (res.cx, av.y + av.h)])
    tag(res.cx + 14, res.y - 16, "1")
    tag(res.cx + 20, av.y + av.h + 2, "0..*")
    # request 1 -- 0..* assignment
    c.line([(req.cx, req.y), (req.cx, asg.y + asg.h)])
    tag(req.cx + 14, req.y - 16, "1")
    tag(req.cx + 20, asg.y + asg.h + 2, "0..*")
    # request 1 -- 1..* request_resource ; resource 1 -- 0..* request_resource
    yr = req.y + 30
    c.line([(B + W, yr), (C, yr)])
    tag(B + W + 14, yr - 16, "1")
    tag(C - 20, yr - 16, "1..*")
    c.line([(C + W + 14, res.y + res.h), (C + W + 14, rr.y + 12), (C + W, rr.y + 12)])
    tag(C + W + 30, res.y + res.h + 2, "1")
    tag(C + W + 36, rr.y - 10, "0..*")
    return c.fit()


PAGES = [("01_gantt_S0", lambda: gantt("S0")), ("02_gantt_S1", lambda: gantt("S1")),
         ("03_gantt_S2", lambda: gantt("S2")), ("04_er_model", er)]


def main():
    OUT.mkdir(exist_ok=True)
    canvases = []
    for name, fn in PAGES:
        canvas = fn()
        canvases.append(canvas)
        canvas.to_png(str(OUT / f"{name}.png"))
        print("png", name, canvas.w, "x", canvas.h)
    (OUT / "scheduling_model.drawio").write_text(drawio_file(canvases), encoding="utf-8")


if __name__ == "__main__":
    main()
