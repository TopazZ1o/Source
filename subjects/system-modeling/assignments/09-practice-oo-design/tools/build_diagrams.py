"""Builds the four UML diagrams of the report.

Run (Python 3.11 with Pillow; Arial fonts from C:/Windows/Fonts):
    python tools/build_diagrams.py [page numbers]

Output: assets/uml_model.drawio (editable, one page per diagram) and assets/NN_name.png (2x scale).
The diagram titles are in Kazakh and English as the task requires.
"""

import pathlib
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(pathlib.Path(__file__).parent))

from diagram_lib import Canvas, drawio_file, text_width, wrap_lines  # noqa: E402

OUT = pathlib.Path(__file__).resolve().parent.parent / "assets"


def title(c: Canvas, text: str, width: int) -> None:
    c.label(10, 6, width, 22, text, size=14, bold=True, align="left")


# ------------------------------------------------------------------------------------ 1. use case

def d1_use_case() -> Canvas:
    c = Canvas("1. Қолдану нұсқалары диаграммасы – Use Case Diagram", 900, 640)
    title(c, "Қолдану нұсқалары диаграммасы – Use Case Diagram", 860)
    c.rect(120, 40, 700, 590, "", stroke="#666666")
    c.label(135, 46, 660, 20, "Система «Заявки о неисправности ВС» (авиатехническая база аэропорта)",
            bold=True, align="left", size=12)

    applicant = c.actor(40, 150, "Заявитель")
    disp = c.actor(850, 190, "Диспетчер ТО")
    tech = c.actor(850, 430, "Специалист")

    def uc(x, y, text, w=270):
        return c.ellipse(x, y, w, 46, text, size=11)

    L, R = 140, 540
    u01 = uc(L, 90, "UC-01 Создать заявку")
    u02 = uc(L, 150, "UC-02 Добавить рабочий пункт")
    u03 = uc(L, 210, "UC-03 Отправить заявку")
    u04 = uc(L, 270, "UC-04 Отменить заявку")
    u11 = uc(R, 76, "UC-11 Проверить компетенцию\nи нагрузку специалиста")
    u05 = uc(R, 160, "UC-05 Назначить специалиста")
    u06 = uc(R, 240, "UC-06 Просмотреть нагрузку\nспециалистов")
    u10 = uc(R, 330, "UC-10 Просмотреть историю заявки")
    u07 = uc(R, 410, "UC-07 Начать работу")
    u08 = uc(R, 470, "UC-08 Отметить выполнение пункта")
    u09 = uc(R, 530, "UC-09 Завершить заявку")

    ap = (70, 180)
    for u in (u01, u02, u03, u04):
        c.line([ap, u.pt("l")])
    c.line([(55, 245), (55, 353), u10.pt("l")])       # applicant -> history, below the left column
    for u in (u05, u06, u10):
        c.line([(850, 220), u.pt("r")])
    for u in (u10, u07, u08, u09):
        c.line([(850, 460), u.pt("r")])

    # include: assignment always checks competence and load
    c.line([u05.pt("t"), u11.pt("b")], end="open", dashed=True)
    c.label(u05.cx + 8, 128, 80, 16, "«include»", size=10, italic=True, align="left")
    # extend: the dispatcher may look at the load before assigning
    c.line([u06.pt("t"), u05.pt("b")], end="open", dashed=True)
    c.label(u06.cx + 8, 209, 80, 16, "«extend»", size=10, italic=True, align="left")
    c.note(140, 395, 270, 120,
           "«include»: компетенция и нагрузка проверяются при каждом назначении (BR-03), "
           "поэтому это обязательная часть UC-05.\n"
           "«extend»: диспетчер может посмотреть нагрузку до выбора специалиста; "
           "без просмотра назначение возможно – поведение необязательное.", size=10)
    return c.fit()


# ------------------------------------------------------------------------------------ 2. class

# ------------------------------------------------------------------------------------ 2. class

