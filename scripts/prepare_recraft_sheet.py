#!/usr/bin/env python3
"""Explicit offline authoring: split a reviewed monochrome Recraft SVG sheet.

Painted white counters become holes before the strict Fontify compiler sees them.
This helper never generates artwork, guesses Unicode, or adjusts curves/weights.
"""

import argparse
import hashlib
import json
from pathlib import Path

import pathops
from defusedxml import ElementTree as ET
from fontTools.misc.transform import Transform
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.recordingPen import RecordingPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.svgLib.path import parse_path

from fontify.model import FontifyError, load_project, local_path
from fontify.outlines import affine, compile_project
from fontify.quality import SegmentsPen, to_record


def remove_collapsing_edges(record):
    """Remove only sub-unit edges whose every control point rounds identically."""
    pen = SegmentsPen()
    record.replay(pen)
    removed = 0
    for edges in pen.contours:
        for i in range(len(edges) - 1, -1, -1):
            _, points = edges[i]
            if len({tuple(round(v) for v in p) for p in points}) != 1:
                continue
            anchor = points[0]
            following = edges[(i + 1) % len(edges)]
            delta = tuple(anchor[j] - following[1][0][j] for j in (0, 1))
            following[1][0] = anchor
            if following[0] != "L":
                following[1][1] = tuple(following[1][1][j] + delta[j] for j in (0, 1))
            del edges[i]
            removed += 1
    return to_record(pen.contours), removed


def contains(a, b):
    return a[0] <= b[0] and a[1] <= b[1] and a[2] >= b[2] and a[3] >= b[3]


