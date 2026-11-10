"""Автоматизированные проверки прототипа (TC-01 ... TC-23 из протокола проверки, отчёт, раздел 8)."""
import os
import sqlite3
import tempfile
import threading
import unittest
from datetime import date

from mro_stock import (IdempotencyConflict, InsufficientStock, InvalidState, StockService, NotFound,
                              PermissionDenied, ValidationError, init_db)

TODAY = date(2026, 11, 5)
SN_1 = "SG-40117"
SN_2 = "SG-40118"


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "inv.db")
        init_db(self.path)
        self.svc = StockService(self.path, today=lambda: TODAY)
        self.keeper = self.svc.add_user("Кладовщик", "storekeeper")
        self.plan = self.svc.add_user("Планировщик 1", "planner")
        self.plan2 = self.svc.add_user("Планировщик 2", "planner")
        self.boss = self.svc.add_user("Руководитель технической службы", "manager")
        self.tech = self.svc.add_user("Техник", "technician")
        self.svc.add_location(self.keeper, "A-01")
        self.svc.register_item(self.keeper, "FLT-HYD", "Фильтрующий элемент гидросистемы", "pcs", packs={"BOX": 10})

    def tearDown(self):
        self.tmp.cleanup()

    def receive(self, doc="R-1", qty=10, batch="B1", expiry=None, pn="FLT-HYD", uom=None):
        line = {"pn": pn, "qty": qty, "batch_no": batch, "expiry": expiry, "location": "A-01",
                "cert_no": f"CERT-{batch}"}
        if uom:
            line["uom"] = uom
        return self.svc.receive(self.keeper, doc, [line])

    def avail(self, pn="FLT-HYD"):
        return self.svc.availability(self.plan, pn)


class TestBasics(Base):
    def test_tc01_register_item_and_duplicate_sku(self):
        """TC-01: номенклатура регистрируется; повтор P/N и неверный P/N отклоняются."""
        with self.assertRaises(ValidationError):
            self.svc.register_item(self.keeper, "FLT-HYD", "Дубль", "pcs")
        with self.assertRaises(ValidationError):
            self.svc.register_item(self.keeper, "flt 1", "Плохой P/N", "pcs")
        with self.assertRaises(ValidationError):
            self.svc.register_item(self.keeper, "BOLT-1", "Болт", "pcs", packs={"BOX": 1})
        self.assertEqual(self.avail()["on_hand"], 0)

    def test_tc02_receipt_updates_stock_and_history(self):
        """TC-02: приход увеличивает остаток и доступное, в истории одно движение RECEIPT."""
        self.receive(qty=10)
        self.assertEqual(self.avail(), {"on_hand": 10, "reserved": 0, "available": 10, "unusable": 0})
        hist = self.svc.history(self.plan, "FLT-HYD")
        self.assertEqual([h["kind"] for h in hist], ["RECEIPT"])
        self.assertEqual(hist[0]["qty_delta"], 10)

    def test_tc03_unit_conversion(self):
        """TC-03: 2 упаковки по 10 принимаются как 20 штук; неизвестная единица отклоняется."""
        self.receive(qty=2, uom="BOX")
        self.assertEqual(self.avail()["on_hand"], 20)
        with self.assertRaises(ValidationError):
            self.receive(doc="R-2", qty=1, uom="PALLET")

    def test_tc04_repeated_document(self):
        """TC-04: повторная обработка того же документа не меняет остаток."""
        first = self.receive(doc="R-1", qty=10)
        second = self.receive(doc="R-1", qty=10)
        self.assertFalse(first["duplicate"])
        self.assertTrue(second["duplicate"])
        self.assertEqual(self.avail()["on_hand"], 10)
        self.assertEqual(len(self.svc.history(self.plan, "FLT-HYD")), 1)


