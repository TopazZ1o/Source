"""InventoryService: operations that change stock. Every operation is one SQLite write transaction.

Protocol of a changing operation (see _execute):
  1. static checks without the database: role and quantity (positive integer);
  2. BEGIN IMMEDIATE: the write lock is taken before anything is read, so concurrent requests are serialised
     (SQLite has no row-level SELECT FOR UPDATE); a busy database is retried a limited number of times;
  3. look the key up in processed_request: same parameters -> return the stored result;
     other parameters -> CONFLICT, nothing is written;
  4. check business conditions and compute the result, then write the changes;
  5. record the result in processed_request and COMMIT. Any exception -> ROLLBACK, nothing is kept.
"""

from __future__ import annotations

import json
import sqlite3
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional

from . import results as R
from .db import connect
from .results import Result, TechnicalError

STOREKEEPER = "STOREKEEPER"   # warehouse worker
REQUESTER = "REQUESTER"       # applicant (maintenance unit)
PURCHASER = "PURCHASER"       # purchasing manager

# Who may perform which operation (BR-01).
PERMISSIONS = {
    "OPENING": {STOREKEEPER},
    "RECEIVE": {STOREKEEPER},
    "ISSUE": {STOREKEEPER},
    "RESERVE": {REQUESTER},
    "RELEASE": {REQUESTER, STOREKEEPER},
    "REPORT": {STOREKEEPER, REQUESTER, PURCHASER},
    "REPLENISHMENT": {PURCHASER},
}


def _now() -> str:
    return datetime.now().replace(microsecond=0).isoformat(sep=" ")


_NO_QTY = object()     # operations without a quantity parameter (release)


def _is_positive_int(value: Any) -> bool:
    return type(value) is int and value > 0


