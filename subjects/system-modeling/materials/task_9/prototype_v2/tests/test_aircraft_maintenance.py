"""Automated checks of the prototype; the TC-xx code of the traceability matrix is in the test name."""

import dataclasses
import threading
import unittest
from datetime import date, datetime, timedelta

from aircraft_maintenance.adapters import (BrokenNotifier, EmailNotifier, InAppNotifier,
                                           InMemoryAuditLog)
from aircraft_maintenance.domain import (AccessDenied, ActiveRequestExists, Aircraft,
                                         AircraftStatus, Assignment, Employee, InvalidTransition,
                                         MaintenanceType, Priority, ReleaseDenied, RequestStatus,
                                         Resource, ResourceConflict, ResourceKind, Role, Severity,
                                         StorageError, ValidationError, Verdict, WorkOrderStatus)
from aircraft_maintenance.services import (DeadlineService, PlanningService, ReleaseService,
                                           StageSpec, WorkOrderService, WriteOffService)
from aircraft_maintenance.storage import InMemoryDataStore

NOW = datetime(2026, 11, 2, 9, 0)
T10, T12, T14 = (datetime(2026, 11, 5, h, 0) for h in (10, 12, 14))
PLANNER_1, PLANNER_2, TECH_1, TECH_2, CHIEF, ADMIN, BLOCKED = 1, 2, 3, 4, 5, 6, 7
SLOT = 4  # hangar slot, the contested resource


class World:
    """Fixture: store, services and a small reference data set."""

    def __init__(self, notifier=None):
        self.clock_value = NOW
        clock = lambda: self.clock_value  # noqa: E731
        self.store = InMemoryDataStore()
        self.audit = InMemoryAuditLog(clock)
        self.notifier = notifier or InAppNotifier()
        common = dict(clock=clock)
        args = (self.store, self.audit, self.notifier)
        self.planning = PlanningService(*args, **common)
        self.orders = WorkOrderService(*args, **common)
        self.release = ReleaseService(*args, planning=self.planning, **common)
        self.writeoff = WriteOffService(*args, planning=self.planning, **common)
        self.deadlines = DeadlineService(*args, **common)
        for eid, name, role, blocked in ((PLANNER_1, "Планировщик 1", Role.PLANNER, False),
                                         (PLANNER_2, "Планировщик 2", Role.PLANNER, False),
                                         (TECH_1, "Техник 1", Role.TECHNICIAN, False),
                                         (TECH_2, "Техник 2", Role.TECHNICIAN, False),
                                         (CHIEF, "Руководитель", Role.CHIEF, False),
                                         (ADMIN, "Администратор", Role.ADMIN, False),
                                         (BLOCKED, "Заблокированный", Role.PLANNER, True)):
            self.store.add_employee(Employee(eid, name, role, blocked))
        for aid, tail in ((1, "UP-A1001"), (2, "UP-A1002"), (3, "UP-A1003")):
            self.store.add_aircraft(Aircraft(aid, tail, "Boeing 737", f"SN-{aid}", date(2015, 5, 1)))
        for rid, kind, name, emp in ((1, ResourceKind.SPECIALIST, "Техник 1", TECH_1),
                                     (2, ResourceKind.SPECIALIST, "Техник 2", TECH_2),
                                     (3, ResourceKind.EQUIPMENT, "Стенд проверки", None),
                                     (SLOT, ResourceKind.HANGAR_SLOT, "Ангар, место 1", None)):
            self.store.add_resource(Resource(rid, kind, name, employee_id=emp))

    def request(self, aircraft_id=1, user=PLANNER_1, mtype=MaintenanceType.PLANNED,
                desired=date(2026, 11, 5), description="Плановое ТО"):
        return self.planning.create_request(user, aircraft_id, mtype, Priority.NORMAL,
                                            desired, description)

    def scheduled(self, aircraft_id=1, resources=(1, SLOT), start=T10, end=T12):
        request = self.request(aircraft_id)
        self.planning.schedule(PLANNER_1, request.request_id, list(resources), start, end)
        return request

    def in_progress(self, aircraft_id=1):
        """Request scheduled, work order opened and started; returns (request, work order)."""
        request = self.scheduled(aircraft_id)
        order = self.orders.open(PLANNER_1, request.request_id, [
            StageSpec("Осмотр планера", True, TECH_1),
            StageSpec("Проверка двигателя", True, TECH_2),
            StageSpec("Уборка салона", False, TECH_1)])
        self.orders.start(TECH_1, order.work_order_id)
        return request, order

    def work_done(self, aircraft_id=1):
        request, order = self.in_progress(aircraft_id)
        wid = order.work_order_id
        self.orders.complete_stage(TECH_1, wid, 1, "норма")
        self.orders.complete_stage(TECH_2, wid, 2, "норма")
        return request, self.store.get_work_order(wid)

    def aircraft(self, aircraft_id=1):
        return self.store.get_aircraft(aircraft_id)

    def outcomes(self, action):
        return [r.outcome for r in self.audit.records() if r.action == action]


