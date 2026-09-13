from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

from common_data import PROJECT_ROOT, load_attachment2, sha256
from dispatch_core import FLOW_MAX_KWH, POSITIVE_TOL_KWH, SOC_MAX, SOC_MIN, SOLVER_TOL_KWH
import q2_solve as q2


RESULTS = PROJECT_ROOT / "results"
VALIDATION = PROJECT_ROOT / "validation"
EXPECTED = {
    "q3_feedback_none": (), "q3_feedback_6": (6,), "q3_feedback_12": (12,),
    "q3_feedback_18": (18,), "q3_feedback_6_12": (6, 12),
    "q3_feedback_6_18": (6, 18), "q3_feedback_12_18": (12, 18),
    "q3_feedback_6_12_18": (6, 12, 18),
}


def rows(path: Path):
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        yield from csv.DictReader(stream)


def main() -> None:
    summary_path = RESULTS / "q3_load_feedback_candidate_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    annual = load_attachment2()
    dates = annual["dates"]
    load_kw, pv_kw = annual["load_kw"], annual["pv_kw"]
    date_index = {day.isoformat(): idx for idx, day in enumerate(dates)}
    base_cache = {}
    ratio_cache = {}

    detail_count = defaultdict(int)
    used_issues = defaultdict(set)
    max_checks = defaultdict(float)
    sums = defaultdict(lambda: defaultdict(float))
    violations = defaultdict(int)
    detail_path = PROJECT_ROOT / summary["files"]["detail"]
    for row in rows(detail_path):
        strategy = row["strategy"]
        detail_count[strategy] += 1
        day_idx = date_index[row["date"]]
        slot = int(row["slot"]) - 1
        issue_hour = int(row["executed_plan_issue_time"].split(":")[0])
        issue_slot = issue_hour * 6
        used_issues[strategy].add(issue_hour)
        if slot < issue_slot:
            violations["future_plan_used_on_past_slot"] += 1
        if int(row["load_observed_through_slot"]) != issue_slot:
            violations["observed_cutoff_label"] += 1
        base = base_cache.setdefault(day_idx, q2.weekday_weighted_forecast(load_kw, dates, day_idx, dates[day_idx], "linear"))
        expected_ratio = ratio_cache.get((day_idx, issue_hour))
        if expected_ratio is None:
            expected_ratio = 1.0 if issue_slot == 0 else float(np.sum(load_kw[day_idx, :issue_slot]) / np.sum(base[:issue_slot]))
            ratio_cache[(day_idx, issue_hour)] = expected_ratio
        logged_ratio = float(row["load_feedback_ratio"])
        max_checks["feedback_ratio_abs"] = max(max_checks["feedback_ratio_abs"], abs(logged_ratio - expected_ratio))
        max_checks["base_load_abs_kw"] = max(max_checks["base_load_abs_kw"], abs(float(row["base_forecast_load_kw"]) - base[slot]))
        max_checks["feedback_load_abs_kw"] = max(max_checks["feedback_load_abs_kw"], abs(float(row["forecast_load_kw"]) - base[slot] * expected_ratio))
        max_checks["source_load_abs_kw"] = max(max_checks["source_load_abs_kw"], abs(float(row["actual_load_kw"]) - load_kw[day_idx, slot]))
        max_checks["source_pv_abs_kw"] = max(max_checks["source_pv_abs_kw"], abs(float(row["actual_pv_kw"]) - pv_kw[day_idx, slot]))
        for field, name in (("balance_residual_kwh", "balance"), ("state_residual_kwh", "state")):
            max_checks[name] = max(max_checks[name], abs(float(row[field])))
        charge = float(row["charge_bus_kwh"]); discharge = float(row["discharge_bus_kwh"])
        emergency = float(row["emergency_purchase_kwh"])
        max_checks["charge_kwh"] = max(max_checks["charge_kwh"], charge)
        max_checks["discharge_kwh"] = max(max_checks["discharge_kwh"], discharge)
        soc_open = float(row["soc_open_kwh"]); soc_close = float(row["soc_close_kwh"])
        max_checks["soc_above_max"] = max(max_checks["soc_above_max"], soc_open - SOC_MAX, soc_close - SOC_MAX)
        max_checks["soc_below_min"] = max(max_checks["soc_below_min"], SOC_MIN - soc_open, SOC_MIN - soc_close)
        if charge > POSITIVE_TOL_KWH and discharge > POSITIVE_TOL_KWH:
            violations["simultaneous_charge_discharge"] += 1
        if emergency > POSITIVE_TOL_KWH and charge > POSITIVE_TOL_KWH:
            violations["emergency_charge_overlap"] += 1
        q0 = float(row["original_purchase_kwh"]); q = float(row["effective_purchase_kwh"])
        up = max(q - q0, 0.0); down = max(q0 - q, 0.0)
        price = float(row["actual_price_yuan_per_kwh"])
        expected_total = price * q0 - 0.5 * price * down + 1.5 * price * up + 5.0 * price * emergency
        max_checks["settlement_abs_yuan"] = max(max_checks["settlement_abs_yuan"], abs(expected_total - float(row["total_cost_yuan"])))
        for field in ("original_purchase_kwh", "effective_purchase_kwh", "upward_adjustment_kwh", "downward_adjustment_kwh", "emergency_purchase_kwh", "total_cost_yuan"):
            sums[strategy][field] += float(row[field])

    version_count = defaultdict(int)
    version_last = {}
    versions_path = PROJECT_ROOT / summary["files"]["plan_versions"]
    for row in rows(versions_path):
        strategy = row["strategy"]
        version_count[strategy] += 1
        issue_slot = int(row["issue_slot"]); target_slot = int(row["target_slot"])
        if issue_slot > 0 and target_slot <= issue_slot:
            violations["past_slot_revised"] += 1
        if int(row["load_observed_through_slot"]) != issue_slot:
            violations["version_observed_cutoff_label"] += 1
        key = (strategy, row["date"], target_slot)
        expected_previous = version_last.get(key, float(row["original_plan_kwh"]))
        max_checks["version_previous_link_kwh"] = max(max_checks["version_previous_link_kwh"], abs(float(row["previous_effective_plan_kwh"]) - expected_previous))
        max_checks["version_increment_link_kwh"] = max(max_checks["version_increment_link_kwh"], abs(float(row["incremental_change_kwh"]) - (float(row["new_effective_plan_kwh"]) - expected_previous)))
        version_last[key] = float(row["new_effective_plan_kwh"])

    aggregate_checks = {}
    for strategy, hours in EXPECTED.items():
        agg = summary["strategies"][strategy]
        aggregate_checks[strategy] = {
            field: abs(sums[strategy][field] - float(agg[field]))
            for field in ("original_purchase_kwh", "effective_purchase_kwh", "upward_adjustment_kwh", "downward_adjustment_kwh", "emergency_purchase_kwh", "total_cost_yuan")
        }
        expected_versions = 334 * (144 + sum(144 - hour * 6 for hour in hours))
        if version_count[strategy] != expected_versions:
            violations["version_row_count"] += 1
        allowed_issues = {0, *hours}
        if used_issues[strategy] - allowed_issues:
            violations["disabled_issue_used"] += 1

    frozen_recomputed = {path: sha256(PROJECT_ROOT / path) for path in summary["frozen_hashes_before"]}
    frozen_ok = frozen_recomputed == summary["frozen_hashes_before"] == summary["frozen_hashes_after"]
    max_aggregate_error = max(v for fields in aggregate_checks.values() for v in fields.values())
    pass_flags = {
        "eight_subsets_present": set(summary["strategies"]) == set(EXPECTED),
        "detail_rows_complete": all(detail_count[s] == 334 * 144 for s in EXPECTED),
        "version_rows_complete": violations["version_row_count"] == 0,
        "information_cutoff_and_past_lock": violations["future_plan_used_on_past_slot"] == 0 and violations["past_slot_revised"] == 0,
        "feedback_reconstructs_from_observed_prefix": max_checks["feedback_ratio_abs"] <= 1e-12 and max_checks["feedback_load_abs_kw"] <= 1e-8,
        "source_data_matches": max_checks["source_load_abs_kw"] <= 1e-10 and max_checks["source_pv_abs_kw"] <= 1e-10,
        "balance_and_state": max_checks["balance"] <= SOLVER_TOL_KWH and max_checks["state"] <= SOLVER_TOL_KWH,
        "soc_bounds": max_checks["soc_above_max"] <= SOLVER_TOL_KWH and max_checks["soc_below_min"] <= SOLVER_TOL_KWH,
        "power_bounds": max_checks["charge_kwh"] <= FLOW_MAX_KWH + SOLVER_TOL_KWH and max_checks["discharge_kwh"] <= FLOW_MAX_KWH + SOLVER_TOL_KWH,
        "no_forbidden_flow_overlap": violations["simultaneous_charge_discharge"] == 0 and violations["emergency_charge_overlap"] == 0,
        "a08_settlement_recomputes": max_checks["settlement_abs_yuan"] <= 1e-8,
        "version_chain_recomputes": max_checks["version_previous_link_kwh"] <= 1e-10 and max_checks["version_increment_link_kwh"] <= 1e-10,
        "aggregates_recompute": max_aggregate_error <= 1e-6,
        "disabled_updates_not_used": violations["disabled_issue_used"] == 0,
        "frozen_q1_q2_q3_q4_files_unchanged": frozen_ok,
    }
    report = {
        "status": "PASS" if all(pass_flags.values()) else "FAIL",
        "pass_flags": pass_flags,
        "violations": dict(violations),
        "max_checks": dict(max_checks),
        "aggregate_max_abs_error": max_aggregate_error,
        "detail_rows": dict(detail_count),
        "version_rows": dict(version_count),
        "candidate_decision": summary["decision"],
        "candidate_summary_sha256": sha256(summary_path),
        "candidate_code_sha256": sha256(PROJECT_ROOT / "code/q3_load_feedback_candidate.py"),
        "frozen_hashes_recomputed": frozen_recomputed,
    }
    output = VALIDATION / "q3_load_feedback_candidate_validation.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if report["status"] != "PASS":
        raise SystemExit(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps({"status": report["status"], "output": str(output), "pass_flags": pass_flags}, ensure_ascii=False))


if __name__ == "__main__":
    main()
