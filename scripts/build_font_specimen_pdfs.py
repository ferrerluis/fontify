#!/usr/bin/env python3
"""Build cream-and-rust vector specimens from hash-pinned external TTF files.

Dependencies: reportlab, fonttools, uharfbuzz, pypdf. No font installation,
generation service, raster tracing, or source-font modification is performed.
"""

import argparse
import hashlib
import json
import math
import string
from pathlib import Path

import uharfbuzz as hb
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.reportLabPen import ReportLabPen
from fontTools.ttLib import TTFont
from pypdf import PdfReader
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont as PDFTTFont
from reportlab.pdfgen import canvas

W, H = A4
M = 30
WIDTH = W - M * 2
INK = HexColor("#201b17")
RUST = HexColor("#a35c3c")
MUTED = HexColor("#7b6b5d")
PAPER = HexColor("#fffdf8")
RULE = HexColor("#e6dbcf")
BASIC = set(map(ord, string.ascii_letters))


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Specimen:
    def __init__(self, source, path, output):
        self.source, self.path = source, path
        assert sha256(path) == source["ttf_sha256"], path
        self.font = TTFont(path)
        self.cmap = self.font.getBestCmap()
        self.glyphs = self.font.getGlyphSet()
        self.order = self.font.getGlyphOrder()
        self.upem = self.font["head"].unitsPerEm
        self.shaper = hb.Font(hb.Face(path.read_bytes()))
        self.shaper.scale = (self.upem, self.upem)
        hb.ot_font_set_funcs(self.shaper)
        self.name = source["family"]
        self.output = output / f"{self.name}-v{source['version']}-specimen.pdf"
        self.pdf = canvas.Canvas(
            str(self.output), pagesize=A4, pageCompression=1, invariant=1
        )
        self.pdf.setTitle(f"{self.name} {source['version']} | Font specimen")
        self.pdf.setAuthor("Fontify")
        self.pdf.setSubject("Complete character inventory and shaped display proofs")
        self.cache, self.forms = {}, set()
        self.page = 0
        self.records, self.boxes, self.sections = [], [], []
        self.inventory = sorted(set(self.cmap) - BASIC)
        self.helpers = [
            g for g in self.order if g not in self.cmap.values() and g != ".notdef"
        ]
        self.total = 3 + math.ceil(len(self.inventory) / 63)

    def label(self, text, x, y, size=9, color=MUTED, bold=False):
        self.pdf.setFillColor(color)
        self.pdf.setFont("LabelBold" if bold else "Label", size)
        self.pdf.drawString(x, y, text)
        width = pdfmetrics.stringWidth(text, "LabelBold" if bold else "Label", size)
        assert x + width <= W - M + 1, (self.name, text, width)

    def bound(self, glyph):
        if glyph not in self.cache:
            pen = BoundsPen(self.glyphs)
            self.glyphs[glyph].draw(pen)
            self.cache[glyph] = pen.bounds
        return self.cache[glyph]

    def shape(self, text, kern=True):
        assert all(ord(c) in self.cmap for c in text), (self.name, text)
        buffer = hb.Buffer()
        buffer.add_str(text)
        buffer.guess_segment_properties()
        hb.shape(self.shaper, buffer, {"kern": kern})
        assert all(i.codepoint for i in buffer.glyph_infos), (self.name, text)
        return [
            (self.order[i.codepoint], p)
            for i, p in zip(buffer.glyph_infos, buffer.glyph_positions)
        ]

    def measure(self, text, size, kern=True):
        return sum(p.x_advance for _, p in self.shape(text, kern)) * size / self.upem

    def glyph(self, name, x, y, size, region=None):
        box = self.bound(name)
        if not box:
            return
        form = f"g{self.font.getGlyphID(name)}"
        if form not in self.forms:
            self.pdf.beginForm(form, box[0] - 1, box[1] - 1, box[2] + 1, box[3] + 1)
            path = self.pdf.beginPath()
            path.closePath = path.close
            self.glyphs[name].draw(ReportLabPen(self.glyphs, path))
            self.pdf.drawPath(path, fill=1, stroke=0, fillMode=1)
            self.pdf.endForm()
            self.forms.add(form)
        scale = size / self.upem
        actual = [
            x + box[0] * scale,
            y + box[1] * scale,
            x + box[2] * scale,
            y + box[3] * scale,
        ]
        limits = region or [M - 1, 48, W - M + 1, H - 38]
        assert (
            actual[0] >= limits[0]
            and actual[1] >= limits[1]
            and actual[2] <= limits[2]
            and actual[3] <= limits[3]
        ), (self.name, self.page, name, actual, limits)
        self.boxes.append({"page": self.page, "glyph": name, "bounds": actual})
        self.pdf.saveState()
        self.pdf.setFillColor(INK)
        self.pdf.translate(x, y)
        self.pdf.scale(scale, scale)
        self.pdf.doForm(form)
        self.pdf.restoreState()

    def text(self, text, x, y, size, kern=True):
        self.pdf.addLiteral(
            "/Span << /ActualText <FEFF"
            + text.encode("utf-16-be").hex().upper()
            + "> >> BDC"
        )
        advance = 0
        for glyph, pos in self.shape(text, kern):
            self.glyph(
                glyph,
                x + (advance + pos.x_offset) * size / self.upem,
                y + pos.y_offset * size / self.upem,
                size,
            )
            advance += pos.x_advance
        self.pdf.addLiteral("EMC")
        self.records.append(
            {
                "page": self.page,
                "text": text,
                "size_pt": size,
                "kern": kern,
                "advance_pt": advance * size / self.upem,
            }
        )
        return advance * size / self.upem

    def wrapped(self, text, y, size, leading, width=WIDTH):
        row = ""
        for word in text.split(" "):
            trial = (row + " " + word).strip()
            if self.measure(trial, size) > width and row:
                self.text(row, M, y, size)
                y -= leading
                row = word
            else:
                row = trial
        if row:
            self.text(row, M, y, size)
        return y - leading

    def start(self, section, hero=False):
        self.page += 1
        self.sections.append(section)
        self.pdf.setFillColor(PAPER)
        self.pdf.rect(0, 0, W, H, fill=1, stroke=0)
        self.label("FONTIFY  /  TYPE SPECIMENS", M, H - 28, 8, RUST, True)
        size = 60 if hero else 38
        while self.measure(self.name, size) > WIDTH:
            size -= 1
        self.text(self.name, M, H - 104 if hero else H - 81, size)
        y = H - 128 if hero else H - 105
        self.label(
            f"REGULAR {self.source['version']}  /  {section.upper()}",
            M,
            y,
            9,
            RUST,
            True,
        )
        self.label(self.source["description"], M, y - 18, 9)
        self.pdf.setStrokeColor(RULE)
        self.pdf.setLineWidth(0.5)
        self.pdf.line(M, 34, W - M, 34)
        self.label(
            f"{self.name} {self.source['version']}  |  {len(self.cmap)} mapped characters",
            M,
            21,
            7,
        )
        self.label(f"{self.page:02d} / {self.total:02d}", W - M - 35, 21, 7)

    def heading(self, title, y):
        self.label(title, M, y, 9, RUST, True)

    def end(self):
        self.pdf.showPage()

    def build(self):
        self.start("The alphabet & display text", hero=True)
        self.heading("THE ALPHABET", 650)
        upper_size = min(30, 30 * WIDTH / self.measure(string.ascii_uppercase, 30))
        lower_size = min(32, 32 * WIDTH / self.measure(string.ascii_lowercase, 32))
        y = self.wrapped(string.ascii_uppercase, 609, upper_size, 42)
        y = self.wrapped(string.ascii_lowercase, y - 12, lower_size, 44)
        self.heading("THE QUICK BROWN FOX", y - 20)
        y = self.wrapped("THE QUICK BROWN FOX JUMPS OVER THE LAZY DOG.", y - 62, 32, 44)
        y = self.wrapped("the quick brown fox jumps over the lazy dog.", y - 10, 32, 44)
        minimum = self.source["minimum_display_px"] * 0.75
        self.heading(
            f"AT THE {self.source['minimum_display_px']} PX DISPLAY MINIMUM ({minimum:g} PT)",
            177,
        )
        self.text("Hello! 0123456789", M, 138, minimum)
        self.text("@ & € £ $ %", M, 91, minimum)
        self.label(
            "Reference size only. Screen rendering and print scaling can differ.",
            M,
            59,
            8,
        )
        self.end()

        self.start("Numerals, symbols & spacing")
        self.heading("NUMERALS", 675)
        self.text("0123456789", M, 620, 50)
        self.heading("PUNCTUATION & COMPLEX SIGNS", 574)
        self.wrapped("@ & € $ £ %  ¹²³  ¼ ½ ¾", 530, 36, 45)
        self.wrapped("! ? . , : ;  ( ) [ ] { }  / \\", 475, 36, 45)
        self.heading("KERNING ON", 372)
        self.label("KERNING OFF", 312, 372, 9, RUST, True)
        self.deltas = []
        for i, text in enumerate(
            ["AV VA AW WA", "To Ta Te Ty", "CD DE LT LY", "ra re ry we"]
        ):
            y = 328 - i * 72
            on = self.text(text, M, y, 30)
            off = self.text(text, 312, y, 30, False)
            self.label(f"Advance difference: {on - off:+.2f} pt", M, y - 22, 8)
            self.deltas.append({"text": text, "on_minus_off_pt": on - off})
        self.label(
            "Unadjusted pairs can have identical widths. The outlines are the same.",
            M,
            60,
            8,
        )
        self.end()

        self.start("Punctuation & character details")
        self.heading("PUNCTUATION ON BOTH SIDES", 675)
        self.label(
            "Period, comma, forward slash and backslash. Kerning on, 36 pt.", M, 655, 9
        )
        for i, char in enumerate("rwye"):
            text = f".{char} {char}.   ,{char} {char},   /{char} {char}/   \\{char} {char}\\"
            self.text(text, M, 603 - i * 70, 36)
        self.heading("UNENCODED HELPER GLYPHS", 305)
        self.label(
            "Actual font outlines. These glyphs have no Unicode codepoint.", M, 285, 9
        )
        if not self.helpers:
            self.label("This font has no unencoded helper glyphs.", M, 224, 10)
        for i, glyph in enumerate(self.helpers):
            x = M + (i % 2) * 265
            y = 224 - (i // 2) * 60
            bounds = self.bound(glyph)
            if bounds:
                self.glyph(glyph, x - bounds[0] * 36 / self.upem, y, 36)
            self.label(glyph, x + 65, y + 8, 8)
        self.label("The generic missing-character box (.notdef) is excluded.", M, 95, 8)
        self.label(
            "The following pages show every mapped character beyond A-Z and a-z.",
            M,
            76,
            8,
        )
        self.end()

        for offset in range(0, len(self.inventory), 63):
            chunk = self.inventory[offset : offset + 63]
            self.start(
                f"Complete inventory {offset // 63 + 1} of {math.ceil(len(self.inventory) / 63)}"
            )
            self.label(
                f"{offset + 1}-{offset + len(chunk)} of {len(self.inventory)} non-basic-letter mappings. Outlines at 36 pt.",
                M,
                688,
                8,
            )
            cw, ch, top = WIDTH / 7, 66, 673
            for i, cp in enumerate(chunk):
                x, y = M + (i % 7) * cw, top - (i // 7 + 1) * ch
                self.pdf.setStrokeColor(RULE)
                self.pdf.setLineWidth(0.4)
                self.pdf.rect(x, y, cw, ch, fill=0, stroke=1)
                glyph = self.cmap[cp]
                box = self.bound(glyph)
                if box:
                    scale = 36 / self.upem
                    gx = x + cw / 2 - (box[0] + box[2]) * scale / 2
                    gy = y + 15 + (ch - 18) / 2 - (box[1] + box[3]) * scale / 2
                    self.glyph(
                        glyph, gx, gy, 36, [x + 3, y + 14, x + cw - 3, y + ch - 2]
                    )
                else:
                    word = {32: "SPACE", 160: "NBSP", 173: "SOFT HYPHEN"}.get(
                        cp, "BLANK"
                    )
                    self.label(word, x + 5, y + 32, 6)
                self.label(f"U+{cp:04X}", x + cw / 2 - 15, y + 5, 7)
            self.label(
                "Combining marks are isolated. Spaces are blank; soft hyphens show their mapped outline.",
                M,
                55,
                7,
            )
            self.end()
        assert self.page == self.total
        self.pdf.save()
        assert len(PdfReader(self.output).pages) == self.total
        return {
            "family": self.name,
            "version": self.source["version"],
            "pdf": self.output.name,
            "pdf_sha256": sha256(self.output),
            "ttf": self.source["ttf"],
            "ttf_sha256": sha256(self.path),
            "pages": self.total,
            "mapped_characters": len(self.cmap),
            "special_codepoints": [f"U+{cp:04X}" for cp in self.inventory],
            "helpers": self.helpers,
            "sections": self.sections,
            "shaped_samples": self.records,
            "kerning_deltas": self.deltas,
            "validated_glyph_bounds": len(self.boxes),
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fonts", type=Path, required=True)
    parser.add_argument(
        "--manifest", type=Path, default=Path("docs/font-specimens/sources.json")
    )
    parser.add_argument("--output", type=Path, default=Path("docs/font-specimens"))
    parser.add_argument("--label-font", type=Path, required=True)
    parser.add_argument("--label-bold-font", type=Path, required=True)
    parser.add_argument("--qa", type=Path, default=Path("test-runs/specimens/qa.json"))
    args = parser.parse_args()
    pdfmetrics.registerFont(PDFTTFont("Label", str(args.label_font)))
    pdfmetrics.registerFont(PDFTTFont("LabelBold", str(args.label_bold_font)))
    args.output.mkdir(parents=True, exist_ok=True)
    args.qa.parent.mkdir(parents=True, exist_ok=True)
    source = json.loads(args.manifest.read_text())
    records = []
    for family in source["families"]:
        record = Specimen(family, args.fonts / family["ttf"], args.output).build()
        records.append(record)
        print(
            f"{record['pdf']}: {record['pages']} pages, {record['mapped_characters']} mappings"
        )
    result = {
        "method": "HarfBuzz shaping, exact TTF outlines as vector PDF paths; no font fallback.",
        "families": records,
        "layout_violations": [],
    }
    args.qa.write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