class FullCycleTests(unittest.TestCase):
    def test_tc01_normal_cycle_ends_with_release(self):
        world = World()
        request, order = world.work_done()
        wid = order.work_order_id
        conclusion = world.release.issue_conclusion(CHIEF, wid, Verdict.FIT, "Осмотр пройден")
        self.assertEqual(conclusion.stages_covered, 3)
        aircraft = world.release.release(CHIEF, wid)
        self.assertEqual(aircraft.status, AircraftStatus.READY)
        self.assertEqual(aircraft.next_maintenance_due, NOW.date() + timedelta(days=180))
        self.assertEqual(world.store.get_work_order(wid).status, WorkOrderStatus.CLOSED)
        self.assertEqual(world.store.get_request(request.request_id).status, RequestStatus.COMPLETED)
        self.assertEqual(world.outcomes("выдать допуск"), ["успех"])
        self.assertTrue(any(m[1] == "ВС допущено к эксплуатации" for m in world.notifier.messages))
        self.assertEqual(world.store.list_active_assignments(SLOT), [])  # resources are freed
        other = world.scheduled(2)  # the same slot and interval can be booked again
        self.assertEqual(world.store.get_request(other.request_id).status, RequestStatus.SCHEDULED)

    def test_restricted_aircraft_is_repaired_and_released(self):
        world = World()
        world.aircraft().next_maintenance_due = date(2026, 11, 1)
        self.assertEqual(world.deadlines.check(NOW.date()), [(1, "просрочено")])
        self.assertEqual(world.aircraft().status, AircraftStatus.RESTRICTED)
        request = world.request(mtype=MaintenanceType.UNPLANNED, description="Просрочено ТО")
        world.planning.schedule(PLANNER_1, request.request_id, [1, SLOT], T10, T12)
        self.assertEqual(world.aircraft().status, AircraftStatus.RESTRICTED)  # stays restricted
        order = world.orders.open(PLANNER_1, request.request_id, [StageSpec("ТО", True, TECH_1)])
        world.orders.start(TECH_1, order.work_order_id)
        self.assertEqual(world.aircraft().status, AircraftStatus.IN_MAINTENANCE)
        world.orders.complete_stage(TECH_1, order.work_order_id, 1, "выполнено")
        world.release.issue_conclusion(CHIEF, order.work_order_id, Verdict.FIT, "ТО выполнено")
        world.release.release(CHIEF, order.work_order_id)
        self.assertEqual(world.aircraft().status, AircraftStatus.READY)


