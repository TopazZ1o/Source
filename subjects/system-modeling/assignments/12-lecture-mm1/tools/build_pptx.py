"""Build a 7-slide, 5-minute defence presentation for the M/M/1 work.

Numbers come from mm1.py (same folder), so slides and work.md stay consistent.
Usage: python tools/build_pptx.py  (writes ../output/mm1-presentation.pptx)
"""
import sys
from pathlib import Path

from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

sys.path.insert(0, str(Path(__file__).parent))
from mm1 import analytic  # noqa: E402

NAVY = RGBColor(0x1F, 0x3A, 0x5F)
ACC = RGBColor(0xE0, 0x7A, 0x2F)
GREEN = RGBColor(0x2A, 0x9D, 0x8F)
RED = RGBColor(0xC0, 0x39, 0x2B)
INK = RGBColor(0x22, 0x2B, 0x36)
MUTED = RGBColor(0x6B, 0x77, 0x85)
CARD = RGBColor(0xEE, 0xF2, 0xF7)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
FONT = "Calibri"
LAM, MU = 6, 8
B = analytic(LAM, MU)

prs = Presentation()
prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
BLANK = prs.slide_layouts[6]


def text(s, x, y, w, h, content, size=20, bold=False, color=INK,
         align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP):
    tb = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    for i, item in enumerate(content if isinstance(content, list) else [content]):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.space_after = Pt(8)
        r = p.add_run()
        r.text = item
        r.font.size, r.font.bold, r.font.name = Pt(size), bold, FONT
        r.font.color.rgb = color
    return tb


def rect(s, x, y, w, h, fill, shape=MSO_SHAPE.RECTANGLE):
    r = s.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
    r.fill.solid()
    r.fill.fore_color.rgb = fill
    r.line.fill.background()
    return r


def slide(title, n, notes):
    s = prs.slides.add_slide(BLANK)
    rect(s, 0, 0, 13.333, 1.1, NAVY)
    text(s, 0.6, 0.1, 12.1, 0.9, title, 30, True, WHITE, anchor=MSO_ANCHOR.MIDDLE)
    text(s, 12.0, 6.95, 0.8, 0.4, str(n), 13, False, MUTED, PP_ALIGN.RIGHT)
    s.notes_slide.notes_text_frame.text = notes
    return s


def kpi(s, x, y, w, value, label, color=NAVY):
    rect(s, x, y, w, 1.7, CARD)
    rect(s, x, y, w, 0.07, color)
    text(s, x, y + 0.25, w, 0.8, value, 34, True, color, PP_ALIGN.CENTER)
    text(s, x + 0.1, y + 1.05, w - 0.2, 0.6, label, 15, False, MUTED, PP_ALIGN.CENTER)


def callout(s, y, h, lines, color, size=20, bold=True):
    rect(s, 0.6, y, 12.1, h, CARD)
    rect(s, 0.6, y, 0.08, h, color)
    text(s, 0.9, y + 0.12, 11.6, h - 0.2, lines, size, bold, NAVY)


# 1. Title -------------------------------------------------------------------
s = prs.slides.add_slide(BLANK)
rect(s, 0, 0, 13.333, 7.5, NAVY)
rect(s, 0.8, 3.55, 1.6, 0.07, ACC)
text(s, 0.8, 1.3, 11.8, 2.2,
     "Моделирование и анализ одноканальной системы массового обслуживания M/M/1",
     40, True, WHITE, anchor=MSO_ANCHOR.BOTTOM)
text(s, 0.8, 3.85, 11.5, 1.6,
     ["Лекция 12. Анализ, моделирование и проектирование информационных систем",
      "Выполнил: Маханов Тимур"], 20, False, RGBColor(0xC8, 0xD6, 0xE8))
s.notes_slide.notes_text_frame.text = (
    "(0:15) Тема работы: моделирование и анализ одноканальной СМО M/M/1. "
    "Покажу, как по двум числам – потоку заявок и скорости обслуживания – "
    "предсказать очередь и время ожидания.")

