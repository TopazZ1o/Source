"""Manually driven clock: all times use one local scale (naive datetimes), tests stay deterministic."""

from datetime import datetime, timedelta


class ManualClock:
    def __init__(self, start: datetime) -> None:
        self._now = start

    def __call__(self) -> datetime:
        return self._now

    def set(self, moment: datetime) -> None:
        self._now = moment

    def advance(self, delta: timedelta) -> None:
        self._now += delta
