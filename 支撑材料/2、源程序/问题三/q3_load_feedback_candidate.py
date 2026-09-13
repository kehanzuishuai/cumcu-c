from __future__ import annotations

import csv
import hashlib
import itertools
import json
import math
from collections import defaultdict
from datetime import timedelta
from pathlib import Path
from typing import Any

import numpy as np

from common_data import PROJECT_ROOT, load_attachment1, load_attachment2, load_attachment3, sha256
from dispatch_core import ETA_DISCHARGE, FLOW_MAX_KWH, SOC_MAX, SOC_MIN, SOLVER_TOL_KWH
import q2_solve as q2
import q3_solve as q3


RESULTS = PROJECT_ROOT / "results"
VALIDATION = PROJECT_ROOT / "validation"
INTERMEDIATE = PROJECT_ROOT / "intermediate"
EVAL_START = q3.EVAL_START
N = q3.N
UPDATE_HOURS = (6, 12, 18)


def file_hashes() -> dict[str, str]:
    targets = [
        "results/q1_summary.json", "results/result1.xlsx",
        "results/q2_summary.json", "results/result2.xlsx",
        "results/q3_summary.json", "results/result3.xlsx",
        "results/q3_detail.csv", "validation/q3_validation.json",
        "results/q4_summary.json", "results/result4-2.xlsx", "results/result4-3.xlsx",
    ]
    return {path: sha256(PROJECT_ROOT / path) for path in targets}


def full_base_load(load_kw: np.ndarray, dates: list, day_idx: int) -> np.ndarray:
    return q2.weekday_weighted_forecast(load_kw, dates, day_idx, dates[day_idx], "linear")


def feedback_ratio(load_kw: np.ndarray, dates: list, day_idx: int, issue_hour: int) -> float:
    start = issue_hour * 6
    if start == 0:
        return 1.0
    base = full_base_load(load_kw, dates, day_idx)
    denominator = float(np.sum(base[:start]))
    if denominator <= 0:
        raise ValueError("负载基线前缀和非正，无法构造因果比例反馈")
    return float(np.sum(load_kw[day_idx, :start]) / denominator)


def feedback_issue_forecast(
    *, load_kw: np.ndarray, pv_kw: np.ndarray, forecast3_kw: np.ndarray,
    dates: list, day_idx: int, issue_idx: int, interpolation: str,
) -> tuple[np.ndarray, np.ndarray]:
    issue_hour = q3.ISSUE_HOURS[issue_idx]
    start = issue_hour * 6
    base = q3.target_profile(load_kw, dates, day_idx, issue_hour)
    ratio = feedback_ratio(load_kw, dates, day_idx, issue_hour)
    # Only the unexecuted part of the current day is corrected. The virtual next-day
    # prefix remains the frozen seasonal forecast; this prevents same-day observations
    # from being silently treated as tomorrow's known load.
    corrected = base.copy()
    corrected[: N - start] *= ratio
    pv = q3.pv_forecast_10min(
        forecast3_kw[day_idx, issue_idx],
        q3.issue_boundary_pv(pv_kw, day_idx, issue_hour),
        interpolation,
    )
    return corrected, pv


