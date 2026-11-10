"""Domain objects: User, Technician, WorkItem, StatusHistoryEntry, ServiceRequest.

ServiceRequest owns its state, work items and history. Every public operation first
checks all conditions (in the documented order) and only then changes the object, so a
rejected action leaves the request untouched (BR-07).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from typing import Iterable, Optional

from .enums import ACTIVE_STATUSES, Category, Event, Priority, Role, Status
from .errors import DomainError, ErrorCode
from .sla import SlaPolicy


@dataclass(frozen=True)
class User:
    id: str
    name: str
    role: Role


@dataclass(frozen=True)
class WorkItem:
    """A work point of a request. Immutable: the request replaces it when it is marked done."""
    code: str
    request_code: str
    description: str
    done: bool = False


@dataclass(frozen=True)
class StatusHistoryEntry:
    """One record of the history. from_status is None for the initial DRAFT record."""
    request_code: str
    from_status: Optional[Status]
    to_status: Status
    actor_id: str
    at: datetime


class Technician:
    """Technician profile: one user, served categories and the active-request limit (BR-03)."""

    MAX_ACTIVE_REQUESTS = 2

    def __init__(self, code: str, user: User, categories: Iterable[Category]) -> None:
        cats = frozenset(categories)
        if user.role is not Role.TECHNICIAN:
            raise DomainError(ErrorCode.INVALID_PROFILE, f"user {user.id} is not a technician")
        if not cats:
            raise DomainError(ErrorCode.INVALID_PROFILE, f"technician {code} serves no category")
        self._code = code
        self._user = user
        self._categories = cats

    @property
    def code(self) -> str:
        return self._code

    @property
    def user(self) -> User:
        return self._user

    @property
    def categories(self) -> frozenset[Category]:
        return self._categories

    def can_serve(self, category: Category) -> bool:
        return category in self._categories

    def has_capacity(self, active_load: int) -> bool:
        return active_load < self.MAX_ACTIVE_REQUESTS


# State table of the request (BR-02..BR-06). Anything not listed is rejected with INVALID_STATE.
_TRANSITIONS: dict[tuple[Status, Event], Status] = {
    (Status.DRAFT, Event.SUBMIT): Status.SUBMITTED,
    (Status.DRAFT, Event.CANCEL): Status.CANCELLED,
    (Status.SUBMITTED, Event.CANCEL): Status.CANCELLED,
    (Status.SUBMITTED, Event.ASSIGN): Status.ASSIGNED,
    (Status.ASSIGNED, Event.START): Status.IN_PROGRESS,
    (Status.IN_PROGRESS, Event.COMPLETE): Status.COMPLETED,
}


class ServiceRequest:
    """A request about an aircraft fault. Identity: code. State: status, items, technician, history."""

    def __init__(self, code: str, owner: User, category: Category, priority: Priority,
                 aircraft: str, title: str, created_at: datetime, sla_policy: SlaPolicy) -> None:
        if owner.role is not Role.APPLICANT:
            raise DomainError(ErrorCode.FORBIDDEN, f"user {owner.id} is not an applicant")
        for name, value in (("aircraft", aircraft), ("title", title)):
            if not value.strip():
                raise DomainError(ErrorCode.INVALID_INPUT, f"{name} must not be empty")
        self._code = code
        self._owner = owner
        self._category = category
        self._priority = priority
        self._aircraft = aircraft
        self._title = title
        self._created_at = created_at
        self._due_at = sla_policy.calculate_due_at(created_at)   # the policy is a dependency
        self._status = Status.DRAFT
        self._technician: Optional[Technician] = None
        self._items: list[WorkItem] = []
        self._history: list[StatusHistoryEntry] = []
        self._history.append(StatusHistoryEntry(code, None, Status.DRAFT, owner.id, created_at))

    # ------------------------------------------------------------------ read access
    @property
    def code(self) -> str:
        return self._code

    @property
    def owner(self) -> User:
        return self._owner

    @property
    def category(self) -> Category:
        return self._category

    @property
    def priority(self) -> Priority:
        return self._priority

    @property
    def aircraft(self) -> str:
        return self._aircraft

    @property
    def title(self) -> str:
        return self._title

    @property
    def created_at(self) -> datetime:
        return self._created_at

    @property
    def due_at(self) -> datetime:
        return self._due_at

    @property
    def status(self) -> Status:
        return self._status

    @property
    def technician(self) -> Optional[Technician]:
        """Executor; kept after COMPLETED as a historical reference."""
        return self._technician

    @property
    def items(self) -> tuple[WorkItem, ...]:
        return tuple(self._items)

    @property
    def history(self) -> tuple[StatusHistoryEntry, ...]:
        return tuple(self._history)

    @property
    def is_active(self) -> bool:
        return self._status in ACTIVE_STATUSES

    def involves(self, user: User) -> bool:
        """True for the owner and for the assigned technician."""
        return user.id == self._owner.id or self._is_assignee(user)

    # ------------------------------------------------------------------ operations
    # Order of checks everywhere: FORBIDDEN -> INVALID_STATE -> operation-specific conditions.

    def add_item(self, actor: User, description: str) -> WorkItem:
        self._require_owner(actor)
        if self._status is not Status.DRAFT:
            raise DomainError(ErrorCode.INVALID_STATE, "items can be added only in DRAFT")
        if not description.strip():
            raise DomainError(ErrorCode.INVALID_INPUT, "item description must not be empty")
        item = WorkItem(f"{self._code}-W{len(self._items) + 1}", self._code, description.strip())
        self._items.append(item)
        return item

    def submit(self, actor: User, at: datetime) -> None:
        self._require_owner(actor)
        target = self._next_status(Event.SUBMIT)
        if not self._items:
            raise DomainError(ErrorCode.EMPTY_ITEMS, "a request without work items cannot be submitted")
        self._move(target, actor, at)

    def cancel(self, actor: User, at: datetime) -> None:
        self._require_owner(actor)
        self._move(self._next_status(Event.CANCEL), actor, at)

    def assign(self, actor: User, technician: Technician, active_load: int, at: datetime) -> None:
        """actor is the dispatcher (the role was checked by the service); active_load is given by it."""
        target = self._next_status(Event.ASSIGN)
        if not technician.can_serve(self._category):
            raise DomainError(ErrorCode.SKILL_MISMATCH,
                              f"technician {technician.code} does not serve {self._category.value}")
        if not technician.has_capacity(active_load):
            raise DomainError(ErrorCode.LOAD_LIMIT,
                              f"technician {technician.code} already has {active_load} active requests")
        self._technician = technician
        self._move(target, actor, at)

    def start(self, actor: User, at: datetime) -> None:
        self._require_assignee(actor)
        self._move(self._next_status(Event.START), actor, at)

    def complete_item(self, actor: User, item_code: str) -> WorkItem:
        """Mark a work item done. This is not a state transition: no history record, no state change."""
        self._require_assignee(actor)
        if self._status is not Status.IN_PROGRESS:
            raise DomainError(ErrorCode.INVALID_STATE, "items can be marked only in IN_PROGRESS")
        for index, item in enumerate(self._items):
            if item.code == item_code:
                if item.done:
                    raise DomainError(ErrorCode.INVALID_STATE, f"item {item_code} is already done")
                done = replace(item, done=True)
                self._items[index] = done
                return done
        raise DomainError(ErrorCode.NOT_FOUND, f"item {item_code} not found in {self._code}")

    def complete(self, actor: User, at: datetime) -> None:
        self._require_assignee(actor)
        target = self._next_status(Event.COMPLETE)
        if not all(item.done for item in self._items):
            raise DomainError(ErrorCode.WORK_INCOMPLETE, "not all work items are done")
        self._move(target, actor, at)

    # ------------------------------------------------------------------ internals
    def _is_assignee(self, user: User) -> bool:
        return self._technician is not None and self._technician.user.id == user.id

    def _require_owner(self, actor: User) -> None:
        if actor.id != self._owner.id:
            raise DomainError(ErrorCode.FORBIDDEN, f"{actor.id} is not the owner of {self._code}")

    def _require_assignee(self, actor: User) -> None:
        if not self._is_assignee(actor):
            raise DomainError(ErrorCode.FORBIDDEN, f"{actor.id} is not the assigned technician of {self._code}")

    def _next_status(self, event: Event) -> Status:
        target = _TRANSITIONS.get((self._status, event))
        if target is None:
            raise DomainError(ErrorCode.INVALID_STATE,
                              f"event '{event.value}' is not allowed in state {self._status.value}")
        return target

    def _move(self, target: Status, actor: User, at: datetime) -> None:
        """The only place where the state changes; always adds exactly one history record (BR-07)."""
        self._history.append(StatusHistoryEntry(self._code, self._status, target, actor.id, at))
        self._status = target

    def __repr__(self) -> str:
        return f"ServiceRequest({self._code}, {self._status.value})"
