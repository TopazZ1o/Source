"""Automated checks T01-T19. Every test starts from an independent copy of the initial state (setUp);
T08 builds its own database with the position TEST01."""

import sqlite3
import tempfile
import unittest

from inventory import results as R
from inventory.db import connect
from inventory.planning import Params, choose_lot, replenishment_report
from inventory.results import TechnicalError
from inventory.scenarios import p01_chain, parallel_reservation
from inventory.seed import WAREHOUSE
from inventory.service import InventoryService, PURCHASER, REQUESTER, STOREKEEPER

from .support import DbTestCase, journal, pos_text, record

W = WAREHOUSE


class Operations(DbTestCase):
    def test_t01_receive_increases_stock_once(self):
        before = self.service.position("P01", W)
        res = self.service.receive("IN01", STOREKEEPER, "P01", W, 40)
        journal("T01", res)
        after = self.service.position("P01", W)
        self.assertTrue(res.ok)
        self.assertEqual((after["oh"], after["r"]), (before["oh"] + 40, before["r"]))
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM movement WHERE document = 'IN01'").fetchone()[0], 1)
        record("T01", f"OK; OH {before['oh']} -> {after['oh']}; R {before['r']} -> {after['r']}; 1 движение RECEIPT")

    def test_t02_reserve_available_quantity(self):
        before = self.service.position("P01", W)
        res = self.service.reserve("RES01", REQUESTER, "P01", W, 60, "WO-2001")
        journal("T02", res)
        after = self.service.position("P01", W)
        self.assertTrue(res.ok)
        self.assertEqual((after["oh"], after["r"], after["a"]), (before["oh"], before["r"] + 60, before["a"] - 60))
        self.assertEqual(self.service.reservation_remaining("RES01"), 60)
        record("T02", f"OK; {pos_text(before)} -> {pos_text(after)}; RES01 = 60")

    def test_t03_repeat_creates_no_duplicate(self):
        first = self.service.reserve("RES01", REQUESTER, "P01", W, 60, "WO-2001")
        counts = self.counts()
        second = self.service.reserve("RES01", REQUESTER, "P01", W, 60, "WO-2001")
        journal("T03", second)
        self.assertTrue(second.replayed and not first.replayed)
        self.assertEqual((second.status, second.data), (first.status, first.data))
        self.assertEqual(self.counts(), counts)
        self.assertEqual(self.service.position("P01", W)["r"], 180)
        record("T03", f"{second.status}, повтор=да; число резервов, событий, движений и запросов не изменилось; R = 180")

    def test_t04_same_key_other_quantity_conflict(self):
        self.service.reserve("RES01", REQUESTER, "P01", W, 60, "WO-2001")
        before_inv, before_cnt = self.inventory_snapshot(), self.counts()
        res = self.service.reserve("RES01", REQUESTER, "P01", W, 70, "WO-2001")
        journal("T04", res)
        self.assertEqual(res.status, R.CONFLICT)
        self.assertEqual(self.inventory_snapshot(), before_inv)
        self.assertEqual(self.counts(), before_cnt)
        record("T04", f"{res.status}; остатки, резервы, движения и реестр запросов без изменений")

    def test_t05_insufficient_stock_changes_nothing(self):
        before_pos, before_inv = self.service.position("P01", W), self.inventory_snapshot()
        res = self.service.reserve("RES02", REQUESTER, "P01", W, 500, "WO-2002")
        journal("T05", res)
        self.assertEqual(res.status, R.INSUFFICIENT_STOCK)
        self.assertEqual(self.service.position("P01", W), before_pos)
        self.assertEqual(self.inventory_snapshot(), before_inv)
        self.assertIsNone(self.service.reservation_remaining("RES02"))
        row = self.conn.execute("SELECT status FROM processed_request WHERE request_key = 'RES02'").fetchone()
        self.assertEqual(row[0], R.INSUFFICIENT_STOCK)     # the refusal itself is registered, stock is not touched
        record("T05", f"{res.status}; {pos_text(before_pos)} без изменений; резерва RES02 нет")

    def test_t06_issue_reduces_oh_and_r_equally(self):
        self.service.reserve("RES01", REQUESTER, "P01", W, 60, "WO-2001")
        before = self.service.position("P01", W)
        res = self.service.issue("OUT01", STOREKEEPER, "RES01", 20)
        journal("T06", res)
        after = self.service.position("P01", W)
        self.assertTrue(res.ok)
        self.assertEqual((before["oh"] - after["oh"], before["r"] - after["r"], after["a"]), (20, 20, before["a"]))
        self.assertEqual(self.service.reservation_remaining("RES01"), 40)
        record("T06", f"OK; OH {before['oh']} -> {after['oh']}, R {before['r']} -> {after['r']}, "
                      f"A {before['a']} -> {after['a']}; RES01 = 40")

    def test_t07_release_keeps_oh(self):
        self.service.reserve("RES01", REQUESTER, "P01", W, 60, "WO-2001")
        self.service.issue("OUT01", STOREKEEPER, "RES01", 20)
        before = self.service.position("P01", W)
        res = self.service.release("CANCEL01", REQUESTER, "RES01")
        journal("T07", res)
        after = self.service.position("P01", W)
        self.assertTrue(res.ok)
        self.assertEqual(after["oh"], before["oh"])
        self.assertEqual((before["r"] - after["r"], after["a"] - before["a"]), (40, 40))
        self.assertEqual(self.service.reservation_remaining("RES01"), 0)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM movement WHERE document = 'CANCEL01'").fetchone()[0], 0)
        record("T07", f"OK; OH {before['oh']} -> {after['oh']}; R {before['r']} -> {after['r']}; "
                      f"A {before['a']} -> {after['a']}; движения не создано")


