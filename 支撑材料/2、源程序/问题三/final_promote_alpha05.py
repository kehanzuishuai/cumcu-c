from __future__ import annotations

import csv
import hashlib
import json
import shutil
import sys
from pathlib import Path
from typing import Any

import numpy as np

from common_data import PROJECT_ROOT, load_attachment1, load_attachment2, load_attachment3, load_attachment4
from dispatch_core import FLOW_MAX_KWH, POSITIVE_TOL_KWH, SOC_MAX, SOC_MIN, SOLVER_TOL_KWH
import q3_solve as q3
import q4_solve as q4
from q3_p1_load_feedback_ablation import make_issue_forecast


STAGE = PROJECT_ROOT / "_promotion_staging" / "alpha05_final"
STAGE_RESULTS = STAGE / "results"
STAGE_VALIDATION = STAGE / "validation"
STAGE_INTERMEDIATE = STAGE / "intermediate"
BACKUP = PROJECT_ROOT / "_archive" / "final_promotion_20260911_pre_alpha05"
PROTECTED = [
    "results/q1_detail.csv", "results/q1_summary.json", "results/result1.xlsx",
    "validation/q1_validation.json", "validation/q1_independent_recompute.json",
    "results/q2_detail.csv", "results/q2_daily.csv", "results/q2_summary.json", "results/result2.xlsx",
    "validation/q2_validation.json", "validation/q2_independent_recompute.json",
    "results/q4_2_detail.csv", "results/q4_2_daily.csv", "results/q4_2_storage_4h.csv",
    "results/q4_2_emergency_events.csv", "results/result4-2.xlsx",
    "validation/q4_2_validation.json", "validation/result4-2_workbook_validation.json",
]
PROMOTED = [
    "results/q3_detail.csv", "results/q3_daily.csv", "results/q3_storage_4h.csv",
    "results/q3_emergency_events.csv", "results/q3_plan_versions.csv", "results/q3_summary.json",
    "validation/q3_validation.json", "validation/q3_independent_recompute.json",
    "intermediate/q3_workbook_payload.json", "intermediate/q3_run_manifest.json",
    "results/result3.xlsx", "validation/result3_workbook_validation.json",
    "results/q4_3_detail.csv", "results/q4_3_daily.csv", "results/q4_3_storage_4h.csv",
    "results/q4_3_emergency_events.csv", "results/q4_3_plan_versions.csv", "results/q4_summary.json",
    "validation/q4_3_validation.json", "validation/q4_independent_recompute.json",
    "intermediate/q4_3_workbook_payload.json", "intermediate/q4_run_manifest.json",
    "results/result4-3.xlsx", "validation/result4-3_workbook_validation.json",
]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def hashes(names: list[str]) -> dict[str, str]:
    return {name: sha256(PROJECT_ROOT / name) for name in names if (PROJECT_ROOT / name).exists()}


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], empty_header: str | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        if empty_header is None:
            raise ValueError(f"empty CSV: {path}")
        path.write_text(empty_header + "\n", encoding="utf-8-sig")
        return
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def validate_run(run: dict[str, Any], question: str) -> dict[str, Any]:
    agg, detail, daily, versions = run["aggregate"], run["detail"], run["daily"], run["versions"]
    simultaneous = sum(float(r["charge_bus_kwh"]) > POSITIVE_TOL_KWH and float(r["discharge_bus_kwh"]) > POSITIVE_TOL_KWH for r in detail)
    emergency_charge = sum(float(r["emergency_purchase_kwh"]) > POSITIVE_TOL_KWH and float(r["charge_bus_kwh"]) > POSITIVE_TOL_KWH for r in detail)
    past_lock = sum(int(r["issue_slot"]) > 0 and int(r["target_slot"]) <= int(r["issue_slot"]) for r in versions)
    info = sum(r["train_end_date"] >= r["date"] or r["residual_history_end_date"] >= r["date"] for r in daily)
    max_charge = max(float(r["charge_bus_kwh"]) for r in detail)
    max_discharge = max(float(r["discharge_bus_kwh"]) for r in detail)
    latest: dict[tuple[str, int], dict[str, Any]] = {}
    for row in versions:
        key = (str(row["date"]), int(row["target_slot"]))
        if key not in latest or int(row["issue_slot"]) > int(latest[key]["issue_slot"]):
            latest[key] = row
    effective_diff = max(abs(float(latest[(str(r["date"]), int(r["slot"]))]["new_effective_plan_kwh"]) - float(r["effective_purchase_kwh"])) for r in detail)
    daily_cost = sum(float(r["total_cost_yuan"]) for r in daily)
    flags = {
        "row_counts": len(detail) == 334 * 144 and len(daily) == 334 and len(run["storage"]) == 334 * 6,
        "version_rows": len(versions) == 334 * (144 + sum(144 - h * 6 for h in (6, 12, 18))),
        "past_lock": past_lock == 0,
        "version_reconciliation": effective_diff <= 1e-7,
        "information_cutoff": info == 0,
        "actual_balance": agg["max_actual_balance_residual_kwh"] <= SOLVER_TOL_KWH,
        "actual_state": agg["max_actual_state_residual_kwh"] <= SOLVER_TOL_KWH,
        "soc_bounds": agg["soc_min_kwh"] >= SOC_MIN - SOLVER_TOL_KWH and agg["soc_max_kwh"] <= SOC_MAX + SOLVER_TOL_KWH,
        "storage_power": max_charge <= FLOW_MAX_KWH + SOLVER_TOL_KWH and max_discharge <= FLOW_MAX_KWH + SOLVER_TOL_KWH,
        "crossday_soc": agg["max_crossday_soc_gap_kwh"] <= SOLVER_TOL_KWH,
        "mutual_exclusion": simultaneous == 0,
        "emergency_not_charging": emergency_charge == 0,
        "plan_balance": agg["max_plan_balance_residual_kwh"] <= SOLVER_TOL_KWH,
        "plan_state": agg["max_plan_state_residual_kwh"] <= SOLVER_TOL_KWH,
        "adjustment_link": agg["max_adjustment_link_residual_kwh"] <= SOLVER_TOL_KWH,
        "plan_mutual_exclusion": agg["plan_simultaneous_positive_slots"] == 0,
        "cost_reconciliation": abs(daily_cost - agg["total_cost_yuan"]) <= 1e-6,
    }
    return {
        "schema_version": 1, "question": question, "status": "PASS" if all(flags.values()) else "FAIL",
        "pass_flags": flags,
        "metrics": {
            "past_lock_violations": past_lock, "information_cutoff_violations": info,
            "max_version_effective_difference_kwh": effective_diff,
            "simultaneous_actual_slots": simultaneous, "emergency_charge_overlap_slots": emergency_charge,
            "storage_power_limit_kw": 5000.0, "storage_flow_limit_kwh_per_slot": FLOW_MAX_KWH,
            "max_charge_kwh_per_slot": max_charge, "max_discharge_kwh_per_slot": max_discharge,
            "daily_cost_recompute_yuan": daily_cost, **agg,
        },
    }


