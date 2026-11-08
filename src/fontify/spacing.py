"""Reviewable vector-only optical spacing, separate from font compilation.

Exterior white profiles are integrated over vector segments, never over pixels.
The optical estimate is not an approval: proposals need actual-font review.
"""

import copy
import hashlib
import json
import math
import re
import shutil
import unicodedata
from pathlib import Path

import pathops
from fontTools.pens.recordingPen import RecordingPen

from .model import FontifyError, Project, codepoint, keys, load_project, number
from .outlines import FlattenPen, compile_outline, compile_project, digest

ALGORITHM = "fontify-exterior-white-v1"
GROUPS = ("caps", "lowercase", "digits", "punctuation")
MAX_PAIR_CHECKS = 20_000


def _json(value, label):
    if isinstance(value, (str, Path)):
        try:
            return json.loads(Path(value).read_text())
        except (OSError, ValueError) as exc:
            raise FontifyError(f"cannot read {label}: {exc}") from exc
    return copy.deepcopy(value)


def _group(spec):
    ch = chr(codepoint(spec["unicode"]))
    if ch.isupper():
        return "caps"
    if ch.islower():
        return "lowercase"
    if unicodedata.category(ch) == "Nd":
        return "digits"
    return "punctuation"


def spacing_config(project, config=None):
    """Validate and resolve optional settings; all distances are font units."""
    raw = {} if config is None else _json(config, "spacing config")
    keys(
        raw,
        "schema groups glyph_groups glyph_overrides pair_overrides pairs "
        "kerning_threshold max_kerning collision_gap preserve_existing",
        "spacing config",
    )
    if isinstance(raw.get("schema", 1), bool) or raw.get("schema", 1) != 1:
        raise FontifyError("spacing config schema must be 1")
    upm = project.data["units_per_em"]
    d = {
        "schema": 1,
        "groups": {},
        "glyph_groups": {},
        "glyph_overrides": {},
        "pair_overrides": [],
        "pairs": None,
        "kerning_threshold": 10,
        "max_kerning": round(upm / 5),
        "collision_gap": round(upm / 100),
        "preserve_existing": True,
    }
    for k in d.keys() - {"groups"}:
        if k in raw:
            d[k] = raw[k]
    for k in ("kerning_threshold", "max_kerning", "collision_gap"):
        d[k] = number(d[k], k, 0, 32767, integer=True)
    if not isinstance(d["preserve_existing"], bool):
        raise FontifyError("preserve_existing must be boolean")
    supplied = raw.get("groups", {})
    keys(supplied, " ".join(GROUPS), "spacing groups")
    for group in GROUPS:
        height = project.data["x_height" if group == "lowercase" else "cap_height"]
        settings = {
            "zone": [
                project.data["descender"] if group == "punctuation" else 0,
                height,
            ],
            "overshoot": round(upm / 50),
            "counter_depth": round(upm / 5),
            "side_space": round(upm / 16),
            "min_bearing": 0,
            "max_bearing": round(upm / 4),
        }
        keys(supplied.get(group, {}), " ".join(settings), f"{group} spacing")
        settings.update(supplied.get(group, {}))
        zone = settings["zone"]
        if not isinstance(zone, list) or len(zone) != 2:
            raise FontifyError(f"{group}.zone must be [bottom, top]")
        for v in zone:
            number(v, f"{group}.zone")
        if zone[0] >= zone[1]:
            raise FontifyError(f"{group}.zone must have positive height")
        for k in ("overshoot", "counter_depth", "side_space"):
            number(settings[k], f"{group}.{k}", 0, upm)
        for k in ("min_bearing", "max_bearing"):
            number(settings[k], f"{group}.{k}", -32768, 32767, integer=True)
        if settings["min_bearing"] > settings["max_bearing"]:
            raise FontifyError(f"{group}: min_bearing exceeds max_bearing")
        d["groups"][group] = settings
    names = {g["name"] for g in project.glyphs}
    for k in ("glyph_groups", "glyph_overrides"):
        if not isinstance(d[k], dict) or set(d[k]) - names:
            raise FontifyError(f"{k} must name known glyphs")
    if any(g not in GROUPS for g in d["glyph_groups"].values()):
        raise FontifyError("glyph_groups must select caps/lowercase/digits/punctuation")
    for name, rule in d["glyph_overrides"].items():
        keys(
            rule,
            "left_bearing right_bearing advance reason",
            f"{name} spacing override",
        )
        if not isinstance(rule.get("reason"), str) or not rule["reason"].strip():
            raise FontifyError("glyph override needs a review reason")
        if not set(rule) - {"reason"}:
            raise FontifyError("glyph override needs a bearing or advance")
        if "advance" in rule and "right_bearing" in rule:
            raise FontifyError(
                "glyph override cannot specify both advance and right_bearing"
            )
        for k, v in rule.items():
            if k != "reason":
                number(
                    v,
                    f"{name}.{k}",
                    1 if k == "advance" else -32768,
                    32767,
                    integer=True,
                )
    for field in ("pairs", "pair_overrides"):
        if d[field] is None and field == "pairs":
            continue
        if not isinstance(d[field], list):
            raise FontifyError(f"{field} must be a list")
        seen = set()
        for pair in d[field]:
            allowed = (
                "left right value reason" if field == "pair_overrides" else "left right"
            )
            keys(pair, allowed, field)
            if (
                not isinstance(pair.get("left"), str)
                or not isinstance(pair.get("right"), str)
                or pair["left"] not in names
                or pair["right"] not in names
            ):
                raise FontifyError(f"{field} references unknown glyphs")
            key = (pair["left"], pair["right"])
            if key in seen:
                raise FontifyError(f"duplicate {field} pair: {key}")
            seen.add(key)
            if field == "pair_overrides":
                number(
                    pair.get("value"),
                    "pair override value",
                    -32768,
                    32767,
                    integer=True,
                )
                if (
                    not isinstance(pair.get("reason"), str)
                    or not pair["reason"].strip()
                ):
                    raise FontifyError("pair override needs a review reason")
    return d


