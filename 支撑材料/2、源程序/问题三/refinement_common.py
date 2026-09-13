from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any, Callable

import numpy as np
from scipy.optimize import linprog
from scipy.sparse import coo_matrix

from common_data import PROJECT_ROOT
from dispatch_core import (
    AdjustedPlanSolution,
    ETA_CHARGE,
    ETA_DISCHARGE,
    FLOW_MAX_KWH,
    POSITIVE_TOL_KWH,
    SOC_MAX,
    SOC_MIN,
)


EXPERIMENT_ROOT = PROJECT_ROOT / "experiments" / "q3_q4_refinement"
RESULTS = EXPERIMENT_ROOT / "results"
VALIDATION = EXPERIMENT_ROOT / "validation"
INTERMEDIATE = EXPERIMENT_ROOT / "intermediate"

FROZEN_TARGETS = (
    "results/q1_summary.json",
    "results/result1.xlsx",
    "validation/q1_validation.json",
    "results/q2_summary.json",
    "results/result2.xlsx",
    "validation/q2_validation.json",
    "results/q3_summary.json",
    "results/result3.xlsx",
    "results/q3_detail.csv",
    "validation/q3_validation.json",
    "results/q4_summary.json",
    "results/result4-2.xlsx",
    "results/result4-3.xlsx",
    "validation/q4_2_validation.json",
    "validation/q4_3_validation.json",
)


def ensure_dirs() -> None:
    for path in (RESULTS, VALIDATION, INTERMEDIATE):
        path.mkdir(parents=True, exist_ok=True)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def frozen_hashes() -> dict[str, str]:
    return {name: sha256(PROJECT_ROOT / name) for name in FROZEN_TARGETS}


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"empty CSV rejected: {path}")
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def make_adjusted_solver(downward_objective_multiplier: float) -> Callable[..., AdjustedPlanSolution]:
    """Create the same Q3 LP with only the A08 downward objective coefficient changed."""

    def solve(
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
            raise ValueError("adjusted plan vectors must be one-dimensional and aligned")
        n = len(net)
        if not 0 <= adjustable_count <= n:
            raise ValueError("adjustable_count out of range")
        idx = {
            "q": slice(0, n),
            "charge": slice(n, 2 * n),
            "discharge": slice(2 * n, 3 * n),
            "spill": slice(3 * n, 4 * n),
            "soc": slice(4 * n, 5 * n + 1),
            "up": slice(5 * n + 1, 6 * n + 1),
            "down": slice(6 * n + 1, 7 * n + 1),
        }
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
                rows.append(t); cols.append(col); data.append(value)
            rhs[t] = net[t]
            row = n + t
            for col, value in (
                (idx["charge"].start + t, -ETA_CHARGE),
                (idx["discharge"].start + t, 1.0 / ETA_DISCHARGE),
                (idx["soc"].start + t, -1.0),
                (idx["soc"].start + t + 1, 1.0),
            ):
                rows.append(row); cols.append(col); data.append(value)
        for t in range(adjustable_count):
            row = 2 * n + t
            for col, value in (
                (idx["q"].start + t, 1.0),
                (idx["up"].start + t, -1.0),
                (idx["down"].start + t, 1.0),
            ):
                rows.append(row); cols.append(col); data.append(value)
            rhs[row] = original[t]
        a_eq = coo_matrix((data, (rows, cols)), shape=(len(rhs), 7 * n + 1)).tocsr()

        objective = np.zeros(7 * n + 1, dtype=float)
        objective[idx["q"].start + adjustable_count : idx["q"].stop] = price[adjustable_count:]
        objective[idx["up"].start : idx["up"].start + adjustable_count] = 1.5 * price[:adjustable_count]
        objective[idx["down"].start : idx["down"].start + adjustable_count] = (
            downward_objective_multiplier * price[:adjustable_count]
        )
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
            raise RuntimeError(f"adjusted LP failed: {primary.status} {primary.message}")
        x = np.asarray(primary.x, dtype=float)
        secondary_used = bool(np.any(np.minimum(x[idx["charge"]], x[idx["discharge"]]) > POSITIVE_TOL_KWH))
        if secondary_used:
            secondary_objective = np.zeros_like(objective)
            secondary_objective[idx["charge"]] = 1.0
            secondary_objective[idx["discharge"]] = 1.0
            tolerance = max(1e-7, abs(float(primary.fun)) * 1e-11)
            secondary = linprog(
                secondary_objective,
                A_ub=coo_matrix(objective.reshape(1, -1)).tocsr(),
                b_ub=np.asarray([float(primary.fun) + tolerance]),
                A_eq=a_eq,
                b_eq=rhs,
                bounds=bounds,
                method="highs",
            )
            if not secondary.success:
                raise RuntimeError(f"secondary adjusted LP failed: {secondary.status} {secondary.message}")
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

    return solve


def resettle_run(run: dict[str, Any], settlement: str) -> dict[str, Any]:
    if settlement not in {"refund", "no_refund"}:
        raise ValueError(settlement)
    down_sign = -1.0 if settlement == "refund" else 1.0
    for detail in run["detail"]:
        base = float(detail["base_plan_cost_yuan"])
        down_component = float(detail["downward_credit_yuan"])
        up = float(detail["upward_adjustment_cost_yuan"])
        emergency = float(detail["emergency_cost_yuan"])
        detail["settlement_kind"] = settlement
        detail["downward_component_yuan"] = down_sign * down_component
        detail["net_adjustment_cost_yuan"] = down_sign * down_component + up
        detail["gross_adjustment_fee_yuan"] = down_component + up
        detail["normal_settlement_cost_yuan"] = base + down_sign * down_component + up
        detail["total_cost_yuan"] = detail["normal_settlement_cost_yuan"] + emergency
    by_date: dict[str, list[dict[str, Any]]] = {}
    for row in run["detail"]:
        by_date.setdefault(str(row["date"]), []).append(row)
    for daily in run["daily"]:
        rows = by_date[str(daily["date"])]
        for key in (
            "normal_settlement_cost_yuan",
            "emergency_cost_yuan",
            "total_cost_yuan",
            "net_adjustment_cost_yuan",
            "gross_adjustment_fee_yuan",
        ):
            daily[key] = float(sum(float(row[key]) for row in rows))
        daily["settlement_kind"] = settlement
        daily["downward_component_yuan"] = float(sum(float(row["downward_component_yuan"]) for row in rows))
    aggregate = run["aggregate"]
    aggregate["settlement_kind"] = settlement
    for key in (
        "normal_settlement_cost_yuan",
        "emergency_cost_yuan",
        "total_cost_yuan",
        "net_adjustment_cost_yuan",
        "gross_adjustment_fee_yuan",
    ):
        aggregate[key] = float(sum(float(row[key]) for row in run["daily"]))
    aggregate["downward_component_yuan"] = float(sum(float(row["downward_component_yuan"]) for row in run["daily"]))
    return run

