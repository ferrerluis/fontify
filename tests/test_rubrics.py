import copy
import hashlib
import json
import shutil
import socket
from pathlib import Path

import pytest
from conftest import ROOT
from fontTools.pens.recordingPen import RecordingPen
from fontTools.svgLib.path import parse_path

from fontify import FontifyError, build_font, load_project, preflight, release_font
from fontify.cli import main
from fontify.outlines import compile_project, digest
from fontify.quality import REVIEW_CHECKS, audit_project, glyph_audit, load_profile
from fontify.repair import correction, repair_project
from fontify.review import approval_snapshot, verified_release
from fontify.rubrics import STYLES, plan_profile


def write(path, data):
    path.write_text(json.dumps(data, indent=2) + "\n")


def record(path):
    pen = RecordingPen()
    parse_path(path, pen)
    return pen


@pytest.fixture
def routed(tmp_path):
    root = tmp_path / "source"
    root.mkdir()
    data = json.loads((ROOT / "examples/offline/fontify.json").read_text())
    data.update(approval=None, required_characters=" H", samples=["H HH"], kerning=[])
    data["glyphs"] = [g for g in data["glyphs"] if g["name"] in ("space", "H")]
    data["glyphs"][1]["source"] = "H.svg"
    (root / "H.svg").write_text(
        '<svg viewBox="0 0 660 1000"><path d="M50 800 V100 H250 V350 H410 V100 H610 V800 H410 V500 H250 V800 Z"/></svg>'
    )
    path = root / "fontify.json"
    write(path, data)
    project = load_project(path)
    profile = plan_profile(
        project,
        compile_project(project),
        "geometric",
        "Precise upright test construction.",
    )
    profile["glyphs"]["H"]["decisions"]["confirmed"] = True
    profile["glyphs"]["H"]["note"] = (
        "The H uses precise horizontal and vertical polygon edges; reflection is reviewed optically."
    )
    write(root / "quality.json", profile)
    data["quality"] = "quality.json"
    write(path, data)
    return path


def mock_review(path, manifest):
    """Test-only receipt; this does not represent a human or agent design review."""
    project = load_project(path)
    data = verified_release(manifest)
    audit = audit_project(
        project, compile_project(project), manifest.parent / data["font"]
    )
    evidence = project.root / "fixture-review.svg"
    shutil.copyfile(manifest.parent / "glyph-sheet.svg", evidence)
    receipt = {
        "schema": 1,
        "reviewer": "mock review for rubric gate regression only",
        "project_sha256": digest(project.data),
        "profile_sha256": audit["profile_sha256"],
        "font_sha256": audit["font_sha256"],
        "evidence": [
            {
                "path": evidence.name,
                "sha256": hashlib.sha256(evidence.read_bytes()).hexdigest(),
            }
        ],
        "glyphs": {
            n: {
                "fingerprint": g["fingerprint"],
                "checks": dict.fromkeys(REVIEW_CHECKS, "passed"),
                "notes": "Mocked inspection of the precise H and blank space fixture.",
                "evidence": [evidence.name],
            }
            for n, g in audit["glyphs"].items()
        },
    }
    write(project.root / "agent-review.json", receipt)


@pytest.mark.parametrize("style", STYLES)
def test_rubric_plan_defaults_are_unconfirmed_and_cover_blank(routed, style, tmp_path):
    project = load_project(routed)
    project.data.pop("quality")
    before = routed.read_bytes()
    plan = plan_profile(
        project, compile_project(project), style, "A source-aware style choice."
    )
    assert set(plan["glyphs"]) == {"H", "space"}
    assert plan["glyphs"]["space"]["decisions"]["confirmed"]
    assert not plan["glyphs"]["H"]["decisions"]["confirmed"]
    assert plan["glyphs"]["H"]["decisions"]["repairs"] == []
    assert plan["glyphs"]["H"]["decisions"]["axes"] == STYLES[style]["axes"]
    output = tmp_path / f"{style}.json"
    assert (
        main(
            [
                "rubric-plan",
                str(routed),
                "--style",
                style,
                "--note",
                "Style proposal.",
                "--output",
                str(output),
            ]
        )
        == 0
    )
    assert (
        main(
            [
                "rubric-plan",
                str(routed),
                "--style",
                style,
                "--note",
                "Style proposal.",
                "--output",
                str(output),
            ]
        )
        == 1
    )
    assert routed.read_bytes() == before
    with pytest.raises(FontifyError, match="unknown rubric style"):
        plan_profile(project, compile_project(project), "imagined", "Unknown.")