def _edges(record):
    flat = FlattenPen()
    record.replay(flat)
    return [(a, b) for c in flat.contours for a, b in zip(c, c[1:] + c[:1])]


def _x(edge, y):
    a, b = edge
    return a[0] + (y - a[1]) * (b[0] - a[0]) / (b[1] - a[1])


def _envelope(edges, bottom, top):
    """Piecewise-linear exterior silhouette, split at vector vertices."""
    ys = sorted({bottom, top} | {p[1] for e in edges for p in e if bottom < p[1] < top})
    rows = []
    for lo, hi in zip(ys, ys[1:]):
        mid = (lo + hi) / 2
        active = [
            e for e in edges if min(e[0][1], e[1][1]) < mid < max(e[0][1], e[1][1])
        ]
        if active:
            left = min(active, key=lambda e: _x(e, mid))
            right = max(active, key=lambda e: _x(e, mid))
            rows.append((lo, hi, left, right))
    return rows


def _capped_area(a, b, height, cap):
    """Integral of a linear depth, clipped to [0, cap]."""
    breaks = [0, 1]
    if a != b:
        breaks += [t for v in (0, cap) if 0 < (t := (v - a) / (b - a)) < 1]
    area = 0
    for start, end in zip(sorted(breaks), sorted(breaks)[1:]):
        values = [max(0, min(cap, a + t * (b - a))) for t in (start, end)]
        area += sum(values) * (end - start) * height / 2
    return area


def _measure(outline, settings):
    x0, y0, x1, y1 = outline.diagnostics["bounds"]
    lo = max(y0, settings["zone"][0] - settings["overshoot"])
    hi = min(y1, settings["zone"][1] + settings["overshoot"])
    rows = _envelope(_edges(outline.record), lo, hi) if hi > lo else []
    areas = [0.0, 0.0]
    raw = [0.0, 0.0]
    height = 0.0
    for bottom, top, left, right in rows:
        h = top - bottom
        height += h
        for i, values in enumerate(
            (
                [_x(left, y) - x0 for y in (bottom, top)],
                [x1 - _x(right, y) for y in (bottom, top)],
            )
        ):
            areas[i] += _capped_area(*values, h, settings["counter_depth"])
            raw[i] += sum(values) * h / 2
    return {
        "zone": settings["zone"],
        "overshoot": settings["overshoot"],
        "measured_zone": [lo, hi] if hi > lo else None,
        "active_height": round(height, 6),
        "counter_depth": settings["counter_depth"],
        "white_area": {k: round(areas[i], 6) for i, k in enumerate(("left", "right"))},
        "uncapped_white_area": {
            k: round(raw[i], 6) for i, k in enumerate(("left", "right"))
        },
        "mean_white_depth": {
            k: areas[i] / height if height else None
            for i, k in enumerate(("left", "right"))
        },
        "method": "continuous exterior silhouette integral; vector subdivision at 0.2 units",
    }


