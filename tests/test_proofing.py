"""Synthetic proofs exercise mechanics; mocked receipts are never design approval."""

import copy
import json
import os
import shutil

import pytest
from conftest import ROOT

from fontify import FontifyError, build_font, load_project, release_font
from fontify.outlines import compile_project, digest
from fontify.proofing import (
    FINDING_AREAS,
    capture_browser_proofs,
    check_size_reviews,
    proof_samples,
    proofing_plan,
    sha256,
    validate_proofing,
    write_size_proofs,
)
from fontify.quality import REVIEW_CHECKS, audit_project, check_review, load_profile
from fontify.rubrics import plan_profile


def write(path, data):
    path.write_text(json.dumps(data, indent=2) + "\n")


@pytest.fixture
def sized(tmp_path):
    root = tmp_path / "source"
    root.mkdir()
    data = json.loads((ROOT / "examples/offline/fontify.json").read_text())
    characters = " HIl1O0.,Aa"
    data.update(
        approval=None,
        quality=None,
        required_characters=characters,
        samples=["H Il1 O0 Aa.,"],
        kerning=[],
    )
    (root / "shape.svg").write_text(
        '<svg viewBox="0 0 660 1000"><path d="M50 800 V100 H250 V350 H410 V100 H610 V800 H410 V500 H250 V800 Z"/></svg>'
    )
    # Same synthetic shape for each mapped codepoint: not a real typeface review.
    data["glyphs"] = [
        {
            "name": f"uni{ord(c):04X}",
            "unicode": f"U+{ord(c):04X}",
            "source": None if c == " " else "shape.svg",
            "advance": 300 if c == " " else 660,
        }
        for c in characters
    ]
    path = root / "fontify.json"
    write(path, data)
    project = load_project(path)
    profile = plan_profile(
        project,
        compile_project(project),
        "geometric",
        "Synthetic gate fixture, not typographic approval.",
    )
    for item in profile["glyphs"].values():
        item["decisions"]["confirmed"] = True
        item["note"] = "Synthetic exact geometry fixture for size evidence gate tests."
    write(root / "quality.json", profile)
    data["quality"] = "quality.json"
    write(path, data)
    project = load_project(path)
    manifest_path = build_font(project, tmp_path / "draft", draft=True)
    manifest = json.loads(manifest_path.read_text())
    font = manifest_path.parent / manifest["font"]
    woff = manifest_path.parent / manifest["webfont"]
    bundle = write_size_proofs(font, woff, root / "evidence", project)
    report = audit_project(project, compile_project(project), font, woff)
    return project, load_profile(project), bundle, report, manifest_path


def mock_receipt(sized):
    """Test-only fake browser attestations; never emitted by a production renderer."""
    project, profile, bundle, report, manifest = sized
    records = copy.deepcopy(bundle["size_reviews"])
    for record in records:
        if record["format"] == "woff2":
            source = next(
                r
                for r in bundle["size_reviews"]
                if r["format"] == "ttf" and r["size"] == record["size"]
            )
            record.update(
                proof=source["proof"],
                proof_sha256=source["proof_sha256"],
                pixel_dimensions=source["pixel_dimensions"],
                renderer={
                    "kind": "browser",
                    "name": "Chromium",
                    "version": "TEST-ONLY",
                    "engine": "Blink",
                    "user_agent": "TEST MOCK, NOT A REAL BROWSER CAPTURE",
                },
                font_loaded=True,
                html_sha256=bundle["html_sha256"],
                html="evidence/size-proof.html",
            )
        record["proof"] = "evidence/" + record["proof"]
        record["status"] = "passed"
        record["findings"] = {
            area: {
                "status": "not_applicable"
                if area in record["samples"] and not record["samples"][area]
                else "passed",
                "notes": f"Mock finding for {area} at {record['size']} in {record['format']}; gate test only, not a real review.",
            }
            for area in FINDING_AREAS
        }
    evidence = [
        {"path": r["proof"], "sha256": r["proof_sha256"]}
        for r in records
        if r["format"] == "ttf"
    ]
    return {
        "schema": 2,
        "reviewer": "Mock for automated regression only",
        "project_sha256": digest(project.data),
        "font_sha256": report["font_sha256"],
        "profile_sha256": report["profile_sha256"],
        "evidence": evidence,
        "size_reviews": records,
        "glyphs": {
            name: {
                "fingerprint": g["fingerprint"],
                "checks": dict.fromkeys(REVIEW_CHECKS, "passed"),
                "notes": "Synthetic fixture; mocked review for gate mechanics only.",
                "evidence": [evidence[0]["path"]],
            }
            for name, g in report["glyphs"].items()
        },
    }


