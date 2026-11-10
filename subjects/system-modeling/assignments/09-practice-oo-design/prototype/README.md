# Прототип подсистемы заявок о неисправности ВС (практика 9)

Python 3.11, только стандартная библиотека. Условие: `subjects/system-modeling/materials/task_practice_9.md`, отчёт: `../work.md`.

Запуск из этой папки:

```
python demo.py                          # демонстрация на исходных данных (вывод: ../results/demo_output.txt)
python run_tests.py --save ../results   # 44 проверки, таблица TC01-TC12 (../results/test_results.md, .txt)
python -m unittest discover -s tests -t .
```

Структура пакета `mro_requests`: `domain.py` (правила одной заявки), `service.py` (сценарии), `sla.py` (политики срока), `repository.py` (контракты и хранилища), `config.py` (выбор политики по приоритету), `seed.py` (учебные данные через операции), `console.py` (вывод, без правил).

Диаграммы: `../assets/uml_model.drawio` (редактируемый файл, открывается в diagrams.net) и `../assets/*.png`; пересборка – `python ../tools/build_diagrams.py` (нужен Pillow). Отчёт: после правки `work.md` выполнить `python tools/make_appendix.py` в папке задания (подставляет код и результаты в приложения), затем `python tools/build_docx.py <work.md>` из корня репозитория.
