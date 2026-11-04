"""Design-intent checks for source and compiled glyphs, plus a review gate.

These checks do not infer typography from Unicode. A profile states the intended
symmetries/construction; an agent reviews every glyph before a release is exposed.
"""

import hashlib
import json
import math
from pathlib import Path

from fontTools.pens.basePen import BasePen
from fontTools.pens.recordingPen import RecordingPen
from fontTools.ttLib import TTFont

from .model import FontifyError, keys, local_path
from .outlines import FlattenPen, digest, geometry


class SegmentsPen(BasePen):
    def __init__(self):
        super().__init__(None)
        self.contours = []
        self.current = []
        self.start = None

    def _moveTo(self, p):
        self.start = p
        self.current = []

    def _lineTo(self, p):
        a = self._getCurrentPoint()
        if a != p:
            self.current.append(["L", [a, p]])

    def _qCurveToOne(self, c, p):
        self.current.append(["Q", [self._getCurrentPoint(), c, p]])

    def _curveToOne(self, c1, c2, p):
        self.current.append(["C", [self._getCurrentPoint(), c1, c2, p]])

    def _closePath(self):
        if self._getCurrentPoint() != self.start:
            self.current.append(["L", [self._getCurrentPoint(), self.start]])
        if self.current:
            self.contours.append(self.current)
        self.current = []

    def _endPath(self):
        raise FontifyError("quality audit requires closed contours")


def to_record(contours):
    p = RecordingPen()
    for edges in contours:
        if not edges:
            continue
        p.moveTo(edges[0][1][0])
        for op, pts in edges:
            getattr(p, {"L": "lineTo", "Q": "qCurveTo", "C": "curveTo"}[op])(*pts[1:])
        p.closePath()
    return p


def angle(a, b):
    den = math.hypot(*a) * math.hypot(*b)
    if den < 1e-10:
        return 0
    return math.degrees(math.acos(max(-1, min(1, (a[0] * b[0] + a[1] * b[1]) / den))))


def vector(a, b):
    return (b[0] - a[0], b[1] - a[1])


def tangent(edge, end=False):
    pts = edge[1]
    anchor = pts[-1] if end else pts[0]
    candidates = reversed(pts[:-1]) if end else pts[1:]
    for p in candidates:
        v = vector(p, anchor) if end else vector(anchor, p)
        if math.hypot(*v) > 1e-9:
            return v
    return (0, 0)


def curve_has_cusp(edge):
    """Detect a stationary interior tangent reversal, not a wide smooth bend."""
    op, points = edge
    if op == "L":
        return False
    coefficients = []
    for j in (0, 1):
        p = [v[j] for v in points]
        if op == "Q":
            coefficients.append((0, p[2] - 2 * p[1] + p[0], p[1] - p[0]))
        else:
            coefficients.append(
                (
                    -p[0] + 3 * p[1] - 3 * p[2] + p[3],
                    2 * (p[0] - 2 * p[1] + p[2]),
                    p[1] - p[0],
                )
            )
    scale = max(1, max(abs(v) for c in coefficients for v in c))
    eps = scale * 1e-9
    a, b, c = max(coefficients, key=lambda c: max(abs(v) for v in c))
    if abs(a) < eps:
        roots = [] if abs(b) < eps else [-c / b]
    else:
        discriminant = b * b - 4 * a * c
        roots = (
            []
            if discriminant < 0
            else [
                (-b + math.sqrt(discriminant)) / (2 * a),
                (-b - math.sqrt(discriminant)) / (2 * a),
            ]
        )

    def derivative(t):
        return tuple((a * t + b) * t + c for a, b, c in coefficients)

    for t in roots:
        if 1e-6 < t < 1 - 1e-6 and math.hypot(*derivative(t)) < eps:
            delta = min(1e-4, t / 2, (1 - t) / 2)
            if angle(derivative(t - delta), derivative(t + delta)) > 150:
                return True
    return False


def axis_feature(edge, intent):
    """Handwritten glyphs can require declared regions instead of axis guesses."""
    op, points = edge
    declared = any(
        all(r[0] <= p[0] <= r[2] and r[1] <= p[1] <= r[3] for p in points)
        for r in intent.get("straight_regions", [])
    )
    return declared or (
        intent.get("axis_policy", "near_axis") == "near_axis"
        and (op == "L" or intent["construction"] == "polygon")
    )


