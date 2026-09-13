import argparse
import math
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageStat


def fit_same_size(reference, candidate):
    if candidate.size == reference.size:
        return candidate
    return candidate.resize(reference.size, Image.Resampling.LANCZOS)


def metrics(reference, candidate):
    diff = ImageChops.difference(reference, candidate)
    stat = ImageStat.Stat(diff)
    mean = sum(stat.mean) / len(stat.mean)
    rms = math.sqrt(sum(v * v for v in stat.rms) / len(stat.rms))
    return mean, rms


def make_side_by_side(reference, candidate, output, left_label, right_label):
    w, h = reference.size
    margin = 40
    header = 56
    canvas = Image.new("RGB", (w * 2 + margin, h + header), "white")
    draw = ImageDraw.Draw(canvas)
    draw.text((10, 18), left_label, fill="black")
    draw.text((w + margin + 10, 18), right_label, fill="black")
    canvas.paste(reference, (0, header))
    canvas.paste(candidate, (w + margin, header))
    canvas.save(output)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference", required=True)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--left-label", default="Original reference")
    parser.add_argument("--right-label", default="Editable PPT export")
    args = parser.parse_args()

    reference = Image.open(args.reference).convert("RGB")
    candidate = Image.open(args.candidate).convert("RGB")
    candidate = fit_same_size(reference, candidate)

    mean, rms = metrics(reference, candidate)
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    make_side_by_side(reference, candidate, output, args.left_label, args.right_label)

    print(f"reference_size={reference.size[0]}x{reference.size[1]}")
    print(f"candidate_size={candidate.size[0]}x{candidate.size[1]}")
    print(f"mean_abs_diff={mean:.3f}")
    print(f"rms_diff={rms:.3f}")
    print(f"comparison={output}")


if __name__ == "__main__":
    main()
