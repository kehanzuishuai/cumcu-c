#!/usr/bin/env python3
"""Freeze a hash-verified CUMCM submission into a new immutable-version directory."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any, Iterable


CATEGORY_FIELDS = ("code", "results", "figures", "support", "ai_declarations", "additional_files")
AUDIT_FIELDS = {
    "ai_used",
    "has_support_materials",
    "uses_programs",
    "support_dir",
    "support_archive",
    "forbidden_terms",
    "terminology_groups",
    "identity_terms",
    "latex",
    "reproducibility",
}
PAPER_READY_ROLES = {
    "interpretation_final",
    "model_plan_final",
    "ambiguity_decisions",
    "granularity_contract",
    "hard_constraints",
    "interpretation_decisions",
    "model_assumptions",
}
FIGURE_QA = ("density", "evidence_richness", "portfolio", "a4_visual")
FLOWCHART_QA = ("logic_match", "editability", "a4_visual")
SOURCE_SUFFIXES = {".tex", ".docx", ".md", ".qmd", ".typ", ".odt"}
REQUIRED_BOOLEAN_AUDIT_FIELDS = ("ai_used", "has_support_materials", "uses_programs")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return value


def standard_metadata(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    match = re.search(r'^standard_version:\s*["\']?([^"\'\r\n]+)', text, flags=re.MULTILINE)
    if not match:
        raise ValueError(f"standard_version is missing from {path}")
    return {"version": match.group(1).strip(), "sha256": sha256_file(path)}


def project_entry(project_root: Path, raw: Any, label: str) -> tuple[Path, str]:
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError(f"{label} must be a non-empty project-relative path")
    relative = Path(raw)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"{label} must stay inside project root: {raw}")
    candidate = project_root / relative
    resolved = candidate.resolve()
    try:
        resolved.relative_to(project_root)
    except ValueError as exc:
        raise ValueError(f"{label} escapes project root: {raw}") from exc
    if not candidate.exists():
        raise ValueError(f"{label} does not exist: {raw}")
    return candidate, relative.as_posix()


def verified_file_ref(project_root: Path, value: Any, label: str) -> tuple[Path, str]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    path, relative = project_entry(project_root, value.get("path"), f"{label}.path")
    if not path.is_file():
        raise ValueError(f"{label} is not a file: {relative}")
    expected = value.get("sha256")
    actual = sha256_file(path)
    if not isinstance(expected, str) or expected.lower() != actual:
        raise ValueError(f"{label} SHA-256 mismatch: {relative}")
    return path, relative


def expand_entry(project_root: Path, raw: Any, label: str) -> list[tuple[Path, str]]:
    path, relative = project_entry(project_root, raw, label)
    if path.is_file():
        return [(path, relative)]
    if not path.is_dir():
        raise ValueError(f"{label} is neither file nor directory: {relative}")
    expanded = []
    for child in sorted(path.rglob("*")):
        if child.is_file():
            resolved = child.resolve()
            try:
                resolved.relative_to(project_root)
            except ValueError as exc:
                raise ValueError(f"{label} contains a file outside project root: {child}") from exc
            expanded.append((child, child.relative_to(project_root).as_posix()))
    return expanded


def add_files(
    collected: dict[str, dict[str, Any]], entries: Iterable[tuple[Path, str]], category: str
) -> None:
    for path, relative in entries:
        if relative == "audit_manifest.json":
            raise ValueError("input files may not replace the generated audit_manifest.json")
        item = collected.setdefault(relative, {"path": path, "categories": set()})
        item["categories"].add(category)


def verify_paper_ready(
    project_root: Path, manifest_path: Path, standard: dict[str, str]
) -> tuple[dict[str, Any], list[tuple[Path, str]]]:
    manifest = load_json(manifest_path)
    if manifest.get("schema_version") != 1 or manifest.get("status") != "PAPER_READY":
        raise ValueError("paper_ready_manifest is not PAPER_READY schema_version 1")
    if manifest.get("standard") != standard:
        raise ValueError("paper_ready_manifest standard version/hash is stale")
    files = manifest.get("files")
    if not isinstance(files, list) or {item.get("role") for item in files if isinstance(item, dict)} != PAPER_READY_ROLES:
        raise ValueError("paper_ready_manifest must contain the two finals and five contracts")
    return manifest, [
        verified_file_ref(project_root, item, f"paper_ready.files[{index}]")
        for index, item in enumerate(files)
    ]


def verify_figure_manifest(
    project_root: Path,
    manifest_path: Path,
    standard: dict[str, str],
    paper_ready_sha256: str,
) -> tuple[dict[str, Any], list[tuple[Path, str, str]]]:
    manifest = load_json(manifest_path)
    if manifest.get("schema_version") != 2 or manifest.get("status") != "FIGURES_READY":
        raise ValueError("figure_manifest is not FIGURES_READY schema_version 2")
    if manifest.get("standard") != standard:
        raise ValueError("figure_manifest standard version/hash is stale")
    if manifest.get("paper_ready_manifest_sha256") != paper_ready_sha256:
        raise ValueError("figure_manifest points to a stale paper_ready_manifest")
    assets = manifest.get("assets")
    if not isinstance(assets, list) or not assets:
        raise ValueError("figure_manifest.assets must be non-empty")
    dependencies: list[tuple[Path, str, str]] = []
    asset_ids: list[str] = []
    for index, asset in enumerate(assets):
        if not isinstance(asset, dict) or asset.get("status") != "FINAL":
            raise ValueError(f"figure_manifest.assets[{index}] is not FINAL")
        asset_id = asset.get("asset_id")
        if not isinstance(asset_id, str) or not asset_id:
            raise ValueError(f"figure_manifest.assets[{index}] has invalid asset_id")
        asset_ids.append(asset_id)
        asset_type = asset.get("asset_type")
        required_qa = FIGURE_QA if asset_type == "figure" else FLOWCHART_QA
        qa = asset.get("qa")
        if asset_type not in {"figure", "flowchart"} or not isinstance(qa, dict):
            raise ValueError(f"figure_manifest.assets[{index}] has invalid type/QA")
        if any(qa.get(key) != "PASS" for key in required_qa):
            raise ValueError(f"figure_manifest.assets[{index}] has unresolved QA")
        if asset_type == "flowchart" and asset.get("human_approved") is not True:
            raise ValueError(f"figure_manifest.assets[{index}] lacks human approval")
        brief_contract = asset.get("brief_contract")
        expected_status = "READY_FOR_DRAWING" if asset_type == "figure" else "LOGIC_FIXED"
        expected_contract = {
            "schema_version": 2,
            "brief_type": asset_type,
            "asset_id": asset_id,
            "revision": asset.get("brief_revision"),
            "status": expected_status,
            "standard_version": standard["version"],
            "paper_ready_manifest_sha256": paper_ready_sha256,
        }
        if not isinstance(brief_contract, dict) or any(
            brief_contract.get(key) != value for key, value in expected_contract.items()
        ):
            raise ValueError(f"figure_manifest.assets[{index}] has stale Brief contract")
        if (
            not isinstance(brief_contract.get("contract_ids"), list)
            or brief_contract.get("contract_ids") != asset.get("contract_ids")
            or not re.fullmatch(r"[0-9a-f]{64}", str(brief_contract.get("semantic_sha256", "")))
        ):
            raise ValueError(f"figure_manifest.assets[{index}] has invalid semantic Brief snapshot")
        body_context = brief_contract.get("body_context")
        paper_context_ref = body_context.get("paper_source") if isinstance(body_context, dict) else None
        if (
            not isinstance(body_context, dict)
            or not isinstance(paper_context_ref, dict)
            or not isinstance(paper_context_ref.get("path"), str)
            or not paper_context_ref["path"]
            or not re.fullmatch(r"[0-9a-f]{64}", str(paper_context_ref.get("sha256", "")))
            or any(
                not re.fullmatch(r"[0-9a-f]{64}", str(body_context.get(field, "")))
                for field in ("before_sha256", "after_sha256")
            )
        ):
            raise ValueError(f"figure_manifest.assets[{index}] has invalid body-context snapshot")
        if asset_type == "flowchart" and brief_contract.get("human_approved") is not True:
            raise ValueError(f"figure_manifest.assets[{index}] Brief lacks human approval")
        path, relative = verified_file_ref(project_root, asset.get("brief"), f"assets[{index}].brief")
        dependencies.append((path, relative, "brief"))
        source_values = asset.get("data_sources", [])
        output_values = asset.get("outputs", [])
        if not isinstance(source_values, list) or not isinstance(output_values, list) or not output_values:
            raise ValueError(f"figure_manifest.assets[{index}] has invalid sources/outputs")
        if asset_type == "figure" and brief_contract.get("data_sources") != source_values:
            raise ValueError(f"figure_manifest.assets[{index}] Brief/data source snapshot mismatch")
        for source_index, value in enumerate(source_values):
            path, relative = verified_file_ref(
                project_root, value, f"assets[{index}].data_sources[{source_index}]"
            )
            dependencies.append((path, relative, "results"))
        if asset_type == "figure":
            path, relative = verified_file_ref(
                project_root, asset.get("script"), f"assets[{index}].script"
            )
            dependencies.append((path, relative, "code"))
        else:
            path, relative = verified_file_ref(
                project_root, asset.get("source"), f"assets[{index}].source"
            )
            if path.suffix.lower() != ".pptx":
                raise ValueError(f"figure_manifest.assets[{index}] flowchart source is not .pptx")
            dependencies.append((path, relative, "figures"))
            if asset.get("script") is not None:
                path, relative = verified_file_ref(
                    project_root, asset.get("script"), f"assets[{index}].script"
                )
                dependencies.append((path, relative, "code"))
        for output_index, value in enumerate(output_values):
            path, relative = verified_file_ref(
                project_root, value, f"assets[{index}].outputs[{output_index}]"
            )
            dependencies.append((path, relative, "figures"))
    if len(asset_ids) != len(set(asset_ids)):
        raise ValueError("figure_manifest contains duplicate asset_id")
    return manifest, dependencies


def build_freeze_payload(
    *, project_root: Path, plan: dict[str, Any], standard_path: Path
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    root = project_root.resolve()
    if plan.get("schema_version") != 1:
        raise ValueError("freeze_plan schema_version must be 1")
    blockers = plan.get("blockers")
    if blockers != []:
        raise ValueError("freeze_plan blockers must be an empty list")
    standard = standard_metadata(standard_path)

    audit_fields = plan.get("audit_fields")
    if not isinstance(audit_fields, dict) or set(audit_fields) - AUDIT_FIELDS:
        unknown = sorted(set(audit_fields) - AUDIT_FIELDS) if isinstance(audit_fields, dict) else []
        raise ValueError(f"audit_fields contains unsupported keys: {unknown}")
    for field in REQUIRED_BOOLEAN_AUDIT_FIELDS:
        if not isinstance(audit_fields.get(field), bool):
            raise ValueError(f"audit_fields.{field} must be explicitly true or false")

    paper_ready_path, paper_ready_relative = project_entry(
        root, plan.get("paper_ready_manifest"), "paper_ready_manifest"
    )
    figure_manifest_path, figure_manifest_relative = project_entry(
        root, plan.get("figure_manifest"), "figure_manifest"
    )
    if not paper_ready_path.is_file() or not figure_manifest_path.is_file():
        raise ValueError("upstream manifests must be files")
    paper_ready, paper_ready_files = verify_paper_ready(root, paper_ready_path, standard)
    _, figure_dependencies = verify_figure_manifest(
        root, figure_manifest_path, standard, sha256_file(paper_ready_path)
    )

    paper_path, paper_relative = project_entry(root, plan.get("paper"), "paper")
    source_path, source_relative = project_entry(root, plan.get("source"), "source")
    if not paper_path.is_file() or paper_path.suffix.lower() != ".pdf":
        raise ValueError("paper must be the unique final PDF")
    if (
        not source_path.is_file()
        or source_path.resolve() == paper_path.resolve()
        or source_path.suffix.lower() not in SOURCE_SUFFIXES
    ):
        raise ValueError("source must be a distinct final .tex/.docx/.md/.qmd/.typ/.odt file")

    problem_values = plan.get("problem_files")
    if not isinstance(problem_values, list) or not problem_values:
        raise ValueError("problem_files must list the original problem and any supplied attachments")
    problem_files = []
    for index, value in enumerate(problem_values):
        problem_files.extend(expand_entry(root, value, f"problem_files[{index}]"))

    collected: dict[str, dict[str, Any]] = {}
    add_files(collected, [(paper_path, paper_relative)], "paper")
    add_files(collected, [(source_path, source_relative)], "source")
    add_files(collected, problem_files, "problem")
    add_files(collected, [(paper_ready_path, paper_ready_relative)], "manifest")
    add_files(collected, [(figure_manifest_path, figure_manifest_relative)], "manifest")
    add_files(collected, paper_ready_files, "upstream")
    for path, relative, category in figure_dependencies:
        add_files(collected, [(path, relative)], category)

    category_entries: dict[str, list[tuple[Path, str]]] = {}
    for category in CATEGORY_FIELDS:
        values = plan.get(category, [])
        if not isinstance(values, list):
            raise ValueError(f"{category} must be a list")
        entries: list[tuple[Path, str]] = []
        for index, value in enumerate(values):
            entries.extend(expand_entry(root, value, f"{category}[{index}]"))
        category_entries[category] = entries

    if audit_fields["uses_programs"] and not category_entries["code"]:
        raise ValueError("uses_programs=true requires non-empty code entries")
    if not category_entries["results"]:
        raise ValueError("results must contain at least one final result file")
    if not category_entries["figures"]:
        raise ValueError("figures must contain at least one final figure file")
    if audit_fields["has_support_materials"] and not category_entries["support"]:
        raise ValueError("has_support_materials=true requires non-empty support entries")
    if not audit_fields["has_support_materials"] and category_entries["support"]:
        raise ValueError("has_support_materials=false conflicts with non-empty support entries")
    if audit_fields["ai_used"]:
        if not audit_fields["has_support_materials"]:
            raise ValueError("ai_used=true requires has_support_materials=true")
        declarations = category_entries["ai_declarations"]
        if not declarations or not any(path.name == "AI 工具使用详情.pdf" for path, _ in declarations):
            raise ValueError("ai_used=true requires AI 工具使用详情.pdf in ai_declarations")
    elif category_entries["ai_declarations"]:
        raise ValueError("ai_used=false conflicts with non-empty ai_declarations")

    for category, entries in category_entries.items():
        add_files(collected, entries, category)

    required_files = plan.get("required_files", [])
    if not isinstance(required_files, list):
        raise ValueError("required_files must be a list")
    frozen_required = []
    for index, item in enumerate(required_files):
        if not isinstance(item, dict):
            raise ValueError(f"required_files[{index}] must be an object")
        path, relative = project_entry(root, item.get("path"), f"required_files[{index}].path")
        if not path.is_file():
            raise ValueError(f"required_files[{index}] is not a file")
        add_files(collected, [(path, relative)], "required")
        frozen_item = dict(item)
        frozen_item["path"] = relative
        frozen_item["sha256"] = sha256_file(path)
        frozen_required.append(frozen_item)

    frozen_files = [
        {
            "path": relative,
            "sha256": sha256_file(item["path"]),
            "categories": sorted(item["categories"]),
        }
        for relative, item in sorted(collected.items())
    ]
    manifest = {
        "freeze_schema_version": 1,
        "frozen": True,
        "blockers": [],
        "standard": standard,
        "paper": paper_relative,
        "source": source_relative,
        "problem_files": [relative for _, relative in problem_files],
        "problem_count": paper_ready.get("problem_count"),
        "paper_ready_manifest": paper_ready_relative,
        "figure_manifest": figure_manifest_relative,
        "upstream_manifests": {
            "paper_ready": {"path": paper_ready_relative, "sha256": sha256_file(paper_ready_path)},
            "figures": {"path": figure_manifest_relative, "sha256": sha256_file(figure_manifest_path)},
        },
        "freeze_plan_sha256": hashlib.sha256(canonical(plan).encode("utf-8")).hexdigest(),
        "required_files": frozen_required,
        "frozen_files": frozen_files,
    }
    manifest.update(audit_fields)
    return manifest, collected


def freeze_package(
    *, project_root: Path, plan: dict[str, Any], destination: Path, standard_path: Path
) -> dict[str, Any]:
    root = project_root.resolve()
    target = destination if destination.is_absolute() else root / destination
    target = target.resolve()
    if target == root:
        raise ValueError("destination may not be the project root")
    if target.exists():
        raise FileExistsError(f"destination already exists: {target}")
    manifest, collected = build_freeze_payload(
        project_root=root, plan=plan, standard_path=standard_path
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{target.name}-staging-", dir=target.parent))
    try:
        for relative, item in sorted(collected.items()):
            output = staging / Path(relative)
            output.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item["path"], output)
            if sha256_file(output) != sha256_file(item["path"]):
                raise OSError(f"copy verification failed: {relative}")
        (staging / "audit_manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        staging.replace(target)
    except Exception:
        if staging.exists():
            shutil.rmtree(staging)
        raise
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_root", type=Path)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument(
        "--standard",
        type=Path,
        default=Path(__file__).resolve().parents[2] / "_shared" / "cumcm" / "C题规范.md",
    )
    args = parser.parse_args()
    try:
        manifest = freeze_package(
            project_root=args.project_root,
            plan=load_json(args.plan),
            destination=args.destination,
            standard_path=args.standard,
        )
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
