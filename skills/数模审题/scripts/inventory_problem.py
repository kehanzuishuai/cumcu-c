#!/usr/bin/env python3
"""Create a lightweight, read-only inventory of a modeling problem folder."""

from __future__ import annotations

import argparse
import csv
import json
import sys
import zipfile
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree as ET


LARGE_FILE = 100 * 1024 * 1024


def human_size(size: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    value = float(size)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024
    return f"{size} B"


def pdf_pages(path: Path) -> str:
    try:
        from pypdf import PdfReader  # type: ignore

        return str(len(PdfReader(str(path)).pages))
    except Exception:
        return "未读取"


def xlsx_sheets(path: Path) -> str:
    try:
        with zipfile.ZipFile(path) as archive:
            root = ET.fromstring(archive.read("xl/workbook.xml"))
        namespace = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
        names = [node.attrib.get("name", "") for node in root.findall(".//m:sheets/m:sheet", namespace)]
        return ", ".join(names) if names else "未发现工作表"
    except Exception:
        return "未读取"


def detect_text_encoding(path: Path) -> str:
    with path.open("rb") as handle:
        sample = handle.read(131072)
    if sample.startswith(b"\xef\xbb\xbf"):
        try:
            sample.decode("utf-8-sig")
            return "utf-8-sig"
        except UnicodeDecodeError:
            pass
    for encoding in ("utf-8", "gb18030", "gbk"):
        try:
            sample.decode(encoding)
            return encoding
        except UnicodeDecodeError:
            continue
    return "unknown"


def csv_preview(path: Path) -> str:
    encoding = detect_text_encoding(path)
    if encoding == "unknown":
        return "编码未知"
    try:
        with path.open("r", encoding=encoding, errors="replace", newline="") as handle:
            sample = handle.read(65536)
        dialect = csv.Sniffer().sniff(sample, delimiters=",\t;|")
        first = next(csv.reader(sample.splitlines(), dialect=dialect), [])
        fields = ", ".join(first[:8])
        if len(first) > 8:
            fields += ", ..."
        return f"编码={encoding}; 表头={fields}"
    except Exception:
        return f"编码={encoding}; 表头未读取"


def json_preview(path: Path) -> str:
    if path.stat().st_size >= LARGE_FILE:
        return "大JSON：需使用增量解析器或抽样审计"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            keys = ", ".join(list(data.keys())[:8])
            page_count = data.get("page_count")
            extra = f"; page_count={page_count}" if page_count is not None else ""
            return f"keys={keys}{extra}"
        if isinstance(data, list):
            return f"list length={len(data)}"
        return type(data).__name__
    except Exception:
        return "未读取"


def file_detail(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return f"PDF页数={pdf_pages(path)}"
    if suffix in {".xlsx", ".xlsm"}:
        return f"工作表={xlsx_sheets(path)}"
    if suffix in {".csv", ".tsv", ".txt"}:
        return csv_preview(path)
    if suffix == ".json":
        return json_preview(path)
    if suffix in {".rar", ".zip", ".7z"}:
        return "压缩包：需解压后审计内部文件"
    if suffix in {".mp4", ".avi", ".mov", ".mkv", ".jpg", ".jpeg", ".png"}:
        return "媒体文件：需核对尺寸、帧率或内容"
    return ""


def safe_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def build_inventory(root: Path) -> str:
    files = sorted((path for path in root.rglob("*") if path.is_file()), key=lambda path: str(path).lower())
    counts = Counter((path.suffix.lower() or "[no extension]") for path in files)
    total = sum(path.stat().st_size for path in files)
    lines = [
        f"# 赛题材料清单：{root.name}",
        "",
        f"- 根目录：`{root.resolve()}`",
        f"- 文件数：{len(files)}",
        f"- 总大小：{human_size(total)}",
        "- 类型统计：" + (", ".join(f"`{suffix}` {count}" for suffix, count in sorted(counts.items())) or "无文件"),
        "",
        "| 相对路径 | 类型 | 大小 | 结构预览 | 风险提示 |",
        "| --- | --- | ---: | --- | --- |",
    ]
    for path in files:
        size = path.stat().st_size
        risk = "大文件，优先分块或抽样审计" if size >= LARGE_FILE else ""
        lines.append(
            "| {rel} | {suffix} | {size} | {detail} | {risk} |".format(
                rel=safe_cell(str(path.relative_to(root))),
                suffix=safe_cell(path.suffix.lower() or "无扩展名"),
                size=human_size(size),
                detail=safe_cell(file_detail(path)),
                risk=safe_cell(risk),
            )
        )
    lines.extend(
        [
            "",
            "## 后续人工核验",
            "",
            "- [ ] 原题 PDF 的图、公式、表头和页码已检查。",
            "- [ ] 每个附件的对象粒度、主键、单位、缺失和用途已确认。",
            "- [ ] 结果模板的文件名、工作表、指定时刻和精度已登记。",
            "- [ ] 压缩包已解压，大文件采用分块或抽样读取且记录方法。",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path, help="Problem folder to inventory")
    parser.add_argument("--out", type=Path, help="Write the Markdown inventory to this path")
    args = parser.parse_args()
    root = args.root.resolve()
    if not root.is_dir():
        parser.error(f"not a directory: {root}")
    report = build_inventory(root)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(report, encoding="utf-8")
    else:
        sys.stdout.write(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
