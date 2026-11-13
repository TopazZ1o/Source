"""Plan approval service on SQLite: stale-plan check, calendar re-check, double-booking protection, idempotency.

approve_plan() runs in one transaction. BEGIN IMMEDIATE takes the write lock, so parallel approvals are
serialised; the unique constraints (booking_slot primary key, partial unique index on active requests) stay
the last line of defence even if the lock is missed.
"""

from __future__ import annotations

import pathlib
import sqlite3
from dataclasses import dataclass

from planning import COST, JOB_NAMES, JOBS, MACHINES, STEP, TIME, Calendar, check_schedule, duration_of

SCHEMA = pathlib.Path(__file__).resolve().parent / "schema.sql"


def connect(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path, timeout=10, isolation_level=None)      # manual transactions
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(path: str, cal: Calendar) -> None:
    """Create the schema and load Table 1 and the calendar of Table 5."""
    conn = connect(path)
    conn.executescript(SCHEMA.read_text(encoding="utf-8"))
    for r in MACHINES:
        conn.execute("INSERT INTO resource VALUES (?, ?)", (r, f"Машина {r}"))
    for j in JOBS:
        earliest, deadline, dur = TIME[j]
        conn.execute("INSERT INTO request VALUES (?, ?, ?, ?, ?)", (j, JOB_NAMES[j], earliest, deadline, dur))
        for r, c in COST[j].items():
            conn.execute("INSERT INTO eligibility VALUES (?, ?, ?)", (j, r, c))
    conn.execute("INSERT INTO calendar_state VALUES (1, 1)")
    for r, spans in cal.open.items():
        for s, e in spans:
            conn.execute("INSERT INTO availability_window (resource_id, start_min, end_min, kind) "
                         "VALUES (?, ?, ?, 'OPEN')", (r, s, e))
    for r, spans in cal.repairs.items():
        for s, e in spans:
            conn.execute("INSERT INTO availability_window (resource_id, start_min, end_min, kind, label) "
                         "VALUES (?, ?, ?, 'REPAIR', 'repair')", (r, s, e))
    for r, spans in cal.bookings.items():
        for s, e, label in spans:
            conn.execute("INSERT INTO availability_window (resource_id, start_min, end_min, kind, label) "
                         "VALUES (?, ?, ?, 'BOOKING', ?)", (r, s, e, label))
    conn.close()


def load_calendar(conn: sqlite3.Connection) -> Calendar:
    cal = Calendar()
    for r, s, e, kind, label in conn.execute(
            "SELECT resource_id, start_min, end_min, kind, label FROM availability_window ORDER BY id"):
        if kind == "OPEN":
            cal.open.setdefault(r, []).append((s, e))
        elif kind == "REPAIR":
            cal.repairs.setdefault(r, []).append((s, e))
        else:
            cal.bookings.setdefault(r, []).append((s, e, label))
    return cal