def prepare(plan_path, output):
    plan_path = Path(plan_path).resolve()
    plan = json.loads(plan_path.read_text())
    source = local_path(plan_path.parent, plan["source"])
    data = source.read_bytes()
    if hashlib.sha256(data).hexdigest() != plan["source_sha256"]:
        raise FontifyError("source SVG hash changed; review extraction again")
    output = Path(output).resolve()
    if output.exists():
        raise FontifyError("output already exists; preserve the previous candidate")
    root = ET.fromstring(
        data, forbid_dtd=True, forbid_entities=True, forbid_external=True
    )
    paths = []
    viewbox = [float(v) for v in root.get("viewBox").split()]
    if len(viewbox) != 4 or viewbox[2] <= 0 or viewbox[3] <= 0:
        raise FontifyError("sheet needs a positive viewBox")
    canvas = [viewbox[0], viewbox[1], viewbox[0] + viewbox[2], viewbox[1] + viewbox[3]]
    for element in root:
        kind = element.tag.rsplit("}", 1)[-1]
        if kind == "metadata":
            continue
        if kind != "path" or set(element.attrib) - {"d", "fill", "transform"}:
            raise FontifyError("sheet helper accepts simple filled paths only")
        fill = element.get("fill")
        if fill not in plan["ink_fills"] + plan["paper_fills"]:
            raise FontifyError("unexpected paint color; review the source")
        rec = RecordingPen()
        parse_path(
            element.get("d"), TransformPen(rec, affine(element.get("transform", "")))
        )
        if any(op == "endPath" for op, _ in rec.value):
            raise FontifyError("close every source path explicitly")
        bbox = BoundsPen(None)
        rec.replay(bbox)
        if fill in plan["paper_fills"] and list(bbox.bounds) == canvas:
            continue  # The one paper background is not a glyph contour.
        paths.append(
            {"record": rec, "bounds": bbox.bounds, "ink": fill in plan["ink_fills"]}
        )
    all_chars = "".join(row["characters"] for row in plan["rows"])
    if len(set(all_chars)) != len(all_chars):
        raise FontifyError("duplicate explicitly assigned characters")
    assignments = []
    used = set()
    for row in plan["rows"]:
        groups = []
        inks = [
            (i, p)
            for i, p in enumerate(paths)
            if p["ink"]
            and row["top"] <= p["bounds"][1]
            and p["bounds"][3] <= row["bottom"]
        ]
        for index, path in sorted(
            inks, key=lambda x: (x[1]["bounds"][0] + x[1]["bounds"][2]) / 2
        ):
            center = (path["bounds"][0] + path["bounds"][2]) / 2
            group = next(
                (
                    g
                    for g in groups
                    if abs(g["center"] - center) < plan["component_center_tolerance"]
                ),
                None,
            )
            if group is None:
                group = {"center": center, "indices": []}
                groups.append(group)
            group["indices"].append(index)
        if len(groups) != len(row["characters"]):
            raise FontifyError(
                f"row {row['characters']}: {len(groups)} groups, expected {len(row['characters'])}"
            )
        for char, group in zip(row["characters"], groups):
            bounds = [
                min(paths[i]["bounds"][0] for i in group["indices"]),
                min(paths[i]["bounds"][1] for i in group["indices"]),
                max(paths[i]["bounds"][2] for i in group["indices"]),
                max(paths[i]["bounds"][3] for i in group["indices"]),
            ]
            whites = [
                i
                for i, p in enumerate(paths)
                if not p["ink"] and contains(bounds, p["bounds"])
            ]
            indices = sorted(group["indices"] + whites)
            if used.intersection(indices):
                raise FontifyError("ambiguous painted component assignment")
            used.update(indices)
            combined = pathops.Path()
            for index in indices:
                p = pathops.Path()
                paths[index]["record"].replay(p.getPen())
                combined = pathops.op(
                    combined,
                    p,
                    pathops.PathOp.UNION
                    if paths[index]["ink"]
                    else pathops.PathOp.DIFFERENCE,
                )
            # A shared scale; x translation supplies sidebearings, not width fitting.
            bearing = plan["sidebearing"]
            scale = plan["scale"]
            transform = Transform(
                scale,
                0,
                0,
                scale,
                bearing - bounds[0] * scale,
                plan["svg_baseline"] - row["baseline"] * scale,
            )
            rec = RecordingPen()
            combined.draw(TransformPen(rec, transform))
            rec, removed = remove_collapsing_edges(rec)
            advance = round((bounds[2] - bounds[0]) * scale + 2 * bearing)
            assignments.append(
                {
                    "name": char,
                    "unicode": f"U+{ord(char):04X}",
                    "source": f"glyphs/U{ord(char):04X}.svg",
                    "advance": advance,
                    "record": rec,
                    "sheet_bounds": bounds,
                    "path_indices": indices,
                    "row_baseline": row["baseline"],
                    "collapsed_subunit_edges_removed": removed,
                }
            )
    if used != set(range(len(paths))):
        raise FontifyError("unassigned source paths; do not silently discard artwork")
    output.mkdir(parents=True)
    (output / "glyphs").mkdir()
    base = json.loads(local_path(plan_path.parent, plan["base_project"]).read_text())
    base["glyphs"] = [
        {
            "name": "space",
            "unicode": "U+0020",
            "source": None,
            "advance": plan["space_advance"],
        }
    ]
    journal = []
    for item in assignments:
        spec = {k: item[k] for k in ("name", "unicode", "source", "advance")}
        pen = SVGPathPen(None)
        item["record"].replay(pen)
        (output / spec["source"]).write_text(
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {spec["advance"]} 1400"><path d="{pen.getCommands()}"/></svg>\n'
        )
        base["glyphs"].append(spec)
        journal.append({k: v for k, v in item.items() if k != "record"})
    manifest = output / "fontify.json"
    manifest.write_text(json.dumps(base, indent=2) + "\n")
    compile_project(load_project(manifest))
    (output / "extraction.json").write_text(
        json.dumps(
            {
                "source_sha256": plan["source_sha256"],
                "scale": plan["scale"],
                "normalization": "Explicit paint-order union/difference converts white counters to holes; shared scale and declared baselines. Locally join only edges whose controls all round to one integer point. No raster tracing or curve fitting.",
                "glyphs": journal,
            },
            indent=2,
        )
        + "\n"
    )
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("plan", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps({"project": str(prepare(args.plan, args.out))}, indent=2))