class DataValidationTests(unittest.TestCase):
    def test_tc02_incomplete_request_needs_clarification_and_is_not_planned(self):
        world = World()
        request = world.request(desired=None)
        self.assertEqual(request.status, RequestStatus.NEEDS_CLARIFICATION)
        self.assertIn("не указана желаемая дата", request.missing)
        with self.assertRaises(InvalidTransition):
            world.planning.schedule(PLANNER_1, request.request_id, [1, SLOT], T10, T12)
        self.assertEqual(world.store.assignments_of_request(request.request_id), [])
        fixed = world.planning.correct_request(PLANNER_1, request.request_id, date(2026, 11, 5), "ТО")
        self.assertEqual(fixed.status, RequestStatus.NEW)
        world.planning.schedule(PLANNER_1, request.request_id, [1, SLOT], T10, T12)
        self.assertEqual(world.store.get_request(request.request_id).status, RequestStatus.SCHEDULED)

    def test_tc02_other_invalid_inputs(self):
        world = World()
        unplanned = world.request(1, mtype=MaintenanceType.UNPLANNED, description="  ")
        self.assertEqual(unplanned.status, RequestStatus.NEEDS_CLARIFICATION)
        with self.assertRaises(ValidationError):  # unknown aircraft: nothing is saved
            world.planning.create_request(PLANNER_1, 99, MaintenanceType.PLANNED, Priority.NORMAL,
                                          date(2026, 11, 5), "ТО")
        self.assertEqual(len(world.store.requests), 1)
        with self.assertRaises(ValidationError):  # BR-01: tail number is unique
            world.store.add_aircraft(Aircraft(50, "UP-A1001", "ATR 72", "SN-50", date(2020, 1, 1)))
        with self.assertRaises(ValidationError):
            world.store.add_aircraft(Aircraft(51, " ", "ATR 72", "SN-51", date(2020, 1, 1)))

    def test_tc05_boundary_values(self):
        world = World()
        self.assertEqual(world.request(1, desired=NOW.date()).status, RequestStatus.NEW)  # today is ok
        past = world.request(2, desired=NOW.date() - timedelta(days=1))
        self.assertEqual(past.status, RequestStatus.NEEDS_CLARIFICATION)
        order_request, order = world.in_progress(3)
        with self.assertRaises(ValidationError):
            world.orders.add_part(TECH_1, order.work_order_id, "PN-1", 0)
        world.orders.add_part(TECH_1, order.work_order_id, "PN-1", 1)
        self.assertEqual(len(world.store.get_work_order(order.work_order_id).parts), 1)

    def test_tc05_interval_boundaries(self):
        world = World()
        first = world.request(1)
        world.planning.schedule(PLANNER_1, first.request_id, [SLOT], T10, T12)
        adjacent = world.request(2)
        world.planning.schedule(PLANNER_1, adjacent.request_id, [SLOT], T12, T14)  # touches at 12:00
        self.assertEqual(world.store.get_request(adjacent.request_id).status, RequestStatus.SCHEDULED)
        zero = world.request(3)
        with self.assertRaises(ValidationError):  # start == end
            world.planning.schedule(PLANNER_1, zero.request_id, [2], T10, T10)

    def test_tc05_deadline_boundary(self):
        world = World()
        world.aircraft(1).next_maintenance_due = NOW.date()                      # today: not overdue
        world.aircraft(2).next_maintenance_due = NOW.date() - timedelta(days=1)  # yesterday: overdue
        events = dict(world.deadlines.check(NOW.date()))
        self.assertEqual(events, {1: "скоро срок", 2: "просрочено"})
        self.assertEqual(world.aircraft(1).status, AircraftStatus.READY)
        self.assertEqual(world.aircraft(2).status, AircraftStatus.RESTRICTED)


class AccessTests(unittest.TestCase):
    def test_tc03_wrong_role_and_blocked_user_are_denied_and_journaled(self):
        world = World()
        request, order = world.work_done()
        wid = order.work_order_id
        world.release.issue_conclusion(CHIEF, wid, Verdict.FIT, "ok")
        with self.assertRaises(AccessDenied):
            world.release.release(TECH_1, wid)
        with self.assertRaises(AccessDenied):
            world.writeoff.write_off(PLANNER_1, 1, "износ", "Приказ 1")
        with self.assertRaises(AccessDenied):
            world.release.issue_conclusion(PLANNER_1, wid, Verdict.FIT, "ok")
        with self.assertRaises(AccessDenied):
            world.planning.create_request(BLOCKED, 2, MaintenanceType.PLANNED, Priority.NORMAL,
                                          date(2026, 11, 5), "ТО")
        self.assertEqual(world.aircraft().status, AircraftStatus.IN_MAINTENANCE)
        self.assertEqual(world.outcomes("выдать допуск"), ["отказ"])
        self.assertEqual(world.outcomes("оформить списание"), ["отказ"])
        self.assertEqual(world.outcomes("создать заявку")[-1], "отказ")  # NF2: every denial is journaled

    def test_tc14_technician_closes_only_own_stage(self):
        world = World()
        request, order = world.in_progress()
        with self.assertRaises(AccessDenied):
            world.orders.complete_stage(TECH_2, order.work_order_id, 1, "чужой этап")
        self.assertEqual(world.store.get_work_order(order.work_order_id).stages[0].result, "")


