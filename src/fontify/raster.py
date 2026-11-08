#!/usr/bin/env python3
"""Trace reviewed glyph crops from a frozen AI concept sheet, without API calls.

Optional authoring step: requires examples/imagegen/requirements-trace.txt.
The font compiler consumes the resulting SVGs without these dependencies.
"""

import hashlib
import json
import re
import shutil
import tempfile
from collections import deque
from importlib.metadata import version
from io import BytesIO
from pathlib import Path

from fontTools.misc.transform import Transform
from fontTools.pens.recordingPen import RecordingPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen

from .model import FontifyError, codepoint, keys, local_path, number


def _trace_legacy(plan_path, output):
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


def _box(value, size, label):
    if not isinstance(value, list) or len(value) != 4:
        raise FontifyError(f"{label}: expected [left, top, right, bottom]")
    for v in value:
        number(v, f"{label} crop box", 0, max(size), integer=True)
        if type(v) is not int:
            raise FontifyError(f"{label}: crop box coordinates must be integers")
    x0, y0, x1, y1 = value
    if not 0 <= x0 < x1 <= size[0] or not 0 <= y0 < y1 <= size[1]:
        raise FontifyError(f"{label}: crop box exceeds source image")
    return tuple(int(v) for v in value)


def _reason(value, label):
    if not isinstance(value, str) or not value.strip():
        raise FontifyError(f"{label}: a nonempty review reason is required")


def _validate_plan(plan):
    keys(
        plan,
        "schema image source_sha256 image_size threshold cap_height "
        "svg_baseline sidebearing rows trace glyphs review_notes preparation",
        "trace plan",
    )
    if type(plan.get("schema")) is not int or plan["schema"] != 1:
        raise FontifyError("trace plan schema must be 1")
    if not isinstance(plan.get("source_sha256"), str) or not re.fullmatch(
        r"[0-9a-f]{64}", plan["source_sha256"]
    ):
        raise FontifyError("source_sha256 must be a lowercase SHA-256 hash")
    size = plan.get("image_size")
    if not isinstance(size, list) or len(size) != 2:
        raise FontifyError("image_size must be [width, height]")
    for v in size:
        number(v, "image_size", 1, 20000, integer=True)
        if type(v) is not int:
            raise FontifyError("image_size entries must be integers")
    if size[0] * size[1] > 40_000_000:
        raise FontifyError("source image exceeds 40 million pixel preparation limit")
    number(plan.get("threshold"), "threshold", 1, 255, integer=True)
    number(plan.get("cap_height"), "cap_height", 1, 32767)
    number(plan.get("svg_baseline"), "svg_baseline")
    number(plan.get("sidebearing"), "sidebearing", 0, 32767)
    rows = plan.get("rows")
    if not isinstance(rows, list) or not rows:
        raise FontifyError("rows must be a nonempty list")
    for row in rows:
        keys(row, "baseline pixels_per_cap", "row")
        number(row.get("baseline"), "row baseline", 0, size[1])
        number(row.get("pixels_per_cap"), "pixels_per_cap", 0.001, 20000)
    trace = plan.get("trace")
    keys(trace, "turdsize turnpolicy alphamax opticurve opttolerance", "trace")
    for key, lo, hi, integer in (
        ("turdsize", 0, 10000, True),
        ("turnpolicy", 0, 6, True),
        ("alphamax", 0, 1.334, False),
        ("opttolerance", 0, 100, False),
    ):
        if key in trace:
            number(trace[key], f"trace.{key}", lo, hi, integer=integer)
    if "opticurve" in trace and type(trace["opticurve"]) is not bool:
        raise FontifyError("trace.opticurve must be boolean")
    glyphs = plan.get("glyphs")
    if not isinstance(glyphs, list) or not glyphs:
        raise FontifyError("glyphs must be a nonempty list")
    names, cps = set(), set()
    for spec in glyphs:
        keys(spec, "name unicode box row", "trace glyph")
        name = spec.get("name")
        if not isinstance(name, str) or not re.fullmatch(
            r"[A-Za-z_][A-Za-z0-9_.]{0,62}", name
        ):
            raise FontifyError("invalid trace glyph name")
        cp = codepoint(spec.get("unicode"))
        if name in ("space", ".notdef", "NULL") or cp < 33 or 0x7F <= cp < 0xA0:
            raise FontifyError("trace glyph must be a drawable, non-reserved glyph")
        if name in names or cp in cps:
            raise FontifyError("duplicate glyph mapping in crop plan")
        names.add(name)
        cps.add(cp)
        _box(spec.get("box"), size, name)
        number(spec.get("row"), f"{name}.row", 0, len(rows) - 1, integer=True)
        if type(spec["row"]) is not int:
            raise FontifyError(f"{name}.row must be an integer")
    if "preparation" in plan:
        _validate_preparation(plan, names)


