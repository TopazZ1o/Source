"""SLA policies: how the due date of a request is calculated.

All policies implement one contract (SlaPolicy). ServiceRequest and RequestService
only know the contract; the choice of a concrete policy is made in config.py.
"""

from abc import ABC, abstractmethod
from datetime import datetime, timedelta


class SlaPolicy(ABC):
    """Contract: due date by creation time (calendar hours, no weekends or schedule)."""

    @abstractmethod
    def calculate_due_at(self, created_at: datetime) -> datetime:
        """Return the moment by which the request must be completed."""


class StandardSlaPolicy(SlaPolicy):
    HOURS = 24

    def calculate_due_at(self, created_at: datetime) -> datetime:
        return created_at + timedelta(hours=self.HOURS)


class UrgentSlaPolicy(SlaPolicy):
    HOURS = 4

    def calculate_due_at(self, created_at: datetime) -> datetime:
        return created_at + timedelta(hours=self.HOURS)


class AcceleratedSlaPolicy(SlaPolicy):
    HOURS = 8

    def calculate_due_at(self, created_at: datetime) -> datetime:
        return created_at + timedelta(hours=self.HOURS)
