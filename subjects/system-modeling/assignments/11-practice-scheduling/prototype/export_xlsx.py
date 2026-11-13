"""Writes every result of the practice to one Excel workbook (values from the Python model, totals as formulas).

    python export_xlsx.py [--out ../results/results.xlsx]

Sheets: Задание 2, Задание 3, Расписание, Проверки TC, Автотесты. Needs openpyxl.
"""

import argparse
import pathlib
import sys
import time
import unittest

sys.stdout.reconfigure(encoding="utf-8")
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from openpyxl import Workbook  # noqa: E402
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side  # noqa: E402
from openpyxl.utils import get_column_letter  # noqa: E402

from checks import overlap_by_slot_constraint, run_cases  # noqa: E402
from planning import (COST, JOB_NAMES, JOBS, MACHINES, PENALTY, STEP, base_calendar, best_plan,  # noqa: E402
                      best_schedule, calendar_with_r4_repair, changed_jobs, check_schedule, duration_of,
                      enumerate_plans, explain_infeasible, greedy, hhmm, makespan, schedules)

HEAD = PatternFill("solid", fgColor="DAE8FC")
GOOD = PatternFill("solid", fgColor="D5E8D4")
BAD = PatternFill("solid", fgColor="F8CECC")
BOLD = Font(bold=True)
THIN = Side(style="thin", color="999999")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
WRAP = Alignment(wrap_text=True, vertical="top")
TIME_FMT = "hh:mm"


class Sheet:
    """Small helper: a cursor that writes titled tables and keeps track of the current row."""

    def __init__(self, wb, title, widths):
        self.ws = wb.create_sheet(title)
        self.row = 1
        for i, w in enumerate(widths, 1):
            self.ws.column_dimensions[get_column_letter(i)].width = w

    def title(self, text):
        self.ws.cell(self.row, 1, text).font = Font(bold=True, size=13)
        self.row += 1

    def note(self, text):
        self.ws.cell(self.row, 1, text).alignment = Alignment(wrap_text=False)
        self.row += 1

    def blank(self):
        self.row += 1

    def table(self, header, rows, formats=None):
        """Write header + rows; returns (first data row, last data row). Strings starting with = are formulas."""
        for c, h in enumerate(header, 1):
            cell = self.ws.cell(self.row, c, h)
            cell.font, cell.fill, cell.border, cell.alignment = BOLD, HEAD, BORDER, WRAP
        first = self.row + 1
        for r, values in enumerate(rows, first):
            for c, v in enumerate(values, 1):
                cell = self.ws.cell(r, c, v)
                cell.border, cell.alignment = BORDER, WRAP
                if formats and c in formats:
                    cell.number_format = formats[c]
        self.row = first + len(rows)
        return first, self.row - 1


def col(n):
    return get_column_letter(n)


def sheet_task2(wb):
    s = Sheet(wb, "Задание 2", [30, 12, 12, 12, 12, 40])
    s.title("Задание 2. Назначение техники на одну смену, тыс. тенге")
    s.note("Таблица 1: стоимость выполнения работ (пусто – пара недопустима)")
    s.table(["Работа", "R1", "R2", "R3", "R4"],
            [[f"{j} {JOB_NAMES[j]}"] + [COST[j].get(r) for r in MACHINES] for j in JOBS])
    s.blank()
    g = greedy()
    s.note("Последовательный выбор (порядок J1–J4, самая дешёвая из свободных пригодных машин, ничья – меньший код)")
    steps, used = [], set()
    for j in JOBS:
        free = sorted((c, r) for r, c in COST[j].items() if r not in used)
        used.add(g.assign[j])
        steps.append([j, ", ".join(f"{r} ({c})" for c, r in free), g.assign[j], COST[j][g.assign[j]]])
    f1, l1 = s.table(["Работа", "Свободные пригодные машины", "Выбор", "Затраты"], steps)
    s.ws.cell(s.row, 3, "Итого").font = BOLD
    s.ws.cell(s.row, 4, f"=SUM(D{f1}:D{l1})").font = BOLD
    greedy_cell = f"D{s.row}"
    s.row += 2
    s.note("Все допустимые планы (полный перебор): стоимость работы на выбранной машине и итог")
    plans = sorted(enumerate_plans(), key=lambda p: (p.total, sorted(p.assign.items())))
    rows = []
    for n, p in enumerate(plans, 1):
        rows.append([n] + [f"{p.assign[j]} ({COST[j][p.assign[j]]})" for j in JOBS] + [None])
    # separate numeric cost columns so that totals are formulas
    first = s.row + 1
    s.table(["№", "J1", "J2", "J3", "J4", "Стоимость (формула)"], rows)
    cost_cols = {}
    for r, p in zip(range(first, first + len(plans)), plans):
        s.ws.cell(r, 6, "=" + "+".join(str(COST[j][p.assign[j]]) for j in JOBS))
        cost_cols[r] = p.cost
    last = first + len(plans) - 1
    s.blank()
    s.note("Сравнение")
    base = s.row
    s.table(["Показатель", "Значение"], [
        ["Последовательный выбор, тыс. тг", f"={greedy_cell}"],
        ["Оптимальный план, тыс. тг", f"=MIN(F{first}:F{last})"],
        ["Абсолютная разница, тыс. тг", f"=B{base + 1}-B{base + 2}"],
        ["Экономия от последовательного выбора, %", f"=B{base + 3}/B{base + 1}"],
    ])
    s.ws.cell(base + 4, 2).number_format = "0.00%"
    s.ws.column_dimensions["B"].width = 34


