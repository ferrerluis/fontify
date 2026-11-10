#!/usr/bin/env python3
"""Render the skill's exact character/language tables from the runtime inventory."""

import argparse
from html import escape
from pathlib import Path

from fontify.coverage import CATALOG, DEFAULT_LANGUAGES, character_record, repertoire

ROOT = Path(__file__).resolve().parents[1]
START = "<!-- BEGIN GENERATED INVENTORY -->"
END = "<!-- END GENERATED INVENTORY -->"


def display(char):
    if char.isspace():
        return f"␣ (blank {character_record(char)['unicode']})"
    return escape(char).replace("|", "&#124;")


def inventory_markdown():
    baseline = set(repertoire())
    all_chars = set(baseline)
    for data in CATALOG["languages"].values():
        all_chars.update(data["letters"] + data["punctuation"])
    rows = [
        START,
        "",
        "### Language profiles",
        "",
        "All profiles retain the US keyboard and five-language baseline. The letters below are the exact per-language letter inventory, including both cases; they are not Unicode block ranges. Punctuation adds to the shared prose set.",
        "",
        "| Code / language | Selection | Letters | Additional punctuation | Research and scope |",
        "|---|---|---|---|---|",
    ]
    for lang, item in CATALOG["languages"].items():
        status = "Mandatory" if lang in DEFAULT_LANGUAGES else "On request"
        letters = "".join(display(c) for c in item["letters"])
        punctuation = "".join(display(c) for c in item["punctuation"]) or "—"
        rows.append(
            f"| {lang} / {item['name']} | {status} | {letters} | {punctuation} | [CLDR 48]({item['source']}). {item['note']} |"
        )
    rows.extend(
        [
            "",
            "### Every encoded character",
            "",
            "“Default” means mandatory for every new Fontify font. “On request” rows enter generation and validation only when their language profile is selected. Language codes refer to the table above. Keyboard digits/symbols and shared prose punctuation/spacing map to every profile as a product requirement, not an assertion that they belong to each normative alphabet.",
            "",
            "| Character | Unicode | Description (Unicode name) | Languages using this profile mapping | Generation/check scope |",
            "|---|---|---|---|---|",
        ]
    )
    for char in sorted(all_chars):
        record = character_record(char)
        languages = ", ".join(record["languages"])
        if record["shared_keyboard_or_prose"]:
            languages = "All profiles (keyboard/prose)"
        rows.append(
            f"| {display(char)} | {record['unicode']} | {record['description']} | {languages} | {'Default' if char in baseline else 'On request'} |"
        )
    rows.extend(["", END])
    return "\n".join(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    path = ROOT / "references/character-coverage.md"
    text = path.read_text()
    before, rest = text.split(START, 1)
    _, after = rest.split(END, 1)
    expected = before + inventory_markdown() + after
    if args.check:
        if text != expected:
            raise SystemExit(
                "Character inventory is stale; run scripts/render_character_inventory.py"
            )
        print("Character inventory matches the generation and validation catalog.")
    else:
        path.write_text(expected)


if __name__ == "__main__":
    main()
