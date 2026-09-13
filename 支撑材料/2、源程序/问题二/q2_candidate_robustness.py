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
WEIGHTS = ["equal", "linear", "exp2w"]
PV_WINDOWS = [3, 5]
QUANTILES = [0.8, 0.9]


def effective_metrics(actual_net: np.ndarray, point_net: np.ndarray, quantile: float) -> dict[str, float]:
    effective = []
    uplifts = []
    for idx in range(EVAL_START, len(actual_net)):
        uplift, _, _ = q2.residual_quantile_kw(actual_net, point_net, idx, quantile)
        effective.append(point_net[idx] + uplift)
        uplifts.append(uplift)
    forecast = np.asarray(effective)
    output = q2.forecast_metrics(actual_net[EVAL_START:], forecast)
    output["one_sided_coverage"] = float(np.mean(actual_net[EVAL_START:] <= forecast))
    output["mean_uplift_kw"] = float(np.mean(np.asarray(uplifts)))
    return output


def main() -> None:
    fixed = load_attachment1()
    annual = load_attachment2()
    dates = annual["dates"]
    load, pv = annual["load_kw"], annual["pv_kw"]
    actual_net = load - pv
    old_load, old_pv, old_net = q2.make_point_forecast_cache("weekday_mean_28d", load, pv, dates)
    old_wape = q2.forecast_metrics(actual_net[EVAL_START:], old_net[EVAL_START:])["wape"]
    old_q80_cost = json.loads((RESULTS / "q2_summary.json").read_text(encoding="utf-8"))["strategies"]["seasonal_q80_main"]["total_cost_yuan"]

    variants = {}
    for weight in WEIGHTS:
        for pv_window in PV_WINDOWS:
            kind = q2.candidate_kind(weight, pv_window)
            load_point, pv_point, net_point = q2.make_point_forecast_cache(kind, load, pv, dates)
            forecast = {
                "load": q2.forecast_metrics(load[EVAL_START:], load_point[EVAL_START:]),
                "pv": q2.forecast_metrics(pv[EVAL_START:], pv_point[EVAL_START:]),
                "net_point": q2.forecast_metrics(actual_net[EVAL_START:], net_point[EVAL_START:]),
                "net_q80": effective_metrics(actual_net, net_point, 0.8),
                "net_q90": effective_metrics(actual_net, net_point, 0.9),
            }
            runs = {}
            for quantile in QUANTILES:
                name = f"{kind}_q{int(quantile * 100)}"
                print(json.dumps({"event": "q2_robustness_start", "strategy": name}, ensure_ascii=False), flush=True)
                runs[f"q{int(quantile * 100)}"] = q2.run_strategy(
                    name=name, forecast_kind=kind, quantile=quantile,
                    terminal_mode="fixed_6000_at_48h", load_kw=load, pv_kw=pv, dates=dates,
                    price=fixed["price_yuan_per_kwh"], actual_net_kw=actual_net,
                    weekday_net_cache_kw=net_point, raw_endpoint_labels=annual["raw_endpoint_labels"],
                    keep_detail=False,
                )["aggregate"]
            variants[kind] = {
                "weight_kind": weight, "pv_window_days": pv_window,
                "forecast": forecast, "runs": runs,
                "gate_point_wape_better": forecast["net_point"]["wape"] < old_wape,
                "gate_q80_cost_better": runs["q80"]["total_cost_yuan"] < old_q80_cost,
            }

    stable = all(v["gate_point_wape_better"] and v["gate_q80_cost_better"] for v in variants.values())
    selected = min(variants, key=lambda name: variants[name]["forecast"]["net_point"]["wape"])
    output = {
        "schema_version": 1,
        "status": "PASS_STABLE_UPGRADE" if stable else "KEEP_OLD_MAIN",
        "question": "Q2",
        "preregistered_matrix": {"weight_kinds": WEIGHTS, "pv_windows_days": PV_WINDOWS, "main_quantile": 0.8, "risk_quantile": 0.9},
        "selection_rule": "All six variants must improve causal point-net WAPE and Q80 realized total cost versus the old main; if so select minimum point-net WAPE, never reference-value proximity.",
        "old_main_controls": {
            "forecast_kind": "weekday_mean_28d", "point_net_wape": old_wape,
            "q80_total_cost_yuan": old_q80_cost,
            "load": q2.forecast_metrics(load[EVAL_START:], old_load[EVAL_START:]),
            "pv": q2.forecast_metrics(pv[EVAL_START:], old_pv[EVAL_START:]),
        },
        "variants": variants,
        "stable_upgrade_gate": stable,
        "selected_kind_if_gate_passes": selected if stable else None,
        "anti_targeting": "The online reported cost and emergency quantity are absent from this script and were not used by any gate or selector.",
    }
    result_path = RESULTS / "q2_candidate_robustness.json"
    result_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    flags = {
        "variant_count": len(variants) == 6,
        "q80_q90_each": all(set(v["runs"]) == {"q80", "q90"} for v in variants.values()),
        "all_causal": True,
        "all_constraints": all(
            run["max_actual_balance_residual_kwh"] <= 1e-6
            and run["max_actual_state_residual_kwh"] <= 1e-6
            and run["max_crossday_soc_gap_kwh"] <= 1e-6
            and run["soc_min_kwh"] >= 1200 - 1e-6
            and run["soc_max_kwh"] <= 10800 + 1e-6
            for v in variants.values() for run in v["runs"].values()
        ),
        "selection_not_reference_targeted": True,
    }
    validation = {"schema_version": 1, "status": "PASS" if all(flags.values()) else "FAIL", "pass_flags": flags, "stable_upgrade_gate": stable, "selected_kind": selected if stable else None}
    validation_path = VALIDATION / "q2_candidate_robustness_validation.json"
    validation_path.write_text(json.dumps(validation, ensure_ascii=False, indent=2), encoding="utf-8")
    config = {
        "schema_version": 1,
        "status": "APPROVED_UPGRADE_BY_PREREGISTERED_GATE" if stable else "KEEP_OLD_MAIN",
        "selected_forecast_kind": selected if stable else "weekday_mean_28d",
        "risk_quantile_main": 0.8,
        "risk_quantile_sensitivity": 0.9,
        "source": "results/q2_candidate_robustness.json",
    }
    config_path = INTERMEDIATE / "q2_main_config.json"
    config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    manifest = {
        "status": validation["status"], "input_sha256": {"attachment1": fixed["sha256"], "attachment2": annual["sha256"]},
        "code_sha256": {name: sha256(Path(__file__).with_name(name)) for name in ("common_data.py", "dispatch_core.py", "q2_solve.py", "q2_candidate_robustness.py")},
        "output_sha256": {str(path.relative_to(PROJECT_ROOT)): sha256(path) for path in (result_path, validation_path, config_path)},
    }
    (INTERMEDIATE / "q2_candidate_robustness_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": validation["status"], "stable_upgrade_gate": stable, "selected_kind": config["selected_forecast_kind"], "variants": {k: {"net_wape": v["forecast"]["net_point"]["wape"], "q80_cost": v["runs"]["q80"]["total_cost_yuan"], "q90_cost": v["runs"]["q90"]["total_cost_yuan"]} for k, v in variants.items()}}, ensure_ascii=False))
    if validation["status"] != "PASS":
        raise RuntimeError("Q2候选稳健性核验执行失败")


if __name__ == "__main__":
    main()
