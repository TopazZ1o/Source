"""Reusable scenarios: the P01 chain of task 4 and the parallel reservation of TEST01 (task 5)."""

from __future__ import annotations

import tempfile
import threading
import time
from pathlib import Path
from typing import Callable

from .results import Result, TechnicalError
from .seed import WAREHOUSE, build_test01_db
from .service import InventoryService, REQUESTER, STOREKEEPER


def state(service: InventoryService, product: str = "P01", reservation: str = "RES01") -> dict:
    """OH, R, B, A of the product and the remaining quantity of the reservation (None if it does not exist)."""
    pos = service.position(product, WAREHOUSE)
    return {"oh": pos["oh"], "r": pos["r"], "b": pos["b"], "a": pos["a"],
            "res": service.reservation_remaining(reservation)}


def p01_chain(service: InventoryService) -> list[tuple[str, str, Result, dict]]:
    """Six operations of task 4 on P01 from the initial state. Returns (step, action, result, state after)."""
    w = WAREHOUSE
    steps: list[tuple[str, str, Callable[[], Result]]] = [
        ("1", "Приём 40 шт., ключ IN01", lambda: service.receive("IN01", STOREKEEPER, "P01", w, 40)),
        ("2", "Резерв 60 шт., ключ RES01", lambda: service.reserve("RES01", REQUESTER, "P01", w, 60, "WO-2001")),
        ("3", "Повтор RES01 (те же параметры)", lambda: service.reserve("RES01", REQUESTER, "P01", w, 60, "WO-2001")),
        ("4", "Резерв 500 шт., ключ RES02", lambda: service.reserve("RES02", REQUESTER, "P01", w, 500, "WO-2002")),
        ("5", "Выдача 20 шт. из RES01, ключ OUT01", lambda: service.issue("OUT01", STOREKEEPER, "RES01", 20)),
        ("6", "Освобождение остатка RES01, ключ CANCEL01", lambda: service.release("CANCEL01", REQUESTER, "RES01")),
    ]
    rows = []
    for step, action, call in steps:
        result = call()
        rows.append((step, action, result, state(service)))
    return rows


def parallel_reservation(workdir: str | Path, workers: int = 3, qty: int = 5, hold: float = 0.05,
                         busy_timeout: float = 10.0) -> dict:
    """Three independent connections reserve `qty` of TEST01 (OH = 12) after a common start barrier.

    hold keeps the write lock inside each transaction so that the other requests visibly wait.
    Returns the journal (key, start and end offsets, result, before, after) and the final state.
    """
    db = Path(workdir) / "test01.db"
    build_test01_db(db)
    ref: list[float] = []
    barrier = threading.Barrier(workers, action=lambda: ref.append(time.perf_counter()))
    journal: list[dict] = []
    lock = threading.Lock()

    def worker(i: int) -> None:
        service = InventoryService(db, busy_timeout=busy_timeout, hold_seconds=hold)   # own connection
        key = f"T-RES-{i}"
        try:
            barrier.wait()
            t0 = time.perf_counter() - ref[0]
            try:
                result = service.reserve(key, REQUESTER, "TEST01", WAREHOUSE, qty, f"WO-T{i}")
                entry = {"key": key, "status": result.status, "before": result.data.get("before"),
                         "after": result.data.get("after")}
            except TechnicalError as error:
                entry = {"key": key, "status": "TECHNICAL:" + error.code, "before": None, "after": None}
            entry.update(start=t0, end=time.perf_counter() - ref[0])
            with lock:
                journal.append(entry)
        finally:
            service.close()

    threads = [threading.Thread(target=worker, args=(i,), name=f"worker-{i}") for i in range(1, workers + 1)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    checker = InventoryService(db)
    pos = checker.position("TEST01", WAREHOUSE)
    reserved = [dict(r) for r in checker.connection.execute(
        "SELECT code, initial_qty, remaining_qty, status FROM reservation ORDER BY code")]
    checker.close()
    journal.sort(key=lambda e: e["end"])
    return {"journal": journal, "position": pos, "reservations": reserved}


def parallel_batch(runs: int = 100) -> dict:
    """Repeat the experiment on fresh databases (no artificial delay) and count the outcomes."""
    outcomes: dict[str, int] = {}
    violations = 0
    for _ in range(runs):
        with tempfile.TemporaryDirectory() as tmp:
            result = parallel_reservation(tmp, hold=0.0)
        statuses = sorted(e["status"] for e in result["journal"])
        key = ", ".join(statuses)
        outcomes[key] = outcomes.get(key, 0) + 1
        p = result["position"]
        if not (p["r"] <= p["oh"] - p["b"] and p["a"] >= 0):
            violations += 1
    return {"runs": runs, "outcomes": outcomes, "violations": violations}