def _path(record):
    path = pathops.Path()
    record.replay(path.getPen())
    return path


def _pair_gap(left, right, offset, bottom, top):
    """Integrate the common-height external gap and find its minimum."""
    lrows, rrows = left, right
    i = j = 0
    area = height = 0.0
    minimum = None
    while i < len(lrows) and j < len(rrows):
        a, b = lrows[i], rrows[j]
        lo, hi = max(a[0], b[0], bottom), min(a[1], b[1], top)
        if lo < hi:
            gaps = [offset + _x(b[2], y) - _x(a[3], y) for y in (lo, hi)]
            area += sum(gaps) * (hi - lo) / 2
            height += hi - lo
            minimum = min(gaps + ([] if minimum is None else [minimum]))
        if a[1] <= b[1]:
            i += 1
        if b[1] <= a[1]:
            j += 1
    return (area / height if height else None), minimum, height


def _guard(left, right, offset, requested, gap, approximate_minimum):
    """Verify actual compiled vector clearance, including outside optical zones."""
    value = (
        max(requested, math.ceil(gap - approximate_minimum))
        if approximate_minimum is not None
        else requested
    )
    expanded = left["expanded"]
    other = right["path"]

    def safe(kern):
        moved = other.transform(1, 0, 0, 1, offset + kern, 0)
        return (
            abs(pathops.op(expanded, moved, pathops.PathOp.INTERSECTION).area) <= 1e-9
        )

    if not safe(value):
        unsafe = value
        step = 1
        # At disjoint bounds this is guaranteed safe, without assuming that
        # intersections are monotone for nested shapes or disconnected contours.
        end = math.ceil(expanded.bounds[2] - other.bounds[0] - offset) + 1
        while value < end:
            value = min(end, value + step)
            if safe(value):
                break
            unsafe = value
            step *= 2
        if not safe(value):
            raise FontifyError("could not establish vector collision clearance")
        while value - unsafe > 1:
            mid = (value + unsafe) // 2
            if safe(mid):
                value = mid
            else:
                unsafe = mid
    number(value, "collision-safe kerning", -32768, 32767, integer=True)
    return value


