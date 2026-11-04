"""One bounded internal correction/recheck pass; never publishes or approves a font."""

import json
from pathlib import Path

from .build import build_font
from .model import FontifyError, load_project
from .outlines import compile_project
from .quality import audit_project, check_review, load_profile
from .repair import repair_project
from .review import compare_releases
from .rubrics import require_resolved


def preflight(project_path, output, repair_version=None, patches=None):
    project = load_project(project_path)
    output = Path(output).resolve()
    if output.exists() or output.is_relative_to(project.root):
        raise FontifyError("preflight needs a new directory outside the source project")
    output.mkdir(parents=True)
    result = {
        "status": "blocked",
        "source_project": str(project.path),
        "candidate_project": str(project.path),
        "report": str(output / "preflight.json"),
        "published": False,
    }
    try:
        profile = load_profile(project)
        if profile is None or profile["schema"] != 2:
            raise FontifyError(
                "preflight routing needs schema 2; use rubric-plan first"
            )
        outlines = compile_project(project)
        before = audit_project(project, outlines)
        result["before"] = before
        require_resolved(profile)
        if patches and not repair_version:
            raise FontifyError("patches require a repair version and a new candidate")
        if repair_version:
            original = build_font(project, output / "before", draft=True)
            candidate = repair_project(
                project.path, output / "candidate", repair_version, patches
            )
            project = load_project(candidate)
            result["candidate_project"] = str(candidate)
            result["corrections"] = str(candidate.parent / "corrections.json")
        else:
            original = None
        after = audit_project(project, compile_project(project))
        result["after"] = after
        if after["status"] != "passed":
            raise FontifyError(
                "source checks remain unresolved; revise this internal candidate"
            )
        draft = build_font(project, output / "draft", draft=True)
        manifest = json.loads(draft.read_text())
        compiled = audit_project(
            project, compile_project(project), draft.parent / manifest["font"]
        )
        result["draft_manifest"] = str(draft)
        result["compiled"] = compiled
        # build_font reopens both formats, verifies metrics/coverage/outlines,
        # and tests declared pairs and samples using actual HarfBuzz shaping.
        result["construction_checks"] = {
            "status": "passed",
            "evidence": str(draft),
            "formats": ["TTF", "WOFF2"],
        }
        if original:
            compare_releases(original, draft, output / "comparison")
            result["comparison"] = str(output / "comparison/comparison.html")
        if compiled["status"] != "passed":
            raise FontifyError("exported outlines need further correction and review")
        try:
            result["visual_review"] = check_review(project, compiled)
        except FontifyError as e:
            result["visual_review"] = {"status": "required", "reason": str(e)}
            result["status"] = "needs_visual_review"
            result["next"] = (
                "Inspect every actual compiled glyph at enlarged and reading sizes, "
                "plus shaped words and before/after proofs. Retain or revert each edit; "
                "revise locally and repeat as needed. Record a current complete visual "
                "receipt before using release. Do not present these drafts as the first font."
            )
        else:
            result["status"] = "ready_for_release"
            result["next"] = (
                "Use fontify release with this candidate; verify its returned manifest before presentation."
            )
    except (FontifyError, OSError, ValueError) as e:
        result["error"] = str(e)
        result["next"] = (
            "Resolve the recorded issue in the internal candidate, then repeat in a new output directory."
        )
    (output / "preflight.json").write_text(json.dumps(result, indent=2) + "\n")
    return result
