"""Shared helpers of the tests: world builder, snapshot of all data, log of actual results."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from mro_requests.clock import ManualClock
from mro_requests.config import build_service
from mro_requests.enums import ACTIVE_STATUSES
from mro_requests.repository import InMemoryRequestRepository, RequestRepository
from mro_requests.seed import load_seed
from mro_requests.service import RequestService

DISPATCHER = "U03"

# Actual results of the TC checks, filled by the tests and printed by run_tests.py.
ACTUAL: dict[str, str] = {}

# Table of the task (expected results are quoted from the task statement).
TC_TABLE = {
    "TC01": ("U01 отправляет пустую заявку SR03", "EMPTY_ITEMS, сохраняются состояние DRAFT и история"),
    "TC02": ("U01 добавляет пункт в SR03 и отправляет", "SUBMITTED, в истории один новый переход"),
    "TC03": ("U03 назначает SR01 специалисту T01", "ASSIGNED, активная нагрузка T01 равна 2"),
    "TC04": ("U03 назначает SR02 специалисту T01", "SKILL_MISMATCH, изменений нет"),
    "TC05": ("U03 назначает SR02 специалисту T02", "ASSIGNED, активная нагрузка T02 равна 1"),
    "TC06": ("U05 начинает работу над SR01", "FORBIDDEN, изменений нет"),
    "TC07": ("U04 начинает работу над SR01", "IN_PROGRESS, нагрузка прежняя: 2"),
    "TC08": ("U04 завершает SR01, не выполнив пункты", "Отказ (WORK_INCOMPLETE), состояние и история сохраняются"),
    "TC09": ("U04 выполняет все пункты и завершает SR01; затем завершает повторно",
             "Первое – COMPLETED, нагрузка 1; второе – INVALID_STATE, история не растёт"),
    "TC10": ("Сначала U02, затем U01 отменяет отправленную SR03",
             "Первое – FORBIDDEN; действие владельца – CANCELLED"),
    "TC11": ("Специалисту T02 с двумя активными заявками назначается третья", "LOAD_LIMIT, нагрузка остаётся 2"),
    "TC12": ("Через один контракт вызываются две политики срока",
             "Для STANDARD прибавляется 24 часа, для URGENT – 4 часа"),
}


@dataclass
class World:
    service: RequestService
    clock: ManualClock
    requests: RequestRepository


def build_world(repo_factory: Callable[[], RequestRepository] = InMemoryRequestRepository,
                policies=None) -> World:
    """Fresh system with the training data loaded through the service operations."""
    repo = repo_factory()
    service, clock = build_service(repo, policies)
    load_seed(service, clock)
    return World(service, clock, repo)


def snapshot(world: World) -> dict:
    """Everything a failed action must not change: state, executor, history, items, due date, load."""
    data = {}
    for r in world.requests.list_all():
        data[r.code] = (r.status, r.technician.code if r.technician else None, r.history, r.items, r.due_at)
    for code in ("T01", "T02"):
        data["load:" + code] = len(world.requests.find_by_technician(code, ACTIVE_STATUSES))
    return data


def load(world: World, technician_code: str) -> int:
    """Load computed independently of the service: by scanning all requests."""
    return sum(1 for r in world.requests.list_all()
               if r.technician is not None and r.technician.code == technician_code and r.status in ACTIVE_STATUSES)


def record(tc: str, text: str) -> None:
    ACTUAL[tc] = text
