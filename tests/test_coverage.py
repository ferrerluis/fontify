"""Product coverage checks use synthetic artwork, never a claimed real typeface."""

import json
import re
import string
import subprocess
import sys
import unicodedata as ud

import pytest
from conftest import ROOT
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont

from fontify import FontifyError, build_font, load_project
from fontify.cli import main
from fontify.coverage import (
    BLANKS,
    CATALOG,
    DEFAULT_LANGUAGES,
    character_record,
    check_font_coverage,
    configuration,
    coverage_check,
    coverage_plan,
    repertoire,
    specimens,
)
from fontify.review import shape_font, verified_release


def synthetic_project(tmp_path, config=None):
    root = tmp_path / "synthetic"
    root.mkdir()
    (root / "ink.svg").write_text(
        '<svg viewBox="0 0 1000 1000"><path d="M80 300H420V800H80Z M200 190H260V240H200Z"/></svg>'
    )
    config = config or configuration()
    data = dict(
        schema=1,
        family="Coverage Fixture",
        style="Regular",
        version="0.001",
        required_characters=repertoire(config),
        coverage=config,
        samples=["é"],
        glyphs=[
            dict(
                name=f"uni{ord(c):04X}",
                unicode=f"U+{ord(c):04X}",
                source=None if c in BLANKS else "ink.svg",
                advance=(150 if c == "\u202f" else 300) if c in BLANKS else 500,
            )
            for c in repertoire(config)
        ],
    )
    path = root / "fontify.json"
    path.write_text(json.dumps(data))
    return path


@pytest.fixture(scope="module")
def compiled_coverage(tmp_path_factory):
    root = tmp_path_factory.mktemp("language-coverage")
    config = configuration(
        list(CATALOG["languages"]),
        request_note="Explicit QA request for every catalog language; never a default.",
    )
    project = synthetic_project(root, config)
    manifest = build_font(project, root / "build", draft=True)
    return project, manifest


def test_language_inventory_exact_default_and_mapping():
    plan = coverage_plan()
    chars = set(plan["required_characters"])
    accents = "àáâãæçèéêëìíîïñòóôõùúûüÿœ"
    expected = set(
        string.printable[:-6]
        + " "
        + accents
        + accents.upper()
        + "¡¿«»‘’“”…–—ªº\u00a0\u202f"
    )
    assert chars == expected and len(chars) == 160
    assert CATALOG["keyboard_specials"] == "!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~"
    assert set(CATALOG["keyboard_specials"]) == set(string.punctuation)
    assert plan["coverage"]["languages"] == list(DEFAULT_LANGUAGES)
    assert {"de", "pl", "cy"}.isdisjoint(plan["coverage"]["languages"])
    assert not (chars & set("ĀāŁłẞßİıÞþÐð"))
    assert {"en", "es", "fr", "it", "pt"}.issubset(CATALOG["languages"])
    assert set(character_record("Ñ")["languages"]) & set(DEFAULT_LANGUAGES) == {"es"}
    assert set(character_record("Œ")["languages"]) & set(DEFAULT_LANGUAGES) == {"fr"}
    assert "ò" not in CATALOG["languages"]["pt"]["letters"]
    assert "ó" in CATALOG["languages"]["it"]["letters"]
    for row in plan["characters"]:
        assert row["unicode"] == f"U+{ord(row['character']):04X}"
        assert row["description"] == ud.name(row["character"])


def test_language_inventory_researched_main_sets_and_documented_additions():
    additions = {"it": "ó", "tr": "âîû", "de": "ẞ"}
    for lang, item in CATALOG["languages"].items():
        # Frozen external exemplars independently protect the explicit inventories.
        main = set(re.sub(r"[ {}]", "", item["exemplar"]))
        if lang == "pt":
            main.remove("ò")  # Modern grave rule; historical CLDR inheritance.
        if lang == "ca":
            main.remove("·")  # Orthographic punctuation, not an alphabetic glyph.
        main.update(additions.get(lang, ""))
        expected = main | {c.upper() for c in main if len(c.upper()) == 1}
        assert set(item["letters"]) == expected, lang
        assert item["source"].endswith(f"/release-48/common/main/{lang}.xml")