def calendar_version(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT version FROM calendar_state WHERE id = 1").fetchone()[0]


def add_repair(path: str, machine: str, start: int, end: int) -> int:
    """Dispatcher changes the calendar: the data version grows by one."""
    conn = connect(path)
    conn.execute("BEGIN IMMEDIATE")
    conn.execute("INSERT INTO availability_window (resource_id, start_min, end_min, kind, label) "
                 "VALUES (?, ?, ?, 'REPAIR', 'repair')", (machine, start, end))
    conn.execute("UPDATE calendar_state SET version = version + 1 WHERE id = 1")
    version = calendar_version(conn)
    conn.execute("COMMIT")
    conn.close()
    return version


def create_draft(path: str, plan: dict, scenario: str, dispatcher: str) -> int:
    """Save a draft plan (job -> (machine, start)) calculated on the current calendar version."""
    conn = connect(path)
    conn.execute("BEGIN IMMEDIATE")
    cur = conn.execute("INSERT INTO plan (scenario, status, calendar_version, created_by) VALUES (?, 'DRAFT', ?, ?)",
                       (scenario, calendar_version(conn), dispatcher))
    plan_id = cur.lastrowid
    for j, (r, s) in plan.items():
        conn.execute("INSERT INTO allocation (plan_id, request_id, resource_id, start_min, end_min, status) "
                     "VALUES (?, ?, ?, ?, ?, 'PLANNED')", (plan_id, j, r, s, s + duration_of(j)))
    conn.execute("COMMIT")
    conn.close()
    return plan_id


@dataclass
class Decision:
    outcome: str            # APPROVED | REJECTED_STALE | REJECTED_INVALID | REJECTED_CONFLICT
    message: str
    replayed: bool = False  # True if returned from the log for a repeated key

    @property
    def approved(self) -> bool:
        return self.outcome == "APPROVED"


def approve_plan(path: str, plan_id: int, key: str, dispatcher: str) -> Decision:
    """Approve a draft plan in one transaction (version check, calendar re-check, write of the bookings)."""
    conn = connect(path)
    try:
        conn.execute("BEGIN IMMEDIATE")                                  # write lock: approvals are serialised
        row = conn.execute("SELECT outcome, message FROM approval_log WHERE idempotency_key = ?", (key,)).fetchone()
        if row:                                                          # repeated request: previous answer
            conn.execute("COMMIT")
            return Decision(row[0], row[1], replayed=True)
        version = calendar_version(conn)
        status, plan_version = conn.execute("SELECT status, calendar_version FROM plan WHERE id = ?",
                                            (plan_id,)).fetchone()

        def finish(outcome, message):
            conn.execute("INSERT INTO approval_log (idempotency_key, plan_id, dispatcher, outcome, message, "
                         "calendar_version) VALUES (?, ?, ?, ?, ?, ?)", (key, plan_id, dispatcher, outcome, message,
                                                                         version))
            if outcome != "APPROVED":
                conn.execute("UPDATE plan SET status = 'REJECTED' WHERE id = ? AND status = 'DRAFT'", (plan_id,))
            conn.execute("COMMIT")
            return Decision(outcome, message)

        if status != "DRAFT":
            return finish("REJECTED_INVALID", f"план в статусе {status}, утверждение возможно только для DRAFT")
        if plan_version != version:                                      # stale draft
            return finish("REJECTED_STALE", f"план рассчитан на версии календаря {plan_version}, "
                                            f"текущая версия {version}")
        rows = conn.execute("SELECT id, request_id, resource_id, start_min FROM allocation WHERE plan_id = ?",
                            (plan_id,)).fetchall()
        plan = {j: (r, s) for _, j, r, s in rows}
        errors = check_schedule(load_calendar(conn), plan)               # calendar re-check
        if errors:
            return finish("REJECTED_INVALID", "; ".join(errors))
        conn.execute("SAVEPOINT booking")
        try:
            for alloc_id, j, r, s in rows:
                conn.execute("UPDATE allocation SET status = 'ACTIVE' WHERE id = ?", (alloc_id,))
                for slot in range(s, s + duration_of(j), STEP):
                    conn.execute("INSERT INTO booking_slot VALUES (?, ?, ?)", (r, slot, alloc_id))
        except sqlite3.IntegrityError as exc:                            # double booking: nothing is saved
            conn.execute("ROLLBACK TO booking")
            conn.execute("RELEASE booking")
            return finish("REJECTED_CONFLICT", f"конфликт брони: {exc}")
        conn.execute("RELEASE booking")
        conn.execute("UPDATE plan SET status = 'APPROVED' WHERE id = ?", (plan_id,))
        return finish("APPROVED", f"план {plan_id} утверждён, назначений: {len(rows)}")
    except BaseException:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()


def active_allocations(path: str) -> list[tuple]:
    conn = connect(path)
    rows = conn.execute("SELECT request_id, resource_id, start_min, end_min FROM allocation "
                        "WHERE status = 'ACTIVE' ORDER BY request_id").fetchall()
    conn.close()
    return rows
