"""Bounded, researched language coverage shared by planning, proofs and checks."""

import json
import string
import unicodedata as ud
from functools import lru_cache
from importlib.resources import files

from fontTools.pens.boundsPen import BoundsPen
from fontTools.ttLib import TTFont

from .model import FontifyError, codepoint, keys

CATALOG = json.loads(files("fontify").joinpath("data/languages.json").read_text())
DEFAULT_LANGUAGES = tuple(CATALOG["default_languages"])
PROFILE = CATALOG["profile"]
BLANKS = frozenset(CATALOG["spaces"])


def configuration(languages=(), additional_characters="", request_note=""):
    if not isinstance(languages, (list, tuple)) or not all(
        isinstance(x, str) for x in languages
    ):
        raise FontifyError(
            "coverage.languages must be a list of catalog language codes"
        )
    unknown = set(languages) - CATALOG["languages"].keys()
    if unknown:
        raise FontifyError(
            f"unknown coverage languages: {sorted(unknown)}; research an explicit character extension"
        )
    selected = list(dict.fromkeys((*DEFAULT_LANGUAGES, *languages)))
    if not isinstance(additional_characters, str) or not isinstance(request_note, str):
        raise FontifyError(
            "coverage additional_characters and request_note must be strings"
        )
    additional = "".join(sorted(set(ud.normalize("NFC", additional_characters))))
    if any(ud.category(c)[0] in "CMZ" and c not in BLANKS for c in additional):
        raise FontifyError(
            "additional characters must be printable NFC scalars; uncomposable marks need a separately implemented shaping extension"
        )
    if (
        set(selected) - set(DEFAULT_LANGUAGES) or additional
    ) and not request_note.strip():
        raise FontifyError("on-request coverage needs a concrete request_note")
    return dict(
        profile=PROFILE,
        languages=selected,
        additional_characters=additional,
        request_note=request_note,
    )


def read_configuration(config):
    keys(config, "profile languages additional_characters request_note", "coverage")
    if config.get("profile") != PROFILE:
        raise FontifyError(f"coverage.profile must be {PROFILE}")
    return configuration(
        config.get("languages", []),
        config.get("additional_characters", ""),
        config.get("request_note", ""),
    )


def repertoire(config=None):
    config = read_configuration(config) if config is not None else configuration()
    chars = set(
        string.ascii_letters
        + string.digits
        + CATALOG["keyboard_specials"]
        + CATALOG["common_punctuation"]
        + CATALOG["spaces"]
    )
    for lang in config["languages"]:
        item = CATALOG["languages"][lang]
        chars.update(item["letters"] + item["punctuation"])
    chars.update(config["additional_characters"])
    return "".join(sorted(chars))


def character_record(char):
    languages = [
        lang
        for lang, item in CATALOG["languages"].items()
        if char in item["letters"] + item["punctuation"]
    ]
    shared = (
        char
        in CATALOG["keyboard_specials"]
        + CATALOG["common_punctuation"]
        + CATALOG["spaces"]
        + string.digits
    )
    if shared:
        languages = list(CATALOG["languages"])
    return {
        "character": char,
        "unicode": f"U+{ord(char):04X}",
        "description": ud.name(char),
        "languages": languages,
        "shared_keyboard_or_prose": shared,
    }


def uppercase(text, lang):
    if lang == "tr":
        text = text.replace("i", "İ").replace("ı", "I")
    return text.replace("ß", "ẞ").upper()


def specimens(config=None):
    config = read_configuration(config) if config is not None else configuration()
    result = [
        CATALOG["keyboard_specials"],
        "0123456789",
        "«\u00a0Bonjour\u202f!\u00a0» “Hello”—‘Olá’… 1.º 1.ª",
    ]
    for lang in config["languages"]:
        item = CATALOG["languages"][lang]
        text = item["sample"]
        panel = "".join(c for c in item["letters"] if ord(c) > 127)
        result.extend((text, uppercase(text, lang)))
        if panel:
            result.append(panel)
        # Keep original decomposed text; the shaper, not this function, composes it.
        result.extend(
            ud.normalize("NFD", s)
            for s in (text, uppercase(text, lang), panel)
            if s and ud.normalize("NFD", s) != s
        )
    if config["additional_characters"]:
        result.append(config["additional_characters"])
    return list(dict.fromkeys(result))


