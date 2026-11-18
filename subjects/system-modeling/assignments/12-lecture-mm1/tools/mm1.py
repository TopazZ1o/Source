"""M/M/1: analytic formulas and discrete-event simulation check."""
import math
import random
import statistics
import sys

sys.stdout.reconfigure(encoding="utf-8")


def analytic(lam, mu):
    rho = lam / mu
    assert rho < 1
    lq = rho ** 2 / (1 - rho)
    return dict(rho=rho, Lq=lq, L=rho / (1 - rho), Wq=rho / (mu - lam),
                W=1 / (mu - lam), P0=1 - rho,
                Pw10=rho * math.exp(-(mu - lam) * 10 / 60))


def simulate(lam, mu, n_customers, seed, warmup=1000):
    rnd = random.Random(seed)
    t_arr = 0.0
    free_at = 0.0
    waits = []
    for i in range(n_customers):
        t_arr += rnd.expovariate(lam)          # ARRIVAL event
        start = max(t_arr, free_at)            # START: channel free or queue
        free_at = start + rnd.expovariate(mu)  # DEPARTURE time
        if i >= warmup:
            waits.append(start - t_arr)
    return statistics.fmean(waits), sum(w > 10 / 60 for w in waits) / len(waits)


if __name__ == "__main__":
    lam, mu = 6, 8
    a = analytic(lam, mu)
    print("base", {k: round(v, 4) for k, v in a.items()})
    print("lambda sens")
    for l in (4.8, 6, 6.6, 7.2, 7.6, 7.8):
        r = analytic(l, mu)
        print(l, *(round(r[k], 3) for k in ("rho", "Lq", "L", "Wq", "W", "Pw10")), round(r["Wq"] * 60, 1))
    print("mu sens")
    for m in (7, 8, 9, 10, 12):
        r = analytic(lam, m)
        print(m, *(round(r[k], 3) for k in ("rho", "Lq", "L", "Wq", "W", "Pw10")), round(r["Wq"] * 60, 1))
    runs = [simulate(lam, mu, 50000, s) for s in range(100)]
    wq = [r[0] for r in runs]; pw = [r[1] for r in runs]
    for name, x in (("Wq,h", wq), ("P(Wq>10min)", pw)):
        m = statistics.fmean(x); h = 1.984 * statistics.stdev(x) / 10
        print(name, round(m, 4), round(m - h, 4), round(m + h, 4))
    print("lam>=mu check:", 8, 8)
