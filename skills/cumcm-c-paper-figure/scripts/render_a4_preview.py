"""Place a rendered figure on a white A4 page at its final physical width."""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.image as mpimg
import matplotlib.pyplot as plt


A4_WIDTH_MM = 210.0
A4_HEIGHT_MM = 297.0


def render_a4_preview(
    image_path: str | Path,
    output_path: str | Path,
    *,
    width_mm: float = 165.0,
    top_mm: float = 22.0,
    dpi: int = 150,
) -> Path:
    """Render one PNG/JPG figure on A4 without changing its aspect ratio."""

    image_path = Path(image_path)
    output_path = Path(output_path)
    if not image_path.is_file():
        raise FileNotFoundError(image_path)
    if not 0 < width_mm <= A4_WIDTH_MM:
        raise ValueError("width_mm must be within the A4 page width")
    if not 0 <= top_mm < A4_HEIGHT_MM:
        raise ValueError("top_mm must be within the A4 page height")
    if dpi < 72:
        raise ValueError("dpi must be at least 72")

    image = mpimg.imread(image_path)
    if image.ndim < 2 or image.shape[0] <= 0 or image.shape[1] <= 0:
        raise ValueError("input image has invalid dimensions")
    height_mm = width_mm * image.shape[0] / image.shape[1]
    if top_mm + height_mm > A4_HEIGHT_MM:
        raise ValueError("figure does not fit the A4 page at the requested width")

    fig = plt.figure(
        figsize=(A4_WIDTH_MM / 25.4, A4_HEIGHT_MM / 25.4),
        dpi=dpi,
        facecolor="white",
    )
    left = (A4_WIDTH_MM - width_mm) / 2 / A4_WIDTH_MM
    width = width_mm / A4_WIDTH_MM
    height = height_mm / A4_HEIGHT_MM
    bottom = 1 - top_mm / A4_HEIGHT_MM - height
    ax = fig.add_axes([left, bottom, width, height])
    ax.imshow(image)
    ax.set_axis_off()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=dpi, facecolor="white", transparent=False)
    plt.close(fig)
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", help="Rendered PNG/JPG figure")
    parser.add_argument("output", help="A4 preview PNG")
    parser.add_argument("--width-mm", type=float, default=165.0)
    parser.add_argument("--top-mm", type=float, default=22.0)
    parser.add_argument("--dpi", type=int, default=150)
    args = parser.parse_args()
    render_a4_preview(
        args.image,
        args.output,
        width_mm=args.width_mm,
        top_mm=args.top_mm,
        dpi=args.dpi,
    )


if __name__ == "__main__":
    main()
