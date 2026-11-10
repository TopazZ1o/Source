"""Training data. Loaded only through RequestService operations, so no business rule is bypassed.

Result: SR01 SUBMITTED, SR02 SUBMITTED, SR03 DRAFT without items, SR04 IN_PROGRESS with T01.
"""

from __future__ import annotations

from datetime import datetime

from .clock import ManualClock
from .enums import Category, Priority, Role
from .service import RequestService

DISPATCHER_ID = "U03"


def load_seed(service: RequestService, clock: ManualClock) -> None:
    for user_id, name, role in (
        ("U01", "Заявитель 1 (экипаж, авиакомпания А)", Role.APPLICANT),
        ("U02", "Заявитель 2 (экипаж, авиакомпания Б)", Role.APPLICANT),
        ("U03", "Диспетчер ТО", Role.DISPATCHER),
        ("U04", "Специалист по оборудованию", Role.TECHNICIAN),
        ("U05", "Специалист по оборудованию и ПО", Role.TECHNICIAN),
    ):
        service.register_user(user_id, name, role)
    service.register_technician("T01", "U04", [Category.EQUIPMENT])
    service.register_technician("T02", "U05", [Category.EQUIPMENT, Category.SOFTWARE])

    def at(hour: int, minute: int) -> None:
        clock.set(datetime(2026, 11, 16, hour, minute))

    # SR01: created 16.11.2026 09:00, submitted, two items.
    at(9, 0)
    service.create_request("U01", Category.EQUIPMENT, Priority.STANDARD, "UP-A101",
                           "Течь гидравлической жидкости в основной стойке шасси")
    at(9, 2)
    service.add_item("U01", "SR01", "Осмотреть узлы и магистрали гидросистемы основной стойки шасси, найти место течи")
    at(9, 4)
    service.add_item("U01", "SR01", "Заменить уплотнение гидроцилиндра и проверить гидросистему на герметичность")
    at(9, 6)
    service.submit("U01", "SR01")

    # SR02: created 16.11.2026 09:30, submitted, two items, urgent software fault.
    at(9, 30)
    service.create_request("U02", Category.SOFTWARE, Priority.URGENT, "UP-B202",
                           "Сбой программного обеспечения системы индикации в кабине экипажа")
    at(9, 32)
    service.add_item("U02", "SR02", "Считать журнал отказов системы индикации и зафиксировать коды ошибок")
    at(9, 34)
    service.add_item("U02", "SR02", "Обновить ПО блока индикации до утверждённой версии и выполнить функциональную проверку")
    at(9, 36)
    service.submit("U02", "SR02")

    # SR03: draft without items.
    at(9, 45)
    service.create_request("U01", Category.EQUIPMENT, Priority.STANDARD, "UP-A103",
                           "Износ тормозных дисков колёс основной стойки")

    # SR04: created, submitted, assigned to T01 and started.
    at(10, 0)
    service.create_request("U02", Category.EQUIPMENT, Priority.STANDARD, "UP-B204",
                           "Повышенная вибрация двигателя № 2")
    at(10, 2)
    service.add_item("U02", "SR04", "Выполнить бороскопический осмотр лопаток компрессора двигателя № 2")
    at(10, 4)
    service.add_item("U02", "SR04", "Проверить балансировку вентилятора и крепление датчиков вибрации")
    at(10, 6)
    service.submit("U02", "SR04")
    at(10, 15)
    service.assign_technician(DISPATCHER_ID, "SR04", "T01")
    at(10, 30)
    service.start_work("U04", "SR04")

    at(11, 0)   # "now" for the scenarios that follow