class TestReservation(Base):
    def test_tc05_reserve_within_available(self):
        """TC-05: резерв в пределах доступного уменьшает доступное, остаток не меняется."""
        self.receive(qty=10)
        res = self.svc.reserve(self.plan, "REQ-1", "FLT-HYD", 4, "WO-1001")
        self.assertEqual(res["status"], "active")
        self.assertEqual(self.avail(), {"on_hand": 10, "reserved": 4, "available": 6, "unusable": 0})

    def test_tc06_insufficient_stock(self):
        """TC-06: запрос больше доступного отклоняется с указанием доступного; состояние не меняется."""
        self.receive(qty=10)
        self.svc.reserve(self.plan, "REQ-1", "FLT-HYD", 8, "WO-1001")
        with self.assertRaises(InsufficientStock) as ctx:
            self.svc.reserve(self.plan2, "REQ-2", "FLT-HYD", 8, "WO-1002")
        self.assertEqual((ctx.exception.requested, ctx.exception.available), (8, 2))
        self.assertEqual(self.avail()["reserved"], 8)
        self.assertEqual(len([h for h in self.svc.history(self.plan, "FLT-HYD") if h["kind"] == "RESERVE"]), 1)

    def test_tc07_repeated_request(self):
        """TC-07: повтор запроса с тем же ключом даёт тот же резерв; другие данные под тем же ключом – конфликт."""
        self.receive(qty=10)
        a = self.svc.reserve(self.plan, "REQ-1", "FLT-HYD", 4, "WO-1001")
        b = self.svc.reserve(self.plan, "REQ-1", "FLT-HYD", 4, "WO-1001")
        self.assertEqual(a["reservation_id"], b["reservation_id"])
        self.assertTrue(b["duplicate"])
        self.assertEqual(self.avail()["reserved"], 4)
        with self.assertRaises(IdempotencyConflict):
            self.svc.reserve(self.plan, "REQ-1", "FLT-HYD", 5, "WO-1001")

    def test_tc08_parallel_reservation(self):
        """TC-08: два одновременных резерва по 8 из 10 (20 повторов): всегда ровно один успех, резерв 8."""
        for attempt in range(20):
            with tempfile.TemporaryDirectory() as tmp:
                path = os.path.join(tmp, "inv.db")
                init_db(path)
                svc = StockService(path, today=lambda: TODAY)
                keeper = svc.add_user("K", "storekeeper")
                s1, s2 = svc.add_user("S1", "planner"), svc.add_user("S2", "planner")
                svc.add_location(keeper, "A-01")
                svc.register_item(keeper, "FLT-HYD", "Фильтр", "pcs")
                svc.receive(keeper, "R-1", [{"pn": "FLT-HYD", "qty": 10, "batch_no": "B1", "location": "A-01", "cert_no": "C1"}])
                barrier, results = threading.Barrier(2), []

                def worker(user, key):
                    barrier.wait()
                    try:
                        svc.reserve(user, key, "FLT-HYD", 8, "WO-" + key[-1].replace("A", "1001").replace("B", "1002"))
                        results.append("ok")
                    except InsufficientStock as e:
                        results.append(("rejected", e.available))

                threads = [threading.Thread(target=worker, args=(s1, "REQ-A")),
                           threading.Thread(target=worker, args=(s2, "REQ-B"))]
                [t.start() for t in threads]
                [t.join() for t in threads]
                self.assertEqual(results.count("ok"), 1, f"повтор {attempt}: {results}")
                self.assertIn(("rejected", 2), results)
                self.assertEqual(svc.availability(s1, "FLT-HYD")["reserved"], 8)
                self.assertEqual(svc.check_consistency(), [])

    def test_tc09_unauthorized_actions(self):
        """TC-09: действия не по роли (в т. ч. техника) отклоняются, данные не меняются; чужой резерв снимает только руководитель."""
        with self.assertRaises(PermissionDenied):
            self.svc.receive(self.plan, "R-X", [{"pn": "FLT-HYD", "qty": 5, "location": "A-01"}])
        with self.assertRaises(PermissionDenied):
            self.svc.receive(self.tech, "R-Y", [{"pn": "FLT-HYD", "qty": 5, "location": "A-01"}])
        self.receive(qty=10)
        with self.assertRaises(PermissionDenied):
            self.svc.reserve(self.keeper, "REQ-1", "FLT-HYD", 1, "WO-1003")
        with self.assertRaises(PermissionDenied):
            self.svc.reserve(self.tech, "REQ-1", "FLT-HYD", 1, "WO-1003")
        res = self.svc.reserve(self.plan, "REQ-2", "FLT-HYD", 3, "WO-1001")
        with self.assertRaises(PermissionDenied):
            self.svc.release(self.plan2, res["reservation_id"])
        with self.assertRaises(PermissionDenied):
            self.svc.issue(self.plan, res["reservation_id"])
        self.assertEqual(self.avail(), {"on_hand": 10, "reserved": 3, "available": 7, "unusable": 0})
        self.assertEqual(self.svc.release(self.boss, res["reservation_id"])["status"], "released")

    def test_tc10_issue_reserved(self):
        """TC-10: выдача по резерву уменьшает остаток и резерв; повторная выдача запрещена."""
        self.receive(qty=10)
        res = self.svc.reserve(self.plan, "REQ-1", "FLT-HYD", 4, "WO-1001")
        self.svc.issue(self.keeper, res["reservation_id"])
        self.assertEqual(self.avail(), {"on_hand": 6, "reserved": 0, "available": 6, "unusable": 0})
        with self.assertRaises(InvalidState):
            self.svc.issue(self.keeper, res["reservation_id"])
        kinds = [h["kind"] for h in self.svc.history(self.plan, "FLT-HYD")]
        self.assertEqual(kinds, ["RECEIPT", "RESERVE", "ISSUE"])

    def test_tc11_release_restores_availability(self):
        """TC-11: снятие резерва возвращает доступное; повторное снятие запрещено."""
        self.receive(qty=10)
        res = self.svc.reserve(self.plan, "REQ-1", "FLT-HYD", 8, "WO-1001")
        self.svc.release(self.plan, res["reservation_id"])
        self.assertEqual(self.avail()["available"], 10)
        with self.assertRaises(InvalidState):
            self.svc.release(self.plan, res["reservation_id"])
        self.svc.reserve(self.plan2, "REQ-2", "FLT-HYD", 8, "WO-1002")