def test_rubric_routing_preserves_organic_shapes_and_checks_exceptions(routed):
    profile = load_profile(load_project(routed))
    profile["style"] = "handwritten"
    intent = profile["glyphs"]["H"]
    intent.update(axis_policy="declared", note="The small lean is intentional.")
    intent["decisions"].update(axes="organic", balance="asymmetric", weight="variable")
    shape = record("M50 0 L52 700 L610 700 L610 0 Z")
    report = glyph_audit(shape, intent, profile)
    assert report["status"] == "passed"
    checks = {r["id"]: r for r in report["rubrics"]["checks"]}
    assert (
        checks["reflection"]["status"] == checks["axes"]["status"] == "not_applicable"
    )
    assert report["rubrics"]["visual_review"]["status"] == "required"
    intent["decisions"]["axes"] = "declared"
    intent["straight_regions"] = [[49, -1, 53, 701]]
    report = glyph_audit(shape, intent, profile)
    assert report["status"] == "failed"
    assert any(i["kind"] == "axis_alignment" for i in report["issues"])
    intent["symmetry"] = ["vertical"]
    intent["decisions"]["balance"] = "exact"
    report = glyph_audit(shape, intent, profile)
    assert any(i["kind"] == "symmetry" for i in report["issues"])
    intent["decisions"]["weight"] = "measured"
    intent["stems"] = [{"at": 100, "index": 0, "width": 500, "anchor": "left"}]
    assert any(
        i["kind"] == "stem_width" for i in glyph_audit(shape, intent, profile)["issues"]
    )


def test_rubric_routing_explicit_regions_cannot_silently_miss(routed):
    profile = load_profile(load_project(routed))
    intent = profile["glyphs"]["H"]
    intent.update(axis_policy="declared", straight_regions=[[49, -1, 80, 101]])
    intent["decisions"]["axes"] = "declared"
    steep = record("M50 0 L75 100 L200 100 L200 0 Z")
    assert any(
        i["kind"] == "axis_alignment"
        for i in glyph_audit(steep, intent, profile)["issues"]
    )
    intent["straight_regions"] = [[300, 300, 400, 400]]
    assert any(
        i["kind"] == "straight_region_unmatched"
        for i in glyph_audit(steep, intent, profile)["issues"]
    )
    intent["straight_regions"] = [[49, -1, 52, 16]]
    intent["decisions"]["repairs"] = ["axes"]
    small = record("M50 0 L50.5 15 L200 15 L200 0 Z")
    fixed, change = correction(small, intent, profile, 250)
    assert change["audit"]["status"] == "passed"
    assert fixed.value != small.value


def test_rubric_routing_rejects_contradictory_decisions(routed):
    path = routed.parent / "quality.json"
    original = json.loads(path.read_text())
    for change in (
        lambda g: g.update(symmetry=["vertical"]),
        lambda g: g["decisions"].update(weight="measured"),
        lambda g: g["decisions"].update(axes="organic", repairs=["axes"]),
        lambda g: g["decisions"].update(repairs=["pretend"]),
    ):
        data = copy.deepcopy(original)
        change(data["glyphs"]["H"])
        write(path, data)
        with pytest.raises(FontifyError):
            load_profile(load_project(routed))


def test_rubric_permission_findings_do_not_authorize_repairs(routed, tmp_path):
    svg = routed.parent / "H.svg"
    svg.write_text(svg.read_text().replace("M50 800 V100", "M50 800 L52 100"))
    original = svg.read_bytes()
    candidate = repair_project(routed, tmp_path / "no-edits", "1.002")
    assert (candidate.parent / "H.svg").read_bytes() == original
    assert svg.read_bytes() == original
    assert (
        audit_project(
            load_project(candidate), compile_project(load_project(candidate))
        )["status"]
        == "failed"
    )
    profile_path = routed.parent / "quality.json"
    profile = json.loads(profile_path.read_text())
    profile["glyphs"]["H"]["decisions"]["repairs"] = ["axes"]
    write(profile_path, profile)
    candidate = repair_project(routed, tmp_path / "allowed", "1.002")
    assert (candidate.parent / "H.svg").read_bytes() != original
    assert (
        audit_project(
            load_project(candidate), compile_project(load_project(candidate))
        )["status"]
        == "passed"
    )
    assert svg.read_bytes() == original
    project = load_project(routed)
    write(
        project.root / "approved.json",
        approval_snapshot(project, compile_project(project)),
    )
    project.data["approval"] = "approved.json"
    write(routed, project.data)
    with pytest.raises(FontifyError, match="approved projects"):
        repair_project(routed, tmp_path / "protected", "1.003")
    assert not (tmp_path / "protected").exists()


def test_rubric_permission_local_patch_requires_explicit_permission(routed):
    project = load_project(routed)
    profile = load_profile(project)
    outline = next(o for o in compile_project(project) if o.spec["name"] == "H")
    with pytest.raises(FontifyError, match="patch is not allowed"):
        correction(
            outline.record,
            profile["glyphs"]["H"],
            profile,
            660,
            {"fingerprint": "unused"},
        )