def spacing_plan(project_path, config=None):
    """Return a deterministic proposal. This never changes a project or SVG."""
    project = load_project(project_path)
    config = spacing_config(project, config)
    drawing_count = sum(g.get("source") is not None for g in project.glyphs)
    if drawing_count * drawing_count > MAX_PAIR_CHECKS:
        raise FontifyError(
            f"spacing supports at most {MAX_PAIR_CHECKS:,} drawn-glyph pairs; "
            "this project exceeds the bounded collision-check scope. Use a smaller "
            "explicit candidate character set or manual spacing for a larger font. "
            "An optical pairs filter does not disable collision checks."
        )
    outlines = compile_project(project)
    glyphs, prepared = {}, {}
    for outline in outlines:
        spec = outline.spec
        name = spec["name"]
        group = config["glyph_groups"].get(name, _group(spec))
        settings = config["groups"][group]
        report = {
            "group": group,
            "source_sha256": outline.source_hash,
            "normalized_sha256": outline.normalized_hash,
            "compiled_sha256": outline.compiled_hash,
            "reasons": [],
        }
        glyphs[name] = report
        override = config["glyph_overrides"].get(name, {})
        if not outline.record.value:
            if set(override) - {"advance", "reason"}:
                raise FontifyError("blank glyph overrides may only change advance")
            report.update(
                measurement=None,
                current={"advance": spec["advance"]},
                proposed={
                    "advance": override.get("advance", spec["advance"]),
                    "translate_x": 0,
                },
            )
            report["reasons"].append(
                "blank advance preserved"
                if not override
                else "explicit blank advance override: " + override["reason"]
            )
            continue
        measurement = _measure(outline, settings)
        report["measurement"] = measurement
        bounds = outline.diagnostics["compiled_bounds"]
        current = {
            "left_bearing": bounds[0],
            "right_bearing": spec["advance"] - bounds[2],
            "advance": spec["advance"],
        }
        report["current"] = current
        if measurement["active_height"]:
            bearings = {}
            for side in ("left", "right"):
                estimated = round(
                    settings["side_space"] - measurement["mean_white_depth"][side]
                )
                bearings[side + "_bearing"] = max(
                    settings["min_bearing"], min(settings["max_bearing"], estimated)
                )
                if bearings[side + "_bearing"] != estimated:
                    report["reasons"].append(f"{side} bearing limited by group bounds")
            report["reasons"].append(
                "equalize bounded exterior white area within the group zone"
            )
        else:
            bearings = {k: current[k] for k in ("left_bearing", "right_bearing")}
            report["reasons"].append("no ink in reference zone; preserve bearings")
        for k in ("left_bearing", "right_bearing"):
            if k in override:
                bearings[k] = override[k]
        # Tight Bézier extrema can be fractional. Use only integer translation
        # (preserving the compiled outline), and quantize the advance once.
        shift = round(bearings["left_bearing"] - bounds[0])
        if "left_bearing" not in override and measurement["active_height"]:
            low = math.ceil(settings["min_bearing"] - bounds[0])
            high = math.floor(settings["max_bearing"] - bounds[0])
            if low > high:
                raise FontifyError(
                    f"{name}: bearing bounds cannot be met with integer placement"
                )
            shift = max(low, min(high, shift))
        advance = override.get(
            "advance", round(bounds[2] + shift + bearings["right_bearing"])
        )
        if measurement["active_height"] and not (
            {"advance", "right_bearing"} & override.keys()
        ):
            low = math.ceil(bounds[2] + shift + settings["min_bearing"])
            high = math.floor(bounds[2] + shift + settings["max_bearing"])
            if low > high:
                raise FontifyError(
                    f"{name}: bearing bounds cannot be met with integer advance"
                )
            advance = max(low, min(high, advance))
        number(advance, f"{name}.proposed advance", 1, 32767, integer=True)
        proposed_spec = copy.deepcopy(spec)
        proposed_spec["advance"] = advance
        transform = list(spec.get("transform", [1, 0, 0, 1, 0, 0]))
        transform[4] += shift
        number(transform[4], f"{name}.proposed translation")
        proposed_spec["transform"] = transform
        # Guard the precise future compiled glyph, not a fractional translation
        # of an earlier compilation that could round differently on export.
        proposed_outline = compile_outline(project, proposed_spec)
        new_bounds = proposed_outline.diagnostics["compiled_bounds"]
        report["desired_bearings"] = bearings
        report["proposed_compiled_sha256"] = proposed_outline.compiled_hash
        report["proposed"] = {
            "left_bearing": new_bounds[0],
            "right_bearing": advance - new_bounds[2],
            "advance": advance,
            "translate_x": shift,
        }
        if (
            new_bounds[0] != bearings["left_bearing"]
            or advance - new_bounds[2] != bearings["right_bearing"]
        ):
            report["reasons"].append(
                "integer translation and advance preserve compiled shape; tight ink bearings may be fractional"
            )
        if override:
            report["reasons"].append("explicit glyph override: " + override["reason"])
        compiled = RecordingPen()
        proposed_outline.glyph.draw(compiled, None)
        path = _path(compiled)
        expanded = pathops.Path(path)
        # A tiny positive cushion also detects touching when requested gap is 0.
        expanded.stroke(
            2 * (config["collision_gap"] + 0.01),
            pathops.LineCap.ROUND_CAP,
            pathops.LineJoin.ROUND_JOIN,
            4,
        )
        expanded.convertConicsToQuads(0.001)
        expanded = pathops.op(path, expanded, pathops.PathOp.UNION)
        rec = RecordingPen()
        path.draw(rec)
        prepared[name] = {
            "path": path,
            "expanded": expanded,
            "rows": _envelope(_edges(rec), path.bounds[1], path.bounds[3]),
            "bounds": list(path.bounds),
        }
    names = sorted(prepared)
    existing = {
        (p["left"], p["right"]): p["value"] for p in project.data.get("kerning", [])
    }
    overrides = {(p["left"], p["right"]): p for p in config["pair_overrides"]}
    selected_pairs = (
        {(a, b) for a in names for b in names}
        if config["pairs"] is None
        else {(p["left"], p["right"]) for p in config["pairs"]}
    )
    pairs = {(a, b) for a in names for b in names} | set(existing) | set(overrides)
    candidates, kerning = [], []
    for a, b in sorted(pairs):
        reason = []
        current = existing.get((a, b), 0)
        report = {"left": a, "right": b, "current": current, "reasons": reason}
        candidates.append(report)
        requested = None
        optical = minimum = height = None
        target = None
        if a in prepared and b in prepared:
            left, right = prepared[a], prepared[b]
            am, bm = glyphs[a]["measurement"], glyphs[b]["measurement"]
            zone_a, zone_b = am["measured_zone"], bm["measured_zone"]
            offset = glyphs[a]["proposed"]["advance"]
            if (
                zone_a
                and zone_b
                and max(zone_a[0], zone_b[0]) < min(zone_a[1], zone_b[1])
            ):
                optical, _, height = _pair_gap(
                    left["rows"],
                    right["rows"],
                    offset,
                    max(zone_a[0], zone_b[0]),
                    min(zone_a[1], zone_b[1]),
                )
            _, minimum, _ = _pair_gap(
                left["rows"],
                right["rows"],
                offset,
                min(left["bounds"][1], right["bounds"][1]),
                max(left["bounds"][3], right["bounds"][3]),
            )
            target = sum(
                config["groups"][glyphs[n]["group"]]["side_space"] for n in (a, b)
            )
            if optical is not None and (a, b) in selected_pairs:
                requested = round(target - optical)
                reason.append(
                    "match group pair white-space target over shared reference height"
                )
                bounded = max(
                    -config["max_kerning"], min(config["max_kerning"], requested)
                )
                if bounded != requested:
                    reason.append("limited by max_kerning")
                requested = bounded
        if config["preserve_existing"] and (a, b) in existing:
            requested = current
            reason.append(
                "preserve explicit existing kerning unless collision guard requires more space"
            )
        if (a, b) in overrides:
            requested = overrides[(a, b)]["value"]
            reason.append("explicit pair override: " + overrides[(a, b)]["reason"])
        if requested is None:
            requested = current
            reason.append(
                "pair not selected for optical kerning"
                if (a, b) not in selected_pairs
                else "no shared reference ink; no optical pair adjustment"
            )
        thresholded = (
            abs(requested) < config["kerning_threshold"]
            and (a, b) not in overrides
            and not (config["preserve_existing"] and (a, b) in existing)
        )
        selected = 0 if thresholded else requested
        if thresholded:
            reason.append("below kerning threshold; omit optical adjustment")
        guarded = selected
        if a in prepared and b in prepared:
            guarded = _guard(
                left, right, offset, selected, config["collision_gap"], minimum
            )
            if guarded != selected:
                reason.append(
                    "collision guard increased spacing; applies even to overrides and subthreshold pairs"
                )
        if guarded:
            kerning.append({"left": a, "right": b, "value": guarded})
        report.update(
            selected_for_optical=(a, b) in selected_pairs,
            mean_gap=None if optical is None else round(optical, 6),
            shared_height=height,
            target_gap=target,
            minimum_gap_before_kerning=None if minimum is None else round(minimum, 6),
            requested_value=requested,
            value=guarded,
            collision_adjusted=guarded != selected,
            status="candidate" if guarded else "omitted",
        )
    report = {
        "schema": 1,
        "algorithm": ALGORITHM,
        "status": "proposal_requires_visual_review",
        "source": {
            "project_sha256": digest(project.data),
            "project_file_sha256": hashlib.sha256(
                project.path.read_bytes()
            ).hexdigest(),
            "version": project.data["version"],
            "approved": bool(project.data.get("approval")),
        },
        "config": config,
        "glyphs": glyphs,
        "pairs": candidates,
        "kerning": kerning,
        "warnings": [
            "Optical estimates are not design approval; inspect actual-font words and every glyph.",
            "SVG sources are unchanged. Only horizontal placement, advance widths and explicit GPOS kerning are proposed.",
        ],
    }
    report["plan_sha256"] = digest(report)
    return report


