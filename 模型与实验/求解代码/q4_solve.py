from __future__ import annotations

import csv
import json
import platform
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import scipy

from common_data import PROJECT_ROOT, load_attachment1, load_attachment2, load_attachment3, load_attachment4, sha256
from dispatch_core import POSITIVE_TOL_KWH, SOC_MAX, SOC_MIN, SOLVER_TOL_KWH
import q2_solve as q2
import q3_solve as q3


RESULTS = PROJECT_ROOT / "results"
VALIDATION = PROJECT_ROOT / "validation"
INTERMEDIATE = PROJECT_ROOT / "intermediate"
EVAL_START = 31
N = 144


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"拒绝写入无表头空CSV: {path.name}")
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def metric(actual: np.ndarray, forecast: np.ndarray) -> dict[str, float]:
    error = forecast - actual
    return {
        "mae_yuan_per_kwh": float(np.mean(np.abs(error))),
        "rmse_yuan_per_kwh": float(np.sqrt(np.mean(error**2))),
        "wape": float(np.sum(np.abs(error)) / np.sum(np.abs(actual))),
        "bias_yuan_per_kwh": float(np.mean(error)),
    }


def price_issue_diagnostics(price: np.ndarray, dates: list[date]) -> dict[str, Any]:
    diagnostics: dict[str, Any] = {}
    for issue_hour in (0, 6, 12, 18):
        start = issue_hour * 6
        actual_rows: list[np.ndarray] = []
        persistence_rows: list[np.ndarray] = []
        weekday_rows: list[np.ndarray] = []
        scaled_rows: list[np.ndarray] = []
        scaled_ar1_rows: list[np.ndarray] = []
        scales: list[float] = []
        for day_idx in range(EVAL_START, len(dates) - 1):
            actual_rows.append(np.concatenate([price[day_idx, start:], price[day_idx + 1, :start]]))
            persistence, _ = q3.causal_price_forecast_horizon(price, dates, day_idx, issue_hour, "persistence")
            weekday, _ = q3.causal_price_forecast_horizon(price, dates, day_idx, issue_hour, "weekday_mean_28d")
            scaled, scale = q3.causal_price_forecast_horizon(price, dates, day_idx, issue_hour, "weekday_mean_28d_intraday_scale")
            scaled_ar1, _ = q3.causal_price_forecast_horizon(price, dates, day_idx, issue_hour, "weekday_mean_28d_intraday_scale_ar1")
            persistence_rows.append(persistence)
            weekday_rows.append(weekday)
            scaled_rows.append(scaled)
            scaled_ar1_rows.append(scaled_ar1)
            scales.append(scale)
        actual = np.asarray(actual_rows)
        diagnostics[f"{issue_hour:02d}:00"] = {
            "evaluation_days_with_complete_24h_target": len(actual_rows),
            "persistence": metric(actual, np.asarray(persistence_rows)),
            "weekday_mean_28d": metric(actual, np.asarray(weekday_rows)),
            "weekday_mean_28d_intraday_scale": metric(actual, np.asarray(scaled_rows)),
            "weekday_mean_28d_intraday_scale_ar1": metric(actual, np.asarray(scaled_ar1_rows)),
            "scale_range": [float(np.min(scales)), float(np.max(scales))],
        }
    return diagnostics


def fixed_reprice_q2(path: Path, price: np.ndarray, dates: list[date]) -> dict[str, float]:
    date_idx = {value.isoformat(): idx for idx, value in enumerate(dates)}
    normal = emergency = 0.0
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            p = float(price[date_idx[row["date"]], int(row["slot"]) - 1])
            normal += p * float(row["normal_purchase_kwh"])
            emergency += 5.0 * p * float(row["emergency_purchase_kwh"])
    return {"normal_cost_yuan": normal, "emergency_cost_yuan": emergency, "total_cost_yuan": normal + emergency}


