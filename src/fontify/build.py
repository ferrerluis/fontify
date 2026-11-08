"""Deterministic OpenType/TrueType compilation, versioned releases, explicit provenance."""

import hashlib
import json
import shutil
import tempfile
from importlib.metadata import version
from pathlib import Path

from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.recordingPen import RecordingPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont

from .model import FontifyError, Project, codepoint, load_project
from .outlines import compile_project, digest
from .quality import audit_project, check_review
from .review import check_approval, shape_font, verified_release, write_proofs


def _notdef():
    p = TTGlyphPen(None)
    for points in [
        [(50, 0), (50, 700), (550, 700), (550, 0)],
        [(120, 70), (480, 70), (480, 630), (120, 630)],
    ]:
        p.moveTo(points[0])
        for pt in points[1:]:
            p.lineTo(pt)
        p.closePath()
    return p.glyph()


def _compile(project, outlines, path):
    d = project.data
    fb = FontBuilder(d["units_per_em"], isTTF=True)
    order = [".notdef"] + [o.spec["name"] for o in outlines]
    fb.setupGlyphOrder(order)
    fb.setupCharacterMap(
        {codepoint(o.spec["unicode"]): o.spec["name"] for o in outlines}
    )
    fb.setupGlyf({".notdef": _notdef(), **{o.spec["name"]: o.glyph for o in outlines}})
    metrics = {".notdef": (600, 50)}
    for o in outlines:
        # Match the TrueType control-point bbox, not tight ink bounds. A
        # different lsb makes consumers translate curved outlines on replay.
        lsb = o.glyph.xMin if o.glyph.numberOfContours else 0
        metrics[o.spec["name"]] = (o.spec["advance"], lsb)
    fb.setupHorizontalMetrics(metrics)
    fb.setupHorizontalHeader(
        ascent=d["ascender"], descent=d["descender"], lineGap=d["line_gap"]
    )
    ps = d["family"].replace(" ", "") + "-" + d["style"].replace(" ", "")
    fb.setupNameTable(
        {
            "familyName": d["family"],
            "styleName": d["style"],
            "uniqueFontIdentifier": f"fontify:{ps}:{d['version']}",
            "fullName": d["family"] + " " + d["style"],
            "psName": ps,
            "version": "Version " + d["version"],
            "copyright": d.get("copyright", ""),
            "licenseDescription": d.get(
                "license",
                "Unspecified; obtain rights to source artwork before distribution.",
            ),
        }
    )
    fb.setupOS2(
        version=4,
        sTypoAscender=d["ascender"],
        sTypoDescender=d["descender"],
        sTypoLineGap=d["line_gap"],
        usWinAscent=d["ascender"],
        usWinDescent=-d["descender"],
        sxHeight=d["x_height"],
        sCapHeight=d["cap_height"],
        fsType=0,
        fsSelection=0xC0,
    )
    fb.setupPost()
    fb.setupMaxp()
    font = fb.font
    font["head"].fontRevision = float(d["version"])
    # Fixed epoch makes artifacts reproducible; changing wall-clock time changes no bytes.
    font["head"].created = font["head"].modified = (
        3786912000  # 2024-01-01, OpenType epoch
    )
    font.recalcTimestamp = False
    if d.get("kerning"):
        lines = [
            "languagesystem DFLT dflt;",
            "languagesystem latn dflt;",
            "feature kern {",
        ]
        lines.extend(
            f"pos {k['left']} {k['right']} {k['value']};" for k in d["kerning"]
        )
        lines.append("} kern;")
        addOpenTypeFeaturesFromString(font, "\n".join(lines))
    font.save(path)
    font.close()


def verify_compiled(path, project, outlines):
    font = TTFont(path, checkChecksums=2)
    actual = font.getBestCmap()
    expected = {codepoint(o.spec["unicode"]): o.spec["name"] for o in outlines}
    if actual != expected:
        raise FontifyError("compiled cmap differs from declared coverage")
    if font["name"].getDebugName(5) != "Version " + project.data["version"]:
        raise FontifyError("compiled version differs from the project")
    gs = font.getGlyphSet()
    for o in outlines:
        n = o.spec["name"]
        pen = RecordingPen()
        gs[n].draw(pen)
        if digest(pen.value) != o.compiled_hash:
            raise FontifyError(f"compiled outline differs: {n}")
        if font["hmtx"][n][0] != o.spec["advance"]:
            raise FontifyError(f"compiled advance differs: {n}")
    font.close()
    byname = {o.spec["name"]: chr(codepoint(o.spec["unicode"])) for o in outlines}
    pair_checks = []
    for k in project.data.get("kerning", []):
        text = byname[k["left"]] + byname[k["right"]]
        on = shape_font(path, text)
        off = shape_font(path, text, False)
        delta = on["advance"] - off["advance"]
        if delta != k["value"]:
            raise FontifyError(f"HarfBuzz kerning mismatch for {text}: {delta}")
        pair_checks.append(
            {
                "text": text,
                "expected_adjustment": k["value"],
                "actual_adjustment": delta,
            }
        )
    samples = [shape_font(path, t) for t in project.data["samples"]]
    if any(g["gid"] == 0 for s in samples for g in s["glyphs"]):
        raise FontifyError("sample shapes to .notdef")
    return {"kerning_pairs": pair_checks, "samples": samples}


def release_font(project, output_dir):
    """Require geometry preflight and current per-glyph visual evidence."""
    if not isinstance(project, Project):
        project = load_project(project)
    if not project.data.get("quality"):
        raise FontifyError(
            "release requires a complete quality profile and per-glyph agent visual review"
        )
    return build_font(project, output_dir)


