from __future__ import annotations

import json

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
    native = q3.issue_forecast
    q3.issue_forecast = make_issue_forecast(0.5)
    residual, _, _ = q3.build_forecast_caches(
        annual["load_kw"], annual["pv_kw"], forecasts["forecast_kw"], dates, "linear"
    )
    runs = {}
    for label, price_kind in (
        ("load05_price0", "weekday_mean_28d"),
        ("load05_price1", "weekday_mean_28d_intraday_scale_ar1"),
    ):
        print(json.dumps({"event": "start", "strategy": label}, ensure_ascii=False), flush=True)
        run = q3.run_strategy(
            name=f"p2_{label}", update_hours=[6, 12, 18], interpolation="linear",
            load_kw=annual["load_kw"], pv_kw=annual["pv_kw"],
            forecast3_kw=forecasts["forecast_kw"], dates=dates,
            price=fixed["price_yuan_per_kwh"], residual_cache=residual,
            raw_endpoint_labels=annual["raw_endpoint_labels"], keep_detail=True,
            actual_price_by_date=realtime["price_yuan_per_kwh"], planning_price_kind=price_kind,
        )
        runs[label] = run
        write_csv(RESULTS / f"p2_{label}_detail.csv", run["detail"])
        write_csv(RESULTS / f"p2_{label}_daily.csv", run["daily"])
        print(json.dumps({"event": "done", **run["aggregate"]}, ensure_ascii=False), flush=True)
    q3.issue_forecast = native
    base = json.loads((RESULTS / "p2_feedback_price_2x2_summary.json").read_text(encoding="utf-8"))["runs"]
    costs = {
        "load0_price0": base["load0_price0"]["total_cost_yuan"],
        "load0_price1": base["load0_price1"]["total_cost_yuan"],
        **{key: run["aggregate"]["total_cost_yuan"] for key, run in runs.items()},
    }
    decomposition = {
        "load_feedback_effect_without_price_correction_yuan": costs["load05_price0"] - costs["load0_price0"],
        "load_feedback_effect_with_price_correction_yuan": costs["load05_price1"] - costs["load0_price1"],
        "price_correction_effect_without_load_feedback_yuan": costs["load0_price1"] - costs["load0_price0"],
        "price_correction_effect_with_load_feedback_yuan": costs["load05_price1"] - costs["load05_price0"],
        "interaction_yuan": costs["load05_price1"] - costs["load05_price0"] - costs["load0_price1"] + costs["load0_price0"],
    }
    after = frozen_hashes()
    summary = {
        "schema_version": 1,
        "experiment": "P2 primary Q4 transfer using P1-selected alpha=0.5",
        "selection_boundary": "alpha=0.5 selected by the preceding Q3 P1 experiment before this Q4 transfer run; no Q4 result was used to tune alpha",
        "runs": {key: run["aggregate"] for key, run in runs.items()},
        "cost_decomposition": decomposition,
        "frozen_files_unchanged": before == after,
        "frozen_hashes_before": before,
        "frozen_hashes_after": after,
    }
    write_json(RESULTS / "p2_alpha05_transfer_summary.json", summary)
    print(json.dumps({"event": "summary", **decomposition}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
