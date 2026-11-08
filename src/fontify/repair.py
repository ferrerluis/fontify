"""Bounded, explicit corrections of unapproved candidates; never a compiler pass."""

import copy
import json
import math
import shutil
from collections import defaultdict
from pathlib import Path

import pathops
from fontTools.misc.transform import Transform
from fontTools.pens.cu2quPen import Cu2QuPen
from fontTools.pens.recordingPen import RecordingPen
from fontTools.pens.roundingPen import RoundingPen

from .model import FontifyError, keys, load_project
from .outlines import FlattenPen, compile_project, digest, geometry
from .quality import (
    SegmentsPen,
    angle,
    axis_feature,
    glyph_audit,
    ink_intervals,
    load_profile,
    tangent,
    to_record,
    vector,
)
from .rubrics import require_resolved


def line_distance(p, a, b):
    dx, dy = vector(a, b)
    return abs(dx * (a[1] - p[1]) - (a[0] - p[0]) * dy) / max(math.hypot(dx, dy), 1e-10)


def rdp(points, epsilon):
    if len(points) <= 2:
        return points
    distances = [line_distance(p, points[0], points[-1]) for p in points[1:-1]]
    if not distances or max(distances) <= epsilon:
        return [points[0], points[-1]]
    index = distances.index(max(distances)) + 1
    return rdp(points[: index + 1], epsilon)[:-1] + rdp(points[index:], epsilon)


def intersection(a, b, c, d):
    u = vector(a, b)
    v = vector(c, d)
    den = u[0] * v[1] - u[1] * v[0]
    if abs(den) < 1e-8:
        return None
    w = vector(a, c)
    t = (w[0] * v[1] - w[1] * v[0]) / den
    return (a[0] + t * u[0], a[1] + t * u[1])


def polygonize(record, epsilon):
    flat = FlattenPen()
    record.replay(flat)
    out = []
    for points in flat.contours:
        start = min(range(len(points)), key=lambda i: points[i])
        points = points[start:] + points[:start]
        far = max(range(len(points)), key=lambda i: math.dist(points[0], points[i]))
        poly = (
            rdp(points[: far + 1], epsilon)[:-1]
            + rdp(points[far:] + points[:1], epsilon)[:-1]
        )
        # Short bevels left by tracing rounded polygon corners become the
        # intersection of the two adjacent intended straight edges, locally.
        for _ in range(len(poly)):
            changed = False
            for i in range(len(poly)):
                a, b, c, d = (
                    poly[i - 1],
                    poly[i],
                    poly[(i + 1) % len(poly)],
                    poly[(i + 2) % len(poly)],
                )
                if math.dist(b, c) > epsilon * 4:
                    continue
                p = intersection(a, b, c, d)
                if p and max(math.dist(p, b), math.dist(p, c)) <= epsilon * 4:
                    poly[i] = p
                    del poly[(i + 1) % len(poly)]
                    changed = True
                    break
            if not changed:
                break
        poly = [tuple(round(v) for v in p) for p in poly]
        out.append(
            [
                ["L", [poly[i], poly[(i + 1) % len(poly)]]]
                for i in range(len(poly))
                if poly[i] != poly[(i + 1) % len(poly)]
            ]
        )
    return to_record(out)


