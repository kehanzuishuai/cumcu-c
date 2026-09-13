from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
VALIDATION = ROOT / "validation"
INTERMEDIATE = ROOT / "intermediate"
SUMMARY_PATH = RESULTS / "q3_summary.json"
DETAIL_PATH = RESULTS / "q3_detail.csv"
OUTPUT_PATH = RESULTS / "q3_a08_settlement_sensitivity.json"
VALIDATION_PATH = VALIDATION / "q3_a08_settlement_validation.json"
MANIFEST_PATH = INTERMEDIATE / "q3_a08_settlement_manifest.json"
TOL_YUAN = 1e-5


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def current_cost(agg: dict[str, Any]) -> float:
    return (
        float(agg["base_plan_cost_yuan"])
        - float(agg["downward_credit_yuan"])
        + float(agg["upward_adjustment_cost_yuan"])
        + float(agg["emergency_cost_yuan"])
    )


def no_refund_cost(agg: dict[str, Any]) -> float:
    return (
        float(agg["base_plan_cost_yuan"])
        + float(agg["downward_credit_yuan"])
        + float(agg["upward_adjustment_cost_yuan"])
        + float(agg["emergency_cost_yuan"])
    )


def main() -> None:
    summary = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
    ordered = ["q3_0only", "q3_0_6", "q3_0_6_12", "q3_all_main"]
    compare = [*ordered, "q3_all_step_hold"]
    strategies: dict[str, dict[str, Any]] = {}
    max_reported_gap = 0.0
    for name in compare:
        agg = summary["strategies"][name]
        main_total = current_cost(agg)
        alternative_total = no_refund_cost(agg)
        reported = float(agg["total_cost_yuan"])
        max_reported_gap = max(max_reported_gap, abs(main_total - reported))
        strategies[name] = {
            "update_hours": agg["update_hours"],
            "interpolation": agg["interpolation"],
            "trajectory_invariants": {
                key: float(agg[key])
                for key in (
                    "original_purchase_kwh", "effective_purchase_kwh",
                    "upward_adjustment_kwh", "downward_adjustment_kwh",
                    "emergency_purchase_kwh", "charge_kwh", "discharge_kwh",
                    "soc_initial_kwh", "soc_final_kwh",
                )
            },
            "cost_components_yuan": {
                "original_plan_cost": float(agg["base_plan_cost_yuan"]),
                "cancelled_original_cost_refund_under_main": 2.0 * float(agg["downward_credit_yuan"]),
                "downward_50pct_penalty": float(agg["downward_credit_yuan"]),
                "upward_150pct_incremental_cost": float(agg["upward_adjustment_cost_yuan"]),
                "emergency_5x_cost": float(agg["emergency_cost_yuan"]),
            },
            "main_refund_plus_penalty_total_yuan": main_total,
            "alternative_full_plan_plus_penalty_total_yuan": alternative_total,
            "alternative_minus_main_yuan": alternative_total - main_total,
            "alternative_minus_main_percent": (alternative_total - main_total) / main_total * 100.0,
        }

    incremental = []
    for before, after in zip(ordered[:-1], ordered[1:]):
        main_change = strategies[after]["main_refund_plus_penalty_total_yuan"] - strategies[before]["main_refund_plus_penalty_total_yuan"]
        alt_change = strategies[after]["alternative_full_plan_plus_penalty_total_yuan"] - strategies[before]["alternative_full_plan_plus_penalty_total_yuan"]
        incremental.append({
            "from": before,
            "to": after,
            "main_cost_change_yuan": main_change,
            "main_cost_saving_yuan": -main_change,
            "alternative_cost_change_yuan": alt_change,
            "alternative_cost_saving_yuan": -alt_change,
        })

    base = strategies[ordered[0]]
    all_updates = strategies[ordered[-1]]
    cumulative = {
        "main_all_updates_vs_0only_cost_change_yuan": all_updates["main_refund_plus_penalty_total_yuan"] - base["main_refund_plus_penalty_total_yuan"],
        "main_all_updates_vs_0only_saving_yuan": base["main_refund_plus_penalty_total_yuan"] - all_updates["main_refund_plus_penalty_total_yuan"],
        "alternative_all_updates_vs_0only_cost_change_yuan": all_updates["alternative_full_plan_plus_penalty_total_yuan"] - base["alternative_full_plan_plus_penalty_total_yuan"],
        "alternative_all_updates_vs_0only_saving_yuan": base["alternative_full_plan_plus_penalty_total_yuan"] - all_updates["alternative_full_plan_plus_penalty_total_yuan"],
    }

    detail_sums = {
        "base": 0.0,
        "downward_50pct": 0.0,
        "upward_150pct": 0.0,
        "emergency_5x": 0.0,
        "reported_total": 0.0,
    }
    rows = 0
    with DETAIL_PATH.open("r", encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            rows += 1
            detail_sums["base"] += float(row["base_plan_cost_yuan"])
            detail_sums["downward_50pct"] += float(row["downward_credit_yuan"])
            detail_sums["upward_150pct"] += float(row["upward_adjustment_cost_yuan"])
            detail_sums["emergency_5x"] += float(row["emergency_cost_yuan"])
            detail_sums["reported_total"] += float(row["total_cost_yuan"])
    detail_main = detail_sums["base"] - detail_sums["downward_50pct"] + detail_sums["upward_150pct"] + detail_sums["emergency_5x"]
    detail_alternative = detail_sums["base"] + detail_sums["downward_50pct"] + detail_sums["upward_150pct"] + detail_sums["emergency_5x"]
    aggregate_main = strategies["q3_all_main"]["main_refund_plus_penalty_total_yuan"]
    aggregate_alternative = strategies["q3_all_main"]["alternative_full_plan_plus_penalty_total_yuan"]

    payload = {
        "schema_version": 1,
        "question": "Q3",
        "sensitivity_id": "A08",
        "status": "PASS",
        "scope": "Fixed-trajectory settlement-only sensitivity; no forecast, information, normal-purchase adjustment, storage execution, or emergency-purchase trajectory was changed.",
        "main_interpretation": {
            "label": "cancelled original purchase refunded; cancelled quantity pays 50% penalty",
            "formula": "base_plan_cost - 0.5*p*downward + 1.5*p*upward + 5*p*emergency",
            "evidence_level": "user-approved frozen recommended interpretation A08",
        },
        "alternative_interpretation": {
            "label": "original plan remains fully paid; downward quantity additionally pays 50% penalty",
            "formula": "base_plan_cost + 0.5*p*downward + 1.5*p*upward + 5*p*emergency",
            "evidence_level": "alternative interpretation retained by A08 sensitivity",
        },
        "strategies": strategies,
        "incremental_update_value": incremental,
        "cumulative_update_value": cumulative,
        "main_strategy_conclusion": {
            "current_total_yuan": aggregate_main,
            "alternative_total_yuan": aggregate_alternative,
            "alternative_minus_current_yuan": aggregate_alternative - aggregate_main,
            "alternative_minus_current_percent": (aggregate_alternative - aggregate_main) / aggregate_main * 100.0,
            "warning": "The alternative is a fixed-trajectory re-settlement, not a re-optimized policy under the alternative objective.",
        },
        "no_reference_targeting": True,
    }

    checks = {
        "q3_detail_rows": rows,
        "all_reported_main_totals_reconcile": max_reported_gap <= TOL_YUAN,
        "max_reported_main_total_gap_yuan": max_reported_gap,
        "detail_reported_total_gap_yuan": abs(detail_sums["reported_total"] - aggregate_main),
        "detail_main_formula_gap_yuan": abs(detail_main - aggregate_main),
        "detail_alternative_formula_gap_yuan": abs(detail_alternative - aggregate_alternative),
        "alternative_minus_main_identity_gap_yuan": abs((aggregate_alternative - aggregate_main) - 2.0 * detail_sums["downward_50pct"]),
        "trajectory_reoptimization_performed": False,
        "online_reference_values_used": False,
    }
    validation = {
        "schema_version": 1,
        "question": "Q3",
        "sensitivity_id": "A08",
        "status": "PASS",
        "checks": checks,
        "independence": "The main strategy is independently re-settled from all 48,096 ten-minute detail rows; other fixed strategies are mechanically re-settled from their frozen cost components in q3_summary.json.",
    }
    if (
        rows != 334 * 144
        or not checks["all_reported_main_totals_reconcile"]
        or checks["detail_reported_total_gap_yuan"] > TOL_YUAN
        or checks["detail_main_formula_gap_yuan"] > TOL_YUAN
        or checks["detail_alternative_formula_gap_yuan"] > TOL_YUAN
        or checks["alternative_minus_main_identity_gap_yuan"] > TOL_YUAN
    ):
        payload["status"] = "FAIL"
        validation["status"] = "FAIL"

    RESULTS.mkdir(parents=True, exist_ok=True)
    VALIDATION.mkdir(parents=True, exist_ok=True)
    INTERMEDIATE.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    VALIDATION_PATH.write_text(json.dumps(validation, ensure_ascii=False, indent=2), encoding="utf-8")
    manifest = {
        "schema_version": 1,
        "question": "Q3",
        "sensitivity_id": "A08",
        "status": validation["status"],
        "inputs_sha256": {
            str(SUMMARY_PATH.relative_to(ROOT)): sha256(SUMMARY_PATH),
            str(DETAIL_PATH.relative_to(ROOT)): sha256(DETAIL_PATH),
        },
        "code_sha256": {str(Path(__file__).relative_to(ROOT)): sha256(Path(__file__))},
        "outputs_sha256": {
            str(OUTPUT_PATH.relative_to(ROOT)): sha256(OUTPUT_PATH),
            str(VALIDATION_PATH.relative_to(ROOT)): sha256(VALIDATION_PATH),
        },
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "status": validation["status"],
        "main_total_yuan": aggregate_main,
        "alternative_total_yuan": aggregate_alternative,
        "difference_yuan": aggregate_alternative - aggregate_main,
        "cumulative": cumulative,
    }, ensure_ascii=False))
    if validation["status"] != "PASS":
        raise RuntimeError("Q3 A08 settlement sensitivity validation failed")


if __name__ == "__main__":
    main()