def _validate_preparation(plan, names):
    prep = plan["preparation"]
    keys(prep, "schema masks protect_boxes components resample", "preparation")
    if type(prep.get("schema")) is not int or prep["schema"] != 1:
        raise FontifyError("preparation.schema must be 1")
    if plan["trace"].get("turdsize") != 0:
        raise FontifyError(
            "prepared tracing requires trace.turdsize=0; select noise explicitly"
        )
    for field in ("masks", "protect_boxes"):
        items = prep.get(field, [])
        if not isinstance(items, list):
            raise FontifyError(f"preparation.{field} must be a list")
        for item in items:
            keys(item, "box reason kind" if field == "masks" else "box reason", field)
            _box(item.get("box"), plan["image_size"], field)
            _reason(item.get("reason"), field)
            if field == "masks" and item.get("kind") not in ("guide", "label"):
                raise FontifyError("mask kind must be guide or label")
    comp = prep.get("components", {})
    keys(comp, "connectivity small_area_max glyphs", "components")
    if type(comp.get("connectivity", 8)) is not int or comp.get(
        "connectivity", 8
    ) not in (4, 8):
        raise FontifyError("component connectivity must be 4 or 8")
    number(comp.get("small_area_max", 4), "small_area_max", 0, 40000000, integer=True)
    selections = comp.get("glyphs", {})
    if not isinstance(selections, dict) or set(selections) - names:
        raise FontifyError("component selections must reference declared glyph names")
    boxes = {g["name"]: g["box"] for g in plan["glyphs"]}
    for name, selection in selections.items():
        keys(selection, "preserve remove", "component selections")
        for mode in ("preserve", "remove"):
            entries = selection.get(mode, [])
            if not isinstance(entries, list):
                raise FontifyError(f"components.{name}.{mode} must be a list")
            for entry in entries:
                keys(entry, "point reason", "component selector")
                _reason(entry.get("reason"), "component selector")
                point = entry.get("point")
                if not isinstance(point, list) or len(point) != 2:
                    raise FontifyError("component point must be [source_x, source_y]")
                for v in point:
                    number(v, "component point", 0, 20000, integer=True)
                    if type(v) is not int:
                        raise FontifyError(
                            "component point coordinates must be integers"
                        )
                x0, y0, x1, y1 = boxes[name]
                if not (x0 <= point[0] < x1 and y0 <= point[1] < y1):
                    raise FontifyError(f"component point outside {name} crop")
    resample = prep.get("resample", {})
    keys(resample, "scale filter threshold", "resample")
    number(resample.get("scale", 1), "resample.scale", 1, 8, integer=True)
    if resample.get("filter", "nearest") not in (
        "nearest",
        "bilinear",
        "bicubic",
        "lanczos",
    ):
        raise FontifyError(
            "resample.filter must be nearest, bilinear, bicubic or lanczos"
        )
    number(resample.get("threshold", 128), "resample.threshold", 1, 255, integer=True)


def _raster_dependencies():
    try:
        import numpy as np
        import potrace
        from PIL import Image
    except ImportError as exc:
        raise FontifyError(
            "raster tracing needs optional dependencies; install fontify[raster]"
        ) from exc
    return np, potrace, Image


