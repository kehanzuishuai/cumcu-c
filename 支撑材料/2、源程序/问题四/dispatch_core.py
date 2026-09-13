from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from scipy.optimize import linprog
from scipy.sparse import coo_matrix


DELTA_H = 1.0 / 6.0
SOC_MIN = 1200.0
SOC_MAX = 10800.0
SOC_INITIAL = 6000.0
ETA_CHARGE = 0.9
ETA_DISCHARGE = 0.9
POWER_MAX_KW = 5000.0
FLOW_MAX_KWH = POWER_MAX_KW * DELTA_H
SOLVER_TOL_KWH = 1e-6
POSITIVE_TOL_KWH = 1e-7


@dataclass
class PlanSolution:
    q: np.ndarray
    charge: np.ndarray
    discharge: np.ndarray
    spill: np.ndarray
    soc: np.ndarray
    primary_cost: float
    actual_cost: float
    secondary_used: bool
    solver_status: int
    solver_message: str
    balance_max_abs_kwh: float
    state_max_abs_kwh: float
    simultaneous_positive_slots: int


@dataclass
class ExecutionResult:
    charge: np.ndarray
    discharge: np.ndarray
    emergency: np.ndarray
    surplus: np.ndarray
    soc: np.ndarray


@dataclass
class AdjustedPlanSolution:
    purchase: np.ndarray
    charge: np.ndarray
    discharge: np.ndarray
    spill: np.ndarray
    soc: np.ndarray
    upward: np.ndarray
    downward: np.ndarray
    variable_objective: float
    secondary_used: bool
    balance_max_abs_kwh: float
    state_max_abs_kwh: float
    adjustment_link_max_abs_kwh: float
    simultaneous_positive_slots: int


def _slices(n: int) -> dict[str, slice]:
    return {
        "q": slice(0, n),
        "charge": slice(n, 2 * n),
        "discharge": slice(2 * n, 3 * n),
        "spill": slice(3 * n, 4 * n),
        "soc": slice(4 * n, 5 * n + 1),
    }


def _equalities(net_load_kwh: np.ndarray) -> tuple[Any, np.ndarray]:
    n = len(net_load_kwh)
    idx = _slices(n)
    rows: list[int] = []
    cols: list[int] = []
    data: list[float] = []
    rhs = np.zeros(2 * n, dtype=float)
    for t in range(n):
        # q + discharge = net_load + charge + spill.
        for col, value in (
            (idx["q"].start + t, 1.0),
            (idx["charge"].start + t, -1.0),
            (idx["discharge"].start + t, 1.0),
            (idx["spill"].start + t, -1.0),
        ):
            rows.append(t)
            cols.append(col)
            data.append(value)
        rhs[t] = float(net_load_kwh[t])

        # SOC[t+1] = SOC[t] + eta_c*charge - discharge/eta_d.
        row = n + t
        for col, value in (
            (idx["charge"].start + t, -ETA_CHARGE),
            (idx["discharge"].start + t, 1.0 / ETA_DISCHARGE),
            (idx["soc"].start + t, -1.0),
            (idx["soc"].start + t + 1, 1.0),
        ):
            rows.append(row)
            cols.append(col)
            data.append(value)
    return coo_matrix((data, (rows, cols)), shape=(2 * n, 5 * n + 1)).tocsr(), rhs


