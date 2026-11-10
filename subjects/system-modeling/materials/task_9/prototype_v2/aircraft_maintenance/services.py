"""Application services: access control, transactions, audit and notifications.

Services coordinate; the business rules of one object stay in the object (domain.py).
Every operation runs in one transaction; the audit record and the notification are
written after the commit, so a rollback never leaves a record of a success.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import Enum
from typing import Callable, Optional

from .domain import (AccessDenied, Aircraft, AircraftStatus, Assignment, Conclusion, Defect,
                     DomainError, Employee, MaintenanceRequest, MaintenanceType, Priority,
                     RequestStatus, ResourceConflict, Role, Severity, StorageError, ValidationError,
                     Verdict, WorkOrder, WorkOrderStatus, WriteOffAct, InvalidTransition,
                     ActiveRequestExists)
from .ports import AuditLog, DataStore, Notifier


class Action(Enum):
    CREATE_REQUEST = "создать заявку"
    CORRECT_REQUEST = "уточнить заявку"
    SCHEDULE = "назначить ресурсы"
    CANCEL_REQUEST = "отменить заявку"
    OPEN_WORK_ORDER = "открыть заказ-наряд"
    ADD_STAGE = "добавить этап"
    START_WORK = "начать работы"
    COMPLETE_STAGE = "закрыть этап"
    REGISTER_DEFECT = "зафиксировать дефект"
    RESOLVE_DEFECT = "устранить дефект"
    ADD_PART = "учесть запчасть"
    CONCLUDE = "выдать заключение о годности"
    RELEASE = "выдать допуск"
    WRITE_OFF = "оформить списание"


class AccessPolicy:
    """Role matrix (NF2): who may perform which action."""

    _MATRIX = {
        Action.CREATE_REQUEST: {Role.PLANNER},
        Action.CORRECT_REQUEST: {Role.PLANNER},
        Action.SCHEDULE: {Role.PLANNER},
        Action.CANCEL_REQUEST: {Role.PLANNER},
        Action.OPEN_WORK_ORDER: {Role.PLANNER},
        Action.ADD_STAGE: {Role.PLANNER},
        Action.START_WORK: {Role.TECHNICIAN},
        Action.COMPLETE_STAGE: {Role.TECHNICIAN},
        Action.REGISTER_DEFECT: {Role.TECHNICIAN},
        Action.RESOLVE_DEFECT: {Role.TECHNICIAN},
        Action.ADD_PART: {Role.TECHNICIAN},
        Action.CONCLUDE: {Role.CHIEF},
        Action.RELEASE: {Role.CHIEF},
        Action.WRITE_OFF: {Role.CHIEF},
    }

    def check(self, employee: Optional[Employee], action: Action) -> Employee:
        if employee is None:
            raise AccessDenied("Пользователь не найден")
        if employee.blocked:
            raise AccessDenied("Пользователь заблокирован")
        if employee.role not in self._MATRIX[action]:
            raise AccessDenied(f"Роль «{employee.role.value}» не вправе: {action.value}")
        return employee


class RequestValidator:
    """Completeness check of a request (exceptional situation E1)."""

    def check(self, mtype: MaintenanceType, desired_date: Optional[date],
              description: str, today: date) -> list[str]:
        missing = []
        if desired_date is None:
            missing.append("не указана желаемая дата")
        elif desired_date < today:
            missing.append("желаемая дата в прошлом")
        if mtype == MaintenanceType.UNPLANNED and not description.strip():
            missing.append("для внепланового обслуживания нужно описание причины")
        return missing


class OperationRunner:
    """Common part of the services: rights, one transaction, audit, notifications.

    Services hold a runner (composition) instead of inheriting from a common base class:
    the lecture warns against inheritance used only to share code.
    """

    def __init__(self, store: DataStore, audit: AuditLog, notifier: Notifier,
                 clock: Callable[[], datetime], policy: AccessPolicy) -> None:
        self.store, self.audit, self.notifier = store, audit, notifier
        self.clock, self.policy = clock, policy

    def execute(self, user_id: Optional[int], action: Action, object_ref: str,
                operation: Callable[[Employee], object], detail: str = ""):
        """Check rights, run the operation in one transaction, then write the audit record."""
        try:
            with self.store.transaction():
                employee = self.policy.check(self.store.get_employee(user_id), action)
                result = operation(employee)
        except DomainError as error:
            self.audit.append(user_id, action.value, object_ref, "отказ", str(error))
            raise
        except StorageError as error:
            self.audit.append(user_id, action.value, object_ref, "сбой", str(error))
            raise
        self.audit.append(user_id, action.value, object_ref, "успех", detail)
        return result

    def notify(self, recipient_id: int, subject: str, text: str) -> None:
        """A failing channel never undoes the data (BR-10): the failure is only journaled."""
        try:
            self.notifier.send(recipient_id, subject, text)
        except Exception as error:  # noqa: BLE001 - any channel failure
            self.audit.append(None, "уведомление", f"пользователь {recipient_id}", "сбой", str(error))

    def notify_planners(self, subject: str, text: str) -> None:
        for employee in self.store.list_employees():
            if employee.role == Role.PLANNER and not employee.blocked:
                self.notify(employee.employee_id, subject, text)

    def request(self, request_id: int) -> MaintenanceRequest:
        request = self.store.get_request(request_id)
        if request is None:
            raise ValidationError("Заявка не найдена")
        return request

    def work_order(self, work_order_id: int) -> WorkOrder:
        work_order = self.store.get_work_order(work_order_id)
        if work_order is None:
            raise ValidationError("Заказ-наряд не найден")
        return work_order

    def aircraft(self, aircraft_id: int) -> Aircraft:
        aircraft = self.store.get_aircraft(aircraft_id)
        if aircraft is None:
            raise ValidationError("ВС не найдено")
        return aircraft


# ---------------------------------------------------------------- planning

class PlanningService:
    """Requests, booking of resources, cancelation (UC-02, UC-03)."""

    def __init__(self, store: DataStore, audit: AuditLog, notifier: Notifier,
                 clock: Callable[[], datetime] = datetime.now,
                 policy: Optional[AccessPolicy] = None,
                 validator: Optional[RequestValidator] = None) -> None:
        self.store, self.audit, self.clock = store, audit, clock
        self.ops = OperationRunner(store, audit, notifier, clock, policy or AccessPolicy())
        self.validator = validator or RequestValidator()

    def create_request(self, user_id: int, aircraft_id: int, mtype: MaintenanceType,
                       priority: Priority, desired_date: Optional[date],
                       description: str) -> MaintenanceRequest:
        def operation(employee: Employee) -> MaintenanceRequest:
            aircraft = self.ops.aircraft(aircraft_id)
            if aircraft.status == AircraftStatus.WRITTEN_OFF:
                raise ValidationError("ВС списано, заявка невозможна")
            existing = self.store.find_active_request(aircraft_id)
            if existing is not None:
                if existing.same_content(employee.employee_id, mtype, desired_date, description):
                    return existing  # repeated request is idempotent (BR-04)
                raise ActiveRequestExists("У ВС уже есть активная заявка")
            request = MaintenanceRequest(self.store.next_id("request"), aircraft_id,
                                         employee.employee_id, mtype, priority, desired_date,
                                         description)
            missing = self.validator.check(mtype, desired_date, description, self.clock().date())
            if missing:
                request.mark_needs_clarification(missing)
            self.store.add_request(request)
            return request
        return self.ops.execute(user_id, Action.CREATE_REQUEST, f"ВС {aircraft_id}", operation)

    def correct_request(self, user_id: int, request_id: int, desired_date: Optional[date],
                        description: str) -> MaintenanceRequest:
        def operation(employee: Employee) -> MaintenanceRequest:
            request = self.ops.request(request_id)
            if request.status != RequestStatus.NEEDS_CLARIFICATION:
                raise InvalidTransition("Исправлять можно только заявку «Требует уточнения»")
            request.desired_date, request.description = desired_date, description
            missing = self.validator.check(request.mtype, desired_date, description,
                                           self.clock().date())
            if missing:
                request.mark_needs_clarification(missing)
            else:
                request.mark_clarified()
            self.store.save_request(request)
            return request
        return self.ops.execute(user_id, Action.CORRECT_REQUEST, f"заявка {request_id}", operation)

    def schedule(self, user_id: int, request_id: int, resource_ids: list[int],
                 start: datetime, end: datetime) -> list[Assignment]:
        """Book all resources atomically (all or nothing) and schedule the request."""
        def operation(employee: Employee) -> list[Assignment]:
            request = self.ops.request(request_id)
            aircraft = self.ops.aircraft(request.aircraft_id)
            if aircraft.status == AircraftStatus.WRITTEN_OFF:
                raise ValidationError("ВС списано, планирование невозможно")
            return self._book(request, aircraft, resource_ids, start, end)
        try:
            return self.ops.execute(user_id, Action.SCHEDULE, f"заявка {request_id}", operation)
        except ResourceConflict as error:
            self._enqueue(user_id, request_id, resource_ids, start, end, error)
            raise

    def _book(self, request: MaintenanceRequest, aircraft: Aircraft, resource_ids: list[int],
              start: datetime, end: datetime) -> list[Assignment]:
        ids = list(dict.fromkeys(resource_ids))
        if not ids:
            raise ValidationError("Не указан ни один ресурс")
        if request.status not in (RequestStatus.NEW, RequestStatus.WAITING_RESOURCES):
            raise InvalidTransition(f"Заявку «{request.status.value}» планировать нельзя")
        assignments = []
        for resource_id in ids:
            resource = self.store.get_resource(resource_id)
            if resource is None:
                raise ValidationError(f"Ресурс {resource_id} не найден")
            assignment = resource.book(self.store.list_active_assignments(resource_id),
                                       self.store.next_id("assignment"), request.request_id,
                                       start, end)
            self.store.add_assignment(assignment)
            assignments.append(assignment)
        request.schedule()
        aircraft.reserve_maintenance()
        self.store.save_request(request)
        self.store.save_aircraft(aircraft)
        return assignments

    def _enqueue(self, user_id: int, request_id: int, resource_ids: list[int],
                 start: datetime, end: datetime, error: Exception) -> None:
        """Exceptional situation E2 with the queue: the request waits for its resources in order."""
        with self.store.transaction():
            request = self.store.get_request(request_id)
            if request is not None and request.status in (RequestStatus.NEW,
                                                          RequestStatus.WAITING_RESOURCES):
                request.wait_for_resources(tuple(dict.fromkeys(resource_ids)), start, end,
                                           self.store.next_id("queue"))
                self.store.save_request(request)
        self.audit.append(user_id, "постановка заявки в очередь", f"заявка {request_id}",
                          "успех", str(error))
        self.ops.notify(user_id, "Заявка ожидает ресурсов",
                     f"Заявка {request_id} поставлена в очередь: {error}.")

    def serve_queue(self) -> list[MaintenanceRequest]:
        """Give freed resources to waiting requests: higher priority first, then first come first served."""
        served = []
        with self.store.transaction():
            waiting = sorted(self.store.find_waiting_requests(),
                             key=lambda r: (-int(r.priority), r.queued_seq))
            for entry in waiting:
                try:
                    with self.store.transaction():  # a failed attempt keeps no partial booking
                        request = self.ops.request(entry.request_id)
                        aircraft = self.ops.aircraft(request.aircraft_id)
                        self._book(request, aircraft, list(request.wait_resource_ids),
                                   request.wait_start, request.wait_end)
                except ResourceConflict:
                    continue
                served.append(entry.request_id)
        for request_id in served:
            request = self.store.get_request(request_id)
            self.audit.append(None, "назначение из очереди", f"заявка {request_id}", "успех")
            self.ops.notify(request.author_id, "Заявка назначена из очереди",
                         f"Заявка {request_id}: ресурсы освободились и назначены.")
        return [self.store.get_request(i) for i in served]

    def cancel_request(self, user_id: int, request_id: int) -> None:
        self.ops.execute(user_id, Action.CANCEL_REQUEST, f"заявка {request_id}",
                      lambda employee: self.cancel_in_transaction(self.ops.request(request_id)))
        self.serve_queue()

    def free_resources(self, request: MaintenanceRequest) -> None:
        """Deactivate the assignments of the request (cancelation, release, write-off)."""
        for assignment in self.store.assignments_of_request(request.request_id):
            assignment.cancel()
            self.store.save_assignment(assignment)

    def cancel_in_transaction(self, request: MaintenanceRequest,
                              allow_in_progress: bool = False) -> None:
        """Cancel the request and free its resources; the caller owns the transaction."""
        if request.status == RequestStatus.IN_PROGRESS and not allow_in_progress:
            raise InvalidTransition("Заявку в работе отменяет только списание ВС")
        self.free_resources(request)
        request.cancel()
        aircraft = self.ops.aircraft(request.aircraft_id)
        aircraft.cancel_reservation()
        self.store.save_request(request)
        self.store.save_aircraft(aircraft)


# ---------------------------------------------------------------- work orders

@dataclass(frozen=True)
class StageSpec:
    name: str
    mandatory: bool
    executor_id: int


class WorkOrderService:
    """Work order, stages, defects and spare parts (UC-04, UC-05)."""

    def __init__(self, store: DataStore, audit: AuditLog, notifier: Notifier,
                 clock: Callable[[], datetime] = datetime.now,
                 policy: Optional[AccessPolicy] = None) -> None:
        self.store, self.audit, self.clock = store, audit, clock
        self.ops = OperationRunner(store, audit, notifier, clock, policy or AccessPolicy())

    def open(self, user_id: int, request_id: int, stages: list[StageSpec]) -> WorkOrder:
        def operation(employee: Employee) -> WorkOrder:
            request = self.ops.request(request_id)
            if request.status != RequestStatus.SCHEDULED:
                raise InvalidTransition("Заказ-наряд открывается только по запланированной заявке")
            if self.store.find_work_order_by_request(request_id) is not None:
                raise InvalidTransition("Заказ-наряд по заявке уже открыт")
            work_order = WorkOrder(self.store.next_id("work_order"), request_id, request.aircraft_id)
            for spec in stages:
                executor = self.store.get_employee(spec.executor_id)
                if executor is None or executor.role != Role.TECHNICIAN or executor.blocked:
                    raise ValidationError("Исполнитель этапа должен быть активным техником")
                work_order.add_stage(spec.name, spec.mandatory, spec.executor_id)
            if not any(s.mandatory for s in work_order.stages):
                raise ValidationError("Нужен хотя бы один обязательный этап")
            self.store.add_work_order(work_order)
            return work_order
        return self.ops.execute(user_id, Action.OPEN_WORK_ORDER, f"заявка {request_id}", operation)

    def start(self, user_id: int, work_order_id: int) -> WorkOrder:
        def operation(employee: Employee) -> WorkOrder:
            work_order = self.ops.work_order(work_order_id)
            request = self.ops.request(work_order.request_id)
            aircraft = self.ops.aircraft(work_order.aircraft_id)
            work_order.start()
            request.start()
            aircraft.start_maintenance()
            self.store.save_work_order(work_order)
            self.store.save_request(request)
            self.store.save_aircraft(aircraft)
            return work_order
        return self.ops.execute(user_id, Action.START_WORK, f"заказ-наряд {work_order_id}", operation)

    def add_stage(self, user_id: int, work_order_id: int, name: str, mandatory: bool,
                  executor_id: int) -> WorkOrder:
        def operation(employee: Employee) -> WorkOrder:
            work_order = self.ops.work_order(work_order_id)
            work_order.add_stage(name, mandatory, executor_id)
            self.store.save_work_order(work_order)
            return work_order
        return self.ops.execute(user_id, Action.ADD_STAGE, f"заказ-наряд {work_order_id}", operation)

    def complete_stage(self, user_id: int, work_order_id: int, stage_id: int,
                       result: str) -> WorkOrder:
        def operation(employee: Employee) -> WorkOrder:
            work_order = self.ops.work_order(work_order_id)
            work_order.complete_stage(stage_id, employee.employee_id, result)
            self.store.save_work_order(work_order)
            return work_order
        return self.ops.execute(user_id, Action.COMPLETE_STAGE, f"заказ-наряд {work_order_id}", operation)

    def register_defect(self, user_id: int, work_order_id: int, description: str,
                        severity: Severity) -> Defect:
        def operation(employee: Employee) -> Defect:
            work_order = self.ops.work_order(work_order_id)
            defect = work_order.register_defect(description, severity)
            self.store.save_work_order(work_order)
            return defect
        return self.ops.execute(user_id, Action.REGISTER_DEFECT, f"заказ-наряд {work_order_id}", operation)

    def resolve_defect(self, user_id: int, work_order_id: int, defect_id: int) -> None:
        def operation(employee: Employee) -> None:
            work_order = self.ops.work_order(work_order_id)
            work_order.resolve_defect(defect_id)
            self.store.save_work_order(work_order)
        return self.ops.execute(user_id, Action.RESOLVE_DEFECT, f"заказ-наряд {work_order_id}", operation)

    def add_part(self, user_id: int, work_order_id: int, part_number: str, quantity: int) -> None:
        def operation(employee: Employee) -> None:
            work_order = self.ops.work_order(work_order_id)
            work_order.add_part(part_number, quantity)
            self.store.save_work_order(work_order)
        return self.ops.execute(user_id, Action.ADD_PART, f"заказ-наряд {work_order_id}", operation)


# ---------------------------------------------------------------- release

class ReleaseService:
    """Conclusion of airworthiness and release to service (UC-06, UC-07)."""

    def __init__(self, store: DataStore, audit: AuditLog, notifier: Notifier,
                 clock: Callable[[], datetime] = datetime.now,
                 policy: Optional[AccessPolicy] = None,
                 planning: Optional[PlanningService] = None, interval_days: int = 180) -> None:
        self.store, self.audit, self.clock = store, audit, clock
        self.ops = OperationRunner(store, audit, notifier, clock, policy or AccessPolicy())
        self.planning = planning
        self.interval_days = interval_days  # design assumption: next maintenance in 180 days

    def issue_conclusion(self, user_id: int, work_order_id: int, verdict: Verdict,
                         basis: str) -> Conclusion:
        def operation(employee: Employee) -> Conclusion:
            work_order = self.ops.work_order(work_order_id)
            conclusion = work_order.issue_conclusion(employee.employee_id, verdict, basis,
                                                     self.clock())
            self.store.save_work_order(work_order)
            return conclusion
        return self.ops.execute(user_id, Action.CONCLUDE, f"заказ-наряд {work_order_id}", operation)

    def release(self, user_id: int, work_order_id: int) -> Aircraft:
        def operation(employee: Employee) -> Aircraft:
            work_order = self.ops.work_order(work_order_id)
            aircraft = self.ops.aircraft(work_order.aircraft_id)
            request = self.ops.request(work_order.request_id)
            aircraft.release(work_order, self.clock().date() + timedelta(days=self.interval_days))
            work_order.close()
            request.complete()
            self.planning.free_resources(request)
            self.store.save_aircraft(aircraft)
            self.store.save_work_order(work_order)
            self.store.save_request(request)
            return aircraft
        aircraft = self.ops.execute(user_id, Action.RELEASE, f"заказ-наряд {work_order_id}", operation,
                                 detail="статус ВС: Готово к эксплуатации")
        self.ops.notify_planners("ВС допущено к эксплуатации", f"Борт {aircraft.tail_number}")
        self.planning.serve_queue()
        return aircraft


# ---------------------------------------------------------------- write-off

class WriteOffService:
    """Write-off of an aircraft (UC-09): irreversible in the system (BR-08)."""

    def __init__(self, store: DataStore, audit: AuditLog, notifier: Notifier,
                 clock: Callable[[], datetime] = datetime.now,
                 policy: Optional[AccessPolicy] = None,
                 planning: Optional[PlanningService] = None) -> None:
        self.store, self.audit, self.clock = store, audit, clock
        self.ops = OperationRunner(store, audit, notifier, clock, policy or AccessPolicy())
        self.planning = planning

    def write_off(self, user_id: int, aircraft_id: int, reason: str,
                  document_ref: str) -> WriteOffAct:
        def operation(employee: Employee) -> WriteOffAct:
            if not reason.strip() or not document_ref.strip():
                raise ValidationError("Нужны основание и реквизиты утверждающего документа")
            aircraft = self.ops.aircraft(aircraft_id)
            request = self.store.find_active_request(aircraft_id)
            if request is not None:
                work_order = self.store.find_work_order_by_request(request.request_id)
                self.planning.cancel_in_transaction(request, allow_in_progress=True)
                if work_order is not None:
                    work_order.terminate()
                    self.store.save_work_order(work_order)
            aircraft.write_off()
            self.store.save_aircraft(aircraft)
            act = WriteOffAct(self.store.next_id("act"), aircraft_id, reason, document_ref,
                              employee.employee_id, self.clock())
            self.store.add_write_off_act(act)
            return act
        act = self.ops.execute(user_id, Action.WRITE_OFF, f"ВС {aircraft_id}", operation)
        self.planning.serve_queue()
        return act


# ---------------------------------------------------------------- deadlines

class DeadlineService:
    """Control of maintenance deadlines (UC-10); runs on a schedule, so no user rights check."""

    def __init__(self, store: DataStore, audit: AuditLog, notifier: Notifier,
                 clock: Callable[[], datetime] = datetime.now,
                 policy: Optional[AccessPolicy] = None,
                 warn_days: int = 7) -> None:
        self.store, self.audit, self.clock = store, audit, clock
        self.ops = OperationRunner(store, audit, notifier, clock, policy or AccessPolicy())
        self.warn_days = warn_days  # design assumption: warn 7 days before the deadline

    def check(self, today: Optional[date] = None) -> list[tuple[int, str]]:
        today = today or self.clock().date()
        events = []
        for aircraft in self.store.list_aircraft():
            if aircraft.status in (AircraftStatus.READY, AircraftStatus.SCHEDULED) \
                    and aircraft.is_overdue(today):
                with self.store.transaction():
                    current = self.ops.aircraft(aircraft.aircraft_id)
                    current.restrict()
                    self.store.save_aircraft(current)
                self.audit.append(None, "контроль сроков", f"ВС {aircraft.aircraft_id}", "успех",
                                  "срок ТО просрочен, статус «Ограничено/не допущено к полётам»")
                self.ops.notify_planners("Срок ТО просрочен", f"Борт {aircraft.tail_number} ограничен")
                events.append((aircraft.aircraft_id, "просрочено"))
            elif aircraft.status == AircraftStatus.READY and aircraft.is_due_soon(today, self.warn_days):
                self.ops.notify_planners("Приближается срок ТО", f"Борт {aircraft.tail_number}")
                events.append((aircraft.aircraft_id, "скоро срок"))
        return events
