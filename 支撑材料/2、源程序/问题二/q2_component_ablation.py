from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from scipy.optimize import linprog
from scipy.sparse import coo_matrix

from common_data import PROJECT_ROOT, load_attachment1, load_attachment2, sha256
from dispatch_core import (
    ETA_CHARGE,
    ETA_DISCHARGE,
    FLOW_MAX_KWH,
    POSITIVE_TOL_KWH,
    SOC_INITIAL,
    SOC_MAX,
    SOC_MIN,
    SOLVER_TOL_KWH,
    execute_fixed_plan,
    solve_deterministic_plan,
    _equalities,
    _slices,
)
import q2_solve as q2


RESULTS = PROJECT_ROOT / "results"
VALIDATION = PROJECT_ROOT / "validation"
INTERMEDIATE = PROJECT_ROOT / "intermediate"
EVAL_START = 31
N = 144
PRICE_MULTIPLIER = 5.0
QUANTILE_GRID = (0.7, 0.8, 0.9)


@dataclass
class FlexiblePlan:
    q: np.ndarray
    terminal_soc: float
    balance_residual: float
    state_residual: float
    simultaneous_slots: int


def max_abs(values: np.ndarray) -> float:
    return float(np.max(np.abs(values))) if values.size else 0.0


def solve_with_terminal_value(
    net_load_kwh: np.ndarray,
    price: np.ndarray,
    soc_initial: float,
    terminal_value_yuan_per_kwh_soc: float,
) -> FlexiblePlan:
    net = np.asarray(net_load_kwh, dtype=float)
    price = np.asarray(price, dtype=float)
    n = len(net)
    idx = _slices(n)
    a_eq, b_eq = _equalities(net)
    objective = np.zeros(5 * n + 1, dtype=float)
    objective[idx["q"]] = price
    objective[idx["soc"].stop - 1] = -float(terminal_value_yuan_per_kwh_soc)
    bounds: list[tuple[float | None, float | None]] = []
    bounds.extend([(0.0, None)] * n)
    bounds.extend([(0.0, FLOW_MAX_KWH)] * n)
    bounds.extend([(0.0, FLOW_MAX_KWH)] * n)
    bounds.extend([(0.0, None)] * n)
    bounds.append((soc_initial, soc_initial))
    bounds.extend([(SOC_MIN, SOC_MAX)] * n)
    primary = linprog(objective, A_eq=a_eq, b_eq=b_eq, bounds=bounds, method="highs")
    if not primary.success:
        raise RuntimeError(f"期末价值LP失败: {primary.status} {primary.message}")
    x = np.asarray(primary.x, dtype=float)
    simultaneous = np.minimum(x[idx["charge"]], x[idx["discharge"]])
    if np.any(simultaneous > POSITIVE_TOL_KWH):
        secondary_objective = np.zeros_like(objective)
        secondary_objective[idx["charge"]] = 1.0
        secondary_objective[idx["discharge"]] = 1.0
        tol = max(1e-7, abs(float(primary.fun)) * 1e-11)
        secondary = linprog(
            secondary_objective,
            A_ub=coo_matrix(objective.reshape(1, -1)).tocsr(),
            b_ub=np.asarray([float(primary.fun) + tol]),
            A_eq=a_eq,
            b_eq=b_eq,
            bounds=bounds,
            method="highs",
        )
        if not secondary.success:
            raise RuntimeError(f"期末价值二级LP失败: {secondary.status} {secondary.message}")
        x = np.asarray(secondary.x, dtype=float)
    x[np.abs(x) < 1e-10] = 0.0
    q = x[idx["q"]]
    charge = x[idx["charge"]]
    discharge = x[idx["discharge"]]
    spill = x[idx["spill"]]
    soc = x[idx["soc"]]
    return FlexiblePlan(
        q=q,
        terminal_soc=float(soc[-1]),
        balance_residual=max_abs(q + discharge - net - charge - spill),
        state_residual=max_abs(soc[1:] - soc[:-1] - ETA_CHARGE * charge + discharge / ETA_DISCHARGE),
        simultaneous_slots=int(np.sum(np.minimum(charge, discharge) > POSITIVE_TOL_KWH)),
    )