def d2_class() -> Canvas:
    c = Canvas("2. Кластар диаграммасы – Class Diagram", 900, 1000)
    title(c, "Кластар диаграммасы – Class Diagram", 860)
    S = 10
    A, AW, B, BW, CX, CW = 10, 215, 270, 320, 650, 300
    BR = B + BW

    def tag(x, y, text, w=26, **kw):
        c.label(x - w / 2, y, w, 14, text, size=10, **kw)

    # ---- row 1: users, request, items and history
    usr = c.class_box(A, 40, AW, "User", ["+id: str {id}", "+name: str", "+role: Role"], None, size=S,
                      stereotype="immutable")
    tch = c.class_box(A, usr.y + usr.h + 80, AW, "Technician", [
        "-code: str {id}", "-user: User", "-categories: frozenset[Category]", "+MAX_ACTIVE_REQUESTS: int = 2",
    ], ["+can_serve(category: Category): bool", "+has_capacity(active_load: int): bool"], size=S)
    req = c.class_box(B, 40, BW, "ServiceRequest", [
        "-code: str {id}", "-owner: User", "-category: Category", "-priority: Priority", "-aircraft: str",
        "-title: str", "-created_at: datetime", "-due_at: datetime", "-status: Status",
        "-technician: Technician [0..1]", "-items: list[WorkItem]", "-history: list[StatusHistoryEntry]",
    ], [
        "+add_item(actor: User, description: str): WorkItem",
        "+submit(actor: User, at: datetime): None",
        "+cancel(actor: User, at: datetime): None",
        "+assign(actor: User, technician: Technician, active_load: int, at: datetime): None",
        "+start(actor: User, at: datetime): None",
        "+complete_item(actor: User, item_code: str): WorkItem",
        "+complete(actor: User, at: datetime): None",
        "+involves(user: User): bool",
        "+status, technician, due_at: read-only properties",
        "+items: tuple[WorkItem], history: tuple[StatusHistoryEntry]",
        "-_next_status(event: Event): Status",
        "-_move(target: Status, actor: User, at: datetime): None",
    ], size=S)
    wi = c.class_box(CX, 90, CW, "WorkItem", ["+code: str {id}", "+request_code: str", "+description: str",
                                               "+done: bool"], None, size=S, stereotype="immutable")
    hi = c.class_box(CX, wi.y + wi.h + 60, CW, "StatusHistoryEntry", [
        "+request_code: str", "+from_status: Status [0..1]", "+to_status: Status", "+actor_id: str", "+at: datetime",
    ], None, size=S, stereotype="immutable")

    # ---- row 2: interface, service, SLA policies
    rb = req.y + req.h
    y2 = max(rb, tch.y + tch.h, hi.y + hi.h) + 60
    ui = c.class_box(A, y2, AW, "ConsoleUI", ["-service: RequestService"], [
        "+assign(actor_id, request_code, technician_code): ...", "+submit(actor_id, request_code): ...",
        "+show_history(actor_id, request_code): None", "+show_requests(): None",
    ], size=S, header="#e1d5e7")
    svc = c.class_box(B, y2, BW, "RequestService", [
        "-requests: RequestRepository", "-directory: UserDirectory",
        "-policies: Mapping[Priority, SlaPolicy]", "-clock: Callable[[], datetime]",
    ], [
        "+create_request(actor_id: str, category: Category, priority: Priority, aircraft: str, title: str): ServiceRequest",
        "+add_item(actor_id: str, request_code: str, description: str): WorkItem",
        "+submit(actor_id: str, request_code: str): ServiceRequest",
        "+cancel(actor_id: str, request_code: str): ServiceRequest",
        "+assign_technician(actor_id: str, request_code: str, technician_code: str): ServiceRequest",
        "+start_work(actor_id: str, request_code: str): ServiceRequest",
        "+complete_item(actor_id: str, request_code: str, item_code: str): WorkItem",
        "+complete(actor_id: str, request_code: str): ServiceRequest",
        "+view_history(actor_id: str, request_code: str): tuple[StatusHistoryEntry]",
        "+get_active_load(actor_id: str, technician_code: str): int",
    ], size=S, header="#d5e8d4")
    pol = c.class_box(CX, y2, CW, "SlaPolicy", None, ["+calculate_due_at(created_at: datetime): datetime"],
                      size=S, stereotype="abstract (ABC)", header="#fff2cc", italic_name=True)
    std = c.class_box(CX, pol.y + pol.h + 55, 147, "StandardSlaPolicy", ["+HOURS: int = 24"],
                      ["+calculate_due_at(created_at): datetime"], size=9)
    urg = c.class_box(CX + 153, pol.y + pol.h + 55, 147, "UrgentSlaPolicy", ["+HOURS: int = 4"],
                      ["+calculate_due_at(created_at): datetime"], size=9)

    # ---- row 3: storage contracts and errors
    y3 = max(svc.y + svc.h, std.y + std.h, ui.y + ui.h) + 60
    ud = c.class_box(A, y3, AW, "UserDirectory", None, [
        "+add_user(user: User): None", "+get_user(user_id: str): User [0..1]",
        "+add_technician(t: Technician): None", "+get_technician(code: str): Technician [0..1]",
        "+find_technician_by_user(user_id: str): Technician [0..1]",
    ], size=S, stereotype="abstract (ABC)", header="#fff2cc", italic_name=True)
    udm = c.class_box(A, ud.y + ud.h + 45, AW, "InMemoryUserDirectory", ["-users, -technicians: dict"], None, size=9)
    rr = c.class_box(B, y3, BW, "RequestRepository", None, [
        "+next_code(): str", "+add(request: ServiceRequest): None", "+get(code: str): ServiceRequest [0..1]",
        "+save(request: ServiceRequest): None",
        "+find_by_technician(technician_code: str, statuses: Collection[Status]): list[ServiceRequest]",
        "+list_all(): list[ServiceRequest]",
    ], size=S, stereotype="abstract (ABC)", header="#fff2cc", italic_name=True)
    mem = c.class_box(B, rr.y + rr.h + 45, 155, "InMemoryRequestRepository", ["-items: dict[str, ServiceRequest]"],
                      None, size=9)
    cpy = c.class_box(B + 165, rr.y + rr.h + 45, 155, "CopyOnSaveRequestRepository",
                      ["-items: dict[str, ServiceRequest]", "(stores and returns copies)"], None, size=9)
    err = c.class_box(CX, y3, CW, "DomainError", ["+code: ErrorCode", "+message: str"], None, size=S,
                      stereotype="Exception", header="#f8cecc")
    c.note(CX, err.y + err.h + 15, CW, 95,
           "ErrorCode: EMPTY_ITEMS, FORBIDDEN, INVALID_STATE, SKILL_MISMATCH, LOAD_LIMIT, WORK_INCOMPLETE, "
           "NOT_FOUND, INVALID_INPUT, INVALID_PROFILE. Enums: Role, Category, Priority, Status, Event.", size=9)

    # ---- associations (row 1)
    y = usr.y + 30
    c.line([(A + AW, y), (B, y)])
    tag(A + AW + 8, y - 16, "1")
    tag(B - 14, y + 2, "0..*", 28)
    c.label(A + AW + 2, y + 16, 45, 13, "owner", size=9, italic=True)
    c.line([(usr.cx, usr.y + usr.h), (usr.cx, tch.y)])
    tag(usr.cx + 14, usr.y + usr.h + 2, "1")
    tag(usr.cx + 20, tch.y - 16, "0..1", 28)
    c.label(usr.cx - 50, usr.y + usr.h + 30, 46, 13, "profile", size=9, italic=True)
    y = tch.y + 30
    c.line([(A + AW, y), (B, y)])
    tag(A + AW + 14, y - 16, "0..1", 28)
    tag(B - 14, y + 2, "0..*", 28)
    c.label(A + AW + 1, y + 16, 48, 13, "assigned", size=9, italic=True)
    # compositions
    for target, mu in ((wi, "0..*"), (hi, "1..*")):
        y = target.y + 30
        c.line([(BR, y), (CX, y)], start="diamond")
        tag(BR + 12, y - 16, "1")
        tag(CX - 16, y - 16, mu, 30)
    c.label(CX, wi.y - 20, CW, 14, "{если состояние ≠ DRAFT, пунктов ≥ 1}", size=9, italic=True, align="left")

    # ---- dependencies (rows 2 and 3)
    c.line([(A + AW, ui.y + 30), (B, ui.y + 30)], end="open", dashed=True)
    c.line([(430, svc.y), (430, rb)], end="open", dashed=True)                       # service -> request
    c.line([(BR, svc.y + 30), (CX, pol.y + 30)], end="open", dashed=True)           # service -> contract
    c.label(BR + 8, svc.y + 12, 50, 13, "uses", size=9, italic=True)
    c.line([(560, rb), (560, rb + 28), (CX + 40, rb + 28), (CX + 40, pol.y)], end="open", dashed=True)
    c.label(570, rb + 12, 80, 13, "due_at", size=9, italic=True, align="left")        # request -> contract
    c.line([(B, svc.y + svc.h - 20), (247, svc.y + svc.h - 20), (247, ud.y + 20), (A + AW, ud.y + 20)],
           end="open", dashed=True)
    c.line([(430, svc.y + svc.h), (430, rr.y)], end="open", dashed=True)

    # realizations (hollow triangle at the contract)
    def realize(impl, base, gap):
        c.line([(impl.cx, impl.y), (impl.cx, base.y + base.h + gap),
                (base.cx, base.y + base.h + gap), (base.cx, base.y + base.h)], end="hollow", dashed=True)
    realize(std, pol, 25)
    realize(urg, pol, 25)
    realize(mem, rr, 22)
    realize(cpy, rr, 22)
    c.line([(udm.cx, udm.y), (udm.cx, ud.y + ud.h)], end="hollow", dashed=True)
    return c.fit()


