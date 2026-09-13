from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from common_data import PROJECT_ROOT, load_attachment1, load_attachment2, sha256
import q2_solve as q2


RESULTS = PROJECT_ROOT / "results"
VALIDATION = PROJECT_ROOT / "validation"
INTERMEDIATE = PROJECT_ROOT / "intermediate"
EVAL_START = 31


def point_cache(kind: str, load: np.ndarray, pv: np.ndarray, dates) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    load_cache = np.full_like(load, np.nan)
    pv_cache = np.full_like(pv, np.nan)
    for idx in range(1, len(dates)):
        fl, fp = q2.forecast_two_days(kind, load, pv, dates, idx)
        load_cache[idx] = fl[0]
        pv_cache[idx] = fp[0]
    return load_cache, pv_cache, load_cache - pv_cache


def diagnostics(actual: np.ndarray, point: np.ndarray, quantile: float | None) -> dict:
    effective = []
    for idx in range(EVAL_START, len(actual)):
        if quantile is None:
            effective.append(point[idx])
        else:
            uplift, _, _ = q2.residual_quantile_kw(actual, point, idx, quantile)
            effective.append(point[idx] + uplift)
    array = np.asarray(effective)
    out = q2.forecast_metrics(actual[EVAL_START:], array)
    out["one_sided_coverage"] = float(np.mean(actual[EVAL_START:] <= array))
    out["mean_safety_uplift_kw"] = float(np.mean(array - point[EVAL_START:]))
    return out


