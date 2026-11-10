"""Сервис учёта запасов склада запасных частей и материалов авиатехнической базы.

Правила (коды из отчёта, раздел 2.3):
    BR-01 резерв только в пределах доступного (доступно = остаток - резерв, только годные партии);
    BR-02 отпуск из карантинной или просроченной партии запрещён;
    BR-03 повторный документ или повторный запрос резерва не создаёт дубликат;
    BR-04 подтверждённая операция не правится: исправление – встречным движением;
    BR-05 количество хранится в базовой единице, документы – в упаковках с коэффициентом;
    BR-06 действие допустимо только роли, которой оно разрешено;
    BR-07 серийная единица (S/N) уникальна в пределах P/N, формат 4-30 символов (A-Z, 0-9, дефис);
    BR-08 журнал движений неизменяем;
    BR-13 партия без сертификата годности принимается только в карантин;
    BR-14 резерв оформляется только под заказ-наряд формата WO-NNNN.
Каждая операция – одна транзакция BEGIN IMMEDIATE: проверка остатка и запись резерва неделимы.
"""
import re
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime

from . import db
from .errors import (IdempotencyConflict, InsufficientStock, InvalidState, NotFound, PermissionDenied,
                     ValidationError)

SN_RE = re.compile(r"^[A-Z0-9][A-Z0-9-]{3,29}$")
WO_RE = re.compile(r"^WO-[0-9]{3,8}$")
PN_RE = re.compile(r"^[A-Z0-9][A-Z0-9-]{1,19}$")
ALL_ROLES = {"admin", "storekeeper", "planner", "technician", "manager"}
PERMISSIONS = {
    "add_location": {"admin", "storekeeper"},
    "register_item": {"admin", "storekeeper"},
    "receive": {"storekeeper"},
    "reverse_receipt": {"storekeeper"},
    "quarantine_batch": {"storekeeper", "manager"},
    "certify_batch": {"manager"},
    "reserve": {"planner", "manager"},
    "release": {"planner", "manager"},
    "issue": {"storekeeper"},
    "view": ALL_ROLES,
}