def build_font(project, output_dir, *, draft=False):
    """Build TTF, WOFF2, compiled-outline proofs and a hash manifest; no network.

    A same-version release may be reproduced, but never replaced by different bytes.
    Returns the path of release-manifest.json. Inspect that manifest for every output.
    """
    if not isinstance(project, Project):
        project = load_project(project)
    outlines = compile_project(project)
    approval = check_approval(project, outlines)
    source_quality = audit_project(project, outlines)
    gated = source_quality["status"] != "not_configured"
    if gated and not draft and source_quality["status"] != "passed":
        names = [
            n for n, g in source_quality["glyphs"].items() if g["status"] != "passed"
        ]
        raise FontifyError(
            "preflight geometry failed: "
            + ", ".join(names)
            + "; audit and correct an internal draft before presenting a font"
        )
    root = Path(output_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    target = root / (project.stem + ("-draft" if draft else ""))
    with tempfile.TemporaryDirectory(prefix=".fontify-", dir=root) as tmp:
        tmp = Path(tmp)
        ttf = tmp / (project.stem + ".ttf")
        woff = tmp / (project.stem + ".woff2")
        _compile(project, outlines, ttf)
        shaping = verify_compiled(ttf, project, outlines)
        f = TTFont(ttf, recalcTimestamp=False)
        f.flavor = "woff2"
        f.save(woff)
        f.close()
        verify_compiled(woff, project, outlines)
        compiled_quality = audit_project(project, outlines, ttf, webfont_path=woff)
        review = {"status": "pending"}
        if gated and not draft:
            if compiled_quality["status"] != "passed":
                raise FontifyError(
                    "compiled font failed geometry recheck; inspect an internal draft"
                )
            review = check_review(project, compiled_quality)
        quality = {
            "source": source_quality,
            "compiled": compiled_quality,
            "visual_review": review,
            "status": "internal_draft"
            if draft
            else ("preflight_passed" if gated else "not_configured"),
        }
        proof_approval = approval
        if gated and not draft:
            proof_approval = {
                **approval,
                "status": "preflight passed; glyph baseline matches"
                if approval["status"] == "baseline_matches"
                else "preflight passed; user design approval pending",
            }
        write_proofs(ttf, woff, tmp, project, outlines, proof_approval)
        if gated:
            (tmp / "quality.json").write_text(json.dumps(quality, indent=2) + "\n")
        report = {
            "approval": approval,
            "glyphs": {o.spec["name"]: o.diagnostics for o in outlines},
            "shaping": shaping,
            "limits": [
                "Topology diagnostics flatten curves at 0.2 font units; this is not a mathematical proof.",
                "Symmetry/ink area are measurements, not optical-quality scores.",
                "Human review is required for shape, optical weight, curves, rhythm and style.",
            ],
        }
        (tmp / "validation.json").write_text(json.dumps(report, indent=2) + "\n")
        cps = sorted(codepoint(o.spec["unicode"]) for o in outlines)
        css = (
            f'@font-face {{ font-family: "{project.data["family"]}"; src: url("{woff.name}") format("woff2"); font-style: normal; font-weight: 400; font-display: swap; unicode-range: '
            + ", ".join(f"U+{cp:X}" for cp in cps)
            + "; }\n"
        )
        (tmp / "font.css").write_text(css)
        artifacts = {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(tmp.iterdir())
        }
        manifest = {
            "schema": 1,
            "family": project.data["family"],
            "style": project.data["style"],
            "version": project.data["version"],
            "font": ttf.name,
            "webfont": woff.name,
            "project_sha256": digest(project.data),
            "metrics": {
                k: project.data[k]
                for k in (
                    "units_per_em",
                    "ascender",
                    "descender",
                    "line_gap",
                    "cap_height",
                    "x_height",
                )
            },
            "coverage": [f"U+{cp:04X}" for cp in cps],
            "kerning": project.data.get("kerning", []),
            "glyphs": {
                o.spec["name"]: {
                    "source": o.spec.get("source"),
                    "source_sha256": o.source_hash,
                    "normalized_sha256": o.normalized_hash,
                    "compiled_sha256": o.compiled_hash,
                    "unicode": o.spec["unicode"],
                    "advance": o.spec["advance"],
                }
                for o in outlines
            },
            "approval": approval,
            "artifacts": artifacts,
            "toolchain": {
                p: version(p)
                for p in (
                    "fonttools",
                    "brotli",
                    "uharfbuzz",
                    "skia-pathops",
                    "defusedxml",
                )
            },
        }
        if gated:
            manifest["quality"] = {"status": quality["status"], "visual_review": review}
        (tmp / "release-manifest.json").write_text(
            json.dumps(manifest, indent=2) + "\n"
        )
        if target.exists():
            old = verified_release(target / "release-manifest.json")
            if old != manifest:
                raise FontifyError(
                    "release already exists with different content; increment project version"
                )
        else:
            shutil.copytree(tmp, target)
    if draft:
        return target / "release-manifest.json"
    current = {
        "schema": 1,
        "version": project.data["version"],
        "manifest": f"{project.stem}/release-manifest.json",
    }
    # Publish the pointer last, after every font and proof is verified.
    pointer = root / ".current.json.tmp"
    pointer.write_text(json.dumps(current, indent=2) + "\n")
    pointer.replace(root / "current.json")
    return target / "release-manifest.json"
