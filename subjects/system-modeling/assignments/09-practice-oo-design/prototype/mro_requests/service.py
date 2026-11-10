"""RequestService: coordinates a scenario; the rules of a single request live in ServiceRequest.

The service
  * resolves the user (role comes from the directory, so it cannot be forged by the caller);
  * checks role-based access (who may call an operation at all);
  * collects facts from other objects (the technician's active load) and passes them to the domain;
  * loads and saves requests through the repository contract.

Order of checks in every operation:
  NOT_FOUND -> FORBIDDEN (role, then owner/assignee) -> INVALID_STATE
  -> operation conditions (EMPTY_ITEMS | SKILL_MISMATCH, LOAD_LIMIT | WORK_INCOMPLETE).
"""

from __future__ import annotations

from datetime import datetime
from typing import Callable, Iterable, Mapping

from .domain import ServiceRequest, StatusHistoryEntry, Technician, User, WorkItem
from .enums import ACTIVE_STATUSES, Category, Priority, Role
from .errors import DomainError, ErrorCode
from .repository import RequestRepository, UserDirectory
from .sla import SlaPolicy


class RequestService:
    def __init__(self, requests: RequestRepository, directory: UserDirectory,
                 policies: Mapping[Priority, SlaPolicy], clock: Callable[[], datetime]) -> None:
        self._requests = requests
        self._directory = directory
        self._policies = policies
        self._clock = clock

    # ------------------------------------------------------------------ directory
    def register_user(self, user_id: str, name: str, role: Role) -> User:
        if self._directory.get_user(user_id) is not None:
            raise DomainError(ErrorCode.INVALID_INPUT, f"user {user_id} already exists")
        user = User(user_id, name, role)
        self._directory.add_user(user)
        return user

    def register_technician(self, code: str, user_id: str, categories: Iterable[Category]) -> Technician:
        user = self._user(user_id)
        if self._directory.get_technician(code) is not None:
            raise DomainError(ErrorCode.INVALID_PROFILE, f"technician {code} already exists")
        if self._directory.find_technician_by_user(user_id) is not None:
            raise DomainError(ErrorCode.INVALID_PROFILE, f"user {user_id} already has a technician profile")
        technician = Technician(code, user, categories)
        self._directory.add_technician(technician)
        return technician

    # ------------------------------------------------------------------ request operations
    def create_request(self, actor_id: str, category: Category, priority: Priority,
                       aircraft: str, title: str) -> ServiceRequest:
        actor = self._user(actor_id)
        self._require_role(actor, Role.APPLICANT)
        policy = self._policies.get(priority)
        if policy is None:
            raise DomainError(ErrorCode.INVALID_INPUT, f"no SLA policy configured for {priority}")
        request = ServiceRequest(self._requests.next_code(), actor, category, priority,
                                 aircraft, title, self._clock(), policy)
        self._requests.add(request)
        return request

    def add_item(self, actor_id: str, request_code: str, description: str) -> WorkItem:
        actor, request = self._user(actor_id), self._request(request_code)
        item = request.add_item(actor, description)
        self._requests.save(request)
        return item

    def submit(self, actor_id: str, request_code: str) -> ServiceRequest:
        actor, request = self._user(actor_id), self._request(request_code)
        request.submit(actor, self._clock())
        self._requests.save(request)
        return request

    def cancel(self, actor_id: str, request_code: str) -> ServiceRequest:
        actor, request = self._user(actor_id), self._request(request_code)
        request.cancel(actor, self._clock())
        self._requests.save(request)
        return request

    def assign_technician(self, actor_id: str, request_code: str, technician_code: str) -> ServiceRequest:
        actor = self._user(actor_id)
        self._require_role(actor, Role.DISPATCHER)
        request = self._request(request_code)
        technician = self._technician(technician_code)
        active_load = len(self._requests.find_by_technician(technician_code, ACTIVE_STATUSES))
        request.assign(actor, technician, active_load, self._clock())
        self._requests.save(request)
        return request

    def start_work(self, actor_id: str, request_code: str) -> ServiceRequest:
        actor, request = self._user(actor_id), self._request(request_code)
        request.start(actor, self._clock())
        self._requests.save(request)
        return request

    def complete_item(self, actor_id: str, request_code: str, item_code: str) -> WorkItem:
        actor, request = self._user(actor_id), self._request(request_code)
        item = request.complete_item(actor, item_code)
        self._requests.save(request)
        return item

    def complete(self, actor_id: str, request_code: str) -> ServiceRequest:
        actor, request = self._user(actor_id), self._request(request_code)
        request.complete(actor, self._clock())
        self._requests.save(request)
        return request

    # ------------------------------------------------------------------ queries
    def view_history(self, actor_id: str, request_code: str) -> tuple[StatusHistoryEntry, ...]:
        actor, request = self._user(actor_id), self._request(request_code)
        if actor.role is not Role.DISPATCHER and not request.involves(actor):
            raise DomainError(ErrorCode.FORBIDDEN, f"{actor.id} may not view the history of {request_code}")
        return request.history

    def get_active_load(self, actor_id: str, technician_code: str) -> int:
        self._require_role(self._user(actor_id), Role.DISPATCHER)
        self._technician(technician_code)
        return len(self._requests.find_by_technician(technician_code, ACTIVE_STATUSES))

    def list_requests(self) -> list[ServiceRequest]:
        return self._requests.list_all()

    # ------------------------------------------------------------------ helpers
    def _user(self, user_id: str) -> User:
        user = self._directory.get_user(user_id)
        if user is None:
            raise DomainError(ErrorCode.NOT_FOUND, f"user {user_id} not found")
        return user

    def _technician(self, code: str) -> Technician:
        technician = self._directory.get_technician(code)
        if technician is None:
            raise DomainError(ErrorCode.NOT_FOUND, f"technician {code} not found")
        return technician

    def _request(self, code: str) -> ServiceRequest:
        request = self._requests.get(code)
        if request is None:
            raise DomainError(ErrorCode.NOT_FOUND, f"request {code} not found")
        return request

    @staticmethod
    def _require_role(actor: User, role: Role) -> None:
        if actor.role is not role:
            raise DomainError(ErrorCode.FORBIDDEN, f"{actor.id} has role {actor.role.value}, {role.value} required")