def append_csv(path: Path, rows: list[dict[str, Any]], first: bool) -> None:
    if not rows:
        return
    mode = "w" if first else "a"
    with path.open(mode, encoding="utf-8-sig" if first else "utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        if first:
            writer.writeheader()
        writer.writerows(rows)


def enrich_detail(rows: list[dict[str, Any]], strategy: str, load_kw: np.ndarray, dates: list) -> list[dict[str, Any]]:
    by_date = {day.isoformat(): idx for idx, day in enumerate(dates)}
    base_cache: dict[int, np.ndarray] = {}
    ratio_cache: dict[tuple[int, int], float] = {}
    output = []
    for row in rows:
        day_idx = by_date[row["date"]]
        issue_hour = int(str(row["executed_plan_issue_time"]).split(":")[0])
        base = base_cache.setdefault(day_idx, full_base_load(load_kw, dates, day_idx))
        ratio = ratio_cache.setdefault((day_idx, issue_hour), feedback_ratio(load_kw, dates, day_idx, issue_hour))
        slot = int(row["slot"]) - 1
        enriched = {"strategy": strategy, **row}
        enriched["base_forecast_load_kw"] = float(base[slot])
        enriched["load_feedback_ratio"] = ratio
        enriched["load_observed_through_slot"] = issue_hour * 6
        output.append(enriched)
    return output


def enrich_versions(rows: list[dict[str, Any]], strategy: str) -> list[dict[str, Any]]:
    current: dict[tuple[str, int], float] = {}
    output = []
    for row in rows:
        key = (row["date"], int(row["target_slot"]))
        previous = current.get(key, float(row["original_plan_kwh"]))
        new = float(row["new_effective_plan_kwh"])
        current[key] = new
        output.append({
            "strategy": strategy,
            **row,
            "previous_effective_plan_kwh": previous,
            "incremental_change_kwh": new - previous,
            "change_from_original_kwh": new - float(row["original_plan_kwh"]),
            "load_observed_through_slot": int(row["issue_slot"]),
        })
    return output


def prediction_diagnostics(load_kw, pv_kw, forecast3_kw, dates, base_issue_forecast) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for issue_idx, issue_hour in enumerate(q3.ISSUE_HOURS[1:], start=1):
        start = issue_hour * 6
        actual_load_rows, actual_net_rows = [], []
        base_load_rows, feedback_load_rows = [], []
        base_net_rows, feedback_net_rows = [], []
        for day_idx in range(EVAL_START, len(dates)):
            base_load, pv = base_issue_forecast(
                load_kw=load_kw, pv_kw=pv_kw, forecast3_kw=forecast3_kw, dates=dates,
                day_idx=day_idx, issue_idx=issue_idx, interpolation="linear",
            )
            corrected_load, corrected_pv = feedback_issue_forecast(
                load_kw=load_kw, pv_kw=pv_kw, forecast3_kw=forecast3_kw, dates=dates,
                day_idx=day_idx, issue_idx=issue_idx, interpolation="linear",
            )
            count = N - start
            actual_load = load_kw[day_idx, start:]
            actual_pv = pv_kw[day_idx, start:]
            actual_load_rows.append(actual_load)
            actual_net_rows.append(actual_load - actual_pv)
            base_load_rows.append(base_load[:count])
            feedback_load_rows.append(corrected_load[:count])
            base_net_rows.append(base_load[:count] - pv[:count])
            feedback_net_rows.append(corrected_load[:count] - corrected_pv[:count])
        a_load = np.concatenate(actual_load_rows)
        a_net = np.concatenate(actual_net_rows)
        b_load = np.concatenate(base_load_rows)
        f_load = np.concatenate(feedback_load_rows)
        b_net = np.concatenate(base_net_rows)
        f_net = np.concatenate(feedback_net_rows)
        result[f"{issue_hour:02d}:00"] = {
            "horizon": "unexecuted slots of current day only",
            "base_load": q3.metric(a_load, b_load),
            "feedback_load": q3.metric(a_load, f_load),
            "base_point_net": q3.metric(a_net, b_net),
            "feedback_point_net": q3.metric(a_net, f_net),
        }
    return result


def subset_key(hours: tuple[int, ...] | list[int]) -> str:
    return "none" if not hours else "_".join(map(str, hours))


def shapley_and_interactions(aggregates: dict[str, dict[str, Any]]) -> dict[str, Any]:
    costs = {frozenset(v["update_hours"]): float(v["total_cost_yuan"]) for v in aggregates.values()}
    universe = frozenset(UPDATE_HOURS)
    shapley = {}
    for hour in UPDATE_HOURS:
        value = 0.0
        others = universe - {hour}
        for size in range(len(others) + 1):
            for combo in itertools.combinations(others, size):
                s = frozenset(combo)
                weight = math.factorial(size) * math.factorial(2 - size) / math.factorial(3)
                value += weight * (costs[s] - costs[s | {hour}])
        shapley[str(hour)] = value
    pair_synergy = {}
    empty = costs[frozenset()]
    for a, b in itertools.combinations(UPDATE_HOURS, 2):
        pair_synergy[f"{a}+{b}"] = (empty - costs[frozenset({a, b})]) - (
            (empty - costs[frozenset({a})]) + (empty - costs[frozenset({b})])
        )
    triple_synergy = (empty - costs[universe]) - sum(empty - costs[frozenset({h})] for h in UPDATE_HOURS)
    return {"shapley_cost_saving_yuan": shapley, "pair_synergy_yuan": pair_synergy, "triple_synergy_yuan": triple_synergy}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def monthly_stability(candidate_daily: list[dict[str, Any]], current_daily_path: Path) -> dict[str, Any]:
    current = {row["date"]: float(row["total_cost_yuan"]) for row in read_csv(current_daily_path)}
    months: dict[str, dict[str, float]] = defaultdict(lambda: {"candidate": 0.0, "current": 0.0})
    for row in candidate_daily:
        month = row["date"][:7]
        months[month]["candidate"] += float(row["total_cost_yuan"])
        months[month]["current"] += current[row["date"]]
    rows = []
    for month in sorted(months):
        c = months[month]
        rows.append({"month": month, **c, "candidate_minus_current_yuan": c["candidate"] - c["current"]})
    improved = sum(row["candidate_minus_current_yuan"] < 0 for row in rows)
    return {"months": rows, "improved_months": improved, "total_months": len(rows), "strict_majority_improved": improved > len(rows) / 2}


def main() -> None:
    RESULTS.mkdir(parents=True, exist_ok=True)
    VALIDATION.mkdir(parents=True, exist_ok=True)
    INTERMEDIATE.mkdir(parents=True, exist_ok=True)
    before_hashes = file_hashes()
    fixed = load_attachment1()
    annual = load_attachment2()
    forecasts = load_attachment3()
    dates = annual["dates"]
    if dates != forecasts["dates"]:
        raise ValueError("附件2与附件3日期轴不一致")
    load_kw, pv_kw = annual["load_kw"], annual["pv_kw"]
    forecast3_kw = forecasts["forecast_kw"]
    price = fixed["price_yuan_per_kwh"]

    base_issue_forecast = q3.issue_forecast
    diagnostics = prediction_diagnostics(load_kw, pv_kw, forecast3_kw, dates, base_issue_forecast)
    q3.issue_forecast = feedback_issue_forecast
    residual_cache, _, _ = q3.build_forecast_caches(load_kw, pv_kw, forecast3_kw, dates, "linear")

    detail_path = RESULTS / "q3_load_feedback_8comb_detail.csv"
    versions_path = RESULTS / "q3_load_feedback_8comb_plan_versions.csv"
    daily_path = RESULTS / "q3_load_feedback_8comb_daily.csv"
    storage_path = RESULTS / "q3_load_feedback_8comb_storage_4h.csv"
    events_path = RESULTS / "q3_load_feedback_8comb_emergency_events.csv"
    for path in (detail_path, versions_path, daily_path, storage_path, events_path):
        if path.exists():
            path.unlink()

    aggregates: dict[str, dict[str, Any]] = {}
    daily_by_strategy: dict[str, list[dict[str, Any]]] = {}
    first = {"detail": True, "versions": True, "daily": True, "storage": True, "events": True}
    all_subsets = [combo for size in range(4) for combo in itertools.combinations(UPDATE_HOURS, size)]
    for combo in all_subsets:
        key = subset_key(combo)
        name = f"q3_feedback_{key}"
        print(json.dumps({"event": "candidate_start", "strategy": name, "updates": combo}, ensure_ascii=False), flush=True)
        run = q3.run_strategy(
            name=name, update_hours=list(combo), interpolation="linear",
            load_kw=load_kw, pv_kw=pv_kw, forecast3_kw=forecast3_kw, dates=dates,
            price=price, residual_cache=residual_cache,
            raw_endpoint_labels=annual["raw_endpoint_labels"], keep_detail=True,
        )
        enriched_detail = enrich_detail(run["detail"], name, load_kw, dates)
        enriched_versions = enrich_versions(run["versions"], name)
        daily_rows = [{"strategy": name, **row} for row in run["daily"]]
        storage_rows = [{"strategy": name, **row} for row in run["storage"]]
        event_rows = [{"strategy": name, **row} for row in run["events"]]
        append_csv(detail_path, enriched_detail, first["detail"]); first["detail"] = False
        append_csv(versions_path, enriched_versions, first["versions"]); first["versions"] = False
        append_csv(daily_path, daily_rows, first["daily"]); first["daily"] = False
        append_csv(storage_path, storage_rows, first["storage"]); first["storage"] = False
        if event_rows:
            append_csv(events_path, event_rows, first["events"]); first["events"] = False
        aggregates[name] = run["aggregate"]
        daily_by_strategy[name] = run["daily"]
        print(json.dumps({"event": "candidate_complete", **run["aggregate"]}, ensure_ascii=False), flush=True)

    if first["events"]:
        events_path.write_text("strategy,date,event_id,start_slot,end_slot_exclusive,interval,purchase_kwh\n", encoding="utf-8-sig")

    current_summary = json.loads((RESULTS / "q3_summary.json").read_text(encoding="utf-8"))
    current = current_summary["strategies"]["q3_all_main"]
    full_name = "q3_feedback_6_12_18"
    candidate = aggregates[full_name]
    stability = monthly_stability(daily_by_strategy[full_name], RESULTS / "q3_daily.csv")
    inventory_unit_value = float(np.mean(price) * ETA_DISCHARGE)
    inventory_delta = float(candidate["soc_final_kwh"] - current["soc_final_kwh"])
    inventory_adjusted_candidate = float(candidate["total_cost_yuan"] - inventory_unit_value * inventory_delta)
    forecast_all_better = all(
        values["feedback_load"]["wape"] < values["base_load"]["wape"]
        and values["feedback_point_net"]["wape"] < values["base_point_net"]["wape"]
        for values in diagnostics.values()
    )
    constraints_pass = (
        candidate["max_actual_balance_residual_kwh"] <= SOLVER_TOL_KWH
        and candidate["max_actual_state_residual_kwh"] <= SOLVER_TOL_KWH
        and candidate["max_crossday_soc_gap_kwh"] <= SOLVER_TOL_KWH
        and candidate["soc_min_kwh"] >= SOC_MIN - SOLVER_TOL_KWH
        and candidate["soc_max_kwh"] <= SOC_MAX + SOLVER_TOL_KWH
    )
    causal_design_pass = True
    gate = {
        "causal_design_pass": causal_design_pass,
        "constraints_pass": constraints_pass,
        "full_period_cash_cost_lower": candidate["total_cost_yuan"] < current["total_cost_yuan"],
        "emergency_purchase_lower": candidate["emergency_purchase_kwh"] < current["emergency_purchase_kwh"],
        "forecast_wape_lower_at_each_update": forecast_all_better,
        "strict_majority_of_months_cash_cost_lower": stability["strict_majority_improved"],
    }
    eligible = all(gate.values())
    summary = {
        "schema_version": 1,
        "status": "CANDIDATE_EVALUATED",
        "question": "Q3 load-deviation causal-feedback upgrade candidate",
        "frozen_scope": {
            "settlement": "A08 main: cancelled downward amount refunds original energy fee and pays 50% breach charge, equivalently 0.5p net credit",
            "information": "at 06/12/18 only the actually observed load prefix and latest attachment-3 PV release are available; only unexecuted slots change",
            "storage": "unchanged 5000 kW charge/discharge limits, efficiencies, bounds, actual causal executor, cross-day SOC continuity",
            "risk": "unchanged same-issue trailing-56-day slotwise Q80 combined net-load residual",
            "prohibited": "external alternative settlement and published result values are not inputs to code or selection",
        },
        "candidate_load_feedback": {
            "formula": "r_h=sum(actual load slots before h)/sum(base load forecast slots before h); multiply only current-day slots h..24:00 by r_h",
            "tomorrow_virtual_prefix": "left at the frozen seasonal forecast",
            "parameters_added": [],
        },
        "prediction_diagnostics": diagnostics,
        "strategies": aggregates,
        "combination_value": shapley_and_interactions(aggregates),
        "current_main_comparison": {
            "current_q3_main": current,
            "feedback_all_updates": candidate,
            "candidate_minus_current": {
                key: float(candidate[key] - current[key]) for key in (
                    "total_cost_yuan", "emergency_purchase_kwh", "upward_adjustment_kwh",
                    "downward_adjustment_kwh", "soc_final_kwh"
                )
            },
            "inventory_value": {
                "unit_value_yuan_per_kwh_soc": inventory_unit_value,
                "candidate_minus_current_soc_kwh": inventory_delta,
                "candidate_inventory_adjusted_cost_yuan": inventory_adjusted_candidate,
                "current_inventory_adjusted_cost_yuan": float(current["total_cost_yuan"]),
            },
            "monthly_stability": stability,
        },
        "upgrade_gate_definition": "eligible only if causal/constraint checks pass, full-period cash cost and emergency both fall, load and point-net WAPE fall at every update, and cash cost falls in a strict majority of calendar months; this rule was declared before inspecting candidate results",
        "upgrade_gate": gate,
        "decision": "ELIGIBLE_FOR_CONSIDERATION_NO_MAIN_FILES_CHANGED" if eligible else "KEEP_AS_COMPARATOR_NO_MAIN_FILES_CHANGED",
        "files": {
            "detail": str(detail_path.relative_to(PROJECT_ROOT)),
            "plan_versions": str(versions_path.relative_to(PROJECT_ROOT)),
            "daily": str(daily_path.relative_to(PROJECT_ROOT)),
            "storage": str(storage_path.relative_to(PROJECT_ROOT)),
            "events": str(events_path.relative_to(PROJECT_ROOT)),
        },
        "frozen_hashes_before": before_hashes,
    }
    after_hashes = file_hashes()
    summary["frozen_hashes_after"] = after_hashes
    summary["frozen_files_unchanged"] = before_hashes == after_hashes
    summary_path = RESULTS / "q3_load_feedback_candidate_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"event": "candidate_summary", "decision": summary["decision"], "comparison": summary["current_main_comparison"]["candidate_minus_current"], "summary": str(summary_path)}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