def solve_deterministic_plan(
    net_load_kwh: np.ndarray,
    price_yuan_per_kwh: np.ndarray,
    soc_initial_kwh: float,
    terminal_soc_kwh: float,
) -> PlanSolution:
    net = np.asarray(net_load_kwh, dtype=float)
    price = np.asarray(price_yuan_per_kwh, dtype=float)
    if net.ndim != 1 or price.shape != net.shape:
        raise ValueError("净负荷和价格必须是一维同长向量")
    n = len(net)
    idx = _slices(n)
    a_eq, b_eq = _equalities(net)
    objective = np.zeros(5 * n + 1, dtype=float)
    objective[idx["q"]] = price
    bounds: list[tuple[float | None, float | None]] = []
    bounds.extend([(0.0, None)] * n)
    bounds.extend([(0.0, FLOW_MAX_KWH)] * n)
    bounds.extend([(0.0, FLOW_MAX_KWH)] * n)
    bounds.extend([(0.0, None)] * n)
    bounds.append((soc_initial_kwh, soc_initial_kwh))
    bounds.extend([(SOC_MIN, SOC_MAX)] * (n - 1))
    bounds.append((terminal_soc_kwh, terminal_soc_kwh))

    primary = linprog(objective, A_eq=a_eq, b_eq=b_eq, bounds=bounds, method="highs")
    if not primary.success:
        raise RuntimeError(f"确定性计划LP失败: {primary.status} {primary.message}")
    x = np.asarray(primary.x, dtype=float)
    simultaneous = np.minimum(x[idx["charge"]], x[idx["discharge"]])
    secondary_used = bool(np.any(simultaneous > POSITIVE_TOL_KWH))
    status = int(primary.status)
    message = str(primary.message)
    if secondary_used:
        secondary_objective = np.zeros_like(objective)
        secondary_objective[idx["charge"]] = 1.0
        secondary_objective[idx["discharge"]] = 1.0
        cost_tolerance = max(1e-7, abs(float(primary.fun)) * 1e-11)
        secondary = linprog(
            secondary_objective,
            A_ub=coo_matrix(objective.reshape(1, -1)).tocsr(),
            b_ub=np.asarray([float(primary.fun) + cost_tolerance]),
            A_eq=a_eq,
            b_eq=b_eq,
            bounds=bounds,
            method="highs",
        )
        if not secondary.success:
            raise RuntimeError(f"确定性计划二级LP失败: {secondary.status} {secondary.message}")
        x = np.asarray(secondary.x, dtype=float)
        status = int(secondary.status)
        message = str(secondary.message)
    x[np.abs(x) < 1e-10] = 0.0

    q = x[idx["q"]]
    charge = x[idx["charge"]]
    discharge = x[idx["discharge"]]
    spill = x[idx["spill"]]
    soc = x[idx["soc"]]
    balance = q + discharge - net - charge - spill
    state = soc[1:] - soc[:-1] - ETA_CHARGE * charge + discharge / ETA_DISCHARGE
    return PlanSolution(
        q=q,
        charge=charge,
        discharge=discharge,
        spill=spill,
        soc=soc,
        primary_cost=float(primary.fun),
        actual_cost=float(np.dot(price, q)),
        secondary_used=secondary_used,
        solver_status=status,
        solver_message=message,
        balance_max_abs_kwh=float(np.max(np.abs(balance))),
        state_max_abs_kwh=float(np.max(np.abs(state))),
        simultaneous_positive_slots=int(np.sum(np.minimum(charge, discharge) > POSITIVE_TOL_KWH)),
    )


