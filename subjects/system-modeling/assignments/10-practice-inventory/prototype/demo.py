"""Demonstration from the initial state: P01 chain of six operations and the stock report.

    python demo.py [--save DIR]

The initial file data/inventory.db is copied to a temporary working file and stays untouched.
"""

import argparse
import shutil
import sys
import tempfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

from inventory.scenarios import p01_chain, state  # noqa: E402
from inventory.seed import WAREHOUSE  # noqa: E402
from inventory.service import InventoryService, STOREKEEPER  # noqa: E402

INITIAL_DB = Path(__file__).resolve().parent / "data" / "inventory.db"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--save", type=Path, default=None)
    args = parser.parse_args()
    lines: list[str] = []

    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp) / "inventory_work.db"
        shutil.copy(INITIAL_DB, work)
        service = InventoryService(work)

        lines.append("=== Исходное состояние склада W01 (отчёт об остатках) ===")
        lines.append(f"{'Код':<5}{'Номенклатура':<28}{'OH':>5}{'R':>5}{'B':>5}{'A':>5}")
        for r in service.stock_report(STOREKEEPER):
            lines.append(f"{r['product']:<5}{r['name']:<28}{r['oh']:>5}{r['r']:>5}{r['b']:>5}{r['a']:>5}")

        lines.append("")
        lines.append("=== Цепочка операций над P01 ===")
        init = state(service)
        table = ["| Шаг | Действие | Результат | OH | R | B | A | RES01 |", "|----|--------|------|---|---|---|---|----|",
                 f"| 0 | Исходное состояние | – | {init['oh']} | {init['r']} | {init['b']} | {init['a']} | – |"]
        lines.append(f"Шаг 0: OH={init['oh']} R={init['r']} B={init['b']} A={init['a']}")
        for step, action, result, st in p01_chain(service):
            shown = result.status + (" (повтор, сохранённый результат)" if result.replayed else "")
            res = "–" if st["res"] is None else st["res"]
            lines.append(f"Шаг {step}: {action} -> {shown}; OH={st['oh']} R={st['r']} B={st['b']} A={st['a']} RES01={res}")
            table.append(f"| {step} | {action} | {shown} | {st['oh']} | {st['r']} | {st['b']} | {st['a']} | {res} |")

        counts = service.connection.execute(
            "SELECT (SELECT COUNT(*) FROM reservation), (SELECT COUNT(*) FROM movement), "
            "(SELECT COUNT(*) FROM processed_request)").fetchone()
        lines.append("")
        lines.append(f"Записей: резервов {counts[0]}, движений {counts[1]}, обработанных запросов {counts[2]}")
        bad = service.connection.execute(
            "SELECT COUNT(*) FROM v_stock_check WHERE on_hand <> from_movements").fetchone()[0]
        lines.append(f"Расхождений журнала движений и OH: {bad}")
        service.close()

    print("\n".join(lines))
    if args.save:
        args.save.mkdir(parents=True, exist_ok=True)
        (args.save / "demo_output.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
        (args.save / "p01_chain.md").write_text("\n".join(table) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