def save_run(prefix: str, run: dict[str, Any]) -> dict[str, str]:
    names = {
        "detail": f"{prefix}_detail.csv", "daily": f"{prefix}_daily.csv",
        "storage": f"{prefix}_storage_4h.csv", "events": f"{prefix}_emergency_events.csv",
        "versions": f"{prefix}_plan_versions.csv",
    }
    write_csv(STAGE_RESULTS / names["detail"], run["detail"])
    write_csv(STAGE_RESULTS / names["daily"], run["daily"])
    write_csv(STAGE_RESULTS / names["storage"], run["storage"])
    write_csv(STAGE_RESULTS / names["versions"], run["versions"])
    write_csv(STAGE_RESULTS / names["events"], run["events"], "date,event_id,start_slot,end_slot_exclusive,interval,purchase_kwh")
    return {key: f"results/{value}" for key, value in names.items()}


def reprice_detail(detail: list[dict[str, Any]], prices: np.ndarray, dates: list) -> dict[str, float]:
    idx = {d.isoformat(): i for i, d in enumerate(dates)}
    base = down = up = emergency = 0.0
    for r in detail:
        p = float(prices[idx[str(r["date"])], int(r["slot"]) - 1])
        base += p * float(r["original_purchase_kwh"])
        down += .5 * p * float(r["downward_adjustment_kwh"])
        up += 1.5 * p * float(r["upward_adjustment_kwh"])
        emergency += 5 * p * float(r["emergency_purchase_kwh"])
    normal = base - down + up
    return {"base_plan_cost_yuan": base, "downward_credit_yuan": down, "upward_adjustment_cost_yuan": up,
            "normal_settlement_cost_yuan": normal, "emergency_cost_yuan": emergency, "total_cost_yuan": normal + emergency}