# ------------------------------------------------------------------------------------ 3. sequence

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


def d3_sequence() -> Canvas:
    s = Seq("3. Тізбектілік диаграммасы – Sequence Diagram",
            ["@Диспетчер (U03)", ":ConsoleUI", ":RequestService", ":UserDirectory", ":RequestRepository",
             "sr: ServiceRequest"], step=128, x0=76)
    D, UI, SV, UD, RR, SR = range(6)
    s.c.label(10, 6, 860, 22, "Тізбектілік диаграммасы – Sequence Diagram: назначение специалиста (UC-05)",
              size=14, bold=True, align="left")
    s.msg(D, UI, "assign(\"U03\", \"SR01\", \"T01\")")
    s.msg(UI, SV, "assign_technician(actor_id, request_code, technician_code)")
    s.msg(SV, UD, "get_user(actor_id)")
    s.msg(UD, SV, "actor: User", ret=True)
    f1 = s.alt_begin()
    s.operand(f1, "нет права: actor.role ≠ DISPATCHER")
    s.msg(SV, UI, "raise DomainError(FORBIDDEN)", ret=True)
    s.msg(UI, D, "ОТКАЗ [FORBIDDEN]", ret=True)
    s.operand(f1, "иначе")
    s.msg(SV, RR, "get(request_code)")
    s.msg(RR, SV, "sr", ret=True)
    s.msg(SV, UD, "get_technician(technician_code)")
    s.msg(UD, SV, "technician: Technician", ret=True)
    s.msg(SV, RR, "find_by_technician(technician_code, ACTIVE_STATUSES)")
    s.msg(RR, SV, "active_requests → active_load = len(...)", ret=True)
    s.msg(SV, SR, "assign(actor, technician, active_load, at)")
    f2 = s.alt_begin(inset=10)
    s.operand(f2, "состояние sr ≠ SUBMITTED")
    s.msg(SR, UI, "raise DomainError(INVALID_STATE): save не вызывается", ret=True)
    s.operand(f2, "категория не подходит: not technician.can_serve(category)")
    s.msg(SR, UI, "raise DomainError(SKILL_MISMATCH): save не вызывается", ret=True)
    s.operand(f2, "предел нагрузки: not technician.has_capacity(active_load)")
    s.msg(SR, UI, "raise DomainError(LOAD_LIMIT): save не вызывается", ret=True)
    s.operand(f2, "успех: все проверки пройдены")
    s.self_msg(SR, "_move(ASSIGNED, actor, at)")
    s.msg(SR, SV, "None", ret=True)
    s.msg(SV, RR, "save(sr)")
    s.msg(SV, UI, "sr (ASSIGNED)", ret=True)
    s.msg(UI, D, "OK: SR01 → ASSIGNED", ret=True)
    s.alt_end(f2)
    s.alt_end(f1)
    return s.finish()


