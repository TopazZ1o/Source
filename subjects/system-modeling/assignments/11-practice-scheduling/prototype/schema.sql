-- Data model of the resource allocation system (SQLite). Times are minutes from 00:00 of the planned day.
PRAGMA foreign_keys = ON;

CREATE TABLE request (
    id            TEXT PRIMARY KEY,                       -- J1..J4
    name          TEXT NOT NULL,
    earliest_min  INTEGER NOT NULL,                       -- earliest start
    deadline_min  INTEGER NOT NULL,                       -- latest finish
    duration_min  INTEGER NOT NULL CHECK (duration_min > 0 AND duration_min % 30 = 0),
    CHECK (deadline_min - earliest_min >= duration_min)
);

CREATE TABLE resource (
    id    TEXT PRIMARY KEY,                               -- R1..R4
    name  TEXT NOT NULL
);

CREATE TABLE eligibility (                                -- which machine may do which job, and at what cost
    request_id   TEXT NOT NULL REFERENCES request(id),
    resource_id  TEXT NOT NULL REFERENCES resource(id),
    cost_kt      INTEGER NOT NULL CHECK (cost_kt > 0),    -- thousand tenge
    PRIMARY KEY (request_id, resource_id)
);

CREATE TABLE availability_window (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    resource_id  TEXT NOT NULL REFERENCES resource(id),
    start_min    INTEGER NOT NULL,
    end_min      INTEGER NOT NULL,
    kind         TEXT NOT NULL CHECK (kind IN ('OPEN', 'REPAIR', 'BOOKING')),
    label        TEXT,                                    -- B01 for a booking
    CHECK (end_min > start_min)
);

CREATE TABLE calendar_state (                             -- data version: grows with every calendar change
    id       INTEGER PRIMARY KEY CHECK (id = 1),
    version  INTEGER NOT NULL
);

CREATE TABLE plan (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    scenario          TEXT NOT NULL,
    status            TEXT NOT NULL CHECK (status IN ('DRAFT', 'APPROVED', 'REJECTED')),
    calendar_version  INTEGER NOT NULL,                   -- version the plan was calculated on
    created_by        TEXT NOT NULL
);

CREATE TABLE allocation (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_id      INTEGER NOT NULL REFERENCES plan(id),
    request_id   TEXT NOT NULL,
    resource_id  TEXT NOT NULL,
    start_min    INTEGER NOT NULL,
    end_min      INTEGER NOT NULL,
    status       TEXT NOT NULL CHECK (status IN ('PLANNED', 'ACTIVE', 'CANCELLED')),
    CHECK (end_min > start_min),
    UNIQUE (plan_id, request_id),                         -- a job occurs once inside a plan
    FOREIGN KEY (request_id, resource_id) REFERENCES eligibility(request_id, resource_id)
);

-- a request has at most one active allocation
CREATE UNIQUE INDEX uq_active_request ON allocation(request_id) WHERE status = 'ACTIVE';

CREATE TABLE booking_slot (                               -- one row per 30-minute slot of an active allocation
    resource_id    TEXT NOT NULL REFERENCES resource(id),
    slot_start     INTEGER NOT NULL,
    allocation_id  INTEGER NOT NULL REFERENCES allocation(id),
    PRIMARY KEY (resource_id, slot_start)                 -- two active bookings of one slot are impossible
);

CREATE TABLE approval_log (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    idempotency_key  TEXT NOT NULL UNIQUE,                -- repeated request is recognised by the key
    plan_id          INTEGER NOT NULL REFERENCES plan(id),
    dispatcher       TEXT NOT NULL,
    outcome          TEXT NOT NULL CHECK (outcome IN ('APPROVED', 'REJECTED_STALE', 'REJECTED_INVALID',
                                                      'REJECTED_CONFLICT')),
    message          TEXT NOT NULL,
    calendar_version INTEGER NOT NULL                     -- version seen at the moment of the decision
);
