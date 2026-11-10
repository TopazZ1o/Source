"""Генератор МОДЕЛЬНОГО набора данных для задания 5 (СРМ №10, авиатехническая база).

НАЗНАЧЕНИЕ
    Реальных данных нет, поэтому спрос за 12 месяцев, цены и затраты искусственные
    (допущения перечислены в отчёте, раздел 5.1). Результат детерминирован: seed = 10.

ЗАПУСК (из папки task_10)
    python calc/gen_data.py
    -> data/items.csv           справочник позиций (24 шт.)
    -> data/demand_monthly.csv  спрос по месяцам (24 x 12)

ФОРМАТ
    CSV, UTF-8 с BOM (открывается в Excel), разделитель ';'.
ОГРАНИЧЕНИЯ
    Числа не отражают реальные цены и расход запчастей какой-либо авиатехнической базы.
"""
import csv
import random
from pathlib import Path

SEED = 10
HOLD_RATE = 0.25  # годовые затраты на хранение = 25 % стоимости единицы

MONTHS = ["янв", "фев", "мар", "апр", "май", "июн", "июл", "авг", "сен", "окт", "ноя", "дек"]

# Сезонные профили (нормируются в main так, чтобы среднее равнялось 1)
FLAT = [1.0] * 12
SUMMER_TRAFFIC = [0.80, 0.75, 0.90, 1.00, 1.10, 1.25, 1.35, 1.35, 1.10, 1.00, 0.80, 0.75]  # летний пик рейсов
WINTER_DEICE = [2.2, 2.0, 1.4, 0.3, 0.1, 0.05, 0.05, 0.05, 0.2, 0.8, 1.8, 2.4]  # противообледенительная жидкость
WINTER_HEAT = [1.3, 1.25, 1.1, 0.9, 0.8, 0.75, 0.75, 0.8, 0.9, 1.0, 1.2, 1.3]  # зимние работы (подогрев, уплотнения)

# pn, наименование, цена, средний спрос/мес, шум (доля), затраты на заказ, срок поставки (дн.), сезонность
ITEMS = [
    ("TIR-MLG", "Пневматик основной стойки шасси", 520000, 24, 0.25, 20000, 21, SUMMER_TRAFFIC),
    ("TIR-NLG", "Пневматик передней стойки шасси", 380000, 12, 0.30, 20000, 21, SUMMER_TRAFFIC),
    ("BRK-DSK", "Комплект тормозных дисков", 1200000, 6, 0.50, 30000, 30, SUMMER_TRAFFIC),
    ("FLT-HYD", "Фильтрующий элемент гидросистемы", 85000, 40, 0.12, 8000, 14, FLAT),
    ("FLT-FUEL", "Фильтр топливный", 65000, 30, 0.15, 8000, 14, FLAT),
    ("FLT-OIL", "Фильтр масляный двигателя", 48000, 35, 0.12, 8000, 14, FLAT),
    ("FLT-CAB", "Фильтр воздушный кабины", 22000, 60, 0.15, 5000, 10, FLAT),
    ("OIL-JET", "Масло турбинное, банка 1 кг", 14000, 240, 0.10, 6000, 10, SUMMER_TRAFFIC),
    ("HYD-FLD", "Гидрожидкость, 3,8 л", 95000, 45, 0.15, 7000, 14, FLAT),
    ("DEICE-IV", "Противообледенительная жидкость, 20 л", 28000, 150, 0.20, 5000, 7, WINTER_DEICE),
    ("SEAL-PS", "Герметик, туба 0,5 кг", 35000, 55, 0.30, 5000, 21, WINTER_HEAT),
    ("ORG-KIT", "Комплект уплотнительных колец", 18000, 120, 0.20, 4000, 10, FLAT),
    ("BLT-AN", "Болты стандартные, упаковка 100", 12000, 80, 0.20, 3500, 7, FLAT),
    ("NUT-LCK", "Самоконтрящиеся гайки, упаковка 100", 15000, 70, 0.20, 3500, 7, FLAT),
    ("WIRE-LK", "Контровочная проволока и шплинты, комплект", 6500, 90, 0.25, 3000, 7, FLAT),
    ("LGT-LDG", "Лампа посадочной фары", 45000, 18, 0.45, 6000, 21, FLAT),
    ("BAT-NICD", "Бортовой аккумулятор NiCd", 1400000, 3, 0.90, 25000, 45, WINTER_HEAT),
    ("GEN-STR", "Стартёр-генератор", 3800000, 1.5, 1.00, 40000, 60, FLAT),
    ("PMP-HYD", "Гидронасос", 6500000, 0.8, 1.20, 60000, 75, FLAT),
    ("PMP-FUEL", "Топливный насос-регулятор", 4200000, 1.0, 1.10, 50000, 60, FLAT),
    ("WHL-ASM", "Колесо шасси в сборе", 2100000, 4, 0.60, 30000, 45, SUMMER_TRAFFIC),
    ("SNS-PITOT", "Приёмник воздушного давления", 900000, 2, 1.00, 25000, 45, FLAT),
    ("WPR-BLD", "Щётка стеклоочистителя пилотской кабины", 24000, 25, 0.40, 4000, 21, FLAT),
    ("EXT-HAL", "Бортовой огнетушитель", 110000, 12, 0.50, 8000, 30, FLAT),
]


def main() -> None:
    rng = random.Random(SEED)
    out = Path(__file__).resolve().parent.parent / "data"
    out.mkdir(exist_ok=True)
    items_rows, demand_rows = [], []
    for pn, name, cost, base, noise, order_cost, lead, season in ITEMS:
        monthly = []
        for m in range(12):
            value = base * season[m] * (1 + noise * rng.gauss(0, 1))
            monthly.append(max(0, round(value)))
        initial = max(1, round(base * rng.uniform(0.5, 1.2)))
        items_rows.append([pn, name, cost, order_cost, round(cost * HOLD_RATE), lead, initial])
        demand_rows.append([pn] + monthly)
    with open(out / "items.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["pn", "name", "unit_cost_kzt", "order_cost_kzt", "holding_cost_kzt_per_unit_year",
                    "lead_time_days", "initial_stock"])
        w.writerows(items_rows)
    with open(out / "demand_monthly.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["pn"] + MONTHS)
        w.writerows(demand_rows)
    print(f"items: {len(items_rows)}, files in {out}")


if __name__ == "__main__":
    main()
