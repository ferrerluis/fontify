import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from fontify.model import FontifyError, load_project
from fontify.outlines import compile_project
from fontify.spacing import apply_spacing_plan, save_spacing_plan, spacing_plan


def write_json(path, data):
    path.write_text(json.dumps(data, indent=2) + "\n")


def svg(path, drawing, viewbox="-200 -800 1200 1200"):
    path.write_text(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{viewbox}">'
        f'<g transform="scale(1,-1)"><path d="{drawing}"/></g></svg>\n'
    )


@pytest.fixture
def source(tmp_path):
    root = tmp_path / "source"
    root.mkdir()
    drawings = {
        "H": ("H", "M50 0 H150 V700 H50 Z", 200),
        "C": ("C", "M550 0 H50 V700 H550 V600 H150 V100 H550 Z", 600),
        "V": ("V", "M50 700 L300 0 L550 700 Z", 600),
        "n": ("n", "M50 0 H150 V500 H50 Z", 200),
        "zero": ("0", "M50 0 H150 V700 H50 Z", 200),
        "period": (".", "M50 50 H100 V100 H50 Z", 150),
    }
    data = {
        "schema": 1,
        "family": "Spacing Test",
        "style": "Regular",
        "version": "0.001",
        "units_per_em": 1000,
        "ascender": 800,
        "descender": -200,
        "cap_height": 700,
        "x_height": 500,
        "svg_baseline": 0,
        "required_characters": " HCVn0.",
        "samples": ["HC Vn 0."],
        "approval": None,
        "glyphs": [
            {"name": "space", "unicode": "U+0020", "source": None, "advance": 250}
        ],
    }
    for name, (character, drawing, advance) in drawings.items():
        svg(root / (name + ".svg"), drawing)
        data["glyphs"].append(
            {
                "name": name,
                "unicode": f"U+{ord(character):04X}",
                "source": name + ".svg",
                "advance": advance,
            }
        )
    write_json(root / "fontify.json", data)
    return root / "fontify.json"


def snapshot(root):
    return {
        p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in root.rglob("*")
        if p.is_file()
    }


def test_spacing_plan_is_deterministic_vector_only_and_read_only(source):
    before = snapshot(source.parent)
    plan = spacing_plan(source)
    assert spacing_plan(source) == plan
    assert snapshot(source.parent) == before
    assert plan["glyphs"]["H"]["proposed"] == {
        "left_bearing": 62,
        "right_bearing": 62,
        "advance": 224,
        "translate_x": 12,
    }
    assert plan["glyphs"]["space"]["proposed"]["advance"] == 250
    assert plan["source"]["project_file_sha256"] == before["fontify.json"]
    assert plan["plan_sha256"]


def test_spacing_viewbox_padding_does_not_affect_measurement(source):
    first = spacing_plan(source)
    p = source.parent / "C.svg"
    p.write_text(p.read_text().replace("-200 -800 1200 1200", "-1000 -1000 9000 9000"))
    padded = spacing_plan(source)
    for name in first["glyphs"]:
        assert (
            first["glyphs"][name]["measurement"]
            == padded["glyphs"][name]["measurement"]
        )
        assert first["glyphs"][name]["proposed"] == padded["glyphs"][name]["proposed"]
    assert first["pairs"] == padded["pairs"]
    assert (
        first["glyphs"]["C"]["source_sha256"] != padded["glyphs"]["C"]["source_sha256"]
    )


def test_spacing_horizontal_placement_does_not_change_optical_bearings(source):
    first = spacing_plan(source)
    data = json.loads(source.read_text())
    for g in data["glyphs"]:
        if g["source"]:
            g["transform"] = [1, 0, 0, 1, 400, 0]
            g["advance"] += 400
    write_json(source, data)
    shifted = spacing_plan(source)
    for name in first["glyphs"]:
        assert (
            first["glyphs"][name]["measurement"]
            == shifted["glyphs"][name]["measurement"]
        )
        for field in ("left_bearing", "right_bearing", "advance"):
            assert first["glyphs"][name]["proposed"].get(field) == shifted["glyphs"][
                name
            ]["proposed"].get(field)
    assert first["pairs"] == shifted["pairs"]


def test_spacing_open_counter_depth_is_capped_and_groups_have_distinct_zones(source):
    plan = spacing_plan(
        source, {"groups": {"caps": {"counter_depth": 100, "overshoot": 0}}}
    )
    c = plan["glyphs"]["C"]["measurement"]
    assert c["white_area"]["right"] == 50000
    assert c["uncapped_white_area"]["right"] == 200000
    assert c["mean_white_depth"]["right"] <= 100
    for name, group, zone in (
        ("H", "caps", [0, 700]),
        ("n", "lowercase", [0, 500]),
        ("zero", "digits", [0, 700]),
        ("period", "punctuation", [-200, 700]),
    ):
        assert plan["glyphs"][name]["group"] == group
        assert plan["glyphs"][name]["measurement"]["zone"] == zone
    custom = spacing_plan(
        source,
        {
            "glyph_groups": {"C": "lowercase"},
            "groups": {"lowercase": {"zone": [100, 300], "overshoot": 0}},
        },
    )
    assert custom["glyphs"]["C"]["measurement"]["active_height"] == 200


