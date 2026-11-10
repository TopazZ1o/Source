"""Demo of the prototype: one normal and one failed scenario.

Run from the prototype directory:  python demo.py
"""

import sys
from datetime import date, datetime

from aircraft_maintenance.adapters import InAppNotifier, InMemoryAuditLog
from aircraft_maintenance.domain import (Aircraft, DomainError, Employee, MaintenanceType,
                                         Priority, Resource, ResourceKind, Role, Verdict)
from aircraft_maintenance.services import (PlanningService, ReleaseService, StageSpec,
                                           WorkOrderService)
from aircraft_maintenance.storage import InMemoryDataStore

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")  # the Windows console uses cp866

NOW = datetime(2026, 11, 2, 9, 0)
START, END = datetime(2026, 11, 5, 10, 0), datetime(2026, 11, 5, 12, 0)


def main() -> None:
    store, audit, notifier = InMemoryDataStore(), InMemoryAuditLog(lambda: NOW), InAppNotifier()
    args, kwargs = (store, audit, notifier), {"clock": lambda: NOW}
    planning = PlanningService(*args, **kwargs)
    orders = WorkOrderService(*args, **kwargs)
    release = ReleaseService(*args, planning=planning, **kwargs)
    for emp in (Employee(1, "Планировщик 1", Role.PLANNER), Employee(2, "Планировщик 2", Role.PLANNER),
                Employee(3, "Техник", Role.TECHNICIAN), Employee(5, "Руководитель", Role.CHIEF)):
        store.add_employee(emp)
    for aid, tail in ((1, "UP-A1001"), (2, "UP-A1002")):
        store.add_aircraft(Aircraft(aid, tail, "Boeing 737", f"SN-{aid}", date(2015, 5, 1)))
    store.add_resource(Resource(1, ResourceKind.SPECIALIST, "Техник", employee_id=3))
    store.add_resource(Resource(2, ResourceKind.HANGAR_SLOT, "Ангар, место 1"))

    print("== Штатный сценарий: плановое ТО борта UP-A1001 ==")
    request = planning.create_request(1, 1, MaintenanceType.PLANNED, Priority.NORMAL,
                                      date(2026, 11, 5), "Плановое ТО")
    planning.schedule(1, request.request_id, [1, 2], START, END)
    print("Заявка:", store.get_request(request.request_id).status.value,
          "| ВС:", store.get_aircraft(1).status.value)
    order = orders.open(1, request.request_id, [StageSpec("Осмотр планера", True, 3)])
    orders.start(3, order.work_order_id)
    orders.complete_stage(3, order.work_order_id, 1, "норма")
    release.issue_conclusion(5, order.work_order_id, Verdict.FIT, "Осмотр пройден")
    aircraft = release.release(5, order.work_order_id)
    print("Допуск выдан. ВС:", aircraft.status.value, "| следующее ТО:", aircraft.next_maintenance_due)

    print("\n== Неуспешный сценарий: два борта претендуют на одно место в ангаре ==")
    second = planning.create_request(2, 2, MaintenanceType.PLANNED, Priority.NORMAL,
                                     date(2026, 11, 5), "Плановое ТО")
    planning.schedule(2, second.request_id, [2], START, END)
    third = planning.create_request(1, 1, MaintenanceType.UNPLANNED, Priority.HIGH,
                                    date(2026, 11, 5), "Замена колеса")
    try:
        planning.schedule(1, third.request_id, [2], START, END)
    except DomainError as error:
        print("Отказ:", error)
        print("Заявка:", store.get_request(third.request_id).status.value)

    print("\nЖурнал аудита:")
    for record in audit.records():
        print(f"  #{record.seq} {record.action} [{record.object_ref}] — {record.outcome}")
    print("\nСообщения:")
    for recipient, subject, text in notifier.messages:
        print(f"  [{recipient}] {subject}: {text}")


if __name__ == "__main__":
    main()
