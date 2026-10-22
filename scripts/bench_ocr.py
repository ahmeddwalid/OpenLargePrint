"""Compare the bundled recognisers with Tesseract on synthetic pages.

    uv run python scripts/bench_ocr.py [--tessdata DIR] [--out results.md]

Pages of Arabic and English text are drawn in several typefaces and sizes, at
200 and 300 dpi, clean and degraded (blur, noise, JPEG artefacts, a slight
skew), and read by:

* the bundled PP-OCR recognisers (PP-OCRv6 for Latin, PP-OCRv5 Arabic), the
  way the converter runs them;
* Tesseract (if installed), with the language data in --tessdata or its own.

The score is the character error rate (edit distance / reference length) of
the whole page, lines in reading order. Lower is better. Nothing here is used
by the converter; it is how the choice of recogniser is checked.
"""

from __future__ import annotations

import argparse
import io
import random
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

ARABIC = [
    "العقد شريعة المتعاقدين فلا يجوز نقضه ولا تعديله إلا باتفاق الطرفين",
    "أو للأسباب التي يقررها القانون، ويجب تنفيذ العقد طبقا لما اشتمل عليه",
    "وبطريقة تتفق مع ما يوجبه حسن النية في المعاملات بين الناس",
    "لا يقتصر العقد على إلزام المتعاقد بما ورد فيه، ولكن يتناول أيضا",
    "ما هو من مستلزماته وفقا للقانون والعرف والعدالة بحسب طبيعة الالتزام",
    "إذا طرأت حوادث استثنائية عامة لم يكن في الوسع توقعها",
    "وترتب على حدوثها أن تنفيذ الالتزام التعاقدي وإن لم يصبح مستحيلا",
    "صار مرهقا للمدين بحيث يهدده بخسارة فادحة، جاز للقاضي تبعا للظروف",
    "وبعد الموازنة بين مصلحة الطرفين أن يرد الالتزام المرهق إلى الحد المعقول",
    "ويقع باطلا كل اتفاق على خلاف ذلك، المادة ١٤٧ من القانون المدني لسنة ١٩٤٨",
    "يفسر الشك في مصلحة المدين، ومع ذلك لا يجوز أن يكون تفسير العبارات الغامضة",
    "في عقود الإذعان ضارا بمصلحة الطرف المذعن، وفقا للمادة ١٥١ فقرة ٢",
]
ENGLISH = [
    "A contract is the law of the parties; it may not be revoked or altered",
    "except by their mutual consent or for reasons provided by law (Article 147).",
    "The contract must be performed in accordance with its contents and in",
    "a manner consistent with good faith. It binds the party not only to what",
    "is expressly stated, but also to everything that, according to law, custom",
    "and equity, follows from the nature of the obligation, including 3.5% interest.",
    "Where exceptional events of a general character, which could not have been",
    "foreseen, render performance of the obligation excessively onerous, the judge",
    "may, after balancing the interests of both parties, reduce the obligation",
    "to a reasonable limit. Any agreement to the contrary shall be void (s. 12(b)).",
    "Doubt is resolved in favour of the debtor; however, the interpretation of",
    "ambiguous terms in standard-form contracts must not harm the adhering party.",
]
FONTS = {
    "ar": ["NotoNaskhArabic", "NotoSansArabic", "Amiri", "Tajawal"],
    "en": ["NotoSerif", "NotoSans", "AtkinsonHyperlegible", "Andika"],
}
SIZES_PT = [10, 12, 14]
DPIS = [200, 300]


def levenshtein(a: str, b: str) -> int:
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        current = [i] + [0] * len(b)
        for j, cb in enumerate(b, 1):
            current[j] = min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (ca != cb))
        previous = current
    return previous[-1]


def normalise(text: str) -> str:
    from openlargeprint.text.normalize import fold_presentation_forms
    return " ".join(fold_presentation_forms(text).split())


