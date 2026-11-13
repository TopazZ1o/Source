"""Resource allocation model of practice 11: one-shift assignment (tasks 2-3) and timetable (task 4).

Pure functions, no I/O. Times are minutes from 00:00 of the planned day, the time step is 30 minutes.
Costs and penalties are in thousand tenge.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from typing import Optional

STEP = 30            # time step and preparation length, minutes
PREP = 30            # preparation before the next work on the same machine, minutes

JOBS = ["J1", "J2", "J3", "J4"]
MACHINES = ["R1", "R2", "R3", "R4"]
JOB_NAMES = {"J1": "Поверхностная обработка почвы", "J2": "Глубокоерыхление", "J3": "Боронование",
             "J4": "Перевозка груза"}

# Table 1: cost of the job on the machine; a missing pair is not allowed
COST = {
    "J1": {"R1": 5, "R2": 8},
    "J2": {"R1": 6, "R2": 24, "R3": 11},
    "J3": {"R2": 9, "R3": 7, "R4": 10},
    "J4": {"R3": 8, "R4": 4},
}
# Table 2: penalty for postponing a job
PENALTY = {"J1": 25, "J2": 12, "J3": 14, "J4": 30}

# Table 4: earliest start, deadline, duration (minutes)


def hm(text: str) -> int:
    h, m = text.split(":")
    return int(h) * 60 + int(m)


def hhmm(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


TIME = {
    "J1": (hm("09:00"), hm("12:30"), 120),
    "J2": (hm("10:00"), hm("14:00"), 150),
    "J3": (hm("11:30"), hm("16:00"), 120),
    "J4": (hm("10:00"), hm("13:00"), 90),
}


# ----------------------------------------------------------------------------- tasks 2 and 3: one shift
@dataclass
class ShiftPlan:
    assign: dict            # job -> machine (only for executed jobs)
    postponed: tuple        # jobs postponed (y = 1)
    cost: int               # C
    penalty: int            # P

    @property
    def total(self) -> int:     # Z = C + P
        return self.cost + self.penalty

    @property
    def coverage(self) -> float:
        return len(self.assign) / len(JOBS)


def greedy(cost=COST, order=JOBS, available=MACHINES) -> ShiftPlan:
    """Sequential choice: jobs in the given order, each takes the cheapest free eligible machine
    (ties - the smaller machine code). All jobs are mandatory; a job without a machine stays unassigned."""
    used, assign = set(), {}
    for j in order:
        options = sorted((c, r) for r, c in cost[j].items() if r in available and r not in used)
        if options:
            c, r = options[0]
            assign[j] = r
            used.add(r)
    return ShiftPlan(assign, tuple(j for j in order if j not in assign),
                     sum(cost[j][r] for j, r in assign.items()), 0)


def enumerate_plans(available=MACHINES, mandatory=frozenset(JOBS), max_postponed=0,
                    penalty=PENALTY, cost=COST) -> list[ShiftPlan]:
    """All feasible plans: every job gets an eligible available machine or is postponed
    (not mandatory, at most max_postponed postponed); a machine takes at most one job."""
    plans = []
    options = [[None] + [r for r in cost[j] if r in available] for j in JOBS]
    for combo in itertools.product(*options):
        chosen = [r for r in combo if r is not None]
        if len(set(chosen)) != len(chosen):
            continue
        postponed = tuple(j for j, r in zip(JOBS, combo) if r is None)
        if len(postponed) > max_postponed or any(j in mandatory for j in postponed):
            continue
        assign = {j: r for j, r in zip(JOBS, combo) if r is not None}
        plans.append(ShiftPlan(assign, postponed, sum(cost[j][r] for j, r in assign.items()),
                               sum(penalty[j] for j in postponed)))
    return plans


def best_plan(plans: list[ShiftPlan]) -> Optional[ShiftPlan]:
    """Minimum of Z = C + P; ties - the plan with the lexicographically smallest assignment."""
    if not plans:
        return None
    return min(plans, key=lambda p: (p.total, sorted(p.assign.items())))


def explain_infeasible(available, mandatory=frozenset(JOBS), cost=COST) -> list[str]:
    """Why no plan exists: a job without a machine, or fewer machines than mandatory jobs."""
    reasons = []
    for j in sorted(mandatory):
        eligible = [r for r in cost[j] if r in available]
        if not eligible:
            reasons.append(f"{j}: нет доступной подходящей машины")
    usable = sorted({r for j in mandatory for r in cost[j] if r in available})
    if len(mandatory) > len(usable):
        reasons.append(f"обязательных работ {len(mandatory)}, а доступных подходящих машин {len(usable)} "
                       f"({', '.join(usable)}), при этом машине назначается не более одной работы")
    return reasons


def check_shift(assign: dict, available=MACHINES, cost=COST) -> list[str]:
    """Validate a one-shift plan (job -> machine): eligibility, availability, one job per machine."""
    errors = []
    for j, r in assign.items():
        if r not in cost[j]:
            errors.append(f"{j}: пара {j}-{r} недопустима")
        if r not in available:
            errors.append(f"{j}: машина {r} недоступна")
    for r in sorted(set(assign.values())):
        jobs = sorted(j for j, rr in assign.items() if rr == r)
        if len(jobs) > 1:
            errors.append(f"машина {r} назначена нескольким работам за смену: {', '.join(jobs)}")
    return errors


# ----------------------------------------------------------------------------- task 4: timetable
@dataclass
class Calendar:
    """Availability of the machines. open - open intervals [start, end); repairs and bookings block time."""
    open: dict = field(default_factory=dict)
    repairs: dict = field(default_factory=dict)       # machine -> [(start, end)]
    bookings: dict = field(default_factory=dict)      # machine -> [(start, end, label)]

    def copy(self) -> "Calendar":
        return Calendar({r: list(v) for r, v in self.open.items()},
                        {r: list(v) for r, v in self.repairs.items()},
                        {r: list(v) for r, v in self.bookings.items()})

    def with_repair(self, machine: str, start: int, end: int) -> "Calendar":
        cal = self.copy()
        cal.repairs.setdefault(machine, []).append((start, end))
        return cal

    def in_open(self, machine, start, end) -> bool:
        return any(s <= start and end <= e for s, e in self.open.get(machine, []))

    def blockers(self, machine, start, end) -> list[str]:
        """Repairs and bookings that intersect [start, end)."""
        found = [f"ремонтом [{hhmm(s)},{hhmm(e)})" for s, e in self.repairs.get(machine, []) if start < e and s < end]
        found += [f"бронью {lb} [{hhmm(s)},{hhmm(e)})" for s, e, lb in self.bookings.get(machine, [])
                  if start < e and s < end]
        return found


def base_calendar() -> Calendar:
    """Table 5."""
    return Calendar(
        open={"R1": [(hm("09:00"), hm("12:00")), (hm("13:00"), hm("17:00"))],
              "R2": [(hm("09:00"), hm("16:00"))],
              "R3": [(hm("10:00"), hm("16:00"))],
              "R4": [(hm("09:00"), hm("17:00"))]},
        repairs={"R1": [(hm("12:00"), hm("13:00"))]},
        bookings={"R2": [(hm("11:00"), hm("12:00"), "B01")]})


def calendar_with_r4_repair() -> Calendar:
    return base_calendar().with_repair("R4", hm("11:30"), hm("12:30"))


def duration_of(job: str) -> int:
    return TIME[job][2]


def check_schedule(cal: Calendar, plan: dict) -> list[str]:
    """Validate a timetable plan: job -> (machine, start). Returns the list of violations (empty = valid).

    Rules: eligible pair; step 30 min; start >= earliest, end <= deadline; the interval [start, end) lies in one
    open interval and does not meet repairs or bookings; works on a machine do not overlap; 30 minutes of
    preparation directly before every work (job or booking) that has a previous work on the machine; the
    preparation lies in an open interval, does not meet the previous work, repairs and bookings."""
    errors = []
    for j, (r, s) in sorted(plan.items()):
        earliest, deadline, dur = TIME[j]
        e = s + dur
        if r not in COST[j]:
            errors.append(f"{j}: пара {j}-{r} недопустима")
        if (s - earliest) % STEP:
            errors.append(f"{j}: начало {hhmm(s)} не кратно шагу 30 минут")
        if s < earliest:
            errors.append(f"{j}: начало {hhmm(s)} раньше раннего начала {hhmm(earliest)}")
        if e > deadline:
            errors.append(f"{j}: окончание {hhmm(e)} позже крайнего срока {hhmm(deadline)}")
        blockers = cal.blockers(r, s, e)
        if blockers:
            errors.append(f"{j} на {r} [{hhmm(s)},{hhmm(e)}): пересечение с " + ", ".join(blockers))
        elif not cal.in_open(r, s, e):
            errors.append(f"{j} на {r} [{hhmm(s)},{hhmm(e)}): интервал не лежит целиком в открытом интервале машины")
    for r in MACHINES:
        works = [(s, s + duration_of(j), j) for j, (rr, s) in plan.items() if rr == r]
        works += [(s, e, lb) for s, e, lb in cal.bookings.get(r, [])]
        works.sort()
        for (s1, e1, n1), (s2, e2, n2) in zip(works, works[1:]):
            if s2 < e1:
                if not (n1.startswith("B") and n2.startswith("B")):
                    errors.append(f"{r}: пересечение {n1} [{hhmm(s1)},{hhmm(e1)}) и {n2} [{hhmm(s2)},{hhmm(e2)})")
                continue
            ps, pe = s2 - PREP, s2
            why = []
            if e1 > ps:
                why.append(f"пересекается с {n1} [{hhmm(s1)},{hhmm(e1)})")
            blockers = [b for b in cal.blockers(r, ps, pe) if not b.startswith(f"бронью {n1} ")]
            why += ["пересекается с " + b for b in blockers]
            if not cal.in_open(r, ps, pe) and not blockers:
                why.append("не лежит в открытом интервале машины")
            if why:
                errors.append(f"{r}: перед {n2} нет времени на подготовку: подготовка [{hhmm(ps)},{hhmm(pe)}) "
                              + "; ".join(why))
    return errors


def preparations(cal: Calendar, plan: dict) -> list[tuple]:
    """Preparation intervals (machine, start, end, before) of a valid plan, for the Gantt chart."""
    result = []
    for r in MACHINES:
        works = [(s, s + duration_of(j), j) for j, (rr, s) in plan.items() if rr == r]
        works += [(s, e, lb) for s, e, lb in cal.bookings.get(r, [])]
        works.sort()
        for (_, _, _), (s2, _, n2) in zip(works, works[1:]):
            result.append((r, s2 - PREP, s2, n2))
    return result


def candidates(cal: Calendar, job: str) -> list[tuple]:
    """Single-job feasible placements (machine, start) ignoring the other jobs and preparation."""
    earliest, deadline, dur = TIME[job]
    found = []
    for r in COST[job]:
        for s in range(earliest, deadline - dur + 1, STEP):
            if not cal.blockers(r, s, s + dur) and cal.in_open(r, s, s + dur):
                found.append((r, s))
    return found


def schedules(cal: Calendar) -> list[dict]:
    """All valid timetables of the four jobs (complete enumeration over the candidates)."""
    lists = [candidates(cal, j) for j in JOBS]
    result = []
    for combo in itertools.product(*lists):
        plan = dict(zip(JOBS, combo))
        if not check_schedule(cal, plan):
            result.append(plan)
    return result


def makespan(plan: dict) -> int:
    return max(s + duration_of(j) for j, (_, s) in plan.items())


def changed_jobs(old: dict, new: dict) -> list[str]:
    return [j for j in JOBS if old[j] != new[j]]


def best_schedule(cal: Calendar, reference: Optional[dict] = None, plans: Optional[list] = None):
    """Earliest finish of the last job. Ties: fewest changes against the reference plan, then the smaller sum of
    finish times, then the lexicographically smallest plan. Returns (plan, number of plans with the same makespan)."""
    plans = schedules(cal) if plans is None else plans
    if not plans:
        return None, 0
    best = min(makespan(p) for p in plans)
    top = [p for p in plans if makespan(p) == best]

    def key(p):
        changes = len(changed_jobs(reference, p)) if reference else 0
        return (changes, sum(s + duration_of(j) for j, (_, s) in p.items()), sorted(p.items()))

    return min(top, key=key), len(top)
