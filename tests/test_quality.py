import copy
import hashlib
import json
import shutil

import pytest
from conftest import ROOT
from fontTools.pens.recordingPen import RecordingPen
from fontTools.svgLib.path import parse_path

from fontify import FontifyError, build_font, load_project
from fontify.cli import main
from fontify.outlines import compile_project, digest
from fontify.quality import (
    REVIEW_CHECKS,
    SegmentsPen,
    audit_project,
    curve_has_cusp,
    glyph_audit,
    load_profile,
)
from fontify.repair import apply_contour_patch, correction, repair_project
from fontify.review import approval_snapshot


def write_json(path, data):
    path.write_text(json.dumps(data, indent=2) + "\n")


def record(path):
    pen = RecordingPen()
    parse_path(path, pen)
    return pen


@pytest.fixture
def intent_project(tmp_path):
    root = tmp_path / "source"
    root.mkdir()
    d = json.loads((ROOT / "examples/offline/fontify.json").read_text())
    d.update(
        approval=None,
        quality="quality.json",
        required_characters=" H",
        samples=["H HH"],
        kerning=[],
        svg_baseline=800,
    )
    d["glyphs"] = [g for g in d["glyphs"] if g["name"] in ("H", "space")]
    d["glyphs"][1]["source"] = "H.svg"
    # SVG y is down; the intended H has an exact vertical reflection.
    (root / "H.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 660 1000"><path d="M50 800 V100 H250 V350 H410 V100 H610 V800 H410 V500 H250 V800 Z"/></svg>'
    )
    write_json(root / "fontify.json", d)
    write_json(
        root / "quality.json",
        {
            "schema": 1,
            "review": "agent-review.json",
            "glyphs": {
                "H": {
                    "construction": "polygon",
                    "symmetry": ["vertical"],
                    "note": "Matching straight uprights around a centered bar.",
                },
                "space": {
                    "construction": "blank",
                    "symmetry": [],
                    "note": "Blank explicit word spacing.",
                },
            },
        },
    )
    return root / "fontify.json"


def reviewed_fixture(project_path, draft_manifest):
    """A mock agent receipt for a two-glyph fixture, not a real design review."""
    project = load_project(project_path)
    manifest = json.loads(draft_manifest.read_text())
    report = audit_project(
        project, compile_project(project), draft_manifest.parent / manifest["font"]
    )
    proof = project.root / "fixture-proof.svg"
    shutil.copyfile(draft_manifest.parent / "glyph-sheet.svg", proof)
    receipt = {
        "schema": 1,
        "reviewer": "mock agent for gate regression tests",
        "project_sha256": digest(project.data),
        "font_sha256": report["font_sha256"],
        "profile_sha256": report["profile_sha256"],
        "evidence": [
            {
                "path": proof.name,
                "sha256": hashlib.sha256(proof.read_bytes()).hexdigest(),
            }
        ],
        "glyphs": {
            n: {
                "fingerprint": g["fingerprint"],
                "checks": dict.fromkeys(REVIEW_CHECKS, "passed"),
                "notes": "Mocked review: exact H and blank space fixture.",
                "evidence": [proof.name],
            }
            for n, g in report["glyphs"].items()
        },
    }
    path = project.root / "agent-review.json"
    write_json(path, receipt)
    return path, receipt


def test_intent_requires_complete_explicit_profiles(intent_project):
    project = load_project(intent_project)
    assert set(load_profile(project)["glyphs"]) == {"H", "space"}
    p = project.root / "quality.json"
    original = json.loads(p.read_text())
    for mutation in (
        lambda d: d["glyphs"].pop("H"),
        lambda d: d.update(max_tangent_degrees=180),
        lambda d: d["glyphs"]["H"].update(symmetry=[{}]),
        lambda d: d["glyphs"]["H"].update(
            stems=[{"at": 10, "width": float("nan"), "index": 0, "anchor": "left"}]
        ),
    ):
        changed = copy.deepcopy(original)
        mutation(changed)
        write_json(p, changed)
        with pytest.raises(FontifyError):
            load_profile(project)


def test_axes_repairs_are_bounded_and_keep_diagonals(intent_project):
    profile = load_profile(load_project(intent_project))
    intent = {
        "construction": "polygon",
        "symmetry": [],
        "note": "Exact rectangular edges, distinct from diagonals.",
    }
    crooked = record("M50 0 L52 700 L610 700 L610 0 Z")
    original = copy.deepcopy(crooked.value)
    assert any(
        i["kind"] == "axis_alignment"
        for i in glyph_audit(crooked, intent, profile)["issues"]
    )
    fixed, change = correction(crooked, intent, profile, 660)
    assert glyph_audit(fixed, intent, profile)["status"] == "passed"
    assert change["changed_area_ratio"] < 0.01 and change["max_bounds_change"] <= 2
    assert crooked.value == original
    triangle = record("M50 0 L330 700 L610 0 Z")
    fixed, _ = correction(triangle, intent, profile, 660)
    pen = SegmentsPen()
    fixed.replay(pen)
    diagonals = [
        pts
        for op, pts in pen.contours[0]
        if pts[0][0] != pts[-1][0] and pts[0][1] != pts[-1][1]
    ]
    assert len(diagonals) == 2


