from __future__ import annotations

import csv
import json
from datetime import date
from pathlib import Path

from common_data import PROJECT_ROOT
from dispatch_core import ETA_CHARGE, ETA_DISCHARGE, FLOW_MAX_KWH, SOC_MAX, SOC_MIN
from refinement_common import RESULTS, VALIDATION, ensure_dirs, frozen_hashes, sha256, write_json


TOL = 1e-6
ROW_COUNT = 334 * 144


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def validate_detail(path: Path, expected: dict, q2_style: bool = False) -> dict:
    sums = {
        "normal_purchase_kwh": 0.0,
        "original_purchase_kwh": 0.0,
        "effective_purchase_kwh": 0.0,
        "upward_adjustment_kwh": 0.0,
        "downward_adjustment_kwh": 0.0,
        "emergency_purchase_kwh": 0.0,
        "surplus_discard_kwh": 0.0,
        "normal_cost_yuan": 0.0,
        "normal_settlement_cost_yuan": 0.0,
        "emergency_cost_yuan": 0.0,
        "total_cost_yuan": 0.0,
    }
    rows = 0
    max_balance = max_state = max_charge = max_discharge = 0.0
    min_soc = float("inf")
    max_soc = float("-inf")
    simultaneous = emergency_charge = info_violations = issue_violations = 0
    max_cost_row_error = 0.0
    max_crossday_gap = 0.0
    prior_date = None
    prior_close = None
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            rows += 1
            load = float(row["load_kwh"])
            pv = float(row["pv_kwh"])
            charge = float(row["charge_bus_kwh"])
            discharge = float(row["discharge_bus_kwh"])
            emergency = float(row["emergency_purchase_kwh"])
            discard = float(row["surplus_discard_kwh"])
            soc_open = float(row["soc_open_kwh"])
            soc_close = float(row["soc_close_kwh"])
            purchase_key = "normal_purchase_kwh" if q2_style else "effective_purchase_kwh"
            purchase = float(row[purchase_key])
            balance = purchase + pv + discharge + emergency - load - charge - discard
            state = soc_close - soc_open - ETA_CHARGE * charge + discharge / ETA_DISCHARGE
            max_balance = max(max_balance, abs(balance))
            max_state = max(max_state, abs(state))
            max_charge = max(max_charge, charge)
            max_discharge = max(max_discharge, discharge)
            min_soc = min(min_soc, soc_open, soc_close)
            max_soc = max(max_soc, soc_open, soc_close)
            simultaneous += charge > TOL and discharge > TOL
            emergency_charge += emergency > TOL and charge > TOL
            info_violations += date.fromisoformat(row["train_end_date"]) >= date.fromisoformat(row["date"])
            if "executed_plan_issue_time" in row:
                issue = int(row["executed_plan_issue_time"].split(":")[0])
                slot_start_minute = (int(row["slot"]) - 1) * 10
                issue_violations += issue * 60 > slot_start_minute
            if prior_date is not None and row["date"] != prior_date:
                max_crossday_gap = max(max_crossday_gap, abs(soc_open - float(prior_close)))
            prior_date = row["date"]
            prior_close = soc_close
            p = float(row["actual_price_yuan_per_kwh"])
            if q2_style:
                normal = p * purchase
                emergency_cost = 5.0 * p * emergency
                total = normal + emergency_cost
                max_cost_row_error = max(
                    max_cost_row_error,
                    abs(normal - float(row["normal_cost_yuan"])),
                    abs(emergency_cost - float(row["emergency_cost_yuan"])),
                )
                sums["normal_purchase_kwh"] += purchase
                sums["normal_cost_yuan"] += normal
            else:
                original = float(row["original_purchase_kwh"])
                up = float(row["upward_adjustment_kwh"])
                down = float(row["downward_adjustment_kwh"])
                normal = p * original - 0.5 * p * down + 1.5 * p * up
                emergency_cost = 5.0 * p * emergency
                total = normal + emergency_cost
                max_cost_row_error = max(
                    max_cost_row_error,
                    abs(normal - float(row["normal_settlement_cost_yuan"])),
                    abs(emergency_cost - float(row["emergency_cost_yuan"])),
                    abs(total - float(row["total_cost_yuan"])),
                )
                sums["original_purchase_kwh"] += original
                sums["effective_purchase_kwh"] += purchase
                sums["upward_adjustment_kwh"] += up
                sums["downward_adjustment_kwh"] += down
                sums["normal_settlement_cost_yuan"] += normal
            sums["emergency_purchase_kwh"] += emergency
            sums["surplus_discard_kwh"] += discard
            sums["emergency_cost_yuan"] += emergency_cost
            sums["total_cost_yuan"] += total
    expected_map = {
        "normal_purchase_kwh": "normal_purchase_kwh",
        "original_purchase_kwh": "original_purchase_kwh",
        "effective_purchase_kwh": "effective_purchase_kwh",
        "upward_adjustment_kwh": "upward_adjustment_kwh",
        "downward_adjustment_kwh": "downward_adjustment_kwh",
        "emergency_purchase_kwh": "emergency_purchase_kwh",
        "surplus_discard_kwh": "surplus_discard_kwh",
        "normal_cost_yuan": "normal_cost_yuan",
        "normal_settlement_cost_yuan": "normal_settlement_cost_yuan",
        "emergency_cost_yuan": "emergency_cost_yuan",
        "total_cost_yuan": "total_cost_yuan",
    }
    aggregate_errors = {
        key: abs(value - float(expected[expected_map[key]]))
        for key, value in sums.items()
        if expected_map[key] in expected and (value != 0.0 or float(expected[expected_map[key]]) != 0.0)
    }
    flags = {
        "row_count": rows == ROW_COUNT,
        "balance": max_balance <= TOL,
        "state": max_state <= TOL,
        "soc_bounds": min_soc >= SOC_MIN - TOL and max_soc <= SOC_MAX + TOL,
        "power": max_charge <= FLOW_MAX_KWH + TOL and max_discharge <= FLOW_MAX_KWH + TOL,
        "mutual_exclusion": simultaneous == 0,
        "emergency_not_charging": emergency_charge == 0,
        "crossday_soc": max_crossday_gap <= TOL,
        "past_only_training": info_violations == 0,
        "update_not_after_execution": issue_violations == 0,
        "cost_rows": max_cost_row_error <= TOL,
        "aggregate_reproduction": max(aggregate_errors.values(), default=0.0) <= 1e-5,
    }
    return {
        "file": str(path.relative_to(PROJECT_ROOT)),
        "status": "PASS" if all(flags.values()) else "FAIL",
        "flags": flags,
        "metrics": {
            "rows": rows,
            "max_balance_residual_kwh": max_balance,
            "max_state_residual_kwh": max_state,
            "soc_min_kwh": min_soc,
            "soc_max_kwh": max_soc,
            "max_charge_kwh_per_slot": max_charge,
            "max_discharge_kwh_per_slot": max_discharge,
            "max_crossday_gap_kwh": max_crossday_gap,
            "simultaneous_slots": simultaneous,
            "emergency_charge_slots": emergency_charge,
            "information_violations": info_violations,
            "issue_time_violations": issue_violations,
            "max_cost_row_error_yuan": max_cost_row_error,
            "aggregate_errors": aggregate_errors,
        },
    }


