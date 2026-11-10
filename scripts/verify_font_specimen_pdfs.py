#!/usr/bin/env python3
"""Independently validate specimen coverage, source paths and shaped PDF text."""

import argparse
import datetime
import hashlib
import json
import re
import string
from pathlib import Path

from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.reportLabPen import ReportLabPen
from fontTools.ttLib import TTFont
from pypdf import PdfReader
from reportlab.pdfgen.pathobject import PDFPathObject


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(source, root, fonts, qa):
    path = root / qa["pdf"]
    font_path = fonts / source["ttf"]
    assert sha256(font_path) == source["ttf_sha256"] == qa["ttf_sha256"]
    assert sha256(path) == qa["pdf_sha256"]
    font = TTFont(font_path)
    cmap, glyphs = font.getBestCmap(), font.getGlyphSet()
    assert len(cmap) == source["coverage"]
    reader = PdfReader(path)
    assert len(reader.pages) == 8
    actual = []
    labels = []
    forms = {}
    for page in reader.pages:
        data = page.get_contents().get_data()
        actual.extend(
            bytes.fromhex(x.decode())[2:].decode("utf-16-be")
            for x in re.findall(rb"/ActualText <([0-9A-F]+)>", data)
        )
        labels.append(page.extract_text())
        for name, ref in page["/Resources"].get("/XObject", {}).items():
            obj = ref.get_object()
            assert obj["/Subtype"] == "/Form", "Raster image in specimen"
            forms[name] = obj
    assert actual == [s["text"] for s in qa["shaped_samples"]]
    assert string.ascii_uppercase in actual and string.ascii_lowercase in actual
    first_page = [s["text"] for s in qa["shaped_samples"] if s["page"] == 1]
    joined = " ".join(first_page)
    assert "THE QUICK BROWN FOX JUMPS OVER THE LAZY DOG." in joined
    assert "the quick brown fox jumps over the lazy dog." in joined
    for char in "rwye":
        for symbol in ".,/\\":
            assert any(
                symbol + char in text and char + symbol in text for text in actual
            )
    expected = sorted(set(cmap) - set(map(ord, string.ascii_letters)))
    printed = re.findall(r"U\+[0-9A-F]{4,6}", "\n".join(labels))
    assert printed == [f"U+{cp:04X}" for cp in expected] == qa["special_codepoints"]
    assert any(abs(x["on_minus_off_pt"]) > 0.01 for x in qa["kerning_deltas"])
    assert source["family"] in reader.metadata.title
    assert source["version"] in reader.metadata.title
    for i, text in enumerate(labels):
        assert source["family"] in text and source["version"] in text
        assert f"{i + 1:02d} / 08" in text
    helpers = [
        g for g in font.getGlyphOrder() if g not in cmap.values() and g != ".notdef"
    ]
    assert helpers == qa["helpers"]
    for glyph in helpers:
        assert glyph in labels[2]
    checked = 0
    # Compare every specimen form's actual vector path with the original TTF.
    for glyph in set(cmap.values()) | set(helpers):
        bounds = BoundsPen(glyphs)
        glyphs[glyph].draw(bounds)
        if not bounds.bounds:
            continue
        key = f"/FormXob.g{font.getGlyphID(glyph)}"
        assert key in forms, (source["family"], glyph)
        form = forms[key]
        pen_path = PDFPathObject()
        pen_path.closePath = pen_path.close
        glyphs[glyph].draw(ReportLabPen(glyphs, pen_path))
        expected_path = pen_path.getCode()
        assert expected_path in form.get_data().decode("ascii"), (
            source["family"],
            glyph,
        )
        expected_box = [
            bounds.bounds[0] - 1,
            bounds.bounds[1] - 1,
            bounds.bounds[2] + 1,
            bounds.bounds[3] + 1,
        ]
        assert all(
            abs(float(a) - b) < 0.001 for a, b in zip(form["/BBox"], expected_box)
        )
        checked += 1
    return {
        "family": source["family"],
        "version": source["version"],
        "pdf": path.name,
        "pdf_sha256": sha256(path),
        "pages": 8,
        "mapped_characters": len(cmap),
        "inventory_characters": len(expected),
        "helpers": len(helpers),
        "verified_vector_outlines": checked,
        "content": "passed",
        "coverage": "passed",
        "source_outlines": "passed",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fonts", type=Path, required=True)
    parser.add_argument("--root", type=Path, default=Path("docs/font-specimens"))
    parser.add_argument("--qa", type=Path, default=Path("test-runs/specimens/qa.json"))
    parser.add_argument(
        "--output", type=Path, default=Path("test-runs/specimens/content-results.json")
    )
    args = parser.parse_args()
    sources = json.loads((args.root / "sources.json").read_text())["families"]
    qa = json.loads(args.qa.read_text())
    assert (
        len(sources) == len(qa["families"]) == len(list(args.root.glob("*.pdf"))) == 10
    )
    assert not qa["layout_violations"]
    results = [
        verify(source, args.root, args.fonts, proof)
        for source, proof in zip(sources, qa["families"])
    ]
    result = {
        "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "families": results,
        "total_pages": sum(x["pages"] for x in results),
        "scope": "Exact source hashes, document content, coverage and vector paths. Visual review is separate.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