def test_spacing_overshoot_is_measured_only_within_configured_limit(source):
    svg(source.parent / "H.svg", "M50 -20 H150 V720 H50 Z")
    no = spacing_plan(source, {"groups": {"caps": {"overshoot": 0}}})
    yes = spacing_plan(source, {"groups": {"caps": {"overshoot": 12}}})
    assert no["glyphs"]["H"]["measurement"]["measured_zone"] == [0, 700]
    assert yes["glyphs"]["H"]["measurement"]["measured_zone"] == [-12, 712]


def test_spacing_collision_guard_overrules_unsafe_explicit_pair(source):
    config = {
        "pairs": [],
        "pair_overrides": [
            {
                "left": "H",
                "right": "H",
                "value": -500,
                "reason": "Deliberately unsafe regression input.",
            }
        ],
        "collision_gap": 10,
    }
    plan = spacing_plan(source, config)
    pair = next(p for p in plan["pairs"] if p["left"] == "H" and p["right"] == "H")
    assert pair["requested_value"] == -500
    assert pair["value"] >= -114
    assert pair["collision_adjusted"]
    assert pair["minimum_gap_before_kerning"] + pair["value"] >= 10


def test_spacing_collision_guard_checks_outside_reference_zone(source):
    # The broad cap lies above the lowercase zone and must still prevent collision.
    svg(source.parent / "n.svg", "M50 0 H150 V600 H500 V700 H50 Z")
    plan = spacing_plan(
        source,
        {
            "pairs": [{"left": "n", "right": "n"}],
            "groups": {"lowercase": {"overshoot": 0}},
            "pair_overrides": [
                {
                    "left": "n",
                    "right": "n",
                    "value": -500,
                    "reason": "Test whole-outline guard.",
                }
            ],
        },
    )
    pair = next(p for p in plan["pairs"] if p["left"] == "n" and p["right"] == "n")
    assert pair["collision_adjusted"]
    assert pair["minimum_gap_before_kerning"] + pair["value"] >= 10


def test_spacing_threshold_omits_small_proposals_but_keeps_explicit_override(source):
    base = {
        "pairs": [{"left": "H", "right": "H"}],
        "glyph_overrides": {
            "H": {
                "left_bearing": 65,
                "right_bearing": 65,
                "reason": "Set a six-unit optical difference.",
            }
        },
    }
    small = spacing_plan(source, {**base, "kerning_threshold": 10})
    assert (
        next(p for p in small["pairs"] if p["left"] == p["right"] == "H")[
            "requested_value"
        ]
        == -6
    )
    assert (
        next(p for p in small["pairs"] if p["left"] == p["right"] == "H")["status"]
        == "omitted"
    )
    assert not any(p["left"] == p["right"] == "H" for p in small["kerning"])
    exact = spacing_plan(source, {**base, "kerning_threshold": 6})
    assert (
        next(p for p in exact["pairs"] if p["left"] == p["right"] == "H")["value"] == -6
    )
    override = spacing_plan(
        source,
        {
            **base,
            "pair_overrides": [
                {
                    "left": "H",
                    "right": "H",
                    "value": -4,
                    "reason": "Keep an intentional subtle adjustment.",
                }
            ],
        },
    )
    assert (
        next(p for p in override["pairs"] if p["left"] == p["right"] == "H")["value"]
        == -4
    )


def test_spacing_existing_authored_kerning_is_preserved_even_when_pairs_filtered(
    source,
):
    data = json.loads(source.read_text())
    data["kerning"] = [{"left": "H", "right": "H", "value": -3}]
    write_json(source, data)
    plan = spacing_plan(source, {"pairs": []})
    assert data["kerning"][0] in plan["kerning"]
    assert "preserve explicit existing" in " ".join(
        next(p for p in plan["pairs"] if p["left"] == p["right"] == "H")["reasons"]
    )


