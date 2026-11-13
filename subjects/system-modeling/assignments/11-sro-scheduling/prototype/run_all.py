"""Reproduce all numbers of the report: baseline, optimum for S0-S2, checks, re-validation.

    python run_all.py [--save ../results]
"""

import argparse
import io
import pathlib
import sys
from contextlib import redirect_stdout

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from scheduling import (check_plan, count_optimal, enumerate_min, greedy, make_scenario,  # noqa: E402
                        optimise, revalidate)


def table(rows, header):
    print("| " + " | ".join(header) + " |")
    print("|" + "|".join("---" for _ in header) + "|")
    for r in rows:
        print("| " + " | ".join(str(x) for x in r) + " |")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--save", type=pathlib.Path)
    args = ap.parse_args()
    buf = io.StringIO()
    with redirect_stdout(buf):
        s0 = make_scenario("S0")
        log = []
        g = greedy(s0, log)
        print("## Жадный план S0")
        table(log, ["Заявка", "Бригада", "Начало", "Конец", "Затраты", "Примечание"])
        print(f"\nЗатраты {g.run_cost()}, штрафы {g.penalty()}, итого {g.total()}; "
              f"нарушений: {len(check_plan(s0, g.assign))}\n")
        results = {}
        for code in ("S0", "S1", "S2"):
            sc = make_scenario(code)
            plan = optimise(sc)
            results[code] = plan
            print(f"## Оптимальный план {code}: {sc.title}")
            table(plan.rows(), ["Заявка", "Работа", "Бригада", "Начало", "Конец", "Затраты", "Штраф", "Причина переноса"])
            n = len(sc.jobs)
            print(f"\nВыполнено {plan.done()} из {n} ({100 * plan.done() / n:.1f} %), затраты {plan.run_cost()}, "
                  f"штрафы {plan.penalty()}, итого {plan.total()}; "
                  f"проверка плана: {check_plan(sc, plan.assign) or 'нарушений нет'}; "
                  f"полный перебор: {enumerate_min(sc)}; число оптимальных планов: {count_optimal(sc)}\n")
        print("## Повторная проверка плана S0 на календаре S1")
        for e in revalidate(results["S0"], make_scenario("S1")):
            print("-", e)
        print("\n## Модель при недоступности R3 на всю смену")
        print("optimise ->", optimise(make_scenario("S0", r3_off_all_shift=True)))
    text = buf.getvalue()
    print(text)
    if args.save:
        args.save.mkdir(exist_ok=True)
        (args.save / "run_all.txt").write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
