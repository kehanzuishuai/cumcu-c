from __future__ import annotations

import json

from common_data import load_attachment1, load_attachment2, load_attachment3
import q3_solve as q3
from refinement_common import (
    RESULTS,
    frozen_hashes,
    ensure_dirs,
    make_adjusted_solver,
    resettle_run,
    write_csv,
    write_json,
)


def main() -> None:
    ensure_dirs()
    before = frozen_hashes()
    fixed = load_attachment1()
    annual = load_attachment2()
    forecasts = load_attachment3()
    if annual["dates"] != forecasts["dates"]:
        raise ValueError("attachment 2/3 date axes differ")
    dates = annual["dates"]
    load_kw = annual["load_kw"]
    pv_kw = annual["pv_kw"]
    cache, _, _ = q3.build_forecast_caches(load_kw, pv_kw, forecasts["forecast_kw"], dates, "linear")
    native_solver = q3.solve_adjusted_plan
    runs = {}
    for settlement, coefficient in (("refund", -0.5), ("no_refund", 0.5)):
        q3.solve_adjusted_plan = native_solver if settlement == "refund" else make_adjusted_solver(coefficient)
        for label, updates in (("0only", []), ("all_updates", [6, 12, 18])):
            name = f"p0_{settlement}_{label}"
            print(json.dumps({"event": "start", "strategy": name}, ensure_ascii=False), flush=True)
            run = q3.run_strategy(
                name=name,
                update_hours=updates,
                interpolation="linear",
                load_kw=load_kw,
                pv_kw=pv_kw,
                forecast3_kw=forecasts["forecast_kw"],
                dates=dates,
                price=fixed["price_yuan_per_kwh"],
                residual_cache=cache,
                raw_endpoint_labels=annual["raw_endpoint_labels"],
                keep_detail=True,
            )
            runs[name] = resettle_run(run, settlement)
            write_csv(RESULTS / f"{name}_detail.csv", runs[name]["detail"])
            write_csv(RESULTS / f"{name}_daily.csv", runs[name]["daily"])
            if runs[name]["versions"]:
                write_csv(RESULTS / f"{name}_versions.csv", runs[name]["versions"])
            print(json.dumps({"event": "done", **runs[name]["aggregate"]}, ensure_ascii=False), flush=True)
    q3.solve_adjusted_plan = native_solver

    summary_runs = {name: run["aggregate"] for name, run in runs.items()}
    value = {}
    for settlement in ("refund", "no_refund"):
        base = summary_runs[f"p0_{settlement}_0only"]
        rolling = summary_runs[f"p0_{settlement}_all_updates"]
        value[settlement] = {
            "rolling_minus_0only_total_cost_yuan": rolling["total_cost_yuan"] - base["total_cost_yuan"],
            "rolling_minus_0only_emergency_kwh": rolling["emergency_purchase_kwh"] - base["emergency_purchase_kwh"],
            "rolling_minus_0only_discard_kwh": rolling["surplus_discard_kwh"] - base["surplus_discard_kwh"],
            "daily_update_has_positive_cash_value": rolling["total_cost_yuan"] < base["total_cost_yuan"],
        }
    after = frozen_hashes()
    summary = {
        "schema_version": 1,
        "experiment": "P0 A08 settlement re-optimization",
        "pre_registered_change": {
            "refund": "downward adjustment objective and settlement contribution = -0.5*p*down",
            "no_refund": "downward adjustment objective and settlement contribution = +0.5*p*down",
        },
        "held_fixed": [
            "00:00 load/PV forecast and Q80 residual correction",
            "06/12/18 attachment-3 update information",
            "5000 kW storage executor, efficiencies, SOC bounds, and cross-day continuity",
            "five-times emergency purchase",
        ],
        "runs": summary_runs,
        "value_of_updates": value,
        "robust_conclusion": all(v["daily_update_has_positive_cash_value"] for v in value.values()),
        "frozen_hashes_before": before,
        "frozen_hashes_after": after,
        "frozen_files_unchanged": before == after,
    }
    write_json(RESULTS / "p0_a08_reoptimization_summary.json", summary)
    print(json.dumps({"event": "summary", "robust": summary["robust_conclusion"], "unchanged": before == after}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
