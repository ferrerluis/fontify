"""Fixed-size display QA of final fonts, never raster-to-vector source conversion.

Generators deliberately produce unreviewed evidence. A browser screenshot is a
separate operation; a Pillow image cannot stand in for browser/WOFF2 rendering.
"""

import base64
import hashlib
import json
import math
import re
import struct
import unicodedata
from html import escape
from pathlib import Path

from fontTools.ttLib import TTFont

from .model import FontifyError, keys, local_path

TEXT_SIZES = [12, 16, 24, 48]
FINDING_AREAS = {
    "legibility",
    "counters",
    "optical_weight",
    "spacing",
    "confusables",
    "punctuation",
    "mixed_case",
}
CONFUSABLE_GROUPS = (
    "Il1",
    "O0",
    "S5",
    "B8",
    "Z2",
    "rnмm",
    "cld",
    "uv",
    "CG",
    "EF",
    "HН",
    "pq",
    "bd",
)


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def proofing_plan(
    intended_use="text", sizes_ppem=None, min_supported_ppem=None, rationale=None
):
    minimum = (
        min_supported_ppem
        if min_supported_ppem is not None
        else (24 if intended_use == "display" else 12)
    )
    sizes = (
        sizes_ppem
        if sizes_ppem is not None
        else (
            TEXT_SIZES.copy()
            if intended_use == "text"
            else [minimum, minimum * 2, minimum * 3]
        )
    )
    plan = {
        "intended_use": intended_use,
        "sizes_ppem": sizes,
        "min_supported_ppem": minimum,
        "rationale": rationale
        if rationale is not None
        else (
            "Text use requires review at reading sizes as well as enlarged reference sizes."
            if intended_use == "text"
            else ""
        ),
    }
    validate_proofing(plan)
    return plan


def validate_proofing(plan):
    keys(
        plan,
        "intended_use sizes_ppem min_supported_ppem rationale",
        "size proofing intent",
    )
    if plan.get("intended_use") not in ("text", "display"):
        raise FontifyError("size proofing requires text or display intended_use")
    sizes = plan.get("sizes_ppem")
    if (
        not isinstance(sizes, list)
        or len(sizes) < 2
        or any(type(s) is not int or not 6 <= s <= 512 for s in sizes)
        or sizes != sorted(set(sizes))
    ):
        raise FontifyError(
            "sizes_ppem must be sorted unique integers from 6 through 512, with at least two sizes"
        )
    minimum = plan.get("min_supported_ppem")
    if type(minimum) is not int or minimum != sizes[0]:
        raise FontifyError("min_supported_ppem must equal the smallest proof size")
    if plan["intended_use"] == "text" and not set(TEXT_SIZES).issubset(sizes):
        raise FontifyError("text proofing must include 12, 16, 24 and 48 ppem")
    if not isinstance(plan.get("rationale"), str) or not plan["rationale"].strip():
        raise FontifyError(
            "size proofing needs a rationale, including any display-only minimum"
        )


def proof_samples(project):
    """Deterministic covered repertoire, with honest empty categories for subsets."""
    characters = sorted({chr(int(g["unicode"][2:], 16)) for g in project.glyphs})
    supported = set(characters)
    separator = " " if " " in supported else ""
    confusables = []
    for group in CONFUSABLE_GROUPS:
        subset = "".join(c for c in group if c in supported)
        if len(set(subset)) >= 2:
            confusables.append(subset + separator + subset[::-1])
    punctuation = "".join(
        c for c in characters if unicodedata.category(c).startswith("P")
    )
    upper = [c for c in characters if c.isupper()]
    lower = [c for c in characters if c.islower()]
    mixed = "".join(a + b for a, b in zip(upper, lower)) if upper and lower else ""

    # Bounded line lengths, never font-size adjustment or per-glyph fitting.
    def lines(text):
        return [text[i : i + 48] for i in range(0, len(text), 48)]

    return {
        "coverage": lines("".join(characters)),
        "words": [part for text in project.data["samples"] for part in lines(text)],
        "confusables": confusables,
        "punctuation": lines(punctuation),
        "mixed_case": lines(mixed),
    }


def _rows(samples):
    return [(category, text) for category, values in samples.items() for text in values]


def _record(fmt, size, font_hash, samples):
    return {
        "format": fmt,
        "font_sha256": font_hash,
        "size": size,
        "size_unit": "ppem" if fmt == "ttf" else "css_px",
        "device_scale": 1,
        "renderer": None,
        "proof": None,
        "proof_sha256": None,
        "pixel_dimensions": None,
        "samples": samples,
        "status": "unreviewed",
        "findings": {},
    }


