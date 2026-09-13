from __future__ import annotations

import json
from collections import defaultdict

import numpy as np

from common_data import load_attachment1, load_attachment2, load_attachment3
import q3_solve as q3
from refinement_common import RESULTS, ensure_dirs, frozen_hashes, write_csv, write_json


N = q3.N


def make_issue_forecast(alpha: float):
    def forecast(*, load_kw, pv_kw, forecast3_kw, dates, day_idx, issue_idx, interpolation):
        issue_hour = q3.ISSUE_HOURS[issue_idx]
        start = issue_hour * 6
        base = q3.target_profile(load_kw, dates, day_idx, issue_hour)
        corrected = base.copy()
        if start:
            full_base = q3.q2.weekday_weighted_forecast(load_kw, dates, day_idx, dates[day_idx], "linear")
            ratio_raw = float(np.sum(load_kw[day_idx, :start]) / np.sum(full_base[:start]))
            ratio = 1.0 + alpha * (ratio_raw - 1.0)
            corrected[: N - start] *= ratio
        pv = q3.pv_forecast_10min(
            forecast3_kw[day_idx, issue_idx],
            q3.issue_boundary_pv(pv_kw, day_idx, issue_hour),
            interpolation,
        )
        return corrected, pv
    return forecast


def diagnostics(alpha: float, load_kw, pv_kw, forecast3_kw, dates) -> dict:
    issue_forecast = make_issue_forecast(alpha)
    output = {}
    for issue_idx, issue_hour in enumerate(q3.ISSUE_HOURS[1:], start=1):
        start = issue_hour * 6
        actual_load_rows = []
        forecast_load_rows = []
        actual_net_rows = []
        forecast_net_rows = []
        monthly = defaultdict(lambda: {"actual_load": [], "forecast_load": [], "actual_net": [], "forecast_net": []})
        for day_idx in range(q3.EVAL_START, len(dates)):
            forecast_load, forecast_pv = issue_forecast(
                load_kw=load_kw, pv_kw=pv_kw, forecast3_kw=forecast3_kw, dates=dates,
                day_idx=day_idx, issue_idx=issue_idx, interpolation="linear",
            )
            count = N - start
            actual_load = load_kw[day_idx, start:]
            actual_net = actual_load - pv_kw[day_idx, start:]
            f_load = forecast_load[:count]
            f_net = f_load - forecast_pv[:count]
            actual_load_rows.append(actual_load); forecast_load_rows.append(f_load)
            actual_net_rows.append(actual_net); forecast_net_rows.append(f_net)
            bucket = monthly[dates[day_idx].strftime("%Y-%m")]
            bucket["actual_load"].append(actual_load); bucket["forecast_load"].append(f_load)
            bucket["actual_net"].append(actual_net); bucket["forecast_net"].append(f_net)
        output[f"{issue_hour:02d}:00"] = {
            "load": q3.metric(np.concatenate(actual_load_rows), np.concatenate(forecast_load_rows)),
            "point_net": q3.metric(np.concatenate(actual_net_rows), np.concatenate(forecast_net_rows)),
            "monthly": {
                month: {
                    "load": q3.metric(np.concatenate(values["actual_load"]), np.concatenate(values["forecast_load"])),
                    "point_net": q3.metric(np.concatenate(values["actual_net"]), np.concatenate(values["forecast_net"])),
                }
                for month, values in sorted(monthly.items())
            },
        }
    return output


def monthly_costs(runs: dict[str, dict]) -> list[dict]:
    buckets = defaultdict(dict)
    for label, run in runs.items():
        per_month = defaultdict(lambda: {"cost": 0.0, "emergency": 0.0, "discard": 0.0})
        for row in run["daily"]:
            month = row["date"][:7]
            per_month[month]["cost"] += float(row["total_cost_yuan"])
            per_month[month]["emergency"] += float(row["emergency_purchase_kwh"])
            per_month[month]["discard"] += float(row["surplus_discard_kwh"])
        for month, values in per_month.items():
            buckets[month][label] = values
    rows = []
    for month in sorted(buckets):
        row = {"month": month}
        for label, values in sorted(buckets[month].items()):
            row[f"{label}_total_cost_yuan"] = values["cost"]
            row[f"{label}_emergency_kwh"] = values["emergency"]
            row[f"{label}_discard_kwh"] = values["discard"]
        row["alpha_0_5_minus_0_cost_yuan"] = row["alpha_0_5_total_cost_yuan"] - row["alpha_0_total_cost_yuan"]
        row["alpha_1_minus_0_cost_yuan"] = row["alpha_1_total_cost_yuan"] - row["alpha_0_total_cost_yuan"]
        rows.append(row)
    return rows


