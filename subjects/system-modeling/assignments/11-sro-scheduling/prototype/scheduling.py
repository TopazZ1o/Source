"""Shift scheduling of six (seven) farm jobs over three crews (SRO 11).

Data model, scenarios S0-S2, exact optimiser (branch and bound), greedy
baseline and an independent plan checker. Standard library only.

Time grid: 30-minute slots, slot t covers [08:00 + 30*t, 08:00 + 30*(t+1)).
A job started in slot s with duration d slots occupies slots s .. s+d-1, i.e.
the half-open interval [start, end); the next job may start at ``end``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

SLOT_MIN = 30
SHIFT_START_MIN = 8 * 60
N_SLOTS = 16                      # 08:00 .. 16:00
RESOURCES = ("R1", "R2", "R3")


def hhmm(t: int) -> str:
    """Slot boundary -> 'HH:MM' (t = 0 is 08:00, t = 16 is 16:00)."""
    m = SHIFT_START_MIN + SLOT_MIN * t
    return f"{m // 60:02d}:{m % 60:02d}"


def to_slot(text: str) -> int:
    h, m = text.split(":")
    return (int(h) * 60 + int(m) - SHIFT_START_MIN) // SLOT_MIN


@dataclass(frozen=True)
class Job:
    code: str
    name: str
    win_from: int                 # earliest start (slot boundary)
    win_to: int                   # latest completion (slot boundary)
    dur: int                      # duration in slots
    mandatory: bool
    penalty: int                  # penalty for postponing, thousand tenge (0 for mandatory)
    cost: dict = field(default_factory=dict)   # resource -> cost; missing = incompatible


@dataclass
class Scenario:
    code: str
    title: str
    jobs: list
    unavailable: dict             # resource -> set of unavailable slots
    horizon: dict                 # resource -> (first slot, last slot + 1) of availability

    def free(self, r: str, t: int) -> bool:
        lo, hi = self.horizon[r]
        return lo <= t < hi and t not in self.unavailable.get(r, set())


def _job(code, name, w, dur_h, mandatory, penalty, **cost) -> Job:
    a, b = w.split("-")
    return Job(code, name, to_slot(a), to_slot(b), round(dur_h * 2), mandatory, penalty, cost)


def base_jobs() -> list:
    return [
        _job("J1", "Посев", "08:00-11:00", 2, True, 0, R1=8, R2=10),
        _job("J2", "Рыхление почвы", "08:00-12:00", 2, True, 0, R1=6, R2=18),
        _job("J3", "Внесение удобрений", "09:00-13:00", 2, True, 0, R1=9, R2=11),
        _job("J4", "Опрыскивание", "10:00-14:00", 1.5, False, 18, R2=8, R3=10),
        _job("J5", "Погрузка", "11:00-15:00", 2, False, 16, R2=9, R3=12),
        _job("J6", "Перевозка", "12:00-16:00", 2, True, 0, R3=12),
    ]


def slots(a: str, b: str) -> set:
    return set(range(to_slot(a), to_slot(b)))


def make_scenario(code: str, r3_off_all_shift: bool = False) -> Scenario:
    """S0, S1, S2 of the task. ``r3_off_all_shift`` is a test variant of S0."""
    if code not in ("S0", "S1", "S2"):
        raise ValueError(code)
    jobs = base_jobs()
    horizon = {"R1": (0, N_SLOTS), "R2": (0, to_slot("14:00")), "R3": (0, N_SLOTS)}
    unav = {"R1": slots("10:00", "10:30"), "R3": slots("11:00", "12:30")}
    title = "исходный вариант"
    if code in ("S1", "S2"):
        unav["R1"] = slots("10:00", "13:00")
        title = "поломка техники R1"
    if code == "S2":
        jobs.append(_job("J7", "Срочная погрузка", "12:00-14:00", 2, True, 0, R2=7))
        title = "поломка R1 и срочная заявка J7"
    if r3_off_all_shift:
        unav["R3"] = set(range(N_SLOTS))
        title += ", R3 недоступна всю смену"
    return Scenario(code, title, jobs, unav, horizon)


# ---------------------------------------------------------------- options
def options(sc: Scenario, job: Job) -> list:
    """All feasible (resource, start) pairs of a job: window, compatibility, calendar."""
    out = []
    for r in RESOURCES:
        if r not in job.cost:
            continue
        for s in range(job.win_from, job.win_to - job.dur + 1):
            if all(sc.free(r, t) for t in range(s, s + job.dur)):
                out.append((r, s))
    return out


# ---------------------------------------------------------------- plan
@dataclass
class Plan:
    scenario: Scenario
    assign: dict                  # job code -> (resource, start); postponed jobs are absent
    method: str = ""

    def run_cost(self) -> int:
        J = {j.code: j for j in self.scenario.jobs}
        return sum(J[c].cost[r] for c, (r, _) in self.assign.items())

    def penalty(self) -> int:
        return sum(j.penalty for j in self.scenario.jobs if j.code not in self.assign)

    def total(self) -> int:
        return self.run_cost() + self.penalty()

    def done(self) -> int:
        return len(self.assign)

    def rows(self) -> list:
        """One row per job: code, name, resource, start, end, cost, penalty, note."""
        out = []
        for j in self.scenario.jobs:
            if j.code in self.assign:
                r, s = self.assign[j.code]
                out.append((j.code, j.name, r, hhmm(s), hhmm(s + j.dur), j.cost[r], 0, ""))
            else:
                out.append((j.code, j.name, "–", "–", "–", 0, j.penalty,
                            postponed_reason(self.scenario, j, self.assign)))
        return out


def postponed_reason(sc: Scenario, job: Job, assign: dict) -> str:
    ops = options(sc, job)
    if not ops:
        return "нет допустимых вариантов: окно, совместимость и календари не оставляют места"
    jobs = {j.code: j for j in sc.jobs}
    free_ops = []
    for r, s in ops:
        clash = any(
            rr == r and a < s + job.dur and s < a + jobs[c].dur
            for c, (rr, a) in assign.items()
        )
        if not clash:
            free_ops.append((r, s))
    if not free_ops:
        return "все допустимые интервалы заняты обязательными и более выгодными заявками"
    return "перенос дешевле размещения: штраф меньше затрат или размещение вытесняет другую заявку"


# ---------------------------------------------------------------- checker
def check_plan(sc: Scenario, assign: dict) -> list:
    """Independent verification; returns violation messages (empty list = valid plan)."""
    errors = []
    J = {j.code: j for j in sc.jobs}
    busy: dict = {r: {} for r in RESOURCES}
    for code, (r, s) in assign.items():
        j = J.get(code)
        if j is None:
            errors.append(f"{code}: неизвестная заявка")
            continue
        if r not in j.cost:
            errors.append(f"{code}: бригада {r} не подходит")
            continue
        if s < j.win_from or s + j.dur > j.win_to:
            errors.append(f"{code}: выход за окно {hhmm(j.win_from)}-{hhmm(j.win_to)}")
        for t in range(s, s + j.dur):
            if not sc.free(r, t):
                errors.append(f"{code}: {r} недоступна в {hhmm(t)}")
            if t in busy[r]:
                errors.append(f"{code}: пересечение с {busy[r][t]} у {r} в {hhmm(t)}")
            busy[r][t] = code
    for j in sc.jobs:
        if j.mandatory and j.code not in assign:
            errors.append(f"{j.code}: обязательная заявка не выполнена")
    unique = []
    for e in errors:
        if e not in unique:
            unique.append(e)
    return unique


# ---------------------------------------------------------------- exact optimiser
def optimise(sc: Scenario) -> Optional[Plan]:
    """Minimum of (running cost + postponement penalties) by branch and bound.

    Tie-break among equal totals: smaller sum of start slots, then the
    lexicographically smaller list of (resource, start) in job-code order.
    Returns None when the mandatory jobs cannot be placed (model infeasible).
    """
    jobs = list(sc.jobs)
    opts = [options(sc, j) for j in jobs]
    if any(j.mandatory and not o for j, o in zip(jobs, opts)):
        return None
    floor = []                    # cheapest possible contribution of each job
    for j, o in zip(jobs, opts):
        c = min((j.cost[r] for r, _ in o), default=10 ** 9)
        floor.append(c if j.mandatory else min(c, j.penalty))
    tail = [sum(floor[i:]) for i in range(len(jobs) + 1)]

    best = {"key": None, "assign": None}
    busy = {r: 0 for r in RESOURCES}         # bit mask of occupied slots

    def rec(i, cost, chosen):
        if best["key"] is not None and cost + tail[i] > best["key"][0]:
            return
        if i == len(jobs):
            starts = sum(c[1] for c in chosen if c)
            key = (cost, starts, tuple(c or ("~", 99) for c in chosen))
            if best["key"] is None or key < best["key"]:
                best["key"], best["assign"] = key, list(chosen)
            return
        j = jobs[i]
        for r, s in opts[i]:
            m = ((1 << j.dur) - 1) << s
            if busy[r] & m:
                continue
            busy[r] |= m
            chosen.append((r, s))
            rec(i + 1, cost + j.cost[r], chosen)
            chosen.pop()
            busy[r] &= ~m
        if not j.mandatory:
            chosen.append(None)
            rec(i + 1, cost + j.penalty, chosen)
            chosen.pop()

    rec(0, 0, [])
    if best["assign"] is None:
        return None
    assign = {j.code: c for j, c in zip(jobs, best["assign"]) if c}
    return Plan(sc, assign, "оптимизация")


def count_optimal(sc: Scenario) -> int:
    """Number of distinct plans with the optimal total, by plain enumeration without
    cost bounding (a cross-check of the branch and bound and a measure of ambiguity)."""
    plan = optimise(sc)
    if plan is None:
        return 0
    target = plan.total()
    jobs = list(sc.jobs)
    opts = [options(sc, j) for j in jobs]
    busy = {r: 0 for r in RESOURCES}
    n = 0

    def rec(i, cost):
        nonlocal n
        if i == len(jobs):
            n += cost == target
            return
        j = jobs[i]
        for r, s in opts[i]:
            m = ((1 << j.dur) - 1) << s
            if busy[r] & m:
                continue
            busy[r] |= m
            rec(i + 1, cost + j.cost[r])
            busy[r] &= ~m
        if not j.mandatory:
            rec(i + 1, cost + j.penalty)

    rec(0, 0)
    return n


def enumerate_min(sc: Scenario) -> Optional[int]:
    """Minimum total by exhaustive enumeration (no pruning by cost); None if infeasible."""
    jobs = list(sc.jobs)
    opts = [options(sc, j) for j in jobs]
    busy = {r: 0 for r in RESOURCES}
    best = [None]

    def rec(i, cost):
        if i == len(jobs):
            if best[0] is None or cost < best[0]:
                best[0] = cost
            return
        j = jobs[i]
        for r, s in opts[i]:
            m = ((1 << j.dur) - 1) << s
            if busy[r] & m:
                continue
            busy[r] |= m
            rec(i + 1, cost + j.cost[r])
            busy[r] &= ~m
        if not j.mandatory:
            rec(i + 1, cost + j.penalty)

    rec(0, 0)
    return best[0]


# ---------------------------------------------------------------- greedy baseline
def greedy(sc: Scenario, log: Optional[list] = None) -> Plan:
    """Baseline rule of the task: mandatory jobs first, then by deadline (then code);
    the cheapest compatible crew that has a free interval, at its earliest start;
    ties: earlier start, then smaller crew code. No place -> postponed."""
    order = sorted(sc.jobs, key=lambda j: (not j.mandatory, j.win_to, j.code))
    assign: dict = {}
    busy = {r: set() for r in RESOURCES}
    for j in order:
        cand = []
        for r, s in options(sc, j):
            if not any(t in busy[r] for t in range(s, s + j.dur)):
                cand.append((j.cost[r], s, r))
        if cand:
            c, s, r = min(cand)
            assign[j.code] = (r, s)
            busy[r].update(range(s, s + j.dur))
            if log is not None:
                log.append((j.code, r, hhmm(s), hhmm(s + j.dur), c, ""))
        elif log is not None:
            log.append((j.code, "–", "–", "–", 0,
                        "не размещена (обязательная)" if j.mandatory else f"перенос, штраф {j.penalty}"))
    return Plan(sc, assign, "жадный план")


# ---------------------------------------------------------------- re-validation
def revalidate(plan: Plan, new_scenario: Scenario) -> list:
    """Check an approved/draft plan against a changed calendar or request list.
    Same rules as ``check_plan``: an empty list means the plan is still valid."""
    return check_plan(new_scenario, plan.assign)
