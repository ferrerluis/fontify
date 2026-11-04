"""Local CLI; JSON output for composition and a separate opt-in creative command."""

import argparse
import json
import os
import sys
from pathlib import Path

from .build import build_font, release_font
from .model import FontifyError, load_project
from .outlines import compile_project
from .review import (
    approval_snapshot,
    check_approval,
    compare_releases,
    inspect_font,
    verified_release,
)


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="fontify",
        description="Build reviewable fonts from vector glyphs; offline first",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("build", "release", "validate", "snapshot"):
        p = sub.add_parser(name)
        p.add_argument("project", type=Path)
        if name in ("build", "release"):
            p.add_argument("--out", type=Path, default=Path("build"))
        if name == "build":
            p.add_argument(
                "--draft",
                action="store_true",
                help="internal audit artifacts; never updates current.json",
            )
        if name == "snapshot":
            p.add_argument("--output", type=Path, required=True)
    p = sub.add_parser("inspect")
    p.add_argument("font", type=Path)
    p.add_argument("--text")
    p = sub.add_parser("audit")
    p.add_argument("project", type=Path)
    p.add_argument("--font", type=Path)
    p.add_argument("--out", type=Path, required=True)
    p = sub.add_parser("repair")
    p.add_argument("project", type=Path)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--version", required=True)
    p.add_argument("--patches", type=Path)
    p = sub.add_parser("verify-release")
    p.add_argument("manifest", type=Path)
    p = sub.add_parser("compare")
    p.add_argument("before", type=Path)
    p.add_argument("after", type=Path)
    p.add_argument("--out", type=Path, required=True)
    p = sub.add_parser("recraft-plan")
    p.add_argument("prompt", type=Path)
    p.add_argument("--model", default="recraftv4_1_vector")
    p.add_argument("--size", default="1:1")
    p.add_argument("--style-id")
    p.add_argument("--reference-url", action="append", default=[])
    p.add_argument("--seed", type=int)
    p = sub.add_parser("recraft-generate")
    p.add_argument("plan", type=Path)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--allow-paid", action="store_true")
    p = sub.add_parser("recraft-discover")
    p.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command in ("build", "release", "validate", "snapshot"):
            project = load_project(args.project)
            if args.command in ("build", "release"):
                draft = getattr(args, "draft", False)
                result = {
                    "manifest": str(
                        release_font(project, args.out)
                        if args.command == "release"
                        else build_font(project, args.out, draft=draft)
                    ),
                    "draft": draft,
                }
            else:
                outlines = compile_project(project)
                if args.command == "snapshot":
                    snap = approval_snapshot(project, outlines)
                    args.output.parent.mkdir(parents=True, exist_ok=True)
                    with args.output.open("x") as f:
                        json.dump(snap, f, indent=2)
                        f.write("\n")
                    result = {
                        "snapshot": str(args.output),
                        "status": "candidate_baseline_requires_human_review",
                    }
                else:
                    result = {
                        "approval": check_approval(project, outlines),
                        "glyphs": {o.spec["name"]: o.diagnostics for o in outlines},
                    }
        elif args.command == "audit":
            from .quality import audit_project

            project = load_project(args.project)
            result = audit_project(project, compile_project(project), args.font)
            if result["status"] == "not_configured":
                raise FontifyError("audit requires a declared quality profile")
            args.out.mkdir(parents=True, exist_ok=True)
            (args.out / "audit.json").write_text(json.dumps(result, indent=2) + "\n")
            print(
                json.dumps(
                    {
                        "status": result["status"],
                        "report": str(args.out / "audit.json"),
                        "failed_glyphs": [
                            n
                            for n, g in result["glyphs"].items()
                            if g["status"] == "failed"
                        ],
                    },
                    indent=2,
                )
            )
            return 0 if result["status"] == "passed" else 1
        elif args.command == "repair":
            from .repair import repair_project

            result = {
                "project": str(
                    repair_project(args.project, args.out, args.version, args.patches)
                ),
                "status": "draft_requires_recheck_and_visual_review",
            }
        elif args.command == "inspect":
            result = inspect_font(args.font, args.text)
        elif args.command == "verify-release":
            d = verified_release(args.manifest)
            result = {
                "status": "verified",
                "version": d["version"],
                "artifacts": len(d["artifacts"]),
            }
        elif args.command == "compare":
            result = compare_releases(args.before, args.after, args.out)
        elif args.command == "recraft-plan":
            from .providers import DesignRequest
            from .providers.recraft import plan_request

            payload = plan_request(
                DesignRequest(
                    args.prompt.read_text(),
                    args.model,
                    args.size,
                    args.style_id,
                    tuple(args.reference_url),
                    args.seed,
                )
            )
            result = {"status": "dry_run_no_network", "request": payload}
        elif args.command == "recraft-generate":
            from .providers import DesignRequest
            from .providers.recraft import RecraftProvider, save_candidate

            if args.out.exists():
                raise FontifyError(
                    "candidate directory exists; choose a new directory before spending credits"
                )
            data = json.loads(args.plan.read_text())["request"]
            req = DesignRequest(
                data["prompt"],
                data["model"],
                data.get("size", "1:1"),
                data.get("style_id"),
                tuple(data.get("style_reference_urls", [])),
                data.get("random_seed"),
            )
            artwork = RecraftProvider().generate(req, allow_paid=args.allow_paid)
            result = {
                "candidate": str(save_candidate(artwork, args.out)),
                "status": "unreviewed_source_artwork",
            }
        elif args.command == "recraft-discover":
            from .providers.mcp import discover_schema

            result = discover_schema(
                args.output, bearer_token=os.environ.get("RECRAFT_MCP_ACCESS_TOKEN")
            )
        print(json.dumps(result, indent=2))
        return 0
    except (FontifyError, OSError, ValueError, KeyError) as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
