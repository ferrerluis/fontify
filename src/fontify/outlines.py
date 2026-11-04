"""Restricted SVG ingestion and read-only geometric checks.

Filled path outlines only. No tracing, smoothing, automatic fitting or boolean repair.
"""

import hashlib
import json
import math
import re
from dataclasses import dataclass

import pathops
from defusedxml import ElementTree as ET
from fontTools.misc.transform import Identity, Transform
from fontTools.pens.basePen import BasePen
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.cu2quPen import Cu2QuPen
from fontTools.pens.recordingPen import RecordingPen
from fontTools.pens.reverseContourPen import ReverseContourPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.svgLib.path import parse_path

from .model import FontifyError, local_path


def digest(value):
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


NUM = r"[-+]?(?:\d*\.\d+|\d+\.?\d*)(?:[eE][-+]?\d+)?"


def affine(text):
    result = Identity
    while text.strip():
        m = re.match(r"\s*(matrix|translate|scale|rotate)\s*\(([^)]*)\)\s*,?", text)
        if not m:
            raise FontifyError(
                "unsupported SVG transform; use matrix/translate/scale/rotate"
            )
        args = m[2]
        if re.sub(NUM, "", args).strip(" ,\t\n\r"):
            raise FontifyError("invalid SVG transform numbers")
        v = [float(n) for n in re.findall(NUM, args)]
        if not all(math.isfinite(n) for n in v):
            raise FontifyError("non-finite SVG transform")
        if m[1] == "matrix" and len(v) == 6:
            t = Transform(*v)
        elif m[1] == "translate" and len(v) in (1, 2):
            t = Identity.translate(v[0], v[1] if len(v) == 2 else 0)
        elif m[1] == "scale" and len(v) in (1, 2):
            t = Identity.scale(v[0], v[-1])
        elif m[1] == "rotate" and len(v) in (1, 3):
            t = Identity
            if len(v) == 3:
                t = t.translate(v[1], v[2])
            t = t.rotate(math.radians(v[0]))
            if len(v) == 3:
                t = t.translate(-v[1], -v[2])
        else:
            raise FontifyError("wrong number of SVG transform arguments")
        result = result.transform(t)
        text = text[m.end() :]
    if abs(result.xx * result.yy - result.xy * result.yx) < 1e-10:
        raise FontifyError("singular SVG transform")
    return result


def read_svg(data, transform):
    if len(data) > 2_000_000:
        raise FontifyError("SVG exceeds 2 MB limit")
    try:
        root = ET.fromstring(
            data, forbid_dtd=True, forbid_entities=True, forbid_external=True
        )
    except Exception as e:
        raise FontifyError(f"invalid or unsafe SVG XML: {e}") from e

    def tag(el):
        return el.tag.rsplit("}", 1)[-1]

    if tag(root) != "svg":
        raise FontifyError("expected an SVG root")
    try:
        vb = [float(x) for x in re.split(r"[\s,]+", root.attrib["viewBox"].strip())]
        if len(vb) != 4 or not all(math.isfinite(v) for v in vb) or min(vb[2:]) <= 0:
            raise ValueError()
    except (KeyError, ValueError):
        raise FontifyError(
            "SVG needs a finite, positive-width/height viewBox"
        ) from None
    pen = RecordingPen()
    count = 0

    def walk(el, t, fill="black", rule="nonzero", depth=0):
        nonlocal count
        count += 1
        if depth > 32 or count > 2000:
            raise FontifyError("SVG nesting/element limit exceeded")
        kind = tag(el)
        if kind in ("title", "desc"):
            return
        if kind not in ("svg", "g", "path"):
            raise FontifyError(
                f"unsupported SVG <{kind}>; convert shapes and strokes to filled paths"
            )
        allowed = {
            "id",
            "viewBox",
            "width",
            "height",
            "version",
            "fill",
            "fill-rule",
            "stroke",
            "transform",
            "d",
        }
        unknown = set(el.attrib) - allowed
        if unknown:
            raise FontifyError(
                f"unsupported SVG attributes: {sorted(unknown)}; export plain paths"
            )
        if kind == "svg" and depth:
            raise FontifyError("nested SVG viewports are unsupported")
        fill = el.get("fill", fill)
        rule = el.get("fill-rule", rule)
        if (
            fill.lower() not in ("black", "#000", "#000000", "rgb(0,0,0)")
            or rule != "nonzero"
        ):
            raise FontifyError(
                "use black filled paths with nonzero winding; remove background paths"
            )
        if el.get("stroke", "none") != "none":
            raise FontifyError(
                "strokes must be expanded to filled paths in your vector editor"
            )
        t = t.transform(affine(el.get("transform", "")))
        if kind == "path":
            d = el.get("d", "")
            if re.search(r"[Aa]", d):
                raise FontifyError(
                    "SVG arcs are unsupported; convert arcs to cubic curves explicitly"
                )
            residue = re.sub(NUM, "", d)
            if re.sub(r"[MmLlHhVvCcSsQqTtZz\s,]", "", residue) or not d.strip():
                raise FontifyError("invalid SVG path commands/numbers")
            try:
                parse_path(d, TransformPen(pen, t))
            except (ValueError, IndexError, AssertionError) as e:
                raise FontifyError(f"invalid SVG path: {e}") from e
        for child in el:
            walk(child, t, fill, rule, depth + 1)

    walk(root, transform)
    if len(pen.value) > 10000:
        raise FontifyError("SVG exceeds 10000 segment limit")
    for op, pts in pen.value:
        if op == "endPath":
            raise FontifyError("open contour; close every path with Z")
        for p in pts:
            if p is not None and (
                not all(math.isfinite(v) for v in p) or max(map(abs, p)) > 32760
            ):
                raise FontifyError("outline coordinates outside finite TrueType range")
    if not pen.value:
        raise FontifyError("empty drawing")
    return pen