def stage() -> None:
    for d in (STAGE_RESULTS, STAGE_VALIDATION, STAGE_INTERMEDIATE):
        d.mkdir(parents=True, exist_ok=True)
    protected_before = hashes(PROTECTED)
    old_q3 = json.loads((PROJECT_ROOT / "results/q3_summary.json").read_text(encoding="utf-8"))
    old_q4 = json.loads((PROJECT_ROOT / "results/q4_summary.json").read_text(encoding="utf-8"))
    fixed, annual, pvf, realtime = load_attachment1(), load_attachment2(), load_attachment3(), load_attachment4()
    dates, load_kw, pv_kw = annual["dates"], annual["load_kw"], annual["pv_kw"]
    native = q3.issue_forecast
    q3.issue_forecast = make_issue_forecast(.5)
    try:
        residual, _, _ = q3.build_forecast_caches(load_kw, pv_kw, pvf["forecast_kw"], dates, "linear")
        q3_runs = {}
        for name, updates in (("q3_0only", []), ("q3_0_6", [6]), ("q3_0_6_12", [6, 12]), ("q3_all_main", [6, 12, 18])):
            print(json.dumps({"event": "stage_q3", "strategy": name}), flush=True)
            q3_runs[name] = q3.run_strategy(name=name, update_hours=updates, interpolation="linear", load_kw=load_kw, pv_kw=pv_kw,
                forecast3_kw=pvf["forecast_kw"], dates=dates, price=fixed["price_yuan_per_kwh"], residual_cache=residual,
                raw_endpoint_labels=annual["raw_endpoint_labels"], keep_detail=name == "q3_all_main")
        q4_runs = {}
        for name, updates in (("q4_3_0only", []), ("q4_3_0_6", [6]), ("q4_3_0_6_12", [6, 12]), ("q4_3_all_main", [6, 12, 18])):
            print(json.dumps({"event": "stage_q4_3", "strategy": name}), flush=True)
            q4_runs[name] = q3.run_strategy(name=name, update_hours=updates, interpolation="linear", load_kw=load_kw, pv_kw=pv_kw,
                forecast3_kw=pvf["forecast_kw"], dates=dates, price=fixed["price_yuan_per_kwh"], residual_cache=residual,
                raw_endpoint_labels=annual["raw_endpoint_labels"], keep_detail=name == "q4_3_all_main",
                actual_price_by_date=realtime["price_yuan_per_kwh"], planning_price_kind="weekday_mean_28d")
    finally:
        q3.issue_forecast = native
    q3_main, q43_main = q3_runs["q3_all_main"], q4_runs["q4_3_all_main"]
    q3_validation, q43_validation = validate_run(q3_main, "Q3"), validate_run(q43_main, "Q4-3")
    q3_paths, q43_paths = save_run("q3", q3_main), save_run("q4_3", q43_main)
    p1 = json.loads((PROJECT_ROOT / "experiments/q3_q4_refinement/results/p1_load_feedback_ablation_summary.json").read_text(encoding="utf-8"))
    q3_summary = {
        **old_q3,
        "status": "SOLVED_AND_VALIDATED", "promotion": {"status": "FINAL_MAIN", "load_feedback_alpha": .5,
            "previous_main_total_cost_yuan": old_q3["strategies"]["q3_all_main"]["total_cost_yuan"]},
        "frozen_basis": {**old_q3["frozen_basis"], "information": "PV forecasts arrive at 00/06/12/18; only unexecuted slots may be revised; at 06/12/18 the observed load prefix causally scales only the current-day unexecuted load forecast with alpha=0.5"},
        "model_settings": {**old_q3["model_settings"], "load_forecast": "prior-28-day same-weekday linearly weighted base; at 06/12/18 apply 1+0.5*(observed-prefix/base-prefix-1) only to current-day unexecuted slots",
            "load_feedback_alpha": .5},
        "forecast_diagnostics": {"alpha_0_5": p1["prediction_diagnostics"]["alpha_0_5"]},
        "strategies": {k: v["aggregate"] for k, v in q3_runs.items()},
        "incremental_update_value": [
            {"from": a, "to": b, "cost_saving_yuan": q3_runs[a]["aggregate"]["total_cost_yuan"] - q3_runs[b]["aggregate"]["total_cost_yuan"],
             "emergency_change_kwh": q3_runs[b]["aggregate"]["emergency_purchase_kwh"] - q3_runs[a]["aggregate"]["emergency_purchase_kwh"]}
            for a, b in zip(("q3_0only", "q3_0_6", "q3_0_6_12"), ("q3_0_6", "q3_0_6_12", "q3_all_main"))],
        "files": q3_paths,
    }
    selected = ["2025-03-20", "2025-06-21", "2025-09-23", "2025-12-21"]
    q3_summary["selected_date_emergency_events"] = {d: [r for r in q3_main["events"] if r["date"] == d] for d in selected}
    fixed_q3 = reprice_detail(q3_main["detail"], realtime["price_yuan_per_kwh"], dates)
    q4_summary = {
        **old_q4,
        "status": "SOLVED_AND_VALIDATED",
        "promotion": {"status": "FINAL_MAIN_Q4_3", "load_feedback_alpha": .5, "intraday_price_correction": "OFF",
            "previous_q4_3_total_cost_yuan": old_q4["q4_3"]["strategies"]["q4_3_all_main"]["total_cost_yuan"]},
        "model_settings": {**old_q4["model_settings"],
            "q4_3_intraday_price_forecast": "prior-28-day same-weekday mean formed causally at 00:00 and kept unchanged at 06/12/18; no observed-price scaling and no AR(1) correction",
            "q4_3_load_feedback": "alpha=0.5 causal observed-prefix correction inherited from promoted Q3"},
        "fixed_strategy_repricing": {**old_q4["fixed_strategy_repricing"], "q3_fixed_decisions": fixed_q3},
        "q4_3": {
            "strategies": {k: v["aggregate"] for k, v in q4_runs.items()},
            "incremental_update_value": [
                {"from": a, "to": b, "cost_saving_yuan": q4_runs[a]["aggregate"]["total_cost_yuan"] - q4_runs[b]["aggregate"]["total_cost_yuan"],
                 "emergency_change_kwh": q4_runs[b]["aggregate"]["emergency_purchase_kwh"] - q4_runs[a]["aggregate"]["emergency_purchase_kwh"]}
                for a, b in zip(("q4_3_0only", "q4_3_0_6", "q4_3_0_6_12"), ("q4_3_0_6", "q4_3_0_6_12", "q4_3_all_main"))],
            "saving_vs_fixed_q3_decisions_yuan": fixed_q3["total_cost_yuan"] - q43_main["aggregate"]["total_cost_yuan"],
            "saving_vs_frozen_midnight_price_forecast_yuan": 0.0,
            "selected_date_events": {d: [r for r in q43_main["events"] if r["date"] == d] for d in selected},
        },
        "files": {**old_q4["files"], "q4_3": q43_paths},
    }
    write_json(STAGE_RESULTS / "q3_summary.json", q3_summary)
    write_json(STAGE_RESULTS / "q4_summary.json", q4_summary)
    write_json(STAGE_VALIDATION / "q3_validation.json", q3_validation)
    write_json(STAGE_VALIDATION / "q4_3_validation.json", q43_validation)
    write_json(STAGE_INTERMEDIATE / "q3_workbook_payload.json", {"schema_version": 1, "question": "Q3", "time_label_mapping": "natural_day_00:00_to_24:00_corrected_from_shifted_official_template", "plans": q3_main["workbook_plans"], "storage_four_hour": q3_main["storage"], "emergency_events": q3_main["events"]})
    write_json(STAGE_INTERMEDIATE / "q4_3_workbook_payload.json", {"schema_version": 1, "question": "Q4-3", "time_label_mapping": "natural_day_00:00_to_24:00_corrected_from_shifted_official_template", "plans": q43_main["workbook_plans"], "storage_four_hour": q43_main["storage"], "emergency_events": q43_main["events"]})
    old3 = old_q3["strategies"]["q3_all_main"]
    old43 = old_q4["q4_3"]["strategies"]["q4_3_all_main"]
    mean_fixed = float(np.mean(fixed["price_yuan_per_kwh"]))
    mean_rt = float(np.mean(realtime["price_yuan_per_kwh"][31:]))
    max_rt = float(np.max(realtime["price_yuan_per_kwh"][31:]))
    def terminal_gate(old: dict, new: dict, mean_price: float, max_price: float) -> dict:
        cash_saving = float(old["total_cost_yuan"] - new["total_cost_yuan"])
        delta_soc = float(new["soc_final_kwh"] - old["soc_final_kwh"])
        standard = cash_saving + delta_soc * .9 * mean_price
        conservative = cash_saving - abs(delta_soc) * .9 * 5 * max_price
        return {"same_initial_soc_kwh": old["soc_initial_kwh"] == new["soc_initial_kwh"] == 6000.0,
                "old_final_soc_kwh": old["soc_final_kwh"], "new_final_soc_kwh": new["soc_final_kwh"],
                "final_soc_difference_kwh": delta_soc, "cash_saving_yuan": cash_saving,
                "inventory_adjusted_saving_mean_price_yuan": standard,
                "conservative_saving_at_5x_max_price_yuan": conservative,
                "ranking_robust": standard > 0 and conservative > 0}
    terminal = {"q3": terminal_gate(old3, q3_main["aggregate"], mean_fixed, float(np.max(fixed["price_yuan_per_kwh"]))),
                "q4_3": terminal_gate(old43, q43_main["aggregate"], mean_rt, max_rt)}
    gate = {"schema_version": 1, "status": "PASS" if q3_validation["status"] == q43_validation["status"] == "PASS" and all(v["ranking_robust"] for v in terminal.values()) and protected_before == hashes(PROTECTED) else "FAIL",
            "candidate": {"q3": q3_main["aggregate"], "q4_3": q43_main["aggregate"]},
            "terminal_soc_inventory_comparability": terminal, "native_validation": {"q3": q3_validation["status"], "q4_3": q43_validation["status"]},
            "protected_hashes_before": protected_before, "protected_hashes_after_stage": hashes(PROTECTED)}
    write_json(STAGE_VALIDATION / "promotion_gate_native.json", gate)
    print(json.dumps({"event": "stage_complete", "status": gate["status"], "q3": q3_main["aggregate"]["total_cost_yuan"], "q4_3": q43_main["aggregate"]["total_cost_yuan"]}, ensure_ascii=False))
    if gate["status"] != "PASS":
        raise RuntimeError("native promotion gate failed")


