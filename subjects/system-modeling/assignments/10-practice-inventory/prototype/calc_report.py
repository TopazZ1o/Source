"""Replenishment calculations (task 2 and the change scenario of task 6). The database is only read.

    python calc_report.py [--save DIR]

Formulas: see inventory/planning.py.
"""

import argparse
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

from inventory.db import connect  # noqa: E402
from inventory.planning import replenishment_report  # noqa: E402

INITIAL_DB = Path(__file__).resolve().parent / "data" / "inventory.db"


def fmt(x: float) -> str:
    return f"{x:,.1f}".replace(",", " ") if x != int(x) else f"{int(x):,}".replace(",", " ")


def tables(rows) -> tuple[str, str]:
    main = ["| Код | A | IP | d | ROP | EOQ | Выбор Q | Нужно ли пополнение |", "|----|---|---|---|----|----|----|--------|"]
    cmp_ = ["| Код | p | Q ниже EOQ | TC | Q выше EOQ | TC | Выбранное Q | Разница TC |", "|----|---|----|-----|----|-----|----|-----|"]
    for r in rows:
        need = "да" if r.need else "нет"
        q = f"{r.lot.q}" if r.need else f"{r.lot.q} (заказ не нужен)"
        main.append(f"| {r.code} | {r.a} | {r.ip} | {fmt(r.d)} | {fmt(r.rop)} | {r.lot.eoq:.2f} | {q} | {need} |")
        lo = r.lot.lower
        cmp_.append(f"| {r.code} | {r.lot.upper - r.lot.lower}"
                    f" | {lo} | {fmt(r.lot.tc_lower)} | {r.lot.upper} | {fmt(r.lot.tc_upper)} | {r.lot.q} | "
                    f"{fmt(abs(r.lot.tc_upper - r.lot.tc_lower))} |")
    return "\n".join(main), "\n".join(cmp_)


def scenario_table(base, shifted) -> str:
    out = ["| Код | L | ROP | IP | ROP − IP | Пополнение | L + 2 | ROP | ROP − IP | Пополнение |",
           "|----|--|----|---|-----|----|----|----|-----|----|"]
    for b, s in zip(base, shifted):
        if b.code in ("P02", "P03"):
            dl = {"P02": 4, "P03": 6}[b.code]
            out.append(f"| {b.code} | {dl} | {fmt(b.rop)} | {b.ip} | {fmt(b.rop - b.ip)} | {'да' if b.need else 'нет'} "
                       f"| {dl + 2} | {fmt(s.rop)} | {fmt(s.rop - s.ip)} | {'да' if s.need else 'нет'} |")
    return "\n".join(out)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--save", type=Path, default=None)
    args = parser.parse_args()
    conn = connect(INITIAL_DB)
    base = replenishment_report(conn)
    shifted = replenishment_report(conn, lead_time_shift={"P02": 2, "P03": 2})
    conn.close()
    main_t, cmp_t = tables(base)
    scen = scenario_table(base, shifted)
    text = ("Таблица показателей (A = OH − R − B; IP = OH + OO − BO; d = D/300; ROP = d·L + SS):\n\n" + main_t +
            "\n\nСравнение двух ближайших партий, кратных упаковке:\n\n" + cmp_t +
            "\n\nСценарий: срок поставки P02 и P03 увеличен на 2 рабочих дня, SS без изменений:\n\n" + scen + "\n")
    print(text)
    if args.save:
        args.save.mkdir(parents=True, exist_ok=True)
        (args.save / "calc_indicators.md").write_text(main_t + "\n", encoding="utf-8")
        (args.save / "calc_lots.md").write_text(cmp_t + "\n", encoding="utf-8")
        (args.save / "calc_scenario.md").write_text(scen + "\n", encoding="utf-8")
        (args.save / "calc_report.txt").write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
