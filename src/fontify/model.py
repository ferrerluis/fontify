"""Small, strict project format. No guessing coverage or fitting letterforms."""

import json
import math
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path


class FontifyError(ValueError):
    """An actionable project, vector, approval, or build error."""


def number(value, label, low=-32768, high=32767, integer=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise FontifyError(f"{label}: expected a number")
    if not math.isfinite(value) or not low <= value <= high:
        raise FontifyError(f"{label}: must be finite and between {low} and {high}")
    if integer and int(value) != value:
        raise FontifyError(f"{label}: expected an integer")
    return int(value) if integer else value


def keys(obj, allowed, label):
    if not isinstance(obj, dict):
        raise FontifyError(f"{label}: expected an object")
    extra = set(obj) - set(allowed.split())
    if extra:
        raise FontifyError(f"{label}: unknown fields {sorted(extra)}")


def local_path(root, value):
    if not isinstance(value, str) or not value:
        raise FontifyError("source/approval path must be a nonempty relative path")
    p = (root / value).resolve()
    if Path(value).is_absolute() or not p.is_relative_to(root):
        raise FontifyError(f"path must stay inside the project: {value}")
    return p


def codepoint(value):
    if not isinstance(value, str) or not re.fullmatch(r"U\+[0-9A-Fa-f]{4,6}", value):
        raise FontifyError(f"invalid Unicode scalar: {value!r}; use U+0041")
    cp = int(value[2:], 16)
    if cp > 0x10FFFF or 0xD800 <= cp <= 0xDFFF:
        raise FontifyError(f"invalid Unicode scalar: {value}")
    return cp


@dataclass(frozen=True)
class Project:
    path: Path
    data: dict

    @property
    def root(self):
        return self.path.parent

    @property
    def glyphs(self):
        return self.data["glyphs"]

    @property
    def stem(self):
        return f"{self.data['family'].replace(' ', '')}-{self.data['style']}-v{self.data['version']}"


def load_project(path):
    path = Path(path).resolve()
    try:
        d = json.loads(path.read_text())
    except (OSError, ValueError) as e:
        raise FontifyError(f"cannot read project: {e}") from e
    keys(
        d,
        "schema family style version copyright license units_per_em ascender descender line_gap cap_height x_height svg_baseline curve_error required_characters glyphs kerning samples approval quality coverage",
        "project",
    )
    if d.get("schema") != 1:
        raise FontifyError("schema must be 1")
    for field in ("family", "style"):
        if not isinstance(d.get(field), str) or not re.fullmatch(
            r"[A-Za-z][A-Za-z0-9 ]{0,49}", d[field]
        ):
            raise FontifyError(
                f"{field}: use 1-50 ASCII letters, digits, spaces; start with a letter"
            )
    if d["style"] != "Regular":
        raise FontifyError("this foundation builds upright Regular metadata only")
    for field in ("copyright", "license"):
        if field in d and not isinstance(d[field], str):
            raise FontifyError(f"{field}: expected a string")
    if not isinstance(d.get("version"), str) or not re.fullmatch(
        r"[0-9]{1,2}\.[0-9]{3}", d["version"]
    ):
        raise FontifyError("version must be a string such as 1.000")
    for field, default, lo, hi in [
        ("units_per_em", 1000, 16, 16384),
        ("ascender", 800, 1, 32767),
        ("descender", -200, -32768, -1),
        ("line_gap", 0, 0, 32767),
        ("cap_height", 700, 1, 32767),
        ("x_height", 500, 1, 32767),
        ("svg_baseline", 800, -32768, 32767),
    ]:
        d[field] = number(d.get(field, default), field, lo, hi, integer=True)
    d["curve_error"] = number(d.get("curve_error", 0.25), "curve_error", 0.01, 2)
    if not d["x_height"] <= d["cap_height"] <= d["ascender"]:
        raise FontifyError("require x_height <= cap_height <= ascender")
    required = d.get("required_characters")
    if (
        not isinstance(required, str)
        or not required
        or len(set(required)) != len(required)
    ):
        raise FontifyError(
            "required_characters must explicitly list unique required characters"
        )
    if not isinstance(d.get("glyphs"), list) or not d["glyphs"]:
        raise FontifyError("glyphs must be a nonempty list")
    names, cps = set(), set()
    for g in d["glyphs"]:
        keys(g, "name unicode source advance transform", "glyph")
        n = g.get("name")
        if (
            not isinstance(n, str)
            or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.]{0,62}", n)
            or n in (".notdef", "NULL")
        ):
            raise FontifyError(f"invalid glyph name: {n!r}")
        cp = codepoint(g.get("unicode"))
        if n in names or cp in cps:
            raise FontifyError(f"duplicate glyph name or Unicode mapping: {n}")
        names.add(n)
        cps.add(cp)
        number(g.get("advance"), f"{n}.advance", 1, 32767, integer=True)
        if cp in (32, 0xA0, 0x202F):
            if g.get("source") is not None:
                raise FontifyError("space must be blank: source must be null")
        else:
            if cp < 32 or 0x7F <= cp < 0xA0:
                raise FontifyError("control characters are not drawing glyphs")
            local_path(path.parent, g.get("source"))
        t = g.get("transform", [1, 0, 0, 1, 0, 0])
        if not isinstance(t, list) or len(t) != 6:
            raise FontifyError(f"{n}.transform must be six affine numbers")
        for v in t:
            number(v, f"{n}.transform")
        if abs(t[0] * t[3] - t[1] * t[2]) < 1e-10:
            raise FontifyError(f"{n}.transform is singular")
    missing = set(map(ord, required)) - cps
    if missing:
        raise FontifyError(
            f"missing required coverage: {', '.join(f'U+{cp:04X}' for cp in sorted(missing))}"
        )
    if 32 not in cps:
        raise FontifyError("include an explicitly mapped, blank U+0020 space")
    pairs = set()
    for k in d.get("kerning", []):
        keys(k, "left right value", "kerning")
        if k.get("left") not in names or k.get("right") not in names:
            raise FontifyError("kerning references an unknown glyph name")
        pair = (k["left"], k["right"])
        if pair in pairs:
            raise FontifyError(f"duplicate kerning pair: {pair}")
        pairs.add(pair)
        number(k.get("value"), "kerning value", -32768, 32767, integer=True)
    samples = d.get("samples", [required])
    if (
        not isinstance(samples, list)
        or not samples
        or not all(isinstance(s, str) and s for s in samples)
    ):
        raise FontifyError("samples must be a nonempty list of nonempty strings")
    for s in samples:
        if (
            set(map(ord, s)) - cps
            and set(map(ord, unicodedata.normalize("NFC", s))) - cps
        ):
            raise FontifyError(f"proof sample contains unmapped characters: {s!r}")
    d["samples"] = samples
    if d.get("approval") is not None:
        local_path(path.parent, d["approval"])
    if d.get("quality") is not None:
        local_path(path.parent, d["quality"])
    project = Project(path, d)
    if d.get("coverage") is not None:
        from .coverage import require_project_coverage, specimens

        require_project_coverage(project)
        d["samples"] = list(dict.fromkeys([*samples, *specimens(d["coverage"])]))
    return project