def trace_sheet(plan_path, output):
    """Trace raster sources only. Preparation is opt-in and versioned in the plan.

    Omitting ``preparation`` preserves the frozen legacy crop/trace behavior.
    Native vectors must go directly to the ordinary SVG compiler.
    """
    plan_path, output = Path(plan_path).resolve(), Path(output)
    if output.exists() or output.is_symlink():
        raise FontifyError(
            "trace output already exists; choose a fresh candidate directory"
        )
    output = output.resolve()
    try:
        plan_data = plan_path.read_bytes()
        plan = json.loads(plan_data)
    except (OSError, ValueError) as exc:
        raise FontifyError(f"cannot read raster trace plan: {exc}") from exc
    _validate_plan(plan)
    image_path = local_path(plan_path.parent, plan.get("image"))
    data = image_path.read_bytes()
    header = data[:4096].lower()
    if (
        image_path.suffix.lower() in (".svg", ".svgz", ".pdf", ".eps", ".ps", ".ai")
        or (header.lstrip().startswith(b"<") and b"<svg" in header)
        or data.startswith((b"%PDF", b"%!PS"))
    ):
        raise FontifyError(
            "native vector source: skip raster preparation and use the SVG compiler"
        )
    if hashlib.sha256(data).hexdigest() != plan["source_sha256"]:
        raise FontifyError("source image hash differs from reviewed trace plan")
    np, potrace, Image = _raster_dependencies()
    try:
        with Image.open(BytesIO(data)) as source:
            # Never ask Pillow to rasterize PDF/EPS or other vector formats.
            if source.format not in ("PNG", "JPEG", "TIFF", "BMP", "WEBP", "GIF"):
                raise FontifyError("unsupported raster image format")
            if list(source.size) != plan["image_size"]:
                raise FontifyError(
                    "source image dimensions differ from reviewed trace plan"
                )
            if getattr(source, "n_frames", 1) != 1:
                raise FontifyError("use one explicitly selected raster frame")
            if "preparation" in plan:
                rgba = source.convert("RGBA")
                white = Image.new("RGBA", rgba.size, "white")
                image = Image.alpha_composite(white, rgba).convert("L")
    except (OSError, ValueError, Image.DecompressionBombError) as exc:
        if isinstance(exc, FontifyError):
            raise
        raise FontifyError(f"cannot decode raster source: {exc}") from exc
    if "preparation" not in plan:
        return _trace_legacy(plan_path, output)
    return _trace_prepared(
        plan_path, output, plan, image_path, image, data, plan_data, np, potrace, Image
    )


def _components(mask, connectivity, np):
    """Stable row-major component IDs; no automatic deletion, erosion or closing."""
    labels = np.zeros(mask.shape, dtype=np.int32)
    result = []
    neighbors = ((-1, 0), (1, 0), (0, -1), (0, 1))
    if connectivity == 8:
        neighbors += ((-1, -1), (-1, 1), (1, -1), (1, 1))
    height, width = mask.shape
    for y, x in np.argwhere(mask):
        if labels[y, x]:
            continue
        ident = len(result) + 1
        labels[y, x] = ident
        pending = deque([(int(y), int(x))])
        left = right = int(x)
        top = bottom = int(y)
        area = 0
        while pending:
            py, px = pending.popleft()
            area += 1
            left, right = min(left, px), max(right, px)
            top, bottom = min(top, py), max(bottom, py)
            for dy, dx in neighbors:
                ny, nx = py + dy, px + dx
                if (
                    0 <= ny < height
                    and 0 <= nx < width
                    and mask[ny, nx]
                    and not labels[ny, nx]
                ):
                    labels[ny, nx] = ident
                    pending.append((ny, nx))
        result.append(
            {"id": ident, "area": area, "box": [left, top, right + 1, bottom + 1]}
        )
    return labels, result


def _apply_rect(target, rect, crop, value):
    x0, y0, x1, y1 = crop
    left, top = max(x0, rect[0]), max(y0, rect[1])
    right, bottom = min(x1, rect[2]), min(y1, rect[3])
    if left < right and top < bottom:
        target[top - y0 : bottom - y0, left - x0 : right - x0] = value


