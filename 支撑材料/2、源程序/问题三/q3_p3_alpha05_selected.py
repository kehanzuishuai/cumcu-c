from __future__ import annotations

import json

from common_data import load_attachment1, load_attachment2, load_attachment3
import q3_solve as q3
from q3_p3_information_ablation import PlannedStatePatch, make_information_forecast
from refinement_common import RESULTS, ensure_dirs, frozen_hashes, write_csv, write_json


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
    runs = {}
    for label, state_update, pv_update in (
        ("load05_only", False, False),
        ("all_three_alpha05", True, True),
    ):
        q3.issue_forecast = make_information_forecast(True, pv_update, alpha=0.5)
        residual, _, _ = q3.build_forecast_caches(
            annual["load_kw"], annual["pv_kw"], forecasts["forecast_kw"], dates, "linear"
        )
        state_patch = PlannedStatePatch(native_det, native_adj)
        q3.solve_deterministic_plan = native_det if state_update else state_patch.solve_deterministic
        q3.solve_adjusted_plan = native_adj if state_update else state_patch.solve_adjusted
        print(json.dumps({"event": "start", "strategy": label}, ensure_ascii=False), flush=True)
        run = q3.run_strategy(
            name=f"p3_{label}", update_hours=[6, 12, 18], interpolation="linear",
            load_kw=annual["load_kw"], pv_kw=annual["pv_kw"],
            forecast3_kw=forecasts["forecast_kw"], dates=dates,
            price=fixed["price_yuan_per_kwh"], residual_cache=residual,
            raw_endpoint_labels=annual["raw_endpoint_labels"], keep_detail=True,
        )
        runs[label] = run
        write_csv(RESULTS / f"p3_{label}_detail.csv", run["detail"])
        write_csv(RESULTS / f"p3_{label}_daily.csv", run["daily"])
        print(json.dumps({"event": "done", **run["aggregate"]}, ensure_ascii=False), flush=True)
    q3.issue_forecast = native_issue
    q3.solve_deterministic_plan = native_det
    q3.solve_adjusted_plan = native_adj
    base = json.loads((RESULTS / "p3_information_ablation_summary.json").read_text(encoding="utf-8"))["runs"]
    summary = {
        "schema_version": 1,
        "experiment": "P3 selected alpha=0.5 load-information modules",
        "selection_boundary": "alpha=0.5 was selected in P1 before this information-value completion run",
        "runs": {key: run["aggregate"] for key, run in runs.items()},
        "effects": {
            "load05_only_vs_none_cost_yuan": runs["load05_only"]["aggregate"]["total_cost_yuan"] - base["none"]["total_cost_yuan"],
            "load05_added_to_state_pv_cost_yuan": runs["all_three_alpha05"]["aggregate"]["total_cost_yuan"] - base["state_pv"]["total_cost_yuan"],
            "load05_added_to_state_pv_emergency_kwh": runs["all_three_alpha05"]["aggregate"]["emergency_purchase_kwh"] - base["state_pv"]["emergency_purchase_kwh"],
        },
        "frozen_files_unchanged": before == frozen_hashes(),
        "frozen_hashes_before": before,
        "frozen_hashes_after": frozen_hashes(),
    }
    write_json(RESULTS / "p3_alpha05_selected_summary.json", summary)
    print(json.dumps({"event": "summary", **summary["effects"]}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