def sheet_task3(wb):
    s = Sheet(wb, "Задание 3", [34, 40, 12, 12, 12, 12, 12, 12, 12, 16])
    avail = [r for r in MACHINES if r != "R1"]
    s.title("Задание 3. R1 недоступна всю смену, тыс. тенге")
    s.note("S1. Все работы обязательны: " + "; ".join(explain_infeasible(avail))
           + f"; допустимых планов: {len(enumerate_plans(avail))}")
    s.blank()
    for name, mandatory in (("S2. Перенос не более одной работы (Z = C + P)", frozenset()),
                            ("S3. J2 обязательна", frozenset({"J2"}))):
        s.note(name)
        plans = enumerate_plans(avail, mandatory, 1)
        rows = []
        for j in JOBS:
            if j in mandatory:
                continue
            best = best_plan([p for p in plans if p.postponed == (j,)])
            rows.append([j, ", ".join(f"{k}–{r}" for k, r in sorted(best.assign.items())), best.cost,
                         PENALTY[j], None])
        first, last = s.table(["Отложена", "Назначения остальных", "C", "P", "Z = C + P"], rows)
        for r in range(first, last + 1):
            s.ws.cell(r, 5, f"=C{r}+D{r}")
        s.ws.cell(s.row, 4, "Оптимум Z").font = BOLD
        s.ws.cell(s.row, 5, f"=MIN(E{first}:E{last})").font = BOLD
        s.row += 2
    s.note("Таблица 3. Сравнение результатов")
    s2 = best_plan(enumerate_plans(avail, frozenset(), 1))
    s3 = best_plan(enumerate_plans(avail, frozenset({"J2"}), 1))
    s0 = best_plan(enumerate_plans())

    def line(code, plan):
        if plan is None:
            return [code, "Решения нет", "–", "–", "–", "–"]
        text = ", ".join(f"{j}–{r}" for j, r in sorted(plan.assign.items()))
        text += f"; отложена {plan.postponed[0]}" if plan.postponed else "; отложенных нет"
        return [code, text, len(plan.assign) / 4, plan.cost, plan.penalty, None]

    rows = [line("S0 Исходный", s0), line("S1 Все обязательны", None), line("S2 Перенос со штрафом", s2),
            line("S3 J2 обязательна", s3)]
    first, last = s.table(["Сценарий", "Назначения и отложенная работа", "Доля охвата", "C", "P", "Z"], rows,
                          {3: "0%"})
    for r in (first, first + 2, first + 3):
        s.ws.cell(r, 6, f"=D{r}+E{r}")
    s.blank()
    s.note("Анализ чувствительности S2: штраф J2 (p2) меняется, остальные штрафы из таблицы 2. "
           "C при переносе: J1 – 24, J2 – 19, J3 – 23, J4 – 29")
    header = ["p2, тыс. тг", "Z при переносе J1", "Z при переносе J2", "Z при переносе J3", "Z при переносе J4",
              "Оптимум Z", "Что откладывать"]
    c_cost = {}
    for j in JOBS:
        c_cost[j] = best_plan([p for p in enumerate_plans(avail, frozenset(), 1) if p.postponed == (j,)]).cost
    rows = [[p2, f"={c_cost['J1']}+{PENALTY['J1']}", f"={c_cost['J2']}+A{{r}}", f"={c_cost['J3']}+{PENALTY['J3']}",
             f"={c_cost['J4']}+{PENALTY['J4']}", None, None] for p2 in range(0, 31)]
    first = s.row + 1
    rows = [[v.replace("{r}", str(first + i)) if isinstance(v, str) else v for v in row] for i, row in enumerate(rows)]
    first, last = s.table(header, rows)
    for r in range(first, last + 1):
        s.ws.cell(r, 6, f"=MIN(B{r}:E{r})")
        s.ws.cell(r, 7, f'=IF(C{r}<D{r},"J2",IF(C{r}>D{r},"J3","J2 или J3 (равны)"))')
    s.blank()
    s.note("Порог: 19 + p2 = 23 + 14, то есть p2 = 18; ниже порога выгоднее отложить J2, выше – J3")


