"""Storage contracts and their in-memory implementations.

The domain and the service know only RequestRepository and UserDirectory. Two implementations
of RequestRepository show that the way of storing can be changed without touching domain rules.
"""

from __future__ import annotations

import copy
from abc import ABC, abstractmethod
from typing import Collection, Optional

from .domain import ServiceRequest, Technician, User
from .enums import Status


class RequestRepository(ABC):
    """Contract for storing requests."""

    @abstractmethod
    def next_code(self) -> str:
        """Code for the next request (no side effects until add is called)."""

    @abstractmethod
    def add(self, request: ServiceRequest) -> None: ...

    @abstractmethod
    def get(self, code: str) -> Optional[ServiceRequest]: ...

    @abstractmethod
    def save(self, request: ServiceRequest) -> None: ...

    @abstractmethod
    def find_by_technician(self, technician_code: str, statuses: Collection[Status]) -> list[ServiceRequest]: ...

    @abstractmethod
    def list_all(self) -> list[ServiceRequest]: ...


class UserDirectory(ABC):
    """Contract for storing users and technician profiles."""

    @abstractmethod
    def add_user(self, user: User) -> None: ...

    @abstractmethod
    def get_user(self, user_id: str) -> Optional[User]: ...

    @abstractmethod
    def add_technician(self, technician: Technician) -> None: ...

    @abstractmethod
    def get_technician(self, code: str) -> Optional[Technician]: ...

    @abstractmethod
    def find_technician_by_user(self, user_id: str) -> Optional[Technician]: ...


class InMemoryRequestRepository(RequestRepository):
    """Keeps the request objects themselves in a dict."""

    def __init__(self) -> None:
        self._items: dict[str, ServiceRequest] = {}

    def next_code(self) -> str:
        return f"SR{len(self._items) + 1:02d}"

    def add(self, request: ServiceRequest) -> None:
        self._items[request.code] = request

    def get(self, code: str) -> Optional[ServiceRequest]:
        return self._items.get(code)

    def save(self, request: ServiceRequest) -> None:
        self._items[request.code] = request

    def find_by_technician(self, technician_code: str, statuses: Collection[Status]) -> list[ServiceRequest]:
        return [r for r in self._items.values()
                if r.technician is not None and r.technician.code == technician_code and r.status in statuses]

    def list_all(self) -> list[ServiceRequest]:
        return list(self._items.values())


class CopyOnSaveRequestRepository(RequestRepository):
    """Stores and returns copies, like a database that hands out rows by value.

    A request changed by the caller but not saved does not reach the storage.
    """

    def __init__(self) -> None:
        self._items: dict[str, ServiceRequest] = {}

    def next_code(self) -> str:
        return f"SR{len(self._items) + 1:02d}"

    def add(self, request: ServiceRequest) -> None:
        self._items[request.code] = copy.deepcopy(request)

    def get(self, code: str) -> Optional[ServiceRequest]:
        stored = self._items.get(code)
        return copy.deepcopy(stored) if stored is not None else None

    def save(self, request: ServiceRequest) -> None:
        self._items[request.code] = copy.deepcopy(request)

    def find_by_technician(self, technician_code: str, statuses: Collection[Status]) -> list[ServiceRequest]:
        return [copy.deepcopy(r) for r in self._items.values()
                if r.technician is not None and r.technician.code == technician_code and r.status in statuses]

    def list_all(self) -> list[ServiceRequest]:
        return [copy.deepcopy(r) for r in self._items.values()]


class InMemoryUserDirectory(UserDirectory):
    def __init__(self) -> None:
        self._users: dict[str, User] = {}
        self._technicians: dict[str, Technician] = {}

    def add_user(self, user: User) -> None:
        self._users[user.id] = user

    def get_user(self, user_id: str) -> Optional[User]:
        return self._users.get(user_id)

    def add_technician(self, technician: Technician) -> None:
        self._technicians[technician.code] = technician

    def get_technician(self, code: str) -> Optional[Technician]:
        return self._technicians.get(code)

    def find_technician_by_user(self, user_id: str) -> Optional[Technician]:
        for technician in self._technicians.values():
            if technician.user.id == user_id:
                return technician
        return None
