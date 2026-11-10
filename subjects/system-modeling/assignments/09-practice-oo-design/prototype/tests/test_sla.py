"""Checks of SLA policies, including AcceleratedSlaPolicy added by the change of task 7."""

import unittest
from datetime import datetime, timedelta

from mro_requests.config import default_policies
from mro_requests.enums import Category, Priority
from mro_requests.sla import AcceleratedSlaPolicy, SlaPolicy, StandardSlaPolicy, UrgentSlaPolicy

from .support import build_world


class SlaPolicies(unittest.TestCase):
    created = datetime(2026, 11, 16, 9, 0)

    def test_all_policies_work_through_one_contract(self):
        for policy, hours in ((StandardSlaPolicy(), 24), (UrgentSlaPolicy(), 4), (AcceleratedSlaPolicy(), 8)):
            contract: SlaPolicy = policy
            self.assertEqual(contract.calculate_due_at(self.created) - self.created, timedelta(hours=hours))

    def test_accelerated_priority_gives_eight_hours_in_a_real_request(self):
        w = build_world()
        request = w.service.create_request("U01", Category.EQUIPMENT, Priority.ACCELERATED, "UP-A105",
                                           "Неисправность датчика температуры двигателя")
        self.assertEqual(request.due_at - request.created_at, timedelta(hours=8))
        self.assertEqual(request.created_at, datetime(2026, 11, 16, 11, 0))

    def test_every_priority_has_a_policy(self):
        self.assertEqual(set(default_policies()), set(Priority))


if __name__ == "__main__":
    unittest.main()