def straighten(record, profile, intent):
    pen = SegmentsPen()
    record.replay(pen)
    result = []
    for edges in pen.contours:
        n = len(edges)
        vertices = [list(e[1][0]) for e in edges]
        constraints = {}
        for dim in (0, 1):
            parents = list(range(n))

            def find(i):
                while parents[i] != i:
                    parents[i] = parents[parents[i]]
                    i = parents[i]
                return i

            for i, (op, pts) in enumerate(edges):
                straight = axis_feature([op, pts], intent)
                if not straight:
                    continue
                dx, dy = vector(pts[0], pts[-1])
                length = math.hypot(dx, dy)
                normal, parallel = (dx, dy) if dim == 0 else (dy, dx)
                explicit = profile["schema"] >= 2 and any(
                    all(r[0] <= p[0] <= r[2] and r[1] <= p[1] <= r[3] for p in pts)
                    for r in intent.get("straight_regions", [])
                )
                if (explicit or length >= profile["min_axis_length"]) and abs(
                    normal
                ) <= abs(parallel) * math.tan(
                    math.radians(profile["axis_angle_degrees"])
                ):
                    parents[find(i)] = find((i + 1) % n)
            groups = defaultdict(list)
            for i in range(n):
                groups[find(i)].append(i)
            for ids in groups.values():
                if len(ids) < 2:
                    continue
                target = round(sum(vertices[i][dim] for i in ids) / len(ids))
                for i in ids:
                    constraints.setdefault(i, {})[dim] = target
        for i, dims in constraints.items():
            for dim, value in dims.items():
                vertices[i][dim] = value
        new = []
        for i, (op, pts) in enumerate(edges):
            a, b = tuple(vertices[i]), tuple(vertices[(i + 1) % n])
            controls = list(pts[1:-1])
            if controls:
                da = vector(pts[0], a)
                db = vector(pts[-1], b)
                if op == "Q":
                    controls = [
                        tuple(
                            c + (da[j] + db[j]) / 2 for j, c in enumerate(controls[0])
                        )
                    ]
                else:
                    controls[0] = tuple(controls[0][j] + da[j] for j in (0, 1))
                    controls[-1] = tuple(controls[-1][j] + db[j] for j in (0, 1))
                if (a[0] == b[0] or a[1] == b[1]) and any(
                    all(r[0] <= p[0] <= r[2] and r[1] <= p[1] <= r[3] for p in pts)
                    for r in intent.get("straight_regions", [])
                ):
                    op = "L"
                    controls = []
            if a != b:
                new.append([op, [a, *controls, b]])
        result.append(new)
    return to_record(result)


def local_tangents(record, intent, profile):
    pen = SegmentsPen()
    record.replay(pen)
    for edges in pen.contours:
        for i, edge in enumerate(edges):
            prev = edges[i - 1]
            p = edge[1][0]
            if edge[0] == "L" and prev[0] == "L":
                continue
            if any(math.dist(p, c) <= 2 for c in intent.get("corners", [])):
                continue
            a, b = tangent(prev, True), tangent(edge)
            if min(math.hypot(*a), math.hypot(*b)) < profile["min_tangent_length"]:
                continue
            degrees = angle(a, b)
            if degrees <= profile["max_tangent_degrees"] or degrees >= 100:
                continue
            if prev[0] == "L":
                direction = a
            elif edge[0] == "L":
                direction = b
            else:
                direction = (
                    a[0] / math.hypot(*a) + b[0] / math.hypot(*b),
                    a[1] / math.hypot(*a) + b[1] / math.hypot(*b),
                )
            size = math.hypot(*direction)
            if not size:
                continue
            u = (direction[0] / size, direction[1] / size)
            for seg, end, old in [(prev, True, a), (edge, False, b)]:
                if seg[0] == "L":
                    continue
                sign = -1 if end else 1
                length = math.hypot(*old)
                candidate = tuple(round(p[j] + sign * u[j] * length) for j in (0, 1))
                index = -2 if end else 1
                if math.dist(candidate, seg[1][index]) <= profile["repair_epsilon"] * 4:
                    seg[1][index] = candidate
    return to_record(pen.contours)