def _rasterize_ttf(font_path, destination, size, samples):
    try:
        import PIL
        from PIL import Image, ImageDraw, ImageFont, features
    except ImportError as e:
        raise FontifyError(
            "fixed-size TTF proofing needs Pillow; install fontify[proof]"
        ) from e
    if not features.check_feature("raqm"):
        raise FontifyError(
            "TTF size proofs require Pillow with RAQM/HarfBuzz shaping support"
        )
    face = ImageFont.truetype(
        str(font_path), size=size, layout_engine=ImageFont.Layout.RAQM
    )
    label = ImageFont.load_default()
    rows = _rows(samples)
    boxes = [face.getbbox(text, anchor="ls") for _, text in rows]
    ascender, descender = face.getmetrics()
    left = min([0] + [b[0] for b in boxes])
    top = min([-ascender] + [b[1] for b in boxes])
    bottom = max([descender] + [b[3] for b in boxes])
    row_height = max(1, bottom - top) + 34
    width = max(640, math.ceil(max([0] + [b[2] - left for b in boxes])) + 32)
    height = 45 + len(rows) * row_height
    if max(width, height) > 32768:
        raise FontifyError(
            "size proof exceeds 32768 pixels; shorten sample lines, do not shrink the font"
        )
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    draw.text(
        (16, 12),
        f"TTF / {size} ppem / device scale 1 / unreviewed",
        font=label,
        fill="#333333",
    )
    for index, (category, text) in enumerate(rows):
        y = 45 + index * row_height
        draw.text((16, y), category, font=label, fill="#555555")
        draw.text((16 - left, y + 20 - top), text, font=face, fill="black", anchor="ls")
    image.save(destination)
    return {
        "kind": "rasterizer",
        "name": "Pillow/FreeType",
        "version": PIL.__version__,
        "freetype_version": features.version_module("freetype2"),
        "shaping": "RAQM/HarfBuzz",
    }, [width, height]


