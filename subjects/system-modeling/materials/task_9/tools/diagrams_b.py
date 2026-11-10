"""Diagrams 5-7: sequence diagrams (create request UC-02, assign resources UC-03, release UC-07)."""

from diagram_lib import Canvas, text_width, wrap_lines

SZ = 10  # message font size


def wrap_lines_width(lines):
    return max(text_width(t, SZ) for t in lines) + 6


class Seq:
    """Sequence diagram builder: lifelines, numbered messages, alt fragments."""

    def __init__(self, name, participants, step=130, x0=75, width=None):
        self.c = Canvas(name, 100, 100)
        self.names = participants
        self.px = {i: x0 + step * i for i in range(len(participants))}
        self.step = step
        self.n = 0
        self.heads = []
        for i, title in enumerate(participants):
            actor = title.startswith("@")
            text = title[1:] if actor else ":" + title
            self.heads.append(self.c.rect(self.px[i] - step / 2 + 4, 16, step - 8, 40, text,
                                          fill="#fff2cc" if actor else "#dae8fc", bold=True, size=SZ, pad=2))
        self.y = 62
        self.left, self.right = self.px[0] - step / 2 + 4, self.px[len(participants) - 1] + step / 2 - 4

    # --- messages
    def msg(self, a, b, text, *, ret=False, num=True, note=False):
        xa, xb = self.px[a], self.px[b]
        if num and not ret:
            self.n += 1
            text = f"{self.n}: {text}"
        w = max(abs(xb - xa) - 14, 80)
        lines = wrap_lines(text, w, SZ)
        h = 12.5 * len(lines)
        y = self.y + h + 4
        self.c.line([(xa, y), (xb, y)], end="open" if ret else "filled", dashed=ret)
        cx = (xa + xb) / 2
        lw = min(w, max(wrap_lines_width(lines), 20))
        self.c.label(cx - lw / 2, y - h - 3, lw, h, text, size=SZ, italic=ret, bg=True)
        self.y = y + 14
        return y

    def self_msg(self, a, text, *, ret=False, num=True):
        x = self.px[a]
        if num and not ret:
            self.n += 1
            text = f"{self.n}: {text}"
        lines = wrap_lines(text, self.step + 40, SZ)
        h = 12.5 * len(lines)
        y = self.y + 8
        loop = max(h, 18)
        self.c.line([(x, y), (x + 30, y), (x + 30, y + loop), (x, y + loop)], end="open" if ret else "filled",
                    dashed=ret)
        self.c.label(x + 34, y + loop / 2 - h / 2, self.step + 40, h, text, size=SZ, align="left", italic=ret, bg=False)
        self.y = y + loop + 12

    def gap(self, h=8):
        self.y += h

    # --- alt fragments
    def alt_begin(self, label="alt", inset=0):
        return dict(y1=self.y + 4, inset=inset, label=label, first=True)

    def operand(self, f, guard):
        x1 = self.left - 8 + f["inset"]
        x2 = self.right + 8 - f["inset"]
        if f["first"]:
            f["first"] = False
            self.c.label(x1 + 46, f["y1"] + 3, x2 - x1 - 50, 15, f"[{guard}]", size=SZ + 1, bold=True,
                         align="left")
            self.y = f["y1"] + 24
        else:
            y = self.y + 4
            self.c.line([(x1, y), (x2, y)], dashed=True, color="#555555")
            self.c.label(x1 + 6, y + 3, x2 - x1 - 12, 15, f"[{guard}]", size=SZ + 1, bold=True, align="left")
            self.y = y + 22

    def alt_end(self, f):
        x1 = self.left - 8 + f["inset"]
        x2 = self.right + 8 - f["inset"]
        y2 = self.y + 4
        self.c.rect(x1, f["y1"], x2 - x1, y2 - f["y1"], "", fill="none", stroke="#444444")
        self.c.rect(x1, f["y1"], 40, 17, f["label"], fill="#ffffff", stroke="#444444", bold=True, size=SZ + 1)
        self.y = y2 + 10

    def finish(self):
        bottom = self.y + 10
        lifelines = []
        for i, head in enumerate(self.heads):
            lifelines.append(dict(kind="line", id=self.c._id("e"), pts=[(self.px[i], head.y + head.h),
                                                                         (self.px[i], bottom)],
                                  end="none", start="none", dashed=True, color="#777777", sw=1, src=None, dst=None))
        self.c.items[0:0] = lifelines
        return self.c.fit()