# ------------------------------------------------------------------------------------ 4. state

def d4_state() -> Canvas:
    c = Canvas("4. Күйлер диаграммасы – State Machine Diagram", 900, 560)
    title(c, "Күйлер диаграммасы – State Machine Diagram: ServiceRequest", 860)

    def state(x, y, w, h, name, fill="#ffffff", inner=""):
        text = name + (("\n" + inner) if inner else "")
        return c.rect(x, y, w, h, text, rounded=18, fill=fill, bold=False, size=12)

    draft = state(40, 140, 130, 56, "DRAFT")
    subm = state(300, 140, 130, 56, "SUBMITTED")
    asg = state(560, 140, 130, 56, "ASSIGNED")
    prog = state(560, 330, 170, 90, "IN_PROGRESS", inner="внутреннее: complete_item\n[назначенный специалист]\n/ пункт отмечен")
    done = state(300, 440, 140, 56, "COMPLETED", fill="#d5e8d4")
    canc = state(40, 440, 140, 56, "CANCELLED", fill="#f8cecc")
    init = c.circle(20, 168, 8)
    f1 = c.circle(190, 540, 9, final=True)
    f2 = c.circle(470, 540, 9, final=True)

    def lab(x, y, w, text):
        c.label(x, y, w, 13 * len(wrap_lines(text, w, 10)), text, size=10, align="left", bg=True)

    c.line([init.pt("r"), draft.pt("l")], end="open")
    lab(8, 100, 140, "создание заявки / запись DRAFT в историю")
    c.line([draft.pt("r"), subm.pt("l")], end="open")
    lab(176, 100, 120, "submit\n[владелец; пунктов ≥ 1]\n/ запись в историю")
    c.line([subm.pt("r"), asg.pt("l")], end="open")
    lab(436, 92, 122, "assign\n[диспетчер; категория подходит; нагрузка < 2]\n/ назначить, нагрузка +1")
    c.line([asg.pt("b"), (625, 330)], end="open")
    lab(632, 225, 110, "start\n[назначенный специалист]")
    c.line([(560, 375), (370, 375), (370, 440)], end="open")
    lab(385, 322, 165, "complete\n[тот же специалист; все пункты выполнены]\n/ нагрузка −1")
    c.line([(105, 196), (105, 440)], end="open")
    lab(12, 300, 85, "cancel\n[владелец]")
    c.line([(365, 196), (365, 215), (150, 215), (150, 440)], end="open")
    lab(165, 222, 150, "cancel [владелец]")
    c.line([(110, 496), (110, 540), (181, 540)], end="open")
    c.line([(370, 496), (370, 540), (461, 540)], end="open")
    c.note(560, 450, 320, 90,
           "Переходы, не вошедшие в таблицу задания, не принимаются (INVALID_STATE). "
           "COMPLETED и CANCELLED – конечные состояния. Нагрузка специалиста – число заявок "
           "в ASSIGNED и IN_PROGRESS: растёт при assign, уменьшается при complete.", size=10)
    return c.fit()


PAGES = [("01_use_case", d1_use_case), ("02_class", d2_class), ("03_sequence_assign", d3_sequence),
         ("04_state_machine", d4_state)]


def main(selected):
    OUT.mkdir(exist_ok=True)
    canvases = []
    for i, (name, fn) in enumerate(PAGES, 1):
        canvas = fn()
        canvases.append(canvas)
        if not selected or i in selected:
            canvas.to_png(str(OUT / f"{name}.png"))
            print("png", name, canvas.w, "x", canvas.h)
    (OUT / "uml_model.drawio").write_text(drawio_file(canvases), encoding="utf-8")
    print("drawio pages:", len(canvases))


if __name__ == "__main__":
    main({int(a) for a in sys.argv[1:]})