class InventoryService:
    def __init__(self, db_path: str | Path, *, busy_timeout: float = 5.0, retries: int = 3,
                 clock: Optional[Callable[[], str]] = None, hold_seconds: float = 0.0) -> None:
        """hold_seconds keeps the write lock for a while inside the transaction (used to show waiting)."""
        self._conn = connect(db_path, busy_timeout)
        self._retries = retries
        self._clock = clock or _now
        self._hold = hold_seconds

    def close(self) -> None:
        self._conn.close()

    @property
    def connection(self) -> sqlite3.Connection:
        return self._conn

    # ------------------------------------------------------------------ operations
    def opening(self, key: str, role: str, product: str, warehouse: str, qty: int) -> Result:
        return self._receive(key, role, "OPENING", "OPENING", product, warehouse, qty)

    def receive(self, key: str, role: str, product: str, warehouse: str, qty: int) -> Result:
        return self._receive(key, role, "RECEIVE", "RECEIPT", product, warehouse, qty)

    def reserve(self, key: str, role: str, product: str, warehouse: str, qty: int, request_id: str) -> Result:
        params = {"product": product, "warehouse": warehouse, "qty": qty, "request_id": request_id}

        def apply(conn):
            before = self._position(conn, product, warehouse)
            if before is None:
                return R.NOT_FOUND, f"no stock row for {product} in {warehouse}", {}
            if before["a"] < qty:
                return R.INSUFFICIENT_STOCK, f"available {before['a']} < requested {qty}", {"before": before}
            now = self._clock()
            conn.execute("INSERT INTO reservation (code, product_code, warehouse_code, request_id, initial_qty, "
                         "remaining_qty, status, created_at) VALUES (?, ?, ?, ?, ?, ?, 'ACTIVE', ?)",
                         (key, product, warehouse, request_id, qty, qty, now))
            conn.execute("INSERT INTO reserve_event (reservation_code, kind, qty, request_key, created_at) "
                         "VALUES (?, 'CREATE', ?, ?, ?)", (key, qty, key, now))
            return R.OK, f"reserved {qty}", {"reservation": key, "before": before,
                                              "after": self._position(conn, product, warehouse)}

        return self._execute(key, "RESERVE", role, params, apply, qty)

    def release(self, key: str, role: str, reservation: str) -> Result:
        """Release the whole remaining part of a reservation. Physical stock does not change."""
        params = {"reservation": reservation}

        def apply(conn):
            res = self._reservation(conn, reservation)
            if res is None:
                return R.NOT_FOUND, f"reservation {reservation} not found", {}
            if res["status"] != "ACTIVE":
                return R.INVALID_STATE, f"reservation {reservation} is {res['status']}", {}
            before = self._position(conn, res["product_code"], res["warehouse_code"])
            released = res["remaining_qty"]
            conn.execute("UPDATE reservation SET remaining_qty = 0, status = 'RELEASED' WHERE code = ?", (reservation,))
            conn.execute("INSERT INTO reserve_event (reservation_code, kind, qty, request_key, created_at) "
                         "VALUES (?, 'RELEASE', ?, ?, ?)", (reservation, released, key, self._clock()))
            return R.OK, f"released {released}", {"released": released, "before": before,
                                                  "after": self._position(conn, res["product_code"], res["warehouse_code"])}

        return self._execute(key, "RELEASE", role, params, apply, _NO_QTY)

    def issue(self, key: str, role: str, reservation: str, qty: int) -> Result:
        """Issue goods from a reservation: remaining quantity of the reservation and OH decrease together."""
        params = {"reservation": reservation, "qty": qty}

        def apply(conn):
            res = self._reservation(conn, reservation)
            if res is None:
                return R.NOT_FOUND, f"reservation {reservation} not found", {}
            if res["status"] != "ACTIVE":
                return R.INVALID_STATE, f"reservation {reservation} is {res['status']}", {}
            product, wh = res["product_code"], res["warehouse_code"]
            before = self._position(conn, product, wh)
            if qty > res["remaining_qty"]:
                return R.INSUFFICIENT_RESERVE, f"remaining {res['remaining_qty']} < requested {qty}", {"before": before}
            now = self._clock()
            left = res["remaining_qty"] - qty
            # the reservation is reduced first, then OH: A never becomes negative in between
            conn.execute("UPDATE reservation SET remaining_qty = ?, status = ? WHERE code = ?",
                         (left, "ACTIVE" if left > 0 else "FULFILLED", reservation))
            conn.execute("UPDATE stock SET on_hand = on_hand - ? WHERE product_code = ? AND warehouse_code = ?",
                         (qty, product, wh))
            conn.execute("INSERT INTO movement (product_code, warehouse_code, kind, qty, document, created_at) "
                         "VALUES (?, ?, 'ISSUE', ?, ?, ?)", (product, wh, qty, key, now))
            conn.execute("INSERT INTO reserve_event (reservation_code, kind, qty, request_key, created_at) "
                         "VALUES (?, 'ISSUE', ?, ?, ?)", (reservation, qty, key, now))
            return R.OK, f"issued {qty}", {"remaining": left, "before": before,
                                            "after": self._position(conn, product, wh)}

        return self._execute(key, "ISSUE", role, params, apply, qty)

    # ------------------------------------------------------------------ queries (no changes)
    def stock_report(self, role: str) -> list[dict]:
        """Report of balances: OH, R, B, A of every stock row. Read-only."""
        self._require(role, "REPORT")
        rows = self._conn.execute("SELECT p.code AS product, p.name, v.warehouse_code AS warehouse, v.oh, v.r, v.b, v.a "
                                  "FROM v_stock_position v JOIN product p ON p.code = v.product_code "
                                  "ORDER BY p.code, v.warehouse_code").fetchall()
        return [dict(r) for r in rows]

    def position(self, product: str, warehouse: str) -> Optional[dict]:
        return self._position(self._conn, product, warehouse)

    def reservation_remaining(self, code: str) -> Optional[int]:
        res = self._reservation(self._conn, code)
        return None if res is None else res["remaining_qty"]

    @staticmethod
    def _require(role: str, operation: str) -> None:
        if role not in PERMISSIONS[operation]:
            raise PermissionError(f"role {role} may not perform {operation}")

    # ------------------------------------------------------------------ internals
    def _receive(self, key, role, operation, kind, product, warehouse, qty) -> Result:
        params = {"product": product, "warehouse": warehouse, "qty": qty}

        def apply(conn):
            before = self._position(conn, product, warehouse)
            if before is None:
                return R.NOT_FOUND, f"no stock row for {product} in {warehouse}", {}
            conn.execute("UPDATE stock SET on_hand = on_hand + ? WHERE product_code = ? AND warehouse_code = ?",
                         (qty, product, warehouse))
            conn.execute("INSERT INTO movement (product_code, warehouse_code, kind, qty, document, created_at) "
                         "VALUES (?, ?, ?, ?, ?, ?)", (product, warehouse, kind, qty, key, self._clock()))
            return R.OK, f"received {qty}", {"before": before, "after": self._position(conn, product, warehouse)}

        return self._execute(key, operation, role, params, apply, qty)

    @staticmethod
    def _position(conn, product: str, warehouse: str) -> Optional[dict]:
        row = conn.execute("SELECT oh, r, b, a FROM v_stock_position WHERE product_code = ? AND warehouse_code = ?",
                           (product, warehouse)).fetchone()
        return dict(row) if row else None

    @staticmethod
    def _reservation(conn, code: str):
        return conn.execute("SELECT * FROM reservation WHERE code = ?", (code,)).fetchone()

    def _begin(self) -> None:
        for attempt in range(self._retries + 1):
            try:
                self._conn.execute("BEGIN IMMEDIATE")
                return
            except sqlite3.OperationalError as error:
                if "locked" not in str(error).lower() and "busy" not in str(error).lower():
                    raise TechnicalError("DB_ERROR", str(error)) from error
                if attempt == self._retries:
                    raise TechnicalError("BUSY", f"database is locked after {attempt + 1} attempts") from error
                time.sleep(0.01 * (attempt + 1))

    def _rollback(self) -> None:
        try:
            if self._conn.in_transaction:
                self._conn.execute("ROLLBACK")
        except sqlite3.Error:
            pass

    def _execute(self, key: str, operation: str, role: str, params: dict, apply, qty: Any) -> Result:
        # 1. static checks: nothing is read or written, the key is not consumed
        if role not in PERMISSIONS[operation]:
            return Result(key, operation, R.FORBIDDEN, f"role {role} may not perform {operation}")
        if qty is not _NO_QTY and not _is_positive_int(qty):
            return Result(key, operation, R.INVALID_QUANTITY, f"quantity must be a positive integer, got {qty!r}")
        fingerprint = json.dumps(params, sort_keys=True, ensure_ascii=False)
        # 2. write transaction
        self._begin()
        try:
            row = self._conn.execute("SELECT operation, params, status, result FROM processed_request "
                                     "WHERE request_key = ?", (key,)).fetchone()
            if row is not None:                                        # 3. repeated key
                self._rollback()
                if row["operation"] == operation and row["params"] == fingerprint:
                    stored = json.loads(row["result"])
                    return Result(key, operation, row["status"], stored["message"], stored["data"], replayed=True)
                return Result(key, operation, R.CONFLICT,
                              f"key {key} was used for {row['operation']} {row['params']}")
            status, message, data = apply(self._conn)                  # 4. business logic and changes
            if self._hold:
                time.sleep(self._hold)
            self._conn.execute("INSERT INTO processed_request (request_key, operation, params, status, result, created_at) "
                               "VALUES (?, ?, ?, ?, ?, ?)",
                               (key, operation, fingerprint, status,
                                json.dumps({"message": message, "data": data}, ensure_ascii=False), self._clock()))
            self._conn.execute("COMMIT")                               # 5. commit
            return Result(key, operation, status, message, data)
        except TechnicalError:
            self._rollback()
            raise
        except sqlite3.OperationalError as error:
            self._rollback()
            code = "BUSY" if ("locked" in str(error).lower() or "busy" in str(error).lower()) else "DB_ERROR"
            raise TechnicalError(code, str(error)) from error
        except sqlite3.Error as error:
            self._rollback()
            raise TechnicalError("DB_ERROR", str(error)) from error
        except BaseException:
            self._rollback()
            raise