class Parallel(unittest.TestCase):
    def test_t08_three_parallel_reservations(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = parallel_reservation(tmp, hold=0.02)
        statuses = sorted(e["status"] for e in out["journal"])
        self.assertEqual(statuses, ["INSUFFICIENT_STOCK", "OK", "OK"])
        p = out["position"]
        reservations = out["reservations"]
        self.assertEqual(len(reservations), 2)
        self.assertTrue(all(r["initial_qty"] == 5 and r["remaining_qty"] == 5 and r["status"] == "ACTIVE"
                            for r in reservations))                       # two full reservations, none partial
        total = sum(r["remaining_qty"] for r in reservations)
        self.assertLessEqual(total, p["oh"] - p["b"])
        self.assertEqual(p["a"], p["oh"] - p["b"] - total)
        self.assertGreaterEqual(p["a"], 0)
        starts = [e["start"] for e in out["journal"]]
        self.assertLess(max(starts) - min(starts), 0.02)                  # started together (barrier)
        for e in sorted(out["journal"], key=lambda x: x["end"]):
            from .support import JOURNAL
            b, a = e["before"], e["after"]
            JOURNAL.append(f"T08  ключ={e['key']:<10} RESERVE  {e['status']:<19} до: A={b['a']:<3} после: A={a['a'] if a else b['a']}"
                           f"   старт +{e['start'] * 1000:.2f} мс, конец +{e['end'] * 1000:.1f} мс")
        record("T08", f"{', '.join(statuses)}; ΣR = {total}, OH − B = {p['oh'] - p['b']}, A = {p['a']}; "
                      f"разброс стартов {1000 * (max(starts) - min(starts)):.2f} мс")


class Planning(DbTestCase):
    def test_t09_indicators(self):
        rows = {r.code: r for r in replenishment_report(self.conn)}
        expected = {  # A, IP, d, ROP, EOQ, need
            "P01": (350, 580, 40, 260, 346.41, False), "P02": (70, 80, 20, 120, 244.95, True),
            "P03": (160, 330, 60, 450, 424.26, True), "P04": (160, 180, 30, 120, 282.84, False),
            "P05": (75, 140, 10, 105, 173.21, False), "P06": (160, 170, 50, 325, 387.30, True),
        }
        for code, (a, ip, d, rop, eoq_, need) in expected.items():
            r = rows[code]
            self.assertEqual((r.a, r.ip, r.d, r.rop, round(r.lot.eoq, 2), r.need), (a, ip, d, rop, eoq_, need), code)
        record("T09", "A, IP, d, ROP, EOQ всех шести позиций совпали; пополнение: " +
               ", ".join(c for c, r in rows.items() if r.need))

    def test_t10_lot_is_multiple_of_pack_and_cheaper(self):
        params = {r.code: r for r in replenishment_report(self.conn)}
        packs = {"P01": 50, "P02": 20, "P03": 100, "P04": 50, "P05": 25, "P06": 50}
        chosen = {}
        for code, r in params.items():
            lot = r.lot
            self.assertEqual(lot.q % packs[code], 0)
            self.assertLess(lot.lower, lot.eoq)
            self.assertGreater(lot.upper, lot.eoq)
            self.assertEqual(lot.q, lot.lower if lot.tc_lower <= lot.tc_upper else lot.upper)
            chosen[code] = lot.q
        self.assertEqual(chosen, {"P01": 350, "P02": 240, "P03": 400, "P04": 300, "P05": 175, "P06": 400})
        # EOQ exactly a multiple of the pack size: it is chosen itself and compared with the next multiple
        exact = choose_lot(Params("X", D=20000, S=100, H=100, L=1, SS=0, p=50, OO=0, BO=0))
        self.assertEqual((exact.eoq, exact.lower, exact.upper, exact.q), (200.0, 200, 250, 200))
        record("T10", "Q кратны упаковке и дают меньший TC из двух соседних: " +
               ", ".join(f"{c} {q}" for c, q in chosen.items()) + "; точное кратное EOQ = 200 выбрано само")

    def test_t11_report_does_not_change_the_database(self):
        before = self.dump()
        rows = replenishment_report(self.conn)
        self.service.stock_report(PURCHASER)
        self.assertTrue(any(r.need for r in rows))
        self.assertEqual(self.dump(), before)
        record("T11", f"рекомендации сформированы ({sum(r.need for r in rows)} позиции к пополнению); "
                      f"полный дамп базы ({len(before)} строк) до и после совпал")

    def test_t17_lead_time_scenario(self):
        base = {r.code: r for r in replenishment_report(self.conn)}
        new = {r.code: r for r in replenishment_report(self.conn, lead_time_shift={"P02": 2, "P03": 2})}
        self.assertEqual((new["P02"].rop, new["P03"].rop), (160, 570))
        self.assertTrue(new["P02"].need and new["P03"].need)
        for code in ("P01", "P04", "P05", "P06"):
            self.assertEqual(new[code].rop, base[code].rop)
        params = {r.code: r for r in replenishment_report(self.conn)}
        self.assertEqual(params["P02"].rop, 120)       # the base calculation is unchanged by the scenario
        record("T17", "P02: ROP 120 -> 160, P03: ROP 450 -> 570; IP 80 и 330, пополнение нужно; остальные позиции не изменились")


class Integrity(DbTestCase):
    def test_t12_sql_constraints(self):
        c = self.conn
        bad = [
            "UPDATE stock SET on_hand = -1 WHERE product_code = 'P01'",
            "INSERT INTO movement (product_code, warehouse_code, kind, qty, document, created_at) "
            "VALUES ('P01', 'W01', 'RECEIPT', 0, 'X1', 'now')",
            "INSERT INTO movement (product_code, warehouse_code, kind, qty, document, created_at) "
            "VALUES ('NOPE', 'W01', 'RECEIPT', 5, 'X2', 'now')",
            "INSERT INTO stock (product_code, warehouse_code) VALUES ('P01', 'W01')",
            "INSERT INTO reservation (code, product_code, warehouse_code, request_id, initial_qty, remaining_qty, status, "
            "created_at) VALUES ('BIG', 'P01', 'W01', 'WO', 351, 351, 'ACTIVE', 'now')",
            "UPDATE stock SET blocked_qty = 600 WHERE product_code = 'P01'",
            "UPDATE stock SET on_hand = 140 WHERE product_code = 'P01'",
        ]
        errors = []
        for sql in bad:
            with self.assertRaises(sqlite3.IntegrityError, msg=sql) as ctx:
                c.execute(sql)
            errors.append(str(ctx.exception).split(":")[0][:30])
        self.assertEqual(self.service.position("P01", W), {"oh": 500, "r": 120, "b": 30, "a": 350})
        record("T12", f"{len(bad)} из {len(bad)} нарушений отклонены SQL (CHECK, FOREIGN KEY, PRIMARY KEY, триггеры); P01 не изменён")

    def test_t13_consistency_of_journal_and_balance(self):
        p01_chain(self.service)
        c = self.conn
        self.assertEqual(c.execute("SELECT COUNT(*) FROM v_stock_check WHERE on_hand <> from_movements").fetchone()[0], 0)
        self.assertEqual(c.execute("SELECT COUNT(*) FROM v_reserve_check "
                                   "WHERE initial_qty <> remaining_qty + issued + released").fetchone()[0], 0)
        for product in ("P01", "P02", "P03", "P04", "P05", "P06"):
            r = c.execute("SELECT COALESCE(SUM(remaining_qty), 0) FROM reservation WHERE product_code = ? AND status = 'ACTIVE'",
                          (product,)).fetchone()[0]
            self.assertEqual(r, self.service.position(product, W)["r"])
        oh = c.execute("SELECT on_hand FROM stock WHERE product_code = 'P01'").fetchone()[0]
        moves = c.execute("SELECT SUM(CASE WHEN kind = 'ISSUE' THEN -qty ELSE qty END) FROM movement "
                          "WHERE product_code = 'P01'").fetchone()[0]
        self.assertEqual((oh, moves), (520, 520))
        record("T13", "P01: OH = 520 = 500 (OPENING) + 40 − 20; расхождений журнала 0; R всех позиций = сумме остатков резервов; "
                      "история резервов сходится")

    def test_t14_invalid_quantities_and_roles(self):
        before = self.counts()
        for qty in (0, -5, 2.5, "3", True, None):
            res = self.service.receive("BADQ", STOREKEEPER, "P01", W, qty)
            self.assertEqual(res.status, R.INVALID_QUANTITY, repr(qty))
        self.assertEqual(self.service.receive("ROLE1", REQUESTER, "P01", W, 5).status, R.FORBIDDEN)
        self.assertEqual(self.service.reserve("ROLE2", PURCHASER, "P01", W, 5, "WO").status, R.FORBIDDEN)
        self.assertEqual(self.service.issue("ROLE3", REQUESTER, "INIT-P01-1", 5).status, R.FORBIDDEN)
        self.assertEqual(self.counts(), before)                            # the keys are not consumed
        self.assertTrue(self.service.receive("BADQ", STOREKEEPER, "P01", W, 5).ok)   # the same key, now correct
        record("T14", "INVALID_QUANTITY для 0, −5, 2.5, '3', True, None; FORBIDDEN для трёх чужих ролей; "
                      "записей в базе не добавилось, ключ BADQ после исправления принят")

    def test_t15_busy_database_is_technical_error(self):
        blocker = connect(self.path)
        blocker.execute("BEGIN IMMEDIATE")                                 # another writer holds the lock
        impatient = InventoryService(self.path, busy_timeout=0.05, retries=1)
        try:
            with self.assertRaises(TechnicalError) as ctx:
                impatient.reserve("RES-BUSY", REQUESTER, "P01", W, 10, "WO-B")
        finally:
            blocker.execute("ROLLBACK")
            blocker.close()
        self.assertEqual(ctx.exception.code, "BUSY")
        self.assertEqual(self.service.position("P01", W)["r"], 120)
        self.assertIsNone(self.service.reservation_remaining("RES-BUSY"))
        res = impatient.reserve("RES-BUSY", REQUESTER, "P01", W, 10, "WO-B")  # the key was not consumed
        impatient.close()
        self.assertTrue(res.ok)
        record("T15", "TechnicalError BUSY (исключение, а не INSUFFICIENT_STOCK); данные не менялись; "
                      "после освобождения базы тот же ключ выполнен: OK")

    def test_t16_available_unchanged_after_issue(self):
        rows = p01_chain(self.service)
        a = {step: st["a"] for step, _, _, st in rows}
        oh = {step: st["oh"] for step, _, _, st in rows}
        r_ = {step: st["r"] for step, _, _, st in rows}
        self.assertEqual((a["4"], a["5"]), (330, 330))
        self.assertEqual((oh["4"] - oh["5"], r_["4"] - r_["5"]), (20, 20))
        self.assertEqual([rows[i][2].status for i in range(6)],
                         ["OK", "OK", "OK", "INSUFFICIENT_STOCK", "OK", "OK"])
        record("T16", f"после шага 4: OH {oh['4']}, R {r_['4']}, A {a['4']}; после шага 5: OH {oh['5']}, R {r_['5']}, A {a['5']}")

    def test_t18_initial_state(self):
        expected = {"P01": (500, 120, 30, 350), "P02": (100, 20, 10, 70), "P03": (240, 60, 20, 160),
                    "P04": (180, 20, 0, 160), "P05": (90, 10, 5, 75), "P06": (200, 40, 0, 160)}
        for code, vals in expected.items():
            p = self.service.position(code, W)
            self.assertEqual((p["oh"], p["r"], p["b"], p["a"]), vals, code)
            opening = self.conn.execute("SELECT SUM(qty) FROM movement WHERE product_code = ? AND kind = 'OPENING'",
                                        (code,)).fetchone()[0]
            self.assertEqual(opening, vals[0])
            created = self.conn.execute("SELECT SUM(e.qty) FROM reserve_event e JOIN reservation r ON r.code = e.reservation_code "
                                        "WHERE r.product_code = ? AND e.kind = 'CREATE'", (code,)).fetchone()[0]
            self.assertEqual(created, vals[1])
        record("T18", "OH, R, B, A шести позиций совпали с таблицей; OH = сумма OPENING, R = сумма начальных резервов")

    def test_t19_failure_before_commit_rolls_back(self):
        calls = {"n": 0}

        def clock():
            calls["n"] += 1
            if calls["n"] >= 2:      # the 1st call stamps the reservation, the 2nd one stamps the register entry
                raise RuntimeError("simulated failure before COMMIT")
            return "2026-11-16 10:00:00"

        failing = InventoryService(self.path, clock=clock)
        before = self.inventory_snapshot()
        with self.assertRaises(RuntimeError):
            failing.reserve("RES-FAIL", REQUESTER, "P01", W, 10, "WO-F")
        failing.close()
        self.assertEqual(self.inventory_snapshot(), before)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM processed_request WHERE request_key = 'RES-FAIL'").fetchone()[0], 0)
        record("T19", "RuntimeError после вставки резерва и события: ROLLBACK, резерва, события и записи в реестре нет")


if __name__ == "__main__":
    unittest.main()
