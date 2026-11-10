"""Initial state of the warehouse W01 and of the separate test position TEST01.

Everything is loaded through InventoryService operations: OH is confirmed by OPENING movements,
R by the initial reservations (history: reserve_event). Only the blocked quantity B and the planning
parameters are inserted directly (they are inputs, not results of operations).
"""

from __future__ import annotations

from pathlib import Path

from .db import connect, create_schema
from .service import InventoryService, REQUESTER, STOREKEEPER

# code, name, OH, B, planning: D, S, H, L, SS, p, OO, BO
ITEMS = [
    ("P01", "Фильтр топливный", 500, 30, 12000, 3000, 600, 5, 60, 50, 100, 20),
    ("P02", "Ремень привода генератора", 100, 10, 6000, 2500, 500, 4, 40, 20, 0, 20),
    ("P03", "Подшипник", 240, 20, 18000, 4000, 800, 6, 90, 100, 100, 10),
    ("P04", "Датчик температуры", 180, 0, 9000, 2000, 450, 3, 30, 50, 0, 0),
    ("P05", "Комплект уплотнителей", 90, 5, 3000, 1500, 300, 7, 35, 25, 50, 0),
    ("P06", "Комплект крепежа", 200, 0, 15000, 3500, 700, 5, 75, 50, 0, 30),
]

# Initial active reservations of earlier work requests: product -> quantities (their sum is R).
INITIAL_RESERVES = {
    "P01": [70, 50], "P02": [20], "P03": [40, 20], "P04": [20], "P05": [10], "P06": [25, 15],
}

WAREHOUSE = "W01"


class FixedClock:
    """Deterministic time stamps for the initial data: one second per call."""

    def __init__(self) -> None:
        self._n = 0

    def __call__(self) -> str:
        self._n += 1
        return f"2026-11-02 08:{self._n // 60:02d}:{self._n % 60:02d}"


def build_initial_db(path: str | Path) -> None:
    path = Path(path)
    if path.exists():
        path.unlink()
    conn = connect(path)
    create_schema(conn)
    conn.execute("INSERT INTO warehouse (code, name) VALUES (?, ?)",
                 (WAREHOUSE, "Склад запасных частей авиатехнической базы"))
    for code, name, oh, blocked, D, S, H, L, SS, p, OO, BO in ITEMS:
        conn.execute("INSERT INTO product (code, name) VALUES (?, ?)", (code, name))
        conn.execute("INSERT INTO stock (product_code, warehouse_code) VALUES (?, ?)", (code, WAREHOUSE))
        conn.execute("INSERT INTO planning_param VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                     (code, D, S, H, L, SS, p, OO, BO))
    conn.close()

    service = InventoryService(path, clock=FixedClock())
    for code, name, oh, blocked, *_ in ITEMS:
        result = service.opening(f"OPEN-{code}", STOREKEEPER, code, WAREHOUSE, oh)
        assert result.ok, result
        if blocked:   # quantity blocked for quality control (input data)
            service.connection.execute("UPDATE stock SET blocked_qty = ? WHERE product_code = ?", (blocked, code))
    for code, quantities in INITIAL_RESERVES.items():
        for i, qty in enumerate(quantities, 1):
            result = service.reserve(f"INIT-{code}-{i}", REQUESTER, code, WAREHOUSE, qty, f"WO-{code}-{i}")
            assert result.ok, result
    service.close()


def build_test01_db(path: str | Path) -> None:
    """Separate database with one position: TEST01, OH = 12, R = 0, B = 0 (parallel reservation test)."""
    path = Path(path)
    if path.exists():
        path.unlink()
    conn = connect(path)
    create_schema(conn)
    conn.execute("INSERT INTO warehouse (code, name) VALUES (?, ?)", (WAREHOUSE, "Склад"))
    conn.execute("INSERT INTO product (code, name) VALUES ('TEST01', 'Тестовая позиция')")
    conn.execute("INSERT INTO stock (product_code, warehouse_code) VALUES ('TEST01', ?)", (WAREHOUSE,))
    conn.close()
    service = InventoryService(path, clock=FixedClock())
    assert service.opening("OPEN-TEST01", STOREKEEPER, "TEST01", WAREHOUSE, 12).ok
    service.close()
