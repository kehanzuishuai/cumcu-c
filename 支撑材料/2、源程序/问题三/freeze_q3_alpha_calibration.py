from __future__ import annotations

import hashlib
import json
from pathlib import Path

from common_data import PROJECT_ROOT


EXP = PROJECT_ROOT / "experiments" / "q3_alpha_calibration"
FILES = (
    "results/alpha_calibration_summary.json",
    "results/alpha标定数值表.md",
    "validation/alpha_calibration_independent.json",
    "intermediate/selection_lock.json",
)
CODE = (
    "code/q3_alpha_time_order_calibration.py",
    "code/validate_q3_alpha_calibration.py",
    "code/freeze_q3_alpha_calibration.py",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


summary = json.loads((EXP / FILES[0]).read_text(encoding="utf-8"))
validation = json.loads((EXP / FILES[2]).read_text(encoding="utf-8"))
manifest = {
    "schema_version": 1,
    "status": "FROZEN_PASS" if summary["status"] == validation["status"] == "PASS" and summary["formal_results_unchanged"] else "FAIL",
    "selected_alpha": summary["selected_alpha"],
    "promotion": "NOT_AUTHORIZED",
    "split": summary["split"],
    "artifacts_sha256": {name: sha256(EXP / name) for name in FILES},
    "code_sha256": {name: sha256(PROJECT_ROOT / name) for name in CODE},
    "formal_hashes": summary["formal_hashes_after"],
}
output = EXP / "intermediate" / "alpha_calibration_manifest.json"
output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({"status": manifest["status"], "selected_alpha": manifest["selected_alpha"]}, ensure_ascii=False))
if manifest["status"] != "FROZEN_PASS":
    raise RuntimeError("alpha calibration freeze failed")