class TestQuality(Base):
    def test_tc12_quarantined_batch(self):
        """TC-12: партия в карантине не попадает в доступное; выдача из неё запрещена."""
        self.receive(doc="R-1", qty=5, batch="B1")
        res = self.svc.reserve(self.plan, "REQ-1", "FLT-HYD", 3, "WO-1001")
        self.svc.quarantine_batch(self.keeper, "FLT-HYD", "B1")
        self.assertEqual(self.avail()["available"], 0)
        self.assertEqual(self.avail()["unusable"], 5)
        with self.assertRaises(InsufficientStock):
            self.svc.reserve(self.plan, "REQ-2", "FLT-HYD", 1, "WO-1002")
        with self.assertRaises(InvalidState):
            self.svc.issue(self.keeper, res["reservation_id"])
        self.assertEqual(self.svc.availability(self.plan, "FLT-HYD")["on_hand"], 5)

    def test_tc13_expired_batch(self):
        """TC-13: просроченная партия не резервируется; резерв, выданный до срока, нельзя выдать после него."""
        with self.assertRaises(ValidationError):
            self.receive(doc="R-0", qty=1, batch="OLD", expiry="2026-10-01")
        self.receive(doc="R-1", qty=5, batch="B1", expiry="2026-11-10")
        res = self.svc.reserve(self.plan, "REQ-1", "FLT-HYD", 2, "WO-1001")
        later = StockService(self.path, today=lambda: date(2026, 11, 11))
        self.assertEqual(later.availability(self.plan, "FLT-HYD")["available"], 0)
        with self.assertRaises(InsufficientStock):
            later.reserve(self.plan, "REQ-2", "FLT-HYD", 1, "WO-1002")
        with self.assertRaises(InvalidState):
            later.issue(self.keeper, res["reservation_id"])

    def test_tc14_fefo_allocation(self):
        """TC-14: резерв берёт сначала партию с ближайшим сроком годности и может охватить две партии."""
        self.receive(doc="R-1", qty=5, batch="LATE", expiry="2027-06-01")
        self.receive(doc="R-2", qty=5, batch="SOON", expiry="2026-12-01")
        self.svc.reserve(self.plan, "REQ-1", "FLT-HYD", 7, "WO-1001")
        reserved = {h["batch_no"]: h["reserved_delta"] for h in self.svc.history(self.plan, "FLT-HYD")
                    if h["kind"] == "RESERVE"}
        self.assertEqual(reserved, {"SOON": 5, "LATE": 2})

    def test_tc15_reverse_confirmed_receipt(self):
        """TC-15: ошибочный приход исправляется встречным движением; при резерве части товара сторно запрещено."""
        self.receive(doc="R-1", qty=10)
        self.svc.reserve(self.plan, "REQ-1", "FLT-HYD", 4, "WO-1001")
        with self.assertRaises(InvalidState):
            self.svc.reverse_receipt(self.keeper, "R-1")
        self.receive(doc="R-2", qty=3, batch="B2")
        self.svc.reverse_receipt(self.keeper, "R-2")
        self.assertEqual(self.avail()["on_hand"], 10)
        hist = self.svc.history(self.plan, "FLT-HYD")
        reversal = [h for h in hist if h["kind"] == "REVERSAL"][0]
        self.assertEqual(reversal["qty_delta"], -3)
        self.assertIsNotNone(reversal["reverses_id"])
        with self.assertRaises(InvalidState):
            self.svc.reverse_receipt(self.keeper, "R-2")

    def test_tc16_serial_numbers(self):
        """TC-16: серийная позиция принимается только с уникальными корректными S/N; выдача называет S/N."""
        self.svc.register_item(self.keeper, "STRGEN-1", "Стартёр-генератор", "pcs", is_serial=True)
        line = {"pn": "STRGEN-1", "qty": 2, "location": "A-01", "cert_no": "F1-77", "serials": [SN_1, SN_2]}
        for bad in (["SG1", SN_2], [SN_1, SN_1], ["sg-40117", SN_2], [SN_1]):
            with self.assertRaises(ValidationError):
                self.svc.receive(self.keeper, "R-C", [dict(line, serials=bad)])
        self.assertEqual(self.svc.availability(self.plan, "STRGEN-1")["on_hand"], 0)
        self.svc.receive(self.keeper, "R-C", [line])
        with self.assertRaises(ValidationError):
            self.svc.receive(self.keeper, "R-C2", [dict(line, qty=1, serials=[SN_1], cert_no="F1-78", batch_no="B2")])
        res = self.svc.reserve(self.plan, "REQ-C", "STRGEN-1", 1, "WO-1001")
        out = self.svc.issue(self.keeper, res["reservation_id"])
        self.assertEqual(out["serials"], [SN_1])


