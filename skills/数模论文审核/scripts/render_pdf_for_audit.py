#!/usr/bin/env python3
"""Render a final PDF to page PNGs and contact sheets for human visual audit."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def numeric_suffix(path: Path) -> int:
    match = re.search(r"-(\d+)\.png$", path.name)
    return int(match.group(1)) if match else 0


def render_pages(pdf: Path, destination: Path, dpi: int) -> list[Path]:
    destination.mkdir(parents=True, exist_ok=True)
    prefix = destination / "raw-page"
    if shutil.which("pdftoppm"):
        command = ["pdftoppm", "-png", "-r", str(dpi), str(pdf), str(prefix)]
    elif shutil.which("pdftocairo"):
        command = ["pdftocairo", "-png", "-r", str(dpi), str(pdf), str(prefix)]
    else:
        raise RuntimeError("需要 Poppler 的 pdftoppm 或 pdftocairo 才能渲染 PDF")
    result = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=False)
    if result.returncode != 0:
        raise RuntimeError(result.stdout[-2000:] or f"PDF renderer exit={result.returncode}")
    raw_pages = sorted(destination.glob("raw-page-*.png"), key=numeric_suffix)
    pages: list[Path] = []
    for index, raw in enumerate(raw_pages, 1):
        final = destination / f"page-{index:04d}.png"
        raw.replace(final)
        pages.append(final)
    if not pages:
        raise RuntimeError("PDF 渲染后没有生成页面图片")
    return pages


def page_metrics(path: Path) -> dict[str, Any]:
    from PIL import Image

    with Image.open(path) as source:
        gray = source.convert("L")
        if gray.width > 500:
            height = max(1, round(gray.height * 500 / gray.width))
            gray = gray.resize((500, height))
        width, height = gray.size
        pixels = gray.load()
        row_ratios: list[float] = []
        total_ink = 0
        for y in range(height):
            row_ink = sum(1 for x in range(width) if pixels[x, y] < 245)
            total_ink += row_ink
            row_ratios.append(row_ink / width)
        content_rows = [index for index, ratio in enumerate(row_ratios) if ratio >= 0.002]
        occupied_height = (
            (content_rows[-1] - content_rows[0] + 1) / height if content_rows else 0.0
        )
        top_blank = content_rows[0] / height if content_rows else 1.0
        bottom_blank = (height - 1 - content_rows[-1]) / height if content_rows else 1.0
        largest_blank = 0
        current_blank = 0
        for ratio in row_ratios:
            if ratio < 0.001:
                current_blank += 1
                largest_blank = max(largest_blank, current_blank)
            else:
                current_blank = 0
        ink_ratio = total_ink / (width * height)
    flags: list[str] = []
    if ink_ratio < 0.004:
        flags.append("页面内容极少/疑似空白页")
    if occupied_height < 0.55:
        flags.append("有效内容纵向占比偏低")
    if largest_blank / height > 0.34:
        flags.append("存在大面积连续空白候选")
    return {
        "ink_ratio": round(ink_ratio, 5),
        "occupied_height_ratio": round(occupied_height, 4),
        "top_blank_ratio": round(top_blank, 4),
        "bottom_blank_ratio": round(bottom_blank, 4),
        "largest_blank_band_ratio": round(largest_blank / height, 4),
        "heuristic_flags": flags,
    }


def make_contact_sheet(pages: list[Path], output: Path, columns: int, thumb_width: int) -> None:
    from PIL import Image, ImageDraw, ImageFont

    thumbnails: list[tuple[int, Image.Image]] = []
    for page_number, path in enumerate(pages, 1):
        with Image.open(path) as source:
            image = source.convert("RGB")
            height = max(1, round(image.height * thumb_width / image.width))
            thumbnails.append((page_number, image.resize((thumb_width, height))))
    label_height = 26
    cell_height = max(image.height for _, image in thumbnails) + label_height + 12
    rows = (len(thumbnails) + columns - 1) // columns
    sheet = Image.new("RGB", (columns * (thumb_width + 16) + 16, rows * cell_height + 16), "#E7E9EC")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    for index, (page_number, image) in enumerate(thumbnails):
        row, column = divmod(index, columns)
        x = 16 + column * (thumb_width + 16)
        y = 16 + row * cell_height
        draw.text((x, y), f"Page {page_number}", fill="#111111", font=font)
        image_y = y + label_height
        draw.rectangle((x - 1, image_y - 1, x + image.width, image_y + image.height), outline="#7A7F87")
        sheet.paste(image, (x, image_y))
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output, optimize=True)


def build_review_markdown(pdf: Path, digest: str, pages: list[dict[str, Any]], session: Path) -> str:
    candidates = [page for page in pages if page["metrics"]["heuristic_flags"]]
    lines = [
        "# FINAL PDF VISUAL REVIEW",
        "",
        f"- PDF: `{pdf}`",
        f"- SHA-256: `{digest}`",
        f"- Pages: {len(pages)}",
        "- Boundary: 页面指标只生成候选页，不自动判定视觉 FAIL；必须查看最终 PDF 渲染图。",
        "",
        "## 必查项目",
        "",
        "- [ ] 逐页查看所有 `page-XXXX.png`，不是只看 LaTeX 源码。",
        "- [ ] 检查大面积空白、机械/强制分页、标题孤行和页尾孤行。",
        "- [ ] 检查图题/表题分离、跨页表、续表表头和公式拆分。",
        "- [ ] 检查图表碰撞、图例或 colorbar 遮挡、标签重叠和多面板对齐。",
        "- [ ] 检查摘要占版、字体可读性、页码、最后一页和全文页面节奏。",
        "",
        "## 启发式候选页（仅提示人工确认）",
        "",
        "| 页码 | 候选原因 | 内容纵向占比 | 最大空白带 |",
        "|---:|---|---:|---:|",
    ]
    if candidates:
        for page in candidates:
            metrics = page["metrics"]
            lines.append(
                f"| {page['page']} | {'；'.join(metrics['heuristic_flags'])} | "
                f"{metrics['occupied_height_ratio']:.1%} | {metrics['largest_blank_band_ratio']:.1%} |"
            )
    else:
        lines.append("| — | 未发现明显空白候选；仍须逐页人工检查 | — | — |")
    lines += [
        "",
        "## 输出",
        "",
        f"- 全文总览：`{session / 'contact-sheet-all.png'}`",
        f"- 分组总览：`{session / 'contact-sheets'}`",
        f"- 全页图片：`{session / 'pages'}`",
        "",
    ]
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render final PDF for CUMCM visual audit.")
    parser.add_argument("pdf", help="Final PDF path")
    parser.add_argument("--output-dir", required=True, help="Base output directory")
    parser.add_argument("--dpi", type=int, default=160)
    parser.add_argument("--overview-width", type=int, default=190)
    parser.add_argument("--detail-width", type=int, default=360)
    parser.add_argument("--chunk-size", type=int, default=12)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    pdf = Path(args.pdf).resolve()
    if not pdf.is_file() or pdf.suffix.lower() != ".pdf":
        raise SystemExit(f"not a PDF file: {pdf}")
    if args.dpi < 72 or args.dpi > 300:
        raise SystemExit("--dpi must be between 72 and 300")
    digest = sha256_file(pdf)
    base = Path(args.output_dir).resolve()
    session = base / f"{pdf.stem}-{digest[:10]}"
    pages_dir = session / "pages"
    manifest_path = session / "visual-manifest.json"
    if manifest_path.exists():
        try:
            existing = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            existing = {}
        existing_pages = sorted(pages_dir.glob("page-*.png"))
        if existing.get("pdf_sha256") == digest and len(existing_pages) == existing.get("page_count"):
            print(json.dumps(existing, ensure_ascii=False, indent=2))
            return 0
    session.mkdir(parents=True, exist_ok=True)
    try:
        page_paths = render_pages(pdf, pages_dir, args.dpi)
        page_records = [
            {"page": index, "image": str(path), "metrics": page_metrics(path)}
            for index, path in enumerate(page_paths, 1)
        ]
        make_contact_sheet(page_paths, session / "contact-sheet-all.png", 5, args.overview_width)
        contact_dir = session / "contact-sheets"
        for start in range(0, len(page_paths), args.chunk_size):
            chunk = page_paths[start:start + args.chunk_size]
            first_page = start + 1
            last_page = start + len(chunk)
            make_contact_sheet(chunk, contact_dir / f"pages-{first_page:04d}-{last_page:04d}.png", 3, args.detail_width)
    except (RuntimeError, OSError, ValueError) as exc:
        print(f"render failed: {exc}", file=sys.stderr)
        return 2
    payload = {
        "pdf": str(pdf),
        "pdf_sha256": digest,
        "page_count": len(page_paths),
        "dpi": args.dpi,
        "session_dir": str(session),
        "contact_sheet": str(session / "contact-sheet-all.png"),
        "contact_sheet_dir": str(session / "contact-sheets"),
        "pages_dir": str(pages_dir),
        "candidate_pages": [record["page"] for record in page_records if record["metrics"]["heuristic_flags"]],
        "pages": page_records,
        "notice": "Heuristic candidates are WARN only; visual findings require human inspection of the rendered final PDF.",
    }
    manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (session / "visual-review.md").write_text(
        build_review_markdown(pdf, digest, page_records, session), encoding="utf-8"
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
