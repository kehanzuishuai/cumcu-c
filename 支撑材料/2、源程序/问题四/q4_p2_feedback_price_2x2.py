from __future__ import annotations

import json
from collections import defaultdict

from common_data import load_attachment1, load_attachment2, load_attachment3, load_attachment4
import q3_solve as q3
from q3_p1_load_feedback_ablation import make_issue_forecast
from refinement_common import RESULTS, ensure_dirs, frozen_hashes, write_csv, write_json


def main() -> None:
    ensure_dirs()
    before = frozen_hashes()
    fixed = load_attachment1()
    annual = load_attachment2()
    forecasts = load_attachment3()
    realtime = load_attachment4()
    dates = annual["dates"]
    if not (dates == forecasts["dates"] == realtime["dates"]):
        raise ValueError("attachment 2/3/4 date axes differ")
    native = q3.issue_forecast
    runs = {}
    specs = [
        ("load0_price0", 0.0, "weekday_mean_28d"),
        ("load0_price1", 0.0, "weekday_mean_28d_intraday_scale_ar1"),
        ("load1_price0", 1.0, "weekday_mean_28d"),
        ("load1_price1", 1.0, "weekday_mean_28d_intraday_scale_ar1"),
    ]
    for label, alpha, price_kind in specs:
        q3.issue_forecast = make_issue_forecast(alpha)
        residual, _, _ = q3.build_forecast_caches(
            annual["load_kw"], annual["pv_kw"], forecasts["forecast_kw"], dates, "linear"
        )
        print(json.dumps({"event": "start", "strategy": label}, ensure_ascii=False), flush=True)
        run = q3.run_strategy(
            name=f"p2_{label}",
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
            actual_price_by_date=realtime["price_yuan_per_kwh"],
            planning_price_kind=price_kind,
        )
        runs[label] = run
        write_csv(RESULTS / f"p2_{label}_detail.csv", run["detail"])
        write_csv(RESULTS / f"p2_{label}_daily.csv", run["daily"])
        print(json.dumps({"event": "done", "strategy": label, **run["aggregate"]}, ensure_ascii=False), flush=True)
    q3.issue_forecast = native

    costs = {label: run["aggregate"]["total_cost_yuan"] for label, run in runs.items()}
    emergency = {label: run["aggregate"]["emergency_purchase_kwh"] for label, run in runs.items()}
    decomposition = {
        "load_feedback_effect_without_price_correction_yuan": costs["load1_price0"] - costs["load0_price0"],
        "load_feedback_effect_with_price_correction_yuan": costs["load1_price1"] - costs["load0_price1"],
        "price_correction_effect_without_load_feedback_yuan": costs["load0_price1"] - costs["load0_price0"],
        "price_correction_effect_with_load_feedback_yuan": costs["load1_price1"] - costs["load1_price0"],
        "interaction_yuan": costs["load1_price1"] - costs["load1_price0"] - costs["load0_price1"] + costs["load0_price0"],
    }
    monthly = defaultdict(dict)
    for label, run in runs.items():
        buckets = defaultdict(lambda: {"cost": 0.0, "emergency": 0.0})
        for row in run["daily"]:
            month = row["date"][:7]
            buckets[month]["cost"] += float(row["total_cost_yuan"])
            buckets[month]["emergency"] += float(row["emergency_purchase_kwh"])
        for month, values in buckets.items():
            monthly[month][label] = values
    monthly_rows = []
    for month in sorted(monthly):
        row = {"month": month}
        for label in [spec[0] for spec in specs]:
            row[f"{label}_cost_yuan"] = monthly[month][label]["cost"]
            row[f"{label}_emergency_kwh"] = monthly[month][label]["emergency"]
        row["load_effect_with_price_correction_yuan"] = row["load1_price1_cost_yuan"] - row["load0_price1_cost_yuan"]
        monthly_rows.append(row)
    write_csv(RESULTS / "p2_monthly_2x2.csv", monthly_rows)
    after = frozen_hashes()
    summary = {
        "schema_version": 1,
        "experiment": "P2 Q4-3 load feedback x intraday price correction",
        "factor_load_feedback": "alpha=1 causal prefix feedback off/on",
        "factor_price_correction": "midnight weekday-mean price frozen vs causal prefix scale+AR1 at 06/12/18",
        "runs": {label: run["aggregate"] for label, run in runs.items()},
        "cost_decomposition": decomposition,
        "emergency_purchase_kwh": emergency,
        "load_feedback_lower_cost_months_with_price_correction": sum(
            row["load_effect_with_price_correction_yuan"] < 0 for row in monthly_rows
        ),
        "months": len(monthly_rows),
        "frozen_files_unchanged": before == after,
        "frozen_hashes_before": before,
        "frozen_hashes_after": after,
    }
    write_json(RESULTS / "p2_feedback_price_2x2_summary.json", summary)
    print(json.dumps({"event": "summary", **decomposition}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
