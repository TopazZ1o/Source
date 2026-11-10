"""Демонстрация прототипа: приход, резерв под заказ-наряд, отказ при нехватке, карантин, выдача, история.

Запуск (из папки prototype): python demo.py
База создаётся во временной папке и удаляется после показа.
"""
import os
import sys
import tempfile
from datetime import date

from mro_stock import InsufficientStock, StockService, init_db

sys.stdout.reconfigure(encoding="utf-8")


def show(svc, user, pn):
    a = svc.availability(user, pn)
    print(f"  остаток {a['on_hand']}, резерв {a['reserved']}, доступно {a['available']}, негодно {a['unusable']}")


with tempfile.TemporaryDirectory() as tmp:
    path = os.path.join(tmp, "stock.db")
    init_db(path)
    svc = StockService(path, today=lambda: date(2026, 11, 5))
    keeper = svc.add_user("Кладовщик", "storekeeper")
    plan1 = svc.add_user("Планировщик 1", "planner")
    plan2 = svc.add_user("Планировщик 2", "planner")
    boss = svc.add_user("Руководитель технической службы", "manager")

    print("1. Регистрация номенклатуры и приход 10 шт с сертификатом годности")
    svc.add_location(keeper, "A-01")
    svc.register_item(keeper, "FLT-HYD", "Фильтрующий элемент гидросистемы", "pcs", packs={"BOX": 10})
    svc.receive(keeper, "RCPT-0001", [{"pn": "FLT-HYD", "qty": 10, "batch_no": "L-2611", "cert_no": "F1-2611-07",
                                       "expiry": "2028-11-01", "location": "A-01"}])
    show(svc, plan1, "FLT-HYD")

    print("2. Планировщик 1 резервирует 8 шт под заказ-наряд WO-1001")
    res = svc.reserve(plan1, "REQ-001", "FLT-HYD", 8, "WO-1001")
    print(f"  резерв №{res['reservation_id']} {res['status']}")
    show(svc, plan1, "FLT-HYD")

    print("3. Планировщик 2 просит ещё 8 шт под WO-1002 – отказ")
    try:
        svc.reserve(plan2, "REQ-002", "FLT-HYD", 8, "WO-1002")
    except InsufficientStock as e:
        print(f"  отказ: {e.message}")

    print("4. Повтор запроса планировщика 1 с тем же ключом – тот же резерв, без дубля")
    again = svc.reserve(plan1, "REQ-001", "FLT-HYD", 8, "WO-1001")
    print(f"  резерв №{again['reservation_id']}, повтор: {again['duplicate']}")
    show(svc, plan1, "FLT-HYD")

    print("5. Приход партии без сертификата: уходит в карантин, не резервируется")
    svc.receive(keeper, "RCPT-0002", [{"pn": "FLT-HYD", "qty": 5, "batch_no": "L-2612", "location": "A-01"}])
    show(svc, plan1, "FLT-HYD")
    svc.certify_batch(boss, "FLT-HYD", "L-2612", "F1-2612-03")
    print("  руководитель снял карантин, указав сертификат F1-2612-03")
    show(svc, plan1, "FLT-HYD")

    print("6. Кладовщик выдаёт резерв по WO-1001")
    svc.issue(keeper, res["reservation_id"])
    show(svc, plan1, "FLT-HYD")

    print("7. История движений")
    for h in svc.history(plan1, "FLT-HYD"):
        print(f"  #{h['movement_id']} {h['kind']:<9} партия {h['batch_no']} {h['location']} "
              f"остаток {h['qty_delta']:+d} резерв {h['reserved_delta']:+d} {h['doc_ref']} ({h['user']})")
    print("Проверка согласованности:", svc.check_consistency() or "расхождений нет")