class StockService:
    def __init__(self, path: str, today=date.today):
        self.path = path
        self.today = today
        self.fault_hook = None  # для проверки отката: вызывается в контрольных точках

    # ---------- служебное ----------
    @contextmanager
    def _tx(self):
        con = db.connect(self.path)
        try:
            con.execute("BEGIN IMMEDIATE")
            yield con
            con.execute("COMMIT")
        except BaseException:
            if con.in_transaction:
                con.execute("ROLLBACK")
            raise
        finally:
            con.close()

    def _fault(self, point: str) -> None:
        if self.fault_hook:
            self.fault_hook(point)

    def _now(self) -> str:
        return datetime.now().isoformat(timespec="seconds")

    def _user(self, con, user_id: int, action: str):
        row = con.execute("SELECT * FROM app_user WHERE user_id = ?", (user_id,)).fetchone()
        if row is None:
            raise NotFound(f"Пользователь {user_id} не найден")
        if row["blocked"] or row["role"] not in PERMISSIONS[action]:
            raise PermissionDenied(f"Роль «{row['role']}» не может выполнять «{action}»")
        return row

    def _item(self, con, pn: str):
        row = con.execute("SELECT * FROM item WHERE pn = ?", (pn,)).fetchone()
        if row is None:
            raise NotFound(f"Номенклатура {pn} не найдена")
        return row

    def _usable_sql(self) -> str:
        return "b.status = 'ok' AND (b.expiry_date IS NULL OR b.expiry_date >= :today)"

    def add_user(self, name: str, role: str) -> int:
        """Начальная настройка (без проверки прав): создаёт пользователя."""
        with self._tx() as con:
            cur = con.execute("INSERT INTO app_user(name, role) VALUES (?, ?)", (name, role))
            return cur.lastrowid

    # ---------- справочники ----------
    def add_location(self, user_id: int, code: str) -> int:
        with self._tx() as con:
            self._user(con, user_id, "add_location")
            if not code or not code.strip():
                raise ValidationError("Код места хранения пуст")
            if con.execute("SELECT 1 FROM location WHERE code = ?", (code,)).fetchone():
                raise ValidationError(f"Место {code} уже есть")
            return con.execute("INSERT INTO location(code) VALUES (?)", (code,)).lastrowid

    def register_item(self, user_id: int, pn: str, name: str, base_uom: str, is_serial: bool = False,
                      packs: dict | None = None) -> int:
        with self._tx() as con:
            self._user(con, user_id, "register_item")
            if not PN_RE.match(pn or ""):
                raise ValidationError("P/N: 2-20 символов, заглавные латинские буквы, цифры и дефис")
            if not name or not name.strip() or not base_uom:
                raise ValidationError("Наименование и базовая единица обязательны")
            if con.execute("SELECT 1 FROM item WHERE pn = ?", (pn,)).fetchone():
                raise ValidationError(f"P/N {pn} уже зарегистрирован")
            item_id = con.execute("INSERT INTO item(pn, name, base_uom, is_serial) VALUES (?,?,?,?)",
                                  (pn, name.strip(), base_uom, int(is_serial))).lastrowid
            con.execute("INSERT INTO item_uom VALUES (?,?,1)", (item_id, base_uom))
            for uom, factor in (packs or {}).items():
                if not isinstance(factor, int) or factor < 2 or uom == base_uom:
                    raise ValidationError(f"Коэффициент упаковки {uom} должен быть целым числом больше 1")
                con.execute("INSERT INTO item_uom VALUES (?,?,?)", (item_id, uom, factor))
            return item_id

    def quarantine_batch(self, user_id: int, pn: str, batch_no: str) -> None:
        """Перевод партии в карантин (подозрение на несоответствие): партия перестаёт быть доступной."""
        with self._tx() as con:
            self._user(con, user_id, "quarantine_batch")
            item = self._item(con, pn)
            cur = con.execute("UPDATE batch SET status = 'quarantine' WHERE item_id = ? AND batch_no = ?",
                              (item["item_id"], batch_no))
            if cur.rowcount != 1:
                raise NotFound(f"Партия {batch_no} не найдена")

    def certify_batch(self, user_id: int, pn: str, batch_no: str, cert_no: str | None = None) -> None:
        """Снятие карантина инспектором качества. Партия без сертификата требует его номер (BR-13)."""
        with self._tx() as con:
            self._user(con, user_id, "certify_batch")
            item = self._item(con, pn)
            batch = con.execute("SELECT * FROM batch WHERE item_id = ? AND batch_no = ?",
                                (item["item_id"], batch_no)).fetchone()
            if batch is None:
                raise NotFound(f"Партия {batch_no} не найдена")
            cert = (cert_no or "").strip() or batch["cert_no"]
            if not cert:
                raise ValidationError("Для снятия карантина нужен номер сертификата годности")
            con.execute("UPDATE batch SET status = 'ok', cert_no = ? WHERE batch_id = ?", (cert, batch["batch_id"]))

    # ---------- приход ----------
    def receive(self, user_id: int, doc_no: str, lines: list[dict]) -> dict:
        """lines: pn, qty, uom (необязательно), batch_no, expiry ('ГГГГ-ММ-ДД'), cert_no, location, serials (для серийных)."""
        with self._tx() as con:
            self._user(con, user_id, "receive")
            if not doc_no or not doc_no.strip():
                raise ValidationError("Номер документа обязателен")
            old = con.execute("SELECT receipt_id FROM receipt WHERE doc_no = ?", (doc_no,)).fetchone()
            if old:
                return {"receipt_id": old["receipt_id"], "duplicate": True}
            if not lines:
                raise ValidationError("В документе нет строк")
            rid = con.execute("INSERT INTO receipt(doc_no, created_by, created_at) VALUES (?,?,?)",
                              (doc_no, user_id, self._now())).lastrowid
            for ln in lines:
                self._receive_line(con, user_id, rid, doc_no, ln)
            self._fault("receive:after_lines")
            return {"receipt_id": rid, "duplicate": False}

    def _receive_line(self, con, user_id, rid, doc_no, ln) -> None:
        item = self._item(con, ln.get("pn", ""))
        qty = ln.get("qty")
        if not isinstance(qty, int) or isinstance(qty, bool) or qty <= 0:
            raise ValidationError("Количество должно быть целым числом больше 0")
        uom = ln.get("uom") or item["base_uom"]
        factor = con.execute("SELECT factor FROM item_uom WHERE item_id = ? AND uom = ?",
                             (item["item_id"], uom)).fetchone()
        if factor is None:
            raise ValidationError(f"Единица {uom} не определена для {item['pn']}")
        qty_base = qty * factor["factor"]
        loc = con.execute("SELECT location_id FROM location WHERE code = ?", (ln.get("location"),)).fetchone()
        if loc is None:
            raise NotFound(f"Место хранения {ln.get('location')} не найдено")
        expiry = ln.get("expiry")
        if expiry:
            try:
                exp_date = date.fromisoformat(expiry)
            except ValueError:
                raise ValidationError("Срок годности: формат ГГГГ-ММ-ДД")
            if exp_date < self.today():
                raise ValidationError("Партия просрочена на момент приёмки")
        batch_no = ln.get("batch_no") or "-"
        cert_no = (ln.get("cert_no") or "").strip() or None
        batch = con.execute("SELECT * FROM batch WHERE item_id = ? AND batch_no = ?",
                            (item["item_id"], batch_no)).fetchone()
        if batch is None:
            # BR-13: без сертификата годности партия принимается, но сразу попадает в карантин
            status = "ok" if cert_no else "quarantine"
            batch_id = con.execute("INSERT INTO batch(item_id, batch_no, expiry_date, cert_no, status) "
                                   "VALUES (?,?,?,?,?)", (item["item_id"], batch_no, expiry, cert_no, status)).lastrowid
        else:
            batch_id = batch["batch_id"]
            if (batch["expiry_date"] or None) != (expiry or None):
                raise ValidationError(f"Партия {batch_no} уже есть с другим сроком годности")
            if cert_no and batch["cert_no"] and cert_no != batch["cert_no"]:
                raise ValidationError(f"Партия {batch_no} уже есть с другим сертификатом")
        if item["is_serial"]:
            serials = ln.get("serials") or []
            if len(serials) != qty_base or len(set(serials)) != len(serials):
                raise ValidationError("Для серийной позиции нужен уникальный S/N на каждую единицу")
            for sn in serials:
                if not SN_RE.match(sn):
                    raise ValidationError(f"S/N {sn}: 4-30 символов, заглавная латиница, цифры и дефис")
                if con.execute("SELECT 1 FROM serial_unit WHERE item_id = ? AND serial_no = ?",
                               (item["item_id"], sn)).fetchone():
                    raise ValidationError(f"S/N {sn} для {item['pn']} уже принят")
                con.execute("INSERT INTO serial_unit(item_id, serial_no, receipt_id, batch_id, location_id) "
                            "VALUES (?,?,?,?,?)", (item["item_id"], sn, rid, batch_id, loc["location_id"]))
        con.execute("INSERT INTO receipt_line(receipt_id, item_id, batch_id, location_id, qty_doc, uom, qty_base) "
                    "VALUES (?,?,?,?,?,?,?)",
                    (rid, item["item_id"], batch_id, loc["location_id"], qty, uom, qty_base))
        con.execute("INSERT INTO stock_balance(item_id, batch_id, location_id, on_hand) VALUES (?,?,?,?) "
                    "ON CONFLICT(item_id, batch_id, location_id) DO UPDATE SET on_hand = on_hand + excluded.on_hand",
                    (item["item_id"], batch_id, loc["location_id"], qty_base))
        self._movement(con, "RECEIPT", item["item_id"], batch_id, loc["location_id"], qty_base, 0,
                       f"RCPT:{doc_no}", user_id)

    def _movement(self, con, kind, item_id, batch_id, location_id, qty_delta, reserved_delta, doc_ref, user_id,
                  reverses_id=None) -> int:
        return con.execute(
            "INSERT INTO stock_movement(ts, kind, item_id, batch_id, location_id, qty_delta, reserved_delta, "
            "doc_ref, user_id, reverses_id) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (self._now(), kind, item_id, batch_id, location_id, qty_delta, reserved_delta, doc_ref, user_id,
             reverses_id)).lastrowid

    def reverse_receipt(self, user_id: int, doc_no: str) -> dict:
        """Исправление подтверждённого прихода встречным движением (BR-04)."""
        with self._tx() as con:
            self._user(con, user_id, "reverse_receipt")
            rec = con.execute("SELECT * FROM receipt WHERE doc_no = ?", (doc_no,)).fetchone()
            if rec is None:
                raise NotFound(f"Документ {doc_no} не найден")
            if rec["status"] != "posted":
                raise InvalidState(f"Документ {doc_no} уже сторнирован")
            lines = con.execute("SELECT * FROM receipt_line WHERE receipt_id = ?", (rec["receipt_id"],)).fetchall()
            for ln in lines:
                bal = con.execute("SELECT on_hand, reserved FROM stock_balance WHERE item_id=? AND batch_id=? "
                                  "AND location_id=?", (ln["item_id"], ln["batch_id"], ln["location_id"])).fetchone()
                if bal["on_hand"] - bal["reserved"] < ln["qty_base"]:
                    raise InvalidState("Часть принятого товара уже зарезервирована или отпущена, сторно невозможно")
            if con.execute("SELECT 1 FROM serial_unit WHERE receipt_id = ? AND status != 'in_stock'",
                           (rec["receipt_id"],)).fetchone():
                raise InvalidState("Часть серийных единиц уже отпущена, сторно невозможно")
            for ln in lines:
                orig = con.execute("SELECT movement_id FROM stock_movement WHERE doc_ref = ? AND item_id = ? "
                                   "AND batch_id = ? AND location_id = ? AND kind = 'RECEIPT'",
                                   (f"RCPT:{doc_no}", ln["item_id"], ln["batch_id"], ln["location_id"])).fetchone()
                con.execute("UPDATE stock_balance SET on_hand = on_hand - ? WHERE item_id=? AND batch_id=? "
                            "AND location_id=?", (ln["qty_base"], ln["item_id"], ln["batch_id"], ln["location_id"]))
                self._movement(con, "REVERSAL", ln["item_id"], ln["batch_id"], ln["location_id"], -ln["qty_base"], 0,
                               f"RCPT:{doc_no}", user_id, orig["movement_id"])
            con.execute("UPDATE serial_unit SET status = 'reversed' WHERE receipt_id = ?", (rec["receipt_id"],))
            con.execute("UPDATE receipt SET status = 'reversed' WHERE receipt_id = ?", (rec["receipt_id"],))
            return {"receipt_id": rec["receipt_id"], "status": "reversed"}

    # ---------- резерв ----------
    def reserve(self, user_id: int, request_id: str, pn: str, qty: int, work_order: str) -> dict:
        """Резерв под заказ-наряд по правилу FEFO среди годных партий. Повтор с тем же request_id возвращает прежний резерв."""
        with self._tx() as con:
            self._user(con, user_id, "reserve")
            if not request_id:
                raise ValidationError("Ключ запроса обязателен")
            if not isinstance(qty, int) or isinstance(qty, bool) or qty <= 0:
                raise ValidationError("Количество должно быть целым числом больше 0")
            if not WO_RE.match(work_order or ""):
                raise ValidationError("Резерв оформляется под заказ-наряд формата WO-NNNN (BR-14)")
            item = self._item(con, pn)
            old = con.execute("SELECT * FROM reservation WHERE request_id = ?", (request_id,)).fetchone()
            if old:
                if (old["item_id"], old["qty"], old["work_order"]) != (item["item_id"], qty, work_order):
                    raise IdempotencyConflict("Ключ запроса уже использован с другими данными")
                return {"reservation_id": old["reservation_id"], "qty": old["qty"], "status": old["status"],
                        "duplicate": True}
            rows = con.execute(
                "SELECT s.batch_id, s.location_id, s.on_hand - s.reserved AS avail FROM stock_balance s "
                "JOIN batch b ON b.batch_id = s.batch_id WHERE s.item_id = :item AND "
                + self._usable_sql() + " AND s.on_hand - s.reserved > 0 "
                "ORDER BY b.expiry_date IS NULL, b.expiry_date, b.batch_id",
                {"item": item["item_id"], "today": self.today().isoformat()}).fetchall()
            total = sum(r["avail"] for r in rows)
            if total < qty:
                raise InsufficientStock(qty, total)
            rid = con.execute("INSERT INTO reservation(request_id, item_id, qty, work_order, created_by, "
                              "created_at) VALUES (?,?,?,?,?,?)",
                              (request_id, item["item_id"], qty, work_order, user_id, self._now())).lastrowid
            left = qty
            for r in rows:
                take = min(left, r["avail"])
                cur = con.execute("UPDATE stock_balance SET reserved = reserved + ? WHERE item_id = ? AND "
                                  "batch_id = ? AND location_id = ? AND on_hand - reserved >= ?",
                                  (take, item["item_id"], r["batch_id"], r["location_id"], take))
                if cur.rowcount != 1:
                    raise InsufficientStock(qty, total)
                self._fault("reserve:after_update")
                con.execute("INSERT INTO reservation_line VALUES (?,?,?,?)",
                            (rid, r["batch_id"], r["location_id"], take))
                self._movement(con, "RESERVE", item["item_id"], r["batch_id"], r["location_id"], 0, take,
                               f"RSV:{rid}", user_id)
                left -= take
                if not left:
                    break
            return {"reservation_id": rid, "qty": qty, "status": "active", "duplicate": False}

    def _active_reservation(self, con, reservation_id: int):
        res = con.execute("SELECT * FROM reservation WHERE reservation_id = ?", (reservation_id,)).fetchone()
        if res is None:
            raise NotFound(f"Резерв {reservation_id} не найден")
        if res["status"] != "active":
            raise InvalidState(f"Резерв {reservation_id} уже в статусе «{res['status']}»")
        return res

    def release(self, user_id: int, reservation_id: int) -> dict:
        with self._tx() as con:
            user = self._user(con, user_id, "release")
            res = self._active_reservation(con, reservation_id)
            if user["role"] != "manager" and res["created_by"] != user_id:
                raise PermissionDenied("Чужой резерв может снять только руководитель")
            for ln in con.execute("SELECT * FROM reservation_line WHERE reservation_id = ?",
                                  (reservation_id,)).fetchall():
                con.execute("UPDATE stock_balance SET reserved = reserved - ? WHERE item_id = ? AND batch_id = ? "
                            "AND location_id = ?", (ln["qty"], res["item_id"], ln["batch_id"], ln["location_id"]))
                self._movement(con, "UNRESERVE", res["item_id"], ln["batch_id"], ln["location_id"], 0, -ln["qty"],
                               f"RSV:{reservation_id}", user_id)
            con.execute("UPDATE reservation SET status = 'released' WHERE reservation_id = ?", (reservation_id,))
            return {"reservation_id": reservation_id, "status": "released"}

    def issue(self, user_id: int, reservation_id: int) -> dict:
        """Выдача по резерву: годность проверяется в момент выдачи (BR-02)."""
        with self._tx() as con:
            self._user(con, user_id, "issue")
            res = self._active_reservation(con, reservation_id)
            lines = con.execute("SELECT l.*, b.status, b.expiry_date, b.batch_no FROM reservation_line l "
                                "JOIN batch b ON b.batch_id = l.batch_id WHERE l.reservation_id = ?",
                                (reservation_id,)).fetchall()
            for ln in lines:
                if ln["status"] != "ok":
                    raise InvalidState(f"Партия {ln['batch_no']} в карантине, выдача запрещена")
                if ln["expiry_date"] and ln["expiry_date"] < self.today().isoformat():
                    raise InvalidState(f"Партия {ln['batch_no']} просрочена, выдача запрещена")
            for ln in lines:
                con.execute("UPDATE stock_balance SET on_hand = on_hand - ?, reserved = reserved - ? "
                            "WHERE item_id = ? AND batch_id = ? AND location_id = ?",
                            (ln["qty"], ln["qty"], res["item_id"], ln["batch_id"], ln["location_id"]))
                self._movement(con, "ISSUE", res["item_id"], ln["batch_id"], ln["location_id"], -ln["qty"],
                               -ln["qty"], f"RSV:{reservation_id}", user_id)
            serials = []
            item = con.execute("SELECT is_serial FROM item WHERE item_id = ?", (res["item_id"],)).fetchone()
            if item["is_serial"]:
                serials = [r["serial_no"] for r in con.execute(
                    "SELECT serial_no FROM serial_unit WHERE item_id = ? AND status = 'in_stock' "
                    "ORDER BY serial_no LIMIT ?", (res["item_id"], res["qty"])).fetchall()]
                con.executemany("UPDATE serial_unit SET status = 'issued' WHERE item_id = ? AND serial_no = ?",
                                [(res["item_id"], v) for v in serials])
            con.execute("UPDATE reservation SET status = 'issued' WHERE reservation_id = ?", (reservation_id,))
            return {"reservation_id": reservation_id, "status": "issued", "qty": res["qty"], "serials": serials}

    # ---------- просмотр ----------
    def availability(self, user_id: int, pn: str) -> dict:
        with self._tx() as con:
            self._user(con, user_id, "view")
            item = self._item(con, pn)
            row = con.execute(
                "SELECT COALESCE(SUM(s.on_hand), 0) AS on_hand, COALESCE(SUM(s.reserved), 0) AS reserved, "
                "COALESCE(SUM(CASE WHEN " + self._usable_sql() + " THEN s.on_hand - s.reserved ELSE 0 END), 0) "
                "AS available, "
                "COALESCE(SUM(CASE WHEN " + self._usable_sql() + " THEN 0 ELSE s.on_hand END), 0) AS unusable "
                "FROM stock_balance s JOIN batch b ON b.batch_id = s.batch_id WHERE s.item_id = :item",
                {"item": item["item_id"], "today": self.today().isoformat()}).fetchone()
            return dict(row)

    def history(self, user_id: int, pn: str) -> list[dict]:
        with self._tx() as con:
            self._user(con, user_id, "view")
            item = self._item(con, pn)
            rows = con.execute(
                "SELECT m.movement_id, m.ts, m.kind, b.batch_no, l.code AS location, m.qty_delta, m.reserved_delta, "
                "m.doc_ref, u.name AS user, m.reverses_id FROM stock_movement m "
                "JOIN batch b ON b.batch_id = m.batch_id JOIN location l ON l.location_id = m.location_id "
                "JOIN app_user u ON u.user_id = m.user_id WHERE m.item_id = ? ORDER BY m.movement_id",
                (item["item_id"],)).fetchall()
            return [dict(r) for r in rows]

    def check_consistency(self) -> list[str]:
        """Хранимый остаток должен равняться сумме движений; резерв – сумме активных резервов."""
        problems = []
        with self._tx() as con:
            rows = con.execute(
                "SELECT s.item_id, s.batch_id, s.location_id, s.on_hand, s.reserved, "
                "COALESCE((SELECT SUM(qty_delta) FROM stock_movement m WHERE m.item_id = s.item_id AND "
                "m.batch_id = s.batch_id AND m.location_id = s.location_id), 0) AS mv_on_hand, "
                "COALESCE((SELECT SUM(reserved_delta) FROM stock_movement m WHERE m.item_id = s.item_id AND "
                "m.batch_id = s.batch_id AND m.location_id = s.location_id), 0) AS mv_reserved, "
                "COALESCE((SELECT SUM(l.qty) FROM reservation_line l JOIN reservation r ON "
                "r.reservation_id = l.reservation_id WHERE r.status = 'active' AND r.item_id = s.item_id AND "
                "l.batch_id = s.batch_id AND l.location_id = s.location_id), 0) AS active_res FROM stock_balance s"
            ).fetchall()
            for r in rows:
                key = (r["item_id"], r["batch_id"], r["location_id"])
                if r["on_hand"] != r["mv_on_hand"]:
                    problems.append(f"{key}: остаток {r['on_hand']} != движения {r['mv_on_hand']}")
                if r["reserved"] != r["mv_reserved"] or r["reserved"] != r["active_res"]:
                    problems.append(f"{key}: резерв {r['reserved']} != движения {r['mv_reserved']} / "
                                    f"активные резервы {r['active_res']}")
        return problems