class TransitionTests(unittest.TestCase):
    def test_tc04_forbidden_aircraft_transitions(self):
        world = World()
        aircraft = world.aircraft()
        with self.assertRaises(InvalidTransition):
            aircraft.start_maintenance()  # READY -> IN_MAINTENANCE without a plan
        aircraft.restrict()
        with self.assertRaises(InvalidTransition):
            aircraft._move(AircraftStatus.READY)  # RESTRICTED -> READY without maintenance
        aircraft.write_off()
        for action in (aircraft.restrict, aircraft.start_maintenance, aircraft.write_off):
            with self.assertRaises(InvalidTransition):
                action()

    def test_tc04_release_of_aircraft_not_in_maintenance_is_denied(self):
        world = World()
        request = world.scheduled()
        order = world.orders.open(PLANNER_1, request.request_id, [StageSpec("ТО", True, TECH_1)])
        with self.assertRaises(ReleaseDenied) as caught:
            world.release.release(CHIEF, order.work_order_id)
        self.assertTrue(any("а не «На обслуживании»" in r for r in caught.exception.reasons))
        self.assertEqual(world.aircraft().status, AircraftStatus.SCHEDULED)

    def test_request_completed_cannot_be_rescheduled(self):
        world = World()
        request, order = world.work_done()
        world.release.issue_conclusion(CHIEF, order.work_order_id, Verdict.FIT, "ok")
        world.release.release(CHIEF, order.work_order_id)
        with self.assertRaises(InvalidTransition):
            world.planning.schedule(PLANNER_1, request.request_id, [1, SLOT], T10, T12)


class ReleaseRuleTests(unittest.TestCase):
    def test_tc09_release_denied_without_conclusion_with_list_of_reasons(self):
        world = World()
        request, order = world.in_progress()
        with self.assertRaises(ReleaseDenied) as caught:
            world.release.release(CHIEF, order.work_order_id)
        text = " ".join(caught.exception.reasons)
        self.assertIn("работы не завершены", text)
        self.assertIn("Осмотр планера", text)
        self.assertIn("нет заключения", text)
        self.assertEqual(world.aircraft().status, AircraftStatus.IN_MAINTENANCE)

    def test_tc09_open_critical_defect_blocks_release_but_minor_does_not(self):
        world = World()
        request, order = world.work_done()
        wid = order.work_order_id
        minor = world.orders.register_defect(TECH_1, wid, "Царапина обшивки", Severity.MINOR)
        critical = world.orders.register_defect(TECH_1, wid, "Трещина лонжерона", Severity.CRITICAL)
        world.release.issue_conclusion(CHIEF, wid, Verdict.FIT, "ok")
        with self.assertRaises(ReleaseDenied) as caught:
            world.release.release(CHIEF, wid)
        self.assertIn("Трещина лонжерона", " ".join(caught.exception.reasons))
        self.assertNotIn("Царапина", " ".join(caught.exception.reasons))
        world.orders.resolve_defect(TECH_1, wid, critical.defect_id)
        world.release.release(CHIEF, wid)  # the minor defect stays open
        self.assertEqual(world.aircraft().status, AircraftStatus.READY)
        self.assertEqual(minor.defect_id, 1)

    def test_tc13_unfit_conclusion_blocks_and_new_stage_requires_new_conclusion(self):
        world = World()
        request, order = world.work_done()
        wid = order.work_order_id
        world.release.issue_conclusion(CHIEF, wid, Verdict.UNFIT, "Течь гидравлики")
        with self.assertRaises(ReleaseDenied):
            world.release.release(CHIEF, wid)
        world.release.issue_conclusion(CHIEF, wid, Verdict.FIT, "Ошибочно годно")
        world.orders.add_stage(PLANNER_1, wid, "Замена уплотнений", True, TECH_1)
        self.assertEqual(world.store.get_work_order(wid).status, WorkOrderStatus.IN_PROGRESS)
        world.orders.complete_stage(TECH_1, wid, 4, "заменено")
        with self.assertRaises(ReleaseDenied) as caught:  # the old conclusion no longer covers the work
            world.release.release(CHIEF, wid)
        self.assertIn("нужно новое", " ".join(caught.exception.reasons))
        world.release.issue_conclusion(CHIEF, wid, Verdict.FIT, "Повторная проверка")
        world.release.release(CHIEF, wid)
        self.assertEqual(world.aircraft().status, AircraftStatus.READY)