class FlattenPen(BasePen):
    """Bounded curve subdivision for diagnostics only; never used to compile."""

    def __init__(self):
        super().__init__(None)
        self.contours = []
        self.points = []

    def _moveTo(self, p):
        self.points = [p]

    def _lineTo(self, p):
        self.points.append(p)

    def _closePath(self):
        if self.points and self.points[-1] == self.points[0]:
            self.points.pop()
        self.contours.append(self.points)
        self.points = []

    def _endPath(self):
        raise FontifyError("open contour")

    def _curveToOne(self, p1, p2, p3):
        p0 = self._getCurrentPoint()

        # Convex hull distance to chord bounds the subdivision flatness.
        def split(a, b, c, d, depth=0):
            def dist(p):
                dx, dy = d[0] - a[0], d[1] - a[1]
                return abs(dx * (a[1] - p[1]) - (a[0] - p[0]) * dy) / max(
                    math.hypot(dx, dy), 1e-12
                )

            if max(dist(b), dist(c)) < 0.2 and math.dist(a, d) > 1e-9 or depth >= 14:
                self.points.append(d)
                return

            def mid(x, y):
                return ((x[0] + y[0]) / 2, (x[1] + y[1]) / 2)

            ab, bc, cd = mid(a, b), mid(b, c), mid(c, d)
            abc, bcd = mid(ab, bc), mid(bc, cd)
            m = mid(abc, bcd)
            split(a, ab, abc, m, depth + 1)
            split(m, bcd, cd, d, depth + 1)

        split(p0, p1, p2, p3)

    def _qCurveToOne(self, p1, p2):
        p0 = self._getCurrentPoint()
        c1 = tuple(p0[i] + 2 * (p1[i] - p0[i]) / 3 for i in (0, 1))
        c2 = tuple(p2[i] + 2 * (p1[i] - p2[i]) / 3 for i in (0, 1))
        self._curveToOne(c1, c2, p2)


def cross(a, b, c):
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def intersects(a, b, c, d):
    eps = 1e-8

    def on(p, q, r):
        return (
            abs(cross(p, q, r)) <= eps
            and min(p[0], q[0]) - eps <= r[0] <= max(p[0], q[0]) + eps
            and min(p[1], q[1]) - eps <= r[1] <= max(p[1], q[1]) + eps
        )

    return (
        cross(a, b, c) * cross(a, b, d) < 0 and cross(c, d, a) * cross(c, d, b) < 0
    ) or any((on(a, b, c), on(a, b, d), on(c, d, a), on(c, d, b)))


def inside(p, poly):
    x, y = p
    hit = False
    for a, b in zip(poly, poly[1:] + poly[:1]):
        if (a[1] > y) != (b[1] > y) and x < (b[0] - a[0]) * (y - a[1]) / (
            b[1] - a[1]
        ) + a[0]:
            hit = not hit
    return hit


