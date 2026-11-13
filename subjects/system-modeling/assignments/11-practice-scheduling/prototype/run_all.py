"""Reproduces every number of the report: tasks 2-4, checks TC01-TC08 and the comparison of task 7.

    python run_all.py        # prints to the console; Excel results: python export_xlsx.py
"""

import pathlib
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from checks import overlap_by_slot_constraint, run_cases  # noqa: E402
from planning import (JOBS, MACHINES, PENALTY, base_calendar, best_plan, best_schedule, calendar_with_r4_repair,  # noqa: E402
                      candidates, changed_jobs, check_schedule, duration_of, enumerate_plans, explain_infeasible, greedy, hhmm,
                      makespan, schedules)

R4_ONLY = [m for m in MACHINES if m != "R1"]


def fmt_assign(plan):
    return ", ".join(f"{j}-{r}" for j, r in sorted(plan.assign.items()))


def fmt_schedule(plan):
    return "; ".join(f"{j}: {r} {hhmm(s)}-{hhmm(s + duration_of(j))}"
                     for j, (r, s) in sorted(plan.items()))


def main():
    print("=== Задание 2. Одна смена, не более одной работы на машину ===")
    g = greedy()
    plans = sorted(enumerate_plans(), key=lambda p: (p.total, sorted(p.assign.items())))
    opt = best_plan(plans)
    print(f"Последовательный выбор: {fmt_assign(g)}; затраты {g.cost}")
    print(f"Все допустимые планы ({len(plans)}):")
    for p in plans:
        print(f"  {fmt_assign(p)}; затраты {p.cost}")
    print(f"Оптимум: {fmt_assign(opt)}; затраты {opt.cost}; разница {g.cost - opt.cost}; "
          f"экономия {(g.cost - opt.cost) / g.cost * 100:.2f} % от последовательного выбора")

    print("\n=== Задание 3. R1 недоступна ===")
    print("S1:", enumerate_plans(R4_ONLY), explain_infeasible(R4_ONLY))
    for title, mandatory in (("S2 (перенос не более одной, обязательных нет)", frozenset()),
                             ("S3 (J2 обязательна)", frozenset({"J2"}))):
        all_plans = sorted(enumerate_plans(R4_ONLY, mandatory, 1), key=lambda p: (p.total, sorted(p.assign.items())))
        print(f"{title}: допустимых планов {len(all_plans)}")
        for j in JOBS:
            best = best_plan([p for p in all_plans if p.postponed == (j,)])
            if best:
                print(f"  отложена {j}: {fmt_assign(best)}; C={best.cost}, P={best.penalty}, Z={best.total}")
    print("Чувствительность S2 (штраф J2 от 0 до 30, остальные штрафы из таблицы 2):")
    previous = None
    for p2 in range(0, 31):
        pen = dict(PENALTY, J2=p2)
        best = best_plan(enumerate_plans(R4_ONLY, frozenset(), 1, pen))
        tie = [x for x in enumerate_plans(R4_ONLY, frozenset(), 1, pen) if x.total == best.total]
        label = ",".join(sorted(x.postponed[0] for x in tie))
        if label != previous:
            print(f"  p2 = {p2}: отложить {label}, Z = {best.total}")
            previous = label
    z_j2 = lambda p2: 19 + p2          # noqa: E731  C = 19 when J2 postponed (J1-R2, J3-R3, J4-R4)
    z_j3 = 23 + PENALTY["J3"]          # C = 23 when J3 postponed (J1-R2, J2-R3, J4-R4)
    print(f"  порог: 19 + p2 = {z_j3} -> p2 = {z_j3 - 19}")

    print("\n=== Задание 4. Расписание ===")
    cal = base_calendar()
    for j in JOBS:
        print(f"Кандидаты {j}:", ", ".join(f"{r} {hhmm(s)}" for r, s in candidates(cal, j)))
    all_s = schedules(cal)
    base, ties = best_schedule(cal, plans=all_s)
    print(f"Допустимых расписаний: {len(all_s)}; окончание последней работы лучшего: {hhmm(makespan(base))}; "
          f"расписаний с тем же временем окончания: {ties}; с окончанием раньше: "
          f"{sum(makespan(p) < makespan(base) for p in all_s)}")
    print("Расписание S0:", fmt_schedule(base), "| проверка:", check_schedule(cal, base) or "нарушений нет")
    print(f"Окончания по работам J3 в допустимых расписаниях: "
          + ", ".join(sorted({hhmm(p['J3'][1] + 120) for p in all_s})))
    cal2 = calendar_with_r4_repair()
    all_s2 = schedules(cal2)
    new, ties2 = best_schedule(cal2, base, all_s2)
    print(f"R4 ремонт 11:30-12:30: допустимых расписаний {len(all_s2)}; лучшее окончание {hhmm(makespan(new))}; "
          f"с тем же окончанием {ties2}")
    print("Расписание S1:", fmt_schedule(new), "| проверка:", check_schedule(cal2, new) or "нарушений нет")
    print("Изменились:", changed_jobs(base, new), "; окончание последней работы:",
          hhmm(makespan(base)), "->", hhmm(makespan(new)))
    print("Старое расписание в новом календаре:", check_schedule(cal2, base))

    print("\n=== Задание 6. Проверки TC01-TC08 ===")
    cases = run_cases()
    for code, action, expected, actual, ok in cases:
        print(f"{code} | {action} | ожидается: {expected} | факт: {actual} | {'PASS' if ok else 'FAIL'}")
    print("Дополнительно, пересечение разных заявок по слотам (J4 11:00-12:30 и J3 11:30-13:30 на R4):",
          overlap_by_slot_constraint())
    print("Итого пройдено:", sum(c[4] for c in cases), "из", len(cases))

    print("\n=== Задание 7. Сравнение ===")
    saving = g.cost - opt.cost
    print(f"Затраты: последовательный выбор {g.cost}, оптимум {opt.cost}, разница {saving}, "
          f"{saving / g.cost * 100:.2f} % от последовательного выбора")


if __name__ == "__main__":
    main()
