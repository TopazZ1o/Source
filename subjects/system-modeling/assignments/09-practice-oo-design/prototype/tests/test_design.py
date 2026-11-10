"""Checks of the design itself: training data, rules outside TC01-TC12, encapsulation, polymorphism, storage swap."""

import dataclasses
import inspect
import unittest
from datetime import datetime

from mro_requests.domain import DomainError, ServiceRequest
from mro_requests.enums import Category, Priority, Role, Status
from mro_requests.errors import ErrorCode
from mro_requests.repository import CopyOnSaveRequestRepository, InMemoryRequestRepository

from .support import DISPATCHER, build_world, load, snapshot


class TrainingData(unittest.TestCase):
    def test_initial_states_match_the_task(self):
        w = build_world()
        got = {r.code: (r.owner.id, r.category, r.priority, r.status, r.technician.code if r.technician else None)
               for r in w.requests.list_all()}
        self.assertEqual(got, {
            "SR01": ("U01", Category.EQUIPMENT, Priority.STANDARD, Status.SUBMITTED, None),
            "SR02": ("U02", Category.SOFTWARE, Priority.URGENT, Status.SUBMITTED, None),
            "SR03": ("U01", Category.EQUIPMENT, Priority.STANDARD, Status.DRAFT, None),
            "SR04": ("U02", Category.EQUIPMENT, Priority.STANDARD, Status.IN_PROGRESS, "T01"),
        })
        self.assertEqual([len(w.requests.get(c).items) for c in ("SR01", "SR02", "SR03", "SR04")], [2, 2, 0, 2])
        for code in ("SR01", "SR02", "SR04"):
            self.assertFalse(any(i.done for i in w.requests.get(code).items))
        self.assertEqual(w.requests.get("SR01").created_at, datetime(2026, 11, 16, 9, 0))
        self.assertEqual(w.requests.get("SR02").created_at, datetime(2026, 11, 16, 9, 30))

    def test_sr04_history_explains_its_state(self):
        history = build_world().requests.get("SR04").history
        self.assertEqual([(e.from_status, e.to_status, e.actor_id) for e in history], [
            (None, Status.DRAFT, "U02"),
            (Status.DRAFT, Status.SUBMITTED, "U02"),
            (Status.SUBMITTED, Status.ASSIGNED, "U03"),
            (Status.ASSIGNED, Status.IN_PROGRESS, "U04"),
        ])

    def test_item_codes_are_unique(self):
        codes = [i.code for r in build_world().requests.list_all() for i in r.items]
        self.assertEqual(len(codes), len(set(codes)))

    def test_loading_twice_gives_the_same_data(self):
        self.assertEqual(snapshot(build_world()), snapshot(build_world()))


