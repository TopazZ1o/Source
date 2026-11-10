"""Доменные ошибки прототипа: у каждой есть код, который видит вызывающая сторона."""


class InventoryError(Exception):
    code = "ERROR"

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class ValidationError(InventoryError):
    code = "VALIDATION"


class PermissionDenied(InventoryError):
    code = "FORBIDDEN"


class NotFound(InventoryError):
    code = "NOT_FOUND"


class InsufficientStock(InventoryError):
    """Запрошено больше доступного количества; в сообщении – сколько доступно."""

    code = "INSUFFICIENT_STOCK"

    def __init__(self, requested: int, available: int):
        super().__init__(f"Запрошено {requested}, доступно {available}")
        self.requested = requested
        self.available = available


class InvalidState(InventoryError):
    code = "INVALID_STATE"


class IdempotencyConflict(InventoryError):
    """Тот же ключ запроса пришёл с другими данными."""

    code = "IDEMPOTENCY_CONFLICT"
