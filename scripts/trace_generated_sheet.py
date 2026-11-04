#!/usr/bin/env python3
"""Trace reviewed glyph crops from a frozen AI concept sheet, without API calls.

Optional authoring step: requires examples/imagegen/requirements-trace.txt.
The font compiler consumes the resulting SVGs without these dependencies.
"""

import argparse
import hashlib
import json
import shutil
import tempfile
from importlib.metadata import version
from pathlib import Path

from fontTools.misc.transform import Transform
from fontTools.pens.recordingPen import RecordingPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen

from fontify.model import FontifyError, local_path


def trace_sheet(plan_path, output):
    import numpy as np
    import potrace
    from PIL import Image

    plan_path = Path(plan_path).resolve()
    output = Path(output).resolve()
    if output.exists():
        raise FontifyError(
            "trace output already exists; choose a fresh candidate directory"
        )
    plan = json.loads(plan_path.read_text())
    image_path = local_path(plan_path.parent, plan["image"])
    data = image_path.read_bytes()
    source_hash = hashlib.sha256(data).hexdigest()
    if source_hash != plan["source_sha256"]:
        raise FontifyError("source image hash differs from reviewed trace plan")
    image = Image.open(image_path).convert("L")
    if list(image.size) != plan["image_size"]:
        raise FontifyError("source image dimensions differ from reviewed trace plan")
    names = [g["name"] for g in plan["glyphs"]]
    cps = [g["unicode"] for g in plan["glyphs"]]
    if len(set(names)) != len(names) or len(set(cps)) != len(cps):
        raise FontifyError("duplicate glyph mapping in crop plan")
    base = json.loads((plan_path.parent / "fontify-base.json").read_text())
    glyphs = [{"name": "space", "unicode": "U+0020", "source": None, "advance": 300}]
    records = []
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".trace-", dir=output.parent) as stage:
        stage = Path(stage)
        (stage / "glyphs").mkdir()
        for spec in plan["glyphs"]:
            x0, y0, x1, y1 = spec["box"]
            if not 0 <= x0 < x1 <= image.width or not 0 <= y0 < y1 <= image.height:
                raise FontifyError("crop box exceeds source image")
            mask = np.asarray(image.crop((x0, y0, x1, y1))) < plan["threshold"]
            if not mask.any():
                raise FontifyError(f"empty glyph crop: {spec['name']}")
            traced = potrace.Bitmap(
                np.where(np.pad(mask, 2), 0, 255).astype(np.uint8)
            ).trace(**plan["trace"])
            pen = RecordingPen()
            for curve in traced:
                pen.moveTo((curve.start_point.x - 2, curve.start_point.y - 2))
                for segment in curve:
                    if segment.is_corner:
                        pen.lineTo((segment.c.x - 2, segment.c.y - 2))
                        pen.lineTo((segment.end_point.x - 2, segment.end_point.y - 2))
                    else:
                        pen.curveTo(
                            (segment.c1.x - 2, segment.c1.y - 2),
                            (segment.c2.x - 2, segment.c2.y - 2),
                            (segment.end_point.x - 2, segment.end_point.y - 2),
                        )
                pen.closePath()
            row = plan["rows"][spec["row"]]
            scale = plan["cap_height"] / row["pixels_per_cap"]
            # One uniform scale per declared row; no per-letter width/height fit.
            transform = Transform(
                scale,
                0,
                0,
                scale,
                plan["sidebearing"],
                plan["svg_baseline"] + (y0 - row["baseline"]) * scale,
            )
            svgpen = SVGPathPen(None)
            pen.replay(TransformPen(svgpen, transform))
            advance = round((x1 - x0) * scale + 2 * plan["sidebearing"])
            filename = spec["name"] + ".svg"
            (stage / "glyphs" / filename).write_text(
                f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {advance} 1000"><path d="{svgpen.getCommands()}"/></svg>\n'
            )
            glyphs.append(
                {
                    "name": spec["name"],
                    "unicode": spec["unicode"],
                    "source": "glyphs/" + filename,
                    "advance": advance,
                }
            )
            records.append(
                {
                    **spec,
                    "uniform_scale": scale,
                    "advance": advance,
                    "source_sha256": source_hash,
                }
            )
        base["glyphs"] = glyphs
        (stage / "fontify.json").write_text(json.dumps(base, indent=2) + "\n")
        record = {
            "schema": 1,
            "source_sha256": source_hash,
            "plan_sha256": hashlib.sha256(plan_path.read_bytes()).hexdigest(),
            "construction": "offline raster tracing of generated artwork; no replacement glyphs",
            "parameters": plan["trace"],
            "threshold": plan["threshold"],
            "glyphs": records,
            "status": "review_required",
            "tools": {p: version(p) for p in ("potracer", "numpy", "pillow")},
        }
        (stage / "trace-record.json").write_text(json.dumps(record, indent=2) + "\n")
        # Run the same topology/metric checks before publishing any candidate files.
        from fontify.model import load_project
        from fontify.outlines import compile_project

        compile_project(load_project(stage / "fontify.json"))
        shutil.copytree(stage, output)
    return output / "fontify.json"


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("plan", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    try:
        print(
            json.dumps(
                {
                    "project": str(trace_sheet(args.plan, args.out)),
                    "status": "review_required",
                }
            )
        )
    except (FontifyError, OSError, ValueError) as e:
        parser.exit(1, f"{e}\n")