class RulesAndOrder(unittest.TestCase):
    def setUp(self):
        self.w = build_world()

    def fails(self, code, action, *args):
        before = snapshot(self.w)
        with self.assertRaises(DomainError) as ctx:
            action(*args)
        self.assertIs(ctx.exception.code, code)
        self.assertEqual(snapshot(self.w), before)

    def test_assign_order_of_checks(self):
        s = self.w.service
        self.fails(ErrorCode.FORBIDDEN, s.assign_technician, "U01", "SR03", "T01")          # role before state
        self.fails(ErrorCode.INVALID_STATE, s.assign_technician, DISPATCHER, "SR03", "T02")  # state before skill/load
        self.fails(ErrorCode.NOT_FOUND, s.assign_technician, DISPATCHER, "SR99", "T01")
        self.fails(ErrorCode.NOT_FOUND, s.assign_technician, DISPATCHER, "SR01", "T99")

    def test_items_are_frozen_after_submit(self):
        self.fails(ErrorCode.INVALID_STATE, self.w.service.add_item, "U01", "SR01", "Ещё один пункт")
        self.fails(ErrorCode.FORBIDDEN, self.w.service.add_item, "U02", "SR03", "Чужая заявка")
        self.fails(ErrorCode.INVALID_INPUT, self.w.service.add_item, "U01", "SR03", "   ")

    def test_transitions_outside_the_table_are_rejected(self):
        s = self.w.service
        self.fails(ErrorCode.INVALID_STATE, s.submit, "U01", "SR01")              # SUBMITTED -> submit
        self.fails(ErrorCode.INVALID_STATE, s.start_work, "U04", "SR04")          # IN_PROGRESS -> start
        self.fails(ErrorCode.INVALID_STATE, s.cancel, "U02", "SR04")              # IN_PROGRESS -> cancel
        s.assign_technician(DISPATCHER, "SR01", "T02")
        self.fails(ErrorCode.INVALID_STATE, s.cancel, "U01", "SR01")              # ASSIGNED -> cancel
        self.fails(ErrorCode.INVALID_STATE, s.assign_technician, DISPATCHER, "SR01", "T01")  # no reassignment

    def test_final_states_stay_final(self):
        s = self.w.service
        s.cancel("U01", "SR01")
        self.fails(ErrorCode.INVALID_STATE, s.submit, "U01", "SR01")
        self.fails(ErrorCode.INVALID_STATE, s.cancel, "U01", "SR01")
        self.fails(ErrorCode.INVALID_STATE, s.assign_technician, DISPATCHER, "SR01", "T01")

    def test_work_items_follow_the_state_rules(self):
        s = self.w.service
        s.assign_technician(DISPATCHER, "SR01", "T01")
        self.fails(ErrorCode.INVALID_STATE, s.complete_item, "U04", "SR01", "SR01-W1")   # still ASSIGNED
        s.start_work("U04", "SR01")
        self.fails(ErrorCode.FORBIDDEN, s.complete_item, "U05", "SR01", "SR01-W1")
        self.fails(ErrorCode.NOT_FOUND, s.complete_item, "U04", "SR01", "SR01-W9")
        s.complete_item("U04", "SR01", "SR01-W1")
        self.fails(ErrorCode.INVALID_STATE, s.complete_item, "U04", "SR01", "SR01-W1")   # already done

    def test_history_visibility(self):
        s = self.w.service
        self.assertEqual(len(s.view_history("U01", "SR01")), 2)      # owner
        self.assertEqual(len(s.view_history(DISPATCHER, "SR04")), 4)  # dispatcher
        self.assertEqual(len(s.view_history("U04", "SR04")), 4)       # assigned technician
        self.fails(ErrorCode.FORBIDDEN, s.view_history, "U02", "SR01")
        self.fails(ErrorCode.FORBIDDEN, s.view_history, "U05", "SR04")
        self.fails(ErrorCode.FORBIDDEN, s.get_active_load, "U01", "T01")

    def test_technician_profile_constraints(self):
        s = self.w.service
        self.fails(ErrorCode.INVALID_PROFILE, s.register_technician, "T03", "U04", [Category.EQUIPMENT])  # 2nd profile
        self.fails(ErrorCode.INVALID_PROFILE, s.register_technician, "T03", "U01", [Category.EQUIPMENT])  # not a technician
        self.fails(ErrorCode.FORBIDDEN, s.create_request, "U03", Category.EQUIPMENT, Priority.STANDARD, "UP-X", "t")

    def test_load_equals_value_computed_from_requests(self):
        s = self.w.service
        steps = [lambda: s.assign_technician(DISPATCHER, "SR01", "T02"),
                 lambda: s.assign_technician(DISPATCHER, "SR02", "T02"),
                 lambda: s.start_work("U05", "SR02"),
                 lambda: s.complete_item("U05", "SR02", "SR02-W1"),
                 lambda: s.complete_item("U05", "SR02", "SR02-W2"),
                 lambda: s.complete("U05", "SR02")]
        for step in steps:
            step()
            for code in ("T01", "T02"):
                self.assertEqual(s.get_active_load(DISPATCHER, code), load(self.w, code))
        self.assertEqual(load(self.w, "T02"), 1)

    def test_every_error_uses_a_declared_code(self):
        self.assertEqual({c.value for c in ErrorCode}, {
            "EMPTY_ITEMS", "FORBIDDEN", "INVALID_STATE", "SKILL_MISMATCH", "LOAD_LIMIT",
            "WORK_INCOMPLETE", "NOT_FOUND", "INVALID_INPUT", "INVALID_PROFILE"})


class Encapsulation(unittest.TestCase):
    def setUp(self):
        self.request = build_world().requests.get("SR01")

    def test_state_cannot_be_assigned_from_outside(self):
        for name in ("status", "technician", "items", "history", "due_at", "owner"):
            with self.assertRaises(AttributeError):
                setattr(self.request, name, None)

    def test_items_and_history_are_immutable_views(self):
        self.assertIsInstance(self.request.items, tuple)
        self.assertIsInstance(self.request.history, tuple)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            self.request.items[0].done = True
        with self.assertRaises(dataclasses.FrozenInstanceError):
            self.request.history[0].to_status = Status.COMPLETED
        self.assertFalse(self.request.items[0].done)

    def test_request_does_not_branch_on_policy_kind(self):
        source = inspect.getsource(ServiceRequest)
        for forbidden in ("isinstance", "Priority.", "StandardSlaPolicy", "UrgentSlaPolicy"):
            self.assertNotIn(forbidden, source)


class StorageSwap(unittest.TestCase):
    def test_same_scenario_gives_same_data_in_both_repositories(self):
        results = []
        for factory in (InMemoryRequestRepository, CopyOnSaveRequestRepository):
            w = build_world(factory)
            w.service.assign_technician(DISPATCHER, "SR01", "T01")
            w.service.start_work("U04", "SR01")
            with self.assertRaises(DomainError):
                w.service.complete("U04", "SR01")
            results.append(snapshot(w))
        self.assertEqual(results[0], results[1])


if __name__ == "__main__":
    unittest.main()
