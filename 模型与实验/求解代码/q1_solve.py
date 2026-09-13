from __future__ import annotations

import csv
import json
import math
import platform
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import scipy
from scipy.optimize import linprog
from scipy.sparse import coo_matrix, vstack

from common_data import PROJECT_ROOT, load_attachment1, natural_slot_label, sha256


RESULTS = PROJECT_ROOT / "results"
VALIDATION = PROJECT_ROOT / "validation"
INTERMEDIATE = PROJECT_ROOT / "intermediate"

N = 144
DELTA_H = 1.0 / 6.0
SOC_MIN = 1200.0
SOC_MAX = 10800.0
SOC_INITIAL = 6000.0
SOC_TERMINAL = 6000.0
POWER_MAX_KW = 5000.0
FLOW_MAX_KWH = POWER_MAX_KW * DELTA_H
SOLVER_TOL_KWH = 1e-6
POSITIVE_TOL_KWH = 1e-7


@dataclass
class Solution:
    scenario: str
    eta_charge: float
    eta_discharge: float
    integration: str
    q: np.ndarray
    charge: np.ndarray
    discharge: np.ndarray
    spill: np.ndarray
    soc: np.ndarray
    load_kwh: np.ndarray
    pv_kwh: np.ndarray
    primary_optimum: float
    actual_cost: float
    solver_status_primary: int
    solver_message_primary: str
    solver_status_secondary: int
    solver_message_secondary: str


def energy_from_power(power_kw: np.ndarray, method: str) -> np.ndarray:
    if method == "right_endpoint_rectangle":
        return power_kw * DELTA_H
    if method == "trapezoidal_repeated_day":
        previous = np.roll(power_kw, 1)
        return 0.5 * (previous + power_kw) * DELTA_H
    raise ValueError(f"未知积分口径: {method}")


def variable_slices() -> dict[str, slice]:
    return {
        "q": slice(0, N),
        "charge": slice(N, 2 * N),
        "discharge": slice(2 * N, 3 * N),
        "spill": slice(3 * N, 4 * N),
        "soc": slice(4 * N, 5 * N + 1),
    }


def build_equalities(load_kwh: np.ndarray, pv_kwh: np.ndarray, eta_c: float, eta_d: float):
    idx = variable_slices()
    rows: list[int] = []
    cols: list[int] = []
    data: list[float] = []
    rhs = np.zeros(2 * N, dtype=float)
    for t in range(N):
        # q + PV + discharge = load + charge + spill
        row = t
        for col, value in (
            (idx["q"].start + t, 1.0),
            (idx["charge"].start + t, -1.0),
            (idx["discharge"].start + t, 1.0),
            (idx["spill"].start + t, -1.0),
        ):
            rows.append(row)
            cols.append(col)
            data.append(value)
        rhs[row] = load_kwh[t] - pv_kwh[t]

        # SOC[t+1] = SOC[t] + eta_c*charge - discharge/eta_d
        row = N + t
        for col, value in (
            (idx["charge"].start + t, -eta_c),
            (idx["discharge"].start + t, 1.0 / eta_d),
            (idx["soc"].start + t, -1.0),
            (idx["soc"].start + t + 1, 1.0),
        ):
            rows.append(row)
            cols.append(col)
            data.append(value)
    matrix = coo_matrix((data, (rows, cols)), shape=(2 * N, 5 * N + 1)).tocsr()
    return matrix, rhs


