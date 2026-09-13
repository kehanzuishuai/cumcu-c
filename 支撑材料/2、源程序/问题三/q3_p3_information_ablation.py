from __future__ import annotations

import json
from collections import defaultdict

import numpy as np

from common_data import load_attachment1, load_attachment2, load_attachment3
import q3_solve as q3
from refinement_common import RESULTS, ensure_dirs, frozen_hashes, write_csv, write_json


N = q3.N


def make_information_forecast(load_feedback: bool, new_pv_release: bool, alpha: float = 1.0):
    def forecast(*, load_kw, pv_kw, forecast3_kw, dates, day_idx, issue_idx, interpolation):
        issue_hour = q3.ISSUE_HOURS[issue_idx]
        start = issue_hour * 6
        load = q3.target_profile(load_kw, dates, day_idx, issue_hour)
        if load_feedback and start:
            full_base = q3.q2.weekday_weighted_forecast(load_kw, dates, day_idx, dates[day_idx], "linear")
            raw_ratio = float(np.sum(load_kw[day_idx, :start]) / np.sum(full_base[:start]))
            ratio = 1.0 + alpha * (raw_ratio - 1.0)
            load[: N - start] *= ratio
        if new_pv_release or start == 0:
            pv = q3.pv_forecast_10min(
                forecast3_kw[day_idx, issue_idx],
                q3.issue_boundary_pv(pv_kw, day_idx, issue_hour),
                interpolation,
            )
        else:
            midnight = q3.pv_forecast_10min(
                forecast3_kw[day_idx, 0],
                q3.issue_boundary_pv(pv_kw, day_idx, 0),
                interpolation,
            )
            tomorrow = np.mean(pv_kw[max(0, day_idx - 5):day_idx], axis=0)
            pv = np.concatenate([midnight[start:], tomorrow[:start]])
        return load, pv
    return forecast


class PlannedStatePatch:
    """Hide realized SOC from re-optimizers while preserving actual physical execution."""

    def __init__(self, deterministic, adjusted):
        self.deterministic = deterministic
        self.adjusted = adjusted
        self.q0_soc = None
        self.last_adjusted_soc = None

    def solve_deterministic(self, *args, **kwargs):
        result = self.deterministic(*args, **kwargs)
        self.q0_soc = result.soc.copy()
        self.last_adjusted_soc = None
        return result

    def solve_adjusted(self, net, price, actual_soc, terminal_soc, original, adjustable_count):
        start = N - adjustable_count
        if self.q0_soc is None:
            raise RuntimeError("missing q0 planned SOC")
        if self.last_adjusted_soc is None:
            model_soc = float(self.q0_soc[start])
        else:
            elapsed = 36
            model_soc = float(self.last_adjusted_soc[elapsed])
        result = self.adjusted(net, price, model_soc, terminal_soc, original, adjustable_count)
        self.last_adjusted_soc = result.soc.copy()
        return result


def main() -> None:
    ensure_dirs()
    before = frozen_hashes()
    fixed = load_attachment1()
    annual = load_attachment2()
    forecasts = load_attachment3()
    dates = annual["dates"]
    native_issue = q3.issue_forecast
    native_det = q3.solve_deterministic_plan
    native_adj = q3.solve_adjusted_plan
    specs = [
        ("none", False, False, False),
        ("state_only", True, False, False),
        ("pv_only", False, True, False),
        ("load_only", False, False, True),
        ("state_pv", True, True, False),
        ("all_three", True, True, True),
    ]
    runs = {}
    for label, state_update, pv_update, load_feedback in specs:
        q3.issue_forecast = make_information_forecast(load_feedback, pv_update)
        state_patch = PlannedStatePatch(native_det, native_adj)
        q3.solve_deterministic_plan = native_det if state_update else state_patch.solve_deterministic
        q3.solve_adjusted_plan = native_adj if state_update else state_patch.solve_adjusted
        residual, _, _ = q3.build_forecast_caches(
            annual["load_kw"], annual["pv_kw"], forecasts["forecast_kw"], dates, "linear"
        )
        print(json.dumps({"event": "start", "strategy": label}, ensure_ascii=False), flush=True)
        run = q3.run_strategy(
            name=f"p3_{label}",
            update_hours=[6, 12, 18],
            interpolation="linear",
            load_kw=annual["load_kw"],
            pv_kw=annual["pv_kw"],
            forecast3_kw=forecasts["forecast_kw"],
            dates=dates,
            price=fixed["price_yuan_per_kwh"],
            residual_cache=residual,
            raw_endpoint_labels=annual["raw_endpoint_labels"],
            keep_detail=True,
        )
        runs[label] = run
        write_csv(RESULTS / f"p3_{label}_detail.csv", run["detail"])
        write_csv(RESULTS / f"p3_{label}_daily.csv", run["daily"])
        print(json.dumps({"event": "done", "strategy": label, **run["aggregate"]}, ensure_ascii=False), flush=True)
    q3.issue_forecast = native_issue
    q3.solve_deterministic_plan = native_det
    q3.solve_adjusted_plan = native_adj

    base = runs["none"]["aggregate"]
    effects = {}
    for label in ("state_only", "pv_only", "load_only", "state_pv", "all_three"):
        agg = runs[label]["aggregate"]
        effects[label] = {
            "total_cost_delta_yuan": agg["total_cost_yuan"] - base["total_cost_yuan"],
            "emergency_delta_kwh": agg["emergency_purchase_kwh"] - base["emergency_purchase_kwh"],
            "discard_delta_kwh": agg["surplus_discard_kwh"] - base["surplus_discard_kwh"],
            "terminal_soc_delta_kwh": agg["soc_final_kwh"] - base["soc_final_kwh"],
        }
    monthly = defaultdict(dict)
    for label, run in runs.items():
        bucket = defaultdict(float)
        for row in run["daily"]:
            bucket[row["date"][:7]] += float(row["total_cost_yuan"])
        for month, cost in bucket.items():
            monthly[month][label] = cost
    monthly_rows = []
    for month in sorted(monthly):
        row = {"month": month}
        for label, *_ in specs:
            row[f"{label}_total_cost_yuan"] = monthly[month][label]
        monthly_rows.append(row)
    write_csv(RESULTS / "p3_information_ablation_monthly.csv", monthly_rows)
    after = frozen_hashes()
    summary = {
        "schema_version": 1,
        "experiment": "P3 same-clock information-module ablation",
        "common_design": {
            "update_times": ["06:00", "12:00", "18:00"],
            "optimization_horizon": "24 hours after each update for every version",
            "terminal_soc": "6000 kWh at the common 24-hour horizon endpoint for every version",
            "settlement": "A08 frozen refund interpretation",
            "risk": "same Q80 method, rebuilt causally for each forecast-information set",
        },
        "module_definition": {
            "state": "use realized SOC at each update; off uses the prior plan-predicted SOC",
            "pv": "use latest attachment-3 release; off continues the 00:00 PV forecast for today and the same past-5-day mean for the virtual next-day prefix",
            "load": "alpha=1 causal same-day observed-prefix ratio on unexecuted current-day load only",
        },
        "runs": {label: run["aggregate"] for label, run in runs.items()},
        "effects_relative_to_no_information_modules": effects,
        "anchors": {
            "state_pv_should_equal_frozen_q3_main": True,
            "all_three_should_equal_existing_alpha1_candidate": True,
        },
        "frozen_files_unchanged": before == after,
        "frozen_hashes_before": before,
        "frozen_hashes_after": after,
    }
    write_json(RESULTS / "p3_information_ablation_summary.json", summary)
    print(json.dumps({"event": "summary", "effects": effects}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
