import json
import re
from xml.etree import ElementTree as ET

import pytest

from fontify import FontifyError, build_font, load_project
from fontify.outlines import compile_project
from fontify.review import (
    check_approval,
    compare_releases,
)


@pytest.mark.parametrize(
    "kind", ["source", "advance", "mapping", "outline", "construction", "remove"]
)
def test_approval_preserves_baseline(project_dir, kind, tmp_path):
    d = json.loads((project_dir / "fontify.json").read_text())
    if kind == "source":
        p = project_dir / "glyphs/A.svg"
        p.write_text(p.read_text() + "\n")
    elif kind == "advance":
        d["glyphs"][1]["advance"] += 1
    elif kind == "mapping":
        d["glyphs"][1]["unicode"] = "U+0061"
        d["required_characters"] = d["required_characters"].replace("A", "a")
        d["samples"] = ["a"]
    elif kind == "outline":
        d["glyphs"][1]["transform"] = [1, 0, 0, 1, 1, 0]
    elif kind == "construction":
        d["curve_error"] = 0.5
    else:
        d["glyphs"].pop()
        d["required_characters"] = d["required_characters"].replace("Z", "")
        d["samples"] = ["AV"]
    (project_dir / "fontify.json").write_text(json.dumps(d))
    with pytest.raises(FontifyError, match="approved"):
        build_font(project_dir / "fontify.json", tmp_path / "rejected")
    assert not (tmp_path / "rejected/current.json").exists()


def test_approval_added_glyph_is_unreviewed(project_dir):
    d = json.loads((project_dir / "fontify.json").read_text())
    d["glyphs"].append(
        {"name": "A.alt", "unicode": "U+0061", "source": "glyphs/A.svg", "advance": 660}
    )
    (project_dir / "fontify.json").write_text(json.dumps(d))
    p = load_project(project_dir / "fontify.json")
    status = check_approval(p, compile_project(p))
    assert status["unreviewed_glyphs"] == ["A.alt"]
    assert "unreviewed" in status["status"]


def test_proof_overhang_fits_canvas(project_dir, tmp_path):
    from fontTools.pens.boundsPen import BoundsPen
    from fontTools.pens.transformPen import TransformPen
    from fontTools.svgLib.path import parse_path

    from fontify.outlines import affine

    (project_dir / "glyphs/W.svg").write_text(
        '<svg viewBox="0 0 5000 1000"><path d="M-300 100 H4000 V800 H-300 Z"/></svg>'
    )
    d = json.loads((project_dir / "fontify.json").read_text())
    d.update(approval=None, samples=["W"])
    (project_dir / "fontify.json").write_text(json.dumps(d))
    release = build_font(project_dir / "fontify.json", tmp_path / "wide")
    sheet = ET.parse(release.parent / "glyph-sheet.svg")
    ns = "{http://www.w3.org/2000/svg}"
    tile = list(sheet.getroot().find(ns + "g"))[23]
    drawing = tile.find(ns + "g")
    pen = BoundsPen(None)
    parse_path(
        drawing.find(ns + "path").get("d"),
        TransformPen(pen, affine(drawing.get("transform"))),
    )
    x0, y0, x1, y1 = pen.bounds
    assert 0 <= x0 < x1 <= 180 and 0 <= y0 < y1 <= 156
    html = (release.parent / "proof.html").read_text()
    sample = ET.fromstring(
        re.search(r'<svg role="img" aria-label="W".*?</svg>', html, re.S)[0]
    )
    group = sample.find("g")
    outline = group.find("path")
    combined = affine(group.get("transform")).transform(
        affine(outline.get("transform"))
    )
    pen = BoundsPen(None)
    parse_path(outline.get("d"), TransformPen(pen, combined))
    _, _, width, height = map(float, sample.get("viewBox").split())
    x0, y0, x1, y1 = pen.bounds
    assert 0 <= x0 < x1 <= width and 0 <= y0 < y1 <= height


def test_comparison_catches_change_and_tampering(project_dir, tmp_path):
    old = build_font(project_dir / "fontify.json", tmp_path / "out")
    p = load_project(project_dir / "fontify.json")
    d = p.data
    d["version"] = "1.002"
    d["approval"] = None
    d["glyphs"][1]["transform"] = [1, 0, 0, 1, 10, 0]
    (project_dir / "fontify.json").write_text(json.dumps(d))
    new = build_font(project_dir / "fontify.json", tmp_path / "out")
    result = compare_releases(old, new, tmp_path / "diff")
    assert result["changed_glyphs"] == ["A"]
    assert (tmp_path / "diff/comparison.html").is_file()
    (old.parent / "glyph-sheet.svg").write_text("tampered")
    with pytest.raises(FontifyError, match="artifact mismatch"):
        compare_releases(old, new, tmp_path / "bad-diff")
