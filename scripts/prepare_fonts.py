"""Build the reading fonts that ship with OpenLargePrint.

Run this only when the font list changes; its output is committed under
src/openlargeprint/exporters/fonts and the conversion itself never downloads
anything.

    uv run --with fonttools --with uharfbuzz --with arabic-reshaper \
        python scripts/prepare_fonts.py

Every source file comes from a pinned commit of github.com/google/fonts and is
checked against its SHA-256 before use; a mismatch stops the build. For each
family the script then:

* freezes variable fonts into static Regular, Bold (and Italic) faces, because
  ReportLab and Word embedding need static TrueType files;
* trims Latin families to the scripts the converter writes (Latin, Greek,
  Cyrillic, IPA, punctuation, arrows, maths), which keeps the installer small;
* gives Arabic families a mapping for every Arabic presentation form the PDF
  writer needs. The PDF writer cannot shape text itself, so it sets the
  positional forms directly; many good Arabic fonts reach those shapes only
  through OpenType features. Each missing form is found by shaping the letter
  in the right position with HarfBuzz and taking the glyph the font itself
  chooses, so nothing is drawn by hand.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import sys
import unicodedata
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "src" / "openlargeprint" / "exporters" / "fonts"
COMMIT = "45e3d5269e4a17d823f6d84470bc084dc5ae46f6"
BASE = f"https://raw.githubusercontent.com/google/fonts/{COMMIT}/ofl/"

LATIN_RANGES = [
    (0x0020, 0x024F), (0x0250, 0x02FF), (0x0300, 0x036F), (0x0370, 0x03FF), (0x0400, 0x04FF),
    (0x1E00, 0x1EFF), (0x2000, 0x206F), (0x2070, 0x209F), (0x20A0, 0x20CF), (0x2100, 0x214F),
    (0x2150, 0x218F), (0x2190, 0x21FF), (0x2200, 0x22FF), (0x25A0, 0x25FF), (0x2610, 0x2612),
    (0x2713, 0x2717), (0xFB00, 0xFB06), (0xFEFF, 0xFEFF), (0xFFFD, 0xFFFD),
]


@dataclass
class Face:
    style: str            # Regular, Bold, Italic, BoldItalic
    source: str           # path under ofl/
    axes: Dict[str, float] = field(default_factory=dict)


@dataclass
class Family:
    file_prefix: str
    family: str
    script: str           # "latin" or "arabic"
    license_source: str
    faces: List[Face]


FAMILIES: List[Family] = [
    Family("Lexend", "Lexend", "latin", "lexend/OFL.txt", [
               Face("Regular", "lexend/Lexend[wght].ttf", {"wght": 400}),
               Face("Bold", "lexend/Lexend[wght].ttf", {"wght": 700}),
           ]),
    Family("Andika", "Andika", "latin", "andika/OFL.txt", [
        Face("Regular", "andika/Andika-Regular.ttf"),
        Face("Bold", "andika/Andika-Bold.ttf"),
        Face("Italic", "andika/Andika-Italic.ttf"),
        Face("BoldItalic", "andika/Andika-BoldItalic.ttf"),
    ]),
    Family("NotoSans", "Noto Sans", "latin", "notosans/OFL.txt", [
        Face("Regular", "notosans/NotoSans[wdth,wght].ttf", {"wdth": 100, "wght": 400}),
        Face("Bold", "notosans/NotoSans[wdth,wght].ttf", {"wdth": 100, "wght": 700}),
        Face("Italic", "notosans/NotoSans-Italic[wdth,wght].ttf", {"wdth": 100, "wght": 400}),
        Face("BoldItalic", "notosans/NotoSans-Italic[wdth,wght].ttf", {"wdth": 100, "wght": 700}),
    ]),
    Family("NotoSerif", "Noto Serif", "latin", "notoserif/OFL.txt", [
        Face("Regular", "notoserif/NotoSerif[wdth,wght].ttf", {"wdth": 100, "wght": 400}),
        Face("Bold", "notoserif/NotoSerif[wdth,wght].ttf", {"wdth": 100, "wght": 700}),
        Face("Italic", "notoserif/NotoSerif-Italic[wdth,wght].ttf", {"wdth": 100, "wght": 400}),
        Face("BoldItalic", "notoserif/NotoSerif-Italic[wdth,wght].ttf", {"wdth": 100, "wght": 700}),
    ]),
    Family("NotoSansArabic", "Noto Sans Arabic", "arabic", "notosansarabic/OFL.txt", [
        Face("Regular", "notosansarabic/NotoSansArabic[wdth,wght].ttf", {"wdth": 100, "wght": 400}),
        Face("Bold", "notosansarabic/NotoSansArabic[wdth,wght].ttf", {"wdth": 100, "wght": 700}),
    ]),
    Family("NotoNaskhArabic", "Noto Naskh Arabic", "arabic", "notonaskharabic/OFL.txt", [
        Face("Regular", "notonaskharabic/NotoNaskhArabic[wght].ttf", {"wght": 400}),
        Face("Bold", "notonaskharabic/NotoNaskhArabic[wght].ttf", {"wght": 700}),
    ]),
    Family("Amiri", "Amiri", "arabic", "amiri/OFL.txt", [
        Face("Regular", "amiri/Amiri-Regular.ttf"),
        Face("Bold", "amiri/Amiri-Bold.ttf"),
    ]),
    Family("IBMPlexSansArabic", "IBM Plex Sans Arabic", "arabic", "ibmplexsansarabic/OFL.txt", [
        Face("Regular", "ibmplexsansarabic/IBMPlexSansArabic-Regular.ttf"),
        Face("Bold", "ibmplexsansarabic/IBMPlexSansArabic-Bold.ttf"),
    ]),
    Family("Tajawal", "Tajawal", "arabic", "tajawal/OFL.txt", [
        Face("Regular", "tajawal/Tajawal-Regular.ttf"),
        Face("Bold", "tajawal/Tajawal-Bold.ttf"),
    ]),
    Family("ReadexPro", "Readex Pro", "arabic", "readexpro/OFL.txt", [
        Face("Regular", "readexpro/ReadexPro[HEXP,wght].ttf", {"HEXP": 0, "wght": 400}),
        Face("Bold", "readexpro/ReadexPro[HEXP,wght].ttf", {"HEXP": 0, "wght": 700}),
    ]),
]

HASHES_FILE = Path(__file__).with_name("font_sources.sha256")


def load_hashes() -> Dict[str, str]:
    hashes: Dict[str, str] = {}
    if HASHES_FILE.exists():
        for line in HASHES_FILE.read_text(encoding="utf-8").splitlines():
            if line.strip() and not line.startswith("#"):
                digest, name = line.split(None, 1)
                hashes[name.strip()] = digest
    return hashes


_cache: Dict[str, bytes] = {}


def fetch(source: str, hashes: Dict[str, str], record: bool) -> bytes:
    if source in _cache:
        return _cache[source]
    url = BASE + source.replace("[", "%5B").replace("]", "%5D")
    with urllib.request.urlopen(url, timeout=120) as response:
        data = response.read()
    digest = hashlib.sha256(data).hexdigest()
    if record:
        hashes[source] = digest
    elif hashes.get(source) != digest:
        raise SystemExit(f"Checksum mismatch for {source}: got {digest}, expected {hashes.get(source)}")
    _cache[source] = data
    return data


# --- building ----------------------------------------------------------------

def instantiate(font, axes: Dict[str, float]):
    from fontTools.varLib.instancer import instantiateVariableFont
    if "fvar" not in font:
        return font
    present = {a.axisTag for a in font["fvar"].axes}
    location = {tag: value for tag, value in axes.items() if tag in present}
    for axis in font["fvar"].axes:
        location.setdefault(axis.axisTag, axis.defaultValue)
    return instantiateVariableFont(font, location, inplace=False, static=True)


def set_names(font, family: str, style: str, prefix: str) -> None:
    bold = "Bold" in style
    italic = "Italic" in style
    sub = {"Regular": "Regular", "Bold": "Bold", "Italic": "Italic", "BoldItalic": "Bold Italic"}[style]
    name = font["name"]
    for record in list(name.names):
        if record.nameID in (1, 2, 3, 4, 6, 16, 17, 21, 22, 25):
            name.removeNames(nameID=record.nameID)
    name.setName(family, 1, 3, 1, 0x409)
    name.setName(sub, 2, 3, 1, 0x409)
    name.setName(f"{family} {sub}".replace(" Regular", ""), 4, 3, 1, 0x409)
    name.setName(f"{prefix}-{style}", 6, 3, 1, 0x409)
    name.setName(f"{prefix}-{style};OpenLargePrint", 3, 3, 1, 0x409)
    os2 = font["OS/2"]
    os2.usWeightClass = 700 if bold else 400
    selection = os2.fsSelection & ~(0x01 | 0x20 | 0x40)
    if bold:
        selection |= 0x20
    if italic:
        selection |= 0x01
    if not bold and not italic:
        selection |= 0x40
    os2.fsSelection = selection
    font["head"].macStyle = (1 if bold else 0) | (2 if italic else 0)
    if "STAT" in font:
        del font["STAT"]


def subset_latin(font) -> None:
    from fontTools import subset
    unicodes = [cp for lo, hi in LATIN_RANGES for cp in range(lo, hi + 1)]
    options = subset.Options()
    options.layout_features = ["*"]
    options.name_IDs = ["*"]
    options.name_languages = ["*"]
    options.notdef_outline = True
    options.glyph_names = False
    options.hinting = False
    options.drop_tables += ["DSIG"]
    subsetter = subset.Subsetter(options)
    subsetter.populate(unicodes=unicodes)
    subsetter.subset(font)


ZWJ = "‍"


def presentation_forms_needed() -> List[int]:
    """Every Arabic presentation form arabic_reshaper can produce."""
    import arabic_reshaper
    letters = "ءآأؤإئابةتثجحخدذرزسشصضطظعغفقكلمنهوىيپچژگکیۀە"
    needed = set()
    for a in letters:
        for b in letters:
            for ch in arabic_reshaper.reshape(f"ب{a}{b}ب {a} {a}ب ب{a} {a}{b}"):
                if 0xFB50 <= ord(ch) <= 0xFDFF or 0xFE70 <= ord(ch) <= 0xFEFF:
                    needed.add(ord(ch))
    return sorted(needed)


def fill_presentation_forms(font, data: bytes, needed: List[int]) -> Tuple[int, List[int]]:
    """Map missing presentation forms to the glyphs the font's own shaping picks."""
    import uharfbuzz as hb
    face = hb.Face(data)
    hb_font = hb.Font(face)
    cmap = font.getBestCmap()
    order = font.getGlyphOrder()
    added = 0
    missing: List[int] = []
    for cp in needed:
        if cp in cmap:
            continue
        decomposition = unicodedata.decomposition(chr(cp)).split()
        if not decomposition or not decomposition[0].startswith("<"):
            missing.append(cp)
            continue
        form = decomposition[0]
        letters = "".join(chr(int(h, 16)) for h in decomposition[1:])
        text = {"<isolated>": letters, "<initial>": letters + ZWJ,
                "<medial>": ZWJ + letters + ZWJ, "<final>": ZWJ + letters}.get(form)
        if text is None:
            missing.append(cp)
            continue
        buf = hb.Buffer()
        buf.add_str(text)
        buf.guess_segment_properties()
        buf.flags = hb.BufferFlags.REMOVE_DEFAULT_IGNORABLES
        hb.shape(hb_font, buf, {})
        glyphs = [info.codepoint for info in buf.glyph_infos]
        if len(glyphs) != 1 or glyphs[0] == 0:
            missing.append(cp)
            continue
        name = order[glyphs[0]]
        for table in font["cmap"].tables:
            if table.isUnicode():
                table.cmap[cp] = name
        added += 1
    return added, missing