def test_spacing_candidate_preserves_sources_and_shapes_and_unbinds_stale_intent(
    source, tmp_path
):
    data = json.loads(source.read_text())
    data["quality"] = "quality.json"
    write_json(source, data)
    write_json(
        source.parent / "quality.json",
        {"schema": 2, "glyphs": {"H": {"decisions": {"confirmed": True}}}},
    )
    before = snapshot(source.parent)
    plan = spacing_plan(
        source,
        {
            "glyph_overrides": {
                "space": {"advance": 280, "reason": "Reviewed word-space target."}
            }
        },
    )
    output = apply_spacing_plan(source, plan, tmp_path / "candidate", "0.002")
    candidate = load_project(output)
    assert candidate.data["quality"] is None
    assert candidate.data["approval"] is None
    assert candidate.data["version"] == "0.002"
    assert candidate.glyphs[0]["advance"] == 280
    assert snapshot(source.parent) == before
    assert (output.parent / "quality.json").read_bytes() == (
        source.parent / "quality.json"
    ).read_bytes()
    original = compile_project(load_project(source))
    modified = compile_project(candidate)
    for a, b in zip(original, modified):
        assert a.source_hash == b.source_hash
        shift = plan["glyphs"][a.spec["name"]]["proposed"]["translate_x"]
        for (opa, ptsa), (opb, ptsb) in zip(a.record.value, b.record.value):
            assert opa == opb
            assert tuple((x + shift, y) for x, y in ptsa) == ptsb
    assert (
        json.loads((output.parent / "spacing-changes.json").read_text())["plan_sha256"]
        == plan["plan_sha256"]
    )


def test_spacing_approved_plan_is_allowed_but_apply_is_protected(source, tmp_path):
    data = json.loads(source.read_text())
    data["approval"] = "approval.json"
    write_json(source, data)
    write_json(source.parent / "approval.json", {"fixture": True})
    before = snapshot(source.parent)
    plan = spacing_plan(source)
    assert plan["source"]["approved"]
    with pytest.raises(FontifyError, match="approved projects are protected"):
        apply_spacing_plan(source, plan, tmp_path / "candidate", "0.002")
    assert snapshot(source.parent) == before
    assert not (tmp_path / "candidate").exists()


def test_spacing_stale_tampered_and_overwrite_plans_are_rejected(source, tmp_path):
    planfile = save_spacing_plan(source, tmp_path / "plan.json")
    with pytest.raises(FontifyError, match="already exists"):
        save_spacing_plan(source, planfile)
    plan = json.loads(planfile.read_text())
    altered = copy.deepcopy(plan)
    altered["glyphs"]["H"]["proposed"]["advance"] += 1
    with pytest.raises(FontifyError, match="stale or changed"):
        apply_spacing_plan(source, altered, tmp_path / "candidate", "0.002")
    with pytest.raises(FontifyError, match="different version"):
        apply_spacing_plan(source, plan, tmp_path / "candidate", "0.001")
    with pytest.raises(FontifyError, match="outside the source"):
        apply_spacing_plan(source, plan, source.parent / "candidate", "0.002")
    candidate = apply_spacing_plan(source, planfile, tmp_path / "candidate", "0.002")
    before = snapshot(candidate.parent)
    with pytest.raises(FontifyError, match="new directory"):
        apply_spacing_plan(source, plan, candidate.parent, "0.003")
    assert snapshot(candidate.parent) == before
    (source.parent / "H.svg").write_text((source.parent / "H.svg").read_text() + "\n")
    with pytest.raises(FontifyError, match="stale or changed"):
        apply_spacing_plan(source, plan, tmp_path / "other", "0.002")


@pytest.mark.parametrize(
    "config",
    [
        {"mystery": 1},
        {"groups": {"caps": {"counter_depth": -1}}},
        {"groups": {"caps": {"zone": [5, 5]}}},
        {"glyph_groups": {"missing": "caps"}},
        {"pair_overrides": [{"left": "H", "right": "H", "value": 0}]},
        {"collision_gap": float("nan")},
        {
            "glyph_overrides": {
                "H": {
                    "advance": 100,
                    "right_bearing": 10,
                    "reason": "Conflicting dimensions.",
                }
            }
        },
    ],
)
def test_spacing_config_rejects_invalid_or_ambiguous_values(source, config):
    with pytest.raises(FontifyError):
        spacing_plan(source, config)