class TestIntegrity(Base):
    def test_tc17_rollback_on_failure(self):
        """TC-17: сбой в середине операции откатывает всё: приход с неверной второй строкой и сбой при резерве."""
        with self.assertRaises(ValidationError):
            self.svc.receive(self.keeper, "R-BAD", [
                {"pn": "FLT-HYD", "qty": 5, "batch_no": "B1", "location": "A-01", "cert_no": "C1"},
                {"pn": "FLT-HYD", "qty": -1, "batch_no": "B2", "location": "A-01", "cert_no": "C2"}])
        self.assertEqual(self.avail()["on_hand"], 0)
        self.assertEqual(self.svc.history(self.plan, "FLT-HYD"), [])
        self.receive(qty=10)

        def boom(point):
            if point == "reserve:after_update":
                raise RuntimeError("сбой")

        self.svc.fault_hook = boom
        with self.assertRaises(RuntimeError):
            self.svc.reserve(self.plan, "REQ-1", "FLT-HYD", 4, "WO-1001")
        self.svc.fault_hook = None
        self.assertEqual(self.avail()["reserved"], 0)
        self.assertEqual(len(self.svc.history(self.plan, "FLT-HYD")), 1)

    def test_tc18_stored_balance_equals_movements(self):
        """TC-18: после серии операций хранимый остаток и резерв равны сумме движений и активных резервов."""
        self.receive(doc="R-1", qty=10, batch="B1", expiry="2027-01-01")
        self.receive(doc="R-2", qty=5, batch="B2", expiry="2026-12-01")
        a = self.svc.reserve(self.plan, "REQ-1", "FLT-HYD", 6, "WO-1001")
        b = self.svc.reserve(self.plan, "REQ-2", "FLT-HYD", 3, "WO-1002")
        self.svc.issue(self.keeper, a["reservation_id"])
        self.svc.release(self.plan, b["reservation_id"])
        self.receive(doc="R-3", qty=2, batch="B3")
        self.svc.reverse_receipt(self.keeper, "R-3")
        self.assertEqual(self.svc.check_consistency(), [])
        self.assertEqual(self.avail(), {"on_hand": 9, "reserved": 0, "available": 9, "unusable": 0})

    def test_tc19_movement_log_is_append_only(self):
        """TC-19: журнал движений нельзя изменить или удалить средствами СУБД (триггеры)."""
        self.receive(qty=10)
        con = sqlite3.connect(self.path)
        with self.assertRaises(sqlite3.DatabaseError):
            con.execute("UPDATE stock_movement SET qty_delta = 99")
        with self.assertRaises(sqlite3.DatabaseError):
            con.execute("DELETE FROM stock_movement")
        con.close()

    def test_tc20_db_constraint_is_last_line_of_defence(self):
        """TC-20: даже прямая запись в СУБД не может сделать резерв больше остатка."""
        self.receive(qty=10)
        con = sqlite3.connect(self.path)
        with self.assertRaises(sqlite3.IntegrityError):
            con.execute("UPDATE stock_balance SET reserved = 11")
        con.close()

    def test_tc21_unknown_item_and_user(self):
        """TC-21: неизвестная номенклатура и неизвестный пользователь отклоняются."""
        with self.assertRaises(NotFound):
            self.svc.reserve(self.plan, "REQ-1", "NO-SUCH", 1, "WO-1003")
        with self.assertRaises(NotFound):
            self.svc.availability(999, "FLT-HYD")


