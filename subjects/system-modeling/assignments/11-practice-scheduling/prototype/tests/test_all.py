"""Automatic checks: python -m unittest discover -s tests -v (from the prototype folder)."""

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import checks  # noqa: E402
from planning import (base_calendar, best_plan, best_schedule, calendar_with_r4_repair, changed_jobs,  # noqa: E402
                      check_schedule, enumerate_plans, greedy, hm, makespan, schedules)


class Task2(unittest.TestCase):
    def test_greedy_and_optimum(self):
        self.assertEqual(greedy().assign, {"J1": "R1", "J2": "R3", "J3": "R2", "J4": "R4"})
        self.assertEqual(greedy().cost, 29)
        plans = enumerate_plans()
        self.assertEqual(len(plans), 5)
        opt = best_plan(plans)
        self.assertEqual((opt.cost, opt.assign), (25, {"J1": "R2", "J2": "R1", "J3": "R3", "J4": "R4"}))


class Task3(unittest.TestCase):
    avail = ["R2", "R3", "R4"]

    def test_scenarios(self):
        self.assertEqual(enumerate_plans(self.avail), [])
        s2 = best_plan(enumerate_plans(self.avail, frozenset(), 1))
        self.assertEqual((s2.postponed, s2.cost, s2.penalty, s2.total), (("J2",), 19, 12, 31))
        s3 = best_plan(enumerate_plans(self.avail, frozenset({"J2"}), 1))
        self.assertEqual((s3.postponed, s3.cost, s3.penalty, s3.total), (("J3",), 23, 14, 37))

    def test_threshold(self):
        from planning import PENALTY
        totals = {}
        for p2 in (17, 18, 19):
            plans = enumerate_plans(self.avail, frozenset(), 1, dict(PENALTY, J2=p2))
            totals[p2] = {j: min(pl.total for pl in plans if pl.postponed == (j,)) for j in ("J2", "J3")}
        self.assertEqual(totals[17]["J2"], 36)
        self.assertEqual(totals[18]["J2"], totals[18]["J3"])
        self.assertLess(totals[19]["J3"], totals[19]["J2"])


class Task4(unittest.TestCase):
    def test_base_schedule(self):
        cal = base_calendar()
        plan, ties = best_schedule(cal)
        self.assertEqual(makespan(plan), hm("14:00"))
        self.assertEqual(check_schedule(cal, plan), [])
        self.assertFalse([p for p in schedules(cal) if makespan(p) < hm("14:00")])

    def test_after_repair(self):
        base, _ = best_schedule(base_calendar())
        cal2 = calendar_with_r4_repair()
        new, _ = best_schedule(cal2, base)
        self.assertEqual(makespan(new), hm("14:30"))
        self.assertEqual(changed_jobs(base, new), ["J3"])
        self.assertEqual(new["J3"], ("R2", hm("12:30")))
        self.assertTrue(check_schedule(cal2, base))      # the old plan is no longer valid

    def test_end_of_interval_is_free_and_preparation_is_needed(self):
        cal = base_calendar()
        # J4 ends at 11:30, preparation 11:30-12:00, J3 starts at 12:00: valid
        self.assertEqual(check_schedule(cal, {"J4": ("R4", hm("10:00")), "J3": ("R4", hm("12:00"))}), [])
        # J3 starts right at 11:30: the 30 minutes of preparation are missing
        errors = check_schedule(cal, {"J4": ("R4", hm("10:00")), "J3": ("R4", hm("11:30"))})
        self.assertTrue(any("нет времени на подготовку" in e for e in errors))

    def test_preparation_before_booking(self):
        errors = check_schedule(base_calendar(), {"J1": ("R2", hm("09:00"))})
        self.assertTrue(any("перед B01" in e for e in errors))


class Task6(unittest.TestCase):
    def test_all_cases(self):
        for code, _, _, actual, ok in checks.run_cases():
            with self.subTest(code=code):
                self.assertTrue(ok, actual)

    def test_slot_constraint_for_different_requests(self):
        self.assertEqual(checks.overlap_by_slot_constraint(), ["APPROVED", "REJECTED_CONFLICT"])


if __name__ == "__main__":
    unittest.main()