def test_spacing_spacing_import_and_execution_have_no_raster_dependencies(source):
    script = """
import importlib.abc
import sys
class NoRaster(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in ('PIL', 'numpy', 'cv2', 'cairosvg'):
            raise AssertionError('unexpected raster import: ' + fullname)
sys.meta_path.insert(0, NoRaster())
from fontify.spacing import spacing_plan
spacing_plan(sys.argv[1])
"""
    result = subprocess.run(
        [sys.executable, "-c", script, str(source)],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_spacing_curved_extrema_compile_with_integer_placement_and_gpos(tmp_path):
    from conftest import ROOT
    from fontTools.pens.recordingPen import RecordingPen
    from fontTools.ttLib import TTFont

    from fontify import build_font

    original_root = ROOT / "examples/recraft-mellow"
    data = json.loads((original_root / "fontify.json").read_text())
    data.update(
        approval=None,
        quality=None,
        required_characters=" C",
        samples=["CC C"],
        kerning=[],
    )
    data["glyphs"] = [g for g in data["glyphs"] if g["name"] in ("space", "C")]
    root = tmp_path / "curved"
    root.mkdir()
    for spec in data["glyphs"]:
        if spec["source"]:
            destination = root / spec["source"]
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes((original_root / spec["source"]).read_bytes())
    source = root / "fontify.json"
    write_json(source, data)
    plan = spacing_plan(
        source,
        {
            "pair_overrides": [
                {
                    "left": "C",
                    "right": "C",
                    "value": -35,
                    "reason": "Exercise the actual exported GPOS pair.",
                }
            ]
        },
    )
    proposed = plan["glyphs"]["C"]["proposed"]
    assert isinstance(proposed["advance"], int)
    assert isinstance(proposed["translate_x"], int)
    assert proposed["left_bearing"] >= 0
    assert proposed["right_bearing"] >= 0
    output = apply_spacing_plan(source, plan, tmp_path / "candidate", "0.003")
    original = next(
        o for o in compile_project(load_project(source)) if o.spec["name"] == "C"
    )
    revised = next(
        o for o in compile_project(load_project(output)) if o.spec["name"] == "C"
    )
    a, b = RecordingPen(), RecordingPen()
    original.glyph.draw(a, None)
    revised.glyph.draw(b, None)
    for (op1, points1), (op2, points2) in zip(a.value, b.value):
        assert op1 == op2
        assert (
            tuple(
                None if p is None else (p[0] + proposed["translate_x"], p[1])
                for p in points1
            )
            == points2
        )
    manifest_path = build_font(output, tmp_path / "build", draft=True)
    manifest = json.loads(manifest_path.read_text())
    with TTFont(manifest_path.parent / manifest["font"]) as font:
        assert "GPOS" in font
        assert font["hmtx"]["C"][0] == proposed["advance"]


def test_spacing_collision_guard_still_checks_pairs_excluded_from_optical_selection(
    source,
):
    plan = spacing_plan(
        source,
        {
            "pairs": [],
            "glyph_overrides": {
                "H": {
                    "left_bearing": 0,
                    "right_bearing": 0,
                    "reason": "Test safety even with a zero optical pair selection.",
                }
            },
        },
    )
    pair = next(p for p in plan["pairs"] if p["left"] == p["right"] == "H")
    assert not pair["selected_for_optical"]
    assert pair["collision_adjusted"]
    assert pair["value"] >= 10


def test_spacing_no_reference_ink_and_blank_overrides_are_explicit(source):
    plan = spacing_plan(
        source, {"groups": {"caps": {"zone": [-200, -100], "overshoot": 0}}}
    )
    h = plan["glyphs"]["H"]
    assert h["measurement"]["active_height"] == 0
    assert h["proposed"]["advance"] == h["current"]["advance"]
    assert h["proposed"]["translate_x"] == 0
    with pytest.raises(FontifyError, match="blank glyph overrides"):
        spacing_plan(
            source,
            {
                "glyph_overrides": {
                    "space": {
                        "left_bearing": 50,
                        "reason": "Invalid blank geometry request.",
                    }
                }
            },
        )


@pytest.mark.parametrize("exists", [False, True])
def test_spacing_output_symlinks_are_never_followed(source, tmp_path, exists):
    target = tmp_path / "target"
    if exists:
        target.mkdir()
    link = tmp_path / "candidate-link"
    link.symlink_to(target, target_is_directory=True)
    plan = spacing_plan(source)
    with pytest.raises(FontifyError, match="symlink"):
        apply_spacing_plan(source, plan, link, "0.002")
    file_target = tmp_path / "file-target"
    if exists:
        file_target.write_text("Keep unchanged.")
    file_link = tmp_path / "plan-link.json"
    file_link.symlink_to(file_target)
    with pytest.raises(FontifyError, match="symlink"):
        save_spacing_plan(source, file_link)
    assert target.exists() == exists
    assert file_target.exists() == exists
    if exists:
        assert file_target.read_text() == "Keep unchanged."


def test_spacing_pair_budget_is_checked_before_compilation(source, monkeypatch):
    import fontify.spacing as spacing

    monkeypatch.setattr(spacing, "MAX_PAIR_CHECKS", 36)
    assert spacing_plan(source)
    monkeypatch.setattr(spacing, "MAX_PAIR_CHECKS", 35)

    def unexpected_compile(project):
        raise AssertionError("Pair budget must fail before expensive geometry work.")

    monkeypatch.setattr(spacing, "compile_project", unexpected_compile)
    with pytest.raises(FontifyError, match="bounded collision-check scope"):
        spacing_plan(source, {"pairs": []})