def _prepare_mask(raw, spec, prep, np):
    crop = spec["box"]
    x0, y0, _, _ = crop
    erase = np.zeros_like(raw)
    protect = np.zeros_like(raw)
    for entry in prep.get("masks", []):
        _apply_rect(erase, entry["box"], crop, True)
    for entry in prep.get("protect_boxes", []):
        _apply_rect(protect, entry["box"], crop, True)
    mask = raw & ~(erase & ~protect)
    comp = prep.get("components", {})
    labels, records = _components(mask, comp.get("connectivity", 8), np)
    selectors = comp.get("glyphs", {}).get(spec["name"], {})
    decisions = {"preserve": {}, "remove": {}}
    for mode in decisions:
        for entry in selectors.get(mode, []):
            x, y = entry["point"]
            ident = int(labels[y - y0, x - x0])
            if not ident:
                raise FontifyError(
                    f"{spec['name']}: {mode} point {entry['point']} is not retained foreground after masks"
                )
            decisions[mode].setdefault(ident, []).append(entry["reason"])
    largest = max((r["area"] for r in records), default=0)
    for record in records:
        ident = record["id"]
        left, top, right, bottom = record["box"]
        record["source_box"] = [left + x0, top + y0, right + x0, bottom + y0]
        del record["box"]
        record["classification"] = (
            "small_candidate"
            if record["area"] <= comp.get("small_area_max", 4)
            else "primary_ink"
            if record["area"] == largest
            else "detached_ink"
        )
        record["preserve_reasons"] = decisions["preserve"].get(ident, [])
        record["remove_reasons"] = decisions["remove"].get(ident, [])
        if record["preserve_reasons"]:
            record["decision"] = "preserve_explicit"
        elif record["remove_reasons"]:
            record["decision"] = "remove_explicit"
            mask[labels == ident] = False
        else:
            record["decision"] = "preserve_default"
    return mask, {
        "components": records,
        "mask_removed_pixels": int((raw & erase & ~protect).sum()),
        "protected_mask_pixels": int((raw & erase & protect).sum()),
    }


def _bounds(mask, np):
    ys, xs = np.nonzero(mask)
    if not len(xs):
        raise FontifyError("raster preparation produced an empty glyph")
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def _save_mask(stage, name, mask, np, Image):
    target = stage / name
    target.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(np.where(mask, 0, 255).astype(np.uint8)).save(target)
    return {
        "path": name,
        "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
        "size": [mask.shape[1], mask.shape[0]],
        "foreground_pixels": int(mask.sum()),
    }


def _trace_mask(mask, settings, np, potrace):
    traced = potrace.Bitmap(np.where(np.pad(mask, 2), 0, 255).astype(np.uint8)).trace(
        **settings
    )
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
    return pen


