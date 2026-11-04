import json

import pytest
from fontTools.misc.transform import Identity

from fontify import FontifyError, load_project
from fontify.outlines import compile_project, geometry, read_svg


@pytest.mark.parametrize(
    "change,match",
    [
        (lambda d: d["glyphs"].pop(), "missing required coverage"),
        (lambda d: d["glyphs"][2].update(unicode="U+0041"), "duplicate"),
        (lambda d: d["glyphs"][2].update(name="A"), "duplicate"),
        (lambda d: d["glyphs"][2].update(unicode="U+D800"), "invalid Unicode"),
        (lambda d: d["glyphs"][2].update(unicode="U+110000"), "invalid Unicode"),
        (lambda d: d["kerning"][0].update(right="unknown"), "unknown glyph"),
        (
            lambda d: d["glyphs"][1].update(source="../outside.svg"),
            "inside the project",
        ),
        (lambda d: d["glyphs"][1].update(transform=[1, 0, 0, 0, 0, 0]), "singular"),
        (lambda d: d["glyphs"][1].update(advance=0), "advance"),
        (lambda d: d.update(samples=["lowercase"]), "unmapped"),
        (lambda d: d.update(unkown_setting=True), "unknown fields"),
    ],
)
def test_coverage_errors(project_dir, change, match):
    path = project_dir / "fontify.json"
    d = json.loads(path.read_text())
    change(d)
    path.write_text(json.dumps(d))
    with pytest.raises(FontifyError, match=match):
        load_project(path)


def svg(d):
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 1000"><path d="{d}"/></svg>'.encode()


@pytest.mark.parametrize(
    "data,match",
    [
        (svg("M0 0 L100 0 L100 100"), "open contour"),
        (svg("M0 0 L0 0 L0 100 Z"), "degenerate"),
        (svg("M0 0 L120 120 L0 100 L100 0 Z"), "intersect"),
        (svg("M0 0 H100 V100 H0 Z M20 20 H80 V80 H20 Z"), "same winding"),
        (svg("M0 0 H100 V100 H0 Z M100 20 H150 V80 H100 Z"), "touching"),
        (svg("M0 0 A10 10 0 0 0 100 100 Z"), "arcs"),
        (svg("M0 0 H100 V100 Z").replace(b"<path", b'<path stroke="black"'), "strokes"),
        (
            svg("M0 0 H100 V100 Z").replace(b"<path", b'<path fill-rule="evenodd"'),
            "nonzero",
        ),
        (b'<svg viewBox="0 0 10 10"><text>A</text></svg>', "unsupported SVG"),
        (
            b'<svg viewBox="0 0 10 10"><image href="https://example.com/x"/></svg>',
            "unsupported SVG",
        ),
        (
            b'<!DOCTYPE svg [<!ENTITY a SYSTEM "file:///etc/passwd">]><svg viewBox="0 0 10 10">&a;</svg>',
            "unsafe SVG",
        ),
        (b'<svg><path d="M0 0 H100 V100 Z"/></svg>', "viewBox"),
        (svg("M0 0 L1e999 0 L100 100 Z"), "range"),
    ],
)
def test_vector_rejects_unusable_input(data, match):
    with pytest.raises(FontifyError, match=match):
        geometry(read_svg(data, Identity))


def test_vector_holes_curves_transforms_and_metrics(project_dir):
    data = b'<svg viewBox="0 0 1000 1000"><g transform="translate(20 30) scale(2)"><path d="M0 0 H100 V100 H0 Z M20 20 V80 H80 V20 Z"/></g></svg>'
    rec = read_svg(data, Identity)
    diag, _, _ = geometry(rec)
    assert diag["holes"] == 1 and diag["bounds"] == [20, 30, 220, 230]
    assert diag["vertical_asymmetry"] < 1e-5
    d = json.loads((project_dir / "fontify.json").read_text())
    d["approval"] = None
    d["glyphs"][1]["transform"] = [1, 0, 0, 1, 0, 10000]
    (project_dir / "fontify.json").write_text(json.dumps(d))
    with pytest.raises(FontifyError, match="ascender/descender"):
        compile_project(load_project(project_dir / "fontify.json"))
    # Demo contains cubic and quadratic curves; both survive compilation.
    d["glyphs"][1].pop("transform")
    (project_dir / "fontify.json").write_text(json.dumps(d))
    outlines = compile_project(load_project(project_dir / "fontify.json"))
    assert (
        len(outlines) == 27
        and next(o for o in outlines if o.spec["name"] == "O").diagnostics["holes"] == 1
    )


def test_curved_placement_control_bbox(project_dir, tmp_path):
    from fontTools.ttLib import TTFont

    from fontify import build_font

    path = project_dir / "glyphs/A.svg"
    path.write_bytes(svg("M100 100 Q0 450 100 800 H500 V100 Z"))
    d = json.loads((project_dir / "fontify.json").read_text())
    d["approval"] = None
    (project_dir / "fontify.json").write_text(json.dumps(d))
    release = build_font(project_dir / "fontify.json", tmp_path / "curved")
    manifest = json.loads(release.read_text())
    with TTFont(release.parent / manifest["font"]) as font:
        assert font["glyf"]["A"].xMin == 0
        assert font["hmtx"]["A"][1] == 0
    report = json.loads((release.parent / "validation.json").read_text())
    assert report["glyphs"]["A"]["compiled_bounds"][0] == 50
