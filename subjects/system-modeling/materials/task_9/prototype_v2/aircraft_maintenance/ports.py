"""Interfaces (ports) between the domain services and the outside world."""

from __future__ import annotations

from abc import ABC, abstractmethod
from contextlib import AbstractContextManager
from typing import Optional

from .domain import (Aircraft, Assignment, AuditRecord, Employee, MaintenanceRequest, Resource,
                     WorkOrder, WriteOffAct)


class Notifier(ABC):
    """Contract of a notification channel (interface 'КаналУведомления')."""

    @abstractmethod
    def send(self, recipient_id: int, subject: str, text: str) -> None:
        """Deliver a message; may raise on channel failure."""


class AuditLog(ABC):
    """Append-only journal (interface 'ЖурналАудита'): there is deliberately no update or delete."""

    @abstractmethod
    def append(self, user_id: Optional[int], action: str, object_ref: str,
               outcome: str, detail: str = "") -> AuditRecord: ...

    @abstractmethod
    def records(self) -> tuple[AuditRecord, ...]: ...


class DataStore(ABC):
    """Contract of the storage (interface 'ХранилищеДанных')."""

    @abstractmethod
    def transaction(self) -> AbstractContextManager:
        """All changes inside the block are saved together or not at all."""

    @abstractmethod
    def next_id(self, kind: str) -> int: ...

    @abstractmethod
    def add_employee(self, employee: Employee) -> None: ...

    @abstractmethod
    def get_employee(self, employee_id: int) -> Optional[Employee]: ...

    @abstractmethod
    def list_employees(self) -> list[Employee]: ...

    @abstractmethod
    def add_aircraft(self, aircraft: Aircraft) -> None: ...

    @abstractmethod
    def get_aircraft(self, aircraft_id: int) -> Optional[Aircraft]: ...

    @abstractmethod
    def list_aircraft(self) -> list[Aircraft]: ...

    @abstractmethod
    def save_aircraft(self, aircraft: Aircraft) -> None: ...

    @abstractmethod
    def add_resource(self, resource: Resource) -> None: ...

    @abstractmethod
    def get_resource(self, resource_id: int) -> Optional[Resource]: ...

    @abstractmethod
    def add_request(self, request: MaintenanceRequest) -> None: ...

    @abstractmethod
    def get_request(self, request_id: int) -> Optional[MaintenanceRequest]: ...

    @abstractmethod
    def save_request(self, request: MaintenanceRequest) -> None: ...

    @abstractmethod
    def find_active_request(self, aircraft_id: int) -> Optional[MaintenanceRequest]: ...

    @abstractmethod
    def find_waiting_requests(self) -> list[MaintenanceRequest]: ...

    @abstractmethod
    def add_work_order(self, work_order: WorkOrder) -> None: ...

    @abstractmethod
    def get_work_order(self, work_order_id: int) -> Optional[WorkOrder]: ...

    @abstractmethod
    def find_work_order_by_request(self, request_id: int) -> Optional[WorkOrder]: ...

    @abstractmethod
    def save_work_order(self, work_order: WorkOrder) -> None: ...

    @abstractmethod
    def list_active_assignments(self, resource_id: int) -> list[Assignment]: ...

    @abstractmethod
    def assignments_of_request(self, request_id: int) -> list[Assignment]: ...

    @abstractmethod
    def add_assignment(self, assignment: Assignment) -> None: ...

    @abstractmethod
    def save_assignment(self, assignment: Assignment) -> None: ...

    @abstractmethod
    def add_write_off_act(self, act: WriteOffAct) -> None: ...

    @abstractmethod
    def list_write_off_acts(self) -> list[WriteOffAct]: ...
