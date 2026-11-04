#!/usr/bin/env python3
"""Author the original Offline Sans demo using explicit centerline designs.

This is creative source construction, separate from Fontify's compiler. Stroke
expansion/union are intentional *here*, before any glyph is approved. Running
this script never modifies an approval baseline or invokes a provider.
"""

import json
import string
from pathlib import Path

import pathops
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.svgLib.path import parse_path

DESIGNS = {
    "A": "M80 780 L300 120 L520 780 M155 560 H445",
    "B": "M100 780 V140 H310 C540 140 540 450 310 450 H100 M310 450 C570 450 570 780 310 780 H100",
    "C": "M510 220 C410 75 100 80 100 460 C100 840 410 845 510 700",
    "D": "M100 780 V140 H260 C610 140 610 780 260 780 Z",
    "E": "M510 140 H100 V780 H510 M100 450 H440",
    "F": "M510 140 H100 V780 M100 450 H440",
    "G": "M510 220 C410 75 100 80 100 460 C100 840 500 845 510 630 V490 H330",
    "H": "M100 140 V780 M510 140 V780 M100 450 H510",
    "I": "M110 140 H490 M300 140 V780 M110 780 H490",
    "J": "M170 140 H500 V620 C500 850 100 850 100 620",
    "K": "M100 140 V780 M510 140 L100 510 M260 365 L530 780",
    "L": "M100 140 V780 H510",
    "M": "M80 780 V140 L300 490 L520 140 V780",
    "N": "M100 780 V140 L510 780 V140",
    "O": "M300 120 C570 120 570 800 300 800 C30 800 30 120 300 120 Z",
    "P": "M100 780 V140 H300 C580 140 580 470 300 470 H100",
    "Q": "M300 120 C570 120 570 800 300 800 C30 800 30 120 300 120 Z M350 620 L540 820",
    "R": "M100 780 V140 H300 C580 140 580 470 300 470 H100 M300 470 L540 780",
    "S": "M500 215 C390 40 100 105 100 310 C100 520 510 390 510 620 C510 850 180 860 90 695",
    "T": "M50 140 H550 M300 140 V780",
    "U": "M100 140 V580 C100 870 510 870 510 580 V140",
    "V": "M60 140 L300 780 L540 140",
    "W": "M40 140 L150 780 L300 410 L450 780 L560 140",
    "X": "M80 140 L520 780 M520 140 L80 780",
    "Y": "M60 140 L300 460 L540 140 M300 460 V780",
    "Z": "M70 140 H530 L70 780 H530",
}


def make_demo(root):
    root = Path(root)
    (root / "glyphs").mkdir(parents=True, exist_ok=True)
    glyphs = [{"name": "space", "unicode": "U+0020", "source": None, "advance": 300}]
    for char in string.ascii_uppercase:
        p = pathops.Path()
        parse_path(DESIGNS[char], p.getPen())
        # Rounded joins avoid miter spikes at A/M/N/V/W vertices. Square caps
        # give vertical stems the same planned baseline as horizontal strokes.
        p.stroke(80, pathops.LineCap.SQUARE_CAP, pathops.LineJoin.ROUND_JOIN, 4)
        p.convertConicsToQuads(0.1)
        p = pathops.simplify(p)
        pen = SVGPathPen(None)
        p.draw(pen)
        svg = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 660 1000"><path d="{pen.getCommands()}"/></svg>\n'
        (root / "glyphs" / (char + ".svg")).write_text(svg)
        glyphs.append(
            {
                "name": char,
                "unicode": f"U+{ord(char):04X}",
                "source": f"glyphs/{char}.svg",
                "advance": 660,
            }
        )
    project = {
        "schema": 1,
        "family": "Offline Sans",
        "style": "Regular",
        "version": "1.001",
        "copyright": "Copyright 2026 Fontify contributors",
        "license": "MIT; original Fontify demonstration artwork.",
        "units_per_em": 1000,
        "ascender": 900,
        "descender": -200,
        "line_gap": 0,
        "cap_height": 720,
        "x_height": 500,
        "svg_baseline": 820,
        "curve_error": 0.25,
        "required_characters": "ABCDEFGHIJKLMNOPQRSTUVWXYZ ",
        "glyphs": glyphs,
        "kerning": [
            {"left": a, "right": b, "value": v}
            for a, b, v in [
                ("A", "V", -70),
                ("V", "A", -65),
                ("T", "A", -55),
                ("T", "O", -45),
                ("W", "A", -45),
                ("Y", "O", -55),
            ]
        ],
        "samples": [
            "AVATAR",
            "CREATOR OPTIMIST",
            "THE QUICK BROWN FOX JUMPS OVER THE LAZY DOG",
            "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
        ],
        "approval": "approved.json",
    }
    (root / "fontify.json").write_text(json.dumps(project, indent=2) + "\n")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--out",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "examples/offline",
    )
    make_demo(parser.parse_args().out)
