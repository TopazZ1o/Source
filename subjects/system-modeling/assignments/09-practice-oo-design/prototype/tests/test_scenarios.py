"""TC01-TC12 of the task.

Chain A (TC01-TC02) and chain B (TC03-TC09) share one world each, created in setUpClass;
test methods run in the order of their names. TC10-TC12 create independent data in setUp.
Every scenario class is run twice: with InMemoryRequestRepository and with CopyOnSaveRequestRepository.
"""

import unittest
from datetime import datetime, timedelta

from mro_requests.config import default_policies
from mro_requests.domain import DomainError
from mro_requests.enums import Category, Priority, Status
from mro_requests.errors import ErrorCode
from mro_requests.repository import CopyOnSaveRequestRepository, InMemoryRequestRepository
from mro_requests.sla import SlaPolicy

from .support import DISPATCHER, build_world, load, record, snapshot


class Base:
    repo_factory = InMemoryRequestRepository
    log = True   # only the primary run feeds the results table

    def note(self, tc: str, text: str) -> None:
        if self.log:
            record(tc, text)

    def rejected(self, world, code: ErrorCode, action, *args):
        """Run an action that must fail with `code` and leave all data unchanged."""
        before = snapshot(world)
        with self.assertRaises(DomainError) as ctx:
            action(*args)
        self.assertIs(ctx.exception.code, code)
        self.assertEqual(snapshot(world), before, "a rejected action changed the data")
        return ctx.exception


class ChainA(Base, unittest.TestCase):
    """TC01 -> TC02 on SR03."""

    @classmethod
    def setUpClass(cls):
        cls.w = build_world(cls.repo_factory)

    def test_tc01_empty_submit(self):
        w = self.w
        err = self.rejected(w, ErrorCode.EMPTY_ITEMS, w.service.submit, "U01", "SR03")
        sr03 = w.requests.get("SR03")
        self.assertIs(sr03.status, Status.DRAFT)
        self.assertEqual(len(sr03.history), 1)
        self.note("TC01", f"{err.code.value}; состояние {sr03.status.value}; записей истории {len(sr03.history)}")

    def test_tc02_add_item_and_submit(self):
        w = self.w
        history_before = len(w.requests.get("SR03").history)
        w.service.add_item("U01", "SR03", "Заменить изношенные тормозные диски и проверить зазоры колодок")
        sr03 = w.service.submit("U01", "SR03")
        self.assertIs(sr03.status, Status.SUBMITTED)
        self.assertEqual(len(w.requests.get("SR03").history), history_before + 1)
        last = w.requests.get("SR03").history[-1]
        self.assertEqual((last.from_status, last.to_status, last.actor_id), (Status.DRAFT, Status.SUBMITTED, "U01"))
        self.note("TC02", f"{sr03.status.value}; записей истории {history_before} -> "
                          f"{len(w.requests.get('SR03').history)} (новая: DRAFT -> SUBMITTED, U01)")


class ChainB(Base, unittest.TestCase):
    """TC03 -> TC09 on SR01, SR02 and the technicians T01, T02."""

    @classmethod
    def setUpClass(cls):
        cls.w = build_world(cls.repo_factory)

    def test_tc03_assign_sr01_to_t01(self):
        w = self.w
        self.assertEqual(load(w, "T01"), 1)   # SR04 is already IN_PROGRESS
        sr01 = w.service.assign_technician(DISPATCHER, "SR01", "T01")
        self.assertIs(sr01.status, Status.ASSIGNED)
        self.assertEqual(w.service.get_active_load(DISPATCHER, "T01"), 2)
        self.assertEqual(load(w, "T01"), 2)
        self.note("TC03", f"{sr01.status.value}; нагрузка T01 = {w.service.get_active_load(DISPATCHER, 'T01')}")

    def test_tc04_skill_mismatch(self):
        w = self.w
        # T01 is both unsuitable (EQUIPMENT only) and full (2 requests): SKILL_MISMATCH is checked first.
        err = self.rejected(w, ErrorCode.SKILL_MISMATCH, w.service.assign_technician, DISPATCHER, "SR02", "T01")
        self.assertIs(w.requests.get("SR02").status, Status.SUBMITTED)
        self.note("TC04", f"{err.code.value}; SR02 остаётся {w.requests.get('SR02').status.value}, изменений нет")

    def test_tc05_assign_sr02_to_t02(self):
        w = self.w
        sr02 = w.service.assign_technician(DISPATCHER, "SR02", "T02")
        self.assertIs(sr02.status, Status.ASSIGNED)
        self.assertEqual(w.service.get_active_load(DISPATCHER, "T02"), 1)
        self.note("TC05", f"{sr02.status.value}; нагрузка T02 = {w.service.get_active_load(DISPATCHER, 'T02')}")

    def test_tc06_start_by_wrong_technician(self):
        w = self.w
        err = self.rejected(w, ErrorCode.FORBIDDEN, w.service.start_work, "U05", "SR01")
        self.assertIs(w.requests.get("SR01").status, Status.ASSIGNED)
        self.note("TC06", f"{err.code.value}; SR01 остаётся {w.requests.get('SR01').status.value}, изменений нет")

    def test_tc07_start_by_assigned_technician(self):
        w = self.w
        sr01 = w.service.start_work("U04", "SR01")
        self.assertIs(sr01.status, Status.IN_PROGRESS)
        self.assertEqual(w.service.get_active_load(DISPATCHER, "T01"), 2)
        self.note("TC07", f"{sr01.status.value}; нагрузка T01 = {w.service.get_active_load(DISPATCHER, 'T01')}")

    def test_tc08_complete_with_open_items(self):
        w = self.w
        err = self.rejected(w, ErrorCode.WORK_INCOMPLETE, w.service.complete, "U04", "SR01")
        self.assertIs(w.requests.get("SR01").status, Status.IN_PROGRESS)
        self.note("TC08", f"{err.code.value}; SR01 остаётся {w.requests.get('SR01').status.value}, "
                          f"записей в истории {len(w.requests.get('SR01').history)}, без изменений")

    def test_tc09_complete_and_repeat(self):
        w = self.w
        for item in w.requests.get("SR01").items:
            w.service.complete_item("U04", "SR01", item.code)
        # Marking items does not complete the request and does not touch the history.
        sr01 = w.requests.get("SR01")
        self.assertIs(sr01.status, Status.IN_PROGRESS)
        self.assertTrue(all(i.done for i in sr01.items))
        history_before = len(sr01.history)

        done = w.service.complete("U04", "SR01")
        self.assertIs(done.status, Status.COMPLETED)
        self.assertEqual(len(w.requests.get("SR01").history), history_before + 1)
        self.assertEqual(w.service.get_active_load(DISPATCHER, "T01"), 1)
        self.assertEqual(load(w, "T01"), 1)

        err = self.rejected(w, ErrorCode.INVALID_STATE, w.service.complete, "U04", "SR01")
        self.assertEqual(len(w.requests.get("SR01").history), history_before + 1)
        self.assertEqual(w.service.get_active_load(DISPATCHER, "T01"), 1)
        self.note("TC09", f"1-е: {done.status.value}, нагрузка T01 = 1; 2-е: {err.code.value}, "
                          f"записей в истории {history_before + 1}, без роста")