def write_size_proofs(font_path, woff_path, directory, project, profile=None):
    """Write fixed-scale TTF PNGs, real-WOFF2 HTML, and PENDING evidence records."""
    if profile is None:
        from .quality import load_profile

        profile = load_profile(project)
    if not profile or profile["schema"] != 3:
        raise FontifyError("size proofs require a schema-3 quality profile")
    validate_proofing(profile["proofing"])
    with TTFont(font_path) as ttf, TTFont(woff_path) as woff:
        if ttf.flavor is not None or woff.flavor != "woff2":
            raise FontifyError("size proofs need an actual TTF and WOFF2, respectively")
        expected = {int(g["unicode"][2:], 16): g["name"] for g in project.glyphs}
        if ttf.getBestCmap() != expected or woff.getBestCmap() != expected:
            raise FontifyError("size proof font coverage differs from the project")
        # Verify both formats really contain the same final glyphs and advances.
        from fontTools.pens.recordingPen import RecordingPen

        for name in expected.values():
            a, b = RecordingPen(), RecordingPen()
            ttf.getGlyphSet()[name].draw(a)
            woff.getGlyphSet()[name].draw(b)
            if a.value != b.value or ttf["hmtx"][name] != woff["hmtx"][name]:
                raise FontifyError("size proof TTF and WOFF2 differ")
    directory = Path(directory)
    if (directory / "release-manifest.json").exists():
        raise FontifyError(
            "size proofs need a standalone evidence directory, not a frozen draft or release directory"
        )
    destinations = ["size-proof.html", "size-proof-evidence.json"] + [
        f"size-ttf-{size}.png" for size in profile["proofing"]["sizes_ppem"]
    ]
    if any(
        (directory / name).exists() or (directory / name).is_symlink()
        for name in destinations
    ):
        raise FontifyError(
            "size proofs already exist; use a new evidence directory, never overwrite reviewed proofs"
        )
    directory.mkdir(parents=True, exist_ok=True)
    samples = proof_samples(project)
    hashes = {"ttf": sha256(font_path), "woff2": sha256(woff_path)}
    records = []
    for size in profile["proofing"]["sizes_ppem"]:
        item = _record("ttf", size, hashes["ttf"], samples)
        path = directory / f"size-ttf-{size}.png"
        renderer, dimensions = _rasterize_ttf(font_path, path, size, samples)
        item.update(
            renderer=renderer,
            proof=path.name,
            proof_sha256=sha256(path),
            pixel_dimensions=dimensions,
        )
        records.append(item)
        records.append(_record("woff2", size, hashes["woff2"], samples))
    metadata = {
        "schema": 1,
        "font_hashes": hashes,
        "proofing": profile["proofing"],
        "samples": samples,
    }
    webfont = base64.b64encode(Path(woff_path).read_bytes()).decode("ascii")
    sections = []
    for size in profile["proofing"]["sizes_ppem"]:
        rows = "".join(
            f'<div class="label">{escape(category)}</div><div class="sample" data-category="{category}" style="font-size:{size}px">{escape(text)}</div>'
            for category, text in _rows(samples)
        )
        sections.append(
            f'<section id="size-{size}" data-size="{size}"><h2>WOFF2 / {size} CSS px / unreviewed</h2>{rows}</section>'
        )
    html = """<!doctype html><html lang="en"><meta charset="utf-8"><title>Fontify intended-size proof</title><style>
@font-face{font-family:FontifySizeProof;src:url(data:font/woff2;base64,WEBFONT) format('woff2');font-display:block}
*{box-sizing:border-box}body{margin:24px;background:white;color:black;font:14px sans-serif}section{padding:16px;margin:16px 0;border:1px solid #ccc;width:max-content;min-width:640px}h1,h2{font:18px sans-serif}.label{font:12px sans-serif;color:#555;margin-top:14px}.sample{font-family:FontifySizeProof;font-weight:400;font-style:normal;font-synthesis:none;line-height:2;white-space:pre;font-kerning:normal;font-feature-settings:"kern" 1;font-optical-sizing:none}
</style><h1>Final-font size proof, not source tracing</h1><p>Fixed CSS sizes. Do not zoom or scale. Capture in a real browser after font loading, then inspect and record findings.</p>SECTIONS
<script id="fontify-proof-data" type="application/json">METADATA</script><script>
const data=JSON.parse(document.getElementById('fontify-proof-data').textContent);
window.fontifyProofReady=Promise.all(data.proofing.sizes_ppem.map(size=>document.fonts.load(`${size}px FontifySizeProof`))).then(results=>{if(results.some(fonts=>fonts.length!==1||fonts[0].status!=='loaded'))throw Error('WOFF2 failed to load');document.documentElement.dataset.fontifyLoaded='true';return true;});
</script></html>"""
    # Substitute source once, before inserting metadata or arbitrary sample text.
    substitutions = {
        "WEBFONT": webfont,
        "METADATA": json.dumps(metadata).replace("<", "\\u003c"),
        "SECTIONS": "".join(sections),
    }
    html = re.sub(
        r"WEBFONT|METADATA|SECTIONS", lambda match: substitutions[match[0]], html
    )
    html_path = directory / "size-proof.html"
    html_path.write_text(html)
    bundle = {
        **metadata,
        "status": "unreviewed",
        "html": html_path.name,
        "html_sha256": sha256(html_path),
        "size_reviews": records,
    }
    (directory / "size-proof-evidence.json").write_text(
        json.dumps(bundle, indent=2) + "\n"
    )
    return bundle


