from __future__ import annotations

import json

from common_data import PROJECT_ROOT, sha256


def main() -> None:
    files = [
        "Q3_因果负载反馈升级候选.md",
        "code/q3_load_feedback_candidate.py",
        "code/validate_q3_load_feedback_candidate.py",
        "results/q3_load_feedback_candidate_summary.json",
        "results/q3_load_feedback_8comb_detail.csv",
        "results/q3_load_feedback_8comb_plan_versions.csv",
        "results/q3_load_feedback_8comb_daily.csv",
        "results/q3_load_feedback_8comb_storage_4h.csv",
        "results/q3_load_feedback_8comb_emergency_events.csv",
        "validation/q3_load_feedback_candidate_validation.json",
    ]
    summary = json.loads((PROJECT_ROOT / files[3]).read_text(encoding="utf-8"))
    validation = json.loads((PROJECT_ROOT / files[-1]).read_text(encoding="utf-8"))
    if validation["status"] != "PASS":
        raise ValueError("候选验证未通过，拒绝冻结")
    if not summary["frozen_files_unchanged"]:
        raise ValueError("Q1-Q4冻结文件发生变化，拒绝冻结候选")
    manifest = {
        "schema_version": 1,
        "status": "FROZEN_CANDIDATE_NOT_PROMOTED",
        "decision": summary["decision"],
        "main_results_modified": False,
        "validation_status": validation["status"],
        "files": {path: {"sha256": sha256(PROJECT_ROOT / path), "bytes": (PROJECT_ROOT / path).stat().st_size} for path in files},
        "protected_main_files": summary["frozen_hashes_after"],
    }
    output = PROJECT_ROOT / "intermediate/q3_load_feedback_candidate_freeze_manifest.json"
    output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": manifest["status"], "output": str(output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
