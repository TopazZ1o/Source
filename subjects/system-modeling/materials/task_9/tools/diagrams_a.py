"""Diagrams 1-4: use cases, conceptual model, design class diagrams (domain; services and interfaces)."""

import math

from diagram_lib import Canvas
from model_data import DOMAIN, ENUMS, IMPLEMENTATIONS, INTERFACES, SERVICES


def mult(c: Canvas, p, q, text, *, flip=False, dist=14, off=11, size=11):
    """Multiplicity label near the end p of a line whose next point is q (above / right of the line)."""
    dx, dy = q[0] - p[0], q[1] - p[1]
    n = math.hypot(dx, dy) or 1
    ux, uy = dx / n, dy / n
    nx, ny = -uy, ux
    if abs(ny) > abs(nx):
        if ny > 0:
            nx, ny = -nx, -ny
    elif nx < 0:
        nx, ny = -nx, -ny
    if flip:
        nx, ny = -nx, -ny
    w = max(22, 7 * len(text))
    dist = max(dist, w / 2 + 5) if abs(ux) > abs(uy) else dist
    off = max(off, w / 2 + 4) if abs(nx) > abs(ny) else off
    c.label(p[0] + ux * dist + nx * off - w / 2, p[1] + uy * dist + ny * off - 8, w, 16, text, size=size)


def assoc(c, pts, ma="", mb="", role="", role_at=None, role_w=120, **kw):
    """Association line with multiplicities at both ends and an optional role label."""
    c.line(pts, **kw)
    if ma:
        mult(c, pts[0], pts[1], ma)
    if mb:
        mult(c, pts[-1], pts[-2], mb)
    if role:
        x, y = role_at
        c.label(x - role_w / 2, y - 8, role_w, 16, role, size=10, italic=True, bg=True)


# ------------------------------------------------------------------------------------ 1. use cases

def d01_use_case() -> Canvas:
    c = Canvas("1. Диаграмма вариантов использования", 1180, 830)
    c.rect(170, 20, 820, 795, "", stroke="#666666")
    c.label(190, 26, 700, 22, "Система «ТОиР ВС»: техническое обслуживание и ремонт воздушных судов",
            bold=True, align="left")
    planner = c.actor(60, 170, "Планировщик")
    tech = c.actor(60, 520, "Техник")
    chief = c.actor(1060, 360, "Руководитель\nтехслужбы /\nинспектор")
    admin = c.actor(1060, 650, "Администратор")
    ext = c.actor(1060, 50, "Система учёта ВС\nавиакомпании")

    def uc(x, y, text, w=250, h=50):
        return c.ellipse(x, y, w, h, text, size=11)

    A, B = 235, 650
    u01 = uc(A, 70, "UC-01 Вести реестр ВС")
    u02 = uc(A, 150, "UC-02 Записать ВС на обслуживание")
    u03 = uc(A, 230, "UC-03 Назначить ресурсы")
    u13 = uc(A, 330, "UC-13 Перевести заявку в ожидание ресурсов")
    u10 = uc(A, 420, "UC-10 Контролировать сроки")
    u04 = uc(A, 510, "UC-04 Вести заказ-наряд и этапы")
    u05 = uc(A, 610, "UC-05 Зафиксировать дефект и запчасти")
    u11 = uc(380, 725, "UC-11 Просматривать историю и отчёты", w=300)
    u06 = uc(B, 250, "UC-06 Подтвердить техническую годность", w=270)
    u07 = uc(B, 340, "UC-07 Допустить ВС к эксплуатации", w=270)
    u08 = uc(B, 435, "UC-08 Проверить готовность к допуску", w=270)
    u09 = uc(B, 530, "UC-09 Оформить списание ВС", w=270)
    u12 = uc(B, 650, "UC-12 Управлять пользователями и ролями", w=270)

    pr = (planner.x + 30, planner.y + 30)
    for u in (u01, u02, u03, u10):
        c.line([pr, u.pt("l")])
    c.line([pr, (210, 330), (210, 750), u11.pt("l")])
    tr = (tech.x + 30, tech.y + 30)
    for u in (u04, u05):
        c.line([tr, u.pt("l")])
    c.line([tr, (210, 700), (210, 750)])
    cr = (chief.x, chief.y + 30)
    for u in (u06, u07, u09):
        c.line([cr, u.pt("r")])
    c.line([(chief.x, chief.y + 45), (1020, chief.y + 45), (1020, 800), (530, 800), u11.pt("b")])
    c.line([(admin.x, admin.y + 30), u12.pt("r")])
    c.line([(ext.x, ext.y + 30), (ext.x - 40, ext.y + 30), (ext.x - 40, u01.cy), u01.pt("r")])

    def rel(a, b, kind, note, w=230):
        c.line([a.pt("t", .5), b.pt("b", .5)], end="open", dashed=True)
        gap_mid = (a.y + b.y + b.h) / 2
        c.label(a.cx + 10, gap_mid - 20, w, 40, f"«{kind}»\n{note}".strip(), size=10, align="left")

    rel(u13, u03, "extend", "[ресурс занят]")
    rel(u05, u04, "extend", "[обнаружен дефект или расход запчасти]", 300)
    c.line([u07.pt("b", .5), u08.pt("t", .5)], end="open", dashed=True)
    c.label(u07.cx + 10, 396, 100, 16, "«include»", size=10, align="left")
    return c.fit()