class ConcurrencyTests(unittest.TestCase):
    def _race(self, world, requests):
        barrier = threading.Barrier(len(requests))
        errors = []

        def planner(user, request):
            barrier.wait()
            try:
                world.planning.schedule(user, request.request_id, [SLOT], T10, T12)
            except ResourceConflict as error:
                errors.append(error)

        threads = [threading.Thread(target=planner, args=(user, request))
                   for user, request in zip((PLANNER_1, PLANNER_2), requests)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        return errors

    def test_tc06_two_planners_book_one_slot_exactly_one_wins(self):
        for attempt in range(20):
            world = World()
            requests = [world.request(1, PLANNER_1), world.request(2, PLANNER_2)]
            errors = self._race(world, requests)
            statuses = sorted(world.store.get_request(r.request_id).status.value for r in requests)
            self.assertEqual(statuses, sorted([RequestStatus.SCHEDULED.value,
                                               RequestStatus.WAITING_RESOURCES.value]), attempt)
            self.assertEqual(len(errors), 1, attempt)
            self.assertEqual(len(world.store.list_active_assignments(SLOT)), 1, attempt)

    def test_tc06_control_without_lock_and_constraint_double_books(self):
        """Control test: the domain check alone (check-then-act) is not enough under concurrency."""
        world = World()
        world.store.enforce_constraints = False
        barrier = threading.Barrier(2)

        def naive_booking(request_id):
            resource = world.store.get_resource(SLOT)
            active = world.store.list_active_assignments(SLOT)
            assignment = resource.book(active, world.store.next_id("assignment"), request_id, T10, T12)
            barrier.wait()  # both threads have checked, nobody has written yet
            world.store.add_assignment(assignment)

        threads = [threading.Thread(target=naive_booking, args=(rid,)) for rid in (1, 2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(len(world.store.list_active_assignments(SLOT)), 2)  # BR-03 violated

    def test_tc07_two_planners_create_request_for_one_aircraft(self):
        world = World()
        barrier = threading.Barrier(2)
        results = []

        def create(user, text):
            barrier.wait()
            try:
                results.append(world.planning.create_request(user, 1, MaintenanceType.PLANNED,
                                                             Priority.NORMAL, date(2026, 11, 5), text))
            except ActiveRequestExists as error:
                results.append(error)

        threads = [threading.Thread(target=create, args=(PLANNER_1, "ТО А")),
                   threading.Thread(target=create, args=(PLANNER_2, "ТО Б"))]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(sum(isinstance(r, ActiveRequestExists) for r in results), 1)
        self.assertEqual(len([r for r in world.store.requests.values() if r.is_active]), 1)

    def test_tc10_busy_resource_request_waits_planner_notified_no_double_booking(self):
        world = World()
        first = world.scheduled(1)
        second = world.request(2)
        with self.assertRaises(ResourceConflict):
            world.planning.schedule(PLANNER_2, second.request_id, [SLOT], T10, T12)
        self.assertEqual(world.store.get_request(second.request_id).status, RequestStatus.WAITING_RESOURCES)
        self.assertEqual(len(world.store.list_active_assignments(SLOT)), 1)
        self.assertIn((PLANNER_2, "Заявка ожидает ресурсов"), [(m[0], m[1]) for m in world.notifier.messages])
        world.planning.schedule(PLANNER_2, second.request_id, [SLOT], T12, T14)  # planner picks another time
        self.assertEqual(world.store.get_request(second.request_id).status, RequestStatus.SCHEDULED)
        self.assertEqual(first.aircraft_id, 1)


class RepeatAndFailureTests(unittest.TestCase):
    def test_tc07_repeated_request_is_idempotent(self):
        world = World()
        first = world.request()
        again = world.request()
        self.assertEqual(first.request_id, again.request_id)
        self.assertEqual(len(world.store.requests), 1)
        with self.assertRaises(ActiveRequestExists):
            world.request(description="Другое описание")

    def test_tc08_storage_failure_during_release_rolls_everything_back(self):
        world = World()
        request, order = world.work_done()
        wid = order.work_order_id
        world.release.issue_conclusion(CHIEF, wid, Verdict.FIT, "ok")
        world.store.fail_once("save_aircraft")
        with self.assertRaises(StorageError):
            world.release.release(CHIEF, wid)
        self.assertEqual(world.aircraft().status, AircraftStatus.IN_MAINTENANCE)
        self.assertEqual(world.store.get_work_order(wid).status, WorkOrderStatus.WORK_DONE)
        self.assertEqual(world.store.get_request(request.request_id).status, RequestStatus.IN_PROGRESS)
        self.assertEqual(world.outcomes("выдать допуск"), ["сбой"])  # no record of a success
        world.release.release(CHIEF, wid)  # a retry is safe
        self.assertEqual(world.aircraft().status, AircraftStatus.READY)

    def test_tc08_booking_is_atomic_for_several_resources(self):
        world = World()
        world.scheduled(1, resources=(SLOT,))
        second = world.request(2)
        with self.assertRaises(ResourceConflict):
            world.planning.schedule(PLANNER_2, second.request_id, [1, SLOT], T10, T12)
        self.assertEqual(world.store.list_active_assignments(1), [])  # specialist was not kept booked
        self.assertEqual(world.store.get_request(second.request_id).status, RequestStatus.WAITING_RESOURCES)

    def test_tc12_notification_failure_does_not_undo_release(self):
        world = World(BrokenNotifier())
        request, order = world.work_done()
        world.release.issue_conclusion(CHIEF, order.work_order_id, Verdict.FIT, "ok")
        world.release.release(CHIEF, order.work_order_id)
        self.assertEqual(world.aircraft().status, AircraftStatus.READY)
        self.assertIn("сбой", world.outcomes("уведомление"))

    def test_cancel_request_frees_resource_and_returns_aircraft_to_ready(self):
        world = World()
        request = world.scheduled(1)
        self.assertEqual(world.aircraft().status, AircraftStatus.SCHEDULED)
        world.planning.cancel_request(PLANNER_1, request.request_id)
        self.assertEqual(world.aircraft().status, AircraftStatus.READY)
        self.assertEqual(world.store.list_active_assignments(SLOT), [])
        other = world.scheduled(2)  # the freed interval can be booked again
        self.assertEqual(world.store.get_request(other.request_id).status, RequestStatus.SCHEDULED)

    def test_second_channel_can_replace_the_first(self):
        world = World(EmailNotifier())
        request, order = world.work_done()
        world.release.issue_conclusion(CHIEF, order.work_order_id, Verdict.FIT, "ok")
        world.release.release(CHIEF, order.work_order_id)
        self.assertTrue(world.notifier.outbox)


class WriteOffTests(unittest.TestCase):
    def test_tc11_write_off_requires_reason_and_document(self):
        world = World()
        for reason, document in (("", "Приказ 7"), ("Износ", " ")):
            with self.assertRaises(ValidationError):
                world.writeoff.write_off(CHIEF, 1, reason, document)
        self.assertEqual(world.aircraft().status, AircraftStatus.READY)
        self.assertEqual(world.store.list_write_off_acts(), [])

    def test_tc11_write_off_closes_open_work_and_frees_resources(self):
        world = World()
        request, order = world.in_progress()
        act = world.writeoff.write_off(CHIEF, 1, "Не подлежит восстановлению", "Приказ 7")
        self.assertEqual(act.approved_by, CHIEF)
        self.assertEqual(world.aircraft().status, AircraftStatus.WRITTEN_OFF)
        self.assertEqual(world.store.get_work_order(order.work_order_id).status, WorkOrderStatus.TERMINATED)
        self.assertEqual(world.store.get_request(request.request_id).status, RequestStatus.CANCELLED)
        self.assertEqual(world.store.list_active_assignments(SLOT), [])
        with self.assertRaises(InvalidTransition):  # repeated write-off
            world.writeoff.write_off(CHIEF, 1, "Повтор", "Приказ 8")
        with self.assertRaises(ValidationError):  # a written-off aircraft is not planned
            world.request(1)
        self.assertEqual(len(world.store.list_write_off_acts()), 1)


class ImmutabilityTests(unittest.TestCase):
    def test_tc15_conclusion_audit_and_act_are_immutable(self):
        world = World()
        request, order = world.work_done()
        conclusion = world.release.issue_conclusion(CHIEF, order.work_order_id, Verdict.FIT, "ok")
        with self.assertRaises(dataclasses.FrozenInstanceError):
            conclusion.verdict = Verdict.UNFIT
        record = world.audit.records()[0]
        with self.assertRaises(dataclasses.FrozenInstanceError):
            record.outcome = "успех"
        self.assertIsInstance(world.audit.records(), tuple)
        for forbidden in ("update", "delete", "remove", "clear"):
            self.assertFalse(hasattr(world.audit, forbidden))


if __name__ == "__main__":
    unittest.main()