def match_stems(record, intent):
    for rule in intent.get("stems", []):
        if intent["construction"] != "polygon":
            raise FontifyError(
                "automatic stem correction is limited to declared polygonal glyphs"
            )
        intervals = ink_intervals(record, rule["at"])
        if rule["index"] >= len(intervals):
            raise FontifyError("declared stem probe misses the glyph")
        left, right = intervals[rule["index"]]
        if abs((right - left) - rule["width"]) < 1e-6:
            continue
        if rule["anchor"] == "left":
            a, b = left, left + rule["width"]
        else:
            a, b = (
                (left + right - rule["width"]) / 2,
                (left + right + rule["width"]) / 2,
            )
        pen = SegmentsPen()
        record.replay(pen)
        for contour in pen.contours:
            for edge in contour:
                pts = []
                for x, y in edge[1]:
                    if y <= rule.get("below", 1e9):
                        if abs(x - left) < 1e-6:
                            x = a
                        elif abs(x - right) < 1e-6:
                            x = b
                    pts.append((x, y))
                edge[1] = pts
        record = to_record(pen.contours)
    return record


def symmetric(record, axes, advance):
    if not axes:
        return record
    bounds, _, _ = geometry(record)
    x0, y0, x1, y1 = bounds["bounds"]
    ax = round(advance / 2)
    ay = round((y0 + y1) / 2)
    path = pathops.Path()
    record.replay(path.getPen())
    clip = pathops.Path()
    p = clip.getPen()
    p.moveTo((x0 - 100, y0 - 100))
    p.lineTo((ax if "vertical" in axes else x1 + 100, y0 - 100))
    p.lineTo(
        (
            ax if "vertical" in axes else x1 + 100,
            ay if "horizontal" in axes else y1 + 100,
        )
    )
    p.lineTo((x0 - 100, ay if "horizontal" in axes else y1 + 100))
    p.closePath()
    half = pathops.op(path, clip, pathops.PathOp.INTERSECTION)
    master = RecordingPen()
    half.draw(Cu2QuPen(RoundingPen(master), max_err=0.75, reverse_direction=False))
    pen = SegmentsPen()
    master.replay(pen)
    # Decomposing quadratic splines introduces half-unit implied endpoints.
    # Quantize the master BEFORE reflection, so exported integer coordinates
    # remain exact reflections instead of rounding both halves independently.
    pen.contours = [
        [[op, [tuple(round(v) for v in p) for p in pts]] for op, pts in contour]
        for contour in pen.contours
    ]
    transforms = [Transform()]
    if "vertical" in axes:
        transforms += [Transform(-1, 0, 0, 1, 2 * ax, 0)]
    if "horizontal" in axes:
        transforms += [
            t.transform(Transform(1, 0, 0, -1, 0, 2 * ay)) for t in list(transforms)
        ]
    pieces = []
    for tr in transforms:
        for contour in pen.contours:
            for op, pts in contour:
                if op == "L" and (
                    ("vertical" in axes and all(p[0] == ax for p in pts))
                    or ("horizontal" in axes and all(p[1] == ay for p in pts))
                ):
                    continue
                pts = [tr.transformPoint(p) for p in pts]
                if tr.xx * tr.yy - tr.xy * tr.yx < 0:
                    pts = list(reversed(pts))
                if pts[0] != pts[-1]:
                    pieces.append([op, pts])
    # Stitch only matching seam endpoints; never simplify the reflected curves.
    by_start = defaultdict(list)
    for i, (_, pts) in enumerate(pieces):
        by_start[pts[0]].append(i)
    remaining = set(range(len(pieces)))
    contours = []
    while remaining:
        i = min(remaining)
        start = pieces[i][1][0]
        edges = []
        while True:
            if i not in remaining:
                raise FontifyError("ambiguous symmetry seam")
            remaining.remove(i)
            edge = pieces[i]
            edges.append(edge)
            end = edge[1][-1]
            if end == start:
                break
            candidates = [j for j in by_start[end] if j in remaining]
            if len(candidates) != 1:
                raise FontifyError("symmetry seam did not close uniquely")
            i = candidates[0]
        contours.append(edges)
    return to_record(contours)