def fixed_reprice_q3(path: Path, price: np.ndarray, dates: list[date]) -> dict[str, float]:
    date_idx = {value.isoformat(): idx for idx, value in enumerate(dates)}
    base = credit = upward = emergency = 0.0
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            p = float(price[date_idx[row["date"]], int(row["slot"]) - 1])
            base += p * float(row["original_purchase_kwh"])
            credit += 0.5 * p * float(row["downward_adjustment_kwh"])
            upward += 1.5 * p * float(row["upward_adjustment_kwh"])
            emergency += 5.0 * p * float(row["emergency_purchase_kwh"])
    normal = base - credit + upward
    return {
        "base_plan_cost_yuan": base,
        "downward_credit_yuan": credit,
        "upward_adjustment_cost_yuan": upward,
        "normal_settlement_cost_yuan": normal,
        "emergency_cost_yuan": emergency,
        "total_cost_yuan": normal + emergency,
    }


def save_q2_run(run: dict[str, Any]) -> dict[str, Path]:
    paths = {
        "detail": RESULTS / "q4_2_detail.csv",
        "daily": RESULTS / "q4_2_daily.csv",
        "storage": RESULTS / "q4_2_storage_4h.csv",
        "events": RESULTS / "q4_2_emergency_events.csv",
    }
    for key in ("detail", "daily", "storage"):
        write_csv(paths[key], run[key])
    if run["events"]:
        write_csv(paths["events"], run["events"])
    else:
        paths["events"].write_text("date,event_id,start_slot,end_slot_exclusive,interval,purchase_kwh\n", encoding="utf-8-sig")
    return paths


def save_q3_run(run: dict[str, Any]) -> dict[str, Path]:
    paths = {
        "detail": RESULTS / "q4_3_detail.csv",
        "daily": RESULTS / "q4_3_daily.csv",
        "storage": RESULTS / "q4_3_storage_4h.csv",
        "events": RESULTS / "q4_3_emergency_events.csv",
        "versions": RESULTS / "q4_3_plan_versions.csv",
    }
    for key in ("detail", "daily", "storage", "versions"):
        write_csv(paths[key], run[key])
    if run["events"]:
        write_csv(paths["events"], run["events"])
    else:
        paths["events"].write_text("date,event_id,start_slot,end_slot_exclusive,interval,purchase_kwh\n", encoding="utf-8-sig")
    return paths


def validate_aggregate(question: str, agg: dict[str, Any], detail: list[dict[str, Any]], days: int) -> dict[str, Any]:
    simultaneous = sum(
        float(row["charge_bus_kwh"]) > POSITIVE_TOL_KWH and float(row["discharge_bus_kwh"]) > POSITIVE_TOL_KWH
        for row in detail
    )
    emergency_charge = sum(
        float(row["emergency_purchase_kwh"]) > POSITIVE_TOL_KWH and float(row["charge_bus_kwh"]) > POSITIVE_TOL_KWH
        for row in detail
    )
    max_charge = max(float(row["charge_bus_kwh"]) for row in detail)
    max_discharge = max(float(row["discharge_bus_kwh"]) for row in detail)
    info_violations = sum(row["train_end_date"] >= row["date"] for row in detail)
    flags = {
        "detail_rows": len(detail) == days * N,
        "information_cutoff": info_violations == 0,
        "actual_balance": agg["max_actual_balance_residual_kwh"] <= SOLVER_TOL_KWH,
        "actual_state": agg["max_actual_state_residual_kwh"] <= SOLVER_TOL_KWH,
        "soc_bounds": agg["soc_min_kwh"] >= SOC_MIN - SOLVER_TOL_KWH and agg["soc_max_kwh"] <= SOC_MAX + SOLVER_TOL_KWH,
        "storage_power": max_charge <= q3.FLOW_MAX_KWH + SOLVER_TOL_KWH and max_discharge <= q3.FLOW_MAX_KWH + SOLVER_TOL_KWH,
        "crossday_soc": agg["max_crossday_soc_gap_kwh"] <= SOLVER_TOL_KWH,
        "mutual_exclusion_actual": simultaneous == 0,
        "emergency_not_charging": emergency_charge == 0,
        "plan_balance": agg["max_plan_balance_residual_kwh"] <= SOLVER_TOL_KWH,
        "plan_state": agg["max_plan_state_residual_kwh"] <= SOLVER_TOL_KWH,
        "plan_mutual_exclusion": agg["plan_simultaneous_positive_slots"] == 0,
    }
    return {
        "schema_version": 1,
        "question": question,
        "status": "PASS" if all(flags.values()) else "FAIL",
        "pass_flags": flags,
        "metrics": {"information_violations": info_violations, "simultaneous_actual_slots": simultaneous, "emergency_charge_overlap_slots": emergency_charge,
                    "storage_power_limit_kw": 5000.0, "storage_flow_limit_kwh_per_slot": q3.FLOW_MAX_KWH,
                    "max_charge_kwh_per_slot": max_charge, "max_discharge_kwh_per_slot": max_discharge, **agg},
        "environment": {"python": sys.version, "python_executable": sys.executable, "platform": platform.platform(), "numpy": np.__version__, "scipy": scipy.__version__, "solver": "scipy.optimize.linprog(method='highs')"},
    }