def test_size_proof_new_profiles_record_explicit_use_and_fixed_sizes(sized):
    project, profile, _, report, _ = sized
    assert profile["schema"] == 3
    assert profile["proofing"] == proofing_plan()
    assert report["size_proofing"]["status"] == "review_required"
    assert report["webfont_sha256"]
    for mutate in (
        lambda p: p.pop("intended_use"),
        lambda p: p.update(sizes_ppem=[16, 24, 48], min_supported_ppem=16),
        lambda p: p.update(sizes_ppem=[12, 16, 24, 24, 48]),
        lambda p: p.update(sizes_ppem=[12, 16, 24, True, 48]),
        lambda p: p.update(min_supported_ppem=16),
        lambda p: p.update(rationale=""),
    ):
        plan = proofing_plan()
        mutate(plan)
        with pytest.raises(FontifyError):
            validate_proofing(plan)
    with pytest.raises(FontifyError, match="rationale"):
        proofing_plan("display")
    plan = proofing_plan(
        "display",
        [32, 64, 96],
        32,
        "Title-only display artwork is supported from 32 pixels.",
    )
    assert plan["min_supported_ppem"] == 32
    profile.pop("proofing")
    write(project.root / "quality.json", profile)
    with pytest.raises(FontifyError, match="size proofing intent"):
        load_profile(project)


def test_size_proof_fixed_actual_font_proofs_are_pending_and_covered(sized):
    project, profile, bundle, _, _ = sized
    assert bundle["status"] == "unreviewed"
    assert len(bundle["size_reviews"]) == 8
    assert proof_samples(project)["confusables"]
    assert proof_samples(project)["punctuation"]
    assert proof_samples(project)["mixed_case"]
    html = (project.root / "evidence/size-proof.html").read_text()
    assert "data:font/woff2;base64," in html
    for size in [12, 16, 24, 48]:
        assert f"font-size:{size}px" in html
        record = next(
            r
            for r in bundle["size_reviews"]
            if r["format"] == "ttf" and r["size"] == size
        )
        assert record["renderer"]["name"] == "Pillow/FreeType"
        assert record["renderer"]["shaping"] == "RAQM/HarfBuzz"
        assert record["status"] == "unreviewed" and record["findings"] == {}
        assert record["device_scale"] == 1 and record["size_unit"] == "ppem"
        assert (
            (project.root / "evidence" / record["proof"])
            .read_bytes()
            .startswith(b"\x89PNG")
        )
    assert all(
        r["renderer"] is None and r["proof"] is None
        for r in bundle["size_reviews"]
        if r["format"] == "woff2"
    )
    allowed = {chr(int(g["unicode"][2:], 16)) for g in project.glyphs}
    assert all(
        set(text).issubset(allowed)
        for rows in bundle["samples"].values()
        for text in rows
    )


def test_size_proof_renderer_never_fits_text_to_width(sized, monkeypatch, tmp_path):
    from PIL import ImageFont

    from fontify.proofing import _rasterize_ttf

    project, _, _, _, manifest_path = sized
    manifest = json.loads(manifest_path.read_text())
    original = ImageFont.truetype
    requested = []

    def observe(*args, **kwargs):
        requested.append(kwargs.get("size", args[1] if len(args) > 1 else None))
        return original(*args, **kwargs)

    monkeypatch.setattr(ImageFont, "truetype", observe)
    _, dimensions = _rasterize_ttf(
        manifest_path.parent / manifest["font"],
        tmp_path / "wide.png",
        48,
        {"words": ["H" * 100]},
    )
    assert requested[0] == 48
    assert dimensions[0] > 1800