def residual_uplift(
    actual_net: np.ndarray,
    point_net: np.ndarray,
    day_idx: int,
    quantile: float,
    window_days: int,
) -> np.ndarray:
    start = max(1, day_idx - window_days)
    valid = np.arange(start, day_idx, dtype=int)
    valid = valid[np.isfinite(point_net[valid]).all(axis=1)]
    if len(valid) == 0:
        raise ValueError(f"{day_idx=}无历史残差")
    return np.quantile(actual_net[valid] - point_net[valid], quantile, axis=0)


def build_proxy_losses(
    actual_net: np.ndarray,
    point_net: np.ndarray,
    price: np.ndarray,
    residual_window: int,
) -> dict[float, np.ndarray]:
    losses = {quantile: np.full(len(actual_net), np.nan) for quantile in QUANTILE_GRID}
    for idx in range(2, len(actual_net)):
        for quantile in QUANTILE_GRID:
            uplift = residual_uplift(actual_net, point_net, idx, quantile, residual_window)
            target = point_net[idx] + uplift
            plan_proxy = np.maximum(target, 0.0) / 6.0
            emergency_proxy = np.maximum(actual_net[idx] - target, 0.0) / 6.0
            losses[quantile][idx] = float(np.dot(price, plan_proxy) + PRICE_MULTIPLIER * np.dot(price, emergency_proxy))
    return losses


def select_dynamic_quantile(losses: dict[float, np.ndarray], day_idx: int) -> tuple[float, int, int]:
    left = max(2, day_idx - 28)
    right = day_idx
    scores = {
        quantile: float(np.nanmean(values[left:right]))
        for quantile, values in losses.items()
    }
    selected = min(QUANTILE_GRID, key=lambda qv: (scores[qv], abs(qv - 0.8), qv))
    return selected, left, right - 1


def plan_for_day(
    *,
    kind: str,
    day_idx: int,
    point_net_cache: np.ndarray,
    actual_net: np.ndarray,
    load_kw: np.ndarray,
    pv_kw: np.ndarray,
    dates: list,
    price: np.ndarray,
    soc: float,
    risk_mode: str,
    residual_window: int,
    proxy_losses: dict[float, np.ndarray] | None,
    terminal_value: bool,
    horizon_days: int,
) -> tuple[np.ndarray, float | None, np.ndarray, int, int, float, float, int]:
    forecast_load, forecast_pv = q2.forecast_two_days(kind, load_kw, pv_kw, dates, day_idx)
    point_2d = forecast_load - forecast_pv
    selected_q: float | None = None
    history_left = day_idx - 1
    history_right = day_idx - 1
    uplift = np.zeros(N)
    if risk_mode == "fixed_q80":
        selected_q = 0.8
    elif risk_mode == "dynamic":
        if proxy_losses is None:
            raise ValueError("动态风险需要费用代理历史")
        selected_q, history_left, history_right = select_dynamic_quantile(proxy_losses, day_idx)
    elif risk_mode != "none":
        raise ValueError(risk_mode)
    if selected_q is not None:
        uplift = residual_uplift(actual_net, point_net_cache, day_idx, selected_q, residual_window)
    slots = N * horizon_days
    net_kwh = (point_2d[:horizon_days] + np.tile(uplift, (horizon_days, 1))).reshape(-1) / 6.0
    plan_price = np.tile(price, horizon_days)
    if terminal_value:
        # One kWh of terminal SOC can replace eta_d kWh of next-period normal purchase.
        salvage = float(np.mean(price) * ETA_DISCHARGE)
        solution = solve_with_terminal_value(net_kwh, plan_price, soc, salvage)
        return solution.q[:N], selected_q, uplift, history_left, history_right, solution.balance_residual, solution.state_residual, solution.simultaneous_slots
    solution = solve_deterministic_plan(net_kwh, plan_price, soc, SOC_INITIAL)
    return solution.q[:N], selected_q, uplift, history_left, history_right, solution.balance_max_abs_kwh, solution.state_max_abs_kwh, solution.simultaneous_positive_slots