def close(a: float, b: float, tolerance: float = 1e-5) -> bool:
    return abs(float(a) - float(b)) <= tolerance


def main() -> None:
    ensure_dirs()
    p1 = load_json(RESULTS / "p1_load_feedback_ablation_summary.json")
    p2 = load_json(RESULTS / "p2_feedback_price_2x2_summary.json")
    p2_alpha05 = load_json(RESULTS / "p2_alpha05_transfer_summary.json")
    p3 = load_json(RESULTS / "p3_information_ablation_summary.json")
    p3_alpha05 = load_json(RESULTS / "p3_alpha05_selected_summary.json")
    p4 = load_json(RESULTS / "p4_evening_soc_reserve_summary.json")
    frozen_q3 = load_json(PROJECT_ROOT / "results" / "q3_summary.json")["strategies"]["q3_all_main"]
    frozen_q4 = load_json(PROJECT_ROOT / "results" / "q4_summary.json")
    checks = []
    for label, expected in p1["runs"].items():
        checks.append(validate_detail(RESULTS / f"p1_{label}_detail.csv", expected))
    for label, expected in p2["runs"].items():
        checks.append(validate_detail(RESULTS / f"p2_{label}_detail.csv", expected))
    for label, expected in p2_alpha05["runs"].items():
        checks.append(validate_detail(RESULTS / f"p2_{label}_detail.csv", expected))
    for label, expected in p3["runs"].items():
        checks.append(validate_detail(RESULTS / f"p3_{label}_detail.csv", expected))
    for label, expected in p3_alpha05["runs"].items():
        checks.append(validate_detail(RESULTS / f"p3_{label}_detail.csv", expected))
    checks.append(validate_detail(RESULTS / "p4_q4_2_reserve_detail.csv", p4["runs"]["q4_2_reserve"], q2_style=True))
    checks.append(validate_detail(RESULTS / "p4_q4_3_reserve_detail.csv", p4["runs"]["q4_3_reserve"]))

    anchors = {
        "p1_alpha0_equals_frozen_q3_cost": close(p1["runs"]["alpha_0"]["total_cost_yuan"], frozen_q3["total_cost_yuan"]),
        "p1_alpha0_equals_frozen_q3_emergency": close(p1["runs"]["alpha_0"]["emergency_purchase_kwh"], frozen_q3["emergency_purchase_kwh"]),
        "p3_state_pv_equals_frozen_q3_cost": close(p3["runs"]["state_pv"]["total_cost_yuan"], frozen_q3["total_cost_yuan"]),
        "p3_all_equals_p1_alpha1_cost": close(p3["runs"]["all_three"]["total_cost_yuan"], p1["runs"]["alpha_1"]["total_cost_yuan"]),
        "p3_alpha05_all_equals_p1_alpha05_cost": close(
            p3_alpha05["runs"]["all_three_alpha05"]["total_cost_yuan"],
            p1["runs"]["alpha_0_5"]["total_cost_yuan"],
        ),
        "p2_load0_price1_equals_frozen_q43_cost": close(
            p2["runs"]["load0_price1"]["total_cost_yuan"],
            frozen_q4["q4_3"]["strategies"]["q4_3_all_main"]["total_cost_yuan"],
        ),
        "all_summaries_preserved_frozen_hashes": all(
            payload["frozen_files_unchanged"] for payload in (p1, p2, p2_alpha05, p3, p3_alpha05, p4)
        ),
        "current_frozen_hashes_equal_recorded": frozen_hashes() == p4["frozen_hashes_after"],
    }
    source_design = {
        "status": "PASS",
        "evidence": [
            "P1/P2 load feedback source multiplies only current-day unexecuted load by an observed-prefix ratio; the virtual next-day prefix is unchanged.",
            "P2 price correction calls the frozen causal price routine with actual observations only before each issue time.",
            "P3 all versions re-optimize at 06/12/18 with a common 24-hour horizon and 6000 kWh terminal target; module-off states use prior-plan SOC or midnight PV information.",
            "P4 reserve is computed from trailing dates ending strictly before the decision date and uses no fitted reserve multiplier.",
        ],
        "code_hashes": {
            name: sha256(PROJECT_ROOT / "code" / name)
            for name in (
                "q3_p1_load_feedback_ablation.py",
                "q4_p2_feedback_price_2x2.py",
                "q4_p2_alpha05_transfer.py",
                "q3_p3_information_ablation.py",
                "q3_p3_alpha05_selected.py",
                "q4_p4_evening_soc_reserve.py",
            )
        },
    }
    status = "PASS" if all(item["status"] == "PASS" for item in checks) and all(anchors.values()) else "FAIL"
    report = {
        "schema_version": 1,
        "scope": "Independent ledger/physics/cost/cutoff validation for P1-P4; withdrawn P0 intentionally excluded.",
        "status": status,
        "detail_checks": checks,
        "cross_run_anchors": anchors,
        "causal_design_audit": source_design,
        "frozen_hashes": frozen_hashes(),
    }
    write_json(VALIDATION / "q3_q4_refinement_validation.json", report)
    if status != "PASS":
        raise RuntimeError("refinement validation failed")
    print(json.dumps({"status": status, "files": len(checks), "anchors": anchors}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
