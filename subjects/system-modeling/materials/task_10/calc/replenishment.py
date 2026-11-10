"""Расчёты задания 5 (СРМ №10): ABC, XYZ, EOQ, точка заказа, страховой запас, сравнение политик.

НАЗНАЧЕНИЕ
    Читает модельные данные (data/items.csv, data/demand_monthly.csv) и выполняет:
    1) ABC-анализ по годовому объёму продаж в тенге (A до 80 %, B до 95 %, C остальное);
    2) XYZ-анализ по коэффициенту вариации месячного спроса (X <= 0,25; Y <= 0,50; Z > 0,50);
    3) EOQ = sqrt(2*D*S/H) для всех позиций;
    4) страховой запас SS = z*sigma_сутки*sqrt(L) и точку заказа ROP = d*L + SS (z = 1,645, уровень 95 %);
    5) имитацию 365 суток для двух политик при ОДИНАКОВЫХ начальных остатках и ОДНОЙ последовательности спроса:
       - непрерывный контроль (s, Q): заказ Q = EOQ, когда позиция запаса <= ROP;
       - периодический контроль (R, S): раз в R суток заказ до уровня S = d*(R+L) + z*sigma*sqrt(R+L).

ДОПУЩЕНИЯ СИМУЛЯЦИИ
    - Дефицит НЕ теряется: неудовлетворённый спрос ждёт поставки (backorder) и закрывается первым.
    - Срок поставки постоянный; поставка приходит в начале суток. Начальных заказов в пути нет.
    - Суточный спрос получен случайным распределением месячных итогов по дням (сумма за месяц сохраняется).
    - Затраты: заказы * S + средний остаток * H. Штраф за дефицит в затраты не входит, он отдельный показатель.

ЗАПУСК (из папки task_10, нужны numpy и matplotlib)
    python calc/replenishment.py
    -> results/*.csv, results/report.txt, assets/chart_*.png
"""
import csv
import math
import random
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
Z = 1.645  # уровень обслуживания 95 %
REVIEW_DAYS = 30  # период контроля R основного варианта
DAYS_IN_MONTH = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
SEED = 100
REPLICATIONS = 30
SLOW_D = 60  # порог годового спроса (ед.): медленные позиции в смешанной политике ведутся по (R, S)
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9})


def load():
    items = {}
    with open(ROOT / "data/items.csv", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f, delimiter=";"):
            items[r["pn"]] = dict(
                pn=r["pn"], name=r["name"], cost=float(r["unit_cost_kzt"]), S=float(r["order_cost_kzt"]),
                H=float(r["holding_cost_kzt_per_unit_year"]), L=int(r["lead_time_days"]),
                init=int(r["initial_stock"]))
    with open(ROOT / "data/demand_monthly.csv", encoding="utf-8-sig") as f:
        for r in csv.reader(f, delimiter=";"):
            if r[0] == "pn":
                continue
            items[r[0]]["monthly"] = [int(x) for x in r[1:]]
    return list(items.values())


def analyse(items):
    for it in items:
        m = np.array(it["monthly"], dtype=float)
        it["D"] = m.sum()
        it["mean_m"] = m.mean()
        it["std_m"] = m.std(ddof=1)
        it["cv"] = it["std_m"] / it["mean_m"]
        it["value"] = it["D"] * it["cost"]
        it["xyz"] = "X" if it["cv"] <= 0.25 else ("Y" if it["cv"] <= 0.5 else "Z")
    total = sum(i["value"] for i in items)
    cum = 0.0
    for it in sorted(items, key=lambda i: -i["value"]):
        prev = cum
        cum += it["value"]
        it["share"] = it["value"] / total
        it["cum_share"] = cum / total
        # позиция относится к A, если её начало лежит внутри первых 80 %
        it["abc"] = "A" if prev < 0.8 * total else ("B" if prev < 0.95 * total else "C")
    for it in items:
        it["eoq"] = math.sqrt(2 * it["D"] * it["S"] / it["H"])
        it["Q"] = max(1, math.ceil(it["eoq"]))
        it["d"] = it["D"] / 365
        it["sigma_d"] = it["std_m"] / math.sqrt(365 / 12)
        it["ss"] = math.ceil(Z * it["sigma_d"] * math.sqrt(it["L"]))
        it["rop"] = math.ceil(it["d"] * it["L"] + it["ss"])
        it["tc_eoq"] = it["D"] / it["Q"] * it["S"] + it["Q"] / 2 * it["H"]


