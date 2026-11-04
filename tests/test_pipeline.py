import json
import string
import subprocess
import sys
from pathlib import Path

import pytest
from conftest import ROOT, edit_project
from fontTools.ttLib import TTFont

from fontify import FontifyError, build_font
from fontify.review import inspect_font, shape_font, verified_release


def test_offline_build_and_reopen(release, monkeypatch):
    def forbidden(*a, **k):
        raise AssertionError("offline build attempted network")

    import socket

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    d = verified_release(release)
    assert len(d["coverage"]) == 27
    assert d["version"] == "1.001"
    assert d["approval"]["checked_glyphs"] == 27
    for field in ("font", "webfont"):
        f = TTFont(release.parent / d[field])
        assert f.getBestCmap() == {
            32: "space",
            **{ord(c): c for c in string.ascii_uppercase},
        }
        assert f["glyf"]["space"].numberOfContours == 0
        assert f["hmtx"]["space"] == (300, 0)
        assert f["name"].getDebugName(1) == "Offline Sans"
        assert f["name"].getDebugName(5) == "Version 1.001"
        assert f["hhea"].ascent == 900 and f["hhea"].descent == -200
        assert f["OS/2"].sCapHeight == 720
        assert "GPOS" in f
        for name in string.ascii_uppercase:
            g = f["glyf"][name]
            assert g.numberOfContours > 0 and g.yMin >= -200 and g.yMax <= 900
            assert f["hmtx"][name][0] == 660
        f.close()
    proof = (release.parent / "proof.html").read_text()
    assert "data:font/woff2;base64," in proof and "THE QUICK BROWN FOX" in proof
    assert (release.parent / "glyph-sheet.svg").is_file()
    # Exercise a build while all socket connections are forbidden.
    built = build_font(
        ROOT / "examples/offline/fontify.json",
        release.parent.parent / "network-disabled",
    )
    assert verified_release(built)["artifacts"] == d["artifacts"]


def test_reproducible_release_and_version_collision(project_dir, tmp_path):
    a = build_font(project_dir / "fontify.json", tmp_path / "a")
    b = build_font(project_dir / "fontify.json", tmp_path / "b")
    assert {p.name: p.read_bytes() for p in a.parent.iterdir()} == {
        p.name: p.read_bytes() for p in b.parent.iterdir()
    }
    assert build_font(project_dir / "fontify.json", tmp_path / "a") == a
    edit_project(project_dir, samples=["AVATAR AVATAR"])
    with pytest.raises(FontifyError, match="increment project version"):
        build_font(project_dir / "fontify.json", tmp_path / "a")
    assert json.loads((tmp_path / "a/current.json").read_text())["version"] == "1.001"
    verified_release(a)


def test_shaping_with_real_harfbuzz(release):
    d = verified_release(release)
    font = release.parent / d["font"]
    for k in d["kerning"]:
        text = k["left"] + k["right"]
        assert (
            shape_font(font, text)["advance"] - shape_font(font, text, False)["advance"]
            == k["value"]
        )
    assert shape_font(font, "AVATAR")["advance"] == 6 * 660 - 70 - 65 - 55
    assert all(
        g["gid"]
        for g in shape_font(font, "THE QUICK BROWN FOX JUMPS OVER THE LAZY DOG")[
            "glyphs"
        ]
    )
    assert shape_font(release.parent / d["webfont"], "AV")["advance"] == 1250
    with pytest.raises(FontifyError, match="U\\+0031"):
        shape_font(font, "A1")
    report = inspect_font(font, "AV")
    assert report["characters"] == " " + string.ascii_uppercase


def test_offline_cli(release, tmp_path):
    d = verified_release(release)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "fontify",
            "inspect",
            str(release.parent / d["font"]),
            "--text",
            "AV",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["shaping"]["advance"] == 1250
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "fontify",
            "build",
            str(ROOT / "examples/offline/fontify.json"),
            "--out",
            str(tmp_path / "cli"),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert Path(json.loads(result.stdout)["manifest"]).is_file()
