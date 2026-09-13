from __future__ import annotations

"""Isolated five-point sensitivity replay for the frozen Q3 MAIN.

This script never writes into PROJECT_ROOT/results, PROJECT_ROOT/validation or
PROJECT_ROOT/intermediate.  It only replaces the causal feedback coefficient
while retaining the frozen Q3 solver, Q80 residual correction and settlement.
"""

import csv
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

import numpy as np

PROJECT_ROOT = Path(os.environ.get("CUMCM_PROJECT_ROOT", Path.cwd())).resolve()
CODE_ROOT = PROJECT_ROOT / "code"
if str(CODE_ROOT) not in sys.path:
    sys.path.insert(0, str(CODE_ROOT))

from common_data import load_attachment1, load_attachment2, load_attachment3  # noqa: E402
import q3_solve as q3  # noqa: E402
from final_promote_alpha05 import validate_run  # noqa: E402
from q3_p1_load_feedback_ablation import make_issue_forecast  # noqa: E402


EXPERIMENT_ROOT = Path(__file__).resolve().parent
RESULTS = EXPERIMENT_ROOT / "results"
VALIDATION = EXPERIMENT_ROOT / "validation"
INTERMEDIATE = EXPERIMENT_ROOT / "intermediate"
ALPHAS = (0.0, 0.25, 0.5, 0.75, 1.0)
UPDATE_HOURS = (6, 12, 18)
PROTECTED = (
    "results/q3_detail.csv",
    "results/q3_daily.csv",
    "results/q3_storage_4h.csv",
    "results/q3_emergency_events.csv",
    "results/q3_plan_versions.csv",
    "results/q3_summary.json",
    "results/result3.xlsx",
    "validation/q3_validation.json",
    "validation/q3_independent_recompute.json",
    "validation/result3_workbook_validation.json",
    "intermediate/q3_workbook_payload.json",
    "intermediate/q3_run_manifest.json",
    "intermediate/final_promotion_alpha05_manifest.json",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def protected_hashes() -> dict[str, str]:
    return {
        name: sha256(PROJECT_ROOT / name)
        for name in PROTECTED
        if (PROJECT_ROOT / name).is_file()
    }


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError("refuse to write an empty sensitivity table")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def independent_cost_recompute(run: dict[str, Any]) -> dict[str, float]:
    """Rebuild Q3's A08-main cash ledger from 10-minute detail rows."""
    base = downward = upward = emergency = 0.0
    for row in run["detail"]:
        price = float(row["actual_price_yuan_per_kwh"])
        base += price * float(row["original_purchase_kwh"])
        downward += 0.5 * price * float(row["downward_adjustment_kwh"])
        upward += 1.5 * price * float(row["upward_adjustment_kwh"])
        emergency += 5.0 * price * float(row["emergency_purchase_kwh"])
    adjustment = upward - downward
    total = base + adjustment + emergency
    return {
        "base_plan_cost_yuan": base,
        "downward_credit_yuan": downward,
        "upward_adjustment_cost_yuan": upward,
        "purchase_adjustment_cost_yuan": adjustment,
        "normal_settlement_cost_yuan": base + adjustment,
        "emergency_cost_yuan": emergency,
        "total_cost_yuan": total,
    }


def alpha_tag(alpha: float) -> str:
    return f"{alpha:.2f}".replace(".", "p")


def make_summary_row(alpha: float, run: dict[str, Any], check: dict[str, Any], recomputed: dict[str, float]) -> dict[str, Any]:
    agg = run["aggregate"]
    daily_total = sum(float(row["total_cost_yuan"]) for row in run["daily"])
    return {
        "alpha": alpha,
        "normal_purchase_cost_yuan": float(agg["base_plan_cost_yuan"]),
        "purchase_adjustment_cost_yuan": float(agg["upward_adjustment_cost_yuan"] - agg["downward_credit_yuan"]),
        "emergency_purchase_cost_yuan": float(agg["emergency_cost_yuan"]),
        "total_purchase_cost_yuan": float(agg["total_cost_yuan"]),
        "emergency_purchase_kwh": float(agg["emergency_purchase_kwh"]),
        "base_plan_cost_yuan": float(agg["base_plan_cost_yuan"]),
        "downward_credit_yuan": float(agg["downward_credit_yuan"]),
        "upward_adjustment_cost_yuan": float(agg["upward_adjustment_cost_yuan"]),
        "normal_settlement_cost_yuan": float(agg["normal_settlement_cost_yuan"]),
        "terminal_soc_kwh": float(agg["soc_final_kwh"]),
        "daily_recompute_difference_yuan": daily_total - float(agg["total_cost_yuan"]),
        "detail_recompute_difference_yuan": recomputed["total_cost_yuan"] - float(agg["total_cost_yuan"]),
        "validation_status": check["status"],
    }


def main() -> None:
    for folder in (RESULTS, VALIDATION, INTERMEDIATE):
        folder.mkdir(parents=True, exist_ok=True)
    before = protected_hashes()
    write_json(INTERMEDIATE / "formal_q3_hashes_before.json", before)

    fixed = load_attachment1()
    annual = load_attachment2()
    forecasts = load_attachment3()
    formal_summary = json.loads((PROJECT_ROOT / "results/q3_summary.json").read_text(encoding="utf-8"))
    formal_main = formal_summary["strategies"]["q3_all_main"]

    rows: list[dict[str, Any]] = []
    daily_rows: list[dict[str, Any]] = []
    validations: dict[str, Any] = {}
    native_issue_forecast = q3.issue_forecast
    try:
        for alpha in ALPHAS:
            print(json.dumps({"event": "start", "alpha": alpha}, ensure_ascii=False), flush=True)
            q3.issue_forecast = make_issue_forecast(alpha)
            residual, _, _ = q3.build_forecast_caches(
                annual["load_kw"], annual["pv_kw"], forecasts["forecast_kw"], annual["dates"], "linear"
            )
            run = q3.run_strategy(
                name=f"q3_alpha_sensitivity_{alpha_tag(alpha)}",
                update_hours=list(UPDATE_HOURS),
                interpolation="linear",
                load_kw=annual["load_kw"],
                pv_kw=annual["pv_kw"],
                forecast3_kw=forecasts["forecast_kw"],
                dates=annual["dates"],
                price=fixed["price_yuan_per_kwh"],
                residual_cache=residual,
                raw_endpoint_labels=annual["raw_endpoint_labels"],
                keep_detail=True,
            )
            check = validate_run(run, "Q3_alpha_five_point_sensitivity")
            recomputed = independent_cost_recompute(run)
            row = make_summary_row(alpha, run, check, recomputed)
            rows.append(row)
            for daily in run["daily"]:
                daily_rows.append({"alpha": alpha, **daily})
            validations[f"alpha_{alpha:.2f}"] = {
                "alpha": alpha,
                "q80_rule": "same per-issue historical residual 80th percentile correction as frozen Q3 MAIN",
                "update_hours": list(UPDATE_HOURS),
                "checks": check,
                "independent_detail_cost_recompute": recomputed,
                "summary_vs_detail_differences_yuan": {
                    key: recomputed[key] - float(run["aggregate"][key])
                    for key in recomputed
                    if key in run["aggregate"]
                },
            }
            print(json.dumps({"event": "done", "alpha": alpha, "total_cost_yuan": row["total_purchase_cost_yuan"], "validation": check["status"]}, ensure_ascii=False), flush=True)
    finally:
        q3.issue_forecast = native_issue_forecast

    alpha05 = next(row for row in rows if abs(float(row["alpha"]) - 0.5) <= 1e-12)
    reproduction_keys = (
        "normal_settlement_cost_yuan", "emergency_cost_yuan", "total_cost_yuan",
        "emergency_purchase_kwh", "base_plan_cost_yuan", "downward_credit_yuan", "upward_adjustment_cost_yuan",
    )
    alpha05_diffs = {
        key: float(alpha05[{"normal_settlement_cost_yuan": "normal_settlement_cost_yuan", "emergency_cost_yuan": "emergency_purchase_cost_yuan", "total_cost_yuan": "total_purchase_cost_yuan", "emergency_purchase_kwh": "emergency_purchase_kwh", "base_plan_cost_yuan": "base_plan_cost_yuan", "downward_credit_yuan": "downward_credit_yuan", "upward_adjustment_cost_yuan": "upward_adjustment_cost_yuan"}[key]]) - float(formal_main[key])
        for key in reproduction_keys
    }
    reproduction_pass = all(abs(value) <= 1e-6 for value in alpha05_diffs.values())

    after = protected_hashes()
    frozen_unchanged = before == after
    write_json(INTERMEDIATE / "formal_q3_hashes_after.json", after)
    write_csv(RESULTS / "q3_alpha_five_point_summary.csv", rows)
    write_csv(RESULTS / "q3_alpha_five_point_daily.csv", daily_rows)
    validation = {
        "schema_version": 1,
        "experiment": "Q3 frozen-MAIN causal load-feedback five-point sensitivity",
        "purpose": "paper sensitivity analysis only; no promotion authorization",
        "alphas": list(ALPHAS),
        "only_changed_parameter": "causal load-feedback coefficient alpha",
        "held_constant": [
            "Q80 residual quantile correction", "00/06/12/18 rolling update schedule", "PV forecast interface",
            "baseline load predictor", "cross-day SOC continuity", "storage physics and 5000 kW power limit",
            "A08-main purchase-adjustment settlement", "emergency purchase rule",
        ],
        "per_alpha": validations,
        "alpha_0_5_reproduces_frozen_main": {"pass": reproduction_pass, "differences": alpha05_diffs},
        "formal_q3_files_unchanged": frozen_unchanged,
        "formal_hashes_before": before,
        "formal_hashes_after": after,
        "status": "PASS" if frozen_unchanged and reproduction_pass and all(v["checks"]["status"] == "PASS" for v in validations.values()) else "FAIL",
    }
    write_json(VALIDATION / "q3_alpha_five_point_validation.json", validation)
    if validation["status"] != "PASS":
        raise RuntimeError("five-point sensitivity validation failed; formal Q3 remains untouched")
    print(json.dumps({"event": "complete", "status": validation["status"], "formal_unchanged": frozen_unchanged, "alpha05_reproduced": reproduction_pass}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