def load_profile(project):
    if not project.data.get("quality"):
        return None
    path = local_path(project.root, project.data["quality"])
    try:
        d = json.loads(path.read_text())
    except (ValueError, OSError) as e:
        raise FontifyError(f"cannot read quality profile: {e}") from e
    keys(
        d,
        "schema glyphs symmetry_tolerance axis_angle_degrees min_axis_length max_tangent_degrees min_join_length min_tangent_length max_change_ratio max_bounds_change repair_epsilon review",
        "quality profile",
    )
    if d.get("schema") != 1 or not isinstance(d.get("glyphs"), dict):
        raise FontifyError("invalid quality profile")
    if set(d["glyphs"]) != {g["name"] for g in project.glyphs}:
        raise FontifyError("quality profile must explicitly cover every mapped glyph")
    for name, g in d["glyphs"].items():
        keys(
            g,
            "construction symmetry corners straight_regions stems note axis_policy",
            "glyph quality intent",
        )
        if g.get("construction") not in ("polygon", "curved", "blank"):
            raise FontifyError(f"{name}: declare polygon, curved or blank construction")
        if g.get("axis_policy", "near_axis") not in ("near_axis", "declared"):
            raise FontifyError(f"{name}: axis_policy must be near_axis or declared")
        if (
            not isinstance(g.get("symmetry"), list)
            or not all(isinstance(s, str) for s in g["symmetry"])
            or set(g["symmetry"]) - {"vertical", "horizontal"}
        ):
            raise FontifyError(f"{name}: invalid symmetry intent")
        if not isinstance(g.get("note"), str) or not g["note"]:
            raise FontifyError(f"{name}: quality intent needs a rationale")
        if (g["construction"] == "blank") != (
            next(s for s in project.glyphs if s["name"] == name).get("source") is None
        ):
            raise FontifyError(
                f"{name}: blank construction must match the actual blank glyph"
            )
        for field in ("corners", "straight_regions", "stems"):
            if field in g and not isinstance(g[field], list):
                raise FontifyError(f"{name}: {field} must be a list")
        for p in g.get("corners", []):
            if (
                not isinstance(p, list)
                or len(p) != 2
                or any(
                    not isinstance(v, (int, float))
                    or isinstance(v, bool)
                    or not math.isfinite(v)
                    for v in p
                )
            ):
                raise FontifyError(
                    "intentional curve corners must be named finite points"
                )
        for r in g.get("straight_regions", []):
            if (
                not isinstance(r, list)
                or len(r) != 4
                or any(
                    not isinstance(v, (int, float))
                    or isinstance(v, bool)
                    or not math.isfinite(v)
                    for v in r
                )
                or r[0] >= r[2]
                or r[1] >= r[3]
            ):
                raise FontifyError("straight regions must be finite bounding boxes")
        for r in g.get("stems", []):
            keys(r, "at index width anchor below", "stem rule")
            if (
                r.get("anchor") not in ("left", "center")
                or not isinstance(r.get("index"), int)
                or isinstance(r.get("index"), bool)
                or r["index"] < 0
            ):
                raise FontifyError("invalid explicit stem rule")
            for field in ("at", "width", "below"):
                if field not in r and field == "below":
                    continue
                v = r.get(field)
                if (
                    not isinstance(v, (int, float))
                    or isinstance(v, bool)
                    or not math.isfinite(v)
                ):
                    raise FontifyError("stem rule values must be finite numbers")
            if r["width"] <= 0:
                raise FontifyError("stem width must be positive")
    for key, default in [
        ("symmetry_tolerance", 1e-6),
        ("axis_angle_degrees", 3),
        ("min_axis_length", 30),
        ("max_tangent_degrees", 7),
        ("min_join_length", 3),
        ("min_tangent_length", 12),
        ("max_change_ratio", 0.12),
        ("max_bounds_change", 6),
        ("repair_epsilon", 4),
    ]:
        d.setdefault(key, default)
        if (
            not isinstance(d[key], (int, float))
            or isinstance(d[key], bool)
            or not math.isfinite(d[key])
            or d[key] < 0
        ):
            raise FontifyError(f"invalid quality limit: {key}")
    upm = project.data["units_per_em"]
    for key, limit in [
        ("symmetry_tolerance", 0.001),
        ("axis_angle_degrees", 5),
        ("min_axis_length", upm / 10),
        ("max_tangent_degrees", 15),
        ("min_join_length", upm / 50),
        ("min_tangent_length", upm / 30),
        ("max_change_ratio", 0.15),
        ("max_bounds_change", upm / 50),
        ("repair_epsilon", upm / 100),
    ]:
        if d[key] > limit:
            raise FontifyError(
                f"{key} exceeds the preflight limit; change design intent explicitly instead of disabling checks"
            )
    if not d.get("review"):
        raise FontifyError("quality profile requires an agent review receipt path")
    local_path(project.root, d["review"])
    return d