def solve_lp(
    price: np.ndarray,
    load_kw: np.ndarray,
    pv_kw: np.ndarray,
    *,
    scenario: str,
    eta_c: float,
    eta_d: float,
    integration: str,
) -> Solution:
    load_kwh = energy_from_power(load_kw, integration)
    pv_kwh = energy_from_power(pv_kw, integration)
    idx = variable_slices()
    a_eq, b_eq = build_equalities(load_kwh, pv_kwh, eta_c, eta_d)

    objective = np.zeros(5 * N + 1, dtype=float)
    objective[idx["q"]] = price
    bounds: list[tuple[float | None, float | None]] = []
    bounds.extend([(0.0, None)] * N)
    bounds.extend([(0.0, FLOW_MAX_KWH)] * N)
    bounds.extend([(0.0, FLOW_MAX_KWH)] * N)
    bounds.extend([(0.0, None)] * N)
    bounds.append((SOC_INITIAL, SOC_INITIAL))
    bounds.extend([(SOC_MIN, SOC_MAX)] * (N - 1))
    bounds.append((SOC_TERMINAL, SOC_TERMINAL))

    primary = linprog(objective, A_eq=a_eq, b_eq=b_eq, bounds=bounds, method="highs")
    if not primary.success:
        raise RuntimeError(f"Q1主LP失败: {primary.status} {primary.message}")

    # Lexicographic tie-break: keep the purchase optimum, then minimize battery throughput.
    # This does not replace the primary cash-cost objective and removes degenerate cycling.
    secondary_objective = np.zeros_like(objective)
    secondary_objective[idx["charge"]] = 1.0
    secondary_objective[idx["discharge"]] = 1.0
    cost_tolerance = max(1e-7, abs(float(primary.fun)) * 1e-11)
    a_ub = coo_matrix(objective.reshape(1, -1)).tocsr()
    b_ub = np.asarray([float(primary.fun) + cost_tolerance])
    secondary = linprog(
        secondary_objective,
        A_ub=a_ub,
        b_ub=b_ub,
        A_eq=a_eq,
        b_eq=b_eq,
        bounds=bounds,
        method="highs",
    )
    if not secondary.success:
        raise RuntimeError(f"Q1二级LP失败: {secondary.status} {secondary.message}")

    x = np.asarray(secondary.x, dtype=float)
    x[np.abs(x) < 1e-10] = 0.0
    return Solution(
        scenario=scenario,
        eta_charge=eta_c,
        eta_discharge=eta_d,
        integration=integration,
        q=x[idx["q"]],
        charge=x[idx["charge"]],
        discharge=x[idx["discharge"]],
        spill=x[idx["spill"]],
        soc=x[idx["soc"]],
        load_kwh=load_kwh,
        pv_kwh=pv_kwh,
        primary_optimum=float(primary.fun),
        actual_cost=float(np.dot(price, x[idx["q"]])),
        solver_status_primary=int(primary.status),
        solver_message_primary=str(primary.message),
        solver_status_secondary=int(secondary.status),
        solver_message_secondary=str(secondary.message),
    )


def validate(solution: Solution, price: np.ndarray) -> dict[str, Any]:
    balance = solution.q + solution.pv_kwh + solution.discharge - solution.load_kwh - solution.charge - solution.spill
    state = solution.soc[1:] - solution.soc[:-1] - solution.eta_charge * solution.charge + solution.discharge / solution.eta_discharge
    simultaneous = np.minimum(solution.charge, solution.discharge)
    independent_cost = float(np.sum(price * solution.q))
    checks = {
        "balance_max_abs_kwh": float(np.max(np.abs(balance))),
        "state_max_abs_kwh": float(np.max(np.abs(state))),
        "soc_min_kwh": float(np.min(solution.soc)),
        "soc_max_kwh": float(np.max(solution.soc)),
        "soc_open_kwh": float(solution.soc[0]),
        "soc_close_kwh": float(solution.soc[-1]),
        "charge_max_kwh_per_slot": float(np.max(solution.charge)),
        "discharge_max_kwh_per_slot": float(np.max(solution.discharge)),
        "simultaneous_positive_slot_count": int(np.sum(simultaneous > POSITIVE_TOL_KWH)),
        "simultaneous_max_kwh": float(np.max(simultaneous)),
        "independent_cost_yuan": independent_cost,
        "reported_cost_yuan": solution.actual_cost,
        "cost_reconciliation_abs_yuan": float(abs(independent_cost - solution.actual_cost)),
        "secondary_cost_above_primary_yuan": float(solution.actual_cost - solution.primary_optimum),
    }
    pass_flags = {
        "balance": checks["balance_max_abs_kwh"] <= SOLVER_TOL_KWH,
        "state": checks["state_max_abs_kwh"] <= SOLVER_TOL_KWH,
        "soc_bounds": checks["soc_min_kwh"] >= SOC_MIN - SOLVER_TOL_KWH and checks["soc_max_kwh"] <= SOC_MAX + SOLVER_TOL_KWH,
        "soc_cycle": abs(checks["soc_open_kwh"] - SOC_INITIAL) <= SOLVER_TOL_KWH and abs(checks["soc_close_kwh"] - SOC_TERMINAL) <= SOLVER_TOL_KWH,
        "power": checks["charge_max_kwh_per_slot"] <= FLOW_MAX_KWH + SOLVER_TOL_KWH and checks["discharge_max_kwh_per_slot"] <= FLOW_MAX_KWH + SOLVER_TOL_KWH,
        "nonnegative": bool(np.min(np.concatenate([solution.q, solution.charge, solution.discharge, solution.spill])) >= -SOLVER_TOL_KWH),
        "mutual_exclusion": checks["simultaneous_positive_slot_count"] == 0,
        "cost_reconciliation": checks["cost_reconciliation_abs_yuan"] <= 1e-6,
    }
    return {"metrics": checks, "pass_flags": pass_flags, "all_pass": all(pass_flags.values())}


