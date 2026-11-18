"""Build the 11-slide presentation "Credit technology of education in a university".

Source of the topic: materials/photo_2026-11-17_13-33-03.md (module 4, topic 12).
Usage: python build_pptx.py   (writes ../output/credit-technology.pptx)
"""

from pathlib import Path

from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LABEL_POSITION
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

NAVY = RGBColor(0x1F, 0x3A, 0x5F)
TEAL = RGBColor(0x2A, 0x9D, 0x8F)
RED = RGBColor(0xC0, 0x4B, 0x3C)
INK = RGBColor(0x22, 0x2B, 0x36)
MUTED = RGBColor(0x6B, 0x77, 0x85)
CARD = RGBColor(0xEE, 0xF3, 0xF8)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
FONT = "Calibri"

prs = Presentation()
prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
BLANK = prs.slide_layouts[6]


def text(slide, x, y, w, h, content, size=18, bold=False, color=INK,
         align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP):
    """Add a textbox; content is a str or a list of str (one paragraph each)."""
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    items = content if isinstance(content, list) else [content]
    for i, item in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.space_after = Pt(6)
        r = p.add_run()
        r.text = item
        r.font.size, r.font.bold, r.font.name = Pt(size), bold, FONT
        r.font.color.rgb = color
    return tb


def rect(slide, x, y, w, h, fill, shape=MSO_SHAPE.RECTANGLE):
    s = slide.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
    s.fill.solid()
    s.fill.fore_color.rgb = fill
    s.line.fill.background()
    return s


def card(slide, x, y, w, h, title, body, accent=TEAL, size=16):
    rect(slide, x, y, w, h, CARD)
    rect(slide, x, y, 0.08, h, accent)
    text(slide, x + 0.25, y + 0.12, w - 0.4, 0.5, title, 18, True, NAVY)
    text(slide, x + 0.25, y + 0.62, w - 0.4, h - 0.7, body, size)


def base(title, sources, n):
    s = prs.slides.add_slide(BLANK)
    rect(s, 0, 0, 13.333, 1.15, NAVY)
    text(s, 0.6, 0.12, 12.1, 0.9, title, 30, True, WHITE, anchor=MSO_ANCHOR.MIDDLE)
    if sources:
        text(s, 0.6, 6.95, 11.2, 0.4, "Источники: " + sources, 13, False, MUTED)
    text(s, 12.0, 6.95, 0.8, 0.4, str(n), 13, False, MUTED, PP_ALIGN.RIGHT)
    return s


# 1. Title ------------------------------------------------------------------
s = prs.slides.add_slide(BLANK)
rect(s, 0, 0, 13.333, 7.5, NAVY)
rect(s, 0.8, 3.55, 1.6, 0.07, TEAL)
text(s, 0.8, 1.6, 11.5, 1.9, "Кредитная технология обучения в вузе", 46, True, WHITE,
     anchor=MSO_ANCHOR.BOTTOM)
text(s, 0.8, 3.85, 11.5, 1.2,
     ["Модуль 4 – «Менеджмент высшей школы», тема № 12",
      "Дисциплина: Педагогика высшей школы"], 22, False, RGBColor(0xC9, 0xD6, 0xE4))
text(s, 0.8, 6.6, 11.5, 0.5,
     "Тема и вопросы взяты из тематического плана силлабуса [5]. Ссылки в квадратных скобках – на слайд 11.",
     14, False, RGBColor(0x9F, 0xB3, 0xC8))

# 2. Goals ------------------------------------------------------------------
s = base("Цель и вопросы для изучения", "[5] тематический план силлабуса, модуль 4, тема № 12", 2)
qs = [("1", "Понятие", "Изучить понятие «кредитная технология обучения»"),
      ("2", "Правила", "Правила организации кредитной технологии обучения"),
      ("3", "Особенности", "Особенности применения кредитной технологии в высшей школе"),
      ("4", "Анализ", "Преимущества и риски применения кредитной технологии в высшей школе")]
