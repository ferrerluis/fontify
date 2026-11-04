import hashlib
import importlib.util
import json
import shutil
import socket
import string

import pytest
from conftest import ROOT
from fontTools.ttLib import TTFont
from PIL import Image

from fontify import FontifyError, build_font, release_font
from fontify.review import shape_font, verified_release

EXAMPLE = ROOT / "examples/recraft-mellow"
RAW = EXAMPLE / "source/extracted-v0.001"


def helper(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def no_network(*args, **kwargs):
    raise AssertionError("offline Recraft example attempted a network call")


def test_recraft_extraction_reproduces_vectors_and_components(tmp_path, monkeypatch):
    monkeypatch.setattr(socket.socket, "connect", no_network)
    prepare = helper("prepare_recraft_sheet").prepare
    result = prepare(EXAMPLE / "source/extraction-plan.json", tmp_path / "extracted")
    assert result.read_bytes() == (RAW / "fontify.json").read_bytes()
    expected = list((RAW / "glyphs").glob("*.svg"))
    assert len(expected) == 52 and len({p.name.lower() for p in expected}) == 52
    for p in expected:
        assert (result.parent / "glyphs" / p.name).read_bytes() == p.read_bytes()
    manifest = build_font(result, tmp_path / "raw-font", draft=True)
    d = verified_release(manifest)
    with TTFont(manifest.parent / d["font"]) as f:
        assert (
            f["glyf"]["i"].numberOfContours == 2
            and f["glyf"]["j"].numberOfContours == 2
        )
    journal = json.loads((result.parent / "extraction.json").read_text())
    assert len(journal["glyphs"]) == 52
    assert sum(g["collapsed_subunit_edges_removed"] for g in journal["glyphs"]) > 0


def test_recraft_extraction_refuses_stale_source_and_overwrite(tmp_path):
    prepare = helper("prepare_recraft_sheet").prepare
    occupied = tmp_path / "occupied"
    occupied.mkdir()
    with pytest.raises(FontifyError, match="already exists"):
        prepare(EXAMPLE / "source/extraction-plan.json", occupied)
    source = tmp_path / "source"
    source.mkdir()
    for name in ("generated-alphabet.svg", "fontify-base.json", "extraction-plan.json"):
        shutil.copyfile(EXAMPLE / "source" / name, source / name)
    p = source / "generated-alphabet.svg"
    p.write_bytes(p.read_bytes() + b"\n")
    with pytest.raises(FontifyError, match="source SVG hash changed"):
        prepare(source / "extraction-plan.json", tmp_path / "rejected")
    assert not (tmp_path / "rejected").exists()


def test_recraft_offline_reviewed_font_preserves_the_generated_design(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(socket.socket, "connect", no_network)
    final = release_font(EXAMPLE / "fontify.json", tmp_path / "reviewed")
    raw = build_font(RAW / "fontify.json", tmp_path / "raw", draft=True)
    d = verified_release(final)
    before = verified_release(raw)
    assert len(d["coverage"]) == 53 and d["quality"]["status"] == "preflight_passed"
    assert d["quality"]["visual_review"]["reviewed_glyphs"] == 53
    changed = {
        n
        for n, g in d["glyphs"].items()
        if g["compiled_sha256"] != before["glyphs"][n]["compiled_sha256"]
    }
    assert changed == {"H", "Z", "q"}
    for field in ("font", "webfont"):
        with TTFont(final.parent / d[field]) as font:
            assert font.getBestCmap() == {
                32: "space",
                **{ord(c): c for c in string.ascii_letters},
            }
            assert font["glyf"]["space"].numberOfContours == 0
            assert font["hmtx"]["space"] == (280, 0)
            assert font["hhea"].ascent == 950 and font["hhea"].descent == -350
            assert font["OS/2"].sCapHeight == 700 and font["OS/2"].sxHeight == 450
    for pair in d["kerning"]:
        text = pair["left"] + pair["right"]
        font = final.parent / d["font"]
        assert (
            shape_font(font, text)["advance"] - shape_font(font, text, False)["advance"]
            == pair["value"]
        )
    assert all(
        g["gid"]
        for g in shape_font(
            final.parent / d["font"], "The Quick Brown Fox Jumps Over The Lazy Dog"
        )["glyphs"]
    )
    provenance = json.loads((EXAMPLE / "source/provenance.json").read_text())
    assert (
        provenance["model"] == "recraftv4_1_vector"
        and provenance["generation_calls"] == 1
        and provenance["credits_used"] == 4
    )
    assert (
        provenance["source_sha256"]
        == hashlib.sha256(
            (EXAMPLE / "source/generated-alphabet.svg").read_bytes()
        ).hexdigest()
    )


def test_proof_overhang_review_sheets_fit_descenders(tmp_path):
    release = release_font(EXAMPLE / "fontify.json", tmp_path / "font")
    d = verified_release(release)
    font = release.parent / d["font"]
    out = tmp_path / "sheets"
    helper("render_quality_review").render(
        font,
        font,
        out,
        before_label="SOURCE",
        after_label="CANDIDATE",
        samples=["Hello there", "The Quick Brown Fox"],
    )
    index = json.loads((out / "index.json").read_text())
    height = index["layout"]["row_height"]
    assert {c for item in index["sheets"] for c in item["glyphs"]} == set(
        string.ascii_letters
    )
    # g/j/p/q/y previously ran into the next row/header or were cropped below it.
    for item in index["sheets"]:
        if item["path"] == "spacing-and-weight.png":
            continue
        with Image.open(out / item["path"]) as im:
            assert im.height == height * 2
            for y in (height - 10, im.height - 10):
                assert im.crop((0, y, im.width, y + 10)).getextrema() == (
                    (250, 250),
                    (249, 249),
                    (246, 246),
                )