def check_change(before, record, profile):
    original, _, _ = geometry(before)
    after, _, _ = geometry(record)
    if (after["contours"], after["holes"]) != (original["contours"], original["holes"]):
        raise FontifyError("correction changed contour topology")
    paths = []
    for rec in (before, record):
        flat = FlattenPen()
        rec.replay(flat)
        path = pathops.Path()
        pen = path.getPen()
        for contour in flat.contours:
            pen.moveTo(contour[0])
            for point in contour[1:]:
                pen.lineTo(point)
            pen.closePath()
        paths.append(path)
    p, q = paths
    change = abs(pathops.op(p, q, pathops.PathOp.XOR).area) / max(abs(p.area), 1)
    bounds_change = max(abs(a - b) for a, b in zip(original["bounds"], after["bounds"]))
    if (
        change > profile["max_change_ratio"]
        or bounds_change > profile["max_bounds_change"]
    ):
        raise FontifyError(
            f"correction exceeds design-preservation budget: area={change:.4f}, bounds={bounds_change:.2f}"
        )
    return {"changed_area_ratio": change, "max_bounds_change": bounds_change}


def apply_contour_patch(record, patch):
    """Apply an explicit, fingerprint-bound editorial edit, never an inferred fit."""
    from fontTools.pens.areaPen import AreaPen
    from fontTools.pens.reverseContourPen import ReverseContourPen
    from fontTools.svgLib.path import parse_path

    from .model import keys

    keys(patch, "fingerprint note contours", "contour patch")
    if patch.get("fingerprint") != digest(record.value):
        raise FontifyError("local patch is stale: corrected outline changed")
    if not isinstance(patch.get("note"), str) or not patch["note"].strip():
        raise FontifyError("local patch needs concrete reasons")
    if not isinstance(patch.get("contours"), dict) or not patch["contours"]:
        raise FontifyError("local patch needs named contours")
    pen = SegmentsPen()
    record.replay(pen)
    for index, path in patch["contours"].items():
        if (
            not index.isdigit()
            or int(index) >= len(pen.contours)
            or not isinstance(path, str)
        ):
            raise FontifyError("invalid contour patch")
        replacement = SegmentsPen()
        try:
            parse_path(path, replacement)
        except Exception as e:
            raise FontifyError("invalid local replacement path") from e
        if len(replacement.contours) != 1:
            raise FontifyError(
                "each local patch must replace exactly one closed contour"
            )
        old_area = AreaPen()
        to_record([pen.contours[int(index)]]).replay(old_area)
        new_area = AreaPen()
        to_record(replacement.contours).replay(new_area)
        if old_area.value * new_area.value < 0:
            reversed_record = RecordingPen()
            to_record(replacement.contours).replay(ReverseContourPen(reversed_record))
            replacement = SegmentsPen()
            reversed_record.replay(replacement)
        pen.contours[int(index)] = replacement.contours[0]
    return to_record(pen.contours)


