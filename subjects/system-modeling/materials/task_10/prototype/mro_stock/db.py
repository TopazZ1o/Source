"""Схема SQLite и открытие соединений.

Склад запасных частей и материалов авиатехнической базы (учебная модель).
Остаток хранится в stock_balance и одновременно выводится из журнала stock_movement
(сравнение – StockService.check_consistency). Ограничения CHECK – последний рубеж защиты:
остаток не отрицателен, резерв не превышает остаток.
"""
import sqlite3

SCHEMA = """
CREATE TABLE app_user (
    user_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    role TEXT NOT NULL CHECK (role IN ('admin', 'storekeeper', 'planner', 'technician', 'manager')),
    blocked INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE item (
    item_id INTEGER PRIMARY KEY,
    pn TEXT NOT NULL UNIQUE,          -- Part Number (P/N)
    name TEXT NOT NULL,
    base_uom TEXT NOT NULL,
    is_serial INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE item_uom (
    item_id INTEGER NOT NULL REFERENCES item(item_id),
    uom TEXT NOT NULL,
    factor INTEGER NOT NULL CHECK (factor > 0),
    PRIMARY KEY (item_id, uom)
);
CREATE TABLE location (
    location_id INTEGER PRIMARY KEY,
    code TEXT NOT NULL UNIQUE
);
CREATE TABLE batch (
    batch_id INTEGER PRIMARY KEY,
    item_id INTEGER NOT NULL REFERENCES item(item_id),
    batch_no TEXT NOT NULL,
    expiry_date TEXT,                 -- срок годности (shelf life), если задан
    cert_no TEXT,                     -- номер сертификата годности (Form 1 / сертификат соответствия)
    status TEXT NOT NULL DEFAULT 'ok' CHECK (status IN ('ok', 'quarantine')),
    CHECK (status = 'quarantine' OR cert_no IS NOT NULL),
    UNIQUE (item_id, batch_no)
);
CREATE TABLE serial_unit (
    item_id INTEGER NOT NULL REFERENCES item(item_id),
    serial_no TEXT NOT NULL,          -- серийный номер (S/N), уникален в пределах P/N
    receipt_id INTEGER NOT NULL REFERENCES receipt(receipt_id),
    batch_id INTEGER NOT NULL REFERENCES batch(batch_id),
    location_id INTEGER NOT NULL REFERENCES location(location_id),
    status TEXT NOT NULL DEFAULT 'in_stock' CHECK (status IN ('in_stock', 'issued', 'reversed')),
    PRIMARY KEY (item_id, serial_no)
);
CREATE TABLE receipt (
    receipt_id INTEGER PRIMARY KEY,
    doc_no TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL DEFAULT 'posted' CHECK (status IN ('posted', 'reversed')),
    created_by INTEGER NOT NULL REFERENCES app_user(user_id),
    created_at TEXT NOT NULL
);
CREATE TABLE receipt_line (
    line_id INTEGER PRIMARY KEY,
    receipt_id INTEGER NOT NULL REFERENCES receipt(receipt_id),
    item_id INTEGER NOT NULL REFERENCES item(item_id),
    batch_id INTEGER NOT NULL REFERENCES batch(batch_id),
    location_id INTEGER NOT NULL REFERENCES location(location_id),
    qty_doc INTEGER NOT NULL CHECK (qty_doc > 0),
    uom TEXT NOT NULL,
    qty_base INTEGER NOT NULL CHECK (qty_base > 0)
);
CREATE TABLE stock_balance (
    item_id INTEGER NOT NULL REFERENCES item(item_id),
    batch_id INTEGER NOT NULL REFERENCES batch(batch_id),
    location_id INTEGER NOT NULL REFERENCES location(location_id),
    on_hand INTEGER NOT NULL DEFAULT 0 CHECK (on_hand >= 0),
    reserved INTEGER NOT NULL DEFAULT 0 CHECK (reserved >= 0),
    PRIMARY KEY (item_id, batch_id, location_id),
    CHECK (reserved <= on_hand)
);
CREATE TABLE reservation (
    reservation_id INTEGER PRIMARY KEY,
    request_id TEXT NOT NULL UNIQUE,
    item_id INTEGER NOT NULL REFERENCES item(item_id),
    qty INTEGER NOT NULL CHECK (qty > 0),
    work_order TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'released', 'issued')),
    created_by INTEGER NOT NULL REFERENCES app_user(user_id),
    created_at TEXT NOT NULL
);
CREATE TABLE reservation_line (
    reservation_id INTEGER NOT NULL REFERENCES reservation(reservation_id),
    batch_id INTEGER NOT NULL REFERENCES batch(batch_id),
    location_id INTEGER NOT NULL REFERENCES location(location_id),
    qty INTEGER NOT NULL CHECK (qty > 0),
    PRIMARY KEY (reservation_id, batch_id, location_id)
);
CREATE TABLE stock_movement (
    movement_id INTEGER PRIMARY KEY,
    ts TEXT NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('RECEIPT', 'RESERVE', 'UNRESERVE', 'ISSUE', 'REVERSAL')),
    item_id INTEGER NOT NULL REFERENCES item(item_id),
    batch_id INTEGER NOT NULL REFERENCES batch(batch_id),
    location_id INTEGER NOT NULL REFERENCES location(location_id),
    qty_delta INTEGER NOT NULL,
    reserved_delta INTEGER NOT NULL,
    doc_ref TEXT NOT NULL,
    user_id INTEGER NOT NULL REFERENCES app_user(user_id),
    reverses_id INTEGER REFERENCES stock_movement(movement_id)
);
CREATE TRIGGER movement_no_update BEFORE UPDATE ON stock_movement
BEGIN SELECT RAISE(ABORT, 'stock_movement is append-only'); END;
CREATE TRIGGER movement_no_delete BEFORE DELETE ON stock_movement
BEGIN SELECT RAISE(ABORT, 'stock_movement is append-only'); END;
"""


def init_db(path: str) -> None:
    con = sqlite3.connect(path)
    con.executescript(SCHEMA)
    con.commit()
    con.close()


def connect(path: str) -> sqlite3.Connection:
    """Соединение без автоматических транзакций: границы задаёт сервис (BEGIN IMMEDIATE)."""
    con = sqlite3.connect(path, timeout=15, isolation_level=None)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con