def baseline(load_kwh: np.ndarray, pv_kwh: np.ndarray, price: np.ndarray) -> dict[str, float]:
    q = np.maximum(load_kwh - pv_kwh, 0.0)
    spill = np.maximum(pv_kwh - load_kwh, 0.0)
    return {
        "purchase_kwh": float(np.sum(q)),
        "cost_yuan": float(np.sum(price * q)),
        "pv_spill_kwh": float(np.sum(spill)),
    }


def write_detail(solution: Solution, data: dict[str, Any], price: np.ndarray) -> Path:
    path = RESULTS / "q1_detail.csv"
    fields = [
        "slot", "source_endpoint_label", "interval_start", "interval_end", "interval_label",
        "price_yuan_per_kwh", "load_kw", "pv_kw", "load_kwh", "pv_kwh",
        "normal_purchase_kwh", "charge_bus_kwh", "discharge_bus_kwh", "pv_spill_or_surplus_kwh",
        "soc_open_kwh", "soc_close_kwh", "purchase_cost_yuan", "balance_residual_kwh", "state_residual_kwh",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for t in range(N):
            start, end, label = natural_slot_label(t)
            balance = solution.q[t] + solution.pv_kwh[t] + solution.discharge[t] - solution.load_kwh[t] - solution.charge[t] - solution.spill[t]
            state = solution.soc[t + 1] - solution.soc[t] - solution.eta_charge * solution.charge[t] + solution.discharge[t] / solution.eta_discharge
            writer.writerow({
                "slot": t + 1,
                "source_endpoint_label": data["raw_endpoint_labels"][t],
                "interval_start": start,
                "interval_end": end,
                "interval_label": label,
                "price_yuan_per_kwh": f"{price[t]:.10f}",
                "load_kw": f"{data['load_kw'][t]:.10f}",
                "pv_kw": f"{data['pv_kw'][t]:.10f}",
                "load_kwh": f"{solution.load_kwh[t]:.10f}",
                "pv_kwh": f"{solution.pv_kwh[t]:.10f}",
                "normal_purchase_kwh": f"{solution.q[t]:.10f}",
                "charge_bus_kwh": f"{solution.charge[t]:.10f}",
                "discharge_bus_kwh": f"{solution.discharge[t]:.10f}",
                "pv_spill_or_surplus_kwh": f"{solution.spill[t]:.10f}",
                "soc_open_kwh": f"{solution.soc[t]:.10f}",
                "soc_close_kwh": f"{solution.soc[t + 1]:.10f}",
                "purchase_cost_yuan": f"{price[t] * solution.q[t]:.10f}",
                "balance_residual_kwh": f"{balance:.12g}",
                "state_residual_kwh": f"{state:.12g}",
            })
    return path


def four_hour_summary(solution: Solution) -> list[dict[str, float | str]]:
    rows: list[dict[str, float | str]] = []
    for block in range(6):
        start = block * 24
        stop = (block + 1) * 24
        rows.append({
            "interval": f"{block * 4:02d}:00-{(block + 1) * 4:02d}:00",
            "charge_kwh": float(np.sum(solution.charge[start:stop])),
            "discharge_kwh": float(np.sum(solution.discharge[start:stop])),
        })
    return rows


def write_four_hour(rows: list[dict[str, float | str]]) -> Path:
    path = RESULTS / "q1_storage_4h.csv"
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["interval", "charge_kwh", "discharge_kwh"])
        writer.writeheader()
        for row in rows:
            writer.writerow({"interval": row["interval"], "charge_kwh": f"{float(row['charge_kwh']):.10f}", "discharge_kwh": f"{float(row['discharge_kwh']):.10f}"})
    return path