def test_rubric_permission_compliant_glyph_is_not_reauthored(routed):
    project = load_project(routed)
    profile = load_profile(project)
    intent = profile["glyphs"]["H"]
    intent["symmetry"] = ["vertical"]
    intent["decisions"].update(
        balance="exact", repairs=["polygonize", "axes", "symmetry"]
    )
    outline = next(o for o in compile_project(project) if o.spec["name"] == "H")
    assert glyph_audit(outline.record, intent, profile)["status"] == "passed"
    fixed, _ = correction(outline.record, intent, profile, outline.spec["advance"])
    assert fixed.value == outline.record.value


def test_rubric_preflight_repairs_then_requires_visual_review(
    routed, tmp_path, monkeypatch
):
    def no_network(*args, **kwargs):
        raise AssertionError("preflight attempted a network call")

    monkeypatch.setattr(socket.socket, "connect", no_network)
    svg = routed.parent / "H.svg"
    svg.write_text(svg.read_text().replace("M50 800 V100", "M50 800 L52 100"))
    before = {p.name: p.read_bytes() for p in routed.parent.iterdir()}
    profile_path = routed.parent / "quality.json"
    profile = json.loads(profile_path.read_text())
    profile["glyphs"]["H"]["decisions"]["repairs"] = ["axes"]
    write(profile_path, profile)
    before[profile_path.name] = profile_path.read_bytes()
    out = tmp_path / "pass"
    result = preflight(routed, out, "1.002")
    assert result["before"]["status"] == "failed"
    assert result["after"]["status"] == result["compiled"]["status"] == "passed"
    assert result["status"] == "needs_visual_review" and not result["published"]
    assert Path(result["comparison"]).is_file()
    assert not list(out.rglob("current.json"))
    assert all(
        (routed.parent / name).read_bytes() == data for name, data in before.items()
    )
    assert (
        main(
            [
                "preflight",
                str(result["candidate_project"]),
                "--out",
                str(tmp_path / "again"),
            ]
        )
        == 2
    )
    with pytest.raises(FontifyError, match="new directory"):
        preflight(routed, out)


def test_rubric_preflight_residual_defects_stay_blocked(routed, tmp_path):
    svg = routed.parent / "H.svg"
    svg.write_text(svg.read_text().replace("M50 800 V100", "M50 800 L52 100"))
    result = preflight(routed, tmp_path / "unfixed", "1.002")
    assert result["status"] == "blocked" and "source checks remain" in result["error"]
    assert not list((tmp_path / "unfixed").rglob("current.json"))


def test_rubric_gate_blocks_pending_intent_and_requires_current_receipt(
    routed, tmp_path
):
    profile_path = routed.parent / "quality.json"
    profile = json.loads(profile_path.read_text())
    profile["glyphs"]["H"]["decisions"]["confirmed"] = False
    write(profile_path, profile)
    result = preflight(routed, tmp_path / "pending")
    assert (
        result["status"] == "blocked" and "unresolved rubric intent" in result["error"]
    )
    assert not list((tmp_path / "pending").rglob("*.ttf"))
    with pytest.raises(FontifyError, match="preflight geometry failed"):
        release_font(routed, tmp_path / "rejected")
    profile["glyphs"]["H"]["decisions"]["confirmed"] = True
    write(profile_path, profile)
    draft = build_font(routed, tmp_path / "draft", draft=True)
    with pytest.raises(FontifyError, match="visual review is missing"):
        release_font(routed, tmp_path / "no-review")
    mock_review(routed, draft)
    result = preflight(routed, tmp_path / "reviewed")
    assert result["status"] == "ready_for_release" and not result["published"]
    manifest = release_font(routed, tmp_path / "release")
    assert (manifest.parent.parent / "current.json").exists()
    profile["style_note"] += " A changed design brief."
    write(profile_path, profile)
    with pytest.raises(FontifyError, match="stale"):
        release_font(routed, tmp_path / "stale")


@pytest.mark.parametrize("style", STYLES)
def test_rubric_universal_checks_cannot_be_disabled_by_style(routed, tmp_path, style):
    profile_path = routed.parent / "quality.json"
    profile = json.loads(profile_path.read_text())
    profile["style"] = style
    write(profile_path, profile)
    svg = routed.parent / "H.svg"
    original = svg.read_text()
    for invalid in (original.replace(" Z", ""), original.replace("V100", "V-5000")):
        svg.write_text(invalid)
        result = preflight(routed, tmp_path / (style + str(len(invalid))))
        assert result["status"] == "blocked" and not result.get("draft_manifest")
    svg.write_text(original)
    data = json.loads(routed.read_text())
    data["glyphs"][1]["unicode"] = "U+0020"
    write(routed, data)
    with pytest.raises(FontifyError, match="Unicode mapping"):
        preflight(routed, tmp_path / "bad-mapping")