def save_spacing_plan(project_path, output, config=None):
    """Write a new review artifact, refusing to overwrite existing files."""
    plan = spacing_plan(project_path, config)
    output = Path(output)
    if output.is_symlink():
        raise FontifyError("spacing plan output already exists as a symlink")
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        with output.open("x") as stream:
            stream.write(json.dumps(plan, indent=2, allow_nan=False) + "\n")
    except FileExistsError as exc:
        raise FontifyError("spacing plan output already exists") from exc
    return output


def apply_spacing_plan(project_path, plan, output, version):
    """Verify a proposal and apply it only to a fresh, unapproved candidate."""
    project = load_project(project_path)
    if project.data.get("approval"):
        raise FontifyError(
            "approved projects are protected; make an explicitly unapproved candidate copy first"
        )
    if (
        not isinstance(version, str)
        or not re.fullmatch(r"[0-9]{1,2}\.[0-9]{3}", version)
        or version == project.data["version"]
    ):
        raise FontifyError("spacing candidate needs a different version such as 1.001")
    output = Path(output)
    if output.is_symlink():
        raise FontifyError("spacing output already exists as a symlink")
    output = output.resolve()
    if output.exists() or output.is_relative_to(project.root):
        raise FontifyError(
            "spacing output must be a new directory outside the source project"
        )
    plan = _json(plan, "spacing plan")
    if (
        not isinstance(plan, dict)
        or plan.get("schema") != 1
        or plan.get("algorithm") != ALGORITHM
    ):
        raise FontifyError("unsupported spacing plan")
    expected = spacing_plan(project_path, plan.get("config"))
    if plan != expected:
        raise FontifyError(
            "spacing plan is stale or changed; regenerate it with explicit config overrides"
        )
    data = copy.deepcopy(project.data)
    data["version"] = version
    data["approval"] = None
    # Preserve old intent files, but unbind geometry-dependent declarations.
    # Stem probes, regions and patch hashes need fresh review after placement.
    data["quality"] = None
    data["kerning"] = plan["kerning"]
    for spec in data["glyphs"]:
        proposed = plan["glyphs"][spec["name"]]["proposed"]
        spec["advance"] = proposed["advance"]
        if proposed["translate_x"]:
            transform = list(spec.get("transform", [1, 0, 0, 1, 0, 0]))
            transform[4] += proposed["translate_x"]
            number(transform[4], f"{spec['name']}.transform translation")
            spec["transform"] = transform
    # Validate prospective compilation before creating any output directory.
    checked = compile_project(Project(project.path, data))
    for outline in checked:
        expected_hash = plan["glyphs"][outline.spec["name"]].get(
            "proposed_compiled_sha256", outline.compiled_hash
        )
        if outline.compiled_hash != expected_hash:
            raise FontifyError(
                "candidate compiled geometry differs from collision-checked plan"
            )
    # Refuse symlinks rather than following them while copying or writing through
    # a project-file symlink back into a protected source tree.
    if any(p.is_symlink() for p in project.root.rglob("*")):
        raise FontifyError("spacing candidate copy requires a project without symlinks")
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        output.mkdir()
    except FileExistsError as exc:
        raise FontifyError("spacing output already exists") from exc
    try:
        shutil.copytree(project.root, output, dirs_exist_ok=True)
        (output / "fontify.json").write_text(json.dumps(data, indent=2) + "\n")
        receipt = {
            "schema": 1,
            "status": "draft_requires_recheck_and_visual_review",
            "source_project_sha256": plan["source"]["project_sha256"],
            "candidate_project_sha256": digest(data),
            "plan_sha256": plan["plan_sha256"],
            "version": version,
            "previous_quality": project.data.get("quality"),
            "quality_status": "fresh_intent_and_visual_review_required",
            "glyphs": {
                o.spec["name"]: {
                    "source_sha256": o.source_hash,
                    "normalized_sha256": o.normalized_hash,
                    "compiled_sha256": o.compiled_hash,
                }
                for o in checked
            },
            "plan": plan,
        }
        (output / "spacing-changes.json").write_text(
            json.dumps(receipt, indent=2) + "\n"
        )
        load_project(output / "fontify.json")
    except Exception:
        shutil.rmtree(output)
        raise
    return output / "fontify.json"