def build_face(family: Family, face: Face, hashes: Dict[str, str], record: bool,
               needed: List[int]) -> Tuple[Path, str]:
    from fontTools.ttLib import TTFont
    raw = fetch(face.source, hashes, record)
    font = instantiate(TTFont(io.BytesIO(raw)), face.axes)
    set_names(font, family.family, face.style, family.file_prefix)
    note = ""
    if family.script == "latin":
        subset_latin(font)
    else:
        if "hdmx" in font:
            del font["hdmx"]
        buffer = io.BytesIO()
        font.save(buffer)
        added, missing = fill_presentation_forms(font, buffer.getvalue(), needed)
        note = f"{added} forms mapped"
        if missing:
            note += f", {len(missing)} without a single glyph: " + " ".join(f"{m:04X}" for m in missing[:12])
    target = OUT / f"{family.file_prefix}-{face.style}.ttf"
    font.save(target)
    return target, note


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--record-hashes", action="store_true",
                        help="download and write font_sources.sha256 instead of checking it")
    parser.add_argument("--only", nargs="*", help="file prefixes to build")
    args = parser.parse_args(argv)

    hashes = load_hashes()
    needed = presentation_forms_needed()
    OUT.mkdir(parents=True, exist_ok=True)
    for family in FAMILIES:
        if args.only and family.file_prefix not in args.only:
            continue
        license_text = fetch(family.license_source, hashes, args.record_hashes)
        (OUT / f"{family.file_prefix}-OFL.txt").write_bytes(license_text)
        for face in family.faces:
            target, note = build_face(family, face, hashes, args.record_hashes, needed)
            print(f"{target.name:40s} {target.stat().st_size // 1024:5d} KB  {note}")
    if args.record_hashes:
        lines = ["# SHA-256 of every font source, from google/fonts at " + COMMIT]
        lines += [f"{digest}  {name}" for name, digest in sorted(hashes.items())]
        HASHES_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