def ink_intervals(record, y):
    flat = FlattenPen()
    record.replay(flat)
    xs = []
    for contour in flat.contours:
        for a, b in zip(contour, contour[1:] + contour[:1]):
            if (a[1] > y) != (b[1] > y):
                xs.append(a[0] + (y - a[1]) * (b[0] - a[0]) / (b[1] - a[1]))
    xs.sort()
    return [(xs[i], xs[i + 1]) for i in range(0, len(xs) - 1, 2)]


def glyph_audit(record, intent, profile):
    if not record.value:
        return {
            "status": "passed" if intent["construction"] == "blank" else "failed",
            "issues": []
            if intent["construction"] == "blank"
            else [{"kind": "unexpected_blank"}],
            "fingerprint": digest(record.value),
            "curves_checked": 0,
            "joins_checked": 0,
            "axis_edges_checked": 0,
        }
    diag, _, _ = geometry(record)
    pen = SegmentsPen()
    record.replay(pen)
    issues = []
    curves = joins = axes = 0
    for symmetry in intent["symmetry"]:
        value = diag[symmetry + "_asymmetry"]
        if value > profile["symmetry_tolerance"]:
            issues.append({"kind": "symmetry", "axis": symmetry, "ratio": value})
    stem_measurements = []
    for rule in intent.get("stems", []):
        intervals = ink_intervals(record, rule["at"])
        if rule["index"] >= len(intervals):
            issues.append({"kind": "stem_missing", "rule": rule})
            continue
        a, b = intervals[rule["index"]]
        width = b - a
        stem_measurements.append(
            {"at": rule["at"], "width": width, "target": rule["width"]}
        )
        if abs(width - rule["width"]) > 1e-6:
            issues.append(
                {
                    "kind": "stem_width",
                    "at": rule["at"],
                    "actual": width,
                    "target": rule["width"],
                }
            )
    for ci, edges in enumerate(pen.contours):
        for i, edge in enumerate(edges):
            op, pts = edge
            dx, dy = vector(pts[0], pts[-1])
            length = math.hypot(dx, dy)
            if op != "L":
                curves += 1
                if intent["construction"] == "polygon":
                    issues.append(
                        {"kind": "unexpected_curve", "contour": ci, "segment": i}
                    )
                if curve_has_cusp(edge):
                    issues.append({"kind": "curve_cusp", "contour": ci, "segment": i})
            straight_intent = axis_feature(edge, intent)
            if straight_intent and length >= profile["min_axis_length"]:
                axis = "horizontal" if abs(dy) <= abs(dx) else "vertical"
                deviation = math.degrees(
                    math.atan2(min(abs(dx), abs(dy)), max(abs(dx), abs(dy)))
                )
                if deviation <= profile["axis_angle_degrees"]:
                    axes += 1
                    normal = 1 if axis == "horizontal" else 0
                    spread = max(p[normal] for p in pts) - min(p[normal] for p in pts)
                    if spread > 1e-7:
                        issues.append(
                            {
                                "kind": "axis_alignment",
                                "axis": axis,
                                "contour": ci,
                                "segment": i,
                                "degrees": round(deviation, 6),
                                "spread": round(spread, 6),
                            }
                        )
            previous = edges[i - 1]
            if op == "L" and previous[0] == "L":
                continue
            joins += 1
            if (
                min(math.dist(previous[1][0], previous[1][-1]), length)
                < profile["min_join_length"]
            ):
                continue
            if (
                min(math.hypot(*tangent(previous, True)), math.hypot(*tangent(edge)))
                < profile["min_tangent_length"]
            ):
                continue
            degrees = angle(tangent(previous, True), tangent(edge))
            if degrees > profile["max_tangent_degrees"]:
                p = pts[0]
                if not any(
                    math.dist(p, corner) <= 2 for corner in intent.get("corners", [])
                ):
                    issues.append(
                        {
                            "kind": "curve_cusp" if degrees >= 170 else "curve_join",
                            "contour": ci,
                            "segment": i,
                            "point": list(p),
                            "degrees": round(degrees, 4),
                        }
                    )
    return {
        "status": "failed" if issues else "passed",
        "issues": issues,
        "fingerprint": digest(record.value),
        "curves_checked": curves,
        "joins_checked": joins,
        "axis_edges_checked": axes,
        "symmetry": {s: diag[s + "_asymmetry"] for s in intent["symmetry"]},
        "bounds": diag["bounds"],
        "ink_fraction": diag["ink_fraction"],
        "stems": stem_measurements,
        "intent": intent["note"],
    }


