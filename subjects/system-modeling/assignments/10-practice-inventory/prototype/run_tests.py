"""Runs all checks, prints the unittest log, the table "expected / actual / passed" and the request journal.

    python run_tests.py [--save DIR]    # writes test_results.txt, test_results.md, test_journal.txt into DIR
"""

import argparse
import io
import sys
import unittest
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

from tests import support  # noqa: E402


def _iter(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from _iter(item)
        else:
            yield item


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--save", type=Path, default=None)
    args = parser.parse_args()

    suite = unittest.defaultTestLoader.discover("tests", top_level_dir=".")
    names = [str(t) for t in _iter(suite)]            # the suite is emptied while it runs
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    log = stream.getvalue()
    print(log)
    failed = [t.id() for t, _ in result.failures + result.errors]

    rows = ["| Код | Действие проверки | Ожидаемый результат | Фактический результат | Пройден |",
            "|----|--------|--------|-----------|----|"]
    for code, (action, expected) in support.TABLE.items():
        key = f"test_{code.lower()}_"
        ok = any(key in n for n in names) and not any(key in f for f in failed)
        rows.append(f"| {code} | {action} | {expected} | {support.ACTUAL.get(code, 'не выполнено')} | "
                    f"{'пройден' if ok else 'не пройден'} |")
    table = "\n".join(rows)
    print(table)
    journal = "\n".join(support.JOURNAL)
    print("\n" + journal)

    if args.save:
        args.save.mkdir(parents=True, exist_ok=True)
        (args.save / "test_results.txt").write_text(log, encoding="utf-8")
        (args.save / "test_results.md").write_text(table + "\n", encoding="utf-8")
        (args.save / "test_journal.txt").write_text(journal + "\n", encoding="utf-8")
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