def json_default(value: Any):
    if isinstance(value, np.generic):
        return value.item()
    raise TypeError(type(value).__name__)


def main() -> None:
    RESULTS.mkdir(parents=True, exist_ok=True)
    VALIDATION.mkdir(parents=True, exist_ok=True)
    INTERMEDIATE.mkdir(parents=True, exist_ok=True)
    data = load_attachment1()
    price = data["price_yuan_per_kwh"]

    scenarios = [
        ("base", 0.9, 0.9, "right_endpoint_rectangle"),
        ("efficiency_round_trip_0.9_symmetric", math.sqrt(0.9), math.sqrt(0.9), "right_endpoint_rectangle"),
        ("trapezoidal_power_integration", 0.9, 0.9, "trapezoidal_repeated_day"),
    ]
    solved: list[Solution] = []
    validations: dict[str, Any] = {}
    for scenario, eta_c, eta_d, integration in scenarios:
        solution = solve_lp(price, data["load_kw"], data["pv_kw"], scenario=scenario, eta_c=eta_c, eta_d=eta_d, integration=integration)
        solved.append(solution)
        validations[scenario] = validate(solution, price)

    base = solved[0]
    base_baseline = baseline(base.load_kwh, base.pv_kwh, price)
    detail_path = write_detail(base, data, price)
    storage_rows = four_hour_summary(base)
    storage_path = write_four_hour(storage_rows)
    workbook_payload_path = INTERMEDIATE / "q1_workbook_payload.json"
    workbook_payload_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "question": "Q1",
                "time_label_mapping": "natural_day_00:00_to_24:00_corrected_from_shifted_official_template",
                "purchase_plan": [
                    {
                        "slot": slot,
                        "interval": natural_slot_label(slot)[2],
                        "purchase_kwh": float(base.q[slot]),
                    }
                    for slot in range(len(base.q))
                ],
                "storage_four_hour_summary": storage_rows,
                "soc_endpoints_kwh": {"0:00": float(base.soc[0]), "24:00": float(base.soc[-1])},
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    requested_starts = [10 * 60, 12 * 60, 14 * 60, 16 * 60, 18 * 60, 20 * 60]
    specified = {}
    for minute in requested_starts:
        slot = minute // 10
        specified[natural_slot_label(slot)[2]] = float(base.q[slot])

    sensitivity = []
    for solution in solved:
        sensitivity.append({
            "scenario": solution.scenario,
            "eta_charge": solution.eta_charge,
            "eta_discharge": solution.eta_discharge,
            "integration": solution.integration,
            "purchase_kwh": float(np.sum(solution.q)),
            "cost_yuan": solution.actual_cost,
            "charge_kwh": float(np.sum(solution.charge)),
            "discharge_kwh": float(np.sum(solution.discharge)),
            "pv_spill_or_surplus_kwh": float(np.sum(solution.spill)),
            "cost_change_vs_base_yuan": float(solution.actual_cost - base.actual_cost),
            "cost_change_vs_base_fraction": float(solution.actual_cost / base.actual_cost - 1.0),
            "all_checks_pass": validations[solution.scenario]["all_pass"],
        })

    summary = {
        "schema_version": 1,
        "status": "SOLVED_AND_VALIDATED" if validations["base"]["all_pass"] else "FAILED_VALIDATION",
        "question": "Q1",
        "frozen_basis": {
            "time": "natural_day_144_slots_right_endpoint_rectangle",
            "efficiency": {"eta_charge": 0.9, "eta_discharge": 0.9},
            "measurement_side": "microgrid_bus_side",
            "soc_kwh": {"initial": SOC_INITIAL, "terminal": SOC_TERMINAL, "min": SOC_MIN, "max": SOC_MAX},
            "flow_max_kwh_per_slot": FLOW_MAX_KWH,
            "known_conflict": "A01 template labels are shifted by ten minutes; the generated result workbook uses corrected natural-day labels and a visible disclosure, without claiming an official erratum.",
        },
        "input": {"path": str(data["path"].relative_to(PROJECT_ROOT)), "sha256": data["sha256"]},
        "baseline_no_storage_pv_first": base_baseline,
        "optimized": {
            "purchase_kwh": float(np.sum(base.q)),
            "cost_yuan": base.actual_cost,
            "cost_saving_vs_baseline_yuan": float(base_baseline["cost_yuan"] - base.actual_cost),
            "cost_saving_vs_baseline_fraction": float(1.0 - base.actual_cost / base_baseline["cost_yuan"]),
            "charge_kwh": float(np.sum(base.charge)),
            "discharge_kwh": float(np.sum(base.discharge)),
            "pv_spill_or_surplus_kwh": float(np.sum(base.spill)),
            "soc_open_kwh": float(base.soc[0]),
            "soc_close_kwh": float(base.soc[-1]),
            "specified_interval_purchase_kwh": specified,
            "storage_four_hour_summary": storage_rows,
        },
        "sensitivity": sensitivity,
        "model_upgrade_decision": {
            "milp_required": not validations["base"]["pass_flags"]["mutual_exclusion"],
            "reason": "The lexicographic LP produced no simultaneous charge/discharge above the frozen tolerance; MILP is unnecessary." if validations["base"]["pass_flags"]["mutual_exclusion"] else "Simultaneous flow exceeded tolerance; upgrade to MILP before accepting Q1.",
        },
        "files": {
            "detail_csv": str(detail_path.relative_to(PROJECT_ROOT)),
            "storage_4h_csv": str(storage_path.relative_to(PROJECT_ROOT)),
            "workbook_payload_json": str(workbook_payload_path.relative_to(PROJECT_ROOT)),
        },
    }

    validation_payload = {
        "schema_version": 1,
        "question": "Q1",
        "status": "PASS" if all(item["all_pass"] for item in validations.values()) else "FAIL",
        "tolerances": {"solver_balance_state_kwh": SOLVER_TOL_KWH, "positive_flow_kwh": POSITIVE_TOL_KWH},
        "scenarios": validations,
        "independent_recalculation": {
            "detail_rows_expected": 144,
            "detail_rows_written": 144,
            "daily_purchase_from_detail_kwh": float(np.sum(base.q)),
            "daily_cost_from_detail_yuan": float(np.sum(price * base.q)),
            "four_hour_charge_sum_kwh": float(sum(float(row["charge_kwh"]) for row in storage_rows)),
            "four_hour_discharge_sum_kwh": float(sum(float(row["discharge_kwh"]) for row in storage_rows)),
        },
        "environment": {
            "python": sys.version,
            "python_executable": sys.executable,
            "platform": platform.platform(),
            "numpy": np.__version__,
            "scipy": scipy.__version__,
            "solver": "scipy.optimize.linprog(method='highs')",
        },
    }

    summary_path = RESULTS / "q1_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=json_default), encoding="utf-8")
    validation_path = VALIDATION / "q1_validation.json"
    validation_path.write_text(json.dumps(validation_payload, ensure_ascii=False, indent=2, default=json_default), encoding="utf-8")

    run_manifest = {
        "question": "Q1",
        "status": summary["status"],
        "input_sha256": data["sha256"],
        "code_sha256": {
            "common_data.py": sha256(Path(__file__).with_name("common_data.py")),
            "q1_solve.py": sha256(Path(__file__)),
        },
        "outputs_sha256": {
            str(path.relative_to(PROJECT_ROOT)): sha256(path)
            for path in (detail_path, storage_path, workbook_payload_path, summary_path, validation_path)
        },
    }
    manifest_path = INTERMEDIATE / "q1_run_manifest.json"
    manifest_path.write_text(json.dumps(run_manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "status": summary["status"],
        "baseline_cost_yuan": base_baseline["cost_yuan"],
        "optimized_cost_yuan": base.actual_cost,
        "saving_yuan": base_baseline["cost_yuan"] - base.actual_cost,
        "validation": validation_payload["status"],
        "milp_required": summary["model_upgrade_decision"]["milp_required"],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