def coverage_plan(languages=(), additional_characters="", request_note=""):
    config = configuration(languages, additional_characters, request_note)
    chars = repertoire(config)
    return {
        "coverage": config,
        "required_characters": chars,
        "samples": specimens(config),
        "character_count": len(chars),
        "characters": [character_record(c) for c in chars],
        "status": "artwork_required; plan_is_not_generated_glyphs",
    }


def require_project_coverage(project):
    """Opt-in project contract; historical unprofiled projects stay reproducible."""
    if project.data.get("coverage") is None:
        return
    config = read_configuration(project.data["coverage"])
    required = set(repertoire(config))
    mapped = {chr(codepoint(g["unicode"])) for g in project.glyphs}
    missing = required - mapped
    undeclared = required - set(project.data["required_characters"])
    if missing or undeclared:
        detail = ", ".join(f"U+{ord(c):04X}" for c in sorted(missing | undeclared))
        raise FontifyError(
            f"language baseline missing from mappings or required_characters: {detail}"
        )


def check_font_coverage(path, config=None):
    """Reopen the actual font; compare raw NFC/NFD shaping and real ink/spacing."""
    from .review import shape_font

    chars = repertoire(config)
    with TTFont(path) as font:
        cmap = font.getBestCmap()
        gs = font.getGlyphSet()
        missing = [c for c in chars if ord(c) not in cmap or cmap[ord(c)] == ".notdef"]
        if missing:
            raise FontifyError(
                "compiled language coverage missing: "
                + ", ".join(f"U+{ord(c):04X}" for c in missing)
            )
        for char in chars:
            name = cmap[ord(char)]
            pen = BoundsPen(gs)
            gs[name].draw(pen)
            if char in BLANKS:
                if pen.bounds is not None or font["hmtx"][name][0] <= 0:
                    raise FontifyError(
                        f"U+{ord(char):04X}: spacing character must be blank with positive advance"
                    )
            elif pen.bounds is None:
                raise FontifyError(f"U+{ord(char):04X}: encoded glyph has no ink")
        if font["hmtx"][cmap[0xA0]][0] != font["hmtx"][cmap[32]][0]:
            raise FontifyError("NBSP must have the same advance as space")
        if font["hmtx"][cmap[0x202F]][0] > font["hmtx"][cmap[32]][0]:
            raise FontifyError("narrow NBSP must be no wider than space")

    def signature(shaped):
        if any(g["gid"] == 0 for g in shaped["glyphs"]):
            raise FontifyError("language specimen shapes to .notdef")
        return [
            {k: v for k, v in g.items() if k != "cluster"} for g in shaped["glyphs"]
        ]

    @lru_cache(maxsize=None)
    def shaped(text, kern):
        return signature(shape_font(path, text, kern))

    comparisons = 0
    for text in [*chars, *specimens(config)]:
        nfc, nfd = ud.normalize("NFC", text), ud.normalize("NFD", text)
        for kern in (True, False):
            if shaped(nfc, kern) != shaped(nfd, kern):
                raise FontifyError(
                    f"NFC/NFD shaping or accent placement differs: {text!r}"
                )
        comparisons += 1
    return {
        "status": "passed",
        "character_count": len(chars),
        "nfc_nfd_checks": comparisons,
        "kerning": ["on", "off"],
        "visual_accent_review": "required; numeric equivalence is not optical approval",
    }


def coverage_check(project, font_path=None, webfont_path=None):
    config = (
        read_configuration(project.data["coverage"])
        if project.data.get("coverage") is not None
        else configuration()
    )
    required = set(repertoire(config))
    mapped = {chr(codepoint(g["unicode"])) for g in project.glyphs}
    missing = required - mapped
    undeclared = required - set(project.data["required_characters"])
    result = {
        "status": "blocked" if missing or undeclared else "passed",
        "coverage": config,
        "character_count": len(required),
        "profile_attached": project.data.get("coverage") is not None,
        "missing_mappings": [character_record(c) for c in sorted(missing)],
        "missing_required_characters": [
            character_record(c) for c in sorted(undeclared)
        ],
        "compiled": {},
    }
    if (font_path is None) != (webfont_path is None):
        raise FontifyError(
            "coverage-check needs both --font and --webfont, or neither for a source-only check"
        )
    for label, path in (("ttf", font_path), ("woff2", webfont_path)):
        if path is not None:
            result["compiled"][label] = check_font_coverage(path, config)
    result["compiled_status"] = "passed" if font_path is not None else "not_run"
    return result
