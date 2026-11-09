"""Check frozen sample artifacts offline; does not rebuild fonts or grant approval."""

import argparse
import csv
import hashlib
import io
import json
import unicodedata
from pathlib import Path

import uharfbuzz as hb
from fontTools.pens.recordingPen import RecordingPen
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parents[1] / "examples" / "modernized"
MARKS = {0x300, 0x301, 0x302, 0x303, 0x304, 0x306, 0x307, 0x308,
         0x30A, 0x30B, 0x30C, 0x326, 0x327, 0x328}


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sfnt(font):
    """Decode WOFF2 for HarfBuzz without modifying any supplied file."""
    original = font.flavor
    font.flavor = None
    stream = io.BytesIO()
    font.save(stream, reorderTables=False)
    font.flavor = original
    return stream.getvalue()


def shape(font, text):
    buffer = hb.Buffer()
    buffer.add_str(text)
    buffer.guess_segment_properties()
    hb.shape(font, buffer)
    return [(g.codepoint, p.x_advance, p.y_advance, p.x_offset, p.y_offset)
            for g, p in zip(buffer.glyph_infos, buffer.glyph_positions)]


def outlines(font):
    result = {}
    glyphs = font.getGlyphSet()
    for name in font.getGlyphOrder():
        pen = RecordingPen()
        glyphs[name].draw(pen)
        result[name] = pen.value
    return result


def check_sample(entry, required):
    folder = ROOT / entry["slug"]
    meta = json.loads((folder / "metadata.json").read_text())
    for key in ("name", "version", "coverage_count", "minimum_display_px"):
        assert meta[key] == entry[key], (entry["slug"], key)
    for asset in meta["assets"].values():
        path = folder / asset["path"]
        assert sha256(path) == asset["sha256"], str(path)
        assert path.stat().st_size == asset["bytes"], str(path)
    paths = [folder / meta["assets"][ext]["path"] for ext in ("ttf", "woff2")]
    with TTFont(paths[0], checkChecksums=2) as ttf, TTFont(paths[1]) as woff:
        cm = ttf.getBestCmap()
        assert cm == woff.getBestCmap()
        expected = required | {int(cp[2:], 16) for cp in meta["extra_codepoints"]}
        assert set(cm) == expected and len(cm) == meta["coverage_count"]
        assert ttf.getGlyphOrder() == woff.getGlyphOrder()
        assert ttf["hmtx"].metrics == woff["hmtx"].metrics
        assert outlines(ttf) == outlines(woff), entry["slug"]
        for table in ("GPOS", "GSUB", "GDEF", "name", "OS/2", "cmap"):
            assert ttf[table].compile(ttf) == woff[table].compile(woff), table
        assert ttf["name"].getDebugName(1) == meta["name"]
        assert ttf["name"].getDebugName(5) == "Version " + meta["version"]
        assert "private" in ttf["name"].getDebugName(13).lower()
        for cp in (0x20, 0xA0):
            assert ttf["glyf"][cm[cp]].numberOfContours == 0
            assert ttf["hmtx"][cm[cp]][0] > 0
        for cp in MARKS:
            name = cm[cp]
            assert ttf["hmtx"][name][0] == 0
            assert ttf["glyf"][name].numberOfContours != 0
            assert ttf["GDEF"].table.GlyphClassDef.classDefs[name] == 3
        with (folder / "coverage.csv").open(newline="") as stream:
            recorded = list(csv.DictReader(stream))
        assert len(recorded) == len(cm)
        assert {int(r["codepoint"][2:], 16): r["glyph"] for r in recorded} == cm
        assert all(int(r["advance"]) == ttf["hmtx"][r["glyph"]][0]
                   for r in recorded)
        canonical = [chr(cp) for cp in cm
                     if unicodedata.normalize("NFD", chr(cp)) != chr(cp)
                     and all(ord(c) in cm for c in unicodedata.normalize("NFD", chr(cp)))]
        counts = []
        for actual in (ttf, woff):
            font = hb.Font(hb.Face(sfnt(actual)))
            font.scale = (actual["head"].unitsPerEm,) * 2
            for cp in cm:
                assert all(g[0] != 0 for g in shape(font, chr(cp))), hex(cp)
            for text in canonical:
                assert shape(font, text) == shape(font, unicodedata.normalize("NFD", text)), text
            for cp in MARKS:
                shaped = shape(font, "b" + chr(cp))
                assert len(shaped) == 2 and shaped[-1][1] == 0
                assert shaped[-1][3] or shaped[-1][4], hex(cp)
            for a, b, base in (("j\u0326\u0301", "j\u0301\u0326", "j"),
                               ("i\u0326\u030B", "i\u030B\u0326", "i")):
                first, reversed_input = shape(font, a), shape(font, b)
                assert first == reversed_input and len(first) == 3
                assert first[0][0] != shape(font, base)[0][0]
                assert first[0][0] == shape(font, base + a[-1])[0][0]
                assert all(g[1] == 0 for g in first[1:])
                assert shape(font, base + "\u0326")[0][0] == shape(font, base)[0][0]
            assert shape(font, "į") == shape(font, "i\u0328")
            plain = shape(font, "softhyphen")
            soft = shape(font, "soft\u00adhyphen")
            assert sum(g[1] for g in plain) == sum(g[1] for g in soft)
            assert [g for g in plain if g[1]] == [g for g in soft if g[1]]
            counts.append(len(canonical))
        return {"name": meta["name"], "version": meta["version"],
                "status": "passed", "coverage": len(cm), "extras": meta["extra_codepoints"],
                "glyphs": len(ttf.getGlyphOrder()), "canonical_pairs_per_format": counts,
                "font_hashes": {ext: meta["assets"][ext]["sha256"] for ext in ("ttf", "woff2")},
                "checks": ["exact artifact hashes", "all outlines and metrics in both formats",
                           "exact layout and naming tables", "all scalars shape without .notdef",
                           "canonical shaping", "14 zero-advance classified/attached marks",
                           "mixed mark ordering/context and below-only dot retention",
                           "space/NBSP blanks", "native soft-hyphen hiding"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    union = json.loads((ROOT / "required-union.json").read_text())
    required = {int(cp[2:], 16) for cp in union["codepoints"]}
    assert len(required) == union["count"] == 354
    entries = json.loads((ROOT / "catalog.json").read_text())["samples"]
    assert len(entries) == 10
    results = []
    for entry in entries:
        result = check_sample(entry, required)
        results.append(result)
        print(f'{result["name"]} {result["version"]}: passed ({result["coverage"]} mappings)', flush=True)
    report = {"status": "passed", "scope": "Frozen final artifacts only; source-stage release and aesthetic approval are separate.",
              "samples": results}
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
