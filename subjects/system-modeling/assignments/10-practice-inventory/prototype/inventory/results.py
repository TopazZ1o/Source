"""Results of operations and errors.

Business refusals (INSUFFICIENT_STOCK, CONFLICT, ...) are returned as a Result.
Technical failures (database busy, SQL error) raise TechnicalError and are never reported as a lack of stock.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

OK = "OK"
INSUFFICIENT_STOCK = "INSUFFICIENT_STOCK"
INSUFFICIENT_RESERVE = "INSUFFICIENT_RESERVE"
CONFLICT = "CONFLICT"
INVALID_QUANTITY = "INVALID_QUANTITY"
INVALID_STATE = "INVALID_STATE"
NOT_FOUND = "NOT_FOUND"
FORBIDDEN = "FORBIDDEN"


@dataclass(frozen=True)
class Result:
    key: str
    operation: str
    status: str
    message: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    replayed: bool = False          # True when the stored result of an earlier identical request is returned

    @property
    def ok(self) -> bool:
        return self.status == OK


class TechnicalError(Exception):
    """BUSY (the database stayed locked after all attempts) or DB_ERROR (unexpected SQL error)."""

    def __init__(self, code: str, message: str = "") -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
