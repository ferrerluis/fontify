"""Approval fingerprints and proofs drawn from the compiled font via HarfBuzz."""

import base64
import hashlib
import json
import unicodedata
from html import escape
from pathlib import Path

import uharfbuzz as hb
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.ttLib import TTFont

from .model import FontifyError, local_path


def approval_snapshot(project, outlines):
    return {
        "schema": 1,
        "construction": {
            k: project.data[k]
            for k in (
                "units_per_em",
                "ascender",
                "descender",
                "line_gap",
                "svg_baseline",
                "curve_error",
            )
        },
        "glyphs": {
            o.spec["name"]: {
                "source_sha256": o.source_hash,
                "normalized_sha256": o.normalized_hash,
                "compiled_sha256": o.compiled_hash,
                "unicode": o.spec["unicode"],
                "advance": o.spec["advance"],
            }
            for o in outlines
        },
    }


def check_approval(project, outlines):
    if not project.data.get("approval"):
        return {"status": "review_required", "checked_glyphs": 0}
    p = local_path(project.root, project.data["approval"])
    try:
        approved = json.loads(p.read_text())
    except (OSError, ValueError) as e:
        raise FontifyError(f"cannot read approval baseline: {e}") from e
    current = approval_snapshot(project, outlines)
    if (
        not isinstance(approved, dict)
        or approved.get("schema") != 1
        or not isinstance(approved.get("glyphs"), dict)
    ):
        raise FontifyError("invalid approval baseline")
    if approved.get("construction") != current["construction"]:
        raise FontifyError(
            "approved construction settings changed; review and create a new baseline"
        )
    changed = [
        n for n, g in approved["glyphs"].items() if current["glyphs"].get(n) != g
    ]
    if changed:
        raise FontifyError(
            f"approved glyphs changed or disappeared: {', '.join(changed)}; compare before reapproval"
        )
    unreviewed = sorted(set(current["glyphs"]) - set(approved["glyphs"]))
    return {
        "status": "baseline_matches_with_unreviewed_glyphs"
        if unreviewed
        else "baseline_matches",
        "checked_glyphs": len(approved["glyphs"]),
        "unreviewed_glyphs": unreviewed,
    }


def shape_font(path, text, kern=True):
    path = Path(path)
    # HarfBuzz consumes sfnt, not a webfont container: decompress if necessary.
    font = TTFont(path)
    cmap = font.getBestCmap()
    missing = sorted(set(map(ord, text)) - set(cmap))
    if missing:
        missing = sorted(set(map(ord, unicodedata.normalize("NFC", text))) - set(cmap))
    if missing:
        font.close()
        raise FontifyError(
            "text contains unmapped characters: "
            + ", ".join(f"U+{cp:04X}" for cp in missing)
        )
    import io

    stream = io.BytesIO()
    font.flavor = None
    font.save(stream)
    face = hb.Face(stream.getvalue())
    hfont = hb.Font(face)
    hfont.scale = (face.upem, face.upem)
    hb.ot_font_set_funcs(hfont)
    buf = hb.Buffer()
    buf.add_str(text)
    buf.guess_segment_properties()
    hb.shape(hfont, buf, {"kern": kern})
    names = font.getGlyphOrder()
    glyphs = [
        {
            "name": names[i.codepoint],
            "gid": i.codepoint,
            "cluster": i.cluster,
            "x_advance": p.x_advance,
            "y_advance": p.y_advance,
            "x_offset": p.x_offset,
            "y_offset": p.y_offset,
        }
        for i, p in zip(buf.glyph_infos, buf.glyph_positions)
    ]
    font.close()
    return {
        "text": text,
        "kern": kern,
        "advance": sum(g["x_advance"] for g in glyphs),
        "glyphs": glyphs,
    }