def audit_project(project, outlines, font_path=None):
    profile = load_profile(project)
    if profile is None:
        return {"status": "not_configured", "glyphs": {}, "review": "not_configured"}
    glyphs = {}
    font = TTFont(font_path) if font_path else None
    gs = font.getGlyphSet() if font else None
    try:
        for o in outlines:
            name = o.spec["name"]
            record = RecordingPen()
            if gs:
                gs[name].draw(record)
            else:
                record = o.record
            glyphs[name] = glyph_audit(record, profile["glyphs"][name], profile)
    finally:
        if font:
            font.close()
    return {
        "status": "failed"
        if any(g["status"] == "failed" for g in glyphs.values())
        else "passed",
        "stage": "compiled" if font_path else "source",
        "profile_sha256": digest(profile),
        "glyphs": glyphs,
        "font_sha256": hashlib.sha256(Path(font_path).read_bytes()).hexdigest()
        if font_path
        else None,
        "limitations": "Numeric geometry checks cannot establish optical quality; per-glyph agent visual review is separately required.",
    }


REVIEW_CHECKS = {
    "symmetry",
    "axes",
    "curves",
    "optical_weight",
    "spacing",
    "source_preservation",
}


def check_review(project, report):
    profile = load_profile(project)
    if profile is None:
        return {"status": "not_configured"}
    path = local_path(project.root, profile["review"])
    try:
        receipt = json.loads(path.read_text())
    except (OSError, ValueError) as e:
        raise FontifyError(
            "agent visual review is missing; build a draft and review every glyph before release"
        ) from e
    keys(
        receipt,
        "schema reviewer project_sha256 font_sha256 profile_sha256 glyphs evidence human_approval",
        "agent review receipt",
    )
    if (
        receipt.get("schema") != 1
        or report.get("stage") != "compiled"
        or not report.get("font_sha256")
    ):
        raise FontifyError(
            "agent review requires a schema-1 receipt and an actual compiled-font audit"
        )
    if receipt.get("profile_sha256") != report["profile_sha256"]:
        raise FontifyError("agent visual review is stale: quality intent changed")
    if receipt.get("project_sha256") != digest(project.data) or receipt.get(
        "font_sha256"
    ) != report.get("font_sha256"):
        raise FontifyError(
            "agent visual review is stale: project, spacing or font changed"
        )
    if (
        not isinstance(receipt.get("reviewer"), str)
        or not receipt["reviewer"].strip()
        or not isinstance(receipt.get("glyphs"), dict)
    ):
        raise FontifyError("invalid agent visual review receipt")
    evidence = receipt.get("evidence", [])
    if not isinstance(evidence, list) or not evidence:
        raise FontifyError("agent review needs saved visual evidence")
    evidence_paths = set()
    for item in evidence:
        keys(item, "path sha256", "review evidence")
        p = local_path(project.root, item.get("path"))
        if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest() != item.get(
            "sha256"
        ):
            raise FontifyError("agent review evidence is missing or stale")
        evidence_paths.add(item["path"])
    if set(receipt["glyphs"]) != set(report["glyphs"]):
        raise FontifyError("agent review must cover every glyph")
    for name, g in report["glyphs"].items():
        review = receipt["glyphs"][name]
        if not isinstance(review, dict):
            raise FontifyError(f"{name}: invalid glyph review")
        if review.get("fingerprint") != g["fingerprint"]:
            raise FontifyError(f"agent visual review is stale: {name} changed")
        if (
            not isinstance(review.get("checks"), dict)
            or set(review.get("checks", {})) != REVIEW_CHECKS
            or any(v != "passed" for v in review["checks"].values())
        ):
            raise FontifyError(f"{name}: agent review has unresolved checks")
        if not isinstance(review.get("notes"), str) or not review["notes"].strip():
            raise FontifyError(f"{name}: agent review needs concrete findings")
        refs = review.get("evidence")
        if (
            not isinstance(refs, list)
            or not refs
            or not all(isinstance(p, str) and p in evidence_paths for p in refs)
        ):
            raise FontifyError(f"{name}: agent review needs linked visual evidence")
    return {
        "status": "passed",
        "reviewer": receipt["reviewer"],
        "reviewed_glyphs": len(report["glyphs"]),
        "human_approval": "not_implied",
    }