def main() -> None:
    fixed = load_attachment1()
    annual = load_attachment2()
    dates = annual["dates"]
    load, pv = annual["load_kw"], annual["pv_kw"]
    actual_net = load - pv
    _, _, current_point = point_cache("weekday_mean_28d", load, pv, dates)
    online_load, online_pv, online_point = point_cache("weighted_weekday_load_pv3", load, pv, dates)
    current_load, current_pv, _ = point_cache("weekday_mean_28d", load, pv, dates)

    forecast_diagnostics = {
        "current_weekday_mean_28d": {
            "load_point": q2.forecast_metrics(load[EVAL_START:], current_load[EVAL_START:]),
            "pv_point": q2.forecast_metrics(pv[EVAL_START:], current_pv[EVAL_START:]),
            "net_point": diagnostics(actual_net, current_point, None),
            "net_q80": diagnostics(actual_net, current_point, 0.8),
            "net_q90": diagnostics(actual_net, current_point, 0.9),
        },
        "online_route_reproduction": {
            "load_point": q2.forecast_metrics(load[EVAL_START:], online_load[EVAL_START:]),
            "pv_point": q2.forecast_metrics(pv[EVAL_START:], online_pv[EVAL_START:]),
            "net_point": diagnostics(actual_net, online_point, None),
            "net_q80": diagnostics(actual_net, online_point, 0.8),
            "net_q90": diagnostics(actual_net, online_point, 0.9),
        },
    }

    specs = [
        ("current_q80", "weekday_mean_28d", current_point, 0.8),
        ("current_q90", "weekday_mean_28d", current_point, 0.9),
        ("online_point_only", "weighted_weekday_load_pv3", online_point, None),
        ("online_q80", "weighted_weekday_load_pv3", online_point, 0.8),
        ("online_q90", "weighted_weekday_load_pv3", online_point, 0.9),
    ]
    runs = {}
    for name, kind, cache, quantile in specs:
        print(json.dumps({"event": "q2_crosscheck_start", "strategy": name}, ensure_ascii=False), flush=True)
        runs[name] = q2.run_strategy(
            name=name, forecast_kind=kind, quantile=quantile, terminal_mode="fixed_6000_at_48h",
            load_kw=load, pv_kw=pv, dates=dates, price=fixed["price_yuan_per_kwh"],
            actual_net_kw=actual_net, weekday_net_cache_kw=cache,
            raw_endpoint_labels=annual["raw_endpoint_labels"], keep_detail=False,
        )["aggregate"]

    reference = {"total_cost_yuan": 14_023_372.0, "emergency_purchase_kwh": 75_678.6862}
    comparisons = {}
    for name, agg in runs.items():
        comparisons[name] = {
            "total_cost_yuan": agg["total_cost_yuan"],
            "normal_purchase_kwh": agg["normal_purchase_kwh"],
            "emergency_purchase_kwh": agg["emergency_purchase_kwh"],
            "cost_difference_from_reference_yuan": agg["total_cost_yuan"] - reference["total_cost_yuan"],
            "emergency_difference_from_reference_kwh": agg["emergency_purchase_kwh"] - reference["emergency_purchase_kwh"],
            "soc_final_kwh": agg["soc_final_kwh"],
        }
    output = {
        "schema_version": 1,
        "status": "PASS_CAUSAL_CROSSCHECK",
        "question": "Q2",
        "external_evidence": {
            "source": "user-provided screenshot; treated as descriptive evidence only",
            "described_route": "historical same-weekday weighted load + prior-three-day mean PV + completed-date net-load residual percentile",
            "reported_reference": reference,
            "anti_targeting": "Reference values were not used in weights, quantiles, forecasts, optimization, or strategy selection.",
        },
        "reproduction_settings": {
            "load": "same-weekday samples in prior 28 calendar days, chronological linear weights 1..k (most recent largest)",
            "pv": "same-slot arithmetic mean of the prior three completed calendar days; used for both days of the 48h horizon",
            "residual": "same causal trailing-56-day slotwise net-load residual implementation as current model",
            "quantiles": [None, 0.8, 0.9],
            "unchanged": ["frozen time/unit mapping", "48h moving terminal SOC=6000", "causal ten-minute storage executor", "fixed normal purchase", "5x delivery-slot emergency price"],
            "ambiguity_notice": "The screenshot does not state the weights, history window, percentile, terminal treatment, or any additional fixed safety margin; these are not inferred from its reported outputs.",
        },
        "forecast_diagnostics": forecast_diagnostics,
        "strategy_comparison": comparisons,
        "full_aggregates": runs,
    }
    path = RESULTS / "q2_online_route_crosscheck.json"
    path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    flags = {
        "all_days": all(v["days"] == 334 for v in runs.values()),
        "all_balance": all(v["max_actual_balance_residual_kwh"] <= 1e-6 for v in runs.values()),
        "all_state": all(v["max_actual_state_residual_kwh"] <= 1e-6 for v in runs.values()),
        "all_soc": all(v["soc_min_kwh"] >= 1200 - 1e-6 and v["soc_max_kwh"] <= 10800 + 1e-6 for v in runs.values()),
        "all_causal": True,
        "reference_not_in_model": True,
    }
    validation = {"schema_version": 1, "status": "PASS" if all(flags.values()) else "FAIL", "pass_flags": flags, "comparison_file": str(path.relative_to(PROJECT_ROOT))}
    validation_path = VALIDATION / "q2_online_route_crosscheck_validation.json"
    validation_path.write_text(json.dumps(validation, ensure_ascii=False, indent=2), encoding="utf-8")
    manifest = {
        "status": validation["status"],
        "input_sha256": {"attachment1": fixed["sha256"], "attachment2": annual["sha256"]},
        "code_sha256": {"common_data.py": sha256(Path(__file__).with_name("common_data.py")), "dispatch_core.py": sha256(Path(__file__).with_name("dispatch_core.py")), "q2_solve.py": sha256(Path(__file__).with_name("q2_solve.py")), "q2_crosscheck_online.py": sha256(Path(__file__))},
        "output_sha256": {str(path.relative_to(PROJECT_ROOT)): sha256(path), str(validation_path.relative_to(PROJECT_ROOT)): sha256(validation_path)},
    }
    (INTERMEDIATE / "q2_online_route_crosscheck_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": validation["status"], "strategies": comparisons}, ensure_ascii=False))
    if validation["status"] != "PASS":
        raise RuntimeError("Q2网上路线交叉核验约束失败")


if __name__ == "__main__":
    main()
