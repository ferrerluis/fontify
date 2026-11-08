#!/usr/bin/env python3
"""Run product checks and retain machine-readable evidence outside tracked source."""

import hashlib
import json
import os
import platform
import subprocess
import sys
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
CASES = {
    "TC01.1": ("Offline export and CLI", "test_offline"),
    "TC01.2": ("Reproducible release", "test_reproducible"),
    "TC01.3": ("Curved glyph placement survives export", "test_curved_placement"),
    "TC02.1": ("Coverage and mappings", "test_coverage"),
    "TC02.2": ("Vector/topology validation", "test_vector"),
    "TC03.1": ("Real shaping and kerning", "test_shaping"),
    "TC04.1": ("Approved glyph preservation", "test_approval"),
    "TC04.2": ("Compiled comparison and integrity", "test_comparison"),
    "TC04.3": ("Proof reflects protected glyph baseline", "test_approval_proof"),
    "TC05.1": ("Mocked optional provider", "test_adapter"),
    "TC05.2": ("MCP schema discovery protocol", "test_discovery"),
    "TC05.3": (
        "Vector Pro default and explicit non-Pro choice",
        "test_model_selection",
    ),
    "TC06.2": ("Proof canvases include overhanging ink", "test_proof_overhang"),
    "TC07.1": ("Image-generated example builds offline", "test_generated_example"),
    "TC07.2": ("Generated crop tracing and preservation", "test_generated_trace"),
    "TC07.3": (
        "Generated-source / compiled-outline fidelity",
        "test_generated_fidelity",
    ),
    "TC08.1": ("Complete explicit glyph intent", "test_intent"),
    "TC08.2": ("Bounded exact-axis correction", "test_axes"),
    "TC08.3": ("Curve and exported-symmetry checks", "test_curves"),
    "TC08.4": ("Protected correction and preservation", "test_preservation"),
    "TC08.5": ("Pre-presentation review gate", "test_release_gate"),
    "TC09.1": ("Recraft vector extraction and guards", "test_recraft_extraction"),
    "TC09.2": ("Reviewed Recraft example builds offline", "test_recraft_offline"),
    "TC10.1": ("Style plans require inspected intent", "test_rubric_plan"),
    "TC10.2": ("Feature-specific deterministic routing", "test_rubric_routing"),
    "TC10.3": ("Explicit correction permissions", "test_rubric_permission"),
    "TC10.4": ("Internal correction and recheck pass", "test_rubric_preflight"),
    "TC10.5": ("Rubric and visual presentation gate", "test_rubric_gate"),
    "TC10.6": ("Universal checks for every style", "test_rubric_universal"),
    "TC11.1": ("Vector optical spacing and collision-guarded pairs", "test_spacing_"),
    "TC12.1": ("Raster-only preparation and preservation", "test_raster_"),
    "TC13.1": ("Fixed-size proof generation and release gate", "test_size_proof_"),
    "TC14.1": (
        "Native vector route excludes raster tools",
        "test_vector_source_route_",
    ),
}


def source_digest():
    h = hashlib.sha256()
    for base in ("src", "tests", "examples"):
        for p in sorted((ROOT / base).rglob("*")):
            if (
                p.is_file()
                and "__pycache__" not in p.parts
                and not any(part.endswith(".egg-info") for part in p.parts)
            ):
                h.update(str(p.relative_to(ROOT)).encode() + b"\0" + p.read_bytes())
    for name in ("pyproject.toml", "requirements.lock", "scripts/run_acceptance.py"):
        h.update((ROOT / name).read_bytes())
    return h.hexdigest()


def main():
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    directory = ROOT / "test-runs" / stamp
    directory.mkdir(parents=True, exist_ok=False)
    junit = directory / "junit.xml"
    cmd = [sys.executable, "-m", "pytest", "-q", f"--junitxml={junit}"]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, env=env)
    (directory / "pytest.txt").write_text(run.stdout + run.stderr)
    tests = list(ET.parse(junit).getroot().iter("testcase")) if junit.exists() else []
    results = []
    for ident, (label, prefix) in CASES.items():
        group = [t for t in tests if t.get("name", "").startswith(prefix)]
        status = "passed" if group else "blocked"
        if any(
            t.find("failure") is not None or t.find("error") is not None for t in group
        ):
            status = "failed"
        elif any(t.find("skipped") is not None for t in group):
            status = "blocked"
        results.append(
            {
                "id": ident,
                "label": label,
                "status": status,
                "checks": len(group),
                "prerequisites": "local project and installed dev/recraft dependencies; no credentials or network",
                "command": " ".join(cmd),
                "expected": "observable outcomes in docs/acceptance.md",
                "evidence": ["junit.xml", "pytest.txt"],
                "dependencies": [],
                "bug_iterations": [],
                "timestamp": stamp,
            }
        )
    # Browser observation is external evidence and never inferred from pytest.
    results.append(
        {
            "id": "TC06.1",
            "label": "Browser webfont and visual proof",
            "status": "pending",
            "prerequisites": "built demo and browser",
            "command": "open release proof.html",
            "expected": "loaded WOFF2, covered/unsupported input, kerning views and visible glyph sheet",
            "evidence": [],
            "dependencies": ["TC01.1", "TC03.1"],
            "timestamp": stamp,
        }
    )
    report = {
        "catalog_version": 9,
        "timestamp": stamp,
        "source_digest": source_digest(),
        "python": platform.python_version(),
        "components": {
            p: version(p)
            for p in (
                "fontify",
                "fonttools",
                "uharfbuzz",
                "skia-pathops",
                "brotli",
                "pytest",
                "httpx",
            )
        },
        "command": cmd,
        "exit_code": run.returncode,
        "results": results,
        "live_recraft": {
            "status": "not_run_by_offline_suite; prior authorized experiment saved separately",
            "paid_calls": 0,
            "schema_evidence": "docs/research/recraft-live-tools.json",
            "prior_experiment_evidence": "examples/recraft-mellow/source/provenance.json",
        },
    }
    (directory / "results.json").write_text(json.dumps(report, indent=2) + "\n")
    text = [
        f"# Acceptance {stamp}",
        "",
        f"Source digest: `{report['source_digest']}`",
        "",
        "| ID | Status | Checks | Evidence |",
        "|---|---|---:|---|",
    ]
    text.extend(
        f"| {r['id']} | {r['status']} | {r.get('checks', '—')} | {', '.join(r['evidence'])} |"
        for r in results
    )
    (directory / "results.md").write_text("\n".join(text) + "\n")
    (ROOT / "test-runs/latest.json").write_text(
        json.dumps(
            {"results": str((directory / "results.json").relative_to(ROOT))}, indent=2
        )
        + "\n"
    )
    print(run.stdout.strip())
    print(f"Evidence: {directory}")
    return run.returncode or (
        1 if any(r["status"] != "passed" for r in results[:-1]) else 0
    )


if __name__ == "__main__":
    raise SystemExit(main())