def daily_demand(it, rng):
    """Распределяет месячный спрос по дням случайно; сумма за месяц сохраняется."""
    out = []
    for qty, days in zip(it["monthly"], DAYS_IN_MONTH):
        arr = [0] * days
        for _ in range(qty):
            arr[rng.randrange(days)] += 1
        out.extend(arr)
    return out


def simulate(it, demand, policy, R=REVIEW_DAYS, keep_path=False):
    """policy: 'sQ' (непрерывный) или 'RS' (периодический). Возвращает показатели за 365 суток."""
    L, init = it["L"], it["init"]
    on_hand, backlog, pipeline = init, 0, {}
    orders = 0
    sum_stock = shortage_units = backlog_days = 0
    served_now = 0
    path = []
    s, Q = it["rop"], it["Q"]
    sigma_cover = it["sigma_d"] * math.sqrt(R + L)
    S_level = math.ceil(it["d"] * (R + L) + Z * sigma_cover)
    for t, dem in enumerate(demand):
        on_hand += pipeline.pop(t, 0)
        if backlog and on_hand:
            take = min(on_hand, backlog)
            on_hand -= take
            backlog -= take
        now = min(on_hand, dem)
        served_now += now
        on_hand -= now
        miss = dem - now
        backlog += miss
        shortage_units += miss
        sum_stock += on_hand
        backlog_days += backlog
        position = on_hand - backlog + sum(pipeline.values())
        qty = 0
        if policy == "sQ":
            if position <= s:
                qty = Q * math.ceil((s + 1 - position) / Q)
        elif (t + 1) % R == 0 and position < S_level:
            qty = S_level - position
        if qty:
            orders += 1
            pipeline[t + 1 + L] = pipeline.get(t + 1 + L, 0) + qty
        if keep_path:
            path.append(on_hand - backlog)
    D = sum(demand)
    return dict(
        avg_stock=sum_stock / 365, shortage=shortage_units, backlog_days=backlog_days, orders=orders,
        order_cost=orders * it["S"], hold_cost=sum_stock / 365 * it["H"],
        fill=(served_now / D if D else 1.0), path=path, S_level=S_level)


def aggregate(items, results):
    """Суммарные показатели по всем позициям; запас в тенге для сопоставимости."""
    agg = dict(stock_kzt=0.0, shortage=0, backlog_days=0, orders=0, order_cost=0.0, hold_cost=0.0)
    served = demand_total = 0.0
    for it, r, dem in results:
        agg["stock_kzt"] += r["avg_stock"] * it["cost"]
        agg["shortage"] += r["shortage"]
        agg["backlog_days"] += r["backlog_days"]
        agg["orders"] += r["orders"]
        agg["order_cost"] += r["order_cost"]
        agg["hold_cost"] += r["hold_cost"]
        served += r["fill"] * dem
        demand_total += dem
    agg["total_cost"] = agg["order_cost"] + agg["hold_cost"]
    agg["fill"] = served / demand_total
    return agg


def write_csv(path, header, rows):
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(header)
        w.writerows(rows)