# 2. Task --------------------------------------------------------------------
s = slide("Задача и исходные данные", 2,
          "(0:40) Служба техподдержки, один диспетчер. Заявки приходят случайно, в среднем шесть в час, "
          "диспетчер обрабатывает восемь в час. M/M/1 значит: пуассоновский поток, экспоненциальное время "
          "обслуживания, один канал; очередь неограниченная, порядок FIFO. Требование – ожидание не более десяти минут.")
rect(s, 0.6, 1.5, 6.0, 5.2, CARD)
text(s, 0.85, 1.65, 5.5, 0.5, "Система", 22, True, NAVY)
text(s, 0.85, 2.3, 5.5, 4.2,
     ["Служба техподдержки с одним диспетчером.",
      "Заявки приходят случайно и ждут в очереди, если диспетчер занят.",
      "Порядок обслуживания – FIFO.",
      "Норматив (SLA): ожидание не более 10 минут."], 20)
rect(s, 6.9, 1.5, 5.8, 5.2, CARD)
text(s, 7.15, 1.65, 5.3, 0.5, "Исходные данные", 22, True, NAVY)
kpi(s, 7.15, 2.35, 2.5, "6", "заявок/час: поток λ", ACC)
kpi(s, 9.9, 2.35, 2.5, "8", "заявок/час: обслуживание μ", GREEN)
text(s, 7.15, 4.3, 5.3, 2.3,
     ["Запись по Кендаллу: M/M/1/∞/∞/FIFO.",
      "M – пуассоновский поток и экспоненциальное обслуживание; 1 – один канал."], 17)

# 3. Model -------------------------------------------------------------------
s = slide("Модель и формулы", 3,
          "(0:45) Главное условие – лямбда меньше мю, то есть загрузка ро меньше единицы. Иначе очередь растёт "
          "бесконечно. У нас ро равно 0,75, условие выполнено. Дальше формулы: загрузка, средняя очередь, "
          "число заявок в системе, время ожидания и время в системе. Закон Литтла связывает число заявок и время "
          "и служит для проверки расчёта.")
callout(s, 1.5, 1.3,
        ["Условие устойчивости: λ < μ, то есть ρ = λ/μ < 1.",
         f"У нас ρ = {LAM}/{MU} = {B['rho']:.2f} < 1: система устойчива, резерв мощности 25 %."], RED)
formulas = [("ρ = λ / μ", "загрузка канала"),
            ("Lq = ρ² / (1 − ρ)", "средняя очередь"),
            ("L = ρ / (1 − ρ)", "заявок в системе"),
            ("Wq = ρ / (μ − λ)", "среднее ожидание"),
            ("W = 1 / (μ − λ)", "время в системе"),
            ("L = λW,  Lq = λWq", "закон Литтла (проверка)")]
