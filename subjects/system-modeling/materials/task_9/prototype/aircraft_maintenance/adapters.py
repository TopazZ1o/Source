"""Implementations of the interfaces used in the prototype and in the tests."""

from __future__ import annotations

import threading
from datetime import datetime
from typing import Callable, Optional

from .domain import AuditRecord
from .ports import AuditLog, Notifier


class InAppNotifier(Notifier):
    """Keeps messages in a list (a real system would show them in the web client)."""

    def __init__(self) -> None:
        self.messages: list[tuple[int, str, str]] = []

    def send(self, recipient_id: int, subject: str, text: str) -> None:
        self.messages.append((recipient_id, subject, text))


class EmailNotifier(Notifier):
    """Second channel: formats the message as an e-mail (nothing is actually sent)."""

    def __init__(self, domain: str = "example.kz") -> None:
        self.outbox: list[str] = []
        self._domain = domain

    def send(self, recipient_id: int, subject: str, text: str) -> None:
        self.outbox.append(f"To: user{recipient_id}@{self._domain} | {subject} | {text}")


class BrokenNotifier(Notifier):
    """Channel that always fails: checks that a notification failure never undoes data."""

    def send(self, recipient_id: int, subject: str, text: str) -> None:
        raise ConnectionError("Канал уведомлений недоступен")


class InMemoryAuditLog(AuditLog):
    """Append-only journal; `records` returns an immutable tuple."""

    def __init__(self, clock: Callable[[], datetime] = datetime.now) -> None:
        self._clock = clock
        self._lock = threading.Lock()
        self._records: list[AuditRecord] = []

    def append(self, user_id: Optional[int], action: str, object_ref: str,
               outcome: str, detail: str = "") -> AuditRecord:
        with self._lock:
            record = AuditRecord(len(self._records) + 1, self._clock(), user_id, action,
                                 object_ref, outcome, detail)
            self._records.append(record)
            return record

    def records(self) -> tuple[AuditRecord, ...]:
        with self._lock:
            return tuple(self._records)