def geometry(record):
    flat = FlattenPen()
    record.replay(flat)
    contours = flat.contours
    edges = []
    areas = []
    for ci, c in enumerate(contours):
        if len(c) < 3:
            raise FontifyError("degenerate contour: fewer than three points")
        area = sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(c, c[1:] + c[:1])) / 2
        if abs(area) < 0.1:
            raise FontifyError("degenerate contour: zero area")
        areas.append(area)
        for ei, (a, b) in enumerate(zip(c, c[1:] + c[:1])):
            if math.dist(a, b) < 1e-8:
                raise FontifyError("zero-length contour edge")
            edges.append((ci, ei, a, b))
    if len(edges) > 5000:
        raise FontifyError("outline too complex for bounded topology validation")
    # Sweep by x bounds; full segment checks only for overlapping boxes.
    active = []
    for edge in sorted(edges, key=lambda e: min(e[2][0], e[3][0])):
        ci, ei, a, b = edge
        minx = min(a[0], b[0])
        active = [e for e in active if max(e[2][0], e[3][0]) >= minx]
        for cj, ej, c, d in active:
            if ci == cj and (
                abs(ei - ej) == 1 or {ei, ej} == {0, len(contours[ci]) - 1}
            ):
                continue
            if max(min(a[1], b[1]), min(c[1], d[1])) > min(
                max(a[1], b[1]), max(c[1], d[1])
            ):
                continue
            if intersects(a, b, c, d):
                raise FontifyError(
                    "intersecting/touching contours or self-intersection; correct source artwork"
                )
        active.append(edge)
    depths = [
        sum(inside(c[0], other) for j, other in enumerate(contours) if i != j)
        for i, c in enumerate(contours)
    ]
    for i, c in enumerate(contours):
        containers = [
            j for j, other in enumerate(contours) if i != j and inside(c[0], other)
        ]
        if containers:
            parent = min(containers, key=lambda j: abs(areas[j]))
            if areas[parent] * areas[i] > 0:
                raise FontifyError(
                    "nested contours have the same winding: the counter would be filled"
                )
    p = pathops.Path()
    record.replay(p.getPen())
    bounds = BoundsPen(None)
    record.replay(bounds)
    result = {
        "contours": len(contours),
        "holes": sum(d % 2 for d in depths),
        "bounds": list(bounds.bounds),
        "ink_area": round(abs(p.area), 3),
    }
    x0, y0, x1, y1 = bounds.bounds
    for label, t in [
        ("vertical", (-1, 0, 0, 1, x0 + x1, 0)),
        ("horizontal", (1, 0, 0, -1, 0, y0 + y1)),
    ]:
        reflected = p.transform(*t)
        delta = pathops.op(p, reflected, pathops.PathOp.XOR)
        result[f"{label}_asymmetry"] = round(abs(delta.area) / max(abs(p.area), 1), 6)
    result["ink_fraction"] = round(abs(p.area) / max((x1 - x0) * (y1 - y0), 1), 6)
    return result, depths, areas


def orient(record, depths, areas):
    out = RecordingPen()
    contour = RecordingPen()
    i = 0
    for op, pts in record.value:
        getattr(contour, op)(*pts)
        if op == "closePath":
            # TrueType: clockwise exterior and counterclockwise hole in y-up space.
            target = (
                out
                if (areas[i] < 0) == (depths[i] % 2 == 0)
                else ReverseContourPen(out)
            )
            contour.replay(target)
            contour = RecordingPen()
            i += 1
    return out


@dataclass
class Outline:
    spec: dict
    record: RecordingPen
    glyph: object
    diagnostics: dict
    source_hash: str | None
    normalized_hash: str
    compiled_hash: str


def compile_outline(project, spec):
    d = project.data
    source_hash = None
    record = RecordingPen()
    diagnostics = {"contours": 0, "holes": 0, "bounds": None, "ink_area": 0}
    if spec.get("source") is not None:
        path = local_path(project.root, spec["source"])
        try:
            data = path.read_bytes()
        except OSError as e:
            raise FontifyError(f"{spec['name']}: {e}") from e
        source_hash = hashlib.sha256(data).hexdigest()
        t = Transform(*spec.get("transform", [1, 0, 0, 1, 0, 0])).transform(
            Transform(1, 0, 0, -1, 0, d["svg_baseline"])
        )
        record = read_svg(data, t)
        diagnostics, depths, areas = geometry(record)
        record = orient(record, depths, areas)
    normal_hash = digest(record.value)
    pen = TTGlyphPen(None)
    record.replay(Cu2QuPen(pen, max_err=d["curve_error"], reverse_direction=False))
    glyph = pen.glyph()
    compiled = RecordingPen()
    glyph.draw(compiled, None)
    if spec.get("source") is not None:
        # Rounding/curve conversion may expose defects in otherwise valid source.
        compiled_diag, _, _ = geometry(compiled)
        if (
            compiled_diag["contours"] != diagnostics["contours"]
            or compiled_diag["holes"] != diagnostics["holes"]
        ):
            raise FontifyError(
                f"{spec['name']}: topology changed during TrueType conversion"
            )
        x0, y0, x1, y1 = compiled_diag["bounds"]
        if y0 < d["descender"] or y1 > d["ascender"]:
            raise FontifyError(
                f"{spec['name']}: ink exceeds ascender/descender; fix metrics or explicit placement"
            )
        diagnostics["compiled_bounds"] = compiled_diag["bounds"]
        diagnostics["left_bearing"] = x0
        diagnostics["right_bearing"] = spec["advance"] - x1
        diagnostics["warnings"] = []
        if x0 < 0 or x1 > spec["advance"]:
            diagnostics["warnings"].append("ink overhangs advance; review spacing")
    return Outline(
        spec,
        record,
        glyph,
        diagnostics,
        source_hash,
        normal_hash,
        digest(compiled.value),
    )


def compile_project(project):
    result = []
    for spec in project.glyphs:
        try:
            result.append(compile_outline(project, spec))
        except (FontifyError, pathops.PathOpsError) as e:
            raise FontifyError(f"{spec['name']}: {e}") from e
    return result