# ------------------------------------------------------------------------------------ 2. conceptual

def concept_box(c, x, y, w, name, attrs, header="#dae8fc"):
    return c.class_box(x, y, w, name, attrs, (), header=header, size=11)


def d02_conceptual() -> Canvas:
    c = Canvas("2. Концептуальная модель предметной области", 1400, 960)
    emp = concept_box(c, 30, 70, 200, "Сотрудник", ["идСотрудника", "ФИО", "роль", "заблокирован"])
    req = concept_box(c, 350, 70, 230, "ЗаявкаНаОбслуживание",
                      ["тип (плановое / внеплановое)", "приоритет", "желаемаяДата", "описание", "статус"])
    ac = concept_box(c, 690, 70, 230, "ВоздушноеСудно",
                     ["бортовойНомер", "модель", "серийныйНомер", "датаВвода", "статус", "срокСледующегоТО"])
    wo = concept_box(c, 760, 340, 160, "ЗаказНаряд", ["статус"])
    asg = concept_box(c, 350, 340, 230, "Назначение", ["начало", "конец", "активно"])
    res = concept_box(c, 350, 570, 230, "РесурсОбслуживания",
                      ["вид (специалист / оборудование / место в ангаре)", "название", "квалификация", "доступен"])
    act = concept_box(c, 690, 570, 230, "АктСписания", ["основание", "реквизитыДокумента", "датаСписания"])
    st = concept_box(c, 1080, 70, 260, "ЭтапРабот", ["название", "обязательный", "статус", "результат"])
    df = concept_box(c, 1080, 230, 260, "Дефект", ["описание", "критичность", "статус"])
    cn = concept_box(c, 1080, 360, 260, "ЗаключениеОГодности", ["вердикт", "основание", "времяВыдачи"])
    pt = concept_box(c, 1080, 500, 260, "ЗапчастьВЗаказе", ["номерДетали", "количество"])
    jr = concept_box(c, 1080, 630, 260, "ЗаписьЖурнала", ["время", "действие", "объект", "результат"])

    # vehicle - request
    assoc(c, [(req.x + req.w, 120), (ac.x, 120)], "0..*", "1", "имеет заявки", (635, 104), 90)
    # request - work order
    ry = req.y + req.h - 12
    assoc(c, [(req.x + req.w, ry), (660, ry), (660, wo.y + 24), (wo.x, wo.y + 24)], "1", "0..1",
          "исполняется по", (660, 290), 100)
    # request - assignment, assignment - resource
    assoc(c, [(req.cx, req.y + req.h), (req.cx, asg.y)], "1", "0..*", "занимает", (req.cx + 36, 290), 64)
    assoc(c, [(asg.cx, asg.y + asg.h), (res.cx, res.y)], "0..*", "1", "на ресурс", (asg.cx + 38, 510), 64)
    # vehicle - write-off act
    assoc(c, [(712, ac.y + ac.h), (712, act.y)], "1", "0..1", "", None)
    c.label(722, 470, 80, 16, "списано актом", size=10, italic=True, bg=True)
    # work order - its parts
    parts = [(st, 350, 130, "1..*", "этапы", 950), (df, 358, 266, "0..*", "дефекты", 965),
             (cn, 366, 400, "0..*", "заключения", 1000), (pt, 374, 540, "0..*", "запчасти", 980)]
    for box, y0, ty, m, role, x in parts:
        c.line([(wo.x + wo.w, y0), (x, y0), (x, ty), (box.x, ty)])
        mult(c, (box.x, ty), (x, ty), m, dist=16, off=10)
        c.label(box.x - 86, ty + 3, 76, 14, role, size=10, italic=True, align="right")
    # employee links
    c.line([(emp.cx, emp.y), (emp.cx, 30), (st.cx, 30), (st.cx, st.y)])
    mult(c, (emp.cx, emp.y), (emp.cx, 30), "1", dist=14)
    mult(c, (st.cx, st.y), (st.cx, 30), "0..*", dist=14)
    c.label(560, 22, 160, 14, "исполнитель этапа", size=10, italic=True, bg=True)
    assoc(c, [(emp.x + emp.w, 120), (req.x, 120)], "1", "0..*", "автор", (290, 104), 50)
    # a specialist is an employee: resource - employee
    c.line([(emp.cx + 50, emp.y + emp.h), (emp.cx + 50, res.y + 40), (res.x, res.y + 40)])
    mult(c, (emp.cx + 50, emp.y + emp.h), (emp.cx + 50, res.y), "0..1", dist=16)
    mult(c, (res.x, res.y + 40), (emp.cx + 50, res.y + 40), "0..1", dist=16, off=10)
    c.label(emp.cx + 58, 400, 130, 30, "ресурс вида\n«специалист»", size=10, italic=True, align="left")
    # employee - conclusion, journal, act: bus along the bottom
    bus_y, bx = 905, emp.cx - 70
    for box, ty, role in ((cn, cn.y + 28, "автор"), (jr, jr.y + 28, "пользователь")):
        right = box.x + box.w + 30
        pts = [(bx, emp.y + emp.h), (bx, bus_y), (right, bus_y), (right, ty), (box.x + box.w, ty)]
        c.line(pts)
        mult(c, pts[-1], pts[-2], "0..*", dist=16, off=10)
        c.label(right + 4, ty - 10, 70, 14, role, size=10, italic=True, align="left")
    pts = [(bx, emp.y + emp.h), (bx, bus_y), (act.x + act.w - 40, bus_y), (act.x + act.w - 40, act.y + act.h)]
    c.line(pts)
    mult(c, pts[-1], pts[-2], "0..*", dist=16, off=10)
    c.label(act.x + act.w - 34, act.y + act.h + 24, 80, 14, "утвердил", size=10, italic=True, align="left")
    mult(c, (bx, emp.y + emp.h), (bx, bus_y), "1", dist=14, off=10)
    # constraints
    c.note(350, 730, 500, 140,
           "Ограничения предметной области\n"
           "1. У ВС не более одной активной заявки.\n"
           "2. Активные назначения одного ресурса не пересекаются по времени.\n"
           "3. Допуск — только после завершения обязательных этапов, при отсутствии открытых критичных "
           "дефектов и при заключении «годно».\n"
           "4. Списанное ВС не планируется. 5. Заключение, акт списания и запись журнала не изменяются "
           "и не удаляются.\n"
           "6. Статус ВС меняется только по допустимым переходам (рис. 9).", size=10)
    return c.fit()


