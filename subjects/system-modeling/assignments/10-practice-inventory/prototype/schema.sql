-- Inventory control of the spare-parts warehouse W01 (educational). SQLite 3.
-- Foreign keys are enabled in every connection by inventory/db.py (PRAGMA foreign_keys = ON).
-- All quantities are integers, in pieces.

CREATE TABLE product (
    code TEXT PRIMARY KEY,
    name TEXT NOT NULL
);

CREATE TABLE warehouse (
    code TEXT PRIMARY KEY,
    name TEXT NOT NULL
);

-- Balance of a product in a warehouse: OH (on_hand) and B (blocked_qty).
-- R is NOT stored: it is the sum of remaining quantities of active reservations (view v_stock_position).
CREATE TABLE stock (
    product_code   TEXT    NOT NULL REFERENCES product (code),
    warehouse_code TEXT    NOT NULL REFERENCES warehouse (code),
    on_hand        INTEGER NOT NULL DEFAULT 0 CHECK (on_hand >= 0),
    blocked_qty    INTEGER NOT NULL DEFAULT 0 CHECK (blocked_qty >= 0),
    PRIMARY KEY (product_code, warehouse_code),
    CHECK (blocked_qty <= on_hand)
);

-- Physical movements only: opening balance, receipt, issue. Reserving and releasing are not movements.
-- document is the basis of the movement; here it is the idempotency key of the request (unique).
CREATE TABLE movement (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    product_code   TEXT    NOT NULL,
    warehouse_code TEXT    NOT NULL,
    kind           TEXT    NOT NULL CHECK (kind IN ('OPENING', 'RECEIPT', 'ISSUE')),
    qty            INTEGER NOT NULL CHECK (qty > 0),
    document       TEXT    NOT NULL UNIQUE,
    created_at     TEXT    NOT NULL,
    FOREIGN KEY (product_code, warehouse_code) REFERENCES stock (product_code, warehouse_code)
);

-- Reservation. code equals the key of the request that created it (RES01).
CREATE TABLE reservation (
    code           TEXT    PRIMARY KEY,
    product_code   TEXT    NOT NULL,
    warehouse_code TEXT    NOT NULL,
    request_id     TEXT    NOT NULL,                       -- linked work request
    initial_qty    INTEGER NOT NULL CHECK (initial_qty > 0),
    remaining_qty  INTEGER NOT NULL CHECK (remaining_qty >= 0),
    status         TEXT    NOT NULL CHECK (status IN ('ACTIVE', 'FULFILLED', 'RELEASED')),
    created_at     TEXT    NOT NULL,
    CHECK (remaining_qty <= initial_qty),
    CHECK ((status = 'ACTIVE' AND remaining_qty > 0) OR (status <> 'ACTIVE' AND remaining_qty = 0)),
    FOREIGN KEY (product_code, warehouse_code) REFERENCES stock (product_code, warehouse_code)
);

-- History of a reservation: creation, issues, release. One event per request key.
CREATE TABLE reserve_event (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    reservation_code TEXT    NOT NULL REFERENCES reservation (code),
    kind             TEXT    NOT NULL CHECK (kind IN ('CREATE', 'ISSUE', 'RELEASE')),
    qty              INTEGER NOT NULL CHECK (qty > 0),
    request_key      TEXT    NOT NULL UNIQUE,
    created_at       TEXT    NOT NULL
);

-- Processed requests: the idempotency register. The key is unique; params identify the request.
CREATE TABLE processed_request (
    request_key TEXT PRIMARY KEY,
    operation   TEXT NOT NULL CHECK (operation IN ('OPENING', 'RECEIVE', 'RESERVE', 'RELEASE', 'ISSUE')),
    params      TEXT NOT NULL,
    status      TEXT NOT NULL,
    result      TEXT NOT NULL,
    created_at  TEXT NOT NULL
);

-- Planning parameters and planning inputs (OO, BO are given, not calculated).
CREATE TABLE planning_param (
    product_code  TEXT PRIMARY KEY REFERENCES product (code),
    annual_demand INTEGER NOT NULL CHECK (annual_demand > 0),   -- D
    order_cost    INTEGER NOT NULL CHECK (order_cost > 0),      -- S, tenge
    holding_cost  INTEGER NOT NULL CHECK (holding_cost > 0),    -- H, tenge per piece per year
    lead_days     INTEGER NOT NULL CHECK (lead_days > 0),       -- L, working days
    safety_stock  INTEGER NOT NULL CHECK (safety_stock >= 0),   -- SS
    pack_size     INTEGER NOT NULL CHECK (pack_size > 0),       -- p
    on_order      INTEGER NOT NULL CHECK (on_order >= 0),       -- OO
    backorder     INTEGER NOT NULL CHECK (backorder >= 0)       -- BO
);

-- OH, B, R and A of every stock row. A = OH - R - B.
CREATE VIEW v_stock_position AS
SELECT product_code, warehouse_code, oh, reserved AS r, blocked AS b, oh - blocked - reserved AS a
FROM (
    SELECT s.product_code, s.warehouse_code, s.on_hand AS oh, s.blocked_qty AS blocked,
           COALESCE((SELECT SUM(r.remaining_qty) FROM reservation r
                     WHERE r.product_code = s.product_code AND r.warehouse_code = s.warehouse_code
                       AND r.status = 'ACTIVE'), 0) AS reserved
    FROM stock s
);

-- Consistency of the journal and the aggregated balance: on_hand must equal the sum of movements.
CREATE VIEW v_stock_check AS
SELECT s.product_code, s.warehouse_code, s.on_hand,
       COALESCE((SELECT SUM(CASE WHEN m.kind = 'ISSUE' THEN -m.qty ELSE m.qty END) FROM movement m
                 WHERE m.product_code = s.product_code AND m.warehouse_code = s.warehouse_code), 0) AS from_movements
FROM stock s;

-- Consistency of reservation history: initial = remaining + issued + released.
CREATE VIEW v_reserve_check AS
SELECT r.code, r.initial_qty, r.remaining_qty,
       COALESCE((SELECT SUM(e.qty) FROM reserve_event e WHERE e.reservation_code = r.code AND e.kind = 'ISSUE'), 0) AS issued,
       COALESCE((SELECT SUM(e.qty) FROM reserve_event e WHERE e.reservation_code = r.code AND e.kind = 'RELEASE'), 0) AS released
FROM reservation r;

-- Last line of defence in SQL: no overselling even if the application is wrong.
CREATE TRIGGER trg_reservation_no_oversell
BEFORE INSERT ON reservation
WHEN NEW.status = 'ACTIVE'
 AND NEW.initial_qty > (SELECT a FROM v_stock_position
                        WHERE product_code = NEW.product_code AND warehouse_code = NEW.warehouse_code)
BEGIN
    SELECT RAISE(ABORT, 'INSUFFICIENT_STOCK');
END;

CREATE TRIGGER trg_stock_no_negative_available
BEFORE UPDATE OF on_hand, blocked_qty ON stock
WHEN NEW.on_hand - NEW.blocked_qty < (SELECT COALESCE(SUM(remaining_qty), 0) FROM reservation
                                      WHERE product_code = NEW.product_code
                                        AND warehouse_code = NEW.warehouse_code AND status = 'ACTIVE')
BEGIN
    SELECT RAISE(ABORT, 'NEGATIVE_AVAILABLE');
END;
