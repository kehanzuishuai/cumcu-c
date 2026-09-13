#!/usr/bin/env python3
"""Validate a modeling interpretation report and its structured freeze contracts."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Optional


CONCEPTS = {
    "positioning": ("题目定位", "结论先行", "一句话实质"),
    "task_chain": ("任务链", "总任务链"),
    "subproblems": ("小问规格", "逐问拆解", "问题 1", "问题1"),
    "attachments": ("附件审计", "附件和模板审计", "附件数据审计", "数据与附件审计", "数据审计", "材料清点"),
    "constraints": ("约束", "歧义", "假设台账"),
    "models": ("主模型", "模型蓝图", "模型与接口", "模型与跨问接口", "建模路线"),
    "validation": ("验证", "敏感性", "验收"),
    "delivery": ("交付", "结果接口", "论文接口"),
}

EVIDENCE_TAGS = (
    "[题面事实]",
    "[附件事实]",
    "[官方勘误]",
    "[必要推论]",
    "[主解释]",
    "[可检验假设]",
    "[备选解释]",
    "[待计算]",
    "[原题明确]",
    "[必然推论]",
    "[建议口径]",
    "[待验证假设]",
)

PLACEHOLDER_PATTERNS = (
    r"\{\{[^{}]+\}\}",
    r"【填写[^】]*】",
    r"\[TODO(?::[^\]]*)?\]",
)

EVIDENCE_RANK = {
    "alternative_interpretation": 1,
    "testable_assumption": 2,
    "main_interpretation": 3,
    "necessary_deduction": 4,
    "attachment_explicit": 5,
    "problem_explicit": 5,
    "official_correction": 6,
}
HIGH_EVIDENCE = {
    "official_correction",
    "problem_explicit",
    "attachment_explicit",
    "necessary_deduction",
}
OFFICIAL_EVIDENCE = {"official_correction", "problem_explicit", "attachment_explicit"}
AMBIGUITY_SCOPES = {
    "entity_definition",
    "data_granularity",
    "hard_constraint",
    "objective_definition",
    "required_output",
    "delivery_requirement",
}
GRANULARITY_ROLES = {
    "observation",
    "parameter",
    "state",
    "decision",
    "constraint",
    "output",
    "interface",
}
INTERPRETATION_DECISION_CATEGORIES = {
    "objective_definition",
    "evaluation_basis",
    "aggregation_rule",
    "cross_question_interface",
    "candidate_set",
    "output_definition",
}
INTERPRETATION_DECISION_STATUSES = {
    "VERIFIED",
    "RESOLVED_BY_EVIDENCE",
    "APPROVED_BY_USER",
    "MODEL_DESIGN",
}
FREEZE_TARGET_CONTRACTS = {
    "granularity_contract",
    "hard_constraints",
    "interpretation_decisions",
    "model_assumptions",
    "model_plan",
}
FREEZEABLE_STATUSES = {"VERIFIED", "RESOLVED_BY_EVIDENCE", "APPROVED_BY_USER"}
PENDING_AMBIGUITY_STATUSES = {"UNRESOLVED", "BLOCKING"}
RESOLVED_AMBIGUITY_STATUSES = {"VERIFIED", "RESOLVED_BY_EVIDENCE", "APPROVED_BY_USER"}
REQUIRED_CONTRACTS = {
    "ambiguities": "ambiguity_decisions",
    "granularity_contract": "granularity_contract",
    "hard_constraints": "hard_constraints",
    "interpretation_decisions": "interpretation_decisions",
    "model_assumptions": "model_assumptions",
    "model_plan": "model_plan",
}


def normalize(text: str) -> str:
    return re.sub(r"\s+", "", text).lower()


STALE_LITERAL_MARKERS = (
    "INTERPRETATION_PENDING",
    "DRAFT",
)
STALE_PENDING_MARKERS = (
    "BLOCKING",
    "UNRESOLVED",
    "待确认",
    "待决定",
    "待实现确认",
    "草稿",
    "确认后升级",
    "待冻结",
)
STALE_OPTION_PATTERNS = (
    re.compile(
        r"(?:方案\s*)?A\s*(?:/|／|、|或|与)\s*(?:方案\s*)?B"
        r".{0,16}(?:待选|待确认|待决定|未定)",
        flags=re.IGNORECASE,
    ),
    re.compile(
        r"(?:A|甲)\s*方案\s*(?:/|／|、|或|与|和)\s*(?:B|乙)\s*方案"
        r".{0,16}(?:待选|待确认|待决定|未定)",
        flags=re.IGNORECASE,
    ),
)
STALE_RESOLVED_OPTION_PATTERNS = (
    re.compile(
        r"(?:方案\s*)?A\s*(?:/|／|、|或|与)\s*(?:方案\s*)?B"
        r".{0,20}(?:题意|口径|解释).{0,16}(?:保留|并列|候选)",
        flags=re.IGNORECASE,
    ),
    re.compile(
        r"(?:保留|并列|继续采用).{0,16}(?:方案\s*)?A"
        r".{0,12}(?:方案\s*)?B.{0,16}(?:题意|口径|解释)",
        flags=re.IGNORECASE,
    ),
)


def marker_is_explicitly_cleared(line: str, marker: str) -> bool:
    """Allow explicit zero/cleared summaries without preserving a pending state."""
    escaped = re.escape(marker)
    cleared_patterns = (
        rf"{escaped}(?:项|事项|问题)?\s*(?:=|:|：|为|数量为|数量)?\s*0\b",
        rf"(?:无|没有|不存在|已清零|已消除|均已解决|全部解决).{{0,12}}{escaped}",
        rf"{escaped}.{{0,12}}(?:为零|已清零|已消除|已解决|不存在)",
        rf"(?:无|没有|不存在).{{0,8}}{escaped}(?:项|事项|问题)?",
    )
    return any(re.search(pattern, line, flags=re.IGNORECASE) for pattern in cleared_patterns)


def scan_stale_decision_state(
    path: Path, *, has_resolved_ambiguities: bool
) -> list[dict[str, Any]]:
    """Locate stale pending-language in a final natural-language document."""
    findings: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        return [{"file": str(path), "line": 0, "marker": "UNREADABLE", "text": str(exc)}]

    for line_number, line in enumerate(lines, start=1):
        for marker in STALE_LITERAL_MARKERS:
            if re.search(re.escape(marker), line, flags=re.IGNORECASE):
                findings.append(
                    {"file": str(path), "line": line_number, "marker": marker, "text": line.strip()}
                )
        for marker in STALE_PENDING_MARKERS:
            if re.search(re.escape(marker), line, flags=re.IGNORECASE) and not marker_is_explicitly_cleared(
                line, marker
            ):
                findings.append(
                    {"file": str(path), "line": line_number, "marker": marker, "text": line.strip()}
                )
        for pattern in STALE_OPTION_PATTERNS:
            match = pattern.search(line)
            if match:
                findings.append(
                    {
                        "file": str(path),
                        "line": line_number,
                        "marker": "A/B_PENDING_SELECTION",
                        "text": line.strip(),
                    }
                )
                break
        if has_resolved_ambiguities:
            for pattern in STALE_RESOLVED_OPTION_PATTERNS:
                if pattern.search(line):
                    findings.append(
                        {
                            "file": str(path),
                            "line": line_number,
                            "marker": "RESOLVED_AMBIGUITY_OPTIONS",
                            "text": line.strip(),
                        }
                    )
                    break
    return findings


def validate_final_document_state(
    report: Path,
    model_plan: Optional[Path],
    *,
    contract_documents: tuple[Optional[Path], ...],
    has_resolved_ambiguities: bool,
) -> dict[str, Any]:
    """Ensure every final Markdown handoff document has current frozen state."""
    handoff_directory = report.parent.resolve()
    documents = {report.resolve()}
    for document in contract_documents:
        if document is not None and document.is_file() and document.suffix.lower() == ".md":
            documents.add(document.resolve())
    for candidate in handoff_directory.glob("*_final.md"):
        if candidate.is_file():
            documents.add(candidate.resolve())

    stale = []
    if not report.stem.lower().endswith("_final"):
        stale.append(
            {
                "file": str(report),
                "line": 0,
                "marker": "FINAL_NAME_REQUIRED",
                "text": "final report must be regenerated as *_final.md",
            }
        )
    if (
        model_plan is not None
        and model_plan.is_file()
        and not model_plan.stem.lower().endswith("_final")
    ):
        stale.append(
            {
                "file": str(model_plan),
                "line": 0,
                "marker": "FINAL_NAME_REQUIRED",
                "text": "final model plan must be regenerated as *_final.md",
            }
        )
    for draft in sorted(handoff_directory.glob("*_draft.md")):
        if draft.is_file():
            stale.append(
                {
                    "file": str(draft),
                    "line": 0,
                    "marker": "UNARCHIVED_DRAFT",
                    "text": "move the draft to _archive/ before PAPER_READY",
                }
            )
    for child in sorted(handoff_directory.rglob("*")):
        if not child.is_dir():
            continue
        relative_parts = tuple(part.lower() for part in child.relative_to(handoff_directory).parts)
        if relative_parts and relative_parts[0] == "_archive":
            continue
        if re.search(r"backup|archive|备份|归档", child.name, flags=re.IGNORECASE):
            stale.append(
                {
                    "file": str(child),
                    "line": 0,
                    "marker": "BACKUP_DIRECTORY_IN_HANDOFF",
                    "text": "move backup/archive directories outside the formal handoff directory",
                }
            )
    for document in sorted(documents):
        stale.extend(
            scan_stale_decision_state(
                document, has_resolved_ambiguities=has_resolved_ambiguities
            )
        )
    return {
        "documents": [str(document) for document in sorted(documents)],
        "stale": stale,
    }


def contains_any(text: str, terms: tuple[str, ...]) -> bool:
    compact = normalize(text)
    return any(normalize(term) in compact for term in terms)


def markdown_headings(text: str) -> list[tuple[int, int, str]]:
    headings = []
    for match in re.finditer(r"(?m)^(#{1,6})\s+(.+?)\s*$", text):
        headings.append((match.start(), len(match.group(1)), match.group(2)))
    return headings


def heading_contains_any(headings: list[tuple[int, int, str]], terms: tuple[str, ...]) -> bool:
    return any(contains_any(title, terms) for _, _, title in headings)


def subproblem_sections(text: str, headings: list[tuple[int, int, str]]) -> dict[int, str]:
    sections = {}
    for index, (start, level, title) in enumerate(headings):
        match = re.match(r"^(?:问题|q)\s*([1-9]\d*)", title.strip(), flags=re.IGNORECASE)
        if not match:
            continue
        number = int(match.group(1))
        end = len(text)
        for next_start, next_level, _ in headings[index + 1 :]:
            if next_level <= level:
                end = next_start
                break
        sections[number] = text[start:end]
    return sections


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def standard_metadata(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    match = re.search(r'^standard_version:\s*["\']?([^"\'\r\n]+)', text, flags=re.MULTILINE)
    if not match:
        raise ValueError(f"standard_version is missing from {path}")
    return {"version": match.group(1).strip(), "sha256": sha256_file(path)}


def project_relative(path: Path, project_root: Path) -> str:
    try:
        relative = path.resolve().relative_to(project_root.resolve())
    except ValueError as exc:
        raise ValueError(f"handoff file is outside project root: {path}") from exc
    return relative.as_posix()


def build_paper_ready_manifest(
    result: dict[str, Any],
    *,
    project_root: Path,
    standard: Path,
    report: Path,
    model_plan: Optional[Path],
    ambiguities: Optional[Path],
    granularity_contract: Optional[Path],
    hard_constraints: Optional[Path],
    interpretation_decisions: Optional[Path],
    model_assumptions: Optional[Path],
) -> dict[str, Any]:
    """Build provenance only after the unchanged final validation gate passes."""
    if result.get("interpretation_status") != "PAPER_READY" or not result.get("pass"):
        raise ValueError("paper_ready_manifest requires a passing final PAPER_READY result")

    required_files = (
        ("interpretation_final", report),
        ("model_plan_final", model_plan),
        ("ambiguity_decisions", ambiguities),
        ("granularity_contract", granularity_contract),
        ("hard_constraints", hard_constraints),
        ("interpretation_decisions", interpretation_decisions),
        ("model_assumptions", model_assumptions),
    )
    files = []
    for role, path in required_files:
        if path is None or not path.is_file():
            raise ValueError(f"paper_ready_manifest is missing required file: {role}")
        files.append(
            {
                "role": role,
                "path": project_relative(path, project_root),
                "sha256": sha256_file(path),
            }
        )

    return {
        "schema_version": 1,
        "status": "PAPER_READY",
        "standard": standard_metadata(standard),
        "validator": {
            "name": Path(__file__).name,
            "result_sha256": hashlib.sha256(canonical(result).encode("utf-8")).hexdigest(),
        },
        "problem_count": len(result.get("detected_subproblems", [])),
        "files": files,
    }


def get_nested_field(item: dict[str, Any], field: str) -> tuple[bool, Any]:
    """Return a dotted-path field without interpreting natural language."""
    current: Any = item
    for part in field.split("."):
        if not isinstance(current, dict) or part not in current:
            return False, None
        current = current[part]
    return True, current


def structure_findings(errors: list[str], warnings: list[str]) -> list[dict[str, str]]:
    """Expose severity and freeze-gate semantics independently."""
    findings = []
    pattern = re.compile(r"^(P[0-3])(?:\s+(BLOCKING|NON_BLOCKING))?\s+([A-Z0-9_]+)\b\s*(.*)$")
    for gate, messages in (("BLOCKING", errors), ("NON_BLOCKING", warnings)):
        for message in messages:
            match = pattern.match(message)
            if match:
                severity, declared_gate, code, detail = match.groups()
                effective_gate = declared_gate or gate
            else:
                severity = "P1" if gate == "BLOCKING" else "P3"
                effective_gate = gate
                code = "STRUCTURAL_INCOMPLETE" if gate == "BLOCKING" else "ADVISORY"
                detail = message
            findings.append(
                {
                    "severity": severity,
                    "gate": effective_gate,
                    "code": code,
                    "message": detail or message,
                }
            )
    return findings


def extract_contract(path: Path, expected_type: str) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    blocks = re.findall(r"```contract-json\s*(\{.*?\})\s*```", text, flags=re.DOTALL)
    parsed = []
    parse_errors = []
    for block in blocks:
        try:
            value = json.loads(block)
        except json.JSONDecodeError as exc:
            parse_errors.append(f"line {exc.lineno}, column {exc.colno}: {exc.msg}")
            continue
        if not isinstance(value, dict):
            parse_errors.append("contract-json root must be an object")
            continue
        if value.get("contract_type") == expected_type:
            parsed.append(value)
    if parse_errors:
        raise ValueError("invalid contract-json: " + "; ".join(parse_errors))
    if not parsed:
        raise ValueError(f"missing contract-json block with contract_type={expected_type}")
    if len(parsed) > 1:
        raise ValueError(f"multiple contract-json blocks with contract_type={expected_type}")
    return parsed[0]


def index_items(contract: dict[str, Any], label: str, errors: list[str]) -> dict[str, dict[str, Any]]:
    raw_items = contract.get("items")
    if not isinstance(raw_items, list):
        errors.append(f"P0 CONTRACT_SCHEMA_ERROR {label}: items must be a list")
        return {}
    indexed: dict[str, dict[str, Any]] = {}
    for position, item in enumerate(raw_items, start=1):
        if not isinstance(item, dict):
            errors.append(f"P0 CONTRACT_SCHEMA_ERROR {label}: item {position} must be an object")
            continue
        item_id = item.get("id")
        if not isinstance(item_id, str) or not item_id.strip():
            errors.append(f"P0 CONTRACT_SCHEMA_ERROR {label}: item {position} has no stable id")
            continue
        if item_id in indexed:
            errors.append(f"P0 CONTRACT_SCHEMA_ERROR {label}: duplicate id {item_id}")
            continue
        indexed[item_id] = item
    return indexed


def validate_contract_header(contract: dict[str, Any], label: str, errors: list[str]) -> None:
    if contract.get("schema_version") != 1:
        errors.append(
            f"P0 CONTRACT_SCHEMA_ERROR {label}: schema_version must be the integer 1"
        )


def find_contract_item(
    contracts: dict[str, dict[str, Any]], contract_type: str, item_id: str
) -> Optional[dict[str, Any]]:
    contract = next(
        (value for value in contracts.values() if value.get("contract_type") == contract_type),
        None,
    )
    if not contract or not isinstance(contract.get("items"), list):
        return None
    for item in contract["items"]:
        if isinstance(item, dict) and item.get("id") == item_id:
            return item
    return None


def validate_ambiguities(
    contract: dict[str, Any],
    contracts: dict[str, dict[str, Any]],
    stage: str,
    errors: list[str],
    warnings: list[str],
) -> dict[str, Any]:
    items = index_items(contract, "ambiguity_decisions", errors)
    blocking = []
    unresolved = []
    resolved = []
    evidence_overrides = []
    decision_not_propagated = []
    official_source_conflicts = []
    for item_id, item in items.items():
        if item.get("kind") != "interpretation_ambiguity":
            errors.append(
                f"P0 CONTRACT_SCHEMA_ERROR ambiguity {item_id}: "
                "kind must be interpretation_ambiguity; model assumptions belong in model_assumptions"
            )
        status = item.get("status")
        if status == "MODEL_ASSUMPTION":
            errors.append(
                f"P0 CONTRACT_SCHEMA_ERROR ambiguity {item_id}: "
                "MODEL_ASSUMPTION is not an ambiguity status"
            )
            continue
        if status not in FREEZEABLE_STATUSES | PENDING_AMBIGUITY_STATUSES:
            errors.append(f"P0 CONTRACT_SCHEMA_ERROR ambiguity {item_id}: unknown status {status!r}")
            continue
        if status == "VERIFIED":
            errors.append(
                f"P0 CONTRACT_SCHEMA_ERROR ambiguity {item_id}: VERIFIED is reserved for facts "
                "that never formed a genuine ambiguity; use RESOLVED_BY_EVIDENCE for a reviewed candidate ambiguity"
            )

        raw_impact = item.get("impact")
        if not isinstance(raw_impact, list) or not raw_impact or not all(
            isinstance(value, str) and value.strip() for value in raw_impact
        ):
            errors.append(f"P0 CONTRACT_SCHEMA_ERROR ambiguity {item_id}: impact must be a non-empty list")
            impact: set[str] = set()
        else:
            impact = set(raw_impact)
        ambiguity_scope = item.get("ambiguity_scope")
        if ambiguity_scope not in AMBIGUITY_SCOPES:
            errors.append(
                f"P0 MISCLASSIFIED_MODELING_CHOICE ambiguity {item_id}: "
                "ambiguity_scope must identify a change to the problem meaning "
                f"({', '.join(sorted(AMBIGUITY_SCOPES))}); mathematical implementation "
                "choices belong in interpretation_decisions or model_assumptions"
            )
        if status == "BLOCKING":
            blocking.append(item_id)
        if status in PENDING_AMBIGUITY_STATUSES:
            unresolved.append(item_id)
        if status in RESOLVED_AMBIGUITY_STATUSES:
            resolved.append(item_id)

        evidence = item.get("evidence")
        ranked: list[tuple[int, Any, str, str]] = []
        if not isinstance(evidence, list) or not evidence:
            errors.append(f"P0 CONTRACT_SCHEMA_ERROR ambiguity {item_id}: evidence must be a non-empty list")
            evidence = []
        for position, evidence_item in enumerate(evidence, start=1):
            if not isinstance(evidence_item, dict):
                errors.append(
                    f"P0 CONTRACT_SCHEMA_ERROR ambiguity {item_id}: evidence {position} must be an object"
                )
                continue
            level = evidence_item.get("level")
            if level not in EVIDENCE_RANK:
                errors.append(
                    f"P0 CONTRACT_SCHEMA_ERROR ambiguity {item_id}: unknown evidence level {level!r}"
                )
                continue
            source = evidence_item.get("source")
            if not isinstance(source, str) or not source.strip():
                errors.append(
                    f"P0 CONTRACT_SCHEMA_ERROR ambiguity {item_id}: evidence {position} has no source"
                )
            if "value" not in evidence_item or evidence_item.get("value") is None:
                errors.append(
                    f"P0 CONTRACT_SCHEMA_ERROR ambiguity {item_id}: evidence {position} has no normalized value"
                )
                continue
            value = evidence_item["value"]
            if "data_granularity" in impact and (
                not isinstance(value, list)
                or not value
                or not all(isinstance(dimension, str) and dimension.strip() for dimension in value)
            ):
                errors.append(
                    f"P0 CONTRACT_SCHEMA_ERROR ambiguity {item_id}: "
                    "granularity evidence.value must be a non-empty dimension list"
                )
            ranked.append((EVIDENCE_RANK[level], value, level, source or ""))

        high_evidence_unique = False
        highest_values: set[str] = set()
        if ranked:
            highest_rank = max(rank for rank, _, _, _ in ranked)
            highest_values = {
                canonical(value) for rank, value, _, _ in ranked if rank == highest_rank
            }
            top_official = [
                row
                for row in ranked
                if row[2] in OFFICIAL_EVIDENCE
                and row[0] == max(
                    (candidate[0] for candidate in ranked if candidate[2] in OFFICIAL_EVIDENCE),
                    default=-1,
                )
            ]
            official_values = {canonical(value) for _, value, _, _ in top_official}
            official_origins = {(level, source) for _, _, level, source in top_official}
            official_source_conflict = (
                len(official_origins) > 1 and len(official_values) > 1
            )
            if official_source_conflict:
                official_source_conflicts.append(item_id)
                errors.append(
                    f"P0 OFFICIAL_SOURCE_CONFLICT ambiguity {item_id}: "
                    "same-rank official sources have incompatible normalized values; "
                    "keep status=BLOCKING until an official correction or clarification resolves the conflict"
                )
            high_evidence_unique = (
                highest_rank >= EVIDENCE_RANK["necessary_deduction"]
                and len(highest_values) == 1
                and not official_source_conflict
            )
            for field in ("recommended", "decision"):
                value = item.get(field)
                if value is None:
                    continue
                if (
                    highest_rank >= EVIDENCE_RANK["necessary_deduction"]
                    and canonical(value) not in highest_values
                ):
                    evidence_overrides.append(item_id)
                    errors.append(
                        f"P0 EVIDENCE_OVERRIDE ambiguity {item_id}: {field} conflicts with highest-level evidence"
                    )

        if status in {"VERIFIED", "RESOLVED_BY_EVIDENCE"} and not high_evidence_unique:
            errors.append(
                f"P0 FREEZE_GATE_BLOCKED ambiguity {item_id}: "
                f"status={status} requires unique high-level evidence"
            )
        if status in PENDING_AMBIGUITY_STATUSES and high_evidence_unique:
            message = (
                f"ambiguity {item_id}: high-level evidence uniquely determines the decision; "
                "use RESOLVED_BY_EVIDENCE"
            )
            if stage == "final":
                errors.append("P0 FREEZE_GATE_BLOCKED " + message)
            else:
                warnings.append(message)
        if status == "APPROVED_BY_USER" and high_evidence_unique:
            warnings.append(
                f"ambiguity {item_id}: user approval is redundant because high-level evidence is unique"
            )

        if status in FREEZEABLE_STATUSES and item.get("decision") is None:
            errors.append(f"P0 FREEZE_GATE_BLOCKED ambiguity {item_id}: frozen status without decision")
        if status == "APPROVED_BY_USER" and not item.get("approved_by"):
            errors.append(f"P0 FREEZE_GATE_BLOCKED ambiguity {item_id}: user approval not recorded")

        if status in {"RESOLVED_BY_EVIDENCE", "APPROVED_BY_USER"}:
            targets = item.get("freeze_targets")
            if not isinstance(targets, list) or not targets:
                decision_not_propagated.append(item_id)
                errors.append(
                    f"P0 DECISION_NOT_PROPAGATED ambiguity {item_id}: "
                    "resolved decisions require a non-empty freeze_targets list"
                )
                targets = []
            for position, target in enumerate(targets, start=1):
                if not isinstance(target, dict):
                    decision_not_propagated.append(item_id)
                    errors.append(
                        f"P0 DECISION_NOT_PROPAGATED ambiguity {item_id}: "
                        f"freeze target {position} must be an object"
                    )
                    continue
                contract_type = target.get("contract")
                target_id = target.get("id")
                field = target.get("field")
                if not all(
                    isinstance(value, str) and value.strip()
                    for value in (contract_type, target_id, field)
                ):
                    decision_not_propagated.append(item_id)
                    errors.append(
                        f"P0 DECISION_NOT_PROPAGATED ambiguity {item_id}: "
                        f"freeze target {position} requires contract, id, and field"
                    )
                    continue
                if contract_type not in FREEZE_TARGET_CONTRACTS:
                    decision_not_propagated.append(item_id)
                    errors.append(
                        f"P0 DECISION_NOT_PROPAGATED ambiguity {item_id}: "
                        f"freeze target {position} cannot use contract {contract_type!r}"
                    )
                    continue
                target_item = find_contract_item(contracts, contract_type, target_id)
                found, target_value = (
                    get_nested_field(target_item, field) if target_item is not None else (False, None)
                )
                if not found or canonical(item.get("decision")) != canonical(target_value):
                    decision_not_propagated.append(item_id)
                    errors.append(
                        f"P0 DECISION_NOT_PROPAGATED ambiguity {item_id}: "
                        f"decision != {contract_type}/{target_id}/{field}"
                    )

    if stage == "final":
        if blocking:
            errors.append("P0 FREEZE_GATE_BLOCKED blocking ambiguities: " + ", ".join(blocking))
        nonblocking_label_pending = sorted(set(unresolved) - set(blocking))
        if nonblocking_label_pending:
            errors.append(
                "P0 FREEZE_GATE_BLOCKED unresolved ambiguities: "
                + ", ".join(nonblocking_label_pending)
            )
    return {
        "count": len(items),
        "blocking": blocking,
        "unresolved": unresolved,
        "resolved": resolved,
        "evidence_overrides": sorted(set(evidence_overrides)),
        "decision_not_propagated": sorted(set(decision_not_propagated)),
        "official_source_conflicts": sorted(set(official_source_conflicts)),
    }


def validate_model_assumptions(
    contract: dict[str, Any], errors: list[str]
) -> dict[str, Any]:
    items = index_items(contract, "model_assumptions", errors)
    for item_id, item in items.items():
        if item.get("status") != "MODEL_ASSUMPTION":
            errors.append(
                f"P0 CONTRACT_SCHEMA_ERROR model assumption {item_id}: "
                "status must be MODEL_ASSUMPTION"
            )
        statement = item.get("statement") or item.get("parameter")
        if not isinstance(statement, str) or not statement.strip():
            errors.append(
                f"P0 CONTRACT_SCHEMA_ERROR model assumption {item_id}: "
                "statement or parameter is required"
            )
        source = item.get("source")
        if not isinstance(source, str) or not source.strip():
            errors.append(f"P0 CONTRACT_SCHEMA_ERROR model assumption {item_id}: source is required")

        challenge_paths = []
        alternatives = item.get("alternative_values")
        if alternatives is not None and not isinstance(alternatives, list):
            errors.append(
                f"P0 CONTRACT_SCHEMA_ERROR model assumption {item_id}: "
                "alternative_values must be a list when provided"
            )
        elif isinstance(alternatives, list) and alternatives:
            challenge_paths.append("alternative_values")

        for field in ("sensitivity", "diagnostic", "robustness_test", "failure_condition"):
            value = item.get(field)
            if value is None:
                continue
            if not isinstance(value, str):
                errors.append(
                    f"P0 CONTRACT_SCHEMA_ERROR model assumption {item_id}: "
                    f"{field} must be a string when provided"
                )
            elif value.strip():
                challenge_paths.append(field)

        if not challenge_paths:
            errors.append(
                f"P0 CONTRACT_SCHEMA_ERROR model assumption {item_id}: "
                "at least one validation/challenge path is required "
                "(alternative_values, sensitivity, diagnostic, robustness_test, or failure_condition)"
            )
    return {"count": len(items), "blocking": False}


def validate_interpretation_decisions(
    contract: dict[str, Any], errors: list[str]
) -> dict[str, dict[str, Any]]:
    items = index_items(contract, "interpretation_decisions", errors)
    for item_id, item in items.items():
        category = item.get("category")
        if category not in INTERPRETATION_DECISION_CATEGORIES:
            errors.append(
                f"P0 CONTRACT_SCHEMA_ERROR interpretation decision {item_id}: "
                f"unknown category {category!r}"
            )
        if not isinstance(item.get("statement"), str) or not item.get("statement", "").strip():
            errors.append(
                f"P0 CONTRACT_SCHEMA_ERROR interpretation decision {item_id}: statement is required"
            )
        if "value" not in item or item.get("value") is None:
            errors.append(
                f"P0 CONTRACT_SCHEMA_ERROR interpretation decision {item_id}: "
                "a normalized value is required"
            )
        if not isinstance(item.get("source"), str) or not item.get("source", "").strip():
            errors.append(
                f"P0 CONTRACT_SCHEMA_ERROR interpretation decision {item_id}: source is required"
            )
        status = item.get("status")
        if status not in INTERPRETATION_DECISION_STATUSES:
            errors.append(
                f"P0 CONTRACT_SCHEMA_ERROR interpretation decision {item_id}: "
                f"unknown status {status!r}"
            )
        if status == "APPROVED_BY_USER" and not item.get("approved_by"):
            errors.append(
                f"P0 FREEZE_GATE_BLOCKED interpretation decision {item_id}: "
                "user approval not recorded"
            )
        used_by = item.get("used_by")
        if not isinstance(used_by, list) or not used_by or not all(
            isinstance(value, str) and value.strip() for value in used_by
        ):
            errors.append(
                f"P0 CONTRACT_SCHEMA_ERROR interpretation decision {item_id}: "
                "used_by must be a non-empty list"
            )
        targets = item.get("freeze_targets")
        expected_field = f"implemented_interpretation_decisions.{item_id}"
        if not isinstance(targets, list) or not targets:
            errors.append(
                f"P0 DECISION_NOT_PROPAGATED interpretation decision {item_id}: "
                "freeze_targets must contain its model_plan target"
            )
            continue
        valid_target = any(
            isinstance(target, dict)
            and target.get("contract") == "model_plan"
            and target.get("field") == expected_field
            for target in targets
        )
        if not valid_target:
            errors.append(
                f"P0 DECISION_NOT_PROPAGATED interpretation decision {item_id}: "
                f"expected model_plan/{expected_field}"
            )
    return items


def validate_granularity(
    contract: dict[str, Any], stage: str, errors: list[str], warnings: list[str]
) -> dict[str, dict[str, Any]]:
    items = index_items(contract, "granularity_contract", errors)
    for item_id, item in items.items():
        if not isinstance(item.get("object"), str) or not item.get("object", "").strip():
            errors.append(f"P0 CONTRACT_SCHEMA_ERROR granularity {item_id}: object is required")
        role = item.get("semantic_role")
        if role not in GRANULARITY_ROLES:
            errors.append(
                f"P0 CONTRACT_SCHEMA_ERROR granularity {item_id}: "
                f"semantic_role must be one of {', '.join(sorted(GRANULARITY_ROLES))}"
            )
        dimensions = item.get("dimensions")
        if not isinstance(dimensions, list) or not dimensions or not all(
            isinstance(value, str) and value for value in dimensions
        ):
            errors.append(f"P0 CONTRACT_SCHEMA_ERROR granularity {item_id}: invalid dimensions")
        level = item.get("evidence_level")
        if level not in EVIDENCE_RANK:
            errors.append(f"P0 CONTRACT_SCHEMA_ERROR granularity {item_id}: unknown evidence level {level!r}")
        status = item.get("status")
        if stage == "final" and status not in FREEZEABLE_STATUSES:
            errors.append(f"P0 FREEZE_GATE_BLOCKED granularity {item_id}: status={status!r}")
        mutable = item.get("mutable")
        if mutable not in {"YES", "NO"}:
            errors.append(f"P0 CONTRACT_SCHEMA_ERROR granularity {item_id}: mutable must be YES or NO")
        if level in OFFICIAL_EVIDENCE and mutable != "NO":
            warnings.append(
                f"P1 NON_BLOCKING EXPLICIT_GRANULARITY_MUTABLE granularity {item_id}: "
                "officially explicit granularity should default to NO"
            )
        if not isinstance(item.get("evidence_ref"), str) or not item.get("evidence_ref", "").strip():
            errors.append(f"P0 CONTRACT_SCHEMA_ERROR granularity {item_id}: evidence_ref is required")
    return items


def validate_hard_constraints(
    contract: dict[str, Any], stage: str, errors: list[str], warnings: list[str]
) -> dict[str, dict[str, Any]]:
    items = index_items(contract, "hard_constraints", errors)
    for item_id, item in items.items():
        if not isinstance(item.get("statement"), str) or not item.get("statement", "").strip():
            errors.append(f"P0 CONTRACT_SCHEMA_ERROR hard constraint {item_id}: statement is required")
        if item.get("type") != "HARD":
            errors.append(f"P0 CONTRACT_SCHEMA_ERROR hard constraint {item_id}: type must be HARD")
        level = item.get("evidence_level")
        if level not in HIGH_EVIDENCE:
            errors.append(
                f"P0 HARD_CONSTRAINT_WITHOUT_HIGH_EVIDENCE {item_id}: evidence_level={level!r}"
            )
        status = item.get("status")
        if stage == "final" and status not in FREEZEABLE_STATUSES:
            errors.append(f"P0 FREEZE_GATE_BLOCKED hard constraint {item_id}: status={status!r}")
        if not isinstance(item.get("evidence_ref"), str) or not item.get("evidence_ref", "").strip():
            errors.append(f"P0 CONTRACT_SCHEMA_ERROR hard constraint {item_id}: evidence_ref is required")
    return items


def validate_model_plan(
    contract: dict[str, Any],
    granularity_items: dict[str, dict[str, Any]],
    hard_constraint_items: dict[str, dict[str, Any]],
    interpretation_decision_items: dict[str, dict[str, Any]],
    errors: list[str],
    warnings: list[str],
) -> dict[str, Any]:
    plan_items = index_items(contract, "model_plan", errors)
    conflicts = []
    semantic_conflicts = []
    for item_id, item in plan_items.items():
        if not isinstance(item.get("object"), str) or not item.get("object", "").strip():
            errors.append(f"P0 CONTRACT_SCHEMA_ERROR model plan {item_id}: object is required")
        role = item.get("semantic_role")
        if role not in GRANULARITY_ROLES:
            errors.append(
                f"P0 CONTRACT_SCHEMA_ERROR model plan {item_id}: "
                f"semantic_role must be one of {', '.join(sorted(GRANULARITY_ROLES))}"
            )
        dimensions = item.get("dimensions")
        if not isinstance(dimensions, list) or not dimensions or not all(
            isinstance(value, str) and value.strip() for value in dimensions
        ):
            errors.append(
                f"P0 CONTRACT_SCHEMA_ERROR model plan {item_id}: actual dimensions are required"
            )
        used_by = item.get("used_by")
        if not isinstance(used_by, list) or not used_by or not all(
            isinstance(value, str) and value.strip() for value in used_by
        ):
            errors.append(
                f"P0 CONTRACT_SCHEMA_ERROR model plan {item_id}: used_by must be a non-empty list"
            )
        symbol = item.get("symbol")
        null_reason = item.get("null_reason")
        has_symbol = isinstance(symbol, str) and bool(symbol.strip())
        has_null_reason = isinstance(null_reason, str) and bool(null_reason.strip())
        if has_symbol == has_null_reason:
            errors.append(
                f"P0 CONTRACT_SCHEMA_ERROR model plan {item_id}: "
                "provide exactly one of symbol or a non-empty null_reason"
            )
    for item_id, frozen in granularity_items.items():
        planned = plan_items.get(item_id)
        if planned is None:
            errors.append(f"P0 GRANULARITY_CONFLICT {item_id}: missing from model plan")
            conflicts.append(item_id)
            continue
        frozen_dimensions = frozen.get("dimensions")
        planned_dimensions = planned.get("dimensions")
        frozen_signature = (frozen.get("object"), frozen.get("semantic_role"))
        planned_signature = (planned.get("object"), planned.get("semantic_role"))
        if planned_signature != frozen_signature:
            errors.append(
                "P0 GRANULARITY_SEMANTIC_CONFLICT "
                f"{item_id}: frozen={canonical(frozen_signature)}, "
                f"model={canonical(planned_signature)}"
            )
            semantic_conflicts.append(item_id)
        if planned_dimensions != frozen_dimensions:
            errors.append(
                "P0 GRANULARITY_CONFLICT "
                f"{item_id}: frozen={canonical(frozen_dimensions)}, model={canonical(planned_dimensions)}"
            )
            conflicts.append(item_id)

    extra_plan_items = sorted(set(plan_items) - set(granularity_items))
    if extra_plan_items:
        warnings.append("model plan contains undeclared granularity ids: " + ", ".join(extra_plan_items))

    implemented = contract.get("implemented_hard_constraints")
    if not isinstance(implemented, list):
        errors.append("P0 CONTRACT_SCHEMA_ERROR model_plan: implemented_hard_constraints must be a list")
        implemented = []
    missing_hard = sorted(set(hard_constraint_items) - set(implemented))
    unknown_hard = sorted(set(implemented) - set(hard_constraint_items))
    if missing_hard:
        errors.append("P0 HARD_CONSTRAINT_NOT_IMPLEMENTED: " + ", ".join(missing_hard))
    if unknown_hard:
        errors.append("P0 UNKNOWN_HARD_CONSTRAINT_IN_PLAN: " + ", ".join(unknown_hard))

    implemented_decisions = contract.get("implemented_interpretation_decisions")
    if not isinstance(implemented_decisions, dict):
        errors.append(
            "P0 CONTRACT_SCHEMA_ERROR model_plan: "
            "implemented_interpretation_decisions must be an object"
        )
        implemented_decisions = {}
    missing_decisions = []
    conflicting_decisions = []
    for item_id, decision in interpretation_decision_items.items():
        if item_id not in implemented_decisions:
            errors.append(
                f"P0 DECISION_NOT_PROPAGATED interpretation decision {item_id}: "
                "missing from model_plan"
            )
            missing_decisions.append(item_id)
        elif canonical(implemented_decisions[item_id]) != canonical(decision.get("value")):
            errors.append(
                f"P0 DECISION_NOT_PROPAGATED interpretation decision {item_id}: "
                "contract value differs from model_plan"
            )
            conflicting_decisions.append(item_id)
    unknown_decisions = sorted(
        set(implemented_decisions) - set(interpretation_decision_items)
    )
    if unknown_decisions:
        warnings.append(
            "P1 NON_BLOCKING UNKNOWN_INTERPRETATION_DECISION_IN_PLAN: "
            + ", ".join(unknown_decisions)
        )
    return {
        "granularity_conflicts": sorted(set(conflicts)),
        "granularity_semantic_conflicts": sorted(set(semantic_conflicts)),
        "missing_hard_constraints": missing_hard,
        "unknown_hard_constraints": unknown_hard,
        "missing_interpretation_decisions": sorted(set(missing_decisions)),
        "conflicting_interpretation_decisions": sorted(set(conflicting_decisions)),
        "unknown_interpretation_decisions": unknown_decisions,
    }


def validate_contract_bundle(
    *,
    stage: str,
    ambiguities: Optional[Path],
    granularity_contract: Optional[Path],
    hard_constraints: Optional[Path],
    interpretation_decisions: Optional[Path],
    model_plan: Optional[Path],
    model_assumptions: Optional[Path] = None,
) -> dict[str, Any]:
    paths = {
        "ambiguities": ambiguities,
        "granularity_contract": granularity_contract,
        "hard_constraints": hard_constraints,
        "interpretation_decisions": interpretation_decisions,
        "model_plan": model_plan,
        "model_assumptions": model_assumptions,
    }
    errors: list[str] = []
    warnings: list[str] = []
    contracts: dict[str, dict[str, Any]] = {}
    for key, expected_type in REQUIRED_CONTRACTS.items():
        path = paths[key]
        if path is None:
            if stage == "final":
                errors.append(f"P0 FREEZE_GATE_BLOCKED missing contract: {key}")
            continue
        if not path.is_file():
            errors.append(f"P0 FREEZE_GATE_BLOCKED contract is not a file: {path}")
            continue
        try:
            contracts[key] = extract_contract(path, expected_type)
            validate_contract_header(contracts[key], key, errors)
        except (OSError, UnicodeError, ValueError) as exc:
            errors.append(f"P0 CONTRACT_SCHEMA_ERROR {key}: {exc}")

    ambiguity_result: dict[str, Any] = {}
    granularity_items: dict[str, dict[str, Any]] = {}
    hard_items: dict[str, dict[str, Any]] = {}
    interpretation_decision_items: dict[str, dict[str, Any]] = {}
    plan_result: dict[str, Any] = {}
    assumption_result: dict[str, Any] = {"count": 0, "blocking": False}
    if "ambiguities" in contracts:
        ambiguity_result = validate_ambiguities(
            contracts["ambiguities"], contracts, stage, errors, warnings
        )
    if "granularity_contract" in contracts:
        granularity_items = validate_granularity(
            contracts["granularity_contract"], stage, errors, warnings
        )
    if "hard_constraints" in contracts:
        hard_items = validate_hard_constraints(contracts["hard_constraints"], stage, errors, warnings)
    if "interpretation_decisions" in contracts:
        interpretation_decision_items = validate_interpretation_decisions(
            contracts["interpretation_decisions"], errors
        )
    if "model_plan" in contracts:
        plan_result = validate_model_plan(
            contracts["model_plan"],
            granularity_items,
            hard_items,
            interpretation_decision_items,
            errors,
            warnings,
        )
    if "model_assumptions" in contracts:
        assumption_result = validate_model_assumptions(contracts["model_assumptions"], errors)

    findings = structure_findings(errors, warnings)
    blocking_count = sum(finding["gate"] == "BLOCKING" for finding in findings)
    return {
        "pass": blocking_count == 0,
        "stage": stage,
        "loaded_contracts": sorted(contracts),
        "ambiguities": ambiguity_result,
        "granularity_item_count": len(granularity_items),
        "hard_constraint_count": len(hard_items),
        "interpretation_decision_count": len(interpretation_decision_items),
        "model_plan": plan_result,
        "model_assumptions": assumption_result,
        "errors": errors,
        "warnings": warnings,
        "findings": findings,
        "gate_counts": {
            "BLOCKING": blocking_count,
            "NON_BLOCKING": len(findings) - blocking_count,
        },
    }


def inspect(
    path: Path,
    expected_subproblems: Optional[int],
    *,
    stage: str = "draft",
    ambiguities: Optional[Path] = None,
    granularity_contract: Optional[Path] = None,
    hard_constraints: Optional[Path] = None,
    interpretation_decisions: Optional[Path] = None,
    model_plan: Optional[Path] = None,
    model_assumptions: Optional[Path] = None,
) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    headings = markdown_headings(text)
    concept_results = {name: heading_contains_any(headings, terms) for name, terms in CONCEPTS.items()}
    sections = subproblem_sections(text, headings)
    subproblems = sorted(sections)
    placeholders = []
    for pattern in PLACEHOLDER_PATTERNS:
        placeholders.extend(re.findall(pattern, text, flags=re.IGNORECASE))
    tags = [tag for tag in EVIDENCE_TAGS if tag in text]
    errors = []
    warnings = []
    for name, present in concept_results.items():
        if not present:
            errors.append(f"missing concept: {name}")
    if expected_subproblems is not None:
        missing = [number for number in range(1, expected_subproblems + 1) if number not in subproblems]
        if missing:
            errors.append("missing subproblems: " + ", ".join(map(str, missing)))
    required_subproblem_fields = {
        "input": ("输入", "可用输入"),
        "output": ("输出", "待求"),
        "constraints": ("约束",),
        "validation": ("验证", "验收"),
        "delivery": ("交付", "结果表", "文件名", "模板"),
    }
    incomplete_sections = {}
    for number, section in sections.items():
        missing_fields = [
            name for name, terms in required_subproblem_fields.items() if not contains_any(section, terms)
        ]
        if missing_fields:
            incomplete_sections[str(number)] = missing_fields
            errors.append(f"subproblem {number} missing fields: {', '.join(missing_fields)}")
    if placeholders:
        errors.append(f"unfinished placeholders: {len(placeholders)}")
    if len(tags) < 3:
        warnings.append("fewer than three evidence-label types detected")
    if len(text) < 1500:
        warnings.append("report is unusually short for a full interpretation")
    contract_result = validate_contract_bundle(
        stage=stage,
        ambiguities=ambiguities,
        granularity_contract=granularity_contract,
        hard_constraints=hard_constraints,
        interpretation_decisions=interpretation_decisions,
        model_plan=model_plan,
        model_assumptions=model_assumptions,
    )
    errors.extend(contract_result["errors"])
    warnings.extend(contract_result["warnings"])
    final_document_state = {"documents": [], "stale": []}
    if stage == "final":
        resolved_ambiguities = contract_result.get("ambiguities", {}).get("resolved", [])
        final_document_state = validate_final_document_state(
            path,
            model_plan,
            contract_documents=(
                ambiguities,
                granularity_contract,
                hard_constraints,
                interpretation_decisions,
                model_assumptions,
                model_plan,
            ),
            has_resolved_ambiguities=bool(resolved_ambiguities),
        )
        for item in final_document_state["stale"]:
            location = f"{item['file']}:{item['line']}" if item["line"] else item["file"]
            resolved_note = (
                " resolved ambiguities=" + ",".join(resolved_ambiguities)
                if resolved_ambiguities
                else ""
            )
            errors.append(
                "P0 STALE_DECISION_STATE "
                f"{location} marker={item['marker']} {item['text']}{resolved_note}"
            )
    all_warnings = warnings + [
        "structural and contract preflight only; source-grounded semantic review is still required"
    ]
    findings = structure_findings(errors, all_warnings)
    blocking_count = sum(finding["gate"] == "BLOCKING" for finding in findings)
    return {
        "file": str(path.resolve()),
        "pass": blocking_count == 0,
        "stage": stage,
        "interpretation_status": (
            "PAPER_READY" if stage == "final" and blocking_count == 0 else "INTERPRETATION_PENDING"
        ),
        "concepts": concept_results,
        "detected_subproblems": subproblems,
        "subproblem_field_gaps": incomplete_sections,
        "evidence_tags": tags,
        "placeholder_count": len(placeholders),
        "contract_checks": {
            key: value
            for key, value in contract_result.items()
            if key not in {"errors", "warnings", "findings"}
        },
        "final_document_state": final_document_state,
        "errors": errors,
        "warnings": all_warnings,
        "findings": findings,
        "gate_counts": {
            "BLOCKING": blocking_count,
            "NON_BLOCKING": len(findings) - blocking_count,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path, help="Markdown interpretation report")
    parser.add_argument("--expected-subproblems", type=int)
    parser.add_argument("--stage", choices=("draft", "final"), default="draft")
    parser.add_argument("--ambiguities", type=Path)
    parser.add_argument("--granularity-contract", type=Path)
    parser.add_argument("--hard-constraints", type=Path)
    parser.add_argument("--interpretation-decisions", type=Path)
    parser.add_argument("--model-plan", type=Path)
    parser.add_argument("--model-assumptions", type=Path)
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--manifest-out", type=Path)
    parser.add_argument("--project-root", type=Path)
    parser.add_argument(
        "--standard",
        type=Path,
        default=Path(__file__).resolve().parents[2] / "_shared" / "cumcm" / "C题规范.md",
    )
    args = parser.parse_args()
    if not args.report.is_file():
        parser.error(f"not a file: {args.report}")
    result = inspect(
        args.report,
        args.expected_subproblems,
        stage=args.stage,
        ambiguities=args.ambiguities,
        granularity_contract=args.granularity_contract,
        hard_constraints=args.hard_constraints,
        interpretation_decisions=args.interpretation_decisions,
        model_plan=args.model_plan,
        model_assumptions=args.model_assumptions,
    )
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(rendered + "\n", encoding="utf-8")
    if args.manifest_out:
        if args.project_root is None:
            parser.error("--project-root is required with --manifest-out")
        project_root = args.project_root.resolve()
        try:
            manifest = build_paper_ready_manifest(
                result,
                project_root=project_root,
                standard=args.standard,
                report=args.report,
                model_plan=args.model_plan,
                ambiguities=args.ambiguities,
                granularity_contract=args.granularity_contract,
                hard_constraints=args.hard_constraints,
                interpretation_decisions=args.interpretation_decisions,
                model_assumptions=args.model_assumptions,
            )
        except (OSError, UnicodeError, ValueError) as exc:
            parser.error(str(exc))
        args.manifest_out.parent.mkdir(parents=True, exist_ok=True)
        args.manifest_out.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    print(rendered)
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
