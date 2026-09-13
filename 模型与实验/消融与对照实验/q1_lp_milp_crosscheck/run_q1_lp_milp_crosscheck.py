from __future__ import annotations

import csv
import hashlib
import json
import platform
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import scipy
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import coo_matrix, hstack, vstack


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CODE_DIR = PROJECT_ROOT / "code"
if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))

from common_data import load_attachment1, natural_slot_label  # noqa: E402
from q1_solve import (  # noqa: E402
    FLOW_MAX_KWH,
    N,
    POSITIVE_TOL_KWH,
    SOC_INITIAL,
    SOC_MAX,
    SOC_MIN,
    SOC_TERMINAL,
    SOLVER_TOL_KWH,
    build_equalities,
    energy_from_power,
    solve_lp,
    validate,
    variable_slices,
)


EXPERIMENT_ROOT = Path(__file__).resolve().parent
RESULTS_DIR = EXPERIMENT_ROOT / "results"
VALIDATION_DIR = EXPERIMENT_ROOT / "validation"
ETA_C = 0.9
ETA_D = 0.9
INTEGRATION = "right_endpoint_rectangle"
TRAJECTORY_TOL_KWH = 1e-6
OBJECTIVE_TOL_YUAN = 1e-5

PROTECTED_FILES = [
    PROJECT_ROOT / "results" / "result1.xlsx",
    PROJECT_ROOT / "results" / "q1_detail.csv",
    PROJECT_ROOT / "results" / "q1_summary.json",
    PROJECT_ROOT / "validation" / "q1_validation.json",
    PROJECT_ROOT / "validation" / "q1_independent_recompute.json",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def json_default(value: Any):
    if isinstance(value, np.generic):
        return value.item()
    raise TypeError(type(value).__name__)


def load_frozen_detail() -> dict[str, np.ndarray]:
    path = PROJECT_ROOT / "results" / "q1_detail.csv"
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if len(rows) != N:
        raise ValueError(f"冻结 Q1 底账应为 {N} 行，实际为 {len(rows)}")
    return {
        "q": np.asarray([float(row["normal_purchase_kwh"]) for row in rows]),
        "charge": np.asarray([float(row["charge_bus_kwh"]) for row in rows]),
        "discharge": np.asarray([float(row["discharge_bus_kwh"]) for row in rows]),
        "spill": np.asarray([float(row["pv_spill_or_surplus_kwh"]) for row in rows]),
        "soc_open": np.asarray([float(row["soc_open_kwh"]) for row in rows]),
        "soc_close": np.asarray([float(row["soc_close_kwh"]) for row in rows]),
    }


def build_milp_matrices(load_kwh: np.ndarray, pv_kwh: np.ndarray):
    # Continuous variables retain the formal Q1 order [q,c,r,w,S]; z is appended.
    a_eq_cont, b_eq = build_equalities(load_kwh, pv_kwh, ETA_C, ETA_D)
    a_eq = hstack([a_eq_cont, coo_matrix((2 * N, N))], format="csr")
    idx = variable_slices()
    total = 6 * N + 1

    rows: list[int] = []
    cols: list[int] = []
    values: list[float] = []
    ub = np.zeros(2 * N, dtype=float)
    z_start = 5 * N + 1
    for t in range(N):
        # c_t <= M z_t
        rows.extend([t, t])
        cols.extend([idx["charge"].start + t, z_start + t])
        values.extend([1.0, -FLOW_MAX_KWH])
        ub[t] = 0.0
        # r_t <= M(1-z_t), i.e. r_t + M z_t <= M
        row = N + t
        rows.extend([row, row])
        cols.extend([idx["discharge"].start + t, z_start + t])
        values.extend([1.0, FLOW_MAX_KWH])
        ub[row] = FLOW_MAX_KWH
    a_mutex = coo_matrix((values, (rows, cols)), shape=(2 * N, total)).tocsr()
    return a_eq, b_eq, a_mutex, ub


def solve_q1_milp(price: np.ndarray, load_kw: np.ndarray, pv_kw: np.ndarray) -> dict[str, Any]:
    load_kwh = energy_from_power(load_kw, INTEGRATION)
    pv_kwh = energy_from_power(pv_kw, INTEGRATION)
    idx = variable_slices()
    total = 6 * N + 1
    z_start = 5 * N + 1
    a_eq, b_eq, a_mutex, mutex_ub = build_milp_matrices(load_kwh, pv_kwh)

    lb = np.zeros(total, dtype=float)
    ub = np.full(total, np.inf, dtype=float)
    ub[idx["charge"]] = FLOW_MAX_KWH
    ub[idx["discharge"]] = FLOW_MAX_KWH
    lb[idx["soc"]] = SOC_MIN
    ub[idx["soc"]] = SOC_MAX
    lb[idx["soc"].start] = ub[idx["soc"].start] = SOC_INITIAL
    lb[idx["soc"].stop - 1] = ub[idx["soc"].stop - 1] = SOC_TERMINAL
    ub[z_start:] = 1.0
    bounds = Bounds(lb, ub)

    integrality = np.zeros(total, dtype=int)
    integrality[z_start:] = 1
    cost_objective = np.zeros(total, dtype=float)
    cost_objective[idx["q"]] = price
    throughput_objective = np.zeros(total, dtype=float)
    throughput_objective[idx["charge"]] = 1.0
    throughput_objective[idx["discharge"]] = 1.0
    base_constraints = [
        LinearConstraint(a_eq, b_eq, b_eq),
        LinearConstraint(a_mutex, np.full(2 * N, -np.inf), mutex_ub),
    ]
    options = {"disp": False, "presolve": True, "mip_rel_gap": 0.0}

    start = time.perf_counter()
    primary = milp(
        cost_objective,
        integrality=integrality,
        bounds=bounds,
        constraints=base_constraints,
        options=options,
    )
    primary_seconds = time.perf_counter() - start
    if not primary.success:
        raise RuntimeError(f"Q1 MILP 第一阶段失败: {primary.status} {primary.message}")

    cost_tolerance = max(1e-7, abs(float(primary.fun)) * 1e-11)
    cost_row = coo_matrix(cost_objective.reshape(1, -1)).tocsr()
    secondary_constraints = base_constraints + [
        LinearConstraint(cost_row, np.asarray([-np.inf]), np.asarray([float(primary.fun) + cost_tolerance]))
    ]
    start = time.perf_counter()
    secondary = milp(
        throughput_objective,
        integrality=integrality,
        bounds=bounds,
        constraints=secondary_constraints,
        options=options,
    )
    secondary_seconds = time.perf_counter() - start
    if not secondary.success:
        raise RuntimeError(f"Q1 MILP 第二阶段失败: {secondary.status} {secondary.message}")

    x = np.asarray(secondary.x, dtype=float)
    x[np.abs(x) < 1e-10] = 0.0
    return {
        "q": x[idx["q"]],
        "charge": x[idx["charge"]],
        "discharge": x[idx["discharge"]],
        "spill": x[idx["spill"]],
        "soc": x[idx["soc"]],
        "z": x[z_start:],
        "load_kwh": load_kwh,
        "pv_kwh": pv_kwh,
        "primary_optimum": float(primary.fun),
        "secondary_cost": float(np.dot(price, x[idx["q"]])),
        "throughput": float(np.sum(x[idx["charge"]] + x[idx["discharge"]])),
        "cost_tolerance": cost_tolerance,
        "solve_time_primary_seconds": primary_seconds,
        "solve_time_secondary_seconds": secondary_seconds,
        "solve_time_total_seconds": primary_seconds + secondary_seconds,
        "primary_status": int(primary.status),
        "primary_message": str(primary.message),
        "secondary_status": int(secondary.status),
        "secondary_message": str(secondary.message),
        "primary_mip_gap": float(getattr(primary, "mip_gap", np.nan)),
        "secondary_mip_gap": float(getattr(secondary, "mip_gap", np.nan)),
    }


def validate_milp(solution: dict[str, Any], price: np.ndarray) -> dict[str, Any]:
    balance = (
        solution["q"] + solution["pv_kwh"] + solution["discharge"]
        - solution["load_kwh"] - solution["charge"] - solution["spill"]
    )
    state = (
        solution["soc"][1:] - solution["soc"][:-1]
        - ETA_C * solution["charge"] + solution["discharge"] / ETA_D
    )
    z = solution["z"]
    violations = {
        "balance_max_abs_kwh": float(np.max(np.abs(balance))),
        "state_max_abs_kwh": float(np.max(np.abs(state))),
        "charge_mutex_max_violation_kwh": float(np.max(np.maximum(solution["charge"] - FLOW_MAX_KWH * z, 0.0))),
        "discharge_mutex_max_violation_kwh": float(np.max(np.maximum(solution["discharge"] - FLOW_MAX_KWH * (1.0 - z), 0.0))),
        "binary_integrality_max_abs": float(np.max(np.abs(z - np.rint(z)))),
        "soc_lower_max_violation_kwh": float(np.max(np.maximum(SOC_MIN - solution["soc"], 0.0))),
        "soc_upper_max_violation_kwh": float(np.max(np.maximum(solution["soc"] - SOC_MAX, 0.0))),
        "charge_upper_max_violation_kwh": float(np.max(np.maximum(solution["charge"] - FLOW_MAX_KWH, 0.0))),
        "discharge_upper_max_violation_kwh": float(np.max(np.maximum(solution["discharge"] - FLOW_MAX_KWH, 0.0))),
        "nonnegative_max_violation_kwh": float(max(0.0, -np.min(np.concatenate([solution["q"], solution["charge"], solution["discharge"], solution["spill"]])))),
        "soc_initial_abs_kwh": float(abs(solution["soc"][0] - SOC_INITIAL)),
        "soc_terminal_abs_kwh": float(abs(solution["soc"][-1] - SOC_TERMINAL)),
        "cost_recompute_abs_yuan": float(abs(np.dot(price, solution["q"]) - solution["secondary_cost"])),
    }
    simultaneous = np.minimum(solution["charge"], solution["discharge"])
    metrics = {
        **violations,
        "simultaneous_positive_slot_count": int(np.sum(simultaneous > POSITIVE_TOL_KWH)),
        "simultaneous_max_kwh": float(np.max(simultaneous)),
        "soc_min_kwh": float(np.min(solution["soc"])),
        "soc_max_kwh": float(np.max(solution["soc"])),
        "charge_max_kwh_per_slot": float(np.max(solution["charge"])),
        "discharge_max_kwh_per_slot": float(np.max(solution["discharge"])),
    }
    residual_keys = [
        "balance_max_abs_kwh", "state_max_abs_kwh", "charge_mutex_max_violation_kwh",
        "discharge_mutex_max_violation_kwh", "soc_lower_max_violation_kwh",
        "soc_upper_max_violation_kwh", "charge_upper_max_violation_kwh",
        "discharge_upper_max_violation_kwh", "nonnegative_max_violation_kwh",
        "soc_initial_abs_kwh", "soc_terminal_abs_kwh",
    ]
    metrics["maximum_constraint_residual_kwh"] = float(max(metrics[key] for key in residual_keys))
    pass_flags = {
        "equalities": metrics["balance_max_abs_kwh"] <= SOLVER_TOL_KWH and metrics["state_max_abs_kwh"] <= SOLVER_TOL_KWH,
        "bounds": max(metrics[key] for key in residual_keys[2:]) <= SOLVER_TOL_KWH,
        "binary_integrality": metrics["binary_integrality_max_abs"] <= 1e-8,
        "mutual_exclusion": metrics["simultaneous_positive_slot_count"] == 0,
        "cost_recompute": metrics["cost_recompute_abs_yuan"] <= 1e-6,
    }
    return {"metrics": metrics, "pass_flags": pass_flags, "all_pass": all(pass_flags.values())}


def max_abs(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.max(np.abs(a - b)))


def write_trajectory_csv(lp: Any, milp_solution: dict[str, Any], frozen: dict[str, np.ndarray]) -> Path:
    path = RESULTS_DIR / "q1_lp_milp_trajectory.csv"
    fields = [
        "slot", "interval", "lp_purchase_kwh", "milp_purchase_kwh",
        "lp_charge_kwh", "milp_charge_kwh", "lp_discharge_kwh", "milp_discharge_kwh",
        "lp_spill_kwh", "milp_spill_kwh",
        "lp_soc_close_kwh", "milp_soc_close_kwh", "milp_z",
        "frozen_lp_purchase_kwh", "frozen_lp_charge_kwh", "frozen_lp_discharge_kwh",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for t in range(N):
            writer.writerow({
                "slot": t + 1,
                "interval": natural_slot_label(t)[2],
                "lp_purchase_kwh": f"{lp.q[t]:.12f}",
                "milp_purchase_kwh": f"{milp_solution['q'][t]:.12f}",
                "lp_charge_kwh": f"{lp.charge[t]:.12f}",
                "milp_charge_kwh": f"{milp_solution['charge'][t]:.12f}",
                "lp_discharge_kwh": f"{lp.discharge[t]:.12f}",
                "milp_discharge_kwh": f"{milp_solution['discharge'][t]:.12f}",
                "lp_spill_kwh": f"{lp.spill[t]:.12f}",
                "milp_spill_kwh": f"{milp_solution['spill'][t]:.12f}",
                "lp_soc_close_kwh": f"{lp.soc[t + 1]:.12f}",
                "milp_soc_close_kwh": f"{milp_solution['soc'][t + 1]:.12f}",
                "milp_z": f"{milp_solution['z'][t]:.0f}",
                "frozen_lp_purchase_kwh": f"{frozen['q'][t]:.12f}",
                "frozen_lp_charge_kwh": f"{frozen['charge'][t]:.12f}",
                "frozen_lp_discharge_kwh": f"{frozen['discharge'][t]:.12f}",
            })
    return path


def main() -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    VALIDATION_DIR.mkdir(parents=True, exist_ok=True)
    protected_before = {str(path.relative_to(PROJECT_ROOT)): sha256(path) for path in PROTECTED_FILES}
    data = load_attachment1()
    price = data["price_yuan_per_kwh"]
    frozen = load_frozen_detail()

    start = time.perf_counter()
    lp = solve_lp(
        price,
        data["load_kw"],
        data["pv_kw"],
        scenario="q1_lp_crosscheck",
        eta_c=ETA_C,
        eta_d=ETA_D,
        integration=INTEGRATION,
    )
    lp_seconds = time.perf_counter() - start
    lp_validation = validate(lp, price)
    milp_solution = solve_q1_milp(price, data["load_kw"], data["pv_kw"])
    milp_validation = validate_milp(milp_solution, price)

    lp_throughput = float(np.sum(lp.charge + lp.discharge))
    objective_diff = float(milp_solution["primary_optimum"] - lp.primary_optimum)
    secondary_cost_diff = float(milp_solution["secondary_cost"] - lp.actual_cost)
    throughput_diff = float(milp_solution["throughput"] - lp_throughput)
    trajectory = {
        "lp_resolve_vs_frozen_max_abs": {
            "purchase_kwh": max_abs(lp.q, frozen["q"]),
            "charge_kwh": max_abs(lp.charge, frozen["charge"]),
            "discharge_kwh": max_abs(lp.discharge, frozen["discharge"]),
            "soc_close_kwh": max_abs(lp.soc[1:], frozen["soc_close"]),
        },
        "milp_vs_frozen_lp_max_abs": {
            "purchase_kwh": max_abs(milp_solution["q"], frozen["q"]),
            "charge_kwh": max_abs(milp_solution["charge"], frozen["charge"]),
            "discharge_kwh": max_abs(milp_solution["discharge"], frozen["discharge"]),
            "soc_close_kwh": max_abs(milp_solution["soc"][1:], frozen["soc_close"]),
        },
        "milp_vs_lp_resolve_max_abs": {
            "purchase_kwh": max_abs(milp_solution["q"], lp.q),
            "charge_kwh": max_abs(milp_solution["charge"], lp.charge),
            "discharge_kwh": max_abs(milp_solution["discharge"], lp.discharge),
            "soc_close_kwh": max_abs(milp_solution["soc"][1:], lp.soc[1:]),
        },
    }
    trajectory["lp_resolve_reproduces_frozen_within_tolerance"] = all(
        value <= TRAJECTORY_TOL_KWH for value in trajectory["lp_resolve_vs_frozen_max_abs"].values()
    )
    trajectory["milp_trajectory_matches_frozen_lp_within_tolerance"] = all(
        value <= TRAJECTORY_TOL_KWH for value in trajectory["milp_vs_frozen_lp_max_abs"].values()
    )

    equivalence_pass = bool(
        lp_validation["all_pass"]
        and lp_validation["pass_flags"]["mutual_exclusion"]
        and milp_validation["all_pass"]
        and abs(objective_diff) <= OBJECTIVE_TOL_YUAN
        and abs(secondary_cost_diff) <= OBJECTIVE_TOL_YUAN
        and abs(throughput_diff) <= TRAJECTORY_TOL_KWH
    )
    trajectory_path = write_trajectory_csv(lp, milp_solution, frozen)
    protected_after = {str(path.relative_to(PROJECT_ROOT)): sha256(path) for path in PROTECTED_FILES}

    summary = {
        "schema_version": 1,
        "experiment": "Q1 LP-MILP mutual-exclusion cross-validation",
        "status": "PASS_EQUIVALENT_OPTIMUM" if equivalence_pass else "DIFFERENCE_REQUIRES_REPORT",
        "scope": "isolated validation only; frozen Q1 MAIN and formal outputs are not replaced",
        "only_change_in_milp": "binary z_t and explicit c_t <= (5000/6)z_t, r_t <= (5000/6)(1-z_t)",
        "held_constant": {
            "input_sha256": data["sha256"],
            "slots": N,
            "integration": INTEGRATION,
            "eta_charge": ETA_C,
            "eta_discharge": ETA_D,
            "soc_min_kwh": SOC_MIN,
            "soc_max_kwh": SOC_MAX,
            "soc_initial_kwh": SOC_INITIAL,
            "soc_terminal_kwh": SOC_TERMINAL,
            "charge_discharge_limit_kwh_per_slot": FLOW_MAX_KWH,
            "lexicographic_structure": "stage 1 minimum purchase cost; stage 2 minimum c+r within the same cost tolerance",
        },
        "comparison": {
            "lp": {
                "primary_minimum_cost_yuan": lp.primary_optimum,
                "secondary_solution_cost_yuan": lp.actual_cost,
                "daily_purchase_kwh": float(np.sum(lp.q)),
                "charge_kwh": float(np.sum(lp.charge)),
                "discharge_kwh": float(np.sum(lp.discharge)),
                "throughput_kwh": lp_throughput,
                "simultaneous_positive_slot_count": lp_validation["metrics"]["simultaneous_positive_slot_count"],
                "maximum_constraint_residual_kwh": float(max(lp_validation["metrics"]["balance_max_abs_kwh"], lp_validation["metrics"]["state_max_abs_kwh"])),
                "solve_time_total_seconds": lp_seconds,
            },
            "milp": {
                "primary_minimum_cost_yuan": milp_solution["primary_optimum"],
                "secondary_solution_cost_yuan": milp_solution["secondary_cost"],
                "daily_purchase_kwh": float(np.sum(milp_solution["q"])),
                "charge_kwh": float(np.sum(milp_solution["charge"])),
                "discharge_kwh": float(np.sum(milp_solution["discharge"])),
                "throughput_kwh": milp_solution["throughput"],
                "simultaneous_positive_slot_count": milp_validation["metrics"]["simultaneous_positive_slot_count"],
                "maximum_constraint_residual_kwh": milp_validation["metrics"]["maximum_constraint_residual_kwh"],
                "solve_time_primary_seconds": milp_solution["solve_time_primary_seconds"],
                "solve_time_secondary_seconds": milp_solution["solve_time_secondary_seconds"],
                "solve_time_total_seconds": milp_solution["solve_time_total_seconds"],
                "primary_mip_gap": milp_solution["primary_mip_gap"],
                "secondary_mip_gap": milp_solution["secondary_mip_gap"],
            },
            "milp_minus_lp": {
                "primary_minimum_cost_yuan": objective_diff,
                "secondary_solution_cost_yuan": secondary_cost_diff,
                "daily_purchase_kwh": float(np.sum(milp_solution["q"]) - np.sum(lp.q)),
                "throughput_kwh": throughput_diff,
                "solve_time_total_seconds": float(milp_solution["solve_time_total_seconds"] - lp_seconds),
            },
        },
        "trajectory_check": trajectory,
        "conclusion": (
            "The frozen LP solution is already mutually exclusive and the explicit MILP has the same lexicographic objective values; "
            "the binary constraint does not change the Q1 optimum."
            if equivalence_pass
            else "At least one equivalence gate failed; retain the frozen LP and report the measured difference without retuning."
        ),
        "files": {"trajectory_csv": str(trajectory_path.relative_to(PROJECT_ROOT))},
    }
    summary_path = RESULTS_DIR / "q1_lp_milp_crosscheck_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=json_default), encoding="utf-8")

    validation_payload = {
        "schema_version": 1,
        "experiment": summary["experiment"],
        "status": "PASS" if equivalence_pass and protected_before == protected_after else "FAIL",
        "tolerances": {
            "constraint_kwh": SOLVER_TOL_KWH,
            "positive_flow_kwh": POSITIVE_TOL_KWH,
            "objective_yuan": OBJECTIVE_TOL_YUAN,
            "trajectory_kwh": TRAJECTORY_TOL_KWH,
        },
        "lp_validation": lp_validation,
        "milp_validation": milp_validation,
        "equivalence_gates": {
            "frozen_lp_has_no_simultaneous_charge_discharge": lp_validation["pass_flags"]["mutual_exclusion"],
            "lp_all_constraints_pass": lp_validation["all_pass"],
            "milp_all_constraints_pass": milp_validation["all_pass"],
            "primary_cost_equal_within_tolerance": abs(objective_diff) <= OBJECTIVE_TOL_YUAN,
            "secondary_cost_equal_within_tolerance": abs(secondary_cost_diff) <= OBJECTIVE_TOL_YUAN,
            "throughput_equal_within_tolerance": abs(throughput_diff) <= TRAJECTORY_TOL_KWH,
            "lp_resolve_matches_frozen_trajectory": trajectory["lp_resolve_reproduces_frozen_within_tolerance"],
            "milp_matches_frozen_trajectory": trajectory["milp_trajectory_matches_frozen_lp_within_tolerance"],
            "protected_formal_files_unchanged": protected_before == protected_after,
        },
        "interpretation": {
            "objective_equivalence_pass": equivalence_pass,
            "trajectory_gate_is_diagnostic_not_required_for_optimality": True,
            "reason": "Multiple slot-level trajectories may share the same cost and throughput; objective equivalence plus LP feasibility under explicit mutual exclusion proves that the binary restriction does not improve or worsen the optimum.",
        },
        "protected_sha256_before": protected_before,
        "protected_sha256_after": protected_after,
        "environment": {
            "python": sys.version,
            "python_executable": sys.executable,
            "platform": platform.platform(),
            "numpy": np.__version__,
            "scipy": scipy.__version__,
            "lp_solver": "scipy.optimize.linprog(method='highs')",
            "milp_solver": "scipy.optimize.milp(HiGHS), mip_rel_gap=0",
        },
    }
    validation_path = VALIDATION_DIR / "q1_lp_milp_crosscheck_validation.json"
    validation_path.write_text(json.dumps(validation_payload, ensure_ascii=False, indent=2, default=json_default), encoding="utf-8")

    manifest = {
        "schema_version": 1,
        "status": validation_payload["status"],
        "input_sha256": data["sha256"],
        "code_sha256": sha256(Path(__file__)),
        "outputs_sha256": {
            str(path.relative_to(PROJECT_ROOT)): sha256(path)
            for path in (summary_path, trajectory_path, validation_path)
        },
        "protected_formal_files_unchanged": protected_before == protected_after,
    }
    manifest_path = EXPERIMENT_ROOT / "q1_lp_milp_crosscheck_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "status": validation_payload["status"],
        "equivalence": equivalence_pass,
        "lp": summary["comparison"]["lp"],
        "milp": summary["comparison"]["milp"],
        "differences": summary["comparison"]["milp_minus_lp"],
        "trajectory": trajectory,
        "protected_formal_files_unchanged": protected_before == protected_after,
    }, ensure_ascii=False, indent=2, default=json_default))


if __name__ == "__main__":
    main()