def test_axes_declared_intent_preserves_handwritten_lean(intent_project):
    profile = load_profile(load_project(intent_project))
    shape = record("M50 0 L52 700 L610 700 L610 0 Z")
    intent = {
        "construction": "curved",
        "symmetry": [],
        "axis_policy": "declared",
        "note": "The slight upright lean is intentional in this handwritten design.",
    }
    fixed, _ = correction(shape, intent, profile, 660)
    pen = SegmentsPen()
    fixed.replay(pen)
    assert pen.contours[0][0][1] == [(50, 0), (52, 700)]
    assert glyph_audit(fixed, intent, profile)["axis_edges_checked"] == 0
    explicit = {
        **intent,
        "straight_regions": [[49, -1, 53, 701]],
        "note": "This selected upright must be exact vertical.",
    }
    fixed, _ = correction(shape, explicit, profile, 660)
    pen = SegmentsPen()
    fixed.replay(pen)
    assert pen.contours[0][0][1] == [(51, 0), (51, 700)]
    assert glyph_audit(fixed, explicit, profile)["status"] == "passed"


def test_curves_detect_kinks_cusps_and_named_corners(intent_project):
    profile = load_profile(load_project(intent_project))
    intent = {
        "construction": "curved",
        "symmetry": [],
        "note": "Two connected bowls; the internal join must be smooth.",
    }
    kink = record(
        "M100 0 L100 500 C100 600 200 700 300 700 C300 600 400 700 500 700 L500 0 Z"
    )
    issues = glyph_audit(kink, intent, profile)["issues"]
    assert any(i["kind"] == "curve_join" and i["point"] == [300, 700] for i in issues)
    allowed = {**intent, "corners": [[300, 700], [500, 700]]}
    assert not any(
        i["kind"] == "curve_join" for i in glyph_audit(kink, allowed, profile)["issues"]
    )
    cusp = record("M100 0 L100 500 C100 400 400 800 500 700 L500 0 Z")
    assert any(
        i["kind"] == "curve_cusp" for i in glyph_audit(cusp, intent, profile)["issues"]
    )


def test_curves_wide_round_hook_is_not_a_cusp():
    # Recraft's g ear sweeps beyond 100 degrees relative to its chord, smoothly.
    hook = [
        "C",
        [(429.402, 461.714), (491.045, 474.786), (502.26, 394.381), (460.402, 386.143)],
    ]
    assert not curve_has_cusp(hook)
    assert curve_has_cusp(["C", [(0, 0), (2, 2), (0, 2), (2, 0)]])
    assert curve_has_cusp(["Q", [(0, 0), (2, 0), (0, 0)]])


def test_curves_exported_symmetry_is_rechecked(tmp_path):
    project = load_project(ROOT / "examples/imagegen/fontify.json")
    manifest = build_font(project, tmp_path, draft=True)
    d = json.loads(manifest.read_text())
    report = audit_project(
        project, compile_project(project), manifest.parent / d["font"]
    )
    assert report["status"] == "passed"
    for name in ("C", "D", "I", "O", "U", "X"):
        assert all(r <= 1e-6 for r in report["glyphs"][name]["symmetry"].values())


def test_preservation_repair_protects_sources_and_budgets(intent_project, tmp_path):
    before = {p.name: p.read_bytes() for p in intent_project.parent.iterdir()}
    out = tmp_path / "corrected"
    repair_project(intent_project, out, "1.002")
    assert all((intent_project.parent / n).read_bytes() == b for n, b in before.items())
    with pytest.raises(FontifyError, match="new directory"):
        repair_project(intent_project, out, "1.002")
    d = json.loads(intent_project.read_text())
    d["approval"] = "approved.json"
    write_json(intent_project, d)
    with pytest.raises(FontifyError, match="approved projects"):
        repair_project(intent_project, tmp_path / "protected", "1.002")
    profile = load_profile(load_project(intent_project))
    intent = profile["glyphs"]["H"]
    shape = record("M50 0 L50 700 L610 700 L610 0 Z")
    patch_base, _ = correction(shape, intent, profile, 660)
    patch = {
        "fingerprint": digest(patch_base.value),
        "note": "An intentionally excessive test edit.",
        "contours": {"0": "M-100 0 L-100 700 L900 700 L900 0 Z"},
    }
    with pytest.raises(FontifyError, match="preservation budget"):
        correction(shape, intent, profile, 660, patch)
    patch["fingerprint"] = "stale"
    with pytest.raises(FontifyError, match="stale"):
        apply_contour_patch(shape, patch)