def d05_sequence_request():
    s = Seq("5. Последовательность: записать ВС на обслуживание (UC-02)",
            ["@Планировщик", "СервисПланирования", "ВыполнительОпераций", "ВалидаторЗаявки",
             "ХранилищеДанных", "ЗаявкаНаОбслуживание", "ЖурналАудита"], step=160, x0=92)
    P, SP, VO, VZ, XD, ZA, ZH = range(7)
    s.msg(P, SP, "создатьЗаявку(идПользователя, идВС, тип, приоритет, желаемаяДата, описание)")
    s.msg(SP, VO, "выполнить(идПользователя, действие, ссылка, операция)")
    s.msg(VO, XD, "транзакция()")
    s.self_msg(VO, "проверить(сотрудник, действие) [ПолитикаДоступа]")
    f1 = s.alt_begin()
    s.operand(f1, "нет права: AccessDenied — ошибка")
    s.msg(VO, XD, "откат транзакции")
    s.msg(VO, ZH, "добавить(идПользователя, действие, ссылка, «отказ», причина)")
    s.msg(VO, SP, "AccessDenied", ret=True)
    s.msg(SP, P, "отказ: роль не вправе создавать заявки", ret=True)
    s.operand(f1, "право есть")
    s.msg(SP, XD, "получитьВС(идВС); найтиАктивнуюЗаявку(идВС)")
    f2 = s.alt_begin(inset=14)
    s.operand(f2, "активной заявки нет, данные полны — основной сценарий")
    s.msg(SP, VZ, "проверить(тип, желаемаяДата, описание, сегодня)")
    s.msg(VZ, SP, "список недостающего пуст", ret=True)
    s.msg(SP, ZA, "создать(…) «Новая»")
    s.msg(SP, XD, "добавитьЗаявку(заявка)")
    s.msg(VO, XD, "фиксация транзакции")
    s.msg(VO, ZH, "добавить(…, «успех»)")
    s.msg(SP, P, "заявка «Новая»", ret=True)
    s.operand(f2, "активной заявки нет, данные неполны — альтернативный путь (E1)")
    s.msg(SP, VZ, "проверить(тип, желаемаяДата, описание, сегодня)")
    s.msg(VZ, SP, "список: «нет даты» / «дата в прошлом»", ret=True)
    s.msg(SP, ZA, "создать(…); отметитьУточнение(недостающее)")
    s.msg(SP, XD, "добавитьЗаявку(заявка) «Требует уточнения»")
    s.msg(VO, XD, "фиксация транзакции")
    s.msg(SP, P, "заявка «Требует уточнения» + перечень недостающего", ret=True)
    s.operand(f2, "активная заявка есть, содержание то же — повторный запрос")
    s.msg(SP, ZA, "тоЖеСодержание(идАвтора, тип, дата, описание)")
    s.msg(ZA, SP, "истина", ret=True)
    s.msg(SP, P, "существующая заявка (новая не создана)", ret=True)
    s.operand(f2, "активная заявка есть, содержание другое — ошибка")
    s.msg(SP, ZA, "тоЖеСодержание(идАвтора, тип, дата, описание)")
    s.msg(ZA, SP, "ложь", ret=True)
    s.msg(VO, XD, "откат транзакции")
    s.msg(VO, ZH, "добавить(…, «отказ», «у ВС уже есть активная заявка»)")
    s.msg(SP, P, "ActiveRequestExists", ret=True)
    s.alt_end(f2)
    s.alt_end(f1)
    return s.finish()


def d06_sequence_assign():
    s = Seq("6. Последовательность: назначить ресурсы (UC-03)",
            ["@Планировщик", "СервисПланирования", "ВыполнительОпераций", "ХранилищеДанных",
             "РесурсОбслуживания", "ЗаявкаНаОбслуживание", "ВоздушноеСудно", "ЖурналАудита",
             "КаналУведомления"], step=134, x0=84)
    P, SP, VO, XD, RS, ZA, VS, ZH, KU = range(9)
    s.msg(P, SP, "назначитьРесурсы(идПользователя, идЗаявки, идыРесурсов, начало, конец)")
    s.msg(SP, VO, "выполнить(идПользователя, действие, ссылка, операция)")
    s.msg(VO, XD, "транзакция()")
    s.self_msg(VO, "проверить(сотрудник, действие) [ПолитикаДоступа]")
    f1 = s.alt_begin()
    s.operand(f1, "нет права: AccessDenied — ошибка")
    s.msg(VO, XD, "откат транзакции")
    s.msg(VO, ZH, "добавить(идПользователя, действие, ссылка, «отказ», причина)")
    s.msg(SP, P, "отказ: доступ запрещён", ret=True)
    s.operand(f1, "право есть")
    s.msg(SP, XD, "получитьЗаявку(идЗаявки); получитьВС(идВС)")
    s.self_msg(SP, "забронировать(заявка, ВС, идыРесурсов, начало, конец)")
    s.msg(SP, XD, "списокАктивныхНазначений(идРесурса)")
    s.msg(SP, RS, "забронировать(активные, идНазначения, идЗаявки, начало, конец)")
    f2 = s.alt_begin(inset=12)
    s.operand(f2, "интервал свободен у всех ресурсов — основной сценарий")
    s.msg(RS, SP, "назначение", ret=True)
    s.msg(SP, XD, "добавитьНазначение(назначение)")
    s.msg(SP, ZA, "назначить()")
    s.msg(SP, VS, "зарезервироватьОбслуживание()")
    s.msg(SP, XD, "сохранитьЗаявку(…); сохранитьВС(…)")
    s.msg(VO, XD, "фиксация транзакции")
    s.msg(VO, ZH, "добавить(…, «успех»)")
    s.msg(SP, P, "назначения; заявка «Запланирована»", ret=True)
    s.operand(f2, "ресурс занят: ResourceConflict — исключительная ситуация (E2)")
    s.msg(RS, SP, "ResourceConflict", ret=True)
    s.msg(VO, XD, "откат транзакции (ни одно назначение не сохраняется)")
    s.msg(VO, ZH, "добавить(…, «отказ», причина)")
    s.msg(SP, XD, "перевестиВОжидание: транзакция(); заявка.запроситьОжидание(); сохранитьЗаявку()")
    s.msg(SP, ZA, "запроситьОжидание() «Ожидает ресурсов»")
    f3 = s.alt_begin(inset=26)
    s.operand(f3, "канал уведомлений доступен")
    s.msg(SP, KU, "отправить(идПолучателя, тема, текст)")
    s.operand(f3, "канал недоступен — альтернативный путь")
    s.msg(KU, SP, "ConnectionError", ret=True)
    s.msg(SP, ZH, "добавить(«уведомление», «сбой»)")
    s.alt_end(f3)
    s.msg(SP, P, "отказ: ресурс занят, заявка «Ожидает ресурсов»", ret=True)
    s.operand(f2, "сбой хранилища при сохранении: StorageError — ошибка")
    s.msg(XD, SP, "StorageError", ret=True)
    s.msg(VO, XD, "откат транзакции")
    s.msg(VO, ZH, "добавить(…, «сбой», причина)")
    s.msg(SP, P, "ошибка сохранения, повторить операцию", ret=True)
    s.alt_end(f2)
    s.alt_end(f1)
    return s.finish()


