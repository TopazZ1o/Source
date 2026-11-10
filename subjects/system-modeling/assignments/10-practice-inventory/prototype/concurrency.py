"""Parallel reservation of TEST01 (OH = 12) by three independent connections.

    python concurrency.py [--save DIR] [--runs N]

Detailed run (the write lock is held 50 ms inside every transaction so that waiting is visible),
then N repetitions without delay on fresh databases.
"""

import argparse
import sys
import tempfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

from inventory.scenarios import parallel_batch, parallel_reservation  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--save", type=Path, default=None)
    parser.add_argument("--runs", type=int, default=100)
    args = parser.parse_args()

    with tempfile.TemporaryDirectory() as tmp:
        result = parallel_reservation(tmp, hold=0.05)
    lines = ["=== TEST01: три параллельных запроса по 5 штук, OH = 12, R = 0, B = 0 ===",
             "Старт всех трёх запросов – после общего барьера threading.Barrier(3); время от момента прохода барьера.", ""]
    first_end = None
    for e in sorted(result["journal"], key=lambda x: x["start"]):
        lines.append(f"t={e['start'] * 1000:7.2f} мс  СТАРТ  {e['key']}")
    lines.append("")
    for e in result["journal"]:
        b, a = e["before"], e["after"]
        ba = f"A до={b['a']} после={a['a']}" if b and a else (f"A до={b['a']}, без изменений" if b else "")
        lines.append(f"t={e['end'] * 1000:7.2f} мс  КОНЕЦ  {e['key']}: {e['status']}  {ba}")
    p = result["position"]
    reserved = sum(r["remaining_qty"] for r in result["reservations"] if r["status"] == "ACTIVE")
    lines += ["", "Резервы: " + "; ".join(f"{r['code']} {r['initial_qty']} шт. {r['status']}" for r in result["reservations"]),
              f"Итог: OH={p['oh']} B={p['b']} ΣR={reserved} A={p['a']}",
              f"Инвариант: ΣR ({reserved}) <= OH − B ({p['oh'] - p['b']}): {reserved <= p['oh'] - p['b']};  A >= 0: {p['a'] >= 0}"]

    batch = parallel_batch(args.runs)
    lines += ["", f"=== Повтор эксперимента без искусственной задержки: {batch['runs']} запусков на новых базах ==="]
    for outcome, n in batch["outcomes"].items():
        lines.append(f"  {n} раз(а): {outcome}")
    lines.append(f"  Нарушений инварианта: {batch['violations']}")
    print("\n".join(lines))
    if args.save:
        args.save.mkdir(parents=True, exist_ok=True)
        (args.save / "concurrency_log.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
