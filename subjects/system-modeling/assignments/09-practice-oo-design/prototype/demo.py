"""Console demonstration on the training data.

    python demo.py
"""

import sys
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8")

from mro_requests.config import build_service, default_policies  # noqa: E402
from mro_requests.console import ConsoleUI, fmt_time  # noqa: E402
from mro_requests.enums import Priority  # noqa: E402
from mro_requests.repository import CopyOnSaveRequestRepository, InMemoryRequestRepository  # noqa: E402
from mro_requests.seed import load_seed  # noqa: E402
from mro_requests.sla import AcceleratedSlaPolicy, SlaPolicy, StandardSlaPolicy, UrgentSlaPolicy  # noqa: E402
from tests.support import snapshot, World  # noqa: E402


def section(ui: ConsoleUI, title: str) -> None:
    ui.say()
    ui.say(f"=== {title} ===")


def main() -> None:
    service, clock = build_service()
    load_seed(service, clock)
    ui = ConsoleUI(service, sys.stdout)

    section(ui, "1. Исходное состояние (загружено операциями сервиса)")
    ui.show_requests()
    ui.show_load("U03", ("T01", "T02"))
    ui.show_history("U02", "SR04")

    section(ui, "2. Сроки завершения: одна операция calculate_due_at, две политики")
    for code in ("SR01", "SR02"):
        r = next(x for x in service.list_requests() if x.code == code)
        hours = (r.due_at - r.created_at).total_seconds() / 3600
        ui.say(f"  {code} ({r.priority.value}): создана {fmt_time(r.created_at)} + {hours:g} ч = {fmt_time(r.due_at)}")
    ui.say("  Разница: политика выбирается по приоритету в конфигурации; ServiceRequest получает объект политики.")

    section(ui, "3. Корректная операция: диспетчер назначает SR01 специалисту T01")
    clock.set(datetime(2026, 11, 16, 11, 5))
    ui.assign("U03", "SR01", "T01")
    ui.show_load("U03", ("T01", "T02"))

    section(ui, "4. Отклоняемая операция: SR02 (ПО) назначается специалисту T01 (только оборудование)")
    ui.assign("U03", "SR02", "T01")
    ui.show_requests()
    ui.show_load("U03", ("T01", "T02"))

    section(ui, "5. Основной сценарий SR01: от начала работы до завершения")
    clock.set(datetime(2026, 11, 16, 11, 20))
    ui.start("U05", "SR01")                 # not the assigned technician
    ui.start("U04", "SR01")
    clock.set(datetime(2026, 11, 16, 12, 40))
    ui.complete("U04", "SR01")              # items are not done
    ui.complete_item("U04", "SR01", "SR01-W1")
    ui.complete_item("U04", "SR01", "SR01-W2")
    clock.set(datetime(2026, 11, 16, 13, 0))
    ui.complete("U04", "SR01")
    ui.complete("U04", "SR01")              # repeated completion
    ui.show_load("U03", ("T01", "T02"))
    ui.show_history("U01", "SR01")

    section(ui, "6. Отправка пустой заявки SR03 и отмена")
    ui.submit("U01", "SR03")
    ui.add_item("U01", "SR03", "Заменить изношенные тормозные диски и проверить зазоры колодок")
    ui.submit("U01", "SR03")
    ui.cancel("U02", "SR03")                # not the owner
    ui.cancel("U01", "SR03")
    ui.show_history("U01", "SR03")

    section(ui, "7. Смена политики срока: тот же контракт, другой объект")
    created = datetime(2026, 11, 16, 9, 0)
    for policy in (StandardSlaPolicy(), UrgentSlaPolicy(), AcceleratedSlaPolicy()):
        p: SlaPolicy = policy
        ui.say(f"  {type(p).__name__:<20} {fmt_time(created)} -> {fmt_time(p.calculate_due_at(created))}")
    swapped = default_policies()
    swapped[Priority.STANDARD] = UrgentSlaPolicy()
    service2, clock2 = build_service(policies=swapped)
    load_seed(service2, clock2)
    sr01 = next(r for r in service2.list_requests() if r.code == "SR01")
    ui.say(f"  Конфигурация STANDARD -> UrgentSlaPolicy: срок SR01 стал {fmt_time(sr01.due_at)} "
           f"(было 17.11.2026 09:00); код ServiceRequest не менялся.")

    section(ui, "8. Смена способа хранения: те же операции над другим репозиторием")
    snaps = []
    for factory in (InMemoryRequestRepository, CopyOnSaveRequestRepository):
        repo = factory()
        svc, clk = build_service(repo)
        load_seed(svc, clk)
        svc.assign_technician("U03", "SR01", "T01")
        snaps.append(snapshot(World(svc, clk, repo)))
    ui.say(f"  Результат одинаков в InMemoryRequestRepository и CopyOnSaveRequestRepository: {snaps[0] == snaps[1]}")


if __name__ == "__main__":
    main()