def correction(record, intent, profile, advance, patch=None):
    before = record
    allowed = (
        set(intent["decisions"]["repairs"])
        if profile["schema"] >= 2
        else {"polygonize", "axes", "stems", "tangents", "symmetry", "patches"}
    )
    if profile["schema"] >= 2:
        if not intent["decisions"]["confirmed"]:
            raise FontifyError("resolve glyph intent before correction")
        if patch and "patches" not in allowed:
            raise FontifyError("local patch is not allowed by this glyph's rubric")

    def needed(action, kinds):
        return action in allowed and (
            profile["schema"] == 1
            or any(
                i["kind"] in kinds
                for i in glyph_audit(record, intent, profile)["issues"]
            )
        )

    polygon_edit = intent["construction"] == "polygon" and needed(
        "polygonize", {"unexpected_curve"}
    )
    if polygon_edit:
        record = polygonize(record, profile["repair_epsilon"])
    if polygon_edit:
        rounded = RecordingPen()
        record.replay(RoundingPen(rounded))
        record = rounded
    for _ in range(4):
        start = record.value
        if needed("axes", {"axis_alignment"}):
            record = straighten(record, profile, intent)
        if needed("stems", {"stem_missing", "stem_width"}):
            record = match_stems(record, intent)
        if needed("tangents", {"curve_join", "curve_cusp"}):
            record = local_tangents(record, intent, profile)
        if needed("symmetry", {"symmetry"}):
            record = symmetric(record, intent["symmetry"], advance)
        audit = glyph_audit(record, intent, profile)
        if audit["status"] == "passed":
            break
        if profile["schema"] >= 2 and start == record.value:
            break
    if patch:
        record = apply_contour_patch(record, patch)
        if needed("symmetry", {"symmetry"}):
            record = symmetric(record, intent["symmetry"], advance)
        audit = glyph_audit(record, intent, profile)
    # Compare both at the same 0.2-unit diagnostic subdivision. Mixed-degree
    # coincident Béziers can make a direct cubic/quadratic XOR unreliable.
    changes = check_change(before, record, profile)
    return record, {
        "before": digest(before.value),
        "after": digest(record.value),
        **changes,
        "local_patch": patch,
        "audit": audit,
        **({"allowed_repairs": sorted(allowed)} if profile["schema"] >= 2 else {}),
    }


def repair_project(project_path, output, version, patches=None):
    from fontTools.misc.transform import Transform
    from fontTools.pens.svgPathPen import SVGPathPen
    from fontTools.pens.transformPen import TransformPen

    project = load_project(project_path)
    profile = load_profile(project)
    patch_plan = (
        json.loads(Path(patches).read_text())
        if patches
        else {"schema": 1, "glyphs": {}}
    )
    keys(patch_plan, "schema glyphs", "local patch plan")
    if (
        patch_plan.get("schema") != 1
        or not isinstance(patch_plan.get("glyphs"), dict)
        or set(patch_plan["glyphs"]) - {g["name"] for g in project.glyphs}
    ):
        raise FontifyError("invalid local patch plan")
    if profile is None:
        raise FontifyError("declare a quality profile before corrections")
    require_resolved(profile)
    if project.data.get("approval"):
        raise FontifyError(
            "approved projects are protected; propose corrections in an unapproved candidate copy"
        )
    output = Path(output).resolve()
    if output.exists() or output.is_relative_to(project.root):
        raise FontifyError(
            "correction output must be a new directory outside the source project"
        )
    outlines = compile_project(project)
    data = copy.deepcopy(project.data)
    data["version"] = version
    changes = {}
    corrected = {}
    for o in outlines:
        if not o.record.value:
            continue
        rec = o.record
        try:
            rec, change = correction(
                rec,
                profile["glyphs"][o.spec["name"]],
                profile,
                o.spec["advance"],
                patch_plan["glyphs"].get(o.spec["name"]),
            )
        except FontifyError as e:
            raise FontifyError(f"{o.spec['name']}: {e}") from e
        if profile["schema"] == 1 or rec.value != o.record.value:
            corrected[o.spec["name"]] = rec
        changes[o.spec["name"]] = change
    shutil.copytree(project.root, output)
    for spec in data["glyphs"]:
        if spec["name"] not in corrected:
            continue
        pen = SVGPathPen(None)
        corrected[spec["name"]].replay(
            TransformPen(pen, Transform(1, 0, 0, -1, 0, data["svg_baseline"]))
        )
        path = output / spec["source"]
        path.write_text(
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {spec["advance"]} 1000"><path d="{pen.getCommands()}"/></svg>\n'
        )
        spec.pop("transform", None)
    (output / "fontify.json").write_text(json.dumps(data, indent=2) + "\n")
    (output / "corrections.json").write_text(
        json.dumps(
            {"status": "draft_requires_recheck_and_visual_review", "glyphs": changes},
            indent=2,
        )
        + "\n"
    )
    return output / "fontify.json"
