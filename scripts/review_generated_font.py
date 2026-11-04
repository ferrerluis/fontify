#!/usr/bin/env python3
"""Compare the frozen generated artwork with actual compiled font outlines."""

import argparse
import base64
import hashlib
import json
from io import BytesIO
from pathlib import Path

from fontTools.pens.recordingPen import RecordingPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.ttLib import TTFont

from fontify.model import FontifyError
from fontify.outlines import FlattenPen, geometry
from fontify.review import verified_release


def review_font(project_dir, manifest_path, output):
    import numpy as np
    from PIL import Image, ImageDraw

    root = Path(project_dir)
    output = Path(output)
    plan = json.loads((root / "source/trace-plan.json").read_text())
    image_path = root / "source" / plan["image"]
    if hashlib.sha256(image_path.read_bytes()).hexdigest() != plan["source_sha256"]:
        raise FontifyError("generated source hash mismatch")
    source = Image.open(image_path).convert("L")
    manifest_path = Path(manifest_path)
    manifest = verified_release(manifest_path)
    cards = []
    scores = []
    with TTFont(manifest_path.parent / manifest["font"]) as font:
        gs = font.getGlyphSet()
        for spec in plan["glyphs"]:
            name = spec["name"]
            x0, y0, x1, y1 = spec["box"]
            row = plan["rows"][spec["row"]]
            scale = plan["cap_height"] / row["pixels_per_cap"]
            crop = source.crop(spec["box"])
            expected = np.asarray(crop) < plan["threshold"]
            rec = RecordingPen()
            gs[name].draw(rec)
            _, depths, _ = geometry(rec)
            flat = FlattenPen()
            rec.replay(flat)
            # Draw from the compiled font back into the source pixel frame.
            oversample = 4
            mask = Image.new(
                "L", (crop.width * oversample, crop.height * oversample), 0
            )
            draw = ImageDraw.Draw(mask)
            for i in sorted(range(len(flat.contours)), key=lambda i: depths[i]):
                pts = [
                    (
                        (x - plan["sidebearing"]) / scale * oversample,
                        (row["baseline"] - y0 - y / scale) * oversample,
                    )
                    for x, y in flat.contours[i]
                ]
                draw.polygon(pts, fill=255 if depths[i] % 2 == 0 else 0)
            rendered = np.asarray(mask.resize(crop.size, Image.Resampling.BOX)) >= 128
            union = np.logical_or(expected, rendered).sum()
            iou = float(np.logical_and(expected, rendered).sum() / max(union, 1))
            scores.append(
                {
                    "glyph": name,
                    "source_compiled_iou": round(iou, 6),
                    "status": "measurement_only",
                }
            )
            png = BytesIO()
            crop.save(png, format="PNG")
            b64 = base64.b64encode(png.getvalue()).decode()
            pen = SVGPathPen(gs)
            gs[name].draw(pen)
            path = pen.getCommands()
            tx = plan["sidebearing"]
            ty = plan["svg_baseline"] + (y0 - row["baseline"]) * scale
            width = max(1100, (x1 - x0) * scale + 100)
            raw = f'<image href="data:image/png;base64,{b64}" width="{crop.width}" height="{crop.height}" transform="translate({tx} {ty}) scale({scale})"/>'
            compiled = f'<path d="{path}" fill="#087eaa" fill-opacity=".65" transform="translate(0 {plan["svg_baseline"]}) scale(1 -1)"/>'
            overlay = f'<svg viewBox="0 0 {width} 1050" role="img" aria-label="{name} source and compiled overlay">{raw}{compiled}</svg>'
            source_view = f'<svg viewBox="0 0 {width} 1050" role="img" aria-label="Generated {name} crop at shared scale">{raw}</svg>'
            cards.append(
                f'<article><h2>{name} <small>mask overlap {iou:.2%}</small></h2><div class="pair">{source_view}{overlay}</div><p>Black: generated source · blue: compiled outline. Shared placement and uniform row scale.</p></article>'
            )
    output.mkdir(parents=True, exist_ok=True)
    result = {
        "source_sha256": plan["source_sha256"],
        "font_sha256": manifest["artifacts"][manifest["font"]],
        "minimum_iou": min(s["source_compiled_iou"] for s in scores),
        "glyphs": scores,
        "status": "review_required",
        "note": "Pixel overlap measures tracing fidelity, not optical quality, exact curve preservation or human approval.",
    }
    (output / "source-comparison.json").write_text(json.dumps(result, indent=2) + "\n")
    html = (
        '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Generated source / compiled font</title><style>body{background:#f7f5ef;color:#161616;font:16px/1.5 system-ui;margin:32px}main{max-width:1200px;margin:auto}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:18px}article{border:1px solid #ccc;padding:16px;background:white}h2{margin:0 0 10px}small{font:12px system-ui}.pair{display:grid;grid-template-columns:1fr 1fr;gap:12px;align-items:center}.pair img{width:100%;max-height:180px;object-fit:contain}.pair svg{width:100%;height:180px}p{max-width:80ch}article p{font-size:12px}</style><main><h1>Image-generated artwork / compiled font</h1><p>The raw AI image is preserved. Each card shows its original crop and a black/blue overlay against the exported TTF. Raster tracing approximates outlines; these measurements do not approve typography.</p><p>The generated bottom row was smaller. Its explicit uniform scaling is recorded in trace-plan.json; no per-letter stretching, mirroring or thinning was applied.</p><div class="grid">'
        + "".join(cards)
        + "</div></main></html>"
    )
    (output / "source-comparison.html").write_text(html)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("project", type=Path)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    a = parser.parse_args()
    result = review_font(a.project, a.manifest, a.out)
    print(
        json.dumps(
            {
                "minimum_source_compiled_iou": result["minimum_iou"],
                "review": str(a.out / "source-comparison.html"),
            }
        )
    )
