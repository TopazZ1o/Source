"""New checks for the changed requirement: queue for resources (FR-14, BR-14, BR-15)."""

import threading
import unittest
from datetime import date

from aircraft_maintenance.domain import (MaintenanceType, Priority, RequestStatus, ResourceConflict,
                                         Verdict)
from tests.test_aircraft_maintenance import (CHIEF, PLANNER_1, PLANNER_2, SLOT, T10, T12, T14,
                                             World)


def waiting_request(world, aircraft_id, priority=Priority.NORMAL, resources=(SLOT,), start=T10, end=T12):
    """Create a request and try to schedule it while the resources are busy: it joins the queue."""
    request = world.planning.create_request(PLANNER_2, aircraft_id, MaintenanceType.PLANNED, priority,
                                            date(2026, 11, 5), "ТО")
    with_error = None
    try:
        world.planning.schedule(PLANNER_2, request.request_id, list(resources), start, end)
    except ResourceConflict as error:
        with_error = error
    assert with_error is not None
    return request


def status(world, request):
    return world.store.get_request(request.request_id).status


class QueueTests(unittest.TestCase):
    def test_q1_urgent_request_is_served_before_earlier_normal_one(self):
        world = World()
        holder = world.scheduled(1)
        normal = waiting_request(world, 2, Priority.NORMAL)
        urgent = waiting_request(world, 3, Priority.URGENT)
        world.planning.cancel_request(PLANNER_1, holder.request_id)
        self.assertEqual(status(world, urgent), RequestStatus.SCHEDULED)
        self.assertEqual(status(world, normal), RequestStatus.WAITING_RESOURCES)

    def test_q2_equal_priority_first_come_first_served(self):
        world = World()
        holder = world.scheduled(1)
        first = waiting_request(world, 2)
        second = waiting_request(world, 3)
        world.planning.cancel_request(PLANNER_1, holder.request_id)
        self.assertEqual(status(world, first), RequestStatus.SCHEDULED)
        self.assertEqual(status(world, second), RequestStatus.WAITING_RESOURCES)

    def test_q3_cancelled_waiting_request_leaves_the_queue(self):
        world = World()
        holder = world.scheduled(1)
        first = waiting_request(world, 2)
        second = waiting_request(world, 3)
        world.planning.cancel_request(PLANNER_2, first.request_id)
        world.planning.cancel_request(PLANNER_1, holder.request_id)
        self.assertEqual(status(world, first), RequestStatus.CANCELLED)
        self.assertEqual(status(world, second), RequestStatus.SCHEDULED)

    def test_q4_release_of_aircraft_serves_the_queue_and_notifies(self):
        world = World()
        request, order = world.work_done(1)
        waiting = waiting_request(world, 2)
        world.release.issue_conclusion(CHIEF, order.work_order_id, Verdict.FIT, "ok")
        world.release.release(CHIEF, order.work_order_id)
        self.assertEqual(status(world, waiting), RequestStatus.SCHEDULED)
        self.assertIn((PLANNER_2, "Заявка назначена из очереди"),
                      [(m[0], m[1]) for m in world.notifier.messages])
        self.assertEqual(world.outcomes("назначение из очереди"), ["успех"])

    def test_q5_write_off_frees_resources_for_the_queue(self):
        world = World()
        world.in_progress(1)
        waiting = waiting_request(world, 2)
        world.writeoff.write_off(CHIEF, 1, "Не подлежит восстановлению", "Приказ 7")
        self.assertEqual(status(world, waiting), RequestStatus.SCHEDULED)

    def test_q6_entry_needing_two_resources_is_not_served_partially(self):
        world = World()
        slot_holder = world.scheduled(1, resources=(SLOT,))
        specialist_holder = world.scheduled(3, resources=(1,))
        waiting = waiting_request(world, 2, resources=(1, SLOT))
        world.planning.cancel_request(PLANNER_1, slot_holder.request_id)
        self.assertEqual(status(world, waiting), RequestStatus.WAITING_RESOURCES)
        self.assertEqual(world.store.list_active_assignments(SLOT), [])  # nothing booked halfway
        world.planning.cancel_request(PLANNER_1, specialist_holder.request_id)
        self.assertEqual(status(world, waiting), RequestStatus.SCHEDULED)
        self.assertEqual(len(world.store.assignments_of_request(waiting.request_id)), 2)

    def test_q7_repeated_attempt_keeps_place_in_queue(self):
        world = World()
        holder = world.scheduled(1)
        first = waiting_request(world, 2)
        second = waiting_request(world, 3)
        seq_before = world.store.get_request(first.request_id).queued_seq
        with self.assertRaises(ResourceConflict):  # the first request retries another busy interval
            world.planning.schedule(PLANNER_2, first.request_id, [SLOT], T10, T14)
        self.assertEqual(world.store.get_request(first.request_id).queued_seq, seq_before)
        world.planning.cancel_request(PLANNER_1, holder.request_id)
        self.assertEqual(status(world, first), RequestStatus.SCHEDULED)
        self.assertEqual(status(world, second), RequestStatus.WAITING_RESOURCES)

    def test_q8_concurrent_queue_service_assigns_freed_slot_once(self):
        for attempt in range(20):
            world = World()
            holder = world.scheduled(1)
            first = waiting_request(world, 2)
            second = waiting_request(world, 3)
            with world.store.transaction():  # free the slot without serving the queue
                world.planning.cancel_in_transaction(world.store.get_request(holder.request_id))
            barrier = threading.Barrier(2)

            def serve():
                barrier.wait()
                world.planning.serve_queue()

            threads = [threading.Thread(target=serve) for _ in range(2)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            self.assertEqual(len(world.store.list_active_assignments(SLOT)), 1, attempt)
            self.assertEqual(status(world, first), RequestStatus.SCHEDULED, attempt)
            self.assertEqual(status(world, second), RequestStatus.WAITING_RESOURCES, attempt)
            self.assertEqual(world.outcomes("назначение из очереди"), ["успех"], attempt)


if __name__ == "__main__":
    unittest.main()