# ------------------------------------------------------------------------------------ 3. design: domain

def build_class(c, x, y, w, name, spec, header="#dae8fc"):
    return c.class_box(x, y, w, name, spec["attrs"], spec["ops"], stereotype=spec.get("stereotype", ""),
                       header=header, size=11)


def d03_design_domain() -> Canvas:
    c = Canvas("3. Проектная модель классов: предметная область", 1900, 1330)
    cols = (20, 580, 1160)
    wv, wr, ww = 440, 440, 460
    ac = build_class(c, cols[0], 20, wv, "ВоздушноеСудно", DOMAIN["ВоздушноеСудно"])
    rq = build_class(c, cols[1], 20, wr, "ЗаявкаНаОбслуживание", DOMAIN["ЗаявкаНаОбслуживание"])
    wo = build_class(c, cols[2], 20, ww, "ЗаказНаряд", DOMAIN["ЗаказНаряд"])
    cx4, w4 = 1720, 240
    df = build_class(c, cx4, 20, w4, "Дефект", DOMAIN["Дефект"])
    cn = build_class(c, cx4, 150, w4, "ЗаключениеОГодности", DOMAIN["ЗаключениеОГодности"])
    pt = build_class(c, cx4, 340, w4, "ЗапчастьВЗаказе", DOMAIN["ЗапчастьВЗаказе"])
    row2 = max(ac.y + ac.h, rq.y + rq.h, wo.y + wo.h) + 70
    act = build_class(c, cols[0], row2, wv, "АктСписания", DOMAIN["АктСписания"])
    asg = build_class(c, cols[1], row2, wr, "Назначение", DOMAIN["Назначение"])
    st = build_class(c, cols[2], row2, ww, "ЭтапРабот", DOMAIN["ЭтапРабот"])
    emp = build_class(c, cx4, max(row2, pt.y + pt.h + 50), w4, "Сотрудник", DOMAIN["Сотрудник"])
    row3 = max(act.y + act.h, asg.y + asg.h, st.y + st.h) + 70
    jr = build_class(c, cols[0], row3, wv, "ЗаписьЖурнала", DOMAIN["ЗаписьЖурнала"])
    res = build_class(c, cols[1], row3, wr, "РесурсОбслуживания", DOMAIN["РесурсОбслуживания"])

    gx1, gx2 = (ac.x + ac.w + rq.x) / 2, (rq.x + rq.w + wo.x) / 2
    assoc(c, [(ac.x + ac.w, 90), (rq.x, 90)], "1", "0..*", "заявки", (gx1, 74), 50)
    assoc(c, [(rq.x + rq.w, 90), (wo.x, 90)], "1", "0..1", "заказ-наряд", (gx2, 74), 70)
    assoc(c, [(act.cx, ac.y + ac.h), (act.cx, act.y)], "1", "0..1", "списано",
          (act.cx + 40, (ac.y + ac.h + act.y) / 2), 60)
    assoc(c, [(asg.cx, rq.y + rq.h), (asg.cx, asg.y)], "1", "0..*", "назначения",
          (asg.cx + 48, (rq.y + rq.h + asg.y) / 2), 70)
    assoc(c, [(asg.cx, asg.y + asg.h), (res.cx, res.y)], "0..*", "1", "ресурс",
          (asg.cx + 36, (asg.y + asg.h + res.y) / 2), 60)
    # composition: work order - stages, defects, conclusions; association: parts
    pts = [(wo.cx, wo.y + wo.h), (wo.cx, st.y)]
    c.line(pts, start="diamond")
    mult(c, pts[1], pts[0], "1..*", dist=16, off=10)
    c.label(wo.cx + 40, (wo.y + wo.h + st.y) / 2 - 8, 60, 16, "этапы", size=10, italic=True, bg=True)
    right = wo.x + wo.w
    for box, y0, ty, role, kind in ((df, 70, 70, "дефекты", "comp"), (cn, 170, 200, "заключения", "comp"),
                                    (pt, 280, 370, "запчасти", "assoc")):
        mid_x = right + 40
        c.line([(right, y0), (mid_x, y0), (mid_x, ty), (box.x, ty)], start="diamond" if kind == "comp" else "none")
        mult(c, (box.x, ty), (mid_x, ty), "0..*", dist=18, off=10)
        mult(c, (right, y0), (mid_x, y0), "1", dist=26, off=10, size=10)
        c.label(right + 12, y0 + 4, 70, 14, role, size=10, italic=True, align="left")
    c.note(1160, row3, 800, 150,
           "Пояснения к модели\n"
           "• Закрашенный ромб (композиция) применён там, где часть не существует вне заказ-наряда и входит в проверку "
           "допуска BR-07: этапы, дефекты, заключения. Запчасти — учёт расхода, на допуск не влияют, поэтому обычная "
           "ассоциация.\n"
           "• Ссылки на Сотрудника (автор, исполнитель, утвердил, пользователь журнала) и ссылки между "
           "агрегатами хранятся идентификаторами (идСотрудника, идВС, идЗаявки); линиями они не показаны.\n"
           "• Наследование не использовано: различие ролей выражено перечислением Роль.", size=11)
    return c.fit()