def test_size_proof_size_gate_accepts_only_complete_reviewed_evidence(sized, tmp_path):
    project, _, _, report, _ = sized
    receipt = mock_receipt(sized)
    write(project.root / "agent-review.json", receipt)
    result = check_review(project, report)
    assert result["size_proofing"]["reviewed_proofs"] == 8
    assert result["human_approval"] == "not_implied"
    released = release_font(project, tmp_path / "release")
    assert (
        json.loads(released.read_text())["quality"]["visual_review"]["size_proofing"][
            "status"
        ]
        == "passed"
    )
    receipt["schema"] = 1
    write(project.root / "agent-review.json", receipt)
    with pytest.raises(FontifyError, match="receipt schema"):
        release_font(project, tmp_path / "legacy-receipt")


@pytest.mark.parametrize(
    "mutate,match",
    [
        (lambda r: r.pop("size_reviews"), "every intended size"),
        (lambda r: r["size_reviews"].pop(), "incomplete"),
        (lambda r: r["size_reviews"][0].update(font_sha256="0" * 64), "stale"),
        (lambda r: r["size_reviews"][0].update(size_unit="points"), "size units"),
        (lambda r: r["size_reviews"][0].update(size=13), "unexpected format or size"),
        (lambda r: r["size_reviews"][0].update(device_scale=2), "device scale"),
        (lambda r: r["size_reviews"][1].update(device_scale=2), "incomplete"),
        (
            lambda r: r["size_reviews"][1].update(
                renderer=r["size_reviews"][0]["renderer"]
            ),
            "actual browser",
        ),
        (lambda r: r["size_reviews"][1].update(font_loaded=False), "actual browser"),
        (
            lambda r: r["size_reviews"][0]["samples"].update(confusables=[]),
            "must cover",
        ),
        (lambda r: r["size_reviews"][0].update(status="unreviewed"), "unreviewed"),
        (lambda r: r["size_reviews"][0].update(findings={}), "findings for every"),
        (
            lambda r: r["size_reviews"][0]["findings"]["counters"].update(
                notes="passed"
            ),
            "concrete",
        ),
        (
            lambda r: r["size_reviews"][0]["findings"]["punctuation"].update(
                status="not_applicable"
            ),
            "concrete",
        ),
        (lambda r: r["size_reviews"][0].update(proof_sha256="0" * 64), "stale"),
        (lambda r: r["size_reviews"][0].update(pixel_dimensions=[1, 1]), "dimensions"),
        (
            lambda r: r["size_reviews"].append(copy.deepcopy(r["size_reviews"][0])),
            "duplicate",
        ),
    ],
)
def test_size_proof_size_gate_rejects_incomplete_stale_or_unreviewed_proofs(
    sized, mutate, match
):
    project, profile, _, report, _ = sized
    receipt = mock_receipt(sized)
    mutate(receipt)
    with pytest.raises(FontifyError, match=match):
        check_size_reviews(project, profile, receipt, report)


def test_size_proof_size_gate_rejects_svg_renamed_png_and_missing_woff_audit(sized):
    project, profile, _, report, _ = sized
    receipt = mock_receipt(sized)
    bad = project.root / "not-a-raster.png"
    bad.write_text('<svg xmlns="http://www.w3.org/2000/svg"/>')
    receipt["size_reviews"][0].update(proof=bad.name, proof_sha256=sha256(bad))
    with pytest.raises(FontifyError, match="actual PNG"):
        check_size_reviews(project, profile, receipt, report)
    report.pop("webfont_sha256")
    with pytest.raises(FontifyError, match="both the current"):
        check_size_reviews(project, profile, mock_receipt(sized), report)