def test_language_inventory_skill_table_is_current():
    run = subprocess.run(
        [sys.executable, "scripts/render_character_inventory.py", "--check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert run.returncode == 0, run.stdout + run.stderr


@pytest.mark.parametrize("language", sorted(CATALOG["languages"]))
def test_language_extension_selected_targets_and_specimens(language):
    plan = coverage_plan([language], request_note=f"User requested {language}.")
    assert set(plan["coverage"]["languages"]) == set(DEFAULT_LANGUAGES) | {language}
    assert set(plan["required_characters"]) == set(repertoire()) | set(
        CATALOG["languages"][language]["letters"]
        + CATALOG["languages"][language]["punctuation"]
    )
    for text in plan["samples"]:
        assert set(ud.normalize("NFC", text)) <= set(plan["required_characters"])
    if language == "tr":
        assert set("İıÂâÎîÛû") <= set(plan["required_characters"])
        assert any("İSTANBUL" in s for s in plan["samples"])
    if language == "de":
        assert "ẞ" in plan["required_characters"] and any(
            "STRAẞE" in s for s in plan["samples"]
        )
    if language == "ro":
        assert set("ȘșȚț") <= set(plan["required_characters"])
        assert not (set("ŞşŢţ") & set(plan["required_characters"]))


def test_language_extension_guards_and_cli(tmp_path, capsys):
    output = tmp_path / "plan.json"
    assert (
        main(
            [
                "coverage-plan",
                "--language",
                "pl",
                "--request-note",
                "User requested Polish.",
                "--output",
                str(output),
            ]
        )
        == 0
    )
    plan = json.loads(output.read_text())
    assert "Ł" in plan["required_characters"] and "Þ" not in plan["required_characters"]
    assert "pl" in json.loads(capsys.readouterr().out)["coverage"]["languages"]
    assert main(["coverage-plan", "--output", str(output)]) == 1
    capsys.readouterr()
    assert (
        coverage_plan(
            additional_characters="A\u0304ā", request_note="User asked for macron A."
        )["coverage"]["additional_characters"]
        == "Āā"
    )
    for args in [
        dict(languages=["all"]),
        dict(languages=["nl"]),
        dict(languages=["de"]),
        dict(additional_characters="Ā"),
        dict(additional_characters="j\u0301", request_note="Uncomposable test."),
        dict(languages="de"),
    ]:
        with pytest.raises(FontifyError):
            coverage_plan(**args)


def test_language_contract_required_cannot_be_reduced(tmp_path):
    path = synthetic_project(tmp_path)
    raw = json.loads(path.read_text())
    assert coverage_check(load_project(path))["status"] == "passed"
    for transform in (
        lambda d: d.update(required_characters="é"),
        lambda d: d["glyphs"].pop(),
        lambda d: d["coverage"].update(profile="all-latin"),
        lambda d: d["coverage"].update(languages=["de"]),
        lambda d: d["coverage"].update(unknown=True),
    ):
        data = json.loads(json.dumps(raw))
        transform(data)
        path.write_text(json.dumps(data))
        with pytest.raises(FontifyError):
            load_project(path)
    # Removing languages from the contract does not remove the five defaults.
    raw["coverage"]["languages"] = []
    path.write_text(json.dumps(raw))
    assert coverage_check(load_project(path))["character_count"] == 160


def test_language_contract_subset_and_source_only_disclosure(tmp_path, capsys):
    assert main(["coverage-check", str(ROOT / "examples/offline/fontify.json")]) == 1
    report = json.loads(capsys.readouterr().out)
    assert report["compiled_status"] == "not_run"
    assert "U+00E9" in {r["unicode"] for r in report["missing_mappings"]}
    path = synthetic_project(tmp_path)
    assert main(["coverage-check", str(path)]) == 0
    assert json.loads(capsys.readouterr().out)["compiled_status"] == "not_run"
    with pytest.raises(FontifyError, match="both"):
        coverage_check(load_project(path), "only.ttf")
    raw = json.loads(path.read_text())
    next(g for g in raw["glyphs"] if g["unicode"] == "U+00A0")["source"] = "ink.svg"
    path.write_text(json.dumps(raw))
    with pytest.raises(FontifyError, match="blank"):
        load_project(path)


def test_language_compiled_formats_and_raw_normalization(compiled_coverage, capsys):
    project_path, manifest = compiled_coverage
    project = load_project(project_path)
    data = verified_release(manifest)
    config = project.data["coverage"]
    assert not (manifest.parent.parent / "current.json").exists()
    for field in ("font", "webfont"):
        path = manifest.parent / data[field]
        with TTFont(path) as font:
            assert set(font.getBestCmap()) == set(map(ord, repertoire(config)))
            assert (
                0x301 not in font.getBestCmap()
            )  # HarfBuzz must consume raw decompositions.
            assert font["hmtx"]["uni0020"][0] == font["hmtx"]["uni00A0"][0] == 300
        for text in ("é", "ñ", "ç", "Ÿ", "İ", "ș", "ŵ"):
            decomposed = ud.normalize("NFD", text)
            assert decomposed != text
            raw = shape_font(path, decomposed)
            assert [g["name"] for g in raw["glyphs"]] == [f"uni{ord(text):04X}"]
            assert raw["glyphs"][0]["x_advance"] == 500
            assert raw["glyphs"][0]["x_offset"] == raw["glyphs"][0]["y_offset"] == 0
    assert (
        main(
            [
                "coverage-check",
                str(project_path),
                "--font",
                str(manifest.parent / data["font"]),
                "--webfont",
                str(manifest.parent / data["webfont"]),
            ]
        )
        == 0
    )
    report = json.loads(capsys.readouterr().out)
    assert report["compiled_status"] == "passed"
    assert set(report["compiled"]) == {"ttf", "woff2"}
    validation = json.loads((manifest.parent / "validation.json").read_text())
    assert validation["shaping"]["language_coverage"]["status"] == "passed"
    assert all(sample in project.data["samples"] for sample in specimens(config))
    assert any(ud.normalize("NFC", s) != s for s in project.data["samples"])
    proof = (manifest.parent / "proof.html").read_text()
    assert "input.value.normalize('NFC')" in proof
    assert "L’œuvre" in proof and "pingüino" in proof


@pytest.mark.parametrize(
    "corruption", ["missing", "notdef", "blank", "wide_nbsp", "wide_narrow"]
)
def test_language_compiled_rejects_export_defects(
    compiled_coverage, tmp_path, corruption
):
    project_path, manifest = compiled_coverage
    config = load_project(project_path).data["coverage"]
    data = verified_release(manifest)
    bad = tmp_path / "bad.ttf"
    with TTFont(manifest.parent / data["font"]) as font:
        if corruption in ("missing", "notdef"):
            for table in font["cmap"].tables:
                if table.isUnicode():
                    if corruption == "missing":
                        table.cmap.pop(0xE9, None)
                    else:
                        table.cmap[0xE9] = ".notdef"
        elif corruption == "blank":
            font["glyf"]["uni00E9"] = TTGlyphPen(None).glyph()
        else:
            font["hmtx"]["uni00A0" if corruption == "wide_nbsp" else "uni202F"] = (
                600,
                0,
            )
        font.save(bad)
    with pytest.raises(FontifyError, match="coverage missing|no ink|advance|no wider"):
        check_font_coverage(bad, config)
