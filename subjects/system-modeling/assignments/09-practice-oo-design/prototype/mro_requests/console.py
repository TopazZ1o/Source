"""Console interface. Presentation only: it calls the service and prints; it checks no business rule."""

from __future__ import annotations

from typing import Callable, TextIO

from .domain import ServiceRequest, StatusHistoryEntry
from .enums import Category, Priority
from .errors import DomainError
from .service import RequestService


def fmt_time(moment) -> str:
    return moment.strftime("%d.%m.%Y %H:%M") if moment is not None else "-"


class ConsoleUI:
    def __init__(self, service: RequestService, out: TextIO) -> None:
        self._service = service
        self._out = out

    def say(self, text: str = "") -> None:
        print(text, file=self._out)

    # ------------------------------------------------------------------ commands
    def create(self, actor_id: str, category: Category, priority: Priority, aircraft: str, title: str):
        return self._run(f"{actor_id}: создать заявку ({category.value}, {priority.value}, {aircraft})",
                         self._service.create_request, actor_id, category, priority, aircraft, title)

    def add_item(self, actor_id: str, request_code: str, description: str):
        return self._run(f"{actor_id}: добавить пункт в {request_code}",
                         self._service.add_item, actor_id, request_code, description)

    def submit(self, actor_id: str, request_code: str):
        return self._run(f"{actor_id}: отправить {request_code}", self._service.submit, actor_id, request_code)

    def cancel(self, actor_id: str, request_code: str):
        return self._run(f"{actor_id}: отменить {request_code}", self._service.cancel, actor_id, request_code)

    def assign(self, actor_id: str, request_code: str, technician_code: str):
        return self._run(f"{actor_id}: назначить {request_code} специалисту {technician_code}",
                         self._service.assign_technician, actor_id, request_code, technician_code)

    def start(self, actor_id: str, request_code: str):
        return self._run(f"{actor_id}: начать работу над {request_code}",
                         self._service.start_work, actor_id, request_code)

    def complete_item(self, actor_id: str, request_code: str, item_code: str):
        return self._run(f"{actor_id}: выполнить пункт {item_code}",
                         self._service.complete_item, actor_id, request_code, item_code)

    def complete(self, actor_id: str, request_code: str):
        return self._run(f"{actor_id}: завершить {request_code}",
                         self._service.complete, actor_id, request_code)

    def show_history(self, actor_id: str, request_code: str) -> None:
        self.say(f"> {actor_id}: история {request_code}")
        try:
            entries = self._service.view_history(actor_id, request_code)
        except DomainError as error:
            self.say(f"  ОТКАЗ [{error.code.value}] {error.message}")
            return
        for entry in entries:
            self.say("  " + self._entry_line(entry))

    def show_requests(self) -> None:
        self.say(f"  {'Заявка':<6} {'Влад.':<5} {'Категория':<10} {'Приор.':<9} {'Состояние':<12} "
                 f"{'Спец.':<5} {'Пункты':<7} {'Срок'}")
        for r in self._service.list_requests():
            self.say("  " + self._request_line(r))

    def show_load(self, actor_id: str, technician_codes) -> None:
        parts = [f"{code} = {self._service.get_active_load(actor_id, code)}" for code in technician_codes]
        self.say("  Активная нагрузка: " + ", ".join(parts))

    # ------------------------------------------------------------------ formatting
    def _run(self, label: str, action: Callable, *args):
        self.say(f"> {label}")
        try:
            result = action(*args)
        except DomainError as error:
            self.say(f"  ОТКАЗ [{error.code.value}] {error.message}")
            return None
        if isinstance(result, ServiceRequest):
            self.say(f"  OK: {result.code} -> {result.status.value}")
        else:
            self.say(f"  OK: {getattr(result, 'code', result)}")
        return result

    @staticmethod
    def _request_line(r: ServiceRequest) -> str:
        done = sum(1 for i in r.items if i.done)
        tech = r.technician.code if r.technician else "-"
        return (f"{r.code:<6} {r.owner.id:<5} {r.category.value:<10} {r.priority.value:<9} {r.status.value:<12} "
                f"{tech:<5} {done}/{len(r.items):<5} {fmt_time(r.due_at)}")

    @staticmethod
    def _entry_line(e: StatusHistoryEntry) -> str:
        before = e.from_status.value if e.from_status else "(создание)"
        return f"{fmt_time(e.at)}  {before} -> {e.to_status.value}  [{e.actor_id}]"
