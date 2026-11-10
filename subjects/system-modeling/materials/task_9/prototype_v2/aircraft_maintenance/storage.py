"""In-memory implementation of DataStore: transactions with rollback and storage constraints."""

from __future__ import annotations

import copy
import threading
from contextlib import contextmanager
from typing import Optional

from .domain import (ActiveRequestExists, Aircraft, Assignment, Employee, MaintenanceRequest,
                     RequestStatus, Resource, ResourceConflict, StorageError, ValidationError,
                     WorkOrder, WriteOffAct)
from .ports import DataStore

_STATE = ("employees", "aircraft", "resources", "requests", "work_orders", "assignments",
          "acts", "seq")


class InMemoryDataStore(DataStore):
    """One global lock serializes transactions (models row locking of a real DBMS).

    The storage constraints repeat the domain rules as the last line of defence:
    unique tail number (BR-01), one active request per aircraft (BR-04) and
    non-overlapping active assignments of a resource (BR-03; in PostgreSQL this is
    an EXCLUDE USING gist constraint). `enforce_constraints` can be switched off
    only by the control test that shows what happens without them.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self.enforce_constraints = True
        self._fail_once: set[str] = set()
        self.employees: dict[int, Employee] = {}
        self.aircraft: dict[int, Aircraft] = {}
        self.resources: dict[int, Resource] = {}
        self.requests: dict[int, MaintenanceRequest] = {}
        self.work_orders: dict[int, "WorkOrder"] = {}
        self.assignments: dict[int, Assignment] = {}
        self.acts: dict[int, WriteOffAct] = {}
        self.seq: dict[str, int] = {}

    # ---- technical helpers

    def fail_once(self, operation: str) -> None:
        """Fault injection for tests: the next call of `operation` raises StorageError."""
        self._fail_once.add(operation)

    def _maybe_fail(self, operation: str) -> None:
        if operation in self._fail_once:
            self._fail_once.discard(operation)
            raise StorageError(f"Сбой хранилища при операции {operation}")

    @contextmanager
    def transaction(self):
        with self._lock:
            snapshot = {name: copy.deepcopy(getattr(self, name)) for name in _STATE}
            try:
                yield self
            except BaseException:
                for name, value in snapshot.items():
                    setattr(self, name, value)
                raise

    def next_id(self, kind: str) -> int:
        self.seq[kind] = self.seq.get(kind, 0) + 1
        return self.seq[kind]

    # ---- employees and resources

    def add_employee(self, employee: Employee) -> None:
        self.employees[employee.employee_id] = employee

    def get_employee(self, employee_id: int) -> Optional[Employee]:
        return self.employees.get(employee_id)

    def list_employees(self) -> list[Employee]:
        return list(self.employees.values())

    def add_resource(self, resource: Resource) -> None:
        self.resources[resource.resource_id] = resource

    def get_resource(self, resource_id: int) -> Optional[Resource]:
        return self.resources.get(resource_id)

    # ---- aircraft

    def add_aircraft(self, aircraft: Aircraft) -> None:
        if not aircraft.tail_number.strip():
            raise ValidationError("Бортовой номер обязателен")
        if any(a.tail_number == aircraft.tail_number for a in self.aircraft.values()):
            raise ValidationError("ВС с таким бортовым номером уже зарегистрировано")
        self.aircraft[aircraft.aircraft_id] = aircraft

    def get_aircraft(self, aircraft_id: int) -> Optional[Aircraft]:
        return self.aircraft.get(aircraft_id)

    def list_aircraft(self) -> list[Aircraft]:
        return list(self.aircraft.values())

    def save_aircraft(self, aircraft: Aircraft) -> None:
        self._maybe_fail("save_aircraft")
        self.aircraft[aircraft.aircraft_id] = aircraft

    # ---- requests

    def add_request(self, request: MaintenanceRequest) -> None:
        other = self.find_active_request(request.aircraft_id)
        if self.enforce_constraints and request.is_active and other is not None:
            raise ActiveRequestExists("У ВС уже есть активная заявка")
        self.requests[request.request_id] = request

    def get_request(self, request_id: int) -> Optional[MaintenanceRequest]:
        return self.requests.get(request_id)

    def save_request(self, request: MaintenanceRequest) -> None:
        self._maybe_fail("save_request")
        self.requests[request.request_id] = request

    def find_active_request(self, aircraft_id: int) -> Optional[MaintenanceRequest]:
        return next((r for r in self.requests.values()
                     if r.aircraft_id == aircraft_id and r.is_active), None)

    def find_waiting_requests(self) -> list[MaintenanceRequest]:
        return [r for r in self.requests.values() if r.status == RequestStatus.WAITING_RESOURCES]

    # ---- work orders

    def add_work_order(self, work_order: WorkOrder) -> None:
        self.work_orders[work_order.work_order_id] = work_order

    def get_work_order(self, work_order_id: int) -> Optional[WorkOrder]:
        return self.work_orders.get(work_order_id)

    def find_work_order_by_request(self, request_id: int) -> Optional[WorkOrder]:
        return next((w for w in self.work_orders.values() if w.request_id == request_id), None)

    def save_work_order(self, work_order: WorkOrder) -> None:
        self._maybe_fail("save_work_order")
        self.work_orders[work_order.work_order_id] = work_order

    # ---- assignments

    def list_active_assignments(self, resource_id: int) -> list[Assignment]:
        return [a for a in self.assignments.values() if a.resource_id == resource_id and a.active]

    def assignments_of_request(self, request_id: int) -> list[Assignment]:
        return [a for a in self.assignments.values() if a.request_id == request_id and a.active]

    def add_assignment(self, assignment: Assignment) -> None:
        if self.enforce_constraints:
            for other in self.list_active_assignments(assignment.resource_id):
                if other.overlaps(assignment):
                    raise ResourceConflict("Нарушено ограничение хранилища: пересечение назначений")
        self.assignments[assignment.assignment_id] = assignment

    def save_assignment(self, assignment: Assignment) -> None:
        self.assignments[assignment.assignment_id] = assignment

    # ---- write-off acts

    def add_write_off_act(self, act: WriteOffAct) -> None:
        self.acts[act.act_id] = act

    def list_write_off_acts(self) -> list[WriteOffAct]:
        return list(self.acts.values())
