from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(os.environ.get("CUMCM_PROJECT_ROOT", Path.cwd())).resolve()
FILES = [
    "Q4模型与结果.md",
    "模型假设台账.md",
    "code/q3_solve.py",
    "code/q4_solve.py",
    "code/validate_q4_independent.py",
    "code/build_result2.mjs",
    "code/build_result3.mjs",
    "results/q4_summary.json",
    "results/q4_2_detail.csv",
    "results/q4_2_daily.csv",
    "results/q4_2_storage_4h.csv",
    "results/q4_2_emergency_events.csv",
    "results/result4-2.xlsx",
    "results/q4_3_detail.csv",
    "results/q4_3_daily.csv",
    "results/q4_3_storage_4h.csv",
    "results/q4_3_emergency_events.csv",
    "results/q4_3_plan_versions.csv",
    "results/result4-3.xlsx",
    "validation/q4_2_validation.json",
    "validation/q4_3_validation.json",
    "validation/q4_independent_recompute.json",
    "validation/result4-2_workbook_validation.json",
    "validation/result4-3_workbook_validation.json",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


missing = [relative for relative in FILES if not (ROOT / relative).is_file()]
if missing:
    raise FileNotFoundError(f"Missing Q4 freeze files: {missing}")

manifest = {
    "schema_version": 1,
    "question": "Q4",
    "status": "FROZEN",
    "created_at_utc": datetime.now(timezone.utc).isoformat(),
    "known_conflict": "A01 natural-day label correction is a frozen working convention, not an official erratum.",
    "files": [
        {
            "path": relative.replace("\\", "/"),
            "bytes": (ROOT / relative).stat().st_size,
            "sha256": sha256(ROOT / relative),
        }
        for relative in FILES
    ],
}
(ROOT / "intermediate" / "q4_freeze_manifest.json").write_text(
    json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
)
print(json.dumps({"status": "FROZEN", "files": len(FILES)}, ensure_ascii=False))