def execute_fixed_plan(
    load_kwh: np.ndarray,
    pv_kwh: np.ndarray,
    normal_purchase_kwh: np.ndarray,
    soc_initial_kwh: float,
) -> ExecutionResult:
    load = np.asarray(load_kwh, dtype=float)
    pv = np.asarray(pv_kwh, dtype=float)
    purchase = np.asarray(normal_purchase_kwh, dtype=float)
    if load.shape != pv.shape or load.shape != purchase.shape or load.ndim != 1:
        raise ValueError("实际负载、光伏和计划购电必须是一维同长向量")
    n = len(load)
    charge = np.zeros(n, dtype=float)
    discharge = np.zeros(n, dtype=float)
    emergency = np.zeros(n, dtype=float)
    surplus = np.zeros(n, dtype=float)
    soc = np.zeros(n + 1, dtype=float)
    soc[0] = float(soc_initial_kwh)

    for t in range(n):
        supply_before_storage = purchase[t] + pv[t] - load[t]
        if supply_before_storage >= 0.0:
            max_charge_by_soc = max(0.0, (SOC_MAX - soc[t]) / ETA_CHARGE)
            charge[t] = min(supply_before_storage, FLOW_MAX_KWH, max_charge_by_soc)
            surplus[t] = max(0.0, supply_before_storage - charge[t])
            soc[t + 1] = soc[t] + ETA_CHARGE * charge[t]
        else:
            shortage = -supply_before_storage
            max_discharge_by_soc = max(0.0, (soc[t] - SOC_MIN) * ETA_DISCHARGE)
            discharge[t] = min(shortage, FLOW_MAX_KWH, max_discharge_by_soc)
            emergency[t] = max(0.0, shortage - discharge[t])
            soc[t + 1] = soc[t] - discharge[t] / ETA_DISCHARGE

    for array in (charge, discharge, emergency, surplus, soc):
        array[np.abs(array) < 1e-10] = 0.0
    return ExecutionResult(charge=charge, discharge=discharge, emergency=emergency, surplus=surplus, soc=soc)