for i, (n, t, b) in enumerate(qs):
    x = 0.6 + (i % 2) * 6.2
    y = 1.6 + (i // 2) * 2.6
    rect(s, x, y, 5.9, 2.3, CARD)
    c = rect(s, x + 0.3, y + 0.3, 0.8, 0.8, TEAL, MSO_SHAPE.OVAL)
    c.text_frame.text = n
    c.text_frame.paragraphs[0].alignment = PP_ALIGN.CENTER
    r = c.text_frame.paragraphs[0].runs[0]
    r.font.size, r.font.bold, r.font.color.rgb, r.font.name = Pt(26), True, WHITE, FONT
    text(s, x + 1.3, y + 0.3, 4.4, 0.6, t, 22, True, NAVY)
    text(s, x + 1.3, y + 0.95, 4.4, 1.3, b, 17)

# 3. Concept ----------------------------------------------------------------
s = base("1. Понятие кредитной технологии обучения",
         "[1] п. 2, подп. 3; [3]; [2] разд. 1", 3)
card(s, 0.6, 1.5, 12.1, 1.55, "Академический кредит",
     "Унифицированная единица измерения объёма учебной (и научной) работы студента "
     "и преподавателя. В Казахстане 1 кредит = 30 академическим часам [1].")
card(s, 0.6, 3.25, 5.9, 3.45, "Суть технологии",
     ["Обучение строится на выборе студентом дисциплин и индивидуальной траектории.",
      "Акцент на самостоятельной работе и самообразовании [3]."], TEAL)
card(s, 6.8, 3.25, 5.9, 3.45, "Европейская основа",
     ["ECTS – система накопления и переноса кредитов, ориентированная на студента, "
      "прозрачность обучения и результаты обучения [2].",
      "В Казахстане введена при присоединении к Болонскому процессу [3]."], NAVY)

# 4. Credit arithmetic ------------------------------------------------------
s = base("Кредит в часах: казахстанская система и ECTS",
         "[1] п. 23–24; [2] разд. 1 (ECTS key features)", 4)
stats = [("30 ч", "1 кредит РК\n(1 акад. час = 50 мин) [1]"),
         ("25–30 ч", "1 кредит ECTS [2]"),
         ("60", "кредитов ECTS за полный\nучебный год [2]"),
         ("1500–1800 ч", "типичная нагрузка за\nучебный год [2]")]
for i, (big, small) in enumerate(stats):
    x = 0.6 + i * 3.08
    rect(s, x, 1.7, 2.9, 2.9, CARD)
    text(s, x, 2.0, 2.9, 1.0, big, 36, True, TEAL, PP_ALIGN.CENTER)
    text(s, x + 0.15, 3.2, 2.6, 1.3, small.split("\n"), 16, False, INK, PP_ALIGN.CENTER)
text(s, 0.6, 5.0, 12.1, 1.7,
     ["Соответствие: один казахстанский кредит (30 ч) приравнивается к 1 кредиту ECTS (25–30 ч) [1].",
      "Это типичная нагрузка: фактическое время освоения у отдельных студентов отличается [2]."],
     18)

# 5. ECTS principles --------------------------------------------------------
s = base("Принципы ECTS как основы кредитной технологии", "[2] разд. 1–2", 5)
items = [("Результаты обучения", "Кредиты привязаны к тому, что студент знает и умеет по итогам освоения."),
         ("Нагрузка", "Объём обучения оценивается по затратам времени: лекции, семинары, практика, самоподготовка."),
         ("Накопление", "Кредиты начисляются после достижения результатов и накапливаются для получения квалификации."),
         ("Перенос", "Кредиты признаются в другом вузе или стране – основа академической мобильности.")]
for i, (t, b) in enumerate(items):
    card(s, 0.6 + (i % 2) * 6.2, 1.5 + (i // 2) * 2.7, 5.9, 2.45, t, b,
         TEAL if i % 3 == 0 else NAVY)

# 6. Rules (1) --------------------------------------------------------------
s = base("2. Правила организации (1): траектория и сопровождение",
         "[1] п. 2, 4–8, 31–32, 37–38", 6)
rules = [("Индивидуальный учебный план", "Каждый год студент с эдвайзером формирует ИУП на основе образовательной программы и каталога элективных дисциплин [1]."),
         ("Эдвайзер", "Академический наставник: помогает выбрать траекторию и пройти программу [1]."),
         ("Элективные дисциплины", "В программе есть каталог элективных дисциплин, студент выбирает из него [1]."),
         ("Офис регистратора", "Записывает на дисциплины, организует промежуточную и итоговую аттестацию, следит за результатами [1].")]
for i, (t, b) in enumerate(rules):
    card(s, 0.6 + (i % 2) * 6.2, 1.5 + (i // 2) * 2.7, 5.9, 2.45, t, b)

# 7. Rules (2) --------------------------------------------------------------
s = base("2. Правила организации (2): период, контроль, оценка",
         "[1] п. 2 подп. 2, 28; п. 19, 28, 36", 7)
rules = [("Академический период", "Семестр или триместр (определяет вуз); завершается промежуточной аттестацией, итоговый контроль дисциплины – в пределах одного периода [1]."),
         ("Оценка", "100-балльная шкала с буквенной системой от A до D, неудовлетворительные оценки FX и F; при FX допускается пересдача итогового экзамена [1]."),
         ("GPA", "Средний балл, взвешенный по кредитам, за выбранный период [1].")]
for i, (t, b) in enumerate(rules):
    card(s, 0.6 + i * 4.15, 1.8, 3.95, 4.2, t, b, TEAL if i != 1 else NAVY, size=18)

# 8. Features in higher school ---------------------------------------------
s = base("3. Особенности применения в высшей школе",
         "[3]; [2] разд. 1–2; [4]", 8)
feats = [("Индивидуализация", "Реализуются индивидуальные образовательные потребности: свобода выбора дисциплин, спецкурсов и преподавателей [3]."),
         ("Роль СРС", "Растёт доля самостоятельной работы; вместо классических лекций – общие ориентиры по материалу [3]."),
         ("Мобильность", "Сопоставимость кредитов облегчает признание периодов обучения и переход между вузами [2], [3]."),
         ("Смена парадигмы", "Переход от преподаватель-центрированного обучения к студент-центрированному [2].")]
for i, (t, b) in enumerate(feats):
    card(s, 0.6 + (i % 2) * 6.2, 1.5 + (i // 2) * 2.7, 5.9, 2.45, t, b,
         NAVY if i in (1, 2) else TEAL)

# 9. Advantages + survey chart ---------------------------------------------
s = base("4. Преимущества: что показывают данные",
         "[3] опрос, г. Кызылорда, 2016, n = 1000; [2]; [4]", 9)
text(s, 0.6, 1.4, 6.0, 0.5, "Преимущества", 22, True, NAVY)
text(s, 0.6, 1.95, 5.9, 4.8,
     ["• Гибкость и выбор траектории [3]",
      "• Академическая мобильность и признание результатов обучения [2], [3]",
      "• Прозрачность обучения и оценивания [2]",
      "• Выше интерес к учёбе при выборе дисциплин и преподавателей; рост посещаемости (по оценке автора, без эмпирической проверки) [4]"],
     17)
cd = CategoryChartData()
cd.categories = ["Положительно", "Отрицательно", "Не определились"]
cd.add_series("Доля респондентов, %", (61.3, 26.2, 12.5))
gf = s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(6.9), Inches(1.95),
                        Inches(5.8), Inches(4.4), cd)
ch = gf.chart
ch.has_legend = False
ch.has_title = False
ch.value_axis.visible = False
ch.value_axis.has_major_gridlines = False
ch.value_axis.maximum_scale = 75
ch.category_axis.tick_labels.font.size = Pt(14)
pl = ch.plots[0]
pl.gap_width = 60
pl.has_data_labels = True
pl.data_labels.font.size = Pt(16)
pl.data_labels.font.bold = True
pl.data_labels.number_format = '0.0"%"'
pl.data_labels.number_format_is_linked = False
pl.data_labels.position = XL_LABEL_POSITION.OUTSIDE_END
for idx, col in enumerate((TEAL, RED, MUTED)):
    pt = pl.series[0].points[idx]
    pt.format.fill.solid()
    pt.format.fill.fore_color.rgb = col
text(s, 6.9, 1.4, 5.8, 0.5, "Отношение к кредитной технологии, % [3]", 18, True, NAVY)
text(s, 6.9, 6.4, 5.8, 0.5, "Опрос 1000 человек, г. Кызылорда, 2016 [3].", 13, False, MUTED)

# 10. Risks + conclusions ---------------------------------------------------
s = base("4. Риски и выводы", "[2] разд. 1; [3]; [4]", 10)
text(s, 0.6, 1.4, 6.0, 0.5, "Риски", 22, True, RED)
text(s, 0.6, 1.95, 5.9, 4.9,
     ["• Недостаточная самостоятельность студентов: 19,22% опрошенных недовольны – средний студент не обладает сознательностью, на которую рассчитывает реформа [3]",
      "• Непродуктивное использование часов СРС, провал на экзамене и платные пересдачи [4]",
      "• Нагрузка в кредитах – оценка типичная; реальные затраты времени у студентов различаются [2]",
      "• Правила применяются на практике не всегда корректно, возникает путаница у участников процесса [4]"],
     16)
rect(s, 6.9, 1.4, 5.8, 5.35, CARD)
rect(s, 6.9, 1.4, 5.8, 0.08, TEAL)
text(s, 7.2, 1.65, 5.3, 0.5, "Выводы", 22, True, NAVY)
text(s, 7.2, 2.25, 5.3, 4.4,
     ["1. Кредитная технология – способ измерения и организации обучения через кредиты, выбор траектории и самостоятельную работу [1], [2].",
      "2. Её преимущества (гибкость, мобильность, прозрачность) подтверждаются большинством позитивных оценок: 61,3% [3].",
      "3. Основной риск – неготовность студентов к самостоятельности и формальное применение правил [3], [4]. Условие успеха – эдвайзинг и продуманная организация СРС [1], [3]."],
     16)

# 11. Literature ------------------------------------------------------------
s = base("Список литературы", None, 11)
lit = [
    "[1] Об утверждении Правил организации учебного процесса по кредитной технологии обучения: приказ Министра образования и науки РК от 20.04.2011 № 152 (в ред. приказа Министра науки и высшего образования РК от 05.04.2023 № 145; зарегистрирован в Минюсте 07.04.2023 № 32256). – URL: https://zakon.uchet.kz/rus/docs/V2300032256",
    "[2] ECTS Users' Guide 2015. – Luxembourg: Publications Office of the European Union, 2015. – URL: https://education.ec.europa.eu/sites/default/files/document-library-docs/ects-users-guide_en.pdf",
    "[3] Фурсова В. В., Сыздыкова М. Кредитная система обучения (на примере Республики Казахстан). – URL: https://kpfu.ru/staff_files/F901004905/mahpal.pdf",
    "[4] Mirzayev M. Advantages of the Transformation to European Credit Transfer System in Uzbek Universities Turned Their Faces // Central Asian Research Journal for Interdisciplinary Studies. – 2022. – URL: https://cyberleninka.ru/article/n/advantages-of-the-transformation-to-european-credit-transfer-system-in-uzbek-universities-turned-their-faces",
    "[5] Силлабус «Педагогика высшей школы» на 2026–2027 уч. г., тематический план (модуль 4, тема № 12). – subjects/higher-ed-pedagogy/materials/",
]
text(s, 0.6, 1.4, 12.1, 5.5, lit, 15)

out = Path(__file__).resolve().parent.parent / "output"
out.mkdir(exist_ok=True)
prs.save(out / "credit-technology.pptx")
print("saved", out / "credit-technology.pptx")