def main():
    (ROOT / "results").mkdir(exist_ok=True)
    (ROOT / "assets").mkdir(exist_ok=True)
    items = load()
    analyse(items)
    lines = []
    out = lines.append

    # ---------- ABC / XYZ ----------
    by_value = sorted(items, key=lambda i: -i["value"])
    out("ABC-XYZ (по убыванию годовых продаж)")
    out("№ | pn | продажи, тыс. тг | доля % | накоп. % | ABC | среднее/мес | σ/мес | CV | XYZ")
    for n, it in enumerate(by_value, 1):
        out(f"{n} | {it['pn']} | {it['value']/1000:,.0f} | {it['share']*100:.1f} | {it['cum_share']*100:.1f} | "
            f"{it['abc']} | {it['mean_m']:.1f} | {it['std_m']:.1f} | {it['cv']:.2f} | {it['xyz']}")
    write_csv(ROOT / "results/abc_xyz.csv",
              ["pn", "name", "annual_demand", "annual_sales_kzt", "share", "cum_share", "abc", "mean_month",
               "std_month", "cv", "xyz"],
              [[i["pn"], i["name"], int(i["D"]), round(i["value"]), round(i["share"], 4), round(i["cum_share"], 4),
                i["abc"], round(i["mean_m"], 2), round(i["std_m"], 2), round(i["cv"], 3), i["xyz"]]
               for i in by_value])
    out("")
    out("Матрица ABC x XYZ (число позиций / доля продаж %)")
    total = sum(i["value"] for i in items)
    for a in "ABC":
        row = []
        for x in "XYZ":
            sel = [i for i in items if i["abc"] == a and i["xyz"] == x]
            row.append(f"{a}{x}: {len(sel)} / {sum(i['value'] for i in sel)/total*100:.1f}")
        out(" | ".join(row))
    for a in "ABC":
        sel = [i for i in items if i["abc"] == a]
        out(f"Группа {a}: {len(sel)} позиций, {sum(i['value'] for i in sel)/total*100:.1f} % продаж")

    # ---------- EOQ, SS, ROP ----------
    out("")
    out("EOQ / SS / ROP")
    out("pn | D | S | H | EOQ | Q | заказов/год | TC(EOQ) тг | σ_сут | L | SS | ROP | нач.остаток")
    for it in by_value:
        out(f"{it['pn']} | {it['D']:.0f} | {it['S']:.0f} | {it['H']:.0f} | {it['eoq']:.1f} | {it['Q']} | "
            f"{it['D']/it['Q']:.1f} | {it['tc_eoq']:,.0f} | {it['sigma_d']:.2f} | {it['L']} | {it['ss']} | "
            f"{it['rop']} | {it['init']}")
    write_csv(ROOT / "results/policy_params.csv",
              ["pn", "abc", "xyz", "D", "S", "H", "eoq", "Q", "orders_per_year", "tc_eoq", "sigma_day", "lead_days",
               "safety_stock", "rop", "initial_stock"],
              [[i["pn"], i["abc"], i["xyz"], int(i["D"]), int(i["S"]), int(i["H"]), round(i["eoq"], 2), i["Q"],
                round(i["D"] / i["Q"], 2), round(i["tc_eoq"]), round(i["sigma_d"], 3), i["L"], i["ss"], i["rop"],
                i["init"]] for i in by_value])

    # ---------- имитация, основная последовательность ----------
    rng = random.Random(SEED)
    series = {i["pn"]: daily_demand(i, rng) for i in items}
    per_item, res_sq, res_rs = [], [], []
    for it in by_value:
        dem = series[it["pn"]]
        a = simulate(it, dem, "sQ")
        b = simulate(it, dem, "RS")
        res_sq.append((it, a, sum(dem)))
        res_rs.append((it, b, sum(dem)))
        per_item.append([it["pn"], it["abc"], it["xyz"], sum(dem), it["rop"], it["Q"], b["S_level"],
                         round(a["avg_stock"], 1), a["shortage"], a["orders"], round(a["fill"], 3),
                         round(b["avg_stock"], 1), b["shortage"], b["orders"], round(b["fill"], 3)])
    write_csv(ROOT / "results/simulation_items.csv",
              ["pn", "abc", "xyz", "demand", "s", "Q", "S_level", "sQ_avg_stock", "sQ_shortage", "sQ_orders",
               "sQ_fill", "RS_avg_stock", "RS_shortage", "RS_orders", "RS_fill"], per_item)
    A, B = aggregate(items, res_sq), aggregate(items, res_rs)
    out("")
    out(f"Сравнение политик, одна последовательность спроса (seed {SEED}), R = {REVIEW_DAYS} сут., z = {Z}")
    for name, g in (("(s,Q) непрерывный", A), ("(R,S) периодический", B)):
        out(f"{name}: средний запас {g['stock_kzt']/1e6:.2f} млн тг; дефицит {g['shortage']} ед. "
            f"({g['backlog_days']} ед.-сут. ожидания); заказов {g['orders']}; затраты на заказ "
            f"{g['order_cost']/1e3:,.0f} тыс.; на хранение {g['hold_cost']/1e3:,.0f} тыс.; "
            f"всего {g['total_cost']/1e3:,.0f} тыс.; доля сразу {g['fill']*100:.2f} %")
    out("")
    out("По группам ABC (одна последовательность)")
    group_rows = []
    for grp in "ABC":
        ga = aggregate(items, [r for r in res_sq if r[0]["abc"] == grp])
        gb = aggregate(items, [r for r in res_rs if r[0]["abc"] == grp])
        n = sum(1 for r in res_sq if r[0]["abc"] == grp)
        out(f"{grp} ({n}): (s,Q) запас {ga['stock_kzt']/1e6:.2f} млн, деф. {ga['shortage']}, зак. {ga['orders']}, "
            f"затраты {ga['total_cost']/1e3:,.0f} тыс., сразу {ga['fill']*100:.2f} % || (R,S) запас "
            f"{gb['stock_kzt']/1e6:.2f} млн, деф. {gb['shortage']}, зак. {gb['orders']}, "
            f"затраты {gb['total_cost']/1e3:,.0f} тыс., сразу {gb['fill']*100:.2f} %")
        group_rows.append([grp, n, round(ga["stock_kzt"]), ga["shortage"], ga["orders"], round(ga["total_cost"]),
                           round(ga["fill"], 4), round(gb["stock_kzt"]), gb["shortage"], gb["orders"],
                           round(gb["total_cost"]), round(gb["fill"], 4)])
    write_csv(ROOT / "results/simulation_by_abc.csv",
              ["group", "items", "sQ_stock_kzt", "sQ_shortage", "sQ_orders", "sQ_total_cost", "sQ_fill",
               "RS_stock_kzt", "RS_shortage", "RS_orders", "RS_total_cost", "RS_fill"], group_rows)

    # ---------- повторения (30 других разбивок по дням) ----------
    out("")
    out(f"Повторения: {REPLICATIONS} разбивок спроса по дням (в каждой обе политики видят один и тот же ряд)")
    rep_rows = []
    rep_a, rep_b, rep_m = [], [], []
    for k in range(REPLICATIONS):
        rr = random.Random(1000 + k)
        sa, sb = [], []
        for it in by_value:
            dem = daily_demand(it, rr)
            sa.append((it, simulate(it, dem, "sQ"), sum(dem)))
            sb.append((it, simulate(it, dem, "RS"), sum(dem)))
        ga, gb = aggregate(items, sa), aggregate(items, sb)
        rep_a.append(ga)
        rep_b.append(gb)
        rep_m.append(aggregate(items, [x if x[0]["D"] >= SLOW_D else y for x, y in zip(sa, sb)]))
        rep_rows.append([k + 1, round(ga["stock_kzt"]), ga["shortage"], ga["orders"], round(ga["total_cost"]),
                         round(ga["fill"], 4), round(gb["stock_kzt"]), gb["shortage"], gb["orders"],
                         round(gb["total_cost"]), round(gb["fill"], 4)])
    write_csv(ROOT / "results/simulation_replications.csv",
              ["rep", "sQ_stock_kzt", "sQ_shortage", "sQ_orders", "sQ_total_cost", "sQ_fill", "RS_stock_kzt",
               "RS_shortage", "RS_orders", "RS_total_cost", "RS_fill"], rep_rows)
    for key, label in (("stock_kzt", "средний запас, млн тг"), ("shortage", "дефицит, ед."),
                       ("orders", "заказов"), ("total_cost", "затраты, тыс. тг"), ("fill", "доля сразу, %")):
        k = {"stock_kzt": 1e-6, "total_cost": 1e-3, "fill": 100}.get(key, 1)
        va = np.array([g[key] * k for g in rep_a])
        vb = np.array([g[key] * k for g in rep_b])
        out(f"{label}: (s,Q) {va.mean():.2f} ± {va.std(ddof=1):.2f}; (R,S) {vb.mean():.2f} ± {vb.std(ddof=1):.2f}")
    wins = sum(1 for a, b in zip(rep_a, rep_b) if a["total_cost"] < b["total_cost"])
    out(f"(s,Q) дешевле в {wins} из {REPLICATIONS} повторений")
    vm = np.array([g["total_cost"] / 1e3 for g in rep_m])
    out(f"Смешанная по спросу (D < {SLOW_D} ед./год – (R,S), иначе (s,Q)): затраты {vm.mean():.0f} ± {vm.std(ddof=1):.0f} тыс. тг; "
        f"дефицит {np.mean([g['shortage'] for g in rep_m]):.1f}; доля сразу {np.mean([g['fill'] for g in rep_m])*100:.2f} %; "
        f"дешевле (s,Q) в {sum(1 for m, a in zip(rep_m, rep_a) if m['total_cost'] < a['total_cost'])} из {REPLICATIONS}")
    pen = [(b["total_cost"] - a["total_cost"]) / (b["shortage"] - a["shortage"]) for a, b in zip(rep_a, rep_b)]
    out(f"Безубыточный штраф за единицу дефицита (при котором (s,Q) и (R,S) равны по затратам): "
        f"{np.mean(pen)*-1:.0f} ± {np.std(pen, ddof=1):.0f} тг")

    # ---------- чувствительность к R ----------
    out("")
    out("Чувствительность (R,S) к периоду контроля R (основная последовательность)")
    sens = []
    for R in (7, 14, 30, 60):
        rs = [(it, simulate(it, series[it["pn"]], "RS", R=R), sum(series[it["pn"]])) for it in by_value]
        g = aggregate(items, rs)
        out(f"R={R}: запас {g['stock_kzt']/1e6:.2f} млн; деф. {g['shortage']}; заказов {g['orders']}; "
            f"затраты {g['total_cost']/1e3:,.0f} тыс.; сразу {g['fill']*100:.2f} %")
        sens.append([R, round(g["stock_kzt"]), g["shortage"], g["orders"], round(g["total_cost"]),
                     round(g["fill"], 4)])
    write_csv(ROOT / "results/sensitivity_R.csv",
              ["R_days", "stock_kzt", "shortage", "orders", "total_cost", "fill"], sens)

    # ---------- смешанная политика по ABC ----------
    mixed = [r for r in res_sq if r[0]["abc"] == "A"] + [r for r in res_rs if r[0]["abc"] != "A"]
    g = aggregate(items, mixed)
    out("")
    mixed2 = [a if a[0]["D"] >= SLOW_D else b for a, b in zip(res_sq, res_rs)]
    g2 = aggregate(items, mixed2)
    out(f"Смешанная по спросу: D < {SLOW_D} ед./год – (R,S), иначе (s,Q): запас {g2['stock_kzt']/1e6:.2f} млн; "
        f"деф. {g2['shortage']} ({g2['backlog_days']} ед.-сут.); заказов {g2['orders']}; затраты на заказ {g2['order_cost']/1e3:,.0f} тыс.; "
        f"на хранение {g2['hold_cost']/1e3:,.0f} тыс.; всего {g2['total_cost']/1e3:,.0f} тыс.; "
        f"сразу {g2['fill']*100:.2f} %; позиций с (R,S): {sum(1 for a in mixed2 if a[0]['D'] < SLOW_D)}")
    out(f"Смешанная: A – (s,Q), B и C – (R,S): запас {g['stock_kzt']/1e6:.2f} млн; деф. {g['shortage']}; "
        f"заказов {g['orders']}; затраты {g['total_cost']/1e3:,.0f} тыс.; сразу {g['fill']*100:.2f} %")

    (ROOT / "results/report.txt").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

    # ---------- графики ----------
    fig, ax = plt.subplots(figsize=(7.2, 3.6))
    ax.bar(range(1, 25), [i["share"] * 100 for i in by_value], color="#7fa8d6")
    ax2 = ax.twinx()
    ax2.plot(range(1, 25), [i["cum_share"] * 100 for i in by_value], color="#c0392b", marker="o", ms=3)
    ax2.axhline(80, ls="--", c="gray", lw=0.8)
    ax2.axhline(95, ls="--", c="gray", lw=0.8)
    ax.set_xticks(range(1, 25))
    ax.set_xticklabels([i["pn"] for i in by_value], rotation=90, fontsize=7)
    ax.set_ylabel("Доля продаж, %")
    ax2.set_ylabel("Накопленная доля, %")
    ax2.set_ylim(0, 105)
    plt.tight_layout()
    plt.savefig(ROOT / "assets/chart_abc.png", dpi=160)
    plt.close()

    fig, axs = plt.subplots(1, 3, figsize=(7.4, 2.8))
    for ax, pn in zip(axs, ("OIL-JET", "FLT-HYD", "TIR-MLG")):
        it = next(i for i in items if i["pn"] == pn)
        q = np.linspace(max(1, it["Q"] * 0.2), it["Q"] * 3, 200)
        ax.plot(q, it["D"] / q * it["S"] / 1e3, label="заказ")
        ax.plot(q, q / 2 * it["H"] / 1e3, label="хранение")
        ax.plot(q, (it["D"] / q * it["S"] + q / 2 * it["H"]) / 1e3, c="k", label="сумма")
        ax.axvline(it["eoq"], ls="--", c="r", lw=0.8)
        ax.set_title(f"{pn}: EOQ={it['eoq']:.0f}", fontsize=8)
        ax.set_xlabel("Q, ед.")
    axs[0].set_ylabel("Затраты, тыс. тг/год")
    axs[0].legend(fontsize=7)
    plt.tight_layout()
    plt.savefig(ROOT / "assets/chart_eoq.png", dpi=160)
    plt.close()

    it = next(i for i in items if i["pn"] == "TIR-MLG")
    pa = simulate(it, series["TIR-MLG"], "sQ", keep_path=True)["path"]
    pb = simulate(it, series["TIR-MLG"], "RS", keep_path=True)["path"]
    fig, ax = plt.subplots(figsize=(7.2, 3.2))
    ax.plot(pa, label="(s,Q) непрерывный", lw=1)
    ax.plot(pb, label=f"(R,S) периодический, R={REVIEW_DAYS}", lw=1)
    ax.axhline(it["rop"], ls="--", c="gray", lw=0.8)
    ax.axhline(0, c="k", lw=0.6)
    ax.set_xlabel("Сутки")
    ax.set_ylabel("Остаток минус невыполненный спрос, ед.")
    ax.set_title("Пневматик основной стойки (TIR-MLG), пунктир – точка заказа", fontsize=9)
    ax.legend(fontsize=8)
    plt.tight_layout()
    plt.savefig(ROOT / "assets/chart_policy_path.png", dpi=160)
    plt.close()

    fig, axs = plt.subplots(1, 4, figsize=(7.4, 2.6))
    metrics = [("Средний запас, млн тг", A["stock_kzt"] / 1e6, B["stock_kzt"] / 1e6),
               ("Заказов в год", A["orders"], B["orders"]),
               ("Дефицит, ед.", A["shortage"], B["shortage"]),
               ("Затраты, тыс. тг", A["total_cost"] / 1e3, B["total_cost"] / 1e3)]
    for ax, (ttl, va, vb) in zip(axs, metrics):
        ax.bar(["(s,Q)", "(R,S)"], [va, vb], color=["#7fa8d6", "#e6a45c"])
        ax.set_title(ttl, fontsize=8)
        ax.tick_params(labelsize=8)
    plt.tight_layout()
    plt.savefig(ROOT / "assets/chart_policy_compare.png", dpi=160)
    plt.close()


if __name__ == "__main__":
    main()
