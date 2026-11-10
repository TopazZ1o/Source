"""Runs all tests, prints the unittest log and builds the table "expected / actual / passed".

    python run_tests.py                  # console
    python run_tests.py --save DIR       # also writes DIR/test_results.txt and DIR/test_results.md
"""

import argparse
import io
import sys
import unittest
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

from tests import support  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--save", type=Path, default=None)
    args = parser.parse_args()

    suite = unittest.defaultTestLoader.discover("tests", top_level_dir=".")
    all_tests = [str(t) for t in _iter(suite)]   # the suite is emptied while it runs
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    log = stream.getvalue()
    print(log)

    failed_ids = [t.id() for t, _ in result.failures + result.errors]

    def tc_passed(code: str) -> bool:
        key = f"test_{code.lower()}_"
        ran = any(key in name for name in all_tests)
        return ran and not any(key in fid and "Copy" not in fid for fid in failed_ids)

    rows = ["| Код | Действие проверки | Ожидаемый результат | Фактический результат | Пройден |",
            "|----|--------|--------|----------|----|"]
    for code, (action, expected) in support.TC_TABLE.items():
        actual = support.ACTUAL.get(code, "не выполнено")
        rows.append(f"| {code} | {action} | {expected} | {actual} | {'пройден' if tc_passed(code) else 'не пройден'} |")
    table = "\n".join(rows)
    print(table)

    if args.save:
        args.save.mkdir(parents=True, exist_ok=True)
        (args.save / "test_results.txt").write_text(log, encoding="utf-8")
        (args.save / "test_results.md").write_text(table + "\n", encoding="utf-8")
    return 0 if result.wasSuccessful() else 1


def _iter(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from _iter(item)
        else:
            yield item


if __name__ == "__main__":
    sys.exit(main())
