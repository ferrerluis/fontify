import hashlib
import importlib.util
import json
import re
import socket
import string

import pytest
from conftest import ROOT
from fontTools.ttLib import TTFont

from fontify import FontifyError, build_font
from fontify.review import shape_font, verified_release

EXAMPLE = ROOT / "examples/imagegen"
RAW_TRACE = EXAMPLE / "source/traced-v0.001"


def helper(name):
    spec = importlib.util.spec_from_file_location(
        name, ROOT / "scripts" / (name + ".py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_generated_example_offline_build(tmp_path, monkeypatch):
    def no_network(*a, **k):
        raise AssertionError("generated example attempted network")

    monkeypatch.setattr(socket.socket, "connect", no_network)
    release = build_font(EXAMPLE / "fontify.json", tmp_path / "font")
    d = verified_release(release)
    assert len(d["coverage"]) == 27 and d["approval"]["status"] == "review_required"
    assert d["quality"]["status"] == "preflight_passed"
    assert d["quality"]["visual_review"]["reviewed_glyphs"] == 27
    for field in ("font", "webfont"):
        with TTFont(release.parent / d[field]) as f:
            assert f.getBestCmap() == {
                32: "space",
                **{ord(c): c for c in string.ascii_uppercase},
            }
            assert f["name"].getDebugName(1) == "Fontify Grotesk"
            assert f["glyf"]["space"].numberOfContours == 0
    font = release.parent / d["font"]
    assert shape_font(font, "AV")["advance"] < shape_font(font, "AV", False)["advance"]
    provenance = json.loads((EXAMPLE / "source/provenance.json").read_text())
    assert provenance["provider"] == "built-in image_gen" and provenance["calls"] == 1
    assert (
        hashlib.sha256((EXAMPLE / "source/alphabet-v1.png").read_bytes()).hexdigest()
        == provenance["source_sha256"]
    )


def test_generated_trace_reproduction_and_guards(tmp_path):
    trace = helper("trace_generated_sheet")
    p = trace.trace_sheet(EXAMPLE / "source/trace-plan.json", tmp_path / "trace")
    assert p.read_bytes() == (RAW_TRACE / "fontify.json").read_bytes()
    for expected in (RAW_TRACE / "glyphs").glob("*.svg"):
        assert (
            p.parent / "glyphs" / expected.name
        ).read_bytes() == expected.read_bytes()
    with pytest.raises(FontifyError, match="already exists"):
        trace.trace_sheet(EXAMPLE / "source/trace-plan.json", p.parent)
    import shutil

    source = tmp_path / "changed"
    shutil.copytree(EXAMPLE / "source", source)
    with (source / "alphabet-v1.png").open("ab") as f:
        f.write(b"changed")
    with pytest.raises(FontifyError, match="source image hash"):
        trace.trace_sheet(source / "trace-plan.json", tmp_path / "rejected")


def test_generated_fidelity_of_compiled_outlines(tmp_path):
    review = helper("review_generated_font")
    release = build_font(RAW_TRACE / "fontify.json", tmp_path / "font")
    results = review.review_font(EXAMPLE, release, tmp_path / "review")
    assert len(results["glyphs"]) == 26 and results["minimum_iou"] >= 0.96
    assert results["status"] == "review_required"
    assert (tmp_path / "review/source-comparison.html").is_file()
    html = (tmp_path / "review/source-comparison.html").read_text()
    frames = re.findall(r'<svg viewBox="([^"]+)"', html)
    assert len(frames) == 52
    assert all(frames[i] == frames[i + 1] for i in range(0, 52, 2))
