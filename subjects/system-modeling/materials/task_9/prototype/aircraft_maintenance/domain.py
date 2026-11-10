"""Domain model of the aircraft maintenance prototype.

State-dependent rules live in the objects themselves (alternative B of the report):
Aircraft owns its status transitions and the release rule BR-07, WorkOrder owns the
readiness check, Resource owns the non-overlap rule BR-03.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum, IntEnum
from typing import Iterable, Optional


class Role(Enum):
    PLANNER = "планировщик"
    TECHNICIAN = "техник"
    CHIEF = "руководитель"
    ADMIN = "администратор"


class AircraftStatus(Enum):
    READY = "Готово к эксплуатации"
    SCHEDULED = "Запланировано обслуживание"
    IN_MAINTENANCE = "На обслуживании"
    RESTRICTED = "Ограничено/не допущено к полётам"
    WRITTEN_OFF = "Списано"


class RequestStatus(Enum):
    NEW = "Новая"
    NEEDS_CLARIFICATION = "Требует уточнения"
    SCHEDULED = "Запланирована"
    WAITING_RESOURCES = "Ожидает ресурсов"
    IN_PROGRESS = "В работе"
    COMPLETED = "Завершена"
    CANCELLED = "Отменена"


class WorkOrderStatus(Enum):
    OPEN = "Открыт"
    IN_PROGRESS = "В работе"
    WORK_DONE = "Работы завершены"
    CLOSED = "Закрыт"
    TERMINATED = "Прекращён"


class MaintenanceType(Enum):
    PLANNED = "плановое"
    UNPLANNED = "внеплановое"


class Priority(IntEnum):
    NORMAL = 1
    HIGH = 2
    URGENT = 3


class Severity(Enum):
    MINOR = "некритичный"
    CRITICAL = "критичный"


class StageStatus(Enum):
    OPEN = "открыт"
    DONE = "выполнен"


class DefectStatus(Enum):
    OPEN = "открыт"
    RESOLVED = "устранён"


class ResourceKind(Enum):
    SPECIALIST = "специалист"
    EQUIPMENT = "оборудование"
    HANGAR_SLOT = "место в ангаре"


class Verdict(Enum):
    FIT = "годно"
    UNFIT = "негодно"


# ---------------------------------------------------------------- errors

class DomainError(Exception):
    """Base class of business-rule violations; the message is shown to the user."""


class ValidationError(DomainError):
    pass


class AccessDenied(DomainError):
    pass


class InvalidTransition(DomainError):
    pass


class ActiveRequestExists(DomainError):
    pass


class ResourceConflict(DomainError):
    pass


class ReleaseDenied(DomainError):
    def __init__(self, reasons: list[str]):
        super().__init__("Допуск запрещён: " + "; ".join(reasons))
        self.reasons = reasons


class StorageError(Exception):
    """Technical failure of the storage (not a business-rule violation)."""


# ---------------------------------------------------------------- employees and resources

@dataclass
class Employee:
    employee_id: int
    full_name: str
    role: Role
    blocked: bool = False


@dataclass
class Resource:
    """Bookable item: specialist, equipment unit or hangar slot (one rule BR-03 for all)."""
    resource_id: int
    kind: ResourceKind
    name: str
    qualification: Optional[str] = None
    employee_id: Optional[int] = None
    available: bool = True

    def book(self, active: Iterable["Assignment"], assignment_id: int, request_id: int,
             start: datetime, end: datetime) -> "Assignment":
        """BR-03: no two active assignments of one resource may overlap."""
        if not self.available:
            raise ResourceConflict(f"Ресурс «{self.name}» недоступен")
        new = Assignment(assignment_id, self.resource_id, request_id, start, end)
        for other in active:
            if other.active and other.overlaps(new):
                raise ResourceConflict(f"Ресурс «{self.name}» занят в выбранный интервал")
        return new


@dataclass
class Assignment:
    assignment_id: int
    resource_id: int
    request_id: int
    start: datetime
    end: datetime
    active: bool = True

    def __post_init__(self) -> None:
        if not self.start < self.end:
            raise ValidationError("Начало назначения должно быть раньше окончания")

    def overlaps(self, other: "Assignment") -> bool:
        # half-open intervals: [10:00, 12:00) and [12:00, 14:00) do not overlap
        return self.start < other.end and other.start < self.end

    def cancel(self) -> None:
        self.active = False


# ---------------------------------------------------------------- aircraft

_AIRCRAFT_TRANSITIONS = {
    (AircraftStatus.READY, AircraftStatus.SCHEDULED),
    (AircraftStatus.SCHEDULED, AircraftStatus.READY),
    (AircraftStatus.SCHEDULED, AircraftStatus.IN_MAINTENANCE),
    (AircraftStatus.RESTRICTED, AircraftStatus.IN_MAINTENANCE),
    (AircraftStatus.IN_MAINTENANCE, AircraftStatus.READY),
    (AircraftStatus.READY, AircraftStatus.RESTRICTED),
    (AircraftStatus.SCHEDULED, AircraftStatus.RESTRICTED),
    (AircraftStatus.READY, AircraftStatus.WRITTEN_OFF),
    (AircraftStatus.SCHEDULED, AircraftStatus.WRITTEN_OFF),
    (AircraftStatus.IN_MAINTENANCE, AircraftStatus.WRITTEN_OFF),
    (AircraftStatus.RESTRICTED, AircraftStatus.WRITTEN_OFF),
}


@dataclass
class Aircraft:
    aircraft_id: int
    tail_number: str
    model: str
    serial_number: str
    commissioned: date
    status: AircraftStatus = AircraftStatus.READY
    next_maintenance_due: Optional[date] = None

    def _move(self, new: AircraftStatus) -> None:
        if (self.status, new) not in _AIRCRAFT_TRANSITIONS:
            raise InvalidTransition(f"Переход ВС «{self.status.value}» → «{new.value}» запрещён")
        self.status = new

    def reserve_maintenance(self) -> None:
        """Maintenance is scheduled; a restricted aircraft stays restricted."""
        if self.status != AircraftStatus.RESTRICTED:
            self._move(AircraftStatus.SCHEDULED)

    def cancel_reservation(self) -> None:
        if self.status == AircraftStatus.SCHEDULED:
            self._move(AircraftStatus.READY)

    def start_maintenance(self) -> None:
        self._move(AircraftStatus.IN_MAINTENANCE)

    def restrict(self) -> None:
        self._move(AircraftStatus.RESTRICTED)

    def release(self, work_order: "WorkOrder", next_due: date) -> None:
        """BR-07: the status 'Готово к эксплуатации' only for a finished, concluded work order."""
        reasons = []
        if self.status != AircraftStatus.IN_MAINTENANCE:
            reasons.append(f"ВС в состоянии «{self.status.value}», а не «На обслуживании»")
        reasons += work_order.release_blockers()
        if reasons:
            raise ReleaseDenied(reasons)
        self._move(AircraftStatus.READY)
        self.next_maintenance_due = next_due

    def write_off(self) -> None:
        self._move(AircraftStatus.WRITTEN_OFF)

    def is_overdue(self, today: date) -> bool:
        return self.next_maintenance_due is not None and self.next_maintenance_due < today

    def is_due_soon(self, today: date, days: int) -> bool:
        return (self.next_maintenance_due is not None
                and 0 <= (self.next_maintenance_due - today).days <= days)


# ---------------------------------------------------------------- request

_ACTIVE_REQUEST = (RequestStatus.NEW, RequestStatus.NEEDS_CLARIFICATION, RequestStatus.SCHEDULED,
                   RequestStatus.WAITING_RESOURCES, RequestStatus.IN_PROGRESS)

_REQUEST_TRANSITIONS = {
    (RequestStatus.NEW, RequestStatus.NEEDS_CLARIFICATION),
    (RequestStatus.NEEDS_CLARIFICATION, RequestStatus.NEW),
    (RequestStatus.NEW, RequestStatus.SCHEDULED),
    (RequestStatus.NEW, RequestStatus.WAITING_RESOURCES),
    (RequestStatus.WAITING_RESOURCES, RequestStatus.SCHEDULED),
    (RequestStatus.WAITING_RESOURCES, RequestStatus.WAITING_RESOURCES),
    (RequestStatus.SCHEDULED, RequestStatus.IN_PROGRESS),
    (RequestStatus.IN_PROGRESS, RequestStatus.COMPLETED),
    (RequestStatus.NEW, RequestStatus.CANCELLED),
    (RequestStatus.NEEDS_CLARIFICATION, RequestStatus.CANCELLED),
    (RequestStatus.SCHEDULED, RequestStatus.CANCELLED),
    (RequestStatus.WAITING_RESOURCES, RequestStatus.CANCELLED),
    (RequestStatus.IN_PROGRESS, RequestStatus.CANCELLED),
}


@dataclass
class MaintenanceRequest:
    request_id: int
    aircraft_id: int
    author_id: int
    mtype: MaintenanceType
    priority: Priority
    desired_date: Optional[date]
    description: str
    status: RequestStatus = RequestStatus.NEW
    missing: list[str] = field(default_factory=list)

    def _move(self, new: RequestStatus) -> None:
        if (self.status, new) not in _REQUEST_TRANSITIONS:
            raise InvalidTransition(f"Переход заявки «{self.status.value}» → «{new.value}» запрещён")
        self.status = new

    @property
    def is_active(self) -> bool:
        return self.status in _ACTIVE_REQUEST

    def same_content(self, author_id: int, mtype: MaintenanceType,
                     desired_date: Optional[date], description: str) -> bool:
        return (self.author_id, self.mtype, self.desired_date, self.description) == \
               (author_id, mtype, desired_date, description)

    def mark_needs_clarification(self, missing: list[str]) -> None:
        self.missing = list(missing)
        if self.status != RequestStatus.NEEDS_CLARIFICATION:
            self._move(RequestStatus.NEEDS_CLARIFICATION)

    def mark_clarified(self) -> None:
        self.missing = []
        self._move(RequestStatus.NEW)

    def schedule(self) -> None:
        self._move(RequestStatus.SCHEDULED)

    def wait_for_resources(self) -> None:
        self._move(RequestStatus.WAITING_RESOURCES)

    def start(self) -> None:
        self._move(RequestStatus.IN_PROGRESS)

    def complete(self) -> None:
        self._move(RequestStatus.COMPLETED)

    def cancel(self) -> None:
        self._move(RequestStatus.CANCELLED)


# ---------------------------------------------------------------- work order

@dataclass
class Stage:
    stage_id: int
    name: str
    mandatory: bool
    executor_id: int
    status: StageStatus = StageStatus.OPEN
    result: str = ""


@dataclass
class Defect:
    defect_id: int
    description: str
    severity: Severity
    status: DefectStatus = DefectStatus.OPEN


@dataclass
class PartUsage:
    part_number: str
    quantity: int


@dataclass(frozen=True)
class Conclusion:
    """Immutable (BR-12): a new check creates a new conclusion."""
    conclusion_id: int
    author_id: int
    verdict: Verdict
    basis: str
    stages_covered: int
    issued_at: datetime


@dataclass(frozen=True)
class WriteOffAct:
    act_id: int
    aircraft_id: int
    reason: str
    document_ref: str
    approved_by: int
    issued_at: datetime


@dataclass
class WorkOrder:
    work_order_id: int
    request_id: int
    aircraft_id: int
    status: WorkOrderStatus = WorkOrderStatus.OPEN
    stages: list[Stage] = field(default_factory=list)
    defects: list[Defect] = field(default_factory=list)
    parts: list[PartUsage] = field(default_factory=list)
    conclusions: list[Conclusion] = field(default_factory=list)

    def _require(self, *allowed: WorkOrderStatus) -> None:
        if self.status not in allowed:
            raise InvalidTransition(f"Операция недоступна для заказ-наряда «{self.status.value}»")

    def _next(self, items: list, attr: str) -> int:
        return max((getattr(i, attr) for i in items), default=0) + 1

    def add_stage(self, name: str, mandatory: bool, executor_id: int) -> Stage:
        if not name.strip():
            raise ValidationError("У этапа должно быть название")
        self._require(WorkOrderStatus.OPEN, WorkOrderStatus.IN_PROGRESS, WorkOrderStatus.WORK_DONE)
        stage = Stage(self._next(self.stages, "stage_id"), name, mandatory, executor_id)
        self.stages.append(stage)
        if self.status == WorkOrderStatus.WORK_DONE and mandatory:
            self.status = WorkOrderStatus.IN_PROGRESS
        return stage

    def start(self) -> None:
        self._require(WorkOrderStatus.OPEN)
        self.status = WorkOrderStatus.IN_PROGRESS

    def complete_stage(self, stage_id: int, executor_id: int, result: str) -> None:
        """BR-11: only the assigned executor closes a stage."""
        self._require(WorkOrderStatus.IN_PROGRESS)
        stage = next((s for s in self.stages if s.stage_id == stage_id), None)
        if stage is None:
            raise ValidationError("Этап не найден")
        if stage.executor_id != executor_id:
            raise AccessDenied("Этап закрывает только назначенный исполнитель")
        if stage.status == StageStatus.DONE:
            raise InvalidTransition("Этап уже выполнен")
        stage.status, stage.result = StageStatus.DONE, result
        if all(s.status == StageStatus.DONE for s in self.stages if s.mandatory):
            self.status = WorkOrderStatus.WORK_DONE

    def register_defect(self, description: str, severity: Severity) -> Defect:
        if not description.strip():
            raise ValidationError("Описание дефекта обязательно")
        self._require(WorkOrderStatus.IN_PROGRESS, WorkOrderStatus.WORK_DONE)
        defect = Defect(self._next(self.defects, "defect_id"), description, severity)
        self.defects.append(defect)
        return defect

    def resolve_defect(self, defect_id: int) -> None:
        self._require(WorkOrderStatus.IN_PROGRESS, WorkOrderStatus.WORK_DONE)
        defect = next((d for d in self.defects if d.defect_id == defect_id), None)
        if defect is None:
            raise ValidationError("Дефект не найден")
        defect.status = DefectStatus.RESOLVED

    def add_part(self, part_number: str, quantity: int) -> None:
        if not part_number.strip() or quantity <= 0:
            raise ValidationError("Нужны номер детали и количество больше 0")
        self._require(WorkOrderStatus.IN_PROGRESS, WorkOrderStatus.WORK_DONE)
        self.parts.append(PartUsage(part_number, quantity))

    def issue_conclusion(self, author_id: int, verdict: Verdict, basis: str,
                         now: datetime) -> Conclusion:
        if not basis.strip():
            raise ValidationError("Заключение требует основания")
        self._require(WorkOrderStatus.WORK_DONE)
        conclusion = Conclusion(self._next(self.conclusions, "conclusion_id"), author_id,
                                verdict, basis, len(self.stages), now)
        self.conclusions.append(conclusion)
        return conclusion

    def release_blockers(self) -> list[str]:
        """Reasons why the aircraft cannot be released after this work order (empty = allowed)."""
        reasons = []
        if self.status != WorkOrderStatus.WORK_DONE:
            reasons.append(f"заказ-наряд в состоянии «{self.status.value}», работы не завершены")
        open_stages = [s.name for s in self.stages if s.mandatory and s.status != StageStatus.DONE]
        if open_stages:
            reasons.append("не выполнены обязательные этапы: " + ", ".join(open_stages))
        critical = [d.description for d in self.defects
                    if d.severity == Severity.CRITICAL and d.status != DefectStatus.RESOLVED]
        if critical:
            reasons.append("не устранены критичные дефекты: " + ", ".join(critical))
        last = self.conclusions[-1] if self.conclusions else None
        if last is None:
            reasons.append("нет заключения о годности")
        elif last.verdict != Verdict.FIT:
            reasons.append("последнее заключение — «негодно»")
        elif last.stages_covered != len(self.stages):
            reasons.append("заключение выдано до добавления этапов, нужно новое")
        return reasons

    def close(self) -> None:
        self._require(WorkOrderStatus.WORK_DONE)
        self.status = WorkOrderStatus.CLOSED

    def terminate(self) -> None:
        """Write-off: the order is closed without release."""
        if self.status not in (WorkOrderStatus.CLOSED, WorkOrderStatus.TERMINATED):
            self.status = WorkOrderStatus.TERMINATED


@dataclass(frozen=True)
class AuditRecord:
    seq: int
    at: datetime
    user_id: Optional[int]
    action: str
    object_ref: str
    outcome: str
    detail: str