def main() -> None:
    RESULTS.mkdir(parents=True, exist_ok=True)
    VALIDATION.mkdir(parents=True, exist_ok=True)
    INTERMEDIATE.mkdir(parents=True, exist_ok=True)
    fixed = load_attachment1()
    annual = load_attachment2()
    pv_forecast = load_attachment3()
    realtime = load_attachment4()
    if not (annual["dates"] == pv_forecast["dates"] == realtime["dates"]):
        raise ValueError("附件2、3、4日期轴不一致")
    dates = annual["dates"]
    load_kw, pv_kw = annual["load_kw"], annual["pv_kw"]
    actual_net = load_kw - pv_kw
    price = realtime["price_yuan_per_kwh"]

    price_weekday = q2.make_historical_weekday_cache(price, dates)
    eval_slice = slice(EVAL_START, len(dates))
    price_diagnostics = {
        "range_yuan_per_kwh": [float(np.min(price)), float(np.max(price))],
        "mean_yuan_per_kwh": float(np.mean(price)),
        "persistence_1d": metric(price[eval_slice], price[EVAL_START - 1 : len(dates) - 1]),
        "weekday_mean_28d": metric(price[eval_slice], price_weekday[eval_slice]),
        "issue_horizon_24h": price_issue_diagnostics(price, dates),
    }

    q2_config = json.loads((INTERMEDIATE / "q2_main_config.json").read_text(encoding="utf-8"))
    q2_kind = str(q2_config["selected_forecast_kind"])
    _, _, q2_point_net = q2.make_point_forecast_cache(q2_kind, load_kw, pv_kw, dates)
    print(json.dumps({"event": "q4_2_start", "price_model": "persistence"}, ensure_ascii=False), flush=True)
    q42_persistence = q2.run_strategy(
        name="q4_2_price_persistence", forecast_kind=q2_kind, quantile=0.8,
        terminal_mode="fixed_6000_at_48h", load_kw=load_kw, pv_kw=pv_kw, dates=dates,
        price=fixed["price_yuan_per_kwh"], actual_net_kw=actual_net, weekday_net_cache_kw=q2_point_net,
        raw_endpoint_labels=annual["raw_endpoint_labels"], keep_detail=False,
        actual_price_by_date=price, planning_price_kind="persistence",
    )
    print(json.dumps({"event": "q4_2_start", "price_model": "weekday_mean_28d"}, ensure_ascii=False), flush=True)
    q42 = q2.run_strategy(
        name="q4_2_main", forecast_kind=q2_kind, quantile=0.8,
        terminal_mode="fixed_6000_at_48h", load_kw=load_kw, pv_kw=pv_kw, dates=dates,
        price=fixed["price_yuan_per_kwh"], actual_net_kw=actual_net, weekday_net_cache_kw=q2_point_net,
        raw_endpoint_labels=annual["raw_endpoint_labels"], keep_detail=True,
        actual_price_by_date=price, planning_price_kind="weekday_mean_28d",
    )
    q42_paths = save_q2_run(q42)

    cache_linear, _, _ = q3.build_forecast_caches(load_kw, pv_kw, pv_forecast["forecast_kw"], dates, "linear")
    q43_specs = [
        ("q4_3_0only", [], "weekday_mean_28d_intraday_scale_ar1", False),
        ("q4_3_0_6", [6], "weekday_mean_28d_intraday_scale_ar1", False),
        ("q4_3_0_6_12", [6, 12], "weekday_mean_28d_intraday_scale_ar1", False),
        ("q4_3_all_main", [6, 12, 18], "weekday_mean_28d_intraday_scale_ar1", True),
        ("q4_3_all_price_scale_only", [6, 12, 18], "weekday_mean_28d_intraday_scale", False),
        ("q4_3_all_price_frozen_midnight", [6, 12, 18], "weekday_mean_28d", False),
        ("q4_3_all_price_persistence", [6, 12, 18], "persistence", False),
    ]
    q43_runs: dict[str, dict[str, Any]] = {}
    for name, updates, price_kind, keep in q43_specs:
        print(json.dumps({"event": "q4_3_start", "strategy": name}, ensure_ascii=False), flush=True)
        q43_runs[name] = q3.run_strategy(
            name=name, update_hours=updates, interpolation="linear", load_kw=load_kw, pv_kw=pv_kw,
            forecast3_kw=pv_forecast["forecast_kw"], dates=dates, price=fixed["price_yuan_per_kwh"],
            residual_cache=cache_linear, raw_endpoint_labels=annual["raw_endpoint_labels"], keep_detail=keep,
            actual_price_by_date=price, planning_price_kind=price_kind,
        )
    q43 = q43_runs["q4_3_all_main"]
    q43_paths = save_q3_run(q43)

    fixed_q2 = fixed_reprice_q2(RESULTS / "q2_detail.csv", price, dates)
    fixed_q3 = fixed_reprice_q3(RESULTS / "q3_detail.csv", price, dates)
    q42_validation = validate_aggregate("Q4-2", q42["aggregate"], q42["detail"], 334)
    q43_validation = validate_aggregate("Q4-3", q43["aggregate"], q43["detail"], 334)
    if q43["aggregate"]["max_adjustment_link_residual_kwh"] > SOLVER_TOL_KWH:
        q43_validation["pass_flags"]["adjustment_link"] = False
        q43_validation["status"] = "FAIL"
    else:
        q43_validation["pass_flags"]["adjustment_link"] = True

    q42_workbook = {
        "schema_version": 1, "question": "Q4-2",
        "time_label_mapping": "natural_day_00:00_to_24:00_corrected_from_shifted_official_template",
        "plans": q42["plans"], "storage_four_hour": q42["storage"], "emergency_events": q42["events"],
    }
    q43_workbook = {
        "schema_version": 1, "question": "Q4-3",
        "time_label_mapping": "natural_day_00:00_to_24:00_corrected_from_shifted_official_template",
        "plans": q43["workbook_plans"], "storage_four_hour": q43["storage"], "emergency_events": q43["events"],
    }
    q42_payload_path = INTERMEDIATE / "q4_2_workbook_payload.json"
    q43_payload_path = INTERMEDIATE / "q4_3_workbook_payload.json"
    q42_payload_path.write_text(json.dumps(q42_workbook, ensure_ascii=False, indent=2), encoding="utf-8")
    q43_payload_path.write_text(json.dumps(q43_workbook, ensure_ascii=False, indent=2), encoding="utf-8")

    ordered = ["q4_3_0only", "q4_3_0_6", "q4_3_0_6_12", "q4_3_all_main"]
    incremental = []
    for before, after in zip(ordered[:-1], ordered[1:]):
        a, b = q43_runs[before]["aggregate"], q43_runs[after]["aggregate"]
        incremental.append({"from": before, "to": after, "cost_saving_yuan": a["total_cost_yuan"] - b["total_cost_yuan"], "emergency_change_kwh": b["emergency_purchase_kwh"] - a["emergency_purchase_kwh"]})
    selected = ["2025-03-20", "2025-06-21", "2025-09-23", "2025-12-21"]
    summary = {
        "schema_version": 1, "status": "SOLVED_AND_VALIDATED" if q42_validation["status"] == q43_validation["status"] == "PASS" else "FAIL",
        "question": "Q4", "evaluation_period": {"start": dates[EVAL_START].isoformat(), "end": dates[-1].isoformat(), "days": 334},
        "frozen_basis": {"future_actual_price": "settlement only; never used in planning", "q4_2_information": "Q2 permissions without attachment 3", "q4_3_information": "Q3 permissions with attachment 3", "settlement_price_index": "actual delivery-slot price", "known_conflict": "A01 remains"},
        "price_forecast_diagnostics": price_diagnostics,
        "model_settings": {"q2_forecast_interface": q2_kind, "q4_2_main_price_forecast": "prior-28-day same-weekday mean formed causally at midnight", "price_baseline": "previous-day same-slot persistence", "q4_3_intraday_price_forecast": "at 00:00 use the prior-28-day same-weekday profile; at 06:00/12:00/18:00 scale the causal 24-hour historical profile by the observed-prefix ratio and add a decaying AR(1) correction from the last observed residual; AR(1) is re-estimated from prior-28-day causal residuals"},
        "fixed_strategy_repricing": {"q2_fixed_decisions": fixed_q2, "q3_fixed_decisions": fixed_q3},
        "q4_2": {"main": q42["aggregate"], "price_persistence": q42_persistence["aggregate"], "saving_vs_fixed_q2_decisions_yuan": fixed_q2["total_cost_yuan"] - q42["aggregate"]["total_cost_yuan"], "saving_vs_price_persistence_yuan": q42_persistence["aggregate"]["total_cost_yuan"] - q42["aggregate"]["total_cost_yuan"], "selected_date_events": {d: [r for r in q42["events"] if r["date"] == d] for d in selected}},
        "q4_3": {"strategies": {name: run["aggregate"] for name, run in q43_runs.items()}, "incremental_update_value": incremental, "saving_vs_fixed_q3_decisions_yuan": fixed_q3["total_cost_yuan"] - q43["aggregate"]["total_cost_yuan"], "saving_vs_price_persistence_yuan": q43_runs["q4_3_all_price_persistence"]["aggregate"]["total_cost_yuan"] - q43["aggregate"]["total_cost_yuan"], "saving_vs_frozen_midnight_price_forecast_yuan": q43_runs["q4_3_all_price_frozen_midnight"]["aggregate"]["total_cost_yuan"] - q43["aggregate"]["total_cost_yuan"], "selected_date_events": {d: [r for r in q43["events"] if r["date"] == d] for d in selected}},
        "files": {"q4_2": {k: str(v.relative_to(PROJECT_ROOT)) for k, v in q42_paths.items()}, "q4_3": {k: str(v.relative_to(PROJECT_ROOT)) for k, v in q43_paths.items()}},
    }
    summary_path = RESULTS / "q4_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    q42_validation_path = VALIDATION / "q4_2_validation.json"
    q43_validation_path = VALIDATION / "q4_3_validation.json"
    q42_validation_path.write_text(json.dumps(q42_validation, ensure_ascii=False, indent=2), encoding="utf-8")
    q43_validation_path.write_text(json.dumps(q43_validation, ensure_ascii=False, indent=2), encoding="utf-8")

    manifest = {
        "question": "Q4", "status": summary["status"],
        "input_sha256": {"attachment1": fixed["sha256"], "attachment2": annual["sha256"], "attachment3": pv_forecast["sha256"], "attachment4": realtime["sha256"]},
        "code_sha256": {name: sha256(Path(__file__).with_name(name)) for name in ("common_data.py", "dispatch_core.py", "q2_solve.py", "q3_solve.py", "q4_solve.py")},
        "outputs_sha256": {str(path.relative_to(PROJECT_ROOT)): sha256(path) for path in [*q42_paths.values(), *q43_paths.values(), summary_path, q42_validation_path, q43_validation_path, q42_payload_path, q43_payload_path]},
    }
    (INTERMEDIATE / "q4_run_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": summary["status"], "q4_2_total_cost_yuan": q42["aggregate"]["total_cost_yuan"], "q4_3_total_cost_yuan": q43["aggregate"]["total_cost_yuan"], "q4_2_fixed_reprice_yuan": fixed_q2["total_cost_yuan"], "q4_3_fixed_reprice_yuan": fixed_q3["total_cost_yuan"]}, ensure_ascii=False))
    if summary["status"] != "SOLVED_AND_VALIDATED":
        raise RuntimeError("Q4核验未通过")


if __name__ == "__main__":
    main()