def draw_page(lines: List[str], script: str, font_prefix: str, size_pt: int, dpi: int, degrade: bool,
              rng: random.Random):
    from PIL import Image, ImageDraw, ImageFilter, ImageFont, features
    from openlargeprint.exporters.fonts import bundled_font_dir

    px = size_pt * dpi / 72.0
    font = ImageFont.truetype(str(bundled_font_dir() / f"{font_prefix}-Regular.ttf"), int(round(px)))
    width = int(8.27 * dpi)
    height = int(px * 1.7 * len(lines) + 2 * dpi * 0.6)
    page = Image.new("L", (width, height), 255)
    draw = ImageDraw.Draw(page)
    raqm = features.check_feature("raqm")
    margin = int(dpi * 0.6)
    for index, line in enumerate(lines):
        y = margin + index * px * 1.7
        if script == "ar":
            if raqm:
                draw.text((width - margin, y), line, fill=0, font=font, anchor="ra", direction="rtl")
            else:
                from openlargeprint.text.bidi import reorder_bidi_line
                draw.text((width - margin, y), reorder_bidi_line(line), fill=0, font=font, anchor="ra")
        else:
            draw.text((margin, y), line, fill=0, font=font)
    if degrade:
        page = page.rotate(rng.uniform(-0.8, 0.8), fillcolor=255, resample=Image.BILINEAR)
        page = page.filter(ImageFilter.GaussianBlur(0.7))
        import numpy as np
        pixels = np.asarray(page).astype(np.int16)
        pixels = pixels + np.random.default_rng(rng.randrange(1 << 30)).normal(0, 18, pixels.shape).astype(np.int16)
        page = Image.fromarray(np.clip(pixels, 0, 255).astype(np.uint8))
        buffer = io.BytesIO()
        page.save(buffer, format="JPEG", quality=55)
        page = Image.open(io.BytesIO(buffer.getvalue())).convert("L")
    return page.convert("RGB")


class Paddle:
    name = "PP-OCR (bundled)"

    def __init__(self):
        from openlargeprint.ocr.paddle_engine import PaddleRapidOcrEngine
        self.engines = {lang: PaddleRapidOcrEngine(language=lang, in_process=True) for lang in ("en", "ar")}

    def read(self, image, script: str) -> str:
        result = self.engines[script]._analyze_page(image, page_num=1)
        lines = sorted(result.lines, key=lambda l: (min(p[1] for p in l.polygon), min(p[0] for p in l.polygon)))
        return "\n".join(line.text for line in lines)


class Tesseract:
    def __init__(self, tessdata: Optional[str]):
        self.tessdata = tessdata
        self.name = f"Tesseract {self._version()}" + (" (tessdata_best)" if tessdata else "")

    @staticmethod
    def _version() -> str:
        out = subprocess.run(["tesseract", "--version"], capture_output=True, text=True)
        return (out.stdout or out.stderr).split()[1]

    def read(self, image, script: str) -> str:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "page.png"
            image.save(path)
            command = ["tesseract", str(path), "-", "-l", "ara" if script == "ar" else "eng", "--psm", "6"]
            if self.tessdata:
                command += ["--tessdata-dir", self.tessdata]
            out = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
            return out.stdout


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tessdata", help="folder with Tesseract language data (e.g. tessdata_best)")
    parser.add_argument("--out", type=Path, help="write the results table here (Markdown)")
    parser.add_argument("--quick", action="store_true", help="one font and size per script")
    args = parser.parse_args(argv)

    engines = [Paddle()]
    if shutil.which("tesseract"):
        engines.append(Tesseract(None))
        if args.tessdata:
            engines.append(Tesseract(args.tessdata))
    rng = random.Random(1947)
    scores: Dict[Tuple[str, str, str], List[float]] = {}
    timing: Dict[str, List[float]] = {e.name: [] for e in engines}
    for script, lines in (("ar", ARABIC), ("en", ENGLISH)):
        fonts = FONTS[script][:1] if args.quick else FONTS[script]
        sizes = SIZES_PT[1:2] if args.quick else SIZES_PT
        for font in fonts:
            for size in sizes:
                for dpi in DPIS:
                    for degrade in (False, True):
                        page = draw_page(lines, script, font, size, dpi, degrade, rng)
                        reference = normalise(" ".join(lines))
                        condition = "degraded" if degrade else "clean"
                        for engine in engines:
                            started = time.perf_counter()
                            text = normalise(engine.read(page, script))
                            timing[engine.name].append(time.perf_counter() - started)
                            cer = levenshtein(reference, text) / len(reference)
                            scores.setdefault((engine.name, script, condition), []).append(cer)
                            print(f"{engine.name:32s} {script} {font:22s} {size:2d}pt {dpi}dpi {condition:8s} "
                                  f"CER {cer:6.3f}", flush=True)
    rows = ["| Recogniser | Arabic clean | Arabic degraded | English clean | English degraded | s/page |",
            "| --- | --- | --- | --- | --- | --- |"]
    for engine in engines:
        cells = [f"{100 * statistics.mean(scores[(engine.name, s, c)]):.1f}%"
                 for s in ("ar", "en") for c in ("clean", "degraded")]
        rows.append(f"| {engine.name} | " + " | ".join(cells) + f" | {statistics.mean(timing[engine.name]):.2f} |")
    table = "\n".join(rows)
    print("\nMean character error rate (lower is better)\n" + table)
    if args.out:
        args.out.write_text(table + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