def main() -> None:
    ensure_dirs()
    before = frozen_hashes()
    fixed = load_attachment1()
    annual = load_attachment2()
    forecasts = load_attachment3()
    dates = annual["dates"]
    load_kw = annual["load_kw"]
    pv_kw = annual["pv_kw"]
    native = q3.issue_forecast
    runs = {}
    prediction = {}
    labels = {0.0: "alpha_0", 0.5: "alpha_0_5", 1.0: "alpha_1"}
    for alpha in (0.0, 0.5, 1.0):
        label = labels[alpha]
        q3.issue_forecast = make_issue_forecast(alpha)
        residual, _, _ = q3.build_forecast_caches(load_kw, pv_kw, forecasts["forecast_kw"], dates, "linear")
        print(json.dumps({"event": "start", "alpha": alpha}, ensure_ascii=False), flush=True)
        run = q3.run_strategy(
            name=f"p1_{label}",
            update_hours=[6, 12, 18],
            interpolation="linear",
            load_kw=load_kw,
            pv_kw=pv_kw,
            forecast3_kw=forecasts["forecast_kw"],
            dates=dates,
            price=fixed["price_yuan_per_kwh"],
            residual_cache=residual,
            raw_endpoint_labels=annual["raw_endpoint_labels"],
            keep_detail=True,
        )
        runs[label] = run
        prediction[label] = diagnostics(alpha, load_kw, pv_kw, forecasts["forecast_kw"], dates)
        write_csv(RESULTS / f"p1_{label}_detail.csv", run["detail"])
        write_csv(RESULTS / f"p1_{label}_daily.csv", run["daily"])
        print(json.dumps({"event": "done", "alpha": alpha, **run["aggregate"]}, ensure_ascii=False), flush=True)
    q3.issue_forecast = native

    monthly = monthly_costs(runs)
    write_csv(RESULTS / "p1_monthly_cost_ablation.csv", monthly)
    base = runs["alpha_0"]["aggregate"]
    comparisons = {
        label: {
            key: float(run["aggregate"][key] - base[key])
            for key in ("total_cost_yuan", "emergency_purchase_kwh", "surplus_discard_kwh", "soc_final_kwh")
        }
        for label, run in runs.items() if label != "alpha_0"
    }
    monthly_direction = {}
    for label in ("alpha_0_5", "alpha_1"):
        key = f"{label}_minus_0_cost_yuan"
        monthly_direction[label] = {
            "lower_cost_months": sum(row[key] < 0 for row in monthly),
            "higher_cost_months": sum(row[key] > 0 for row in monthly),
            "months": len(monthly),
        }
    after = frozen_hashes()
    summary = {
        "schema_version": 1,
        "experiment": "P1 Q3 causal load-feedback alpha ablation",
        "pre_registered_alpha": [0.0, 0.5, 1.0],
        "feedback_formula": "1 + alpha*(observed_prefix_sum/base_prefix_sum - 1); current-day unexecuted load only",
        "runs": {label: run["aggregate"] for label, run in runs.items()},
        "prediction_diagnostics": prediction,
        "comparison_to_alpha_0": comparisons,
        "monthly_direction": monthly_direction,
        "monthly_file": "results/p1_monthly_cost_ablation.csv",
        "frozen_files_unchanged": before == after,
        "frozen_hashes_before": before,
        "frozen_hashes_after": after,
    }
    write_json(RESULTS / "p1_load_feedback_ablation_summary.json", summary)
    print(json.dumps({"event": "summary", "comparisons": comparisons, "monthly": monthly_direction}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
