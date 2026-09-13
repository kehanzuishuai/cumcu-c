from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(os.environ.get("CUMCM_PROJECT_ROOT", Path.cwd())).resolve()
FILES = [
    "Q2轻量组件消融与第二网上方案对照.md",
    "模型假设台账.md",
    "code/q2_component_ablation.py",
    "code/validate_q2_component_ablation_independent.py",
    "results/q2_component_ablation_summary.json",
    "results/q2_component_ablation_daily.csv",
    "results/q2_component_ablation_detail.csv",
    "validation/q2_component_ablation_validation.json",
    "validation/q2_component_ablation_independent.json",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


missing = [name for name in FILES if not (ROOT / name).is_file()]
if missing:
    raise FileNotFoundError(missing)
summary = json.loads((ROOT / "results/q2_component_ablation_summary.json").read_text(encoding="utf-8"))
independent = json.loads((ROOT / "validation/q2_component_ablation_independent.json").read_text(encoding="utf-8"))
if summary["status"] != "PASS" or independent["status"] != "PASS" or not summary["frozen_main_unchanged"]:
    raise RuntimeError("消融尚未满足冻结条件")
current_frozen = {
    relative: sha256(ROOT / relative)
    for relative in summary["frozen_hashes_after"]
}
if current_frozen != summary["frozen_hashes_after"]:
    raise RuntimeError("当前Q2主结果在消融后发生变化")
manifest = {
    "schema_version": 1,
    "status": "FROZEN_EXPERIMENT_ONLY",
    "created_at_utc": datetime.now(timezone.utc).isoformat(),
    "frozen_main_unchanged": True,
    "frozen_q2_sha256": current_frozen,
    "files": [
        {"path": name.replace("\\", "/"), "bytes": (ROOT / name).stat().st_size, "sha256": sha256(ROOT / name)}
        for name in FILES
    ],
}
(ROOT / "intermediate/q2_component_ablation_freeze_manifest.json").write_text(
    json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
)
print(json.dumps({"status": manifest["status"], "files": len(FILES)}, ensure_ascii=False))