def run_strategy(
    *,
    name: str,
    forecast_kind: str,
    risk_mode: str,
    residual_window: int,
    terminal_value: bool,
    horizon_days: int,
    load_kw: np.ndarray,
    pv_kw: np.ndarray,
    dates: list,
    price: np.ndarray,
    actual_net: np.ndarray,
    point_net_cache: np.ndarray,
    proxy_losses: dict[float, np.ndarray] | None,
) -> dict[str, Any]:
    soc = SOC_INITIAL
    detail: list[dict[str, Any]] = []
    daily: list[dict[str, Any]] = []
    max_plan_balance = max_plan_state = max_balance = max_state = max_crossday = 0.0
    plan_simultaneous = 0
    soc_min = soc
    soc_max = soc
    previous_close: float | None = None
    quantile_counts = {"q70": 0, "q80": 0, "q90": 0, "none": 0}
    effective_forecasts = []
    point_forecasts = []
    actual_targets = []
    for day_idx in range(EVAL_START, len(dates)):
        q_plan, selected_q, uplift, hist_left, hist_right, plan_bal, plan_state, simultaneous = plan_for_day(
            kind=forecast_kind, day_idx=day_idx, point_net_cache=point_net_cache,
            actual_net=actual_net, load_kw=load_kw, pv_kw=pv_kw, dates=dates,
            price=price, soc=soc, risk_mode=risk_mode, residual_window=residual_window,
            proxy_losses=proxy_losses, terminal_value=terminal_value, horizon_days=horizon_days,
        )
        point = point_net_cache[day_idx]
        effective = point + uplift
        execution = execute_fixed_plan(load_kw[day_idx] / 6.0, pv_kw[day_idx] / 6.0, q_plan, soc)
        if previous_close is not None:
            max_crossday = max(max_crossday, abs(soc - previous_close))
        balance = q_plan + pv_kw[day_idx] / 6.0 + execution.discharge + execution.emergency - load_kw[day_idx] / 6.0 - execution.charge - execution.surplus
        state = execution.soc[1:] - execution.soc[:-1] - ETA_CHARGE * execution.charge + execution.discharge / ETA_DISCHARGE
        normal_costs = price * q_plan
        emergency_costs = PRICE_MULTIPLIER * price * execution.emergency
        q_key = "none" if selected_q is None else f"q{int(round(selected_q * 100))}"
        quantile_counts[q_key] += 1
        daily.append({
            "strategy": name, "date": dates[day_idx].isoformat(),
            "train_end_date": dates[day_idx - 1].isoformat(),
            "risk_history_start_date": dates[hist_left].isoformat(),
            "risk_history_end_date": dates[hist_right].isoformat(),
            "selected_quantile": "" if selected_q is None else selected_q,
            "normal_purchase_kwh": float(np.sum(q_plan)),
            "emergency_purchase_kwh": float(np.sum(execution.emergency)),
            "normal_cost_yuan": float(np.sum(normal_costs)),
            "emergency_cost_yuan": float(np.sum(emergency_costs)),
            "total_cost_yuan": float(np.sum(normal_costs + emergency_costs)),
            "soc_open_kwh": float(execution.soc[0]), "soc_close_kwh": float(execution.soc[-1]),
        })
        for slot in range(N):
            detail.append({
                "strategy": name, "date": dates[day_idx].isoformat(), "slot": slot + 1,
                "train_end_date": dates[day_idx - 1].isoformat(),
                "risk_history_end_date": dates[hist_right].isoformat(),
                "selected_quantile": "" if selected_q is None else selected_q,
                "point_net_kw": float(point[slot]), "risk_uplift_kw": float(uplift[slot]),
                "effective_net_kw": float(effective[slot]), "actual_load_kw": float(load_kw[day_idx, slot]),
                "actual_pv_kw": float(pv_kw[day_idx, slot]), "price_yuan_per_kwh": float(price[slot]),
                "normal_purchase_kwh": float(q_plan[slot]), "charge_kwh": float(execution.charge[slot]),
                "discharge_kwh": float(execution.discharge[slot]), "emergency_purchase_kwh": float(execution.emergency[slot]),
                "surplus_kwh": float(execution.surplus[slot]), "soc_open_kwh": float(execution.soc[slot]),
                "soc_close_kwh": float(execution.soc[slot + 1]), "normal_cost_yuan": float(normal_costs[slot]),
                "emergency_cost_yuan": float(emergency_costs[slot]), "balance_residual_kwh": float(balance[slot]),
                "state_residual_kwh": float(state[slot]),
            })
        max_plan_balance = max(max_plan_balance, plan_bal)
        max_plan_state = max(max_plan_state, plan_state)
        plan_simultaneous += simultaneous
        max_balance = max(max_balance, max_abs(balance))
        max_state = max(max_state, max_abs(state))
        soc_min = min(soc_min, float(np.min(execution.soc)))
        soc_max = max(soc_max, float(np.max(execution.soc)))
        previous_close = float(execution.soc[-1])
        soc = previous_close
        point_forecasts.append(point)
        effective_forecasts.append(effective)
        actual_targets.append(actual_net[day_idx])
    point_array = np.asarray(point_forecasts)
    effective_array = np.asarray(effective_forecasts)
    actual_array = np.asarray(actual_targets)
    aggregate = {
        "strategy": name, "forecast_kind": forecast_kind, "risk_mode": risk_mode,
        "residual_window_days": residual_window if risk_mode != "none" else None,
        "terminal_value": terminal_value, "planning_horizon_hours": horizon_days * 24,
        "days": len(daily), "normal_purchase_kwh": float(sum(r["normal_purchase_kwh"] for r in daily)),
        "emergency_purchase_kwh": float(sum(r["emergency_purchase_kwh"] for r in daily)),
        "normal_cost_yuan": float(sum(r["normal_cost_yuan"] for r in daily)),
        "emergency_cost_yuan": float(sum(r["emergency_cost_yuan"] for r in daily)),
        "total_cost_yuan": float(sum(r["total_cost_yuan"] for r in daily)),
        "soc_final_kwh": soc, "soc_min_kwh": soc_min, "soc_max_kwh": soc_max,
        "point_forecast": q2.forecast_metrics(actual_array, point_array),
        "effective_forecast": {**q2.forecast_metrics(actual_array, effective_array), "one_sided_coverage": float(np.mean(actual_array <= effective_array))},
        "selected_quantile_days": quantile_counts,
        "max_plan_balance_residual_kwh": max_plan_balance, "max_plan_state_residual_kwh": max_plan_state,
        "plan_simultaneous_positive_slots": plan_simultaneous,
        "max_actual_balance_residual_kwh": max_balance, "max_actual_state_residual_kwh": max_state,
        "max_crossday_soc_gap_kwh": max_crossday,
    }
    return {"aggregate": aggregate, "daily": daily, "detail": detail}


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    RESULTS.mkdir(exist_ok=True)
    VALIDATION.mkdir(exist_ok=True)
    INTERMEDIATE.mkdir(exist_ok=True)
    frozen_paths = [RESULTS / "q2_summary.json", RESULTS / "result2.xlsx", RESULTS / "q2_detail.csv", VALIDATION / "q2_validation.json"]
    before = {str(p.relative_to(PROJECT_ROOT)): sha256(p) for p in frozen_paths}
    fixed = load_attachment1()
    annual = load_attachment2()
    load, pv, dates = annual["load_kw"], annual["pv_kw"], annual["dates"]
    actual_net = load - pv
    price = fixed["price_yuan_per_kwh"]
    _, _, main_point = q2.make_point_forecast_cache("candidate_linear_pv5", load, pv, dates)
    _, _, online_point = q2.make_point_forecast_cache("candidate_equal_pv5", load, pv, dates)
    main_losses = build_proxy_losses(actual_net, main_point, price, 56)
    online_losses = build_proxy_losses(actual_net, online_point, price, 28)
    specs = [
        ("A0_base_point", "candidate_linear_pv5", "none", 56, False, 2, main_point, None),
        ("A1_fixed_q80", "candidate_linear_pv5", "fixed_q80", 56, False, 2, main_point, None),
        ("A2_dynamic_risk", "candidate_linear_pv5", "dynamic", 56, False, 2, main_point, main_losses),
        ("A3_dynamic_plus_terminal_value", "candidate_linear_pv5", "dynamic", 56, True, 2, main_point, main_losses),
        ("O2_online_scheme_reconstruction", "candidate_equal_pv5", "dynamic", 28, True, 1, online_point, online_losses),
    ]
    runs: dict[str, dict[str, Any]] = {}
    for spec in specs:
        name, kind, risk, window, terminal, horizon, point, losses = spec
        print(json.dumps({"event": "ablation_start", "strategy": name}, ensure_ascii=False), flush=True)
        runs[name] = run_strategy(
            name=name, forecast_kind=kind, risk_mode=risk, residual_window=window,
            terminal_value=terminal, horizon_days=horizon, load_kw=load, pv_kw=pv,
            dates=dates, price=price, actual_net=actual_net, point_net_cache=point,
            proxy_losses=losses,
        )
        print(json.dumps({"event": "ablation_complete", **runs[name]["aggregate"]}, ensure_ascii=False), flush=True)
    daily_rows = [row for run in runs.values() for row in run["daily"]]
    detail_rows = [row for run in runs.values() for row in run["detail"]]
    daily_path = RESULTS / "q2_component_ablation_daily.csv"
    detail_path = RESULTS / "q2_component_ablation_detail.csv"
    write_csv(daily_path, daily_rows)
    write_csv(detail_path, detail_rows)
    aggregates = {name: run["aggregate"] for name, run in runs.items()}
    chain = ["A0_base_point", "A1_fixed_q80", "A2_dynamic_risk", "A3_dynamic_plus_terminal_value"]
    increments = []
    for left, right in zip(chain, chain[1:]):
        a, b = aggregates[left], aggregates[right]
        increments.append({
            "from": left, "to": right,
            "total_cost_change_yuan": b["total_cost_yuan"] - a["total_cost_yuan"],
            "normal_cost_change_yuan": b["normal_cost_yuan"] - a["normal_cost_yuan"],
            "emergency_cost_change_yuan": b["emergency_cost_yuan"] - a["emergency_cost_yuan"],
            "emergency_purchase_change_kwh": b["emergency_purchase_kwh"] - a["emergency_purchase_kwh"],
            "final_soc_change_kwh": b["soc_final_kwh"] - a["soc_final_kwh"],
        })
    frozen_main = json.loads((RESULTS / "q2_summary.json").read_text(encoding="utf-8"))["strategies"]["seasonal_q80_main"]
    q80_anchor_difference = {
        key: aggregates["A1_fixed_q80"][key] - frozen_main[key]
        for key in ("normal_purchase_kwh", "emergency_purchase_kwh", "normal_cost_yuan", "emergency_cost_yuan", "total_cost_yuan", "soc_final_kwh")
    }
    after = {str(p.relative_to(PROJECT_ROOT)): sha256(p) for p in frozen_paths}
    constraints_ok = all(
        a["max_actual_balance_residual_kwh"] <= SOLVER_TOL_KWH
        and a["max_actual_state_residual_kwh"] <= SOLVER_TOL_KWH
        and a["max_crossday_soc_gap_kwh"] <= SOLVER_TOL_KWH
        and a["soc_min_kwh"] >= SOC_MIN - SOLVER_TOL_KWH
        and a["soc_max_kwh"] <= SOC_MAX + SOLVER_TOL_KWH
        for a in aggregates.values()
    )
    summary = {
        "schema_version": 1, "status": "PASS" if constraints_ok and before == after and max(map(abs, q80_anchor_difference.values())) <= 1e-7 else "FAIL",
        "question": "Q2 component ablation", "frozen_main_unchanged": before == after,
        "ablation_definition": {
            "common": "candidate_linear_pv5 point forecast, frozen Q2 information/executor/costs, 48h rolling horizon",
            "A0": "point forecast only; terminal SOC fixed to 6000 kWh at 48h",
            "A1": "A0 plus trailing-56-day slotwise fixed Q80 residual uplift; exact frozen-main anchor",
            "A2": "A1 risk replaced by daily causal Q70/Q80/Q90 selection minimizing prior-28-day one-period 1x/5x fee proxy",
            "A3": "A2 plus free terminal SOC valued at mean normal price times discharge efficiency",
        },
        "online_comparator_definition": {
            "evidence": "user-provided screenshot; exact source code unavailable",
            "implementation": "prior-28-day equal-weight same-weekday load, prior-5-day PV, trailing-28-day residuals and fee-calibrated Q70/Q80/Q90, 24h plan, terminal SOC salvage value",
            "non_identified_from_screenshot": ["original weekday weights", "original candidate risk grid", "original fee calibration formula", "original terminal value coefficient"],
            "anti_targeting": "Published 13,894,495.66-yuan total was not used by code, calibration, selection, or validation.",
        },
        "strategies": aggregates, "incremental_contributions": increments,
        "fixed_q80_anchor_difference": q80_anchor_difference,
        "frozen_hashes_before": before, "frozen_hashes_after": after,
        "files": {"daily": str(daily_path.relative_to(PROJECT_ROOT)), "detail": str(detail_path.relative_to(PROJECT_ROOT))},
    }
    summary_path = RESULTS / "q2_component_ablation_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    validation = {
        "schema_version": 1, "status": summary["status"],
        "pass_flags": {"frozen_main_unchanged": before == after, "fixed_q80_exact_anchor": max(map(abs, q80_anchor_difference.values())) <= 1e-7, "all_constraints": constraints_ok, "row_counts": len(daily_rows) == 5 * 334 and len(detail_rows) == 5 * 334 * 144},
        "q80_anchor_difference": q80_anchor_difference,
    }
    validation_path = VALIDATION / "q2_component_ablation_validation.json"
    validation_path.write_text(json.dumps(validation, ensure_ascii=False, indent=2), encoding="utf-8")
    manifest = {
        "schema_version": 1, "status": summary["status"],
        "input_sha256": {"attachment1": fixed["sha256"], "attachment2": annual["sha256"]},
        "frozen_q2_sha256": after,
        "code_sha256": {name: sha256(Path(__file__).with_name(name)) for name in ("common_data.py", "dispatch_core.py", "q2_solve.py", "q2_component_ablation.py")},
        "output_sha256": {str(p.relative_to(PROJECT_ROOT)): sha256(p) for p in (daily_path, detail_path, summary_path, validation_path)},
    }
    (INTERMEDIATE / "q2_component_ablation_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": summary["status"], "strategies": {k: {x: v[x] for x in ("total_cost_yuan", "emergency_purchase_kwh", "soc_final_kwh")} for k, v in aggregates.items()}, "increments": increments}, ensure_ascii=False))
    if summary["status"] != "PASS":
        raise RuntimeError("Q2组件消融未通过")


if __name__ == "__main__":
    main()