def inspect_font(path, text=None):
    font = TTFont(path, checkChecksums=2)
    cmap = font.getBestCmap()
    result = {
        "family": font["name"].getDebugName(1),
        "style": font["name"].getDebugName(2),
        "version": font["name"].getDebugName(5),
        "units_per_em": font["head"].unitsPerEm,
        "tables": sorted(font.keys()),
        "coverage": [f"U+{cp:04X}" for cp in sorted(cmap)],
        "characters": "".join(map(chr, sorted(cmap))),
        "glyph_count": len(font.getGlyphOrder()),
        "metrics": {n: list(font["hmtx"][n]) for n in font.getGlyphOrder()},
    }
    font.close()
    if text is not None:
        result["shaping"] = shape_font(path, text)
    return result


def glyph_path(glyphset, name):
    pen = SVGPathPen(glyphset)
    glyphset[name].draw(pen)
    return pen.getCommands()


def line_svg(font, path, text, size, kern=True):
    shaped = shape_font(path, text, kern)
    gs = font.getGlyphSet()
    upm = font["head"].unitsPerEm
    asc = font["hhea"].ascent
    desc = font["hhea"].descent
    scale = size / upm
    x = 0
    paths = []
    ink_left = 0
    ink_right = 0
    for g in shaped["glyphs"]:
        d = glyph_path(gs, g["name"])
        bounds = BoundsPen(gs)
        gs[g["name"]].draw(bounds)
        if bounds.bounds:
            ink_left = min(ink_left, x + g["x_offset"] + bounds.bounds[0])
            ink_right = max(ink_right, x + g["x_offset"] + bounds.bounds[2])
        paths.append(
            f'<path d="{d}" transform="translate({x + g["x_offset"]} {g["y_offset"]})"/>'
        )
        x += g["x_advance"]
    origin = max(16, 2 - ink_left * scale)
    width = max(1, x * scale + origin + 16, ink_right * scale + origin + 16)
    height = (asc - desc) * scale + 16
    return (
        f'<svg role="img" aria-label="{escape(text, quote=True)}" viewBox="0 0 {width:g} {height:g}" width="{width:g}" height="{height:g}" style="max-width:100%;height:auto"><g transform="translate({origin:g} {asc * scale + 8:g}) scale({scale:g} {-scale:g})">'
        + "".join(paths)
        + "</g></svg>"
    )