def test_release_gate_requires_current_complete_visual_review(intent_project, tmp_path):
    out = tmp_path / "build"
    draft = build_font(intent_project, out, draft=True)
    assert "-draft" in str(draft.parent) and not (out / "current.json").exists()
    with pytest.raises(FontifyError, match="visual review is missing"):
        build_font(intent_project, out)
    path, receipt = reviewed_fixture(intent_project, draft)
    incomplete = copy.deepcopy(receipt)
    incomplete["glyphs"]["H"]["checks"].pop("curves")
    write_json(path, incomplete)
    with pytest.raises(FontifyError, match="unresolved"):
        build_font(intent_project, out)
    incomplete = copy.deepcopy(receipt)
    incomplete["glyphs"].pop("space")
    write_json(path, incomplete)
    with pytest.raises(FontifyError, match="every glyph"):
        build_font(intent_project, out)
    write_json(path, receipt)
    final = build_font(intent_project, out)
    pointer = (out / "current.json").read_bytes()
    assert json.loads(final.read_text())["quality"]["status"] == "preflight_passed"
    for kind in ("spacing", "profile", "evidence", "fingerprint"):
        d = json.loads(intent_project.read_text())
        profile_path = intent_project.parent / "quality.json"
        profile_bytes = profile_path.read_bytes()
        proof = intent_project.parent / "fixture-proof.svg"
        proof_bytes = proof.read_bytes()
        changed_receipt = copy.deepcopy(receipt)
        if kind == "spacing":
            d["glyphs"][0]["advance"] += 1
            write_json(intent_project, d)
        if kind == "profile":
            q = json.loads(profile_bytes)
            q["glyphs"]["H"]["note"] += " Changed intent."
            write_json(profile_path, q)
        if kind == "evidence":
            proof.write_bytes(b"changed")
        if kind == "fingerprint":
            changed_receipt["glyphs"]["H"]["fingerprint"] = "stale"
            write_json(path, changed_receipt)
        with pytest.raises(FontifyError, match="stale"):
            build_font(intent_project, out)
        assert (out / "current.json").read_bytes() == pointer
        if kind == "spacing":
            d["glyphs"][0]["advance"] -= 1
            write_json(intent_project, d)
        profile_path.write_bytes(profile_bytes)
        proof.write_bytes(proof_bytes)
        write_json(path, receipt)
    assert main(["release", str(intent_project), "--out", str(out)]) == 0
    d = json.loads(intent_project.read_text())
    d.pop("quality")
    write_json(intent_project, d)
    assert (
        main(["release", str(intent_project), "--out", str(tmp_path / "ungated")]) == 1
    )


def test_release_gate_keeps_unfixed_geometry_internal(intent_project, tmp_path):
    svg = intent_project.parent / "H.svg"
    svg.write_text(svg.read_text().replace("H250 V350", "H251 V350"))
    assert main(["audit", str(intent_project), "--out", str(tmp_path / "audit")]) == 1
    draft = build_font(intent_project, tmp_path / "drafts", draft=True)
    assert (
        json.loads((draft.parent / "quality.json").read_text())["source"]["status"]
        == "failed"
    )
    with pytest.raises(FontifyError, match="preflight geometry failed"):
        build_font(intent_project, tmp_path / "release")
    assert not (tmp_path / "release/current.json").exists()


def test_approval_proof_tracks_baseline_without_claiming_style_quality(
    intent_project, tmp_path
):
    draft = build_font(intent_project, tmp_path / "draft", draft=True)
    receipt_path, receipt = reviewed_fixture(intent_project, draft)
    before = build_font(intent_project, tmp_path / "before")
    assert "user design approval pending" in (before.parent / "proof.html").read_text()
    project = load_project(intent_project)
    write_json(
        intent_project.parent / "approved.json",
        approval_snapshot(project, compile_project(project)),
    )
    data = project.data
    data["approval"] = "approved.json"
    write_json(intent_project, data)
    receipt["project_sha256"] = digest(data)
    write_json(receipt_path, receipt)
    after = build_font(intent_project, tmp_path / "after")
    report = json.loads(after.read_text())
    assert report["approval"]["status"] == "baseline_matches"
    proof = (after.parent / "proof.html").read_text()
    assert (
        "glyph baseline matches" in proof
        and "user design approval pending" not in proof
    )
    assert "Human review is still required" in proof
    assert report["quality"]["visual_review"]["human_approval"] == "not_implied"
    for field in ("font", "webfont"):
        name = report[field]
        assert (before.parent / name).read_bytes() == (after.parent / name).read_bytes()


def test_preservation_generated_corrections_reproduce(tmp_path):
    source = ROOT / "examples/imagegen"
    result = repair_project(
        source / "source/traced-v0.001/fontify-preflight.json",
        tmp_path / "candidate",
        "0.002",
        source / "source/local-patches.json",
    )
    for glyph in (source / "glyphs").glob("*.svg"):
        assert (
            result.parent / "glyphs" / glyph.name
        ).read_bytes() == glyph.read_bytes()
