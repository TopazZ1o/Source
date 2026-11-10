"""Диаграммы темы 1 (анализ предметной области управления запасами): граница автоматизации и движение запаса.

Одно описание диаграммы даёт и PNG, и страницу draw.io (координаты общие). Библиотека – diagram_lib.py.

Запуск (из папки topic_1, Python 3.11 с Pillow; шрифты Arial из C:/Windows/Fonts):
    python tools/build_diagrams.py
Результат: assets/01_boundary.png, assets/02_flow.png, inventory_domain.drawio (две страницы).
"""

import pathlib
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(pathlib.Path(__file__).parent))

from diagram_lib import Canvas, drawio_file  # noqa: E402

OUT = pathlib.Path(__file__).resolve().parent.parent
BLUE, GREEN, GRAY, YELLOW, RED = "#dae8fc", "#d5e8d4", "#f5f5f5", "#fff2cc", "#f8cecc"


def d01_boundary() -> Canvas:
    c = Canvas("Граница автоматизации", 1100, 640)
    c.label(20, 8, 1060, 24, "Граница автоматизации: учёт запасов запчастей и материалов", size=15, bold=True)

    # граница системы
    c.rect(290, 50, 520, 560, "", dashed=True, stroke="#6c8ebf", sw=2)
    c.label(300, 54, 500, 38, "ГРАНИЦА СИСТЕМЫ\nмодуль учёта запасов (расширение ИС ТО и Р)", size=11, bold=True,
            font_color="#34527a")
    modules = [
        "Номенклатура, склады, места хранения",
        "Приёмка и входной контроль",
        "Партии и серийные номера, статусы запаса",
        "Резервирование под заявку и заказ-наряд",
        "Отпуск, расход, возврат неиспользованного",
        "Снятые детали, брак, списание",
        "Контроль срока годности и минимального остатка",
        "Инвентаризация",
        "Журнал операций и права доступа",
    ]
    mods = []
    for i, text in enumerate(modules):
        mods.append(c.rect(330, 105 + i * 54, 440, 42, text, fill=BLUE, rounded=6, size=12))

    # участники слева (в границах: пользователи системы)
    users = [("Кладовщик", 118), ("Техник-исполнитель", 198), ("Инженер-планировщик", 278),
             ("Руководитель / инспектор качества", 358), ("Специалист по запчастям", 438), ("Администратор", 518)]
    for name, y in users:
        s = c.rect(20, y, 200, 46, name, fill=GREEN, rounded=6, size=12)
        c.line([(220, y + 23), (290, y + 23)], end="open")
    c.label(20, 82, 200, 22, "Пользователи", size=12, bold=True)

    # внешнее окружение справа
    c.label(850, 58, 230, 22, "Внешнее окружение", size=12, bold=True)
    c.rect(850, 90, 230, 70, "Модуль заказ-нарядов и заявок ИС ТО и Р\n(существующая часть)", fill=YELLOW, rounded=6, size=12)
    c.line([(850, 125), (810, 125)], end="open", start="open")
    c.label(812, 100, 40, 20, "наряд", size=10, italic=True)
    c.rect(850, 200, 230, 56, "Поставщик запчастей и материалов", fill=GRAY, rounded=6, size=12)
    c.line([(850, 228), (810, 228)], end="open", start="open")
    c.label(812, 204, 40, 20, "поставка", size=10, italic=True)
    c.rect(850, 296, 230, 56, "Закупка (вне границ)\nдоговоры, оплата", fill=GRAY, rounded=6, size=12)
    c.line([(850, 324), (810, 324)], end="open", start="open", dashed=True)
    c.label(812, 300, 40, 20, "заявка", size=10, italic=True)
    c.rect(850, 392, 230, 56, "Бухгалтерский учёт (вне границ)\nстоимость, списание в учёте", fill=GRAY, rounded=6, size=12)
    c.line([(850, 420), (810, 420)], end="open", dashed=True)
    c.label(812, 396, 40, 20, "выгрузка", size=10, italic=True)
    c.rect(850, 488, 230, 56, "Система учёта ВС авиакомпании\nэксплуатация, наработка", fill=GRAY, rounded=6, size=12)
    c.line([(850, 516), (810, 516)], end="open")
    c.label(812, 492, 40, 20, "наработка", size=10, italic=True)

    c.note(850, 560, 230, 44, "Пунктир – обмен данными вне границ; сплошная линия – вход в систему.", size=10)
    return c.fit()


def d02_flow() -> Canvas:
    c = Canvas("Движение запаса", 1100, 520)
    c.label(20, 8, 1060, 24, "Движение запаса запчастей и материалов и места проблем", size=15, bold=True)

    c.label(20, 44, 400, 22, "Расход: от потребности до списания", size=12, bold=True, align="left")
    steps = ["Потребность\n(заявка, заказ-наряд)", "Проверка наличия", "Выдача со склада", "Установка, отметка\nв заказ-наряде",
             "Возврат неиспользованного", "Снятая деталь: годная\nили негодная"]
    xs = []
    for i, text in enumerate(steps):
        x = 20 + i * 175
        xs.append(c.rect(x, 80, 150, 64, text, fill=BLUE, rounded=6, size=12))
        if i:
            c.line([(x - 25, 112), (x, 112)], end="filled")
    marks = [(2, 1, "П1, П5"), (3, 2, "П3"), (4, 3, "П2, П3"), (5, 5, "П7")]
    for _, idx, text in marks:
        x = 20 + idx * 175 + 35
        c.ellipse(x, 160, 80, 30, text, fill=RED, size=11)
        c.line([(x + 40, 160), (x + 40, 144)], end="open")

    c.label(20, 215, 400, 22, "Пополнение: от остатка до склада", size=12, bold=True, align="left")
    steps2 = ["Контроль остатка\nи сроков", "Заявка на закупку", "Заказ поставщику\n(вне границ)", "Приёмка\nи входной контроль",
              "Размещение\nна складе", "Инвентаризация"]
    for i, text in enumerate(steps2):
        x = 20 + i * 175
        fill = GRAY if i in (1, 2) else BLUE
        c.rect(x, 250, 150, 64, text, fill=fill, rounded=6, size=12)
        if i:
            c.line([(x - 25, 282), (x, 282)], end="filled")
    marks2 = [(0, "П4, П6"), (3, "П3"), (5, "П1")]
    for idx, text in marks2:
        x = 20 + idx * 175 + 35
        c.ellipse(x, 330, 80, 30, text, fill=RED, size=11)
        c.line([(x + 40, 330), (x + 40, 314)], end="open")

    c.label(20, 400, 1060, 22, "Легенда", size=12, bold=True, align="left")
    c.rect(20, 430, 24, 18, "", fill=BLUE)
    c.label(50, 428, 260, 22, "операция в границах системы", size=11, align="left")
    c.rect(330, 430, 24, 18, "", fill=GRAY)
    c.label(360, 428, 260, 22, "операция вне границ системы", size=11, align="left")
    c.ellipse(650, 427, 50, 24, "П", fill=RED, size=11)
    c.label(710, 428, 370, 22, "проблема из раздела 5 отчёта (П1–П7)", size=11, align="left")
    return c.fit()


def main():
    (OUT / "assets").mkdir(exist_ok=True)
    pages = [("01_boundary", d01_boundary()), ("02_flow", d02_flow())]
    for name, canvas in pages:
        canvas.to_png(str(OUT / "assets" / f"{name}.png"))
        print("png", name, canvas.w, "x", canvas.h)
    (OUT / "inventory_domain.drawio").write_text(drawio_file([c for _, c in pages]), encoding="utf-8")


if __name__ == "__main__":
    main()
