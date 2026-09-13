from __future__ import annotations

import csv
import json
from collections import defaultdict

from common_data import PROJECT_ROOT
from refinement_common import EXPERIMENT_ROOT, INTERMEDIATE, RESULTS, VALIDATION, ensure_dirs, frozen_hashes, sha256, write_json


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def monthly_cost(path):
    values = defaultdict(float)
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            values[row["date"][:7]] += float(row["total_cost_yuan"])
    return dict(values)


def main() -> None:
    ensure_dirs()
    p1 = load_json(RESULTS / "p1_load_feedback_ablation_summary.json")
    p2 = load_json(RESULTS / "p2_alpha05_transfer_summary.json")
    p3 = load_json(RESULTS / "p3_alpha05_selected_summary.json")
    p4 = load_json(RESULTS / "p4_evening_soc_reserve_summary.json")
    validation = load_json(VALIDATION / "q3_q4_refinement_validation.json")
    base_month = monthly_cost(PROJECT_ROOT / "results" / "q4_3_daily.csv")
    candidate_month = monthly_cost(RESULTS / "p2_load05_price1_daily.csv")
    q4_monthly = {
        month: candidate_month[month] - base_month[month]
        for month in sorted(base_month)
    }
    decision = {
        "schema_version": 1,
        "status": "EXPERIMENTS_VALIDATED_FORMAL_RESULTS_UNCHANGED",
        "p0": {
            "status": "WITHDRAWN_BY_USER",
            "effect": "excluded from validation, conclusions, paper recommendation, and downstream propagation",
            "frozen_a08": "refund interpretation remains authoritative",
        },
        "p1": {
            "preferred_candidate": "alpha=0.5",
            "total_cost_yuan": p1["runs"]["alpha_0_5"]["total_cost_yuan"],
            "saving_vs_frozen_q3_yuan": -p1["comparison_to_alpha_0"]["alpha_0_5"]["total_cost_yuan"],
            "emergency_reduction_kwh": -p1["comparison_to_alpha_0"]["alpha_0_5"]["emergency_purchase_kwh"],
            "lower_cost_months": p1["monthly_direction"]["alpha_0_5"]["lower_cost_months"],
            "decision": "RETAIN_AS_UPGRADE_CANDIDATE_NOT_PROMOTED",
        },
        "p2": {
            "q4_alpha05_with_price_correction_total_cost_yuan": p2["runs"]["load05_price1"]["total_cost_yuan"],
            "saving_from_load_feedback_with_price_correction_yuan": -p2["cost_decomposition"]["load_feedback_effect_with_price_correction_yuan"],
            "lower_cost_months": sum(delta < 0 for delta in q4_monthly.values()),
            "months": len(q4_monthly),
            "price_correction_effect_with_feedback_yuan": p2["cost_decomposition"]["price_correction_effect_with_load_feedback_yuan"],
            "interaction_yuan": p2["cost_decomposition"]["interaction_yuan"],
            "decision": "LOAD_FEEDBACK_RETAINED_AS_TRANSFER_CANDIDATE; PRICE_CORRECTION_NOT_A_PRIMARY_GAIN",
        },
        "p3": {
            "load05_only_value_yuan": -p3["effects"]["load05_only_vs_none_cost_yuan"],
            "load05_value_added_to_state_pv_yuan": -p3["effects"]["load05_added_to_state_pv_cost_yuan"],
            "decision": "RETAIN_FOR_MAIN_TEXT_MECHANISM_EXPLANATION",
        },
        "p4": {
            "q4_2_cost_increase_yuan": p4["comparison"]["q4_2"]["reserve_minus_greedy_total_cost_yuan"],
            "q4_3_cost_increase_yuan": p4["comparison"]["q4_3"]["reserve_minus_greedy_total_cost_yuan"],
            "decision": "REJECTED_NO_GAIN_NO_MORE_PARAMETER_SCAN",
        },
        "independent_validation": validation["status"],
        "frozen_hashes": frozen_hashes(),
    }
    decision_path = RESULTS / "refinement_decision_summary.json"
    write_json(decision_path, decision)

    code_names = (
        "refinement_common.py",
        "q3_p0_a08_reoptimization.py",
        "q3_p1_load_feedback_ablation.py",
        "q4_p2_feedback_price_2x2.py",
        "q4_p2_alpha05_transfer.py",
        "q3_p3_information_ablation.py",
        "q3_p3_alpha05_selected.py",
        "q4_p4_evening_soc_reserve.py",
        "validate_q3_q4_refinement.py",
        "freeze_q3_q4_refinement.py",
    )
    paths = list(RESULTS.glob("*")) + list(VALIDATION.glob("*"))
    paths += [PROJECT_ROOT / "code" / name for name in code_names]
    paths += [
        PROJECT_ROOT / "Q3_Q4精修实验报告.md",
        PROJECT_ROOT / "模型拓展_消融_敏感性总账.md",
        PROJECT_ROOT / "论文推荐实验清单.md",
    ]
    artifacts = [
        {
            "path": str(path.relative_to(PROJECT_ROOT)).replace("\\", "/"),
            "bytes": path.stat().st_size,
            "sha256": sha256(path),
        }
        for path in sorted(paths, key=lambda value: str(value))
    ]
    manifest = {
        "schema_version": 1,
        "status": "PASS" if validation["status"] == "PASS" else "FAIL",
        "scope": "Independent P1-P4 refinement artifacts; P0 retained only as withdrawn isolated provenance",
        "artifact_count": len(artifacts),
        "artifacts": artifacts,
        "frozen_formal_artifacts": frozen_hashes(),
        "formal_results_unchanged": frozen_hashes() == validation["frozen_hashes"],
        "decision_summary": str(decision_path.relative_to(PROJECT_ROOT)).replace("\\", "/"),
    }
    write_json(INTERMEDIATE / "refinement_manifest.json", manifest)
    print(json.dumps({"status": manifest["status"], "artifacts": len(artifacts), "formal_unchanged": manifest["formal_results_unchanged"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