def sheet_schedule(wb):
    s = Sheet(wb, "Расписание", [14, 12, 12, 12, 14, 16, 60])
    s.title("Задание 4. Расписания (шаг 30 минут, подготовка 30 минут перед следующей работой)")
    cal0, cal1 = base_calendar(), calendar_with_r4_repair()
    all0 = schedules(cal0)
    plan0, ties0 = best_schedule(cal0, plans=all0)
    all1 = schedules(cal1)
    plan1, ties1 = best_schedule(cal1, plan0, all1)
    ranges = []
    for name, cal, plan, total, ties in (("Исходное расписание", cal0, plan0, len(all0), ties0),
                                          ("После ремонта R4 [11:30, 12:30)", cal1, plan1, len(all1), ties1)):
        s.note(f"{name}: допустимых расписаний {total}, с минимальным окончанием {ties}")
        rows = [[j, plan[j][0], plan[j][1] / 1440, duration_of(j), None] for j in JOBS]
        first, last = s.table(["Работа", "Машина", "Начало", "Длительность, мин", "Окончание"], rows,
                              {3: TIME_FMT, 5: TIME_FMT})
        for r in range(first, last + 1):
            s.ws.cell(r, 5, f"=C{r}+D{r}/1440").number_format = TIME_FMT
        s.ws.cell(s.row, 4, "Окончание последней").font = BOLD
        end = s.ws.cell(s.row, 5, f"=MAX(E{first}:E{last})")
        end.font, end.number_format = BOLD, TIME_FMT
        ranges.append((first, last, s.row))
        errors = check_schedule(cal, plan)
        s.ws.cell(s.row, 7, "Проверка: " + ("нарушений нет" if not errors else "; ".join(errors)))
        s.row += 2
    (f0, l0, e0), (f1, l1, e1) = ranges
    s.note("Сравнение расписаний")
    first, last = s.table(["Работа", "Машина, было", "Начало, было", "Машина, стало", "Начало, стало", "Изменилась?"],
                          [[j, plan0[j][0], f"=C{f0 + i}", plan1[j][0], f"=C{f1 + i}", None]
                           for i, j in enumerate(JOBS)], {3: TIME_FMT, 5: TIME_FMT})
    for r in range(first, last + 1):
        s.ws.cell(r, 6, f'=IF(OR(B{r}<>D{r},C{r}<>E{r}),"да","нет")')
    s.ws.cell(s.row, 5, "Число изменённых").font = BOLD
    s.ws.cell(s.row, 6, f'=COUNTIF(F{first}:F{last},"да")').font = BOLD
    s.row += 1
    s.ws.cell(s.row, 5, "Сдвиг окончания, мин").font = BOLD
    s.ws.cell(s.row, 6, f"=ROUND((E{e1}-E{e0})*1440,0)").font = BOLD
    s.blank()
    s.note("Старое расписание в новом календаре: " + "; ".join(check_schedule(cal1, plan0)))
    assert changed_jobs(plan0, plan1) == ["J3"] and hhmm(makespan(plan0)) == "14:00"


def sheet_checks(wb):
    s = Sheet(wb, "Проверки TC", [8, 40, 40, 80, 12])
    s.title("Задание 6. Ожидаемые и фактические результаты проверок")
    cases = run_cases()
    first, last = s.table(["Код", "Проверяемое действие", "Ожидаемый результат", "Фактический результат", "Итог"],
                          [[c, a, e, act, "PASS" if ok else "FAIL"] for c, a, e, act, ok in cases])
    for r in range(first, last + 1):
        cell = s.ws.cell(r, 5)
        cell.fill = GOOD if cell.value == "PASS" else BAD
    s.ws.cell(s.row, 4, "Пройдено проверок").font = BOLD
    s.ws.cell(s.row, 5, f'=COUNTIF(E{first}:E{last},"PASS")&" из "&COUNTA(E{first}:E{last})').font = BOLD
    s.row += 2
    s.note("Дополнительно: разные заявки на пересекающихся слотах R4 (J4 11:00–12:30 и J3 11:30–13:30): "
           + ", ".join(overlap_by_slot_constraint()))


def sheet_tests(wb):
    s = Sheet(wb, "Автотесты", [70, 12, 12])
    s.title("Автоматические тесты (unittest)")
    suite = unittest.defaultTestLoader.discover(str(HERE / "tests"), top_level_dir=str(HERE / "tests"))
    rows = []

    def flatten(item):
        for t in item:
            if isinstance(t, unittest.TestSuite):
                yield from flatten(t)
            else:
                yield t

    for test in flatten(suite):
        result = unittest.TestResult()
        started = time.time()
        test.run(result)
        rows.append([test.id(), "OK" if result.wasSuccessful() else "FAIL", round(time.time() - started, 2)])
    first, last = s.table(["Тест", "Результат", "Время, с"], rows)
    for r in range(first, last + 1):
        cell = s.ws.cell(r, 2)
        cell.fill = GOOD if cell.value == "OK" else BAD
    s.ws.cell(s.row, 1, "Пройдено").font = BOLD
    s.ws.cell(s.row, 2, f'=COUNTIF(B{first}:B{last},"OK")&" из "&COUNTA(B{first}:B{last})').font = BOLD


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(HERE.parent / "results" / "results.xlsx"))
    args = parser.parse_args()
    wb = Workbook()
    wb.remove(wb.active)
    for fn in (sheet_task2, sheet_task3, sheet_schedule, sheet_checks, sheet_tests):
        fn(wb)
    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out)
    print("saved", out)


if __name__ == "__main__":
    main()