def _trace_prepared(
    plan_path, output, plan, image_path, image, data, plan_data, np, potrace, Image
):
    prep = plan["preparation"]
    base_path = plan_path.parent / "fontify-base.json"
    try:
        base_data = base_path.read_bytes()
        base = json.loads(base_data)
    except (OSError, ValueError) as exc:
        raise FontifyError(f"cannot read fontify-base.json: {exc}") from exc
    if not isinstance(base, dict):
        raise FontifyError("fontify-base.json must be an object")
    for field in ("cap_height", "svg_baseline"):
        if (
            base.get(field, {"cap_height": 700, "svg_baseline": 800}[field])
            != plan[field]
        ):
            raise FontifyError(f"trace plan {field} must match fontify-base.json")
    resample = {
        "scale": 1,
        "filter": "nearest",
        "threshold": 128,
        **prep.get("resample", {}),
    }
    factor = int(resample["scale"])
    glyphs = [{"name": "space", "unicode": "U+0020", "source": None, "advance": 300}]
    records = []
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".trace-", dir=output.parent) as temporary:
        stage = Path(temporary)
        (stage / "glyphs").mkdir()
        (stage / "source").mkdir()
        source_name = "source/original" + image_path.suffix.lower()
        (stage / source_name).write_bytes(data)
        (stage / "source/trace-plan.json").write_bytes(plan_data)
        (stage / "source/fontify-base.json").write_bytes(base_data)
        for spec in plan["glyphs"]:
            x0, y0, _, _ = spec["box"]
            raw = np.asarray(image.crop(tuple(spec["box"]))) < plan["threshold"]
            cleaned, decisions = _prepare_mask(raw, spec, prep, np)
            left, top, right, bottom = _bounds(cleaned, np)
            # A canonical, fixed halo makes resampling independent of crop padding.
            halo = 4
            canonical = np.pad(cleaned[top:bottom, left:right], halo)
            height, width = canonical.shape
            if width * height * factor * factor > 40_000_000:
                raise FontifyError("resampled glyph exceeds 40 million pixel limit")
            bitmap = Image.fromarray(np.where(canonical, 0, 255).astype(np.uint8))
            if factor != 1:
                bitmap = bitmap.resize(
                    (width * factor, height * factor),
                    getattr(Image.Resampling, resample["filter"].upper()),
                )
            sampled = np.asarray(bitmap) < resample["threshold"]
            sx0, sy0, sx1, sy1 = _bounds(sampled, np)
            source_x = x0 + left - halo + sx0 / factor
            source_y = y0 + top - halo + sy0 / factor
            trace_mask = sampled[sy0:sy1, sx0:sx1]
            row = plan["rows"][spec["row"]]
            scale = plan["cap_height"] / row["pixels_per_cap"]
            trace_scale = scale / factor
            advance = round((sx1 - sx0) * trace_scale + 2 * plan["sidebearing"])
            number(advance, "prepared advance", 1, 32767, integer=True)
            pen = _trace_mask(trace_mask, plan["trace"], np, potrace)
            svgpen = SVGPathPen(None)
            pen.replay(
                TransformPen(
                    svgpen,
                    Transform(
                        trace_scale,
                        0,
                        0,
                        trace_scale,
                        plan["sidebearing"],
                        plan["svg_baseline"] + (source_y - row["baseline"]) * scale,
                    ),
                )
            )
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
            artifacts = {
                label: _save_mask(
                    stage, f"masks/{spec['name']}/{label}.png", mask, np, Image
                )
                for label, mask in (
                    ("raw", raw),
                    ("cleaned", cleaned),
                    ("resampled", sampled),
                )
            }
            records.append(
                {
                    **spec,
                    **decisions,
                    "uniform_scale": scale,
                    "advance": advance,
                    "source_sha256": plan["source_sha256"],
                    "artifacts": artifacts,
                    "retained_ink_source_box": [
                        x0 + left,
                        y0 + top,
                        x0 + right,
                        y0 + bottom,
                    ],
                    "trace_ink_source_box": [
                        source_x,
                        source_y,
                        source_x + (sx1 - sx0) / factor,
                        source_y + (sy1 - sy0) / factor,
                    ],
                    "resampled_origin_source": [x0 + left - halo, y0 + top - halo],
                    "resampled_pixel_size_source": 1 / factor,
                    "trace_box_resampled": [sx0, sy0, sx1, sy1],
                    "resample_halo_source_pixels": halo,
                    "baseline_source": row["baseline"],
                    "trace_scale": trace_scale,
                }
            )
        base["glyphs"] = glyphs
        (stage / "fontify.json").write_text(json.dumps(base, indent=2) + "\n")
        record = {
            "schema": 2,
            "preparation_schema": 1,
            "preparation": prep,
            "source_sha256": plan["source_sha256"],
            "source_original": source_name,
            "plan_sha256": hashlib.sha256(plan_data).hexdigest(),
            "base_sha256": hashlib.sha256(base_data).hexdigest(),
            "construction": "offline raster preparation and tracing; explicit removals only; no replacement glyphs",
            "parameters": plan["trace"],
            "threshold": plan["threshold"],
            "alpha_background": "white",
            "resample": resample,
            "placement": "retained ink bounds; source-coordinate baseline; uniform row scale",
            "glyphs": records,
            "status": "review_required",
            "tools": {p: version(p) for p in ("potracer", "numpy", "pillow")},
        }
        (stage / "trace-record.json").write_text(json.dumps(record, indent=2) + "\n")
        from .model import load_project
        from .outlines import compile_project

        compile_project(load_project(stage / "fontify.json"))
        shutil.copytree(stage, output)
    return output / "fontify.json"