def test_size_proof_browser_capture_uses_real_woff2_and_remains_unreviewed(sized):
    pytest.importorskip("playwright.sync_api")
    from playwright.sync_api import sync_playwright

    executable = (
        os.environ.get("FONTIFY_BROWSER")
        or os.environ.get("FONTIFY_TEST_BROWSER")
        or shutil.which("google-chrome")
        or shutil.which("chromium")
    )
    if executable is None:
        with sync_playwright() as p:
            from pathlib import Path

            if not Path(p.chromium.executable_path).is_file():
                pytest.skip(
                    "real Chromium is not installed; install playwright chromium or set FONTIFY_TEST_BROWSER"
                )
    project, profile, _, report, _ = sized
    evidence = project.root / "evidence/size-proof-evidence.json"
    result = capture_browser_proofs(
        evidence.with_name("size-proof.html"), evidence, executable_path=executable
    )
    assert result["status"] == "unreviewed"
    browser_records = [r for r in result["size_reviews"] if r["format"] == "woff2"]
    assert len(browser_records) == 4
    for record in browser_records:
        assert record["renderer"]["kind"] == "browser"
        assert record["font_loaded"] is True
        assert record["font_sha256"] == report["webfont_sha256"]
        assert record["findings"] == {} and record["status"] == "unreviewed"
        assert sha256(evidence.parent / record["proof"]) == record["proof_sha256"]
    with pytest.raises(FontifyError, match="unreviewed"):
        pending = copy.deepcopy(result)
        for record in pending["size_reviews"]:
            record["proof"] = "evidence/" + record["proof"]
            if "html" in record:
                record["html"] = "evidence/" + record["html"]
        check_size_reviews(project, profile, pending, report)


def test_size_proof_historical_build_does_not_import_optional_rasterizer(
    tmp_path, monkeypatch
):
    import builtins

    original = builtins.__import__

    def without_raster(name, *args, **kwargs):
        if name == "PIL" or name.startswith("PIL.") or name.startswith("playwright"):
            raise AssertionError("legacy build imported optional proof renderer")
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", without_raster)
    assert build_font(
        ROOT / "examples/offline/fontify.json", tmp_path / "legacy"
    ).is_file()


def test_size_proof_refuses_overwrite_and_frozen_directories(sized):
    project, _, bundle, _, manifest_path = sized
    manifest = json.loads(manifest_path.read_text())
    font = manifest_path.parent / manifest["font"]
    woff = manifest_path.parent / manifest["webfont"]
    evidence = project.root / "evidence/size-proof-evidence.json"
    before = evidence.read_bytes()
    with pytest.raises(FontifyError, match="already exist"):
        write_size_proofs(font, woff, evidence.parent, project)
    assert evidence.read_bytes() == before
    with pytest.raises(FontifyError, match="frozen"):
        write_size_proofs(font, woff, manifest_path.parent, project)
    with pytest.raises(FontifyError, match="frozen"):
        capture_browser_proofs(
            manifest_path.parent / "size-proof.html",
            manifest_path.parent / "size-proof-evidence.json",
        )
    bundle["size_reviews"][0]["status"] = "passed"
    write(evidence, bundle)
    with pytest.raises(FontifyError, match="reviewed evidence"):
        capture_browser_proofs(evidence.with_name("size-proof.html"), evidence)
    assert not list(evidence.parent.glob("size-woff2-*.png"))


def test_size_proof_refuses_partial_browser_capture(sized):
    project, _, _, _, _ = sized
    evidence = project.root / "evidence/size-proof-evidence.json"
    path = evidence.with_name("size-woff2-12-dpr1.png")
    path.write_bytes(b"partial capture preserved")
    with pytest.raises(FontifyError, match="partial capture"):
        capture_browser_proofs(evidence.with_name("size-proof.html"), evidence)
    assert path.read_bytes() == b"partial capture preserved"


def test_size_proof_rejects_stale_browser_html(sized):
    project, profile, _, report, _ = sized
    receipt = mock_receipt(sized)
    html = project.root / "evidence/size-proof.html"
    html.write_text(html.read_text() + "<!-- changed -->")
    with pytest.raises(FontifyError, match="HTML is missing or stale"):
        check_size_reviews(project, profile, receipt, report)
    evidence = html.with_name("size-proof-evidence.json")
    with pytest.raises(FontifyError, match="HTML is missing or stale"):
        capture_browser_proofs(html, evidence)


def test_size_proof_repertoire_exclusions_are_explicit(sized):
    project, _, _, _, _ = sized
    project.data["glyphs"] = [
        g for g in project.glyphs if chr(int(g["unicode"][2:], 16)) in " H"
    ]
    project.data["samples"] = ["H HH"]
    samples = proof_samples(project)
    assert (
        samples["confusables"] == samples["punctuation"] == samples["mixed_case"] == []
    )
    assert samples["coverage"] == [" H"]
    assert samples["words"] == ["H HH"]
