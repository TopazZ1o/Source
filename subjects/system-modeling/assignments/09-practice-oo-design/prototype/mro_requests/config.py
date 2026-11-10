"""Configuration: which SLA policy serves which priority, and how the system is wired together.

This is the only place that maps a priority code to a policy object.
"""

from __future__ import annotations

from datetime import datetime
from typing import Mapping, Optional

from .clock import ManualClock
from .enums import Priority
from .repository import InMemoryRequestRepository, InMemoryUserDirectory, RequestRepository
from .service import RequestService
from .sla import AcceleratedSlaPolicy, SlaPolicy, StandardSlaPolicy, UrgentSlaPolicy

START_TIME = datetime(2026, 11, 16, 9, 0)


def default_policies() -> dict[Priority, SlaPolicy]:
    return {
        Priority.STANDARD: StandardSlaPolicy(),
        Priority.URGENT: UrgentSlaPolicy(),
        Priority.ACCELERATED: AcceleratedSlaPolicy(),
    }


def build_service(requests: Optional[RequestRepository] = None,
                  policies: Optional[Mapping[Priority, SlaPolicy]] = None) -> tuple[RequestService, ManualClock]:
    """Wire the service with in-memory storage. Returns the service and its manual clock."""
    clock = ManualClock(START_TIME)
    service = RequestService(
        requests if requests is not None else InMemoryRequestRepository(),
        InMemoryUserDirectory(),
        policies if policies is not None else default_policies(),
        clock,
    )
    return service, clock