def solve_adjusted_plan(
    net_load_kwh: np.ndarray,
    price_yuan_per_kwh: np.ndarray,
    soc_initial_kwh: float,
    terminal_soc_kwh: float,
    original_purchase_kwh: np.ndarray,
    adjustable_count: int,
) -> AdjustedPlanSolution:
    net = np.asarray(net_load_kwh, dtype=float)
    price = np.asarray(price_yuan_per_kwh, dtype=float)
    original = np.asarray(original_purchase_kwh, dtype=float)
    if net.ndim != 1 or price.shape != net.shape or original.shape != net.shape:
        raise ValueError("调整计划的净负荷、价格和原计划必须是一维同长向量")
    n = len(net)
    if not 0 <= adjustable_count <= n:
        raise ValueError("可调整槽数越界")
    idx = {
        "q": slice(0, n),
        "charge": slice(n, 2 * n),
        "discharge": slice(2 * n, 3 * n),
        "spill": slice(3 * n, 4 * n),
        "soc": slice(4 * n, 5 * n + 1),
        "up": slice(5 * n + 1, 6 * n + 1),
        "down": slice(6 * n + 1, 7 * n + 1),
    }
    variable_count = 7 * n + 1
    rows: list[int] = []
    cols: list[int] = []
    data: list[float] = []
    rhs = np.zeros(2 * n + adjustable_count, dtype=float)
    for t in range(n):
        for col, value in (
            (idx["q"].start + t, 1.0),
            (idx["charge"].start + t, -1.0),
            (idx["discharge"].start + t, 1.0),
            (idx["spill"].start + t, -1.0),
        ):
            rows.append(t)
            cols.append(col)
            data.append(value)
        rhs[t] = net[t]
        row = n + t
        for col, value in (
            (idx["charge"].start + t, -ETA_CHARGE),
            (idx["discharge"].start + t, 1.0 / ETA_DISCHARGE),
            (idx["soc"].start + t, -1.0),
            (idx["soc"].start + t + 1, 1.0),
        ):
            rows.append(row)
            cols.append(col)
            data.append(value)
    for t in range(adjustable_count):
        row = 2 * n + t
        for col, value in (
            (idx["q"].start + t, 1.0),
            (idx["up"].start + t, -1.0),
            (idx["down"].start + t, 1.0),
        ):
            rows.append(row)
            cols.append(col)
            data.append(value)
        rhs[row] = original[t]
    a_eq = coo_matrix((data, (rows, cols)), shape=(len(rhs), variable_count)).tocsr()

    objective = np.zeros(variable_count, dtype=float)
    objective[idx["q"].start + adjustable_count : idx["q"].stop] = price[adjustable_count:]
    objective[idx["up"].start : idx["up"].start + adjustable_count] = 1.5 * price[:adjustable_count]
    objective[idx["down"].start : idx["down"].start + adjustable_count] = -0.5 * price[:adjustable_count]
    bounds: list[tuple[float | None, float | None]] = []
    bounds.extend([(0.0, None)] * n)
    bounds.extend([(0.0, FLOW_MAX_KWH)] * n)
    bounds.extend([(0.0, FLOW_MAX_KWH)] * n)
    bounds.extend([(0.0, None)] * n)
    bounds.append((soc_initial_kwh, soc_initial_kwh))
    bounds.extend([(SOC_MIN, SOC_MAX)] * (n - 1))
    bounds.append((terminal_soc_kwh, terminal_soc_kwh))
    bounds.extend([(0.0, None)] * adjustable_count)
    bounds.extend([(0.0, 0.0)] * (n - adjustable_count))
    bounds.extend([(0.0, None)] * adjustable_count)
    bounds.extend([(0.0, 0.0)] * (n - adjustable_count))

    primary = linprog(objective, A_eq=a_eq, b_eq=rhs, bounds=bounds, method="highs")
    if not primary.success:
        raise RuntimeError(f"调整计划LP失败: {primary.status} {primary.message}")
    x = np.asarray(primary.x, dtype=float)
    simultaneous = np.minimum(x[idx["charge"]], x[idx["discharge"]])
    secondary_used = bool(np.any(simultaneous > POSITIVE_TOL_KWH))
    if secondary_used:
        secondary_objective = np.zeros_like(objective)
        secondary_objective[idx["charge"]] = 1.0
        secondary_objective[idx["discharge"]] = 1.0
        cost_tolerance = max(1e-7, abs(float(primary.fun)) * 1e-11)
        secondary = linprog(
            secondary_objective,
            A_ub=coo_matrix(objective.reshape(1, -1)).tocsr(),
            b_ub=np.asarray([float(primary.fun) + cost_tolerance]),
            A_eq=a_eq,
            b_eq=rhs,
            bounds=bounds,
            method="highs",
        )
        if not secondary.success:
            raise RuntimeError(f"调整计划二级LP失败: {secondary.status} {secondary.message}")
        x = np.asarray(secondary.x, dtype=float)
    x[np.abs(x) < 1e-10] = 0.0
    purchase = x[idx["q"]]
    charge = x[idx["charge"]]
    discharge = x[idx["discharge"]]
    spill = x[idx["spill"]]
    soc = x[idx["soc"]]
    upward = x[idx["up"]]
    downward = x[idx["down"]]
    balance = purchase + discharge - net - charge - spill
    state = soc[1:] - soc[:-1] - ETA_CHARGE * charge + discharge / ETA_DISCHARGE
    link = purchase[:adjustable_count] - original[:adjustable_count] - upward[:adjustable_count] + downward[:adjustable_count]
    return AdjustedPlanSolution(
        purchase=purchase,
        charge=charge,
        discharge=discharge,
        spill=spill,
        soc=soc,
        upward=upward,
        downward=downward,
        variable_objective=float(np.dot(objective, x)),
        secondary_used=secondary_used,
        balance_max_abs_kwh=float(np.max(np.abs(balance))),
        state_max_abs_kwh=float(np.max(np.abs(state))),
        adjustment_link_max_abs_kwh=float(np.max(np.abs(link))) if adjustable_count else 0.0,
        simultaneous_positive_slots=int(np.sum(np.minimum(charge, discharge) > POSITIVE_TOL_KWH)),
    )


def maximal_positive_events(values: np.ndarray, tolerance: float = POSITIVE_TOL_KWH) -> list[tuple[int, int, float]]:
    vector = np.asarray(values, dtype=float)
    events: list[tuple[int, int, float]] = []
    start: int | None = None
    for t, value in enumerate(vector):
        if value > tolerance and start is None:
            start = t
        if start is not None and (value <= tolerance or t == len(vector) - 1):
            end = t if value <= tolerance else t + 1
            events.append((start, end, float(np.sum(vector[start:end]))))
            start = None
    return events