class TestAirworthiness(Base):
    def test_tc22_batch_without_certificate_goes_to_quarantine(self):
        """TC-22: партия без сертификата годности принимается в карантин; снять его может только руководитель с номером."""
        self.svc.receive(self.keeper, "R-NC", [{"pn": "FLT-HYD", "qty": 6, "batch_no": "NC1", "location": "A-01"}])
        self.assertEqual(self.avail(), {"on_hand": 6, "reserved": 0, "available": 0, "unusable": 6})
        with self.assertRaises(InsufficientStock):
            self.svc.reserve(self.plan, "REQ-1", "FLT-HYD", 1, "WO-1001")
        with self.assertRaises(PermissionDenied):
            self.svc.certify_batch(self.keeper, "FLT-HYD", "NC1", "F1-100")
        with self.assertRaises(ValidationError):
            self.svc.certify_batch(self.boss, "FLT-HYD", "NC1")
        self.svc.certify_batch(self.boss, "FLT-HYD", "NC1", "F1-100")
        self.assertEqual(self.avail()["available"], 6)
        self.assertEqual(self.svc.reserve(self.plan, "REQ-1", "FLT-HYD", 2, "WO-1001")["status"], "active")

    def test_tc23_reservation_requires_work_order(self):
        """TC-23: резерв без заказ-наряда или с неверным форматом отклоняется, данные не меняются."""
        self.receive(qty=10)
        for bad in (None, "", "ЗН-5", "WO-1", "wo-1001"):
            with self.assertRaises(ValidationError):
                self.svc.reserve(self.plan, "REQ-1", "FLT-HYD", 1, bad)
        self.assertEqual(self.avail()["reserved"], 0)


class TestControlWithoutTransaction(unittest.TestCase):
    def test_control_naive_reserve_oversells(self):
        """Контроль: проверка и запись раздельно, без транзакции и без CHECK, дают резерв 16 при остатке 10."""
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "naive.db")
            con = sqlite3.connect(path)
            con.execute("CREATE TABLE stock (on_hand INTEGER, reserved INTEGER)")
            con.execute("INSERT INTO stock VALUES (10, 0)")
            con.commit()
            con.close()
            barrier = threading.Barrier(2)
            outcome = []

            def naive():
                c = sqlite3.connect(path, timeout=15)
                on_hand, reserved = c.execute("SELECT on_hand, reserved FROM stock").fetchone()
                barrier.wait()  # оба прочитали «доступно 10»
                if on_hand - reserved >= 8:
                    c.execute("UPDATE stock SET reserved = reserved + 8")
                    c.commit()
                    outcome.append("ok")
                c.close()

            threads = [threading.Thread(target=naive) for _ in range(2)]
            [t.start() for t in threads]
            [t.join() for t in threads]
            c = sqlite3.connect(path)
            reserved = c.execute("SELECT reserved FROM stock").fetchone()[0]
            c.close()
            self.assertEqual(outcome, ["ok", "ok"])
            self.assertEqual(reserved, 16)


if __name__ == "__main__":
    unittest.main()
