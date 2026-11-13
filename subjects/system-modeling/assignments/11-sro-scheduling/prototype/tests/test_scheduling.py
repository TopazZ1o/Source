"""Automatic checks of the scheduling model (python -m unittest discover -s tests)."""

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from scheduling import (check_plan, count_optimal, enumerate_min, greedy, make_scenario,  # noqa: E402
                        optimise, options, revalidate, to_slot)

T = to_slot


def p(code, res, start):
    return code, (res, T(start))


class Checks(unittest.TestCase):
    def setUp(self):
        self.s0 = make_scenario("S0")

    def test_01_incompatible_resource(self):
        errs = check_plan(self.s0, dict([p("J1", "R3", "08:00")]))
        self.assertTrue(any("J1: бригада R3 не подходит" in e for e in errs))
        errs = check_plan(self.s0, dict([p("J6", "R1", "12:30")]))
        self.assertTrue(any("J6: бригада R1 не подходит" in e for e in errs))

    def test_02_overlap(self):
        errs = check_plan(self.s0, dict([p("J2", "R2", "08:00"), p("J1", "R2", "08:30")]))
        self.assertTrue(any("пересечение" in e for e in errs))

    def test_03_end_equals_start_is_allowed(self):
        plan = dict([p("J1", "R2", "08:00"), p("J2", "R2", "10:00"),
                     p("J3", "R1", "10:30"), p("J6", "R3", "12:30")])
        self.assertEqual(check_plan(self.s0, plan), [])
        plan["J2"] = ("R2", T("09:30"))              # one slot earlier: now they overlap
        self.assertTrue(any("пересечение" in e for e in check_plan(self.s0, plan)))

    def test_04_r3_unavailable_all_shift(self):
        sc = make_scenario("S0", r3_off_all_shift=True)
        self.assertEqual(options(sc, sc.jobs[5]), [])            # J6 has no place
        self.assertIsNone(optimise(sc))                          # mandatory job: model infeasible
        self.assertIsNone(enumerate_min(sc))
        errs = check_plan(sc, dict([p("J1", "R1", "08:00"), p("J2", "R2", "08:00"), p("J3", "R1", "10:30")]))
        self.assertIn("J6: обязательная заявка не выполнена", errs)

    def test_05_calendar_edges(self):
        self.assertEqual([e for e in check_plan(self.s0, dict([p("J1", "R1", "08:00")])) if "J1" in e], [])
        errs = check_plan(self.s0, dict([p("J1", "R1", "08:30")]))      # 08:30-10:30 hits 10:00-10:30
        self.assertTrue(any("R1 недоступна в 10:00" in e for e in errs))
        errs = check_plan(self.s0, dict([p("J5", "R2", "13:00")]))      # R2 works only until 14:00
        self.assertTrue(any("R2 недоступна в 14:00" in e for e in errs))
        errs = check_plan(self.s0, dict([p("J6", "R3", "12:00")]))      # R3 off until 12:30
        self.assertTrue(any("R3 недоступна в 12:00" in e for e in errs))

    def test_06_windows(self):
        errs = check_plan(self.s0, dict([p("J3", "R1", "08:30")]))
        self.assertTrue(any("выход за окно" in e for e in errs))
        errs = check_plan(self.s0, dict([p("J4", "R2", "13:00")]))      # ends 14:30 > 14:00
        self.assertTrue(any("выход за окно" in e for e in errs))

    def test_07_mandatory_not_postponed(self):
        for code in ("S0", "S1", "S2"):
            sc = make_scenario(code)
            plan = optimise(sc)
            for j in sc.jobs:
                if j.mandatory:
                    self.assertIn(j.code, plan.assign, f"{code}: {j.code}")

    def test_08_optimum_matches_exhaustive_search(self):
        for code, total in (("S0", 54), ("S1", 58), ("S2", 72)):
            sc = make_scenario(code)
            plan = optimise(sc)
            self.assertEqual(check_plan(sc, plan.assign), [])
            self.assertEqual(plan.total(), total)
            self.assertEqual(enumerate_min(sc), total)

    def test_09_greedy_is_valid_and_worse(self):
        sc = make_scenario("S0")
        g = greedy(sc)
        self.assertEqual(check_plan(sc, g.assign), [])
        self.assertEqual(g.total(), 64)
        self.assertEqual(g.total() - optimise(sc).total(), 10)

    def test_10_deterministic(self):
        for code in ("S0", "S1", "S2"):
            a, b = optimise(make_scenario(code)), optimise(make_scenario(code))
            self.assertEqual(a.assign, b.assign)

    def test_11_urgent_job_only_r2_at_12(self):
        sc = make_scenario("S2")
        j7 = sc.jobs[-1]
        self.assertEqual(options(sc, j7), [("R2", T("12:00"))])
        self.assertEqual(optimise(sc).assign["J7"], ("R2", T("12:00")))

    def test_12_revalidation_after_calendar_change(self):
        plan = optimise(self.s0)
        self.assertEqual(revalidate(plan, make_scenario("S0")), [])
        errs = revalidate(plan, make_scenario("S1"))                    # R1 broke down 10:00-13:00
        self.assertTrue(any(e.startswith("J3: R1 недоступна") for e in errs))
        self.assertFalse(any(e.startswith("J2") for e in errs))         # J2 ends at 10:00: still valid

    def test_13_counts_and_totals(self):
        res = {c: optimise(make_scenario(c)) for c in ("S0", "S1", "S2")}
        self.assertEqual([(r.done(), r.run_cost(), r.penalty()) for r in res.values()],
                         [(6, 54, 0), (6, 58, 0), (6, 56, 16)])
        self.assertEqual(count_optimal(make_scenario("S1")), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