class Independent(Base, unittest.TestCase):
    """TC10-TC12: each test starts from fresh training data."""

    def setUp(self):
        self.w = build_world(self.repo_factory)

    def test_tc10_cancel_by_stranger_then_owner(self):
        w = self.w
        w.service.add_item("U01", "SR03", "Заменить изношенные тормозные диски")
        w.service.submit("U01", "SR03")                         # precondition: SR03 is SUBMITTED
        err = self.rejected(w, ErrorCode.FORBIDDEN, w.service.cancel, "U02", "SR03")
        history_before = len(w.requests.get("SR03").history)
        sr03 = w.service.cancel("U01", "SR03")
        self.assertIs(sr03.status, Status.CANCELLED)
        self.assertEqual(len(w.requests.get("SR03").history), history_before + 1)
        self.note("TC10", f"U02: {err.code.value}; U01: {sr03.status.value}, в истории +1 запись")

    def test_tc11_load_limit(self):
        w = self.w
        w.service.assign_technician(DISPATCHER, "SR02", "T02")   # SOFTWARE -> T02
        w.service.assign_technician(DISPATCHER, "SR01", "T02")   # EQUIPMENT -> T02
        self.assertEqual(load(w, "T02"), 2)
        w.service.add_item("U01", "SR03", "Заменить изношенные тормозные диски")
        w.service.submit("U01", "SR03")
        err = self.rejected(w, ErrorCode.LOAD_LIMIT, w.service.assign_technician, DISPATCHER, "SR03", "T02")
        self.assertEqual(w.service.get_active_load(DISPATCHER, "T02"), 2)
        self.assertIs(w.requests.get("SR03").status, Status.SUBMITTED)
        self.note("TC11", f"{err.code.value}; нагрузка T02 = {w.service.get_active_load(DISPATCHER, 'T02')}")

    def test_tc12_two_policies_one_contract(self):
        created_at = datetime(2026, 11, 16, 9, 0)
        policies = default_policies()
        parts = []
        for priority, hours in ((Priority.STANDARD, 24), (Priority.URGENT, 4)):
            policy: SlaPolicy = policies[priority]              # both used only as the contract SlaPolicy
            self.assertEqual(policy.calculate_due_at(created_at) - created_at, timedelta(hours=hours))
            parts.append(f"{priority.value} +{hours} ч")
        # The same result in real requests of the training data.
        sr01, sr02 = self.w.requests.get("SR01"), self.w.requests.get("SR02")
        self.assertEqual(sr01.due_at, datetime(2026, 11, 17, 9, 0))
        self.assertEqual(sr02.due_at, datetime(2026, 11, 16, 13, 30))
        self.note("TC12", "; ".join(parts) + f"; SR01 срок {sr01.due_at:%d.%m %H:%M}, SR02 срок {sr02.due_at:%d.%m %H:%M}")


# The same scenarios against the second storage: domain rules are not rewritten.
class ChainACopy(ChainA):
    repo_factory = CopyOnSaveRequestRepository
    log = False


class ChainBCopy(ChainB):
    repo_factory = CopyOnSaveRequestRepository
    log = False


class IndependentCopy(Independent):
    repo_factory = CopyOnSaveRequestRepository
    log = False


if __name__ == "__main__":
    unittest.main()