def d07_sequence_release():
    s = Seq("7. Последовательность: допустить ВС к эксплуатации (UC-07)",
            ["@Руководитель", "СервисДопуска", "ВыполнительОпераций", "ХранилищеДанных", "ЗаказНаряд",
             "ВоздушноеСудно", "ЗаявкаНаОбслуживание", "ЖурналАудита", "КаналУведомления"], step=134, x0=84)
    R, SD, VO, XD, ZN, VS, ZA, ZH, KU = range(9)
    s.msg(R, SD, "выдатьДопуск(идПользователя, идЗН)")
    s.msg(SD, VO, "выполнить(идПользователя, действие, ссылка, операция)")
    s.msg(VO, XD, "транзакция()")
    s.self_msg(VO, "проверить(сотрудник, действие) [ПолитикаДоступа]")
    f1 = s.alt_begin()
    s.operand(f1, "нет права: AccessDenied — ошибка")
    s.msg(VO, XD, "откат транзакции")
    s.msg(VO, ZH, "добавить(идПользователя, действие, ссылка, «отказ», причина)")
    s.msg(SD, R, "отказ: доступ запрещён", ret=True)
    s.operand(f1, "право есть")
    s.msg(SD, XD, "получитьЗаказНаряд(идЗН); получитьВС(идВС); получитьЗаявку(идЗаявки)")
    s.msg(SD, VS, "выдатьДопуск(зн, срокТО)")
    s.msg(VS, ZN, "причиныОтказаВДопуске()")
    s.msg(ZN, VS, "список причин", ret=True)
    f2 = s.alt_begin(inset=12)
    s.operand(f2, "список пуст, канал работает — основной сценарий")
    s.self_msg(VS, "статус := «Готово к эксплуатации»; срокСледующегоТО := сегодня + 180 дней")
    s.msg(SD, ZN, "закрыть()")
    s.msg(SD, ZA, "завершить()")
    s.msg(SD, XD, "освободитьРесурсы; сохранитьВС; сохранитьЗаказНаряд; сохранитьЗаявку")
    s.msg(VO, XD, "фиксация транзакции")
    s.msg(VO, ZH, "добавить(…, «успех»)")
    s.msg(SD, KU, "отправить(идПолучателя, тема, текст) — планировщикам")
    s.msg(SD, R, "ВС «Готово к эксплуатации»", ret=True)
    s.operand(f2, "список пуст, канал недоступен — альтернативный путь")
    s.msg(SD, KU, "отправить(идПолучателя, тема, текст)")
    s.msg(KU, SD, "ConnectionError", ret=True)
    s.msg(SD, ZH, "добавить(«уведомление», «сбой»); допуск не откатывается")
    s.msg(SD, R, "ВС «Готово к эксплуатации»", ret=True)
    s.operand(f2, "список не пуст: ReleaseDenied — ошибка (нарушено BR-07)")
    s.msg(VS, SD, "ReleaseDenied(причины)", ret=True)
    s.msg(VO, XD, "откат транзакции")
    s.msg(VO, ZH, "добавить(…, «отказ», причины)")
    s.msg(SD, R, "отказ: допуск запрещён + перечень причин", ret=True)
    s.operand(f2, "сбой хранилища при сохранении: StorageError — ошибка")
    s.msg(XD, SD, "StorageError", ret=True)
    s.msg(VO, XD, "откат: статусы ВС, заказ-наряда и заявки прежние")
    s.msg(VO, ZH, "добавить(…, «сбой», причина)")
    s.msg(SD, R, "ошибка сохранения, повторить", ret=True)
    s.alt_end(f2)
    s.alt_end(f1)
    return s.finish()