def commit() -> None:
    native = json.loads((STAGE_VALIDATION / "promotion_gate_native.json").read_text(encoding="utf-8"))
    independent = json.loads((STAGE_VALIDATION / "promotion_gate_independent.json").read_text(encoding="utf-8"))
    for name in ("results/result3.xlsx", "results/result4-3.xlsx", "validation/result3_workbook_validation.json", "validation/result4-3_workbook_validation.json"):
        if not (STAGE / name).exists():
            raise FileNotFoundError(STAGE / name)
    if native["status"] != "PASS" or independent["status"] != "PASS":
        raise RuntimeError("promotion gates are not all PASS")
    workbook_checks = [json.loads((STAGE / name).read_text(encoding="utf-8"))["status"] for name in ("validation/result3_workbook_validation.json", "validation/result4-3_workbook_validation.json")]
    if workbook_checks != ["PASS", "PASS"]:
        raise RuntimeError("workbook gate failed")
    current_protected = hashes(PROTECTED)
    if current_protected != native["protected_hashes_before"]:
        raise RuntimeError("protected Q1/Q2/Q4-2 hash drift before commit")
    if BACKUP.exists():
        raise FileExistsError(f"backup already exists: {BACKUP}")
    for name in PROMOTED:
        src = PROJECT_ROOT / name
        if src.exists():
            dst = BACKUP / name
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
    mapping = [
        "results/q3_detail.csv", "results/q3_daily.csv", "results/q3_storage_4h.csv", "results/q3_emergency_events.csv", "results/q3_plan_versions.csv", "results/q3_summary.json",
        "validation/q3_validation.json", "intermediate/q3_workbook_payload.json",
        "validation/q3_independent_recompute.json",
        "results/result3.xlsx", "validation/result3_workbook_validation.json",
        "results/q4_3_detail.csv", "results/q4_3_daily.csv", "results/q4_3_storage_4h.csv", "results/q4_3_emergency_events.csv", "results/q4_3_plan_versions.csv", "results/q4_summary.json",
        "validation/q4_3_validation.json", "intermediate/q4_3_workbook_payload.json",
        "validation/q4_independent_recompute.json",
        "results/result4-3.xlsx", "validation/result4-3_workbook_validation.json",
    ]
    for name in mapping:
        dst = PROJECT_ROOT / name
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(STAGE / name, dst)
    q3_manifest = {
        "question": "Q3", "status": "PASS", "promoted_model": "alpha_0_5_causal_load_feedback",
        "outputs_sha256": hashes([name for name in mapping if "/q3" in name or "result3" in name]),
    }
    q4_manifest = {
        "question": "Q4", "status": "PASS",
        "q4_2_preserved_hashes": {k: v for k, v in current_protected.items() if "q4_2" in k or "result4-2" in k},
        "promoted_q4_3_model": "alpha_0_5_load_feedback__weekday_mean_28d_price__no_ar1",
        "outputs_sha256": hashes([name for name in mapping if "q4_" in name or "result4-3" in name or name == "results/q4_summary.json"]),
    }
    write_json(PROJECT_ROOT / "intermediate/q3_run_manifest.json", q3_manifest)
    write_json(PROJECT_ROOT / "intermediate/q4_run_manifest.json", q4_manifest)
    manifest = {"schema_version": 1, "status": "PROMOTED", "backup": str(BACKUP),
                "protected_hashes_before": native["protected_hashes_before"], "protected_hashes_after": hashes(PROTECTED),
                "promoted_outputs_sha256": hashes(mapping), "native_gate": native, "independent_gate": independent}
    write_json(PROJECT_ROOT / "intermediate/final_promotion_alpha05_manifest.json", manifest)
    if manifest["protected_hashes_before"] != manifest["protected_hashes_after"]:
        raise RuntimeError("protected hashes drifted during commit")
    print(json.dumps({"event": "commit_complete", "status": "PASS", "backup": str(BACKUP)}, ensure_ascii=False))


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "stage"
    if mode == "stage":
        stage()
    elif mode == "commit":
        commit()
    else:
        raise ValueError(mode)
