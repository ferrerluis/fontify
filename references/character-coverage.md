# Mandatory character and language coverage

Read this before planning artwork, constructing a new font, or reviewing coverage.
The supported default is **English, Spanish, French, Italian and Portuguese**.
It is a bounded modern orthographic/prose repertoire, never “all Latin”.
Other Latin alphabets, historical forms and auxiliary foreign-name inventories
are generated and checked only for an explicit user request.

## Exact default

The `en-es-fr-it-pt-v1` profile requires **160 encoded Unicode scalars**:

- All 95 printable ASCII characters U+0020–U+007E: A–Z, a–z, 0–9, blank space,
  and exactly these **32 US QWERTY special characters**, in codepoint order:

  ~~~text
  ! " # $ % & ' ( ) * + , - . / : ; < = > ? @ [ \ ] ^ _ ` { | } ~
  ~~~

- **50 non-ASCII letters**, individually listed with their language mappings in
  the generated tables below. Each accented lowercase letter and its uppercase
  counterpart is encoded; uppercase accents cannot be dropped. French æ/Æ and
  œ/Œ are alphabetic characters, not optional `ae`/`oe` substitutions.
- **13 prose/ordinal characters**: ¡ U+00A1, ¿ U+00BF, « U+00AB, » U+00BB,
  ‘ U+2018, ’ U+2019, “ U+201C, ” U+201D, … U+2026, – U+2013, — U+2014,
  ª U+00AA and º U+00BA. Ordinal indicators are not the degree sign ° U+00B0.
- **Two additional blank characters**: NO-BREAK SPACE U+00A0 (same advance as
  U+0020) and NARROW NO-BREAK SPACE U+202F (positive advance no wider than U+0020).
  These support French punctuation spacing. Line breaking is the application's
  job; the font provides correctly encoded blank glyphs and advances.

“Visible on a keyboard” means printable output of an ordinary US layout,
including shifted symbols. Tab, Enter, Shift, arrows, function keys and keycap
legends are controls, not additional drawing glyphs. No Alt/Option extensions,
all-Latin block expansion, currency catalog, IPA or general mathematical set is implied.

## Generation and checking contract

1. Run `fontify coverage-plan --output coverage-plan.json` before generating
   artwork. Copy its `coverage` object and `required_characters` into the new
   manifest; include its `samples`. This is a design target, not generated artwork.
   Make actual source glyphs for every mapping; do not alias uppercase to
   lowercase or use a generic placeholder. Sources may deliberately share an
   accent design, but each encoded letter must have correct composed outlines.
2. New work **must** attach the coverage profile. A caller cannot shrink its
   mandatory repertoire by editing `required_characters` or the language list.
   The project loader enforces the profile; builds and preflight reopen both TTF
   and WOFF2 and verify the actual encoded/ink coverage and normalization shaping.
   Frozen historical examples without `coverage` keep their original subset and
   receipt bindings. That compatibility path does not qualify a newly generated
   font for this skill's five-language promise. Do not silently migrate old
   approved sources, or claim their A–Z examples meet the new baseline.
3. Use `fontify coverage-check project/fontify.json` for source coverage; this
   checks the default even on an unprofiled legacy project and reports missing
   codepoints. Then pass both `--font path.ttf --webfont path.woff2` for exported
   checks. A source-only pass reports compiled checks as **not_run**. Inspect
   both formats' cmaps, non-.notdef mappings, nonempty ink, blank spacing and real
   HarfBuzz output. Save the result with the preflight evidence.
4. Keep required characters as unique **NFC** scalars; don't replace é with two
   mapping entries e + combining acute. Proofs include untouched **NFD** text
   such as `e` + U+0301, `n` + U+0303 and `c` + U+0327. HarfBuzz must canonically
   compose these to the encoded precomposed glyphs; tests compare glyph IDs and
   advances/offsets in NFC and NFD with kerning on and off. Input is never
   normalized away before the HarfBuzz check. The engine may consume a combining
   mark via canonical composition without that mark having its own cmap entry.
   This profile does not claim support for arbitrary isolated, stacked or
   uncomposable combining marks. Do not use NFKC/NFKD to define coverage: they fold ordinal indicators into
   ordinary letters. Alphabetic æ/œ remain distinct from ae/oe under canonical
   normalization and must retain their own mappings. Optional typographic `fi`/`fl` GSUB ligatures remain separate work.
5. Review every accented letter, ligature and punctuation glyph at enlarged and
   fixed text/display sizes in actual TTF and browser WOFF2 proofs, plus every
   language's meaningful words, uppercase and NFC/NFD specimens. Inspect detached
   accents, acute/grave direction, dots above i/j versus accent replacement,
   tilde/circumflex placement, cedilla clearance, spacing, clipping, collisions
   and optical weight. Look for distinct I/l/1, O/0, rn/m, base/accented pairs,
   guillemets versus angle brackets, and º versus requested °. Numeric NFC/NFD
   equivalence proves consistency, not good accent placement. Never mark the
   generated proofs as visually approved without inspecting them.

Profiled projects automatically retain the language specimens in proofs and
verify all required mappings after export. Missing coverage, blank ink or
NFC/NFD differences block compilation/release; the existing full quality and
visual receipt gates still apply. Generation must follow the chosen artwork
provider and its existing spend rules; this update itself makes no paid calls.

## On-request European catalog

The initial catalog contains **23 opt-in profiles**: Albanian, Basque, Catalan,
Croatian, Czech, Danish, Estonian, Finnish, German, Hungarian, Icelandic, Irish,
Latvian, Lithuanian, Maltese, Norwegian Bokmål, Polish, Romanian, Slovak,
Slovenian, Swedish, Turkish and Welsh. Selection is additive:

```sh
fontify coverage-plan --language de --language pl --request-note 'User requested German and Polish.' --output expanded-plan.json
```

Only selected languages enter its `coverage.languages`, extra targets and
specimens. The mere existence of a character in this reference never makes it
a default requirement. Unknown language codes fail rather than selecting all
European alphabets. Research another requested language and add a precise
profile, or use `--additional-characters 'Āā' --request-note 'User requested these Latvian name forms.'`
for an explicitly bounded extension. This option does not infer a whole alphabet.

Scope is modern Latin-script ordinary orthography using CLDR 48 main exemplars
with casing, meaningful samples and the small documented additions below.
CLDR is locale data, **not a normative alphabet**: its main set can include
usual loanwords (e.g. Finnish š/ž, Basque ç) and omit optional modern marks
(e.g. Turkish circumflex). Those distinctions are recorded, not hidden in an
“All Latin” union. Digraphs such as Czech ch, Croatian dž/lj/nj and Welsh ll
are tested as ordinary sequences, not invented single codepoints or mandatory
GSUB ligatures. Romanian uses comma-below ș/ț, not cedilla substitutes. German
explicitly includes ẞ rather than trusting full uppercase of ß, which yields SS;
Turkish keeps the I/ı and İ/i pairs in specimens.

This is an initial researched catalog, **not all European languages**. Dutch
(including its unprecomposable accented ij sequence), Nynorsk, Faroese, Scottish
Gaelic, Sámi varieties, Baltic dictionary stress notation, regional/minority
orthographies and Greek/Cyrillic scripts have not been implemented as profiles.
Research and validate them only when requested; uncomposable combining sequences
need real mark positioning support and tests before claiming coverage. Archaic
long s/þ/ð in English, Irish dotted historical consonants, Italian contracted
plural î and arbitrary foreign proper names do not expand a modern profile.
Characters already required by another selected language remain available.