for i, (f, d) in enumerate(formulas):
    x, y = 0.6 + (i % 3) * 4.1, 3.1 + (i // 3) * 1.9
    rect(s, x, y, 3.9, 1.7, CARD)
    text(s, x, y + 0.2, 3.9, 0.7, f, 26, True, NAVY, PP_ALIGN.CENTER)
    text(s, x, y + 1.0, 3.9, 0.5, d, 16, False, MUTED, PP_ALIGN.CENTER)

# 4. Results -----------------------------------------------------------------
s = slide("Результаты расчёта", 4,
          "(0:50) Диспетчер занят 75 процентов времени. Очередь в среднем 2,25 заявки, в системе три. "
          "Заявка ждёт 22,5 минуты, всего в системе 30. Проверка Литтла сходится: 6 умножить на 0,5 – три, "
          "6 умножить на 0,375 – 2,25. Главный вывод: вероятность ждать дольше десяти минут – 54 процента, "
          "норматив не выполняется, хотя загрузка вроде бы умеренная.")
kpi(s, 0.6, 1.5, 3.9, f"{B['rho']:.2f}", "загрузка ρ (простой 25 %)", NAVY)
kpi(s, 4.7, 1.5, 3.9, f"{B['Lq']:.2f}", "заявки в очереди Lq", NAVY)
kpi(s, 8.8, 1.5, 3.9, f"{B['L']:.2f}", "заявки в системе L", NAVY)
kpi(s, 0.6, 3.4, 3.9, f"{B['Wq']*60:.1f} мин", "среднее ожидание Wq", ACC)
kpi(s, 4.7, 3.4, 3.9, f"{B['W']*60:.0f} мин", "время в системе W", ACC)
kpi(s, 8.8, 3.4, 3.9, f"{B['Pw10']*100:.0f} %", "ждут дольше 10 минут", RED)
callout(s, 5.3, 1.4,
        ["Вывод: норматив SLA не выполняется – среднее ожидание 22,5 мин при норме 10 мин.",
         "Проверка Литтла: 6 · 0,5 = 3,00 = L;  6 · 0,375 = 2,25 = Lq."], RED, 19, False)

# 5. Sensitivity chart -------------------------------------------------------
s = slide("Чувствительность: ожидание растёт нелинейно", 5,
          "(1:00) Меняем поток заявок при тех же восьми в час. Плюс 20 процентов – ожидание вырастает втрое, "
          "до 67 минут; плюс 30 процентов – в тринадцать раз. Чем ближе загрузка к единице, тем сильнее "
          "реакция. Справа: чтобы уложиться в норму по среднему ожиданию, нужно десять заявок в час, "
          "то есть ускорить работу на 25 процентов.")
lams = [4.8, 6.0, 6.6, 7.2, 7.6, 7.8]
cd = CategoryChartData()
cd.categories = [f"λ={l:g}, ρ={l/MU:.2f}" for l in lams]
cd.add_series("Среднее ожидание Wq, мин", [round(analytic(l, MU)["Wq"] * 60, 1) for l in lams])
gf = s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(0.6), Inches(1.4),
                        Inches(7.4), Inches(5.4), cd)
ch = gf.chart
ch.has_legend = False
ch.has_title = True
ch.chart_title.text_frame.text = "Среднее ожидание Wq, мин (μ = 8)"
ch.chart_title.text_frame.paragraphs[0].runs[0].font.size = Pt(16)
pl = ch.plots[0]
pl.gap_width = 60
pl.has_data_labels = True
pl.data_labels.font.size = Pt(14)
pl.data_labels.font.bold = True
ser = pl.series[0]
ser.format.fill.solid()
ser.format.fill.fore_color.rgb = ACC
ser.points[1].format.fill.solid()
ser.points[1].format.fill.fore_color.rgb = NAVY
ch.category_axis.tick_labels.font.size = Pt(11)
ch.value_axis.tick_labels.font.size = Pt(12)
ch.value_axis.has_major_gridlines = False
rect(s, 8.3, 1.5, 4.4, 5.2, CARD)
text(s, 8.5, 1.6, 4.0, 0.5, "Что видно", 21, True, NAVY)
text(s, 8.5, 2.2, 4.0, 4.4,
     ["Синий столбец – исходный режим.",
      "+20 % потока: ожидание ×3 (67,5 мин).",
      "+30 % потока: ожидание ×13 (292,5 мин).",
      "При ρ → 1 очередь растёт неограниченно.",
      "Чтобы Wq ≤ 10 мин, нужно μ ≥ 10 заявок/час (+25 % к скорости)."], 17)

