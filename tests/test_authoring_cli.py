"""Exercise the public authoring commands, not just their internal APIs."""

import json

from fontify.cli import main


def test_spacing_cli_plan_apply_and_protected_source(project_dir, tmp_path, capsys):
    project = project_dir / "fontify.json"
    data = json.loads(project.read_text())
    data["approval"] = None
    data["glyphs"] = [g for g in data["glyphs"] if g["name"] in ("H", "space")]
    data.update(required_characters="H ", samples=["H HH"], kerning=[])
    project.write_text(json.dumps(data))
    before = project.read_bytes()
    plan = tmp_path / "spacing.json"
    assert main(["spacing-plan", str(project), "--output", str(plan)]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "spacing_review_required"
    candidate = tmp_path / "candidate"
    assert (
        main(
            [
                "spacing-apply",
                str(project),
                str(plan),
                "--out",
                str(candidate),
                "--version",
                "0.002",
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["project"] == str(
        candidate / "fontify.json"
    )
    assert project.read_bytes() == before
    assert (
        main(
            [
                "spacing-apply",
                str(project),
                str(plan),
                "--out",
                str(candidate),
                "--version",
                "0.002",
            ]
        )
        == 1
    )
    assert "new directory" in capsys.readouterr().err


def test_size_proof_cli_intended_use_and_legacy_gate(project_dir, tmp_path, capsys):
    project = project_dir / "fontify.json"
    profile = tmp_path / "display.json"
    assert (
        main(
            [
                "rubric-plan",
                str(project),
                "--style",
                "display",
                "--note",
                "Poster lettering.",
                "--intended-use",
                "display",
                "--sizes",
                "32",
                "64",
                "96",
                "--min-size",
                "32",
                "--size-rationale",
                "Display letters intended for posters at 32 pixels or larger.",
                "--output",
                str(profile),
            ]
        )
        == 0
    )
    capsys.readouterr()
    saved = json.loads(profile.read_text())
    assert saved["schema"] == 3
    assert saved["proofing"]["sizes_ppem"] == [32, 64, 96]
    assert saved["proofing"]["intended_use"] == "display"