# ------------------------------------------------------------------------------------ 4. design: services

def d04_design_services() -> Canvas:
    c = Canvas("4. Проектная модель классов: сервисы, интерфейсы, перечисления", 1920, 1700)
    gap = 30
    specs = [("СервисЗаказНарядов", 340), ("СервисПланирования", 460), ("СервисДопуска", 350),
             ("СервисСписания", 320), ("СервисКонтроляСроков", 280)]
    x = 20
    row1 = {}
    for name, w in specs:
        row1[name] = build_class(c, x, 40, w, name, SERVICES[name], header="#e1d5e7")
        x += w + gap
    r1b = max(b.y + b.h for b in row1.values())
    y2 = r1b + 110
    spec_stage = build_class(c, 20, y2, 330, "СпецификацияЭтапа", SERVICES["СпецификацияЭтапа"], header="#e1d5e7")
    val = build_class(c, 400, y2, 400, "ВалидаторЗаявки", SERVICES["ВалидаторЗаявки"], header="#e1d5e7")
    run = build_class(c, 850, y2, 600, "ВыполнительОпераций", SERVICES["ВыполнительОпераций"], header="#e1d5e7")
    pol = build_class(c, 1490, y2, 400, "ПолитикаДоступа", SERVICES["ПолитикаДоступа"], header="#e1d5e7")
    r2b = max(b.y + b.h for b in (spec_stage, val, run, pol))
    y3 = r2b + 100
    ifaces = {}
    ix = {"ХранилищеДанных": (20, 760), "КаналУведомления": (820, 520), "ЖурналАудита": (1380, 510)}
    for name, ops in INTERFACES.items():
        x0, w0 = ix[name]
        ifaces[name] = c.class_box(x0, y3, w0, name, (), ops, stereotype="interface", header="#d5e8d4", size=11)
    r3b = max(b.y + b.h for b in ifaces.values())
    y4 = r3b + 70
    impls = {}
    impl_pos = {"ХранилищеВПамяти": (20, 560), "УведомлениеВПриложении": (820, 250),
                "УведомлениеEmail": (1090, 250), "ЖурналВПамяти": (1380, 510)}
    for name, (iface, attrs, notes) in IMPLEMENTATIONS.items():
        x0, w0 = impl_pos[name]
        impls[name] = c.class_box(x0, y4, w0, name, attrs, notes, header="#fff2cc", size=11)
        tgt = ifaces[iface]
        sx = impls[name].cx
        tx = min(max(sx, tgt.x + 40), tgt.x + tgt.w - 40)
        c.line([(sx, y4), (sx, y4 - 25), (tx, y4 - 25), (tx, tgt.y + tgt.h)], end="hollow", dashed=True)
    for iname in ("ХранилищеДанных", "КаналУведомления", "ЖурналАудита"):
        t = ifaces[iname]
        sx = {"ХранилищеДанных": run.x + 90, "КаналУведомления": run.cx, "ЖурналАудита": run.x + run.w - 90}[iname]
        tx = {"ХранилищеДанных": t.x + t.w - 120, "КаналУведомления": t.cx, "ЖурналАудита": t.x + 80}[iname]
        c.line([(sx, run.y + run.h), (sx, run.y + run.h + 40), (tx, run.y + run.h + 40), (tx, t.y)], end="open",
               dashed=True)
    c.line([(run.x + run.w, run.y + 50), (pol.x, run.y + 50)], end="open", dashed=True)
    chan = r1b + 30
    for i, (name, box) in enumerate(row1.items()):
        sx = box.cx
        tx = run.x + 70 + i * 110
        c.line([(sx, box.y + box.h), (sx, chan + i * 12), (tx, chan + i * 12), (tx, run.y)], end="open")
    pl, dp, wr = row1["СервисПланирования"], row1["СервисДопуска"], row1["СервисСписания"]
    c.line([(dp.x, 200), (pl.x + pl.w, 200)], end="open", dashed=True)
    c.label(pl.x + pl.w + 2, 180, 26, 14, "", size=9)
    c.label(dp.x - 28, 168, 26, 28, "", size=9)
    c.line([(wr.x + 40, wr.y), (wr.x + 40, 18), (pl.x + 60, 18), (pl.x + 60, pl.y)], end="open", dashed=True)
    c.label(pl.x + 100, 2, 260, 14, "СервисСписания и СервисДопуска освобождают ресурсы", size=9, italic=True,
            align="left")
    c.line([(pl.x + 100, pl.y + pl.h), (pl.x + 100, y2 - 20), (val.x + 100, y2 - 20), (val.x + 100, val.y)],
           end="open", dashed=True)
    zn = row1["СервисЗаказНарядов"]
    c.line([(zn.x + 60, zn.y + zn.h), (zn.x + 60, y2)], end="open", dashed=True)
    y5 = y4 + max(b.h for b in impls.values()) + 60
    c.label(20, y5 - 4, 900, 18, "Перечисления (12)", bold=True, align="left")
    ex, ey, rowh = 20, y5 + 20, 0
    for name, vals in ENUMS.items():
        w0 = 295
        box = c.class_box(ex, ey, w0, name, vals, (), stereotype="enumeration", header="#ffe6cc", size=10)
        rowh = max(rowh, box.h)
        ex += w0 + 15
        if ex + w0 > 1900:
            ex, ey, rowh = 20, ey + rowh + 15, 0
    return c.fit()