# 6. Simulation --------------------------------------------------------------
s = slide("Проверка имитацией", 6,
          "(0:50) Чтобы убедиться, что формулы верны, я написал дискретно-событийную имитацию на Python: время "
          "прыгает от события к событию – поступление, начало обслуживания, завершение. Сто независимых "
          "прогонов по пятьдесят тысяч заявок. Аналитическое ожидание 0,3750 часа лежит внутри доверительного "
          "интервала имитации, расхождение около одной десятой процента. Модель и расчёт согласуются.")
text(s, 0.6, 1.4, 12.1, 0.6,
     "Дискретно-событийная модель: ARRIVAL → START → DEPARTURE; 100 прогонов × 50 000 заявок, 95 % доверительные интервалы",
     17, False, MUTED)
tbl = s.shapes.add_table(3, 4, Inches(0.6), Inches(2.2), Inches(12.1), Inches(2.3)).table
rows = [("Показатель", "Аналитика", "Имитация (среднее)", "95 % интервал"),
        ("Среднее ожидание Wq, ч", "0,3750", "0,3755", "0,3723 – 0,3786"),
        ("P(Wq > 10 мин)", "0,5374", "0,5365", "0,5349 – 0,5381")]
for r, row in enumerate(rows):
    for c, v in enumerate(row):
        cell = tbl.cell(r, c)
        cell.text = v
        p = cell.text_frame.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        p.runs[0].font.size, p.runs[0].font.name = Pt(20), FONT
        p.runs[0].font.bold = r == 0
        cell.vertical_anchor = MSO_ANCHOR.MIDDLE
        cell.fill.solid()
        cell.fill.fore_color.rgb = NAVY if r == 0 else CARD
        p.runs[0].font.color.rgb = WHITE if r == 0 else INK
callout(s, 5.0, 1.5,
        ["Аналитические значения лежат внутри доверительных интервалов имитации.",
         "Расхождение среднего ожидания – около 0,1 %: формулы и модель согласуются."], GREEN)

# 7. Conclusions -------------------------------------------------------------
s = slide("Выводы", 7,
          "(0:50) Итог. Система устойчива, но не укладывается в норматив: заявка ждёт 22,5 минуты. "
          "Ожидание растёт нелинейно, поэтому судить по средней загрузке 75 процентов нельзя. Чтобы выполнить "
          "норму, нужно ускорить обслуживание до десяти заявок в час. Для гарантии SLA лучше перейти к "
          "модели M/M/c с несколькими диспетчерами. Имитация подтвердила расчёты. Спасибо за внимание.")
items = [("1", "Система M/M/1 устойчива: ρ = 0,75 < 1, но заявка ждёт 22,5 мин, и 54 % ждут дольше 10 минут."),
         ("2", "Ожидание растёт нелинейно: +20 % потока – ожидание ×3; при ρ → 1 очередь неограниченна."),
         ("3", "Для нормы по среднему ожиданию нужно μ ≥ 10 заявок/час (+25 % к скорости)."),
         ("4", "Для гарантии SLA нужен переход к M/M/c (несколько диспетчеров, формула Эрланга C)."),
         ("5", "Имитация на 100 прогонах подтвердила расчёт (расхождение 0,1 %).")]
for i, (n, t) in enumerate(items):
    y = 1.4 + i * 1.08
    rect(s, 0.6, y, 12.1, 0.95, CARD)
    c = rect(s, 0.8, y + 0.15, 0.65, 0.65, ACC, MSO_SHAPE.OVAL)
    c.text_frame.text = n
    pr = c.text_frame.paragraphs[0]
    pr.alignment = PP_ALIGN.CENTER
    pr.runs[0].font.size, pr.runs[0].font.bold = Pt(20), True
    pr.runs[0].font.color.rgb, pr.runs[0].font.name = WHITE, FONT
    text(s, 1.7, y + 0.08, 10.8, 0.85, t, 19, anchor=MSO_ANCHOR.MIDDLE)

out = Path(__file__).resolve().parent.parent / "output" / "mm1-presentation.pptx"
out.parent.mkdir(exist_ok=True)
prs.save(out)
print("OK:", out)
