Create Virtual environment
```
py -3.11 -m venv .venv
```

VE activate for Windows
```
.\.venv\Scripts\activate
```

ctrl+shift+p (select interpreter)

Install dependencies
```
pip install -r requirements.txt
```

# Домашние задания

Репозиторий для ведения домашних заданий по пяти дисциплинам. Исходные материалы (pdf, docx, pptx) конвертируются в Markdown, выполненные задания собираются в docx.

## Структура

```
tools/                              скрипты и настройки
  convert_to_md.py                  pdf/docx/pptx -> md (markitdown)
  build_docx.py                     work.md -> docx
  templates/work.md                 заготовка выполненной работы
subjects/
  system-modeling/                  Анализ проектирования и моделирование информационных систем
  research-methods/                 Методология и методы научных исследований
  management-psychology/            Психология управления
  higher-ed-pedagogy/               Педагогика высшей школы
  science-history-philosophy/       История и философия науки
    README.md                       сведения о предмете, список заданий и статусы
    lectures/raw, lectures/md       лекции: исходники и Markdown
    notes/raw, notes/md             конспекты: исходники и Markdown
    materials/                      литература и прочее
    assignments/NN-short-name/
      task/                         условие задания (исходник и md)
      work.md                       выполненная работа – источник истины
      assets/                       рисунки, диаграммы
      output/NN-short-name.docx     собирается из work.md
```

Имена папок и файлов – латиницей, содержимое – на русском.

## Рабочий процесс

1. Положить исходники в `lectures/raw`, `notes/raw` или `assignments/NN-name/task`.
2. Конвертировать в Markdown (файлы из папки `raw` попадают в соседнюю `md`):
   ```
   python tools/convert_to_md.py subjects/system-modeling/lectures/raw
   ```
3. Создать задание: папку `assignments/NN-short-name/` и в ней `work.md` на основе `tools/templates/work.md`.
4. Собрать docx:
   ```
   python tools/build_docx.py subjects/system-modeling/assignments/01-short-name/work.md
   python tools/build_docx.py --all
   ```

Файл docx в `output/` вручную не правится: все изменения вносятся в `work.md`.

## Оформление docx

A4, поля 1 см со всех сторон, Times New Roman 12 (в таблицах 10), выравнивание по ширине, абзацный отступ 1,25 см (в таблицах, заголовках и списках его нет), интервалы между абзацами убраны, междустрочный интервал 1. Титульного листа нет. Правила заданы в константах `tools/build_docx.py`.