## Research and maintenance

The runtime source is [`src/fontify/data/languages.json`](../src/fontify/data/languages.json).
It records per-language letters, punctuation, original CLDR exemplar excerpts,
specimens, source links and scope notes. The planner and verifier use that same
mapping. The tables below are rendered from it; regression tests require an
exact match. After an intentional catalog edit, run:

```sh
PYTHONPATH=src python scripts/render_character_inventory.py
PYTHONPATH=src python scripts/render_character_inventory.py --check
```

Sources consulted (2026-11-09):

- [Unicode CLDR exemplar definitions](https://unicode.org/reports/tr35/tr35-general.html#Exemplars)
  distinguish main, auxiliary, index and punctuation inventories. Pinned CLDR 48
  language files are linked in each row below; upgrades must be deliberate.
- [OQLF on æ and œ](https://vitrinelinguistique.oqlf.gouv.qc.ca/21611/lorthographe/problemes-lies-aux-voyelles/ecriture-et-prononciation-des-lettres-doubles-ae-et-oe)
  supports both cases in conventional French vocabulary and learned expressions.
- [FundéuRAE on uppercase accents](https://www.fundeu.es/recomendacion/mayusculas-si-se-tildan-435/)
  and [paired question/exclamation signs](https://www.fundeu.es/recomendacion/interrogacion-y-exclamacion-usos-de-los-signos-ortograficos/).
- [Academia Mexicana de la Lengua on ordinal indicators](https://academia.org.mx/consultas/consultas-frecuentes/item/numeros-ordinales).
- [Accademia della Crusca accent guide](https://accademiadellacrusca.it/it/consulenza/vademecum-sullaccento-quando-indicarlo-e-dove-pronunciarlo/34)
  includes stress disambiguation such as ancóra, beyond the minimum Italian
  main exemplars; ó/Ó is retained for that standard use.
- [Portuguese Orthographic Agreement 1990](https://www.portaldalinguaportuguesa.org/acordo.php?action=acordo&template=print&version=1990),
  especially Bases VIII–XIV: modern accents, grave à and removal of ordinary
  trema. Portugal/Brazil acute/circumflex variants are covered. CLDR's inherited
  ò is not treated as a modern Portuguese requirement.
- [OQLF nonbreaking space](https://vitrinelinguistique.oqlf.gouv.qc.ca/fiche-gdt/fiche/8360213/espace-insecable)
  supports punctuation spacing; narrow-space choice remains typographic practice.
- [Duden spelling rules citing §25 E3](https://www.duden.de/sprachwissen/rechtschreibregeln/doppel-s-und-scharfes-s)
  document uppercase ẞ alongside SS. [TDK spelling rules](https://tdk.gov.tr/icerik/yazim-kurallari/duzeltme-isareti/)
  specify retained circumflexes; Turkish adds â/î/û to the CLDR main set.
- [Unicode UAX #15](https://www.unicode.org/reports/tr15/)
  defines canonical versus compatibility normalization. Unicode names in the
  table come from Python's `unicodedata`, with codepoint/name agreement tested.

<!-- BEGIN GENERATED INVENTORY -->

### Language profiles

All profiles retain the US keyboard and five-language baseline. The letters below are the exact per-language letter inventory, including both cases; they are not Unicode block ranges. Punctuation adds to the shared prose set.

| Code / language | Selection | Letters | Additional punctuation | Research and scope |
|---|---|---|---|---|
| ca / Catalan | On request | ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyzÀÇÈÉÍÏÒÓÚÜàçèéíïòóúü | · | [CLDR 48](https://raw.githubusercontent.com/unicode-org/cldr/release-48/common/main/ca.xml). Modern CLDR main exemplars; auxiliary foreign and historical letters are excluded. |
| cs / Czech | On request | ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyzÁÉÍÓÚÝáéíóúýČčĎďĚěŇňŘřŠšŤťŮůŽž | „‚ | [CLDR 48](https://raw.githubusercontent.com/unicode-org/cldr/release-48/common/main/cs.xml). Modern CLDR main exemplars; auxiliary foreign and historical letters are excluded. |
| cy / Welsh | On request | ABCDEFGHIJLMNOPRSTUWYabcdefghijlmnoprstuwyÀÁÂÄÈÉÊËÌÍÎÏÒÓÔÖÙÚÛÜÝàáâäèéêëìíîïòóôöùúûüýÿŴŵŶŷŸẀẁẂẃẄẅỲỳ | — | [CLDR 48](https://raw.githubusercontent.com/unicode-org/cldr/release-48/common/main/cy.xml). Modern CLDR main exemplars; auxiliary foreign and historical letters are excluded. |
| da / Danish | On request | ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyzÅÆØåæø | — | [CLDR 48](https://raw.githubusercontent.com/unicode-org/cldr/release-48/common/main/da.xml). Modern CLDR main exemplars; auxiliary foreign and historical letters are excluded. |
| de / German | On request | ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyzÄÖÜßäöüẞ | „‚ | [CLDR 48](https://raw.githubusercontent.com/unicode-org/cldr/release-48/common/main/de.xml). Adds uppercase ẞ explicitly; Unicode full uppercase of ß is SS, which is not a substitute for the encoded capital. |
| en / English | Mandatory | ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz | — | [CLDR 48](https://raw.githubusercontent.com/unicode-org/cldr/release-48/common/main/en.xml). No extra obligatory letters. Accented loanwords already in the baseline remain covered; arbitrary foreign names are not a language-wide promise. |
| es / Spanish | Mandatory | ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyzÁÉÍÑÓÚÜáéíñóúü | ¡¿ªº | [CLDR 48](https://raw.githubusercontent.com/unicode-org/cldr/release-48/common/main/es.xml). Modern CLDR main exemplars; auxiliary foreign and historical letters are excluded. |
| et / Estonian | On request | ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyzÄÕÖÜäõöüŠšŽž | „‚ | [CLDR 48](https://raw.githubusercontent.com/unicode-org/cldr/release-48/common/main/et.xml). Modern CLDR main exemplars; auxiliary foreign and historical letters are excluded. |
| eu / Basque | On request | ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyzÇÑçñ | — | [CLDR 48](https://raw.githubusercontent.com/unicode-org/cldr/release-48/common/main/eu.xml). Modern CLDR main exemplars; auxiliary foreign and historical letters are excluded. |
| fi / Finnish | On request | ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyzÄÅÖäåöŠšŽž | — | [CLDR 48](https://raw.githubusercontent.com/unicode-org/cldr/release-48/common/main/fi.xml). Modern CLDR main exemplars; auxiliary foreign and historical letters are excluded. |
| fr / French | Mandatory | ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyzÀÂÆÇÈÉÊËÎÏÔÙÛÜàâæçèéêëîïôùûüÿŒœŸ | — | [CLDR 48](https://raw.githubusercontent.com/unicode-org/cldr/release-48/common/main/fr.xml). Includes rare ÿ/Ÿ and alphabetic æ/Æ, œ/Œ, including conventional learned vocabulary; no arbitrary foreign-name extension. |
| ga / Irish | On request | ABCDEFGHILMNOPRSTUabcdefghilmnoprstuÁÉÍÓÚáéíóú | — | [CLDR 48](https://raw.githubusercontent.com/unicode-org/cldr/release-48/common/main/ga.xml). Modern acute accents; historical dot-above consonants remain on request. |
| hr / Croatian | On request | ABCDEFGHIJKLMNOPRSTUVZabcdefghijklmnoprstuvzĆćČčĐđŠšŽž | — | [CLDR 48](https://raw.githubusercontent.com/unicode-org/cldr/release-48/common/main/hr.xml). Modern CLDR main exemplars; auxiliary foreign and historical letters are excluded. |
| hu / Hungarian | On request | ABCDEFGHIJKLMNOPRSTUVYZabcdefghijklmnoprstuvyzÁÉÍÓÖÚÜáéíóöúüŐőŰű | — | [CLDR 48](https://raw.githubusercontent.com/unicode-org/cldr/release-48/common/main/hu.xml). Modern CLDR main exemplars; auxiliary foreign and historical letters are excluded. |
| is / Icelandic | On request | ABDEFGHIJKLMNOPRSTUVXYabdefghijklmnoprstuvxyÁÆÉÍÐÓÖÚÝÞáæéíðóöúýþ | — | [CLDR 48](https://raw.githubusercontent.com/unicode-org/cldr/release-48/common/main/is.xml). Modern CLDR main exemplars; auxiliary foreign and historical letters are excluded. |
| it / Italian | Mandatory | ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyzÀÈÉÌÒÓÙàèéìòóù | — | [CLDR 48](https://raw.githubusercontent.com/unicode-org/cldr/release-48/common/main/it.xml). Adds ó/Ó for ordinary optional stress disambiguation (ancóra); acute í/ú are already covered by Spanish/Portuguese. Historical contracted plural î is not an Italian requirement. |
| lt / Lithuanian | On request | ABCDEFGHIJKLMNOPRSTUVYZabcdefghijklmnoprstuvyzĄąČčĖėĘęĮįŠšŪūŲųŽž | „‚ | [CLDR 48](https://raw.githubusercontent.com/unicode-org/cldr/release-48/common/main/lt.xml). Modern ordinary spelling; dictionary stress marks and special casing of additional accented text require a separate extension. |
| lv / Latvian | On request | ABCDEFGHIJKLMNOPRSTUVZabcdefghijklmnoprstuvzĀāČčĒēĢģĪīĶķĻļŅņŠšŪūŽž | „‚ | [CLDR 48](https://raw.githubusercontent.com/unicode-org/cldr/release-48/common/main/lv.xml). Modern CLDR main exemplars; auxiliary foreign and historical letters are excluded. |
| mt / Maltese | On request | ABDEFGHIJKLMNOPQRSTUVWXZabdefghijklmnopqrstuvwxzÀÈÌÒÙàèìòùĊċĠġĦħŻż | — | [CLDR 48](https://raw.githubusercontent.com/unicode-org/cldr/release-48/common/main/mt.xml). Modern CLDR main exemplars; auxiliary foreign and historical letters are excluded. |
| no / Norwegian (Bokmål) | On request | ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyzÀÅÆÉÒÓÔØàåæéòóôø | — | [CLDR 48](https://raw.githubusercontent.com/unicode-org/cldr/release-48/common/main/no.xml). Bokmål scope only; Nynorsk is not implicitly claimed. |
| pl / Polish | On request | ABCDEFGHIJKLMNOPRSTUWYZabcdefghijklmnoprstuwyzÓóĄąĆćĘęŁłŃńŚśŹźŻż | „‚ | [CLDR 48](https://raw.githubusercontent.com/unicode-org/cldr/release-48/common/main/pl.xml). Modern CLDR main exemplars; auxiliary foreign and historical letters are excluded. |
| pt / Portuguese | Mandatory | ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyzÀÁÂÃÇÉÊÍÓÔÕÚàáâãçéêíóôõú | ªº | [CLDR 48](https://raw.githubusercontent.com/unicode-org/cldr/release-48/common/main/pt.xml). Modern Portugal/Brazil orthography. The inherited CLDR ò is omitted as a Portuguese requirement: modern grave use is à; it remains covered for Italian. Historical trema is not a Portuguese requirement. |
| ro / Romanian | On request | ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyzÂÎâîĂăȘșȚț | „‚ | [CLDR 48](https://raw.githubusercontent.com/unicode-org/cldr/release-48/common/main/ro.xml). Comma-below ș/ț, not legacy cedilla substitutes ş/ţ. |
| sk / Slovak | On request | ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyzÁÄÉÍÓÔÚÝáäéíóôúýČčĎďĹĺĽľŇňŔŕŠšŤťŽž | „‚ | [CLDR 48](https://raw.githubusercontent.com/unicode-org/cldr/release-48/common/main/sk.xml). Modern CLDR main exemplars; auxiliary foreign and historical letters are excluded. |
| sl / Slovenian | On request | ABCDEFGHIJKLMNOPRSTUVZabcdefghijklmnoprstuvzČčŠšŽž | — | [CLDR 48](https://raw.githubusercontent.com/unicode-org/cldr/release-48/common/main/sl.xml). Modern CLDR main exemplars; auxiliary foreign and historical letters are excluded. |
| sq / Albanian | On request | ABCDEFGHIJKLMNOPQRSTUVXYZabcdefghijklmnopqrstuvxyzÇËçë | — | [CLDR 48](https://raw.githubusercontent.com/unicode-org/cldr/release-48/common/main/sq.xml). Modern CLDR main exemplars; auxiliary foreign and historical letters are excluded. |
| sv / Swedish | On request | ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyzÀÄÅÉÖàäåéö | — | [CLDR 48](https://raw.githubusercontent.com/unicode-org/cldr/release-48/common/main/sv.xml). Modern CLDR main exemplars; auxiliary foreign and historical letters are excluded. |
| tr / Turkish | On request | ABCDEFGHIJKLMNOPRSTUVYZabcdefghijklmnoprstuvyzÂÇÎÖÛÜâçîöûüĞğİıŞş | — | [CLDR 48](https://raw.githubusercontent.com/unicode-org/cldr/release-48/common/main/tr.xml). Explicit İ and ı; adds normative circumflex â, î, û. Locale casing must retain I/ı and İ/i. |

### Every encoded character

“Default” means mandatory for every new Fontify font. “On request” rows enter generation and validation only when their language profile is selected. Language codes refer to the table above. Keyboard digits/symbols and shared prose punctuation/spacing map to every profile as a product requirement, not an assertion that they belong to each normative alphabet.

| Character | Unicode | Description (Unicode name) | Languages using this profile mapping | Generation/check scope |
|---|---|---|---|---|
| ␣ (blank U+0020) | U+0020 | SPACE | All profiles (keyboard/prose) | Default |
| ! | U+0021 | EXCLAMATION MARK | All profiles (keyboard/prose) | Default |
| &quot; | U+0022 | QUOTATION MARK | All profiles (keyboard/prose) | Default |
| # | U+0023 | NUMBER SIGN | All profiles (keyboard/prose) | Default |
| $ | U+0024 | DOLLAR SIGN | All profiles (keyboard/prose) | Default |
| % | U+0025 | PERCENT SIGN | All profiles (keyboard/prose) | Default |
| &amp; | U+0026 | AMPERSAND | All profiles (keyboard/prose) | Default |
| &#x27; | U+0027 | APOSTROPHE | All profiles (keyboard/prose) | Default |
| ( | U+0028 | LEFT PARENTHESIS | All profiles (keyboard/prose) | Default |
| ) | U+0029 | RIGHT PARENTHESIS | All profiles (keyboard/prose) | Default |
| * | U+002A | ASTERISK | All profiles (keyboard/prose) | Default |
| + | U+002B | PLUS SIGN | All profiles (keyboard/prose) | Default |
| , | U+002C | COMMA | All profiles (keyboard/prose) | Default |
| - | U+002D | HYPHEN-MINUS | All profiles (keyboard/prose) | Default |
| . | U+002E | FULL STOP | All profiles (keyboard/prose) | Default |
| / | U+002F | SOLIDUS | All profiles (keyboard/prose) | Default |
| 0 | U+0030 | DIGIT ZERO | All profiles (keyboard/prose) | Default |
| 1 | U+0031 | DIGIT ONE | All profiles (keyboard/prose) | Default |
| 2 | U+0032 | DIGIT TWO | All profiles (keyboard/prose) | Default |
| 3 | U+0033 | DIGIT THREE | All profiles (keyboard/prose) | Default |
| 4 | U+0034 | DIGIT FOUR | All profiles (keyboard/prose) | Default |
| 5 | U+0035 | DIGIT FIVE | All profiles (keyboard/prose) | Default |
| 6 | U+0036 | DIGIT SIX | All profiles (keyboard/prose) | Default |
| 7 | U+0037 | DIGIT SEVEN | All profiles (keyboard/prose) | Default |
| 8 | U+0038 | DIGIT EIGHT | All profiles (keyboard/prose) | Default |
| 9 | U+0039 | DIGIT NINE | All profiles (keyboard/prose) | Default |
| : | U+003A | COLON | All profiles (keyboard/prose) | Default |
| ; | U+003B | SEMICOLON | All profiles (keyboard/prose) | Default |
| &lt; | U+003C | LESS-THAN SIGN | All profiles (keyboard/prose) | Default |
| = | U+003D | EQUALS SIGN | All profiles (keyboard/prose) | Default |
| &gt; | U+003E | GREATER-THAN SIGN | All profiles (keyboard/prose) | Default |
| ? | U+003F | QUESTION MARK | All profiles (keyboard/prose) | Default |
| @ | U+0040 | COMMERCIAL AT | All profiles (keyboard/prose) | Default |
| A | U+0041 | LATIN CAPITAL LETTER A | ca, cs, cy, da, de, en, es, et, eu, fi, fr, ga, hr, hu, is, it, lt, lv, mt, no, pl, pt, ro, sk, sl, sq, sv, tr | Default |
| B | U+0042 | LATIN CAPITAL LETTER B | ca, cs, cy, da, de, en, es, et, eu, fi, fr, ga, hr, hu, is, it, lt, lv, mt, no, pl, pt, ro, sk, sl, sq, sv, tr | Default |
| C | U+0043 | LATIN CAPITAL LETTER C | ca, cs, cy, da, de, en, es, et, eu, fi, fr, ga, hr, hu, it, lt, lv, no, pl, pt, ro, sk, sl, sq, sv, tr | Default |
| D | U+0044 | LATIN CAPITAL LETTER D | ca, cs, cy, da, de, en, es, et, eu, fi, fr, ga, hr, hu, is, it, lt, lv, mt, no, pl, pt, ro, sk, sl, sq, sv, tr | Default |
| E | U+0045 | LATIN CAPITAL LETTER E | ca, cs, cy, da, de, en, es, et, eu, fi, fr, ga, hr, hu, is, it, lt, lv, mt, no, pl, pt, ro, sk, sl, sq, sv, tr | Default |
| F | U+0046 | LATIN CAPITAL LETTER F | ca, cs, cy, da, de, en, es, et, eu, fi, fr, ga, hr, hu, is, it, lt, lv, mt, no, pl, pt, ro, sk, sl, sq, sv, tr | Default |
| G | U+0047 | LATIN CAPITAL LETTER G | ca, cs, cy, da, de, en, es, et, eu, fi, fr, ga, hr, hu, is, it, lt, lv, mt, no, pl, pt, ro, sk, sl, sq, sv, tr | Default |
| H | U+0048 | LATIN CAPITAL LETTER H | ca, cs, cy, da, de, en, es, et, eu, fi, fr, ga, hr, hu, is, it, lt, lv, mt, no, pl, pt, ro, sk, sl, sq, sv, tr | Default |
| I | U+0049 | LATIN CAPITAL LETTER I | ca, cs, cy, da, de, en, es, et, eu, fi, fr, ga, hr, hu, is, it, lt, lv, mt, no, pl, pt, ro, sk, sl, sq, sv, tr | Default |
| J | U+004A | LATIN CAPITAL LETTER J | ca, cs, cy, da, de, en, es, et, eu, fi, fr, hr, hu, is, it, lt, lv, mt, no, pl, pt, ro, sk, sl, sq, sv, tr | Default |
| K | U+004B | LATIN CAPITAL LETTER K | ca, cs, da, de, en, es, et, eu, fi, fr, hr, hu, is, it, lt, lv, mt, no, pl, pt, ro, sk, sl, sq, sv, tr | Default |
| L | U+004C | LATIN CAPITAL LETTER L | ca, cs, cy, da, de, en, es, et, eu, fi, fr, ga, hr, hu, is, it, lt, lv, mt, no, pl, pt, ro, sk, sl, sq, sv, tr | Default |
| M | U+004D | LATIN CAPITAL LETTER M | ca, cs, cy, da, de, en, es, et, eu, fi, fr, ga, hr, hu, is, it, lt, lv, mt, no, pl, pt, ro, sk, sl, sq, sv, tr | Default |
| N | U+004E | LATIN CAPITAL LETTER N | ca, cs, cy, da, de, en, es, et, eu, fi, fr, ga, hr, hu, is, it, lt, lv, mt, no, pl, pt, ro, sk, sl, sq, sv, tr | Default |
| O | U+004F | LATIN CAPITAL LETTER O | ca, cs, cy, da, de, en, es, et, eu, fi, fr, ga, hr, hu, is, it, lt, lv, mt, no, pl, pt, ro, sk, sl, sq, sv, tr | Default |
| P | U+0050 | LATIN CAPITAL LETTER P | ca, cs, cy, da, de, en, es, et, eu, fi, fr, ga, hr, hu, is, it, lt, lv, mt, no, pl, pt, ro, sk, sl, sq, sv, tr | Default |
| Q | U+0051 | LATIN CAPITAL LETTER Q | ca, cs, da, de, en, es, et, eu, fi, fr, it, mt, no, pt, ro, sk, sq, sv | Default |
| R | U+0052 | LATIN CAPITAL LETTER R | ca, cs, cy, da, de, en, es, et, eu, fi, fr, ga, hr, hu, is, it, lt, lv, mt, no, pl, pt, ro, sk, sl, sq, sv, tr | Default |
| S | U+0053 | LATIN CAPITAL LETTER S | ca, cs, cy, da, de, en, es, et, eu, fi, fr, ga, hr, hu, is, it, lt, lv, mt, no, pl, pt, ro, sk, sl, sq, sv, tr | Default |
| T | U+0054 | LATIN CAPITAL LETTER T | ca, cs, cy, da, de, en, es, et, eu, fi, fr, ga, hr, hu, is, it, lt, lv, mt, no, pl, pt, ro, sk, sl, sq, sv, tr | Default |
| U | U+0055 | LATIN CAPITAL LETTER U | ca, cs, cy, da, de, en, es, et, eu, fi, fr, ga, hr, hu, is, it, lt, lv, mt, no, pl, pt, ro, sk, sl, sq, sv, tr | Default |
| V | U+0056 | LATIN CAPITAL LETTER V | ca, cs, da, de, en, es, et, eu, fi, fr, hr, hu, is, it, lt, lv, mt, no, pt, ro, sk, sl, sq, sv, tr | Default |
| W | U+0057 | LATIN CAPITAL LETTER W | ca, cs, cy, da, de, en, es, et, eu, fi, fr, it, mt, no, pl, pt, ro, sk, sv | Default |
| X | U+0058 | LATIN CAPITAL LETTER X | ca, cs, da, de, en, es, et, eu, fi, fr, is, it, mt, no, pt, ro, sk, sq, sv | Default |
| Y | U+0059 | LATIN CAPITAL LETTER Y | ca, cs, cy, da, de, en, es, et, eu, fi, fr, hu, is, it, lt, no, pl, pt, ro, sk, sq, sv, tr | Default |
| Z | U+005A | LATIN CAPITAL LETTER Z | ca, cs, da, de, en, es, et, eu, fi, fr, hr, hu, it, lt, lv, mt, no, pl, pt, ro, sk, sl, sq, sv, tr | Default |
| [ | U+005B | LEFT SQUARE BRACKET | All profiles (keyboard/prose) | Default |
| \ | U+005C | REVERSE SOLIDUS | All profiles (keyboard/prose) | Default |
| ] | U+005D | RIGHT SQUARE BRACKET | All profiles (keyboard/prose) | Default |
| ^ | U+005E | CIRCUMFLEX ACCENT | All profiles (keyboard/prose) | Default |
| _ | U+005F | LOW LINE | All profiles (keyboard/prose) | Default |
| ` | U+0060 | GRAVE ACCENT | All profiles (keyboard/prose) | Default |
| a | U+0061 | LATIN SMALL LETTER A | ca, cs, cy, da, de, en, es, et, eu, fi, fr, ga, hr, hu, is, it, lt, lv, mt, no, pl, pt, ro, sk, sl, sq, sv, tr | Default |
| b | U+0062 | LATIN SMALL LETTER B | ca, cs, cy, da, de, en, es, et, eu, fi, fr, ga, hr, hu, is, it, lt, lv, mt, no, pl, pt, ro, sk, sl, sq, sv, tr | Default |
| c | U+0063 | LATIN SMALL LETTER C | ca, cs, cy, da, de, en, es, et, eu, fi, fr, ga, hr, hu, it, lt, lv, no, pl, pt, ro, sk, sl, sq, sv, tr | Default |
| d | U+0064 | LATIN SMALL LETTER D | ca, cs, cy, da, de, en, es, et, eu, fi, fr, ga, hr, hu, is, it, lt, lv, mt, no, pl, pt, ro, sk, sl, sq, sv, tr | Default |
| e | U+0065 | LATIN SMALL LETTER E | ca, cs, cy, da, de, en, es, et, eu, fi, fr, ga, hr, hu, is, it, lt, lv, mt, no, pl, pt, ro, sk, sl, sq, sv, tr | Default |
| f | U+0066 | LATIN SMALL LETTER F | ca, cs, cy, da, de, en, es, et, eu, fi, fr, ga, hr, hu, is, it, lt, lv, mt, no, pl, pt, ro, sk, sl, sq, sv, tr | Default |
| g | U+0067 | LATIN SMALL LETTER G | ca, cs, cy, da, de, en, es, et, eu, fi, fr, ga, hr, hu, is, it, lt, lv, mt, no, pl, pt, ro, sk, sl, sq, sv, tr | Default |
| h | U+0068 | LATIN SMALL LETTER H | ca, cs, cy, da, de, en, es, et, eu, fi, fr, ga, hr, hu, is, it, lt, lv, mt, no, pl, pt, ro, sk, sl, sq, sv, tr | Default |
| i | U+0069 | LATIN SMALL LETTER I | ca, cs, cy, da, de, en, es, et, eu, fi, fr, ga, hr, hu, is, it, lt, lv, mt, no, pl, pt, ro, sk, sl, sq, sv, tr | Default |
| j | U+006A | LATIN SMALL LETTER J | ca, cs, cy, da, de, en, es, et, eu, fi, fr, hr, hu, is, it, lt, lv, mt, no, pl, pt, ro, sk, sl, sq, sv, tr | Default |
| k | U+006B | LATIN SMALL LETTER K | ca, cs, da, de, en, es, et, eu, fi, fr, hr, hu, is, it, lt, lv, mt, no, pl, pt, ro, sk, sl, sq, sv, tr | Default |
| l | U+006C | LATIN SMALL LETTER L | ca, cs, cy, da, de, en, es, et, eu, fi, fr, ga, hr, hu, is, it, lt, lv, mt, no, pl, pt, ro, sk, sl, sq, sv, tr | Default |
| m | U+006D | LATIN SMALL LETTER M | ca, cs, cy, da, de, en, es, et, eu, fi, fr, ga, hr, hu, is, it, lt, lv, mt, no, pl, pt, ro, sk, sl, sq, sv, tr | Default |
| n | U+006E | LATIN SMALL LETTER N | ca, cs, cy, da, de, en, es, et, eu, fi, fr, ga, hr, hu, is, it, lt, lv, mt, no, pl, pt, ro, sk, sl, sq, sv, tr | Default |
| o | U+006F | LATIN SMALL LETTER O | ca, cs, cy, da, de, en, es, et, eu, fi, fr, ga, hr, hu, is, it, lt, lv, mt, no, pl, pt, ro, sk, sl, sq, sv, tr | Default |
| p | U+0070 | LATIN SMALL LETTER P | ca, cs, cy, da, de, en, es, et, eu, fi, fr, ga, hr, hu, is, it, lt, lv, mt, no, pl, pt, ro, sk, sl, sq, sv, tr | Default |
| q | U+0071 | LATIN SMALL LETTER Q | ca, cs, da, de, en, es, et, eu, fi, fr, it, mt, no, pt, ro, sk, sq, sv | Default |
| r | U+0072 | LATIN SMALL LETTER R | ca, cs, cy, da, de, en, es, et, eu, fi, fr, ga, hr, hu, is, it, lt, lv, mt, no, pl, pt, ro, sk, sl, sq, sv, tr | Default |
| s | U+0073 | LATIN SMALL LETTER S | ca, cs, cy, da, de, en, es, et, eu, fi, fr, ga, hr, hu, is, it, lt, lv, mt, no, pl, pt, ro, sk, sl, sq, sv, tr | Default |
| t | U+0074 | LATIN SMALL LETTER T | ca, cs, cy, da, de, en, es, et, eu, fi, fr, ga, hr, hu, is, it, lt, lv, mt, no, pl, pt, ro, sk, sl, sq, sv, tr | Default |
| u | U+0075 | LATIN SMALL LETTER U | ca, cs, cy, da, de, en, es, et, eu, fi, fr, ga, hr, hu, is, it, lt, lv, mt, no, pl, pt, ro, sk, sl, sq, sv, tr | Default |
| v | U+0076 | LATIN SMALL LETTER V | ca, cs, da, de, en, es, et, eu, fi, fr, hr, hu, is, it, lt, lv, mt, no, pt, ro, sk, sl, sq, sv, tr | Default |
| w | U+0077 | LATIN SMALL LETTER W | ca, cs, cy, da, de, en, es, et, eu, fi, fr, it, mt, no, pl, pt, ro, sk, sv | Default |
| x | U+0078 | LATIN SMALL LETTER X | ca, cs, da, de, en, es, et, eu, fi, fr, is, it, mt, no, pt, ro, sk, sq, sv | Default |
| y | U+0079 | LATIN SMALL LETTER Y | ca, cs, cy, da, de, en, es, et, eu, fi, fr, hu, is, it, lt, no, pl, pt, ro, sk, sq, sv, tr | Default |
| z | U+007A | LATIN SMALL LETTER Z | ca, cs, da, de, en, es, et, eu, fi, fr, hr, hu, it, lt, lv, mt, no, pl, pt, ro, sk, sl, sq, sv, tr | Default |
| { | U+007B | LEFT CURLY BRACKET | All profiles (keyboard/prose) | Default |
| &#124; | U+007C | VERTICAL LINE | All profiles (keyboard/prose) | Default |
| } | U+007D | RIGHT CURLY BRACKET | All profiles (keyboard/prose) | Default |
| ~ | U+007E | TILDE | All profiles (keyboard/prose) | Default |
| ␣ (blank U+00A0) | U+00A0 | NO-BREAK SPACE | All profiles (keyboard/prose) | Default |
| ¡ | U+00A1 | INVERTED EXCLAMATION MARK | es | Default |
| ª | U+00AA | FEMININE ORDINAL INDICATOR | es, pt | Default |
| « | U+00AB | LEFT-POINTING DOUBLE ANGLE QUOTATION MARK | All profiles (keyboard/prose) | Default |
| · | U+00B7 | MIDDLE DOT | ca | On request |
| º | U+00BA | MASCULINE ORDINAL INDICATOR | es, pt | Default |
| » | U+00BB | RIGHT-POINTING DOUBLE ANGLE QUOTATION MARK | All profiles (keyboard/prose) | Default |
| ¿ | U+00BF | INVERTED QUESTION MARK | es | Default |
| À | U+00C0 | LATIN CAPITAL LETTER A WITH GRAVE | ca, cy, fr, it, mt, no, pt, sv | Default |
| Á | U+00C1 | LATIN CAPITAL LETTER A WITH ACUTE | cs, cy, es, ga, hu, is, pt, sk | Default |
| Â | U+00C2 | LATIN CAPITAL LETTER A WITH CIRCUMFLEX | cy, fr, pt, ro, tr | Default |
| Ã | U+00C3 | LATIN CAPITAL LETTER A WITH TILDE | pt | Default |
| Ä | U+00C4 | LATIN CAPITAL LETTER A WITH DIAERESIS | cy, de, et, fi, sk, sv | On request |
| Å | U+00C5 | LATIN CAPITAL LETTER A WITH RING ABOVE | da, fi, no, sv | On request |
| Æ | U+00C6 | LATIN CAPITAL LETTER AE | da, fr, is, no | Default |
| Ç | U+00C7 | LATIN CAPITAL LETTER C WITH CEDILLA | ca, eu, fr, pt, sq, tr | Default |
| È | U+00C8 | LATIN CAPITAL LETTER E WITH GRAVE | ca, cy, fr, it, mt | Default |
| É | U+00C9 | LATIN CAPITAL LETTER E WITH ACUTE | ca, cs, cy, es, fr, ga, hu, is, it, no, pt, sk, sv | Default |
| Ê | U+00CA | LATIN CAPITAL LETTER E WITH CIRCUMFLEX | cy, fr, pt | Default |
| Ë | U+00CB | LATIN CAPITAL LETTER E WITH DIAERESIS | cy, fr, sq | Default |
| Ì | U+00CC | LATIN CAPITAL LETTER I WITH GRAVE | cy, it, mt | Default |
| Í | U+00CD | LATIN CAPITAL LETTER I WITH ACUTE | ca, cs, cy, es, ga, hu, is, pt, sk | Default |
| Î | U+00CE | LATIN CAPITAL LETTER I WITH CIRCUMFLEX | cy, fr, ro, tr | Default |
| Ï | U+00CF | LATIN CAPITAL LETTER I WITH DIAERESIS | ca, cy, fr | Default |
| Ð | U+00D0 | LATIN CAPITAL LETTER ETH | is | On request |
| Ñ | U+00D1 | LATIN CAPITAL LETTER N WITH TILDE | es, eu | Default |
| Ò | U+00D2 | LATIN CAPITAL LETTER O WITH GRAVE | ca, cy, it, mt, no | Default |
| Ó | U+00D3 | LATIN CAPITAL LETTER O WITH ACUTE | ca, cs, cy, es, ga, hu, is, it, no, pl, pt, sk | Default |
| Ô | U+00D4 | LATIN CAPITAL LETTER O WITH CIRCUMFLEX | cy, fr, no, pt, sk | Default |
| Õ | U+00D5 | LATIN CAPITAL LETTER O WITH TILDE | et, pt | Default |
| Ö | U+00D6 | LATIN CAPITAL LETTER O WITH DIAERESIS | cy, de, et, fi, hu, is, sv, tr | On request |
| Ø | U+00D8 | LATIN CAPITAL LETTER O WITH STROKE | da, no | On request |
| Ù | U+00D9 | LATIN CAPITAL LETTER U WITH GRAVE | cy, fr, it, mt | Default |
| Ú | U+00DA | LATIN CAPITAL LETTER U WITH ACUTE | ca, cs, cy, es, ga, hu, is, pt, sk | Default |
| Û | U+00DB | LATIN CAPITAL LETTER U WITH CIRCUMFLEX | cy, fr, tr | Default |
| Ü | U+00DC | LATIN CAPITAL LETTER U WITH DIAERESIS | ca, cy, de, es, et, fr, hu, tr | Default |
| Ý | U+00DD | LATIN CAPITAL LETTER Y WITH ACUTE | cs, cy, is, sk | On request |
| Þ | U+00DE | LATIN CAPITAL LETTER THORN | is | On request |
| ß | U+00DF | LATIN SMALL LETTER SHARP S | de | On request |
| à | U+00E0 | LATIN SMALL LETTER A WITH GRAVE | ca, cy, fr, it, mt, no, pt, sv | Default |
| á | U+00E1 | LATIN SMALL LETTER A WITH ACUTE | cs, cy, es, ga, hu, is, pt, sk | Default |
| â | U+00E2 | LATIN SMALL LETTER A WITH CIRCUMFLEX | cy, fr, pt, ro, tr | Default |
| ã | U+00E3 | LATIN SMALL LETTER A WITH TILDE | pt | Default |
| ä | U+00E4 | LATIN SMALL LETTER A WITH DIAERESIS | cy, de, et, fi, sk, sv | On request |
| å | U+00E5 | LATIN SMALL LETTER A WITH RING ABOVE | da, fi, no, sv | On request |
| æ | U+00E6 | LATIN SMALL LETTER AE | da, fr, is, no | Default |
| ç | U+00E7 | LATIN SMALL LETTER C WITH CEDILLA | ca, eu, fr, pt, sq, tr | Default |
| è | U+00E8 | LATIN SMALL LETTER E WITH GRAVE | ca, cy, fr, it, mt | Default |
| é | U+00E9 | LATIN SMALL LETTER E WITH ACUTE | ca, cs, cy, es, fr, ga, hu, is, it, no, pt, sk, sv | Default |
| ê | U+00EA | LATIN SMALL LETTER E WITH CIRCUMFLEX | cy, fr, pt | Default |
| ë | U+00EB | LATIN SMALL LETTER E WITH DIAERESIS | cy, fr, sq | Default |
| ì | U+00EC | LATIN SMALL LETTER I WITH GRAVE | cy, it, mt | Default |
| í | U+00ED | LATIN SMALL LETTER I WITH ACUTE | ca, cs, cy, es, ga, hu, is, pt, sk | Default |
| î | U+00EE | LATIN SMALL LETTER I WITH CIRCUMFLEX | cy, fr, ro, tr | Default |
| ï | U+00EF | LATIN SMALL LETTER I WITH DIAERESIS | ca, cy, fr | Default |
| ð | U+00F0 | LATIN SMALL LETTER ETH | is | On request |
| ñ | U+00F1 | LATIN SMALL LETTER N WITH TILDE | es, eu | Default |
| ò | U+00F2 | LATIN SMALL LETTER O WITH GRAVE | ca, cy, it, mt, no | Default |
| ó | U+00F3 | LATIN SMALL LETTER O WITH ACUTE | ca, cs, cy, es, ga, hu, is, it, no, pl, pt, sk | Default |
| ô | U+00F4 | LATIN SMALL LETTER O WITH CIRCUMFLEX | cy, fr, no, pt, sk | Default |
| õ | U+00F5 | LATIN SMALL LETTER O WITH TILDE | et, pt | Default |
| ö | U+00F6 | LATIN SMALL LETTER O WITH DIAERESIS | cy, de, et, fi, hu, is, sv, tr | On request |
| ø | U+00F8 | LATIN SMALL LETTER O WITH STROKE | da, no | On request |
| ù | U+00F9 | LATIN SMALL LETTER U WITH GRAVE | cy, fr, it, mt | Default |
| ú | U+00FA | LATIN SMALL LETTER U WITH ACUTE | ca, cs, cy, es, ga, hu, is, pt, sk | Default |
| û | U+00FB | LATIN SMALL LETTER U WITH CIRCUMFLEX | cy, fr, tr | Default |
| ü | U+00FC | LATIN SMALL LETTER U WITH DIAERESIS | ca, cy, de, es, et, fr, hu, tr | Default |
| ý | U+00FD | LATIN SMALL LETTER Y WITH ACUTE | cs, cy, is, sk | On request |
| þ | U+00FE | LATIN SMALL LETTER THORN | is | On request |
| ÿ | U+00FF | LATIN SMALL LETTER Y WITH DIAERESIS | cy, fr | Default |
| Ā | U+0100 | LATIN CAPITAL LETTER A WITH MACRON | lv | On request |
| ā | U+0101 | LATIN SMALL LETTER A WITH MACRON | lv | On request |
| Ă | U+0102 | LATIN CAPITAL LETTER A WITH BREVE | ro | On request |
| ă | U+0103 | LATIN SMALL LETTER A WITH BREVE | ro | On request |
| Ą | U+0104 | LATIN CAPITAL LETTER A WITH OGONEK | lt, pl | On request |
| ą | U+0105 | LATIN SMALL LETTER A WITH OGONEK | lt, pl | On request |
| Ć | U+0106 | LATIN CAPITAL LETTER C WITH ACUTE | hr, pl | On request |
| ć | U+0107 | LATIN SMALL LETTER C WITH ACUTE | hr, pl | On request |
| Ċ | U+010A | LATIN CAPITAL LETTER C WITH DOT ABOVE | mt | On request |
| ċ | U+010B | LATIN SMALL LETTER C WITH DOT ABOVE | mt | On request |
| Č | U+010C | LATIN CAPITAL LETTER C WITH CARON | cs, hr, lt, lv, sk, sl | On request |
| č | U+010D | LATIN SMALL LETTER C WITH CARON | cs, hr, lt, lv, sk, sl | On request |
| Ď | U+010E | LATIN CAPITAL LETTER D WITH CARON | cs, sk | On request |
| ď | U+010F | LATIN SMALL LETTER D WITH CARON | cs, sk | On request |
| Đ | U+0110 | LATIN CAPITAL LETTER D WITH STROKE | hr | On request |
| đ | U+0111 | LATIN SMALL LETTER D WITH STROKE | hr | On request |
| Ē | U+0112 | LATIN CAPITAL LETTER E WITH MACRON | lv | On request |
| ē | U+0113 | LATIN SMALL LETTER E WITH MACRON | lv | On request |
| Ė | U+0116 | LATIN CAPITAL LETTER E WITH DOT ABOVE | lt | On request |
| ė | U+0117 | LATIN SMALL LETTER E WITH DOT ABOVE | lt | On request |
| Ę | U+0118 | LATIN CAPITAL LETTER E WITH OGONEK | lt, pl | On request |
| ę | U+0119 | LATIN SMALL LETTER E WITH OGONEK | lt, pl | On request |
| Ě | U+011A | LATIN CAPITAL LETTER E WITH CARON | cs | On request |
| ě | U+011B | LATIN SMALL LETTER E WITH CARON | cs | On request |
| Ğ | U+011E | LATIN CAPITAL LETTER G WITH BREVE | tr | On request |
| ğ | U+011F | LATIN SMALL LETTER G WITH BREVE | tr | On request |
| Ġ | U+0120 | LATIN CAPITAL LETTER G WITH DOT ABOVE | mt | On request |
| ġ | U+0121 | LATIN SMALL LETTER G WITH DOT ABOVE | mt | On request |
| Ģ | U+0122 | LATIN CAPITAL LETTER G WITH CEDILLA | lv | On request |
| ģ | U+0123 | LATIN SMALL LETTER G WITH CEDILLA | lv | On request |
| Ħ | U+0126 | LATIN CAPITAL LETTER H WITH STROKE | mt | On request |
| ħ | U+0127 | LATIN SMALL LETTER H WITH STROKE | mt | On request |
| Ī | U+012A | LATIN CAPITAL LETTER I WITH MACRON | lv | On request |
| ī | U+012B | LATIN SMALL LETTER I WITH MACRON | lv | On request |
| Į | U+012E | LATIN CAPITAL LETTER I WITH OGONEK | lt | On request |
| į | U+012F | LATIN SMALL LETTER I WITH OGONEK | lt | On request |
| İ | U+0130 | LATIN CAPITAL LETTER I WITH DOT ABOVE | tr | On request |
| ı | U+0131 | LATIN SMALL LETTER DOTLESS I | tr | On request |
| Ķ | U+0136 | LATIN CAPITAL LETTER K WITH CEDILLA | lv | On request |
| ķ | U+0137 | LATIN SMALL LETTER K WITH CEDILLA | lv | On request |
| Ĺ | U+0139 | LATIN CAPITAL LETTER L WITH ACUTE | sk | On request |
| ĺ | U+013A | LATIN SMALL LETTER L WITH ACUTE | sk | On request |
| Ļ | U+013B | LATIN CAPITAL LETTER L WITH CEDILLA | lv | On request |
| ļ | U+013C | LATIN SMALL LETTER L WITH CEDILLA | lv | On request |
| Ľ | U+013D | LATIN CAPITAL LETTER L WITH CARON | sk | On request |
| ľ | U+013E | LATIN SMALL LETTER L WITH CARON | sk | On request |
| Ł | U+0141 | LATIN CAPITAL LETTER L WITH STROKE | pl | On request |
| ł | U+0142 | LATIN SMALL LETTER L WITH STROKE | pl | On request |
| Ń | U+0143 | LATIN CAPITAL LETTER N WITH ACUTE | pl | On request |
| ń | U+0144 | LATIN SMALL LETTER N WITH ACUTE | pl | On request |
| Ņ | U+0145 | LATIN CAPITAL LETTER N WITH CEDILLA | lv | On request |
| ņ | U+0146 | LATIN SMALL LETTER N WITH CEDILLA | lv | On request |
| Ň | U+0147 | LATIN CAPITAL LETTER N WITH CARON | cs, sk | On request |
| ň | U+0148 | LATIN SMALL LETTER N WITH CARON | cs, sk | On request |
| Ő | U+0150 | LATIN CAPITAL LETTER O WITH DOUBLE ACUTE | hu | On request |
| ő | U+0151 | LATIN SMALL LETTER O WITH DOUBLE ACUTE | hu | On request |
| Œ | U+0152 | LATIN CAPITAL LIGATURE OE | fr | Default |
| œ | U+0153 | LATIN SMALL LIGATURE OE | fr | Default |
| Ŕ | U+0154 | LATIN CAPITAL LETTER R WITH ACUTE | sk | On request |
| ŕ | U+0155 | LATIN SMALL LETTER R WITH ACUTE | sk | On request |
| Ř | U+0158 | LATIN CAPITAL LETTER R WITH CARON | cs | On request |
| ř | U+0159 | LATIN SMALL LETTER R WITH CARON | cs | On request |
| Ś | U+015A | LATIN CAPITAL LETTER S WITH ACUTE | pl | On request |
| ś | U+015B | LATIN SMALL LETTER S WITH ACUTE | pl | On request |
| Ş | U+015E | LATIN CAPITAL LETTER S WITH CEDILLA | tr | On request |
| ş | U+015F | LATIN SMALL LETTER S WITH CEDILLA | tr | On request |
| Š | U+0160 | LATIN CAPITAL LETTER S WITH CARON | cs, et, fi, hr, lt, lv, sk, sl | On request |
| š | U+0161 | LATIN SMALL LETTER S WITH CARON | cs, et, fi, hr, lt, lv, sk, sl | On request |
| Ť | U+0164 | LATIN CAPITAL LETTER T WITH CARON | cs, sk | On request |
| ť | U+0165 | LATIN SMALL LETTER T WITH CARON | cs, sk | On request |
| Ū | U+016A | LATIN CAPITAL LETTER U WITH MACRON | lt, lv | On request |
| ū | U+016B | LATIN SMALL LETTER U WITH MACRON | lt, lv | On request |
| Ů | U+016E | LATIN CAPITAL LETTER U WITH RING ABOVE | cs | On request |
| ů | U+016F | LATIN SMALL LETTER U WITH RING ABOVE | cs | On request |
| Ű | U+0170 | LATIN CAPITAL LETTER U WITH DOUBLE ACUTE | hu | On request |
| ű | U+0171 | LATIN SMALL LETTER U WITH DOUBLE ACUTE | hu | On request |
| Ų | U+0172 | LATIN CAPITAL LETTER U WITH OGONEK | lt | On request |
| ų | U+0173 | LATIN SMALL LETTER U WITH OGONEK | lt | On request |
| Ŵ | U+0174 | LATIN CAPITAL LETTER W WITH CIRCUMFLEX | cy | On request |
| ŵ | U+0175 | LATIN SMALL LETTER W WITH CIRCUMFLEX | cy | On request |
| Ŷ | U+0176 | LATIN CAPITAL LETTER Y WITH CIRCUMFLEX | cy | On request |
| ŷ | U+0177 | LATIN SMALL LETTER Y WITH CIRCUMFLEX | cy | On request |
| Ÿ | U+0178 | LATIN CAPITAL LETTER Y WITH DIAERESIS | cy, fr | Default |
| Ź | U+0179 | LATIN CAPITAL LETTER Z WITH ACUTE | pl | On request |
| ź | U+017A | LATIN SMALL LETTER Z WITH ACUTE | pl | On request |
| Ż | U+017B | LATIN CAPITAL LETTER Z WITH DOT ABOVE | mt, pl | On request |
| ż | U+017C | LATIN SMALL LETTER Z WITH DOT ABOVE | mt, pl | On request |
| Ž | U+017D | LATIN CAPITAL LETTER Z WITH CARON | cs, et, fi, hr, lt, lv, sk, sl | On request |
| ž | U+017E | LATIN SMALL LETTER Z WITH CARON | cs, et, fi, hr, lt, lv, sk, sl | On request |
| Ș | U+0218 | LATIN CAPITAL LETTER S WITH COMMA BELOW | ro | On request |
| ș | U+0219 | LATIN SMALL LETTER S WITH COMMA BELOW | ro | On request |
| Ț | U+021A | LATIN CAPITAL LETTER T WITH COMMA BELOW | ro | On request |
| ț | U+021B | LATIN SMALL LETTER T WITH COMMA BELOW | ro | On request |
| Ẁ | U+1E80 | LATIN CAPITAL LETTER W WITH GRAVE | cy | On request |
| ẁ | U+1E81 | LATIN SMALL LETTER W WITH GRAVE | cy | On request |
| Ẃ | U+1E82 | LATIN CAPITAL LETTER W WITH ACUTE | cy | On request |
| ẃ | U+1E83 | LATIN SMALL LETTER W WITH ACUTE | cy | On request |
| Ẅ | U+1E84 | LATIN CAPITAL LETTER W WITH DIAERESIS | cy | On request |
| ẅ | U+1E85 | LATIN SMALL LETTER W WITH DIAERESIS | cy | On request |
| ẞ | U+1E9E | LATIN CAPITAL LETTER SHARP S | de | On request |
| Ỳ | U+1EF2 | LATIN CAPITAL LETTER Y WITH GRAVE | cy | On request |
| ỳ | U+1EF3 | LATIN SMALL LETTER Y WITH GRAVE | cy | On request |
| – | U+2013 | EN DASH | All profiles (keyboard/prose) | Default |
| — | U+2014 | EM DASH | All profiles (keyboard/prose) | Default |
| ‘ | U+2018 | LEFT SINGLE QUOTATION MARK | All profiles (keyboard/prose) | Default |
| ’ | U+2019 | RIGHT SINGLE QUOTATION MARK | All profiles (keyboard/prose) | Default |
| ‚ | U+201A | SINGLE LOW-9 QUOTATION MARK | cs, de, et, lt, lv, pl, ro, sk | On request |
| “ | U+201C | LEFT DOUBLE QUOTATION MARK | All profiles (keyboard/prose) | Default |
| ” | U+201D | RIGHT DOUBLE QUOTATION MARK | All profiles (keyboard/prose) | Default |
| „ | U+201E | DOUBLE LOW-9 QUOTATION MARK | cs, de, et, lt, lv, pl, ro, sk | On request |
| … | U+2026 | HORIZONTAL ELLIPSIS | All profiles (keyboard/prose) | Default |
| ␣ (blank U+202F) | U+202F | NARROW NO-BREAK SPACE | All profiles (keyboard/prose) | Default |

<!-- END GENERATED INVENTORY -->
