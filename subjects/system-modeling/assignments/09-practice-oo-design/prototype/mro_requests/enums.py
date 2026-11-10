"""Enumerations of the domain: roles, categories, priorities, states and events."""

from enum import Enum


class Role(str, Enum):
    APPLICANT = "APPLICANT"      # creates and views own requests
    DISPATCHER = "DISPATCHER"    # assigns technicians, views load
    TECHNICIAN = "TECHNICIAN"    # performs the work


class Category(str, Enum):
    EQUIPMENT = "EQUIPMENT"      # aircraft equipment: airframe, engines, landing gear
    SOFTWARE = "SOFTWARE"        # software of on-board systems


class Priority(str, Enum):
    STANDARD = "STANDARD"
    URGENT = "URGENT"
    ACCELERATED = "ACCELERATED"


class Status(str, Enum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    ASSIGNED = "ASSIGNED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class Event(str, Enum):
    SUBMIT = "submit"
    CANCEL = "cancel"
    ASSIGN = "assign"
    START = "start"
    COMPLETE = "complete"


# A request counts towards the technician's load only in these states (BR-03).
ACTIVE_STATUSES = frozenset({Status.ASSIGNED, Status.IN_PROGRESS})
