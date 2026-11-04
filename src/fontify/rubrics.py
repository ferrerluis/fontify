"""Style defaults and deterministic routing from reviewed glyph intent.

Styles recommend decisions; they never classify artwork or approve its appearance.
"""

import copy

from .model import FontifyError, keys

STYLES = {
    "geometric": {
        "balance": "optical",
        "axes": "near_axis",
        "weight": "optical",
        "reason": "Precise construction; select reflection axes and comparable stems individually.",
    },
    "humanist": {
        "balance": "optical",
        "axes": "declared",
        "weight": "optical",
        "reason": "Optical balance and modulation; name exact straight features individually.",
    },
    "handwritten": {
        "balance": "asymmetric",
        "axes": "organic",
        "weight": "variable",
        "reason": "Retain deliberate lean, bowed strokes and variation; declare precise exceptions.",
    },
    "serif": {
        "balance": "optical",
        "axes": "declared",
        "weight": "variable",
        "reason": "Review contrast, overshoot and serif joins; name intended corners and stem targets.",
    },
    "display": {
        "balance": "unresolved",
        "axes": "unresolved",
        "weight": "unresolved",
        "reason": "Mixed or decorative construction needs explicit decisions for each glyph.",
    },
}
PENDING_NOTE = "Pending source inspection; these style defaults are recommendations."
CHOICES = {
    "balance": {"exact", "optical", "asymmetric", "none", "unresolved"},
    "axes": {"near_axis", "declared", "organic", "none", "unresolved"},
    "weight": {"measured", "optical", "variable", "none", "unresolved"},
}
REPAIRS = {"axes", "symmetry", "stems", "tangents", "polygonize", "patches"}


def plan_profile(project, outlines, style, note):
    """Propose a schema-2 profile without altering input or confirming design intent."""
    from .quality import load_profile

    if not isinstance(style, str) or style not in STYLES:
        raise FontifyError(f"unknown rubric style: {style}")
    if not isinstance(note, str) or not note.strip():
        raise FontifyError("describe the font brief and why this review style fits")
    prior = load_profile(project)
    profile = copy.deepcopy(prior) if prior else {"review": "agent-review.json"}
    profile.update(schema=2, style=style, style_note=note, glyphs={})
    defaults = STYLES[style]
    for o in outlines:
        name = o.spec["name"]
        old = copy.deepcopy(prior["glyphs"][name]) if prior else {}
        construction = old.get(
            "construction",
            "blank"
            if not o.record.value
            else (
                "curved"
                if any(op in ("curveTo", "qCurveTo") for op, _ in o.record.value)
                else "polygon"
            ),
        )
        policy = old.pop("axis_policy", None)
        old.pop("decisions", None)
        glyph = {
            **old,
            "construction": construction,
            "symmetry": old.get("symmetry", []),
            "note": PENDING_NOTE,
        }
        if construction == "blank":
            decisions = dict.fromkeys(CHOICES, "none")
            glyph["note"] = (
                f"Blank glyph; inspect its explicit {o.spec['advance']}-unit advance in words."
            )
        else:
            decisions = {k: defaults[k] for k in CHOICES}
            if construction == "curved" and decisions["axes"] == "near_axis":
                decisions["axes"] = "declared"
            if glyph["symmetry"]:
                decisions["balance"] = "exact"
            if policy:
                decisions["axes"] = policy
            if glyph.get("straight_regions"):
                decisions["axes"] = "declared"
            if glyph.get("stems"):
                decisions["weight"] = "measured"
        glyph["decisions"] = {
            **decisions,
            "confirmed": construction == "blank",
            "repairs": [],
        }
        profile["glyphs"][name] = glyph
    return profile


def validate_rubrics(profile):
    """Validate choices, rejecting contradictions instead of silently relaxing rules."""
    if profile["schema"] == 1:
        if (
            "style" in profile
            or "style_note" in profile
            or any("decisions" in g for g in profile["glyphs"].values())
        ):
            raise FontifyError("style routing requires a schema-2 quality profile")
        return
    if not isinstance(profile.get("style"), str) or profile["style"] not in STYLES:
        raise FontifyError("schema-2 profile requires a supported rubric style")
    if (
        not isinstance(profile.get("style_note"), str)
        or not profile["style_note"].strip()
    ):
        raise FontifyError("schema-2 profile needs the style/brief rationale")
    for name, g in profile["glyphs"].items():
        d = g.get("decisions")
        keys(d, "confirmed balance axes weight repairs", "glyph rubric decisions")
        if not isinstance(d.get("confirmed"), bool):
            raise FontifyError(f"{name}: declare whether glyph intent is confirmed")
        for field, choices in CHOICES.items():
            if not isinstance(d.get(field), str) or d[field] not in choices:
                raise FontifyError(f"{name}: invalid {field} rubric decision")
        repairs = d.get("repairs")
        if (
            not isinstance(repairs, list)
            or any(not isinstance(v, str) or v not in REPAIRS for v in repairs)
            or len(set(repairs)) != len(repairs)
        ):
            raise FontifyError(f"{name}: invalid allowed repairs")
        blank = g["construction"] == "blank"
        if blank:
            if (
                any(d[k] != "none" for k in CHOICES)
                or repairs
                or g["symmetry"]
                or any(g.get(k) for k in ("corners", "straight_regions", "stems"))
            ):
                raise FontifyError(f"{name}: blank glyphs cannot declare ink features")
        elif any(d[k] == "none" for k in CHOICES):
            raise FontifyError(f"{name}: nonblank glyphs need actual rubric decisions")
        if d["balance"] != "unresolved" and bool(g["symmetry"]) != (
            d["balance"] == "exact"
        ):
            raise FontifyError(
                f"{name}: exact balance needs named reflection axes only"
            )
        if d["weight"] != "unresolved" and bool(g.get("stems")) != (
            d["weight"] == "measured"
        ):
            raise FontifyError(
                f"{name}: measured weight needs explicit stem probes only"
            )
        if d["axes"] in ("organic", "none") and g.get("straight_regions"):
            raise FontifyError(
                f"{name}: precise straight regions need the declared axis route"
            )
        if "symmetry" in repairs and d["balance"] != "exact":
            raise FontifyError(f"{name}: reflection repair needs exact balance intent")
        if "axes" in repairs and d["axes"] not in ("near_axis", "declared"):
            raise FontifyError(f"{name}: axis repair needs precise feature intent")
        if "stems" in repairs and (
            d["weight"] != "measured" or g["construction"] != "polygon"
        ):
            raise FontifyError(f"{name}: automatic stem repair needs polygon probes")
        if "polygonize" in repairs and g["construction"] != "polygon":
            raise FontifyError(f"{name}: polygon repair needs polygon intent")
        if "tangents" in repairs and g["construction"] != "curved":
            raise FontifyError(f"{name}: tangent repair needs curved intent")
        policy = "near_axis" if d["axes"] == "near_axis" else "declared"
        if "axis_policy" in g and g["axis_policy"] != policy:
            raise FontifyError(f"{name}: axis policy contradicts the rubric decision")


