"""Uniform domain errors: every rejected action raises DomainError with one ErrorCode."""

from enum import Enum


class ErrorCode(str, Enum):
    EMPTY_ITEMS = "EMPTY_ITEMS"          # submit without work items
    FORBIDDEN = "FORBIDDEN"              # the user may not perform the action
    INVALID_STATE = "INVALID_STATE"      # the transition is not in the state table
    SKILL_MISMATCH = "SKILL_MISMATCH"    # technician does not serve the category
    LOAD_LIMIT = "LOAD_LIMIT"            # technician already has the maximum of active requests
    WORK_INCOMPLETE = "WORK_INCOMPLETE"  # complete while some work items are not done
    NOT_FOUND = "NOT_FOUND"              # unknown user, technician, request or work item
    INVALID_INPUT = "INVALID_INPUT"      # empty text, unknown priority, duplicate id
    INVALID_PROFILE = "INVALID_PROFILE"  # wrong technician profile (role, categories, duplicate)


class DomainError(Exception):
    """Business-rule violation. The object that raised it has not been changed."""

    def __init__(self, code: ErrorCode, message: str) -> None:
        super().__init__(f"{code.value}: {message}")
        self.code = code
        self.message = message
