#!/usr/bin/env python3
"""Internal before/after sheets from actual fonts, for every-glyph agent review."""

import argparse
import hashlib
import json
from pathlib import Path

from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw, ImageFont


def render(
    before,
    after,
    out,
    before_label="RAW TRACE",
    after_label="CORRECTED",
    samples=None,
    sizes_ppem=(12, 16, 24, 48),
):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    old = ImageFont.truetype(str(before), 460)
    new = ImageFont.truetype(str(after), 460)
    label = ImageFont.load_default(size=24)
    bounds = []
    for path in (before, after):
        with TTFont(path) as f:
            bounds.append(
                (
                    f["head"].yMin * 460 / f["head"].unitsPerEm,
                    f["head"].yMax * 460 / f["head"].unitsPerEm,
                )
            )
    baseline = round(110 + max(b[1] for b in bounds))
    row_height = round(baseline - min(0, min(b[0] for b in bounds)) + 35)
    cmap = TTFont(after).getBestCmap()
    chars = [chr(cp) for cp in sorted(cmap) if cp != 32]
    records = []
    groups = [chars[i : i + 3] for i in range(0, len(chars), 3)]
    for index, group in enumerate(groups):
        image = Image.new("RGB", (1800, row_height * 2), "#faf9f6")
        d = ImageDraw.Draw(image)
        for row, (font, title) in enumerate(
            [
                (old, before_label + " - INTERNAL REFERENCE"),
                (new, after_label + " - INTERNAL REVIEW"),
            ]
        ):
            y = row * row_height
            d.text((20, y + 10), title, font=label, fill="#555")
            for col, c in enumerate(group):
                x = col * 600
                d.text((x + 30, y + 60), c, font=label, fill="#555")
                d.line(
                    (x + 20, y + baseline, x + 580, y + baseline),
                    fill="#d8d8d0",
                    width=1,
                )
                d.text((x + 25, y + baseline), c, font=font, fill="#111", anchor="ls")
        path = out / f"group-{index + 1:02}.png"
        image.save(path)
        records.append(
            {
                "path": path.name,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "glyphs": group,
            }
        )
    # Actual final-font pixels at each declared size, never fit text to a width.
    if not sizes_ppem or any(
        type(size) is not int or not 6 <= size <= 512 for size in sizes_ppem
    ):
        raise ValueError("sizes_ppem must contain integers from 6 to 512")
    sample_texts = samples or ["TEHY  EFHILTY", "AVATAR  CREATOR  OPTIMIST"]
    lines = []
    for size in sizes_ppem:
        for source, title in [(before, before_label), (after, after_label)]:
            face = ImageFont.truetype(str(source), size)
            for sample in sample_texts:
                bounds = face.getbbox(sample, anchor="ls")
                lines.append((face, title, size, sample, bounds))
    width = max(800, max(b[2] - min(0, b[0]) for _, _, _, _, b in lines) + 50)
    height = sum(max(1, b[3] - b[1]) + 70 for _, _, _, _, b in lines)
    sheet = Image.new("RGB", (width, height), "#faf9f6")
    d = ImageDraw.Draw(sheet)
    y = 0
    for face, title, size, sample, bounds in lines:
        d.text(
            (25, y + 10),
            f"{title} / {size} ppem / scale 1 / unreviewed",
            font=label,
            fill="#555",
        )
        d.text(
            (25 - min(0, bounds[0]), y + 45 - bounds[1]),
            sample,
            font=face,
            fill="#111",
            anchor="ls",
        )
        y += max(1, bounds[3] - bounds[1]) + 70
    path = out / "spacing-and-weight.png"
    sheet.save(path)
    records.append(
        {
            "path": path.name,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "glyphs": chars,
        }
    )
    (out / "index.json").write_text(
        json.dumps(
            {
                "before_sha256": hashlib.sha256(Path(before).read_bytes()).hexdigest(),
                "after_sha256": hashlib.sha256(Path(after).read_bytes()).hexdigest(),
                "layout": {
                    "baseline": baseline,
                    "row_height": row_height,
                    "font_size": 460,
                    "sample_sizes_ppem": list(sizes_ppem),
                    "device_scale": 1,
                    "review_status": "unreviewed",
                },
                "sheets": records,
            },
            indent=2,
        )
        + "\n"
    )
    return records


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("before", type=Path)
    p.add_argument("after", type=Path)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--before-label", default="RAW TRACE")
    p.add_argument("--after-label", default="CORRECTED")
    p.add_argument("--sample", action="append")
    p.add_argument("--sizes", nargs="+", type=int, default=[12, 16, 24, 48])
    a = p.parse_args()
    print(
        json.dumps(
            render(
                a.before,
                a.after,
                a.out,
                a.before_label,
                a.after_label,
                a.sample,
                a.sizes,
            ),
            indent=2,
        )
    )