def intent_issues(intent, profile):
    if profile["schema"] == 1:
        return []
    d = intent["decisions"]
    if (
        not d["confirmed"]
        or any(d[k] == "unresolved" for k in CHOICES)
        or intent["note"] == PENDING_NOTE
    ):
        return [
            {
                "kind": "intent_unresolved",
                "reason": "Inspect the source and resolve this glyph's intent before correction or presentation.",
            }
        ]
    return []


def require_resolved(profile):
    names = [n for n, g in profile["glyphs"].items() if intent_issues(g, profile)]
    if names:
        raise FontifyError("unresolved rubric intent: " + ", ".join(names))


def route_glyph(audit, intent, profile):
    """Explain numeric applicability/result separately from edit and visual review."""
    blank = intent["construction"] == "blank"
    issues = audit["issues"]
    pending = bool(intent_issues(intent, profile))
    d = intent["decisions"]
    repairs = d["repairs"]

    def rule(ident, applies, reason, kinds, edit=None, limits=None):
        findings = [i for i in issues if i["kind"] in kinds]
        return {
            "id": ident,
            "method": "deterministic",
            "status": "needs_intent"
            if pending
            else (
                "not_applicable"
                if not applies
                else ("failed" if findings else "passed")
            ),
            "reason": "Resolve and confirm source intent first."
            if pending
            else ("Blank glyph: no ink feature to measure." if blank else reason),
            "limits": limits or {},
            "findings": findings,
            "repair_allowed": bool(edit and edit in repairs and not pending),
            "repair_requires_finding": True,
        }

    return {
        "style": profile["style"],
        "decisions": copy.deepcopy(d),
        "checks": [
            rule(
                "reflection",
                not blank and d["balance"] == "exact",
                "Named reflection axes."
                if d["balance"] == "exact"
                else "Optical/asymmetric intent: review balance without forcing reflection.",
                {"symmetry"},
                "symmetry",
                {"max_asymmetry_ratio": profile["symmetry_tolerance"]},
            ),
            rule(
                "axes",
                not blank
                and (
                    bool(intent.get("straight_regions"))
                    or audit["axis_edges_checked"] > 0
                ),
                "Selected straight regions or confirmed near-axis line classification."
                if intent.get("straight_regions") or audit["axis_edges_checked"]
                else (
                    "Organic construction retains its intended lean and curvature."
                    if d["axes"] == "organic"
                    else "No exact axial features selected or classified; inspect their construction visually."
                ),
                {"axis_alignment", "straight_region_unmatched"},
                "axes",
                {
                    "max_alignment_spread_units": 1e-7,
                    "classification_angle_degrees": profile["axis_angle_degrees"],
                    "heuristic_min_length_units": profile["min_axis_length"],
                },
            ),
            rule(
                "curve_geometry",
                not blank and audit["curves_checked"] > 0,
                "Check stationary reversals and unexpected joins; named corners remain intentional. All curve flow also needs visual review."
                if audit["curves_checked"]
                else "No Bezier curves; corners and diagonals still need visual review.",
                {"curve_cusp", "curve_join", "unexpected_curve"},
                "tangents",
                {
                    "max_join_angle_degrees": profile["max_tangent_degrees"],
                    "min_join_length_units": profile["min_join_length"],
                    "min_tangent_length_units": profile["min_tangent_length"],
                },
            ),
            rule(
                "stem_targets",
                not blank and bool(intent.get("stems")),
                "Measure only named probes; targets may differ by feature."
                if intent.get("stems")
                else "No exact stem targets: review optical/variable weight in actual glyphs and words.",
                {"stem_missing", "stem_width"},
                "stems",
                {"max_width_error_units": 1e-6},
            ),
        ],
        "visual_review": {
            "status": "required",
            "areas": [
                "symmetry",
                "axes",
                "curves",
                "optical_weight",
                "spacing",
                "source_preservation",
            ],
            "focus": STYLES[profile["style"]]["reason"],
            "blank": blank,
        },
    }
