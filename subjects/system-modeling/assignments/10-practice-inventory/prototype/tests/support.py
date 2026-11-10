"""Shared helpers of the tests: independent initial database, snapshot, logs of actual results and journal."""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from inventory.results import Result
from inventory.seed import build_initial_db
from inventory.service import InventoryService

ACTUAL: dict[str, str] = {}      # actual result of every check, filled by the tests
JOURNAL: list[str] = []          # journal of requests: key, result, previous and following quantities

# Check code -> (action, expected result)
TABLE = {
    "T01": ("Приём 40 шт. P01 (ключ IN01)", "OH растёт на 40 один раз, R не меняется"),
    "T02": ("Резерв 60 шт. P01 (ключ RES01) при A = 350", "OK, R растёт на 60, OH не меняется"),
    "T03": ("Повтор такого же запроса RES01", "Сохранённый результат, нового резерва и события нет"),
    "T04": ("Ключ RES01 с другим количеством (70)", "CONFLICT, данные не меняются"),
    "T05": ("Резерв 500 шт. P01 (ключ RES02) при A = 350", "INSUFFICIENT_STOCK, запас не меняется"),
    "T06": ("Выдача 20 шт. из резерва RES01 (ключ OUT01)", "OH и R уменьшаются на 20, A не меняется"),
    "T07": ("Освобождение остатка RES01 (ключ CANCEL01)", "OH не меняется, R уменьшается, A растёт"),
    "T08": ("TEST01 (OH = 12): три параллельных запроса по 5 шт. из трёх подключений",
            "Два резерва и один INSUFFICIENT_STOCK; ΣR ≤ OH − B, A ≥ 0"),
    "T09": ("Расчёт A, IP, d, ROP, EOQ для P01-P06", "Значения совпадают с ручным расчётом; пополнение нужно P02, P03, P06"),
    "T10": ("Выбор партии, кратной упаковке, по меньшему TC", "Q: P01 350, P02 240, P03 400, P04 300, P05 175, P06 400"),
    "T11": ("Формирование рекомендации по пополнению", "Содержимое базы не меняется"),
    "T12": ("Прямые SQL-нарушения: отрицательный остаток, количество 0, неизвестный товар, дубль остатка, перерезерв",
            "Все отклонены ограничениями SQL"),
    "T13": ("Согласованность после цепочки P01: журнал движений, резервы, история резервов",
            "OH равен сумме движений, R равен сумме резервов, история резервов сходится"),
    "T14": ("Неверные количества и чужие роли", "INVALID_QUANTITY, FORBIDDEN; ключ не расходуется"),
    "T15": ("База занята другим писателем", "Техническая ошибка BUSY, не INSUFFICIENT_STOCK; данные не меняются"),
    "T16": ("Выдача из резерва: изменение A на шаге 5 цепочки", "A не меняется (OH и R уменьшаются одинаково)"),
    "T17": ("Срок поставки P02 и P03 + 2 дня, SS без изменений", "ROP 160 и 570, пополнение нужно по-прежнему"),
    "T18": ("Исходное состояние склада", "OH, R, B, A совпадают с таблицей задания; OH и R подтверждены записями"),
    "T19": ("Сбой внутри транзакции до фиксации", "Частичные изменения откатываются"),
}


def record(tid: str, text: str) -> None:
    ACTUAL[tid] = text


def journal(tid: str, result: Result) -> None:
    b, a = result.data.get("before"), result.data.get("after")
    fmt = lambda p: "-" if p is None else f"OH={p['oh']} R={p['r']} A={p['a']}"
    if a is None and b is not None:
        after = "без изменений"
    else:
        after = fmt(a)
    status = result.status + (" (повтор)" if result.replayed else "")
    JOURNAL.append(f"{tid}  ключ={result.key:<9} {result.operation:<8} {status:<26} до: {fmt(b):<22} после: {after}")


def pos_text(p: dict) -> str:
    return f"OH={p['oh']} R={p['r']} B={p['b']} A={p['a']}"


class DbTestCase(unittest.TestCase):
    """Every test starts from its own copy of the initial state."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.path = Path(self._tmp.name) / "inventory.db"
        build_initial_db(self.path)
        self.service = InventoryService(self.path)
        self.addCleanup(self.service.close)

    @property
    def conn(self) -> sqlite3.Connection:
        return self.service.connection

    def counts(self) -> dict:
        return {t: self.conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                for t in ("reservation", "movement", "reserve_event", "processed_request")}

    def inventory_snapshot(self) -> list:
        """All data of stock, reservations, movements and reservation history (without the request register)."""
        out = []
        for table in ("stock", "reservation", "movement", "reserve_event"):
            out.append([tuple(r) for r in self.conn.execute(f"SELECT * FROM {table} ORDER BY 1, 2")])
        return out

    def dump(self) -> list[str]:
        return list(self.conn.iterdump())
