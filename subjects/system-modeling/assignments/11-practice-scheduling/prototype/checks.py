"""Checks TC01-TC08 of Table 6: each returns (actual result, passed)."""

from __future__ import annotations

import os
import tempfile
import threading

from approval import (active_allocations, add_repair, approve_plan, connect, create_draft, init_db)
from planning import (JOBS, base_calendar, best_plan, best_schedule, check_schedule, check_shift,
                      enumerate_plans, explain_infeasible, hm, MACHINES, schedules)

KEY = "approve-{}-{}"


def fresh_db() -> str:
    folder = tempfile.mkdtemp(prefix="sched_")
    path = os.path.join(folder, "scheduling.db")
    init_db(path, base_calendar())
    return path


def tc01():
    errors = check_shift({"J1": "R4"})
    return "; ".join(errors), bool(errors) and "недопустима" in errors[0]


def tc02():
    errors = check_shift({"J1": "R2", "J2": "R2"})
    return "; ".join(errors), len(errors) == 1 and "нескольким работам" in errors[0]


def tc03():
    available = [r for r in MACHINES if r != "R1"]
    plans = enumerate_plans(available)
    reasons = explain_infeasible(available)
    return (f"допустимых планов: {len(plans)}; " + "; ".join(reasons)), not plans and bool(reasons)


def tc04():
    errors = check_schedule(base_calendar(), {"J2": ("R1", hm("10:00"))})
    return "; ".join(errors), len(errors) == 1 and "ремонтом [12:00,13:00)" in errors[0]


def tc05():
    errors = check_schedule(base_calendar(), {"J3": ("R2", hm("12:00"))})
    no_overlap_with_work = not any("пересечение" in e for e in errors)
    return "; ".join(errors), no_overlap_with_work and len(errors) == 1 and "нет времени на подготовку" in errors[0]


def best_plan_for(cal):
    plan, _ = best_schedule(cal)
    return plan


def tc06():
    path = fresh_db()
    plan = best_plan_for(base_calendar())
    plan_id = create_draft(path, plan, "S0", "dispatcher-1")
    version = add_repair(path, "R4", hm("11:30"), hm("12:30"))          # calendar changed after the draft
    decision = approve_plan(path, plan_id, KEY.format(plan_id, 1), "dispatcher-1")
    rows = active_allocations(path)
    actual = f"{decision.outcome}: {decision.message}; версия календаря {version}; активных броней {len(rows)}"
    return actual, decision.outcome == "REJECTED_STALE" and not rows


def two_drafts(path):
    """Two dispatchers have drafts that book the same interval of R4: J4 on R4 at 10:00-11:30."""
    plan = best_plan_for(base_calendar())
    return (create_draft(path, plan, "S0-A", "dispatcher-1"), create_draft(path, plan, "S0-B", "dispatcher-2"))


def run_parallel(path, jobs):
    """Run approve_plan calls in threads released by one barrier; returns decisions in the order of jobs."""
    barrier = threading.Barrier(len(jobs))
    results = [None] * len(jobs)

    def worker(i, plan_id, key, dispatcher):
        barrier.wait()
        results[i] = approve_plan(path, plan_id, key, dispatcher)

    threads = [threading.Thread(target=worker, args=(i, *args)) for i, args in enumerate(jobs)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return results


def tc07(rounds: int = 30):
    """Two dispatchers approve plans with the same R4 interval in parallel; repeated `rounds` times."""
    outcomes, good = [], True
    for n in range(rounds):
        path = fresh_db()
        a, b = two_drafts(path)
        results = run_parallel(path, [(a, KEY.format(a, 1), "dispatcher-1"), (b, KEY.format(b, 1), "dispatcher-2")])
        kinds = sorted(r.outcome for r in results)
        conn = connect(path)
        slots_r4 = conn.execute("SELECT count(*), count(DISTINCT slot_start) FROM booking_slot "
                                "WHERE resource_id = 'R4' AND slot_start BETWEEN ? AND ?",
                                (hm("10:00"), hm("11:00"))).fetchone()
        active = conn.execute("SELECT count(*) FROM allocation WHERE status = 'ACTIVE' AND request_id = 'J4'").fetchone()[0]
        conn.close()
        good &= kinds == ["APPROVED", "REJECTED_CONFLICT"] and active == 1 and slots_r4 == (3, 3)
        outcomes.append(kinds)
    ok_rounds = sum(k == ["APPROVED", "REJECTED_CONFLICT"] for k in outcomes)
    actual = (f"{rounds} запусков по 2 параллельных утверждения: в {ok_rounds} из {rounds} один APPROVED и один "
              f"REJECTED_CONFLICT; активных броней J4 – по одной, слотов R4 10:00–11:30 – по три без дублей")
    return actual, good and ok_rounds == rounds


def tc08():
    path = fresh_db()
    plan = best_plan_for(base_calendar())
    plan_id = create_draft(path, plan, "S0", "dispatcher-1")
    first = approve_plan(path, plan_id, "approve-key-77", "dispatcher-1")
    before = (len(active_allocations(path)), _count(path, "booking_slot"), _count(path, "approval_log"))
    second = approve_plan(path, plan_id, "approve-key-77", "dispatcher-1")
    after = (len(active_allocations(path)), _count(path, "booking_slot"), _count(path, "approval_log"))
    actual = (f"1-й запрос: {first.outcome}; повтор: {second.outcome}, из журнала = {second.replayed}; "
              f"броней/слотов/записей журнала до повтора {before}, после {after}")
    ok = first.approved and second.outcome == first.outcome and second.message == first.message \
        and second.replayed and before == after == (4, 4 + 5 + 4 + 3, 1)
    return actual, ok


def _count(path, table):
    conn = connect(path)
    n = conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
    conn.close()
    return n


def overlap_by_slot_constraint():
    """Extra check: even without the service logic the database refuses two bookings of one slot (J4 and J3 on R4)."""
    path = fresh_db()
    a = create_draft(path, {"J4": ("R4", hm("11:00"))}, "X-A", "dispatcher-1")
    b = create_draft(path, {"J3": ("R4", hm("11:30"))}, "X-B", "dispatcher-2")
    results = run_parallel(path, [(a, KEY.format(a, 1), "dispatcher-1"), (b, KEY.format(b, 1), "dispatcher-2")])
    kinds = sorted(r.outcome for r in results)
    return kinds


CASES = [
    ("TC01", "Назначить J1 машине R4", "Недопустимая пара отклоняется", tc01),
    ("TC02", "Назначить J1 и J2 машине R2 в одной смене", "Два назначения одной машине запрещены", tc02),
    ("TC03", "R1 недоступна, все четыре работы обязательны", "Допустимый план отсутствует", tc03),
    ("TC04", "Запланировать J2 на R1 в [10:00, 12:30)", "Есть пересечение с ремонтом", tc04),
    ("TC05", "Запланировать J3 на R2 в [12:00, 14:00)", "Пересечения с B01 нет, но нет времени на подготовку", tc05),
    ("TC06", "Утвердить старый проект после изменения календаря", "Устаревший проект не утверждается", tc06),
    ("TC07", "Два диспетчера одновременно утверждают один интервал R4",
     "Сохраняется одна бронь, второй запрос получает конфликт", tc07),
    ("TC08", "Повторить тот же запрос утверждения с тем же ключом",
     "Возвращается прежний результат, новая бронь не создаётся", tc08),
]


def run_cases():
    return [(code, action, expected, *fn()) for code, action, expected, fn in CASES]