def capture_browser_proofs(
    proof_html, evidence_path, *, executable_path=None, device_scale=1
):
    """Capture actual Chromium WOFF2 rendering. Never mark screenshots reviewed.

    Evidence paths are relative to evidence_path's directory. Keep this output
    separate from a frozen release manifest, which hashes all original artifacts.
    """
    if (
        isinstance(device_scale, bool)
        or not isinstance(device_scale, (int, float))
        or device_scale not in (1, 2)
    ):
        raise FontifyError(
            "browser proof device_scale must be 1 or 2; release requires scale 1"
        )
    proof_html, evidence_path = (
        Path(proof_html).resolve(),
        Path(evidence_path).resolve(),
    )
    if not proof_html.is_relative_to(evidence_path.parent):
        raise FontifyError(
            "keep the proof HTML inside the standalone evidence directory"
        )
    if (evidence_path.parent / "release-manifest.json").exists():
        raise FontifyError(
            "browser capture cannot modify a frozen draft or release; generate standalone size proofs first"
        )
    try:
        bundle = json.loads(evidence_path.read_text())
        html = proof_html.read_text()
    except (OSError, ValueError) as e:
        raise FontifyError(f"cannot read size proof bundle: {e}") from e
    keys(
        bundle,
        "schema font_hashes proofing samples status html html_sha256 size_reviews",
        "size proof bundle",
    )
    if not isinstance(bundle.get("size_reviews"), list) or not bundle["size_reviews"]:
        raise FontifyError("size proof bundle requires pending evidence records")
    if not isinstance(bundle.get("font_hashes"), dict) or set(
        bundle["font_hashes"]
    ) != {"ttf", "woff2"}:
        raise FontifyError("size proof bundle requires TTF and WOFF2 hashes")
    if (
        not isinstance(bundle.get("samples"), dict)
        or set(bundle["samples"])
        != {"coverage", "words", "confusables", "punctuation", "mixed_case"}
        or any(
            not isinstance(rows, list)
            or any(not isinstance(text, str) for text in rows)
            for rows in bundle["samples"].values()
        )
    ):
        raise FontifyError("size proof bundle has invalid covered samples")
    if any(not isinstance(r, dict) for r in bundle["size_reviews"]):
        raise FontifyError("size proof bundle has invalid evidence records")
    if bundle.get("schema") != 1 or bundle.get("html_sha256") != sha256(proof_html):
        raise FontifyError("size proof HTML is missing or stale")
    validate_proofing(bundle.get("proofing"))
    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        raise FontifyError(
            "browser capture needs Playwright; install fontify[proof] and a Chromium browser"
        ) from e
    if bundle.get("status") != "unreviewed" or any(
        r.get("status") != "unreviewed" or r.get("findings")
        for r in bundle.get("size_reviews", [])
    ):
        raise FontifyError(
            "browser capture cannot overwrite reviewed evidence; create a new proof bundle"
        )
    destinations = [
        evidence_path.parent / f"size-woff2-{size}-dpr{device_scale:g}.png"
        for size in bundle["proofing"]["sizes_ppem"]
    ]
    if any(path.exists() or path.is_symlink() for path in destinations):
        raise FontifyError(
            "browser screenshots already exist or a partial capture remains; preserve it and create a new evidence directory"
        )
    # Verify the embedded webfont bytes, rather than trusting a filename or face label.
    encoded = re.search(r"data:font/woff2;base64,([A-Za-z0-9+/=]+)", html)
    try:
        matches_font = (
            encoded
            and hashlib.sha256(base64.b64decode(encoded[1], validate=True)).hexdigest()
            == bundle["font_hashes"]["woff2"]
        )
    except ValueError:
        matches_font = False
    if not matches_font:
        raise FontifyError("embedded WOFF2 does not match the size proof bundle")
    try:
        with sync_playwright() as p:
            options = {"headless": True}
            if executable_path is not None:
                options["executable_path"] = str(executable_path)
            browser = p.chromium.launch(**options)
            try:
                context = browser.new_context(
                    device_scale_factor=device_scale,
                    viewport={"width": 1600, "height": 1000},
                )
                page = context.new_page()
                # Proofs are self-contained. Prevent authored HTML from making network requests.
                page.route(
                    "**/*",
                    lambda route: (
                        route.continue_()
                        if route.request.url == proof_html.as_uri()
                        or route.request.url.startswith("data:")
                        else route.abort()
                    ),
                )
                page.goto(proof_html.as_uri(), wait_until="load")
                page.evaluate("() => window.fontifyProofReady")
                loaded = page.evaluate(
                    "() => document.documentElement.dataset.fontifyLoaded === 'true' && document.fonts.check('12px FontifySizeProof')"
                )
                if not loaded:
                    raise FontifyError("real browser did not load the embedded WOFF2")
                actual = page.locator("#fontify-proof-data").text_content()
                expected = {
                    k: bundle[k]
                    for k in ("schema", "font_hashes", "proofing", "samples")
                }
                if json.loads(actual) != expected:
                    raise FontifyError(
                        "browser proof metadata differs from the evidence bundle"
                    )
                renderer = {
                    "kind": "browser",
                    "name": "Chromium",
                    "version": browser.version,
                    "engine": "Blink",
                    "user_agent": page.evaluate("navigator.userAgent"),
                }
                screenshots = []
                for size in bundle["proofing"]["sizes_ppem"]:
                    section = page.locator(f"#size-{size}")
                    observed = section.locator(".sample").evaluate_all(
                        "els => els.map(e => ({category:e.dataset.category,text:e.textContent,size:getComputedStyle(e).fontSize,family:getComputedStyle(e).fontFamily,transform:getComputedStyle(e).transform}))"
                    )
                    expected_rows = _rows(bundle["samples"])
                    if len(observed) != len(expected_rows) or any(
                        (r["category"], r["text"]) != expected_rows[i]
                        or r["size"] != f"{size}px"
                        or r["family"] != "FontifySizeProof"
                        or r["transform"] != "none"
                        for i, r in enumerate(observed)
                    ):
                        raise FontifyError(
                            "browser samples changed, fell back, or are not at the declared fixed size"
                        )
                    box = section.bounding_box()
                    if (
                        box is None
                        or max(box["width"], box["height"]) * device_scale > 32768
                    ):
                        raise FontifyError(
                            "browser proof dimensions are invalid; shorten samples instead of scaling"
                        )
                    page.set_viewport_size(
                        {
                            "width": math.ceil(box["width"]) + 48,
                            "height": min(16000, math.ceil(box["height"]) + 48),
                        }
                    )
                    path = (
                        evidence_path.parent
                        / f"size-woff2-{size}-dpr{device_scale:g}.png"
                    )
                    section.screenshot(
                        path=str(path), animations="disabled", scale="device"
                    )
                    item = _record(
                        "woff2", size, bundle["font_hashes"]["woff2"], bundle["samples"]
                    )
                    item.update(
                        renderer=renderer,
                        device_scale=device_scale,
                        proof=path.name,
                        proof_sha256=sha256(path),
                        pixel_dimensions=_png_dimensions(path),
                        font_loaded=True,
                        html_sha256=bundle["html_sha256"],
                        html=str(proof_html.relative_to(evidence_path.parent))
                        if proof_html.is_relative_to(evidence_path.parent)
                        else str(proof_html),
                    )
                    screenshots.append(item)
                # Preserve TTF evidence. A capture is still pending visual inspection.
                bundle["size_reviews"] = [
                    r
                    for r in bundle["size_reviews"]
                    if r["format"] != "woff2"
                    or (r.get("proof") and r["device_scale"] != device_scale)
                ] + screenshots
                bundle["status"] = "unreviewed"
                evidence_path.write_text(json.dumps(bundle, indent=2) + "\n")
            finally:
                browser.close()
    except (PlaywrightError, OSError) as e:
        raise FontifyError(
            f"real-browser size capture failed: {e}; any partial PNGs remain unreviewed. Use a new evidence directory for a retry"
        ) from e
    return bundle


