# Прототип управления запасами склада W01 (практика 10)

Python 3.11.9, SQLite 3.45.1 (модуль `sqlite3`), только стандартная библиотека. Условие: `subjects/system-modeling/materials/task_practice_10.md`, отчёт: `../work.md`.

Запуск из этой папки:

```
python init_db.py                       # пересоздать data/inventory.db (схема schema.sql + начальное состояние)
python demo.py [--save ../results]      # начальное состояние и цепочка из шести операций над P01
python calc_report.py [--save ../results]   # A, IP, d, ROP, EOQ, выбор партии, сценарий L + 2 (база только читается)
python concurrency.py [--save ../results]   # TEST01: три параллельных подключения, затем 100 повторов
python run_tests.py --save ../results   # 19 автоматических проверок, таблица и журнал запросов
```

Начальный файл `data/inventory.db` не изменяется: `demo.py` работает с временной копией, проверки создают свои базы.

Пакет `inventory`: `service.py` (операции, транзакции, идемпотентность), `planning.py` (формулы, только чтение), `seed.py` (начальные данные через операции), `scenarios.py` (цепочка P01, параллельный запуск), `db.py`, `results.py`. Диаграммы: `../assets/inventory_model.drawio` и `../assets/*.png`, пересборка – `python ../tools/build_diagrams.py`. Отчёт: `python tools/make_appendix.py` в папке задания, затем `python tools/build_docx.py <work.md>` из корня репозитория.
