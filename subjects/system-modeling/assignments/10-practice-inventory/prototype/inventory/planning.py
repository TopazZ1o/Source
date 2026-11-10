"""Stock indicators and replenishment proposal. Pure calculations plus read-only database access.

A  = OH - R - B            available quantity: decides whether a NEW request can be served
IP = OH + OO - BO          inventory position: decides whether to REPLENISH
d  = D / 300               daily demand (300 working days)
ROP = d * L + SS           reorder point
EOQ = sqrt(2 * D * S / H)  economic order quantity
TC(Q) = D / Q * S + Q / 2 * H   cycle cost of a real lot (SS holding cost is common to all lots and omitted)
"""

from __future__ import annotations

import math
import sqlite3
from dataclasses import dataclass, replace
from typing import Optional

WORKING_DAYS = 300


@dataclass(frozen=True)
class Params:
    code: str
    D: int      # annual demand, pieces
    S: int      # cost of one order, tenge
    H: int      # holding cost per piece per year, tenge
    L: int      # lead time, working days
    SS: int     # safety stock, pieces
    p: int      # supplier pack size
    OO: int     # ordered, not received
    BO: int     # backorders


@dataclass(frozen=True)
class Lot:
    eoq: float
    lower: Optional[int]
    upper: int
    tc_lower: Optional[float]
    tc_upper: float
    q: int


@dataclass(frozen=True)
class Row:
    code: str
    oh: int
    r: int
    b: int
    a: int
    ip: int
    d: float
    rop: float
    lot: Lot
    need: bool          # IP <= ROP
    order_qty: int      # Q if replenishment is needed, otherwise 0
    ip_after: int       # IP after the proposed order


def available(oh: int, r: int, b: int) -> int:
    return oh - r - b


def inventory_position(oh: int, oo: int, bo: int) -> int:
    return oh + oo - bo


def daily_demand(D: int) -> float:
    return D / WORKING_DAYS


def reorder_point(d: float, L: int, SS: int) -> float:
    return d * L + SS


def eoq(D: int, S: int, H: int) -> float:
    return math.sqrt(2 * D * S / H)


def total_cost(D: int, S: int, H: int, Q: int) -> float:
    return D / Q * S + Q / 2 * H


def choose_lot(pr: Params) -> Lot:
    """Compare the two nearest positive lots that are multiples of the pack size: below and above EOQ.

    If EOQ is exactly a multiple of the pack size, it is itself the lower candidate and is compared
    with the next multiple above it.
    """
    e = eoq(pr.D, pr.S, pr.H)
    k = int(e // pr.p)
    exact = k > 0 and (k * pr.p) ** 2 * pr.H == 2 * pr.D * pr.S      # exact integer test, no float noise
    lower = k * pr.p if k > 0 else None
    upper = lower + pr.p if exact else (k + 1) * pr.p
    tc_lo = total_cost(pr.D, pr.S, pr.H, lower) if lower else None
    tc_up = total_cost(pr.D, pr.S, pr.H, upper)
    q = lower if (lower is not None and tc_lo <= tc_up) else upper
    return Lot(e, lower, upper, tc_lo, tc_up, q)


def indicators(pr: Params, oh: int, r: int, b: int) -> Row:
    d = daily_demand(pr.D)
    ip = inventory_position(oh, pr.OO, pr.BO)
    rop = reorder_point(d, pr.L, pr.SS)
    lot = choose_lot(pr)
    need = ip <= rop
    return Row(pr.code, oh, r, b, available(oh, r, b), ip, d, rop, lot, need,
               lot.q if need else 0, ip + (lot.q if need else 0))


def load_params(conn: sqlite3.Connection) -> dict[str, Params]:
    rows = conn.execute("SELECT product_code, annual_demand, order_cost, holding_cost, lead_days, safety_stock, "
                        "pack_size, on_order, backorder FROM planning_param ORDER BY product_code").fetchall()
    return {r[0]: Params(*tuple(r)) for r in rows}


def replenishment_report(conn: sqlite3.Connection, warehouse: str = "W01",
                         lead_time_shift: Optional[dict[str, int]] = None) -> list[Row]:
    """Proposal for replenishment. Only SELECT statements: the stock is never changed (see test T11).

    lead_time_shift adds working days to L of the given products (scenario of task 6); SS stays constant.
    """
    shift = lead_time_shift or {}
    params = load_params(conn)
    rows = []
    for code, pr in params.items():
        if code in shift:
            pr = replace(pr, L=pr.L + shift[code])
        pos = conn.execute("SELECT oh, r, b FROM v_stock_position WHERE product_code = ? AND warehouse_code = ?",
                           (code, warehouse)).fetchone()
        if pos is not None:
            rows.append(indicators(pr, pos["oh"], pos["r"], pos["b"]))
    return rows