def _png_dimensions(path):
    data = Path(path).read_bytes()
    if len(data) < 33 or data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
        raise FontifyError(
            "size evidence must be an actual PNG raster or browser screenshot"
        )
    width, height = struct.unpack(">II", data[16:24])
    if not width or not height:
        raise FontifyError("size evidence PNG has invalid dimensions")
    return [width, height]


def check_size_reviews(project, profile, receipt, report):
    """Enforce each size/format and bind reviewed PNGs to current build hashes."""
    reviews = receipt.get("size_reviews")
    if not isinstance(reviews, list) or not reviews:
        raise FontifyError(
            "release needs reviewed TTF and real-browser WOFF2 evidence at every intended size"
        )
    expected_samples = proof_samples(project)
    hashes = {"ttf": report.get("font_sha256"), "woff2": report.get("webfont_sha256")}
    if not all(hashes.values()):
        raise FontifyError(
            "size review requires an audit of both the current TTF and WOFF2"
        )
    expected = {
        (fmt, size) for fmt in hashes for size in profile["proofing"]["sizes_ppem"]
    }
    found = set()
    seen = set()
    for item in reviews:
        keys(
            item,
            "format font_sha256 size size_unit device_scale renderer proof proof_sha256 pixel_dimensions samples status findings font_loaded html html_sha256",
            "size review",
        )
        fmt, size = item.get("format"), item.get("size")
        if (
            not isinstance(fmt, str)
            or type(size) is not int
            or (fmt, size) not in expected
        ):
            raise FontifyError("size review has an unexpected format or size")
        scale = item.get("device_scale")
        if (
            isinstance(scale, bool)
            or not isinstance(scale, (int, float))
            or scale not in (1, 2)
            or (fmt == "ttf" and scale != 1)
        ):
            raise FontifyError(
                "invalid proof device scale; TTF must use one actual pixel per ppem"
            )
        ident = (fmt, size, scale)
        if ident in seen:
            raise FontifyError("duplicate size proof evidence")
        seen.add(ident)
        if item.get("font_sha256") != hashes[fmt]:
            raise FontifyError("size review is stale: font changed")
        if item.get("size_unit") != ("ppem" if fmt == "ttf" else "css_px"):
            raise FontifyError("size evidence uses the wrong size units")
        if item.get("samples") != expected_samples:
            raise FontifyError(
                "size evidence must cover the current repertoire, words, confusables, punctuation and mixed case"
            )
        renderer = item.get("renderer")
        if not isinstance(renderer, dict) or any(
            not isinstance(renderer.get(k), str) or not renderer[k].strip()
            for k in ("kind", "name", "version")
        ):
            raise FontifyError("size proof must identify its renderer and version")
        if fmt == "ttf":
            if (
                renderer["kind"] != "rasterizer"
                or renderer["name"] != "Pillow/FreeType"
                or not renderer.get("freetype_version")
                or renderer.get("shaping") != "RAQM/HarfBuzz"
            ):
                raise FontifyError(
                    "TTF proof needs actual FreeType rasterization with shaped text"
                )
        elif (
            renderer["kind"] != "browser"
            or renderer["name"]
            not in ("Chromium", "Chrome", "Firefox", "WebKit", "Safari")
            or not renderer.get("engine")
            or not renderer.get("user_agent")
            or item.get("font_loaded") is not True
            or not re.fullmatch(r"[0-9a-f]{64}", str(item.get("html_sha256", "")))
        ):
            raise FontifyError(
                "WOFF2 proof needs an actual browser renderer and successful font loading, not a Pillow substitute"
            )
        if fmt == "woff2":
            html_path = local_path(project.root, item.get("html"))
            if not html_path.is_file() or sha256(html_path) != item["html_sha256"]:
                raise FontifyError("browser proof HTML is missing or stale")
            html = html_path.read_text()
            encoded = re.search(r"data:font/woff2;base64,([A-Za-z0-9+/=]+)", html)
            metadata = re.search(
                r'<script id="fontify-proof-data" type="application/json">(.*?)</script>',
                html,
                re.DOTALL,
            )
            try:
                matching = (
                    encoded
                    and hashlib.sha256(
                        base64.b64decode(encoded[1], validate=True)
                    ).hexdigest()
                    == hashes["woff2"]
                    and metadata
                    and json.loads(metadata[1])
                    == {
                        "schema": 1,
                        "font_hashes": hashes,
                        "proofing": profile["proofing"],
                        "samples": expected_samples,
                    }
                )
            except (ValueError, TypeError):
                matching = False
            if not matching:
                raise FontifyError(
                    "browser HTML does not match the current font, size plan and samples"
                )
        path = local_path(project.root, item.get("proof"))
        if not path.is_file() or sha256(path) != item.get("proof_sha256"):
            raise FontifyError("size proof is missing or stale")
        if item.get("pixel_dimensions") != _png_dimensions(path):
            raise FontifyError("size proof pixel dimensions do not match its evidence")
        if item.get("status") != "passed":
            raise FontifyError("size proof is unreviewed or has unresolved findings")
        findings = item.get("findings")
        if not isinstance(findings, dict) or set(findings) != FINDING_AREAS:
            raise FontifyError(
                "size review needs findings for every optical and coverage area"
            )
        for area, finding in findings.items():
            keys(finding, "status notes", "size review finding")
            wanted = (
                "not_applicable"
                if area in expected_samples and not expected_samples[area]
                else "passed"
            )
            notes = finding.get("notes")
            if (
                finding.get("status") != wanted
                or not isinstance(notes, str)
                or len(notes.strip()) < 20
                or notes.strip().lower()
                in {
                    "pending visual review",
                    "all checks passed",
                    "no issues found",
                    "not applicable",
                }
            ):
                raise FontifyError(
                    f"size review needs concrete resolved findings: {area}"
                )
        if scale == 1:
            found.add((fmt, size))
    if found != expected:
        missing = ", ".join(f"{fmt}@{size}" for fmt, size in sorted(expected - found))
        raise FontifyError("size review is incomplete at device scale 1: " + missing)
    return {
        "status": "passed",
        "intended_use": profile["proofing"]["intended_use"],
        "min_supported_ppem": profile["proofing"]["min_supported_ppem"],
        "sizes_ppem": profile["proofing"]["sizes_ppem"],
        "reviewed_proofs": len(reviews),
        "human_approval": "not_implied",
    }
