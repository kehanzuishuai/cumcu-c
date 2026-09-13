#!/usr/bin/env python3
"""Create a hash-verified figure_manifest.json after existing figure gates pass."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import zipfile
from xml.etree import ElementTree
from pathlib import Path
from typing import Any


FIGURE_QA = ("density", "evidence_richness", "portfolio", "a4_visual")
FLOWCHART_QA = ("logic_match", "editability", "a4_visual")
PAPER_READY_ROLES = {
    "interpretation_final",
    "model_plan_final",
    "ambiguity_decisions",
    "granularity_contract",
    "hard_constraints",
    "interpretation_decisions",
    "model_assumptions",
}
BRIEF_FENCE = re.compile(r"```(?:yaml|yml)\s*\r?\n(.*?)\r?\n```", re.IGNORECASE | re.DOTALL)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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


def resolve_project_file(project_root: Path, raw_path: Any, label: str) -> tuple[Path, str]:
    if not isinstance(raw_path, str) or not raw_path.strip():
        raise ValueError(f"{label}.path must be a non-empty project-relative path")
    relative = Path(raw_path)
    if relative.is_absolute():
        raise ValueError(f"{label}.path must be project-relative: {raw_path}")
    resolved = (project_root / relative).resolve()
    try:
        normalized = resolved.relative_to(project_root).as_posix()
    except ValueError as exc:
        raise ValueError(f"{label}.path escapes project root: {raw_path}") from exc
    if not resolved.is_file():
        raise ValueError(f"{label}.path is not a file: {raw_path}")
    return resolved, normalized


def materialize_file_ref(project_root: Path, value: Any, label: str) -> dict[str, str]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object with path")
    resolved, normalized = resolve_project_file(project_root, value.get("path"), label)
    actual = sha256_file(resolved)
    expected = value.get("sha256")
    if expected not in (None, "") and expected != actual:
        raise ValueError(f"{label} SHA-256 mismatch: {normalized}")
    return {"path": normalized, "sha256": actual}


def parse_yaml_scalar(raw: str) -> Any:
    value = raw.strip()
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        return [] if not inner else [parse_yaml_scalar(item) for item in split_inline(inner)]
    if value.startswith("{") and value.endswith("}"):
        inner = value[1:-1].strip()
        if not inner:
            return {}
        result: dict[str, Any] = {}
        for item in split_inline(inner):
            key, separator, item_value = item.partition(":")
            if not separator or not key.strip():
                raise ValueError(f"unsupported inline YAML mapping: {value}")
            result[key.strip()] = parse_yaml_scalar(item_value)
        return result
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"\"", "'"}:
        return value[1:-1]
    lowered = value.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if lowered in {"null", "none", "~"}:
        return None
    if re.fullmatch(r"[+-]?\d+", value) and len(value.lstrip("+-")) <= 18:
        return int(value)
    return value


def split_inline(value: str) -> list[str]:
    parts: list[str] = []
    start = 0
    quote: str | None = None
    depth = 0
    for index, character in enumerate(value):
        if quote:
            if character == quote and (index == 0 or value[index - 1] != "\\"):
                quote = None
        elif character in {"\"", "'"}:
            quote = character
        elif character in "[{(":
            depth += 1
        elif character in "]})":
            depth -= 1
        elif character == "," and depth == 0:
            parts.append(value[start:index].strip())
            start = index + 1
    if quote or depth != 0:
        raise ValueError(f"unbalanced inline YAML value: {value}")
    parts.append(value[start:].strip())
    if any(not part for part in parts):
        raise ValueError(f"empty item in inline YAML value: {value}")
    return parts


def parse_yaml_subset(payload: str) -> dict[str, Any]:
    """Parse the dependency-free YAML subset used by the Brief templates."""
    tokens: list[tuple[int, str, int]] = []
    for line_number, raw_line in enumerate(payload.splitlines(), start=1):
        if not raw_line.strip() or raw_line.lstrip().startswith("#") or raw_line.strip() == "---":
            continue
        if "\t" in raw_line[: len(raw_line) - len(raw_line.lstrip())]:
            raise ValueError(f"tabs are not allowed for YAML indentation at line {line_number}")
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        tokens.append((indent, raw_line.strip(), line_number))

    def split_mapping(content: str, line_number: int) -> tuple[str, str]:
        key, separator, value = content.partition(":")
        if not separator or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]*", key.strip()):
            raise ValueError(f"unsupported YAML mapping at line {line_number}: {content}")
        return key.strip(), value.strip()

    def parse_block(index: int, indent: int) -> tuple[Any, int]:
        if index >= len(tokens) or tokens[index][0] != indent:
            raise ValueError("invalid YAML indentation")
        is_list = tokens[index][1].startswith("-")
        container: Any = [] if is_list else {}
        while index < len(tokens):
            current_indent, content, line_number = tokens[index]
            if current_indent < indent:
                break
            if current_indent > indent:
                raise ValueError(f"unexpected indentation at line {line_number}")
            if is_list:
                if not content.startswith("-"):
                    break
                remainder = content[1:].strip()
                index += 1
                if not remainder:
                    if index >= len(tokens) or tokens[index][0] <= indent:
                        raise ValueError(f"empty YAML list item at line {line_number}")
                    item, index = parse_block(index, tokens[index][0])
                    container.append(item)
                    continue
                if ":" in remainder:
                    key, raw_value = split_mapping(remainder, line_number)
                    item = {key: parse_yaml_scalar(raw_value) if raw_value else None}
                    if index < len(tokens) and tokens[index][0] > indent:
                        child, index = parse_block(index, tokens[index][0])
                        if not isinstance(child, dict):
                            if raw_value:
                                raise ValueError(f"list mapping has invalid child at line {line_number}")
                            item[key] = child
                        else:
                            for child_key, child_value in child.items():
                                if child_key in item:
                                    raise ValueError(f"duplicate YAML key {child_key!r} at line {line_number}")
                                item[child_key] = child_value
                    container.append(item)
                else:
                    container.append(parse_yaml_scalar(remainder))
            else:
                if content.startswith("-"):
                    break
                key, raw_value = split_mapping(content, line_number)
                if key in container:
                    raise ValueError(f"duplicate YAML key {key!r} at line {line_number}")
                index += 1
                if raw_value:
                    if raw_value in {"|", ">"}:
                        raise ValueError(f"block YAML scalars are not supported at line {line_number}")
                    container[key] = parse_yaml_scalar(raw_value)
                elif index < len(tokens) and tokens[index][0] > indent:
                    container[key], index = parse_block(index, tokens[index][0])
                else:
                    container[key] = None
        return container, index

    if not tokens:
        return {}
    result, final_index = parse_block(0, tokens[0][0])
    if final_index != len(tokens) or not isinstance(result, dict):
        raise ValueError("Brief YAML root must be a mapping")
    return result


def parse_brief_records(path: Path) -> list[dict[str, Any]]:
    """Read fenced Brief records using the template's dependency-free YAML subset."""
    text = path.read_text(encoding="utf-8")
    payloads = BRIEF_FENCE.findall(text)
    if not payloads and re.search(r"^brief_schema_version:\s*", text, flags=re.MULTILINE):
        payloads = [text]
    records: list[dict[str, Any]] = []
    for payload in payloads:
        record = parse_yaml_subset(payload)
        if "brief_schema_version" in record or "brief_type" in record:
            records.append(record)
    if not records:
        raise ValueError(f"Brief contains no fenced YAML records: {path}")
    return records


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_value(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def require_string(record: dict[str, Any], field: str, asset_id: str) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{asset_id}: Brief {field} must be a non-empty string")
    return value.strip()


def require_string_list(
    record: dict[str, Any], field: str, asset_id: str, *, allow_empty: bool = False
) -> list[str]:
    value = record.get(field)
    if not isinstance(value, list) or (not allow_empty and not value) or not all(
        isinstance(item, str) and item.strip() for item in value
    ):
        qualifier = "a string list" if allow_empty else "a non-empty string list"
        raise ValueError(f"{asset_id}: Brief {field} must be {qualifier}")
    return [item.strip() for item in value]


def require_nonempty_mapping(record: dict[str, Any], field: str, asset_id: str) -> dict[str, Any]:
    value = record.get(field)
    if not isinstance(value, dict) or not value:
        raise ValueError(f"{asset_id}: Brief {field} must be a non-empty mapping")
    return value


def extract_paper_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".docx":
        with zipfile.ZipFile(path) as archive:
            xml = archive.read("word/document.xml")
        root = ElementTree.fromstring(xml)
        paragraphs = [
            "".join(child.text or "" for child in node.iter() if child.tag.endswith("}t"))
            for node in root.iter()
            if node.tag.endswith("}p")
        ]
        return "\n".join(paragraphs)
    if suffix == ".odt":
        with zipfile.ZipFile(path) as archive:
            xml = archive.read("content.xml")
        root = ElementTree.fromstring(xml)
        paragraphs = [
            "".join(child.text or "" for child in node.iter() if child.text)
            for node in root.iter()
            if node.tag.endswith("}p") or node.tag.endswith("}h")
        ]
        return "\n".join(paragraphs)
    if suffix not in {".tex", ".md", ".qmd", ".typ", ".txt", ".rst"}:
        raise ValueError(f"unsupported paper_source format for body alignment: {path.suffix}")
    return path.read_text(encoding="utf-8")


def normalized_text(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(value)).strip()


def verify_body_context(
    project_root: Path,
    record: dict[str, Any],
    asset_id: str,
    before_field: str,
    after_field: str,
) -> dict[str, Any]:
    paper_ref = materialize_file_ref(project_root, record.get("paper_source"), f"{asset_id}.paper_source")
    paper_path, _ = resolve_project_file(project_root, paper_ref["path"], f"{asset_id}.paper_source")
    before = normalized_text(require_string(record, before_field, asset_id))
    after = normalized_text(require_string(record, after_field, asset_id))
    body = normalized_text(extract_paper_text(paper_path))
    before_at = body.find(before)
    after_at = body.find(after, before_at + len(before)) if before_at >= 0 else -1
    if before_at < 0:
        raise ValueError(f"{asset_id}: Brief {before_field} is not present in paper_source")
    if after_at < 0:
        raise ValueError(f"{asset_id}: Brief {after_field} is missing or not after {before_field}")
    return {
        "paper_source": paper_ref,
        "before_sha256": hashlib.sha256(before.encode("utf-8")).hexdigest(),
        "after_sha256": hashlib.sha256(after.encode("utf-8")).hexdigest(),
    }


def materialize_data_source(project_root: Path, value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    fields = value.get("fields")
    if not isinstance(fields, list) or not fields or not all(
        isinstance(field, str) and field.strip() for field in fields
    ):
        raise ValueError(f"{label}.fields must be a non-empty string list")
    result: dict[str, Any] = materialize_file_ref(project_root, value, label)
    result["fields"] = [field.strip() for field in fields]
    return result


def verify_brief_contract(
    *,
    project_root: Path,
    brief_path: Path,
    asset_id: str,
    asset_type: str,
    revision: int,
    standard_version: str,
    paper_ready_sha256: str,
) -> dict[str, Any]:
    id_field = "figure_id" if asset_type == "figure" else "flowchart_id"
    matches = [record for record in parse_brief_records(brief_path) if record.get(id_field) == asset_id]
    if len(matches) != 1:
        raise ValueError(f"{asset_id}: Brief must contain exactly one matching {id_field} record")
    record = matches[0]
    expected_status = "READY_FOR_DRAWING" if asset_type == "figure" else "LOGIC_FIXED"
    checks = {
        "brief_schema_version": 2,
        "brief_type": asset_type,
        "standard_version": standard_version,
        "paper_ready_manifest_sha256": paper_ready_sha256,
        id_field: asset_id,
        "revision": revision,
        "status": expected_status,
    }
    for field, expected in checks.items():
        if record.get(field) != expected:
            actual = record.get(field)
            if field == "status" and actual == "RESAMPLE_REQUIRED":
                raise ValueError(f"{asset_id}: Brief is RESAMPLE_REQUIRED")
            raise ValueError(f"{asset_id}: Brief {field} mismatch; expected {expected!r}, got {actual!r}")
    contract_ids = require_string_list(record, "contract_ids", asset_id, allow_empty=True)
    if asset_type == "figure":
        required_strings = (
            "question",
            "task_type",
            "claim",
            "evidence_object",
            "structure",
            "statistical_scope",
            "final_width",
            "caption_key_message",
            "paragraph_before_figure",
            "paragraph_after_figure",
        )
        for field in required_strings:
            require_string(record, field, asset_id)
        if record["task_type"] not in {
            "prediction", "optimization", "evaluation", "statistics", "classification",
            "clustering", "uncertainty", "sensitivity", "risk", "data_overview", "other",
        }:
            raise ValueError(f"{asset_id}: Brief task_type is outside the shared interface")
        if record["evidence_object"] not in {
            "sample", "time_series", "paired_observations", "interval", "matrix",
            "discrete_categories", "network", "composition",
        }:
            raise ValueError(f"{asset_id}: Brief evidence_object is outside the shared interface")
        require_string_list(record, "evidence_roles", asset_id)
        outputs = require_string_list(record, "outputs", asset_id)
        if not {"pdf", "png", "code", "caption"}.issubset(set(outputs)):
            raise ValueError(f"{asset_id}: Brief outputs must include pdf, png, code, and caption")
        require_nonempty_mapping(record, "units", asset_id)
        require_nonempty_mapping(record, "axes_or_groups", asset_id)
        require_nonempty_mapping(record, "scale_and_density", asset_id)
        brief_sources = record.get("data_sources")
        if not isinstance(brief_sources, list) or not brief_sources:
            raise ValueError(f"{asset_id}: Brief data_sources must be non-empty")
        body_context = verify_body_context(
            project_root,
            record,
            asset_id,
            "paragraph_before_figure",
            "paragraph_after_figure",
        )
        semantic_fields = {
            key: record.get(key)
            for key in (
                "question",
                "contract_ids",
                "task_type",
                "claim",
                "evidence_object",
                "evidence_roles",
                "structure",
                "statistical_scope",
                "units",
                "axes_or_groups",
                "comparison_baseline",
                "uncertainty_to_show",
                "required_annotations",
                "standard_chart_candidate",
                "advanced_candidate_inputs",
                "scale_and_density",
                "semantic_roles",
                "final_width",
                "outputs",
                "caption_key_message",
            )
        }
    else:
        for field in (
            "flowchart_type",
            "question",
            "purpose",
            "reading_order",
            "final_width",
            "paragraph_before_flowchart",
            "paragraph_after_flowchart",
        ):
            require_string(record, field, asset_id)
        if record["flowchart_type"] not in {"total", "question"}:
            raise ValueError(f"{asset_id}: Flowchart Brief flowchart_type must be total or question")
        if record["reading_order"] not in {"top_to_bottom", "left_to_right"}:
            raise ValueError(f"{asset_id}: Flowchart Brief reading_order is invalid")
        outputs = require_string_list(record, "outputs", asset_id)
        if "pptx" not in outputs or not {"pdf", "png"}.intersection(outputs):
            raise ValueError(f"{asset_id}: Flowchart Brief outputs must include pptx and pdf or png")
        nodes = record.get("nodes")
        edges = record.get("edges")
        if not isinstance(nodes, list) or not nodes or not all(isinstance(node, dict) for node in nodes):
            raise ValueError(f"{asset_id}: Flowchart Brief nodes must be a non-empty object list")
        node_ids: list[str] = []
        for index, node in enumerate(nodes):
            for field in ("id", "label", "role"):
                if not isinstance(node.get(field), str) or not node[field].strip():
                    raise ValueError(f"{asset_id}: Flowchart node[{index}].{field} is required")
            node_ids.append(node["id"].strip())
        if len(node_ids) != len(set(node_ids)):
            raise ValueError(f"{asset_id}: Flowchart node IDs must be unique")
        if not isinstance(edges, list) or not edges or not all(isinstance(edge, dict) for edge in edges):
            raise ValueError(f"{asset_id}: Flowchart Brief edges must be a non-empty object list")
        for index, edge in enumerate(edges):
            for field in ("from", "to"):
                if not isinstance(edge.get(field), str) or edge[field] not in node_ids:
                    raise ValueError(f"{asset_id}: Flowchart edge[{index}].{field} must reference a node ID")
        if record.get("human_approved") is not True:
            raise ValueError(f"{asset_id}: Flowchart Brief requires human_approved=true")
        body_context = verify_body_context(
            project_root,
            record,
            asset_id,
            "paragraph_before_flowchart",
            "paragraph_after_flowchart",
        )
        semantic_fields = {
            key: record.get(key)
            for key in (
                "flowchart_type",
                "question",
                "contract_ids",
                "purpose",
                "nodes",
                "edges",
                "reading_order",
                "final_width",
                "outputs",
            )
        }
    contract = {
        "schema_version": 2,
        "brief_type": asset_type,
        "asset_id": asset_id,
        "revision": revision,
        "status": expected_status,
        "standard_version": standard_version,
        "paper_ready_manifest_sha256": paper_ready_sha256,
        "contract_ids": contract_ids,
        "semantic_sha256": sha256_value(semantic_fields),
        "body_context": body_context,
    }
    if asset_type == "flowchart":
        contract["human_approved"] = True
    return contract


def verify_paper_ready_manifest(
    manifest_path: Path, project_root: Path, standard: dict[str, str]
) -> dict[str, Any]:
    resolved_manifest = manifest_path.resolve()
    try:
        resolved_manifest.relative_to(project_root)
    except ValueError as exc:
        raise ValueError("paper_ready_manifest must be inside project root") from exc
    if not resolved_manifest.is_file():
        raise ValueError("paper_ready_manifest is not a file")
    manifest_path = resolved_manifest
    manifest = load_json(manifest_path)
    if manifest.get("schema_version") != 1 or manifest.get("status") != "PAPER_READY":
        raise ValueError("paper_ready_manifest is not PAPER_READY schema_version 1")
    if manifest.get("standard") != standard:
        raise ValueError("paper_ready_manifest standard version/hash is stale")
    files = manifest.get("files")
    roles = {item.get("role") for item in files if isinstance(item, dict)} if isinstance(files, list) else set()
    if not isinstance(files, list) or len(files) != 7 or roles != PAPER_READY_ROLES:
        raise ValueError("paper_ready_manifest must list two finals and five contracts")
    for index, item in enumerate(files):
        materialize_file_ref(project_root, item, f"paper_ready.files[{index}]")
    return manifest


def normalize_asset(
    project_root: Path,
    asset: Any,
    *,
    standard_version: str,
    paper_ready_sha256: str,
) -> dict[str, Any]:
    if not isinstance(asset, dict):
        raise ValueError("each asset must be an object")
    asset_id = asset.get("asset_id")
    if not isinstance(asset_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", asset_id):
        raise ValueError("asset_id must be a stable filename-safe identifier")
    asset_type = asset.get("asset_type")
    if asset_type not in {"figure", "flowchart"}:
        raise ValueError(f"{asset_id}: asset_type must be figure or flowchart")
    if asset.get("status") != "FINAL":
        raise ValueError(f"{asset_id}: only FINAL assets may enter figure_manifest")
    revision = asset.get("brief_revision")
    if not isinstance(revision, int) or revision < 1:
        raise ValueError(f"{asset_id}: brief_revision must be a positive integer")
    contract_ids = asset.get("contract_ids", [])
    if not isinstance(contract_ids, list) or not all(
        isinstance(value, str) and value for value in contract_ids
    ):
        raise ValueError(f"{asset_id}: contract_ids must be a string list")

    qa = asset.get("qa")
    required_qa = FIGURE_QA if asset_type == "figure" else FLOWCHART_QA
    if not isinstance(qa, dict) or any(qa.get(key) != "PASS" for key in required_qa):
        raise ValueError(f"{asset_id}: unresolved QA state; required {', '.join(required_qa)}=PASS")
    if asset_type == "flowchart" and asset.get("human_approved") is not True:
        raise ValueError(f"{asset_id}: flowchart requires human_approved=true")

    raw_sources = asset.get("data_sources", [])
    if not isinstance(raw_sources, list) or (asset_type == "figure" and not raw_sources):
        raise ValueError(f"{asset_id}: figure data_sources must be a non-empty list")
    outputs = asset.get("outputs")
    if not isinstance(outputs, list) or not outputs:
        raise ValueError(f"{asset_id}: outputs must be a non-empty list")

    brief_value = asset.get("brief")
    if not isinstance(brief_value, dict):
        raise ValueError(f"{asset_id}.brief must be an object with path")
    brief_path, _ = resolve_project_file(
        project_root, brief_value.get("path"), f"{asset_id}.brief"
    )
    brief_ref = materialize_file_ref(project_root, brief_value, f"{asset_id}.brief")
    normalized_sources = [
        materialize_data_source(project_root, value, f"{asset_id}.data_sources[{index}]")
        for index, value in enumerate(raw_sources)
    ]
    brief_contract = verify_brief_contract(
        project_root=project_root,
        brief_path=brief_path,
        asset_id=asset_id,
        asset_type=asset_type,
        revision=revision,
        standard_version=standard_version,
        paper_ready_sha256=paper_ready_sha256,
    )
    if asset_type == "figure":
        records = parse_brief_records(brief_path)
        brief_record = next(record for record in records if record.get("figure_id") == asset_id)
        brief_sources = [
            materialize_data_source(
                project_root, value, f"{asset_id}.brief.data_sources[{index}]"
            )
            for index, value in enumerate(brief_record.get("data_sources", []))
        ]
        if brief_sources != normalized_sources:
            raise ValueError(f"{asset_id}: Brief data_sources path/hash/fields do not match asset records")
        brief_contract["data_sources"] = brief_sources
    if brief_contract["contract_ids"] != contract_ids:
        raise ValueError(f"{asset_id}: Brief contract_ids do not match asset records")

    normalized = {
        "asset_id": asset_id,
        "asset_type": asset_type,
        "brief_revision": revision,
        "contract_ids": contract_ids,
        "brief": brief_ref,
        "brief_contract": brief_contract,
        "data_sources": normalized_sources,
        "outputs": [
            materialize_file_ref(project_root, value, f"{asset_id}.outputs[{index}]")
            for index, value in enumerate(outputs)
        ],
        "qa": {key: qa[key] for key in required_qa},
        "status": "FINAL",
    }
    if asset_type == "figure":
        normalized["script"] = materialize_file_ref(
            project_root, asset.get("script"), f"{asset_id}.script"
        )
    else:
        source = materialize_file_ref(project_root, asset.get("source"), f"{asset_id}.source")
        if Path(source["path"]).suffix.lower() != ".pptx":
            raise ValueError(f"{asset_id}: flowchart source must be an editable .pptx")
        normalized["source"] = source
        if asset.get("script") not in (None, ""):
            normalized["script"] = materialize_file_ref(
                project_root, asset.get("script"), f"{asset_id}.script"
            )
        normalized["human_approved"] = True
    return normalized


def build_figure_manifest(
    *, project_root: Path, records: dict[str, Any], paper_ready_manifest: Path, standard_path: Path
) -> dict[str, Any]:
    root = project_root.resolve()
    standard = standard_metadata(standard_path)
    verify_paper_ready_manifest(paper_ready_manifest, root, standard)
    paper_ready_sha256 = sha256_file(paper_ready_manifest)
    if records.get("paper_ready_manifest_sha256") != paper_ready_sha256:
        raise ValueError("records point to a stale or missing paper_ready_manifest hash")
    resample_requests = records.get("resample_requests", [])
    if not isinstance(resample_requests, list):
        raise ValueError("records.resample_requests must be a list")
    if resample_requests:
        raise ValueError("unresolved RESAMPLE request blocks FIGURES_READY")
    if records.get("standard_version") != standard["version"]:
        raise ValueError("records standard_version does not match the shared standard")
    raw_assets = records.get("assets")
    if not isinstance(raw_assets, list) or not raw_assets:
        raise ValueError("records.assets must be a non-empty list")
    assets = [
        normalize_asset(
            root,
            asset,
            standard_version=standard["version"],
            paper_ready_sha256=paper_ready_sha256,
        )
        for asset in raw_assets
    ]
    asset_ids = [asset["asset_id"] for asset in assets]
    if len(asset_ids) != len(set(asset_ids)):
        raise ValueError("duplicate asset_id in records")
    return {
        "schema_version": 2,
        "status": "FIGURES_READY",
        "standard": standard,
        "paper_ready_manifest_sha256": paper_ready_sha256,
        "assets": assets,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--records", type=Path, required=True)
    parser.add_argument("--paper-ready-manifest", type=Path, required=True)
    parser.add_argument(
        "--standard",
        type=Path,
        default=Path(__file__).resolve().parents[2] / "_shared" / "cumcm" / "C题规范.md",
    )
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    try:
        manifest = build_figure_manifest(
            project_root=args.project_root,
            records=load_json(args.records),
            paper_ready_manifest=args.paper_ready_manifest,
            standard_path=args.standard,
        )
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        parser.error(str(exc))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