def write_proofs(font_path, woff_path, directory, project, outlines, approval):
    directory = Path(directory)
    font = TTFont(font_path)
    gs = font.getGlyphSet()
    d = project.data
    upm = d["units_per_em"]
    cards = []
    tiles = []
    boxes = [
        o.diagnostics["compiled_bounds"]
        for o in outlines
        if o.diagnostics.get("compiled_bounds")
    ] or [[0, 0, 0, 0]]
    left = min(b[0] for b in boxes)
    right = max(b[2] for b in boxes)
    bottom = min(b[1] for b in boxes)
    scale = min(
        140 / upm,
        168 / max(right, 1),
        176 / max(right - left, 1),
        148 / max(d["ascender"] - bottom, 1),
    )
    origin = max(10, 2 - left * scale)
    for index, o in enumerate(outlines):
        n = o.spec["name"]
        char = chr(int(o.spec["unicode"][2:], 16))
        p = glyph_path(gs, n)
        # Shared scale and baseline: never stretch each glyph to fill its tile.
        tile = f'<g transform="translate({origin:g} {d["ascender"] * scale + 6:g}) scale({scale:g} {-scale:g})"><path d="{p}"/></g>'
        label = f"{escape(n)} · {o.spec['unicode']} · advance {o.spec['advance']}"
        cards.append(
            f'<article><svg viewBox="0 0 180 156" role="img" aria-label="{escape(char, quote=True)}">{tile}</svg><b>{label}</b><small>bounds {escape(str(o.diagnostics.get("compiled_bounds")))}</small></article>'
        )
        x = (index % 6) * 200
        y = (index // 6) * 200
        tiles.append(
            f'<g transform="translate({x} {y})">{tile}<text x="10" y="180" font-size="12" font-family="monospace">{label}</text></g>'
        )
    height = ((len(outlines) + 5) // 6) * 200 + 50
    sheet = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="{height}" viewBox="0 0 1200 {height}"><rect width="100%" height="100%" fill="#f7f5ef"/><g transform="translate(0 35)" fill="#151515">'
        + "".join(tiles)
        + f'</g><text x="10" y="22" font-size="18" font-family="sans-serif">{escape(d["family"])} {d["version"]} — compiled outlines, shared scale</text></svg>'
    )
    (directory / "glyph-sheet.svg").write_text(sheet)
    samples = []
    for text in d["samples"]:
        samples.append(
            f"<section><h2>{escape(text)}</h2><p>HarfBuzz · kerning on</p>{line_svg(font, font_path, text, 72)}<details><summary>Kerning off</summary>{line_svg(font, font_path, text, 72, False)}</details></section>"
        )
    webfont = base64.b64encode(Path(woff_path).read_bytes()).decode()
    coverage = " ".join(f"U+{int(g['unicode'][2:], 16):04X}" for g in project.glyphs)
    html = """<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Fontify proof</title><style>
    @font-face{font-family:Proof;src:url(data:font/woff2;base64,WEBFONT) format('woff2')}
    *{box-sizing:border-box}body{margin:0;background:#f7f5ef;color:#171713;font:16px/1.5 system-ui,sans-serif}main{max-width:1180px;margin:auto;padding:32px}h1{font-size:44px;margin:0}h2{font-size:18px}p{max-width:85ch}section{border-top:1px solid #ccc9bd;padding:22px 0;overflow:auto}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(185px,1fr));gap:12px}article{background:#fffdf7;border:1px solid #dedace;padding:8px}article svg{width:100%;height:156px}b,small{display:block;font-size:12px;overflow-wrap:anywhere}small{color:#666}textarea{width:100%;min-height:150px;font:52px Proof,monospace;background:white;padding:14px}code{overflow-wrap:anywhere}summary{cursor:pointer}#status{font-weight:600}
    </style><main>CONTENT</main><script>
    const allowed=new Set(COVERAGE);const input=document.querySelector('textarea');const status=document.querySelector('#status');
    function check(){const missing=[...new Set([...input.value].filter(c=>!allowed.has(c.codePointAt(0))))];status.textContent=missing.length?'Unsupported characters (fallback may appear): '+missing.join(' '):'All typed characters are covered';}
    input.addEventListener('input',check);document.fonts.load('52px Proof').then(check);
    </script></html>"""
    content = (
        f'<h1>{escape(d["family"])} <small>Version {d["version"]}</small></h1><p>Font construction: {escape(approval["status"])}. Human review is still required for optical weight, curves, symmetry, spacing and style.</p><p>The sheet and samples use outlines from the actual TTF. Each line uses HarfBuzz positions; no generated replacement lettering.</p><section><h2>Type a sample</h2><label for="sample">Live WOFF2 preview</label><textarea id="sample" spellcheck="false">{escape(d["samples"][0])}</textarea><p id="status">Loading embedded font…</p></section>'
        + "".join(samples)
        + f'<section><h2>Exact coverage ({len(project.glyphs)} mappings)</h2><code>{coverage}</code></section><section><h2>Glyph review · shared scale</h2><div class="grid">'
        + "".join(cards)
        + "</div></section>"
    )
    html = (
        html.replace("WEBFONT", webfont)
        .replace("CONTENT", content)
        .replace("COVERAGE", json.dumps(sorted(font.getBestCmap())))
    )
    if d.get("coverage") is not None:
        html = html.replace(
            "[...input.value].filter", "[...input.value.normalize('NFC')].filter"
        )
    (directory / "proof.html").write_text(html)
    font.close()
    # Historical schema-1/2 releases remain byte-for-byte reproducible.
    from .quality import load_profile

    profile = load_profile(project)
    if profile and profile["schema"] == 3:
        from .proofing import write_size_proofs

        write_size_proofs(font_path, woff_path, directory, project, profile)


def verified_release(manifest_path):
    path = Path(manifest_path).resolve()
    try:
        d = json.loads(path.read_text())
    except (OSError, ValueError) as e:
        raise FontifyError(f"cannot read release manifest: {e}") from e
    if (
        not isinstance(d, dict)
        or d.get("schema") != 1
        or not isinstance(d.get("artifacts"), dict)
        or not d["artifacts"]
    ):
        raise FontifyError("invalid release manifest")
    if any(d.get(k) not in d["artifacts"] for k in ("font", "webfont")):
        raise FontifyError("release font/webfont must be hashed artifacts")
    for name, expected in d["artifacts"].items():
        p = local_path(path.parent, name)
        if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest() != expected:
            raise FontifyError(f"release artifact mismatch: {name}")
    return d


def compare_releases(before, after, out):
    a = verified_release(before)
    b = verified_release(after)
    fa = TTFont(Path(before).parent / a["font"])
    fb = TTFont(Path(after).parent / b["font"])
    if fa["head"].unitsPerEm != fb["head"].unitsPerEm:
        raise FontifyError("comparison requires the same units_per_em")
    ga, gb = fa.getGlyphSet(), fb.getGlyphSet()
    cards = []
    changed = []
    outline_changed = []
    layout_changed = []
    source_only = []
    for name in sorted(set(a["glyphs"]) | set(b["glyphs"])):
        old = a["glyphs"].get(name)
        new = b["glyphs"].get(name)
        equal = old == new
        same_outline = (
            old is not None
            and new is not None
            and old["compiled_sha256"] == new["compiled_sha256"]
        )
        same_layout = (
            old is not None
            and new is not None
            and (old["unicode"], old["advance"]) == (new["unicode"], new["advance"])
        )
        if not equal:
            changed.append(name)
        if not same_outline:
            outline_changed.append(name)
        if not same_layout:
            layout_changed.append(name)
        if not equal and same_outline and same_layout:
            source_only.append(name)
        label = (
            "unchanged"
            if equal
            else (
                "OUTLINE CHANGED"
                if not same_outline
                else (
                    "mapping/advance changed"
                    if not same_layout
                    else "source record changed; exported outline identical"
                )
            )
        )
        paths = []
        for gs, color in [(ga, "#d33352"), (gb, "#087eaa")]:
            if name in gs:
                paths.append(
                    f'<path d="{glyph_path(gs, name)}" fill="{color}" fill-opacity=".55"/>'
                )
        asc = max(fa["hhea"].ascent, fb["hhea"].ascent)
        desc = min(fa["hhea"].descent, fb["hhea"].descent)
        width = max(
            fa["hmtx"].metrics.get(name, (0, 0))[0],
            fb["hmtx"].metrics.get(name, (0, 0))[0],
            1000,
        )
        cards.append(
            f'<article><h2>{escape(name)} — {label}</h2><svg viewBox="-40 0 {width + 80} {asc - desc + 40}" width="240" height="240"><g transform="translate(0 {asc + 20}) scale(1 -1)">'
            + "".join(paths)
            + "</g></svg></article>"
        )
    html = (
        '<!doctype html><html lang="en"><meta charset="utf-8"><title>Fontify comparison</title><style>body{background:#f7f5ef;font:16px system-ui;padding:30px}.grid{display:flex;flex-wrap:wrap}article{border:1px solid #ccc;margin:8px;padding:10px}h2{font-size:16px}</style><h1>Before / after overlay</h1><p>Before = red · after = blue · shared origin, scale and baseline. Purple overlap means shared ink. Review sidebearings in the manifests. This comparison does not confer approval.</p><p>'
        + str(len(changed))
        + f' changed glyph records; {len(outline_changed)} exported outlines changed; {len(source_only)} source-only changes.</p><div class="grid">'
        + "".join(cards)
        + "</div></html>"
    )
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "comparison.html").write_text(html)
    result = {
        "before": a["version"],
        "after": b["version"],
        "changed_glyphs": changed,
        "outline_changed_glyphs": outline_changed,
        "mapping_or_advance_changed_glyphs": layout_changed,
        "source_only_changes": source_only,
        "kerning_changed": a["kerning"] != b["kerning"],
        "metrics_changed": a["metrics"] != b["metrics"],
    }
    (out / "comparison.json").write_text(json.dumps(result, indent=2) + "\n")
    fa.close()
    fb.close()
    return result
