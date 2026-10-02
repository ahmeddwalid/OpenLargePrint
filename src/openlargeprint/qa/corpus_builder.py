"""Rights-safe synthetic benchmark corpus builder covering all 16 cases from DESIGN.md §11 (QA-001)."""

from __future__ import annotations

import io
import json
import hashlib
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFont, features
import arabic_reshaper
import pypdfium2 as pdfium
from reportlab.lib.pagesizes import A4, letter
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
import docx
from pptx import Presentation

from openlargeprint.security.isolation import log_safe_info


class BenchmarkCorpusBuilder:
    """Builds a complete, rights-safe synthetic benchmark corpus on demand."""

    #: Text of the Arabic fixture page, in reading order. Used as its reference
    #: transcript so Arabic recognition error rates are measured, not assumed.
    _ARABIC_PAGE_LINES = (
        "عقد بيع ابتدائي وتنازل",
        "تم الاتفاق بين الطرفين على البنود والشروط المذكورة أدناه.",
    )

    def __init__(self, output_dir: Path | str):
        self.output_dir = Path(output_dir).resolve()
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def build_all(self) -> Dict[str, Path]:
        """Generate all 16 benchmark test cases and return a dictionary of their paths."""
        cases = {
            "born_digital_english": self.build_born_digital_english(),
            "two_column_law": self.build_two_column_law(),
            "legal_footnotes": self.build_legal_footnotes(),
            "scanned_english": self.build_scanned_english(),
            "arabic_scan": self.build_arabic_scan(),
            "mixed_bidi": self.build_mixed_bidi(),
            "scanned_table": self.build_scanned_table(),
            "images_captions": self.build_images_captions(),
            "rotated_page": self.build_rotated_page(),
            "skewed_page": self.build_skewed_page(),
            "low_res_scan": self.build_low_res_scan(),
            "mixed_digital_scan": self.build_mixed_digital_scan(),
            "page_numbering": self.build_page_numbering(),
            "malformed_pdf": self.build_malformed_pdf(),
            "docx_sample": self.build_docx_sample(),
            "pptx_sample": self.build_pptx_sample(),
        }
        for name, path in cases.items():
            if name == "malformed_pdf":
                continue
            lines = REFERENCE_LINES[name]
            self._write_ground_truth(path, "\n".join(lines))
            reference = {
                "reading_order": lines,
                "source_pages": list(range(1, int(CASE_EXPECTATIONS[name].get("page_count", 1)) + 1)),
                "tables": REFERENCE_TABLES.get(name, []),
                "image_count": 2 if name == "images_captions" else 0,
                "image_pixel_hashes": self._figure_hashes() if name == "images_captions" else [],
                "license": "Project-authored synthetic fixture; GPL-3.0-or-later",
            }
            path.with_suffix(".reference.json").write_text(json.dumps(reference, ensure_ascii=False, indent=2), encoding="utf-8")
        log_safe_info(f"Generated {len(cases)} benchmark documents in {self.output_dir}")
        return cases

    def build_born_digital_english(self) -> Path:
        """Case 1: Born-digital English PDF (tests exact text preservation, 0% CER)."""
        out_path = self.output_dir / "01_born_digital_english.pdf"
        c = canvas.Canvas(str(out_path), pagesize=A4)
        c.setFont("Helvetica-Bold", 16)
        c.drawString(72, 750, "Contract Law Restatement")
        c.setFont("Helvetica", 11)
        c.drawString(72, 720, "An agreement requires mutual assent and valid consideration to be legally binding.")
        c.drawString(72, 700, "Performance may be excused only upon impossibility, impracticability, or frustration.")
        c.showPage()
        c.save()
        self._write_ground_truth(out_path, "\n".join([
            "Contract Law Restatement",
            "An agreement requires mutual assent and valid consideration to be legally binding.",
            "Performance may be excused only upon impossibility, impracticability, or frustration.",
        ]))
        return out_path

    def build_two_column_law(self) -> Path:
        """Case 2: Two-column law page (tests reading order flow)."""
        out_path = self.output_dir / "02_two_column_law.pdf"
        c = canvas.Canvas(str(out_path), pagesize=letter)
        c.setFont("Helvetica", 10)
        for x, lines in ((50, REFERENCE_LINES["two_column_law"][:2]), (320, REFERENCE_LINES["two_column_law"][2:])):
            for y, line in zip((700, 660), lines):
                assert c.stringWidth(line, "Helvetica", 10) < 250
                c.drawString(x, y, line)
        c.showPage()
        c.save()
        self._write_ground_truth(out_path, "\n".join(REFERENCE_LINES["two_column_law"]))
        return out_path

    def build_legal_footnotes(self) -> Path:
        """Case 3: Legal footnotes (tests body vs footnote separation)."""
        out_path = self.output_dir / "03_legal_footnotes.pdf"
        c = canvas.Canvas(str(out_path), pagesize=A4)
        c.setFont("Helvetica", 11)
        c.drawString(72, 750, "The doctrine of promissory estoppel prevents injustice when a promise is relied upon.[1]")
        # Footnote separator line
        c.line(72, 120, 200, 120)
        c.setFont("Helvetica", 8)
        c.drawString(72, 100, "[1] Restatement (Second) of Contracts § 90.")
        c.showPage()
        c.save()
        return out_path

    def _write_ground_truth(self, pdf_path: Path, text: str) -> Path:
        """Write a rights-safe ground-truth .txt sidecar for a synthetic scanned page (QA-002)."""
        gt_path = pdf_path.with_suffix(".txt")
        gt_path.write_text(text, encoding="utf-8")
        gt_dir = self.output_dir / "ocr_ground_truth"
        gt_dir.mkdir(parents=True, exist_ok=True)
        (gt_dir / f"{pdf_path.stem}.txt").write_text(text, encoding="utf-8")
        return gt_path

    def _save_image_as_pdf(self, img: Image.Image, out_pdf_path: Path, pagesize=A4) -> Path:
        """Helper to render PIL image into a pure raster PDF page using ReportLab."""
        temp_img = out_pdf_path.with_suffix(".png")
        img.save(temp_img, format="PNG")
        c = canvas.Canvas(str(out_pdf_path), pagesize=pagesize)
        c.drawImage(str(temp_img), 0, 0, width=pagesize[0], height=pagesize[1])
        c.showPage()
        c.save()
        if temp_img.exists():
            temp_img.unlink()
        return out_pdf_path

    def build_scanned_english(self) -> Path:
        """Case 4: Scanned English page (tests baseline OCR)."""
        out_path = self.output_dir / "04_scanned_english.pdf"
        lines = [
            "IN THE COURT OF APPEALS",
            "This appeal concerns the interpretation of indemnity clauses.",
            "We affirm the judgment of the district court.",
        ]
        img = Image.new("RGB", (800, 1100), color=(250, 250, 248))
        draw = ImageDraw.Draw(img)
        draw.text((60, 80), lines[0], fill=(20, 20, 20))
        draw.text((60, 130), lines[1], fill=(30, 30, 30))
        draw.text((60, 170), lines[2], fill=(30, 30, 30))
        out_path = self._save_image_as_pdf(img, out_path)
        self._write_ground_truth(out_path, "\n".join(lines))
        return out_path

    def arabic_font(self, size: int) -> ImageFont.FreeTypeFont:
        """Load the bundled Arabic face, or fail instead of drawing boxes (QA-002, OCR-003).

        PIL's default bitmap font has no Arabic glyph coverage: drawing Arabic with
        it produces replacement boxes, which turns the Arabic fixture into a page of
        noise and makes every Arabic measurement meaningless.
        """
        relative = Path("ui") / "public" / "fonts" / "NotoSansArabic.ttf"
        here = Path(__file__).resolve()
        for parent in (here, *here.parents):
            candidate = parent / relative
            if candidate.exists():
                return ImageFont.truetype(str(candidate), size)
        raise FileNotFoundError(
            "The bundled Arabic font is missing, so the Arabic benchmark page cannot be "
            "rendered with real Arabic text."
        )

    @staticmethod
    def _arabic_display(text: str) -> str:
        # Reference transcripts keep logical Unicode; only fixture painting shapes.
        return text if features.check_feature("raqm") else arabic_reshaper.reshape(text)[::-1]

    def render_arabic_page(self) -> Image.Image:
        """Draw the Arabic benchmark page (LANG-002, OCR-003)."""
        img = Image.new("RGB", (1100, 1400), color=(252, 250, 246))
        draw = ImageDraw.Draw(img)
        title, body = self._ARABIC_PAGE_LINES
        draw.text((300, 100), self._arabic_display(title), fill=(10, 10, 10), font=self.arabic_font(34))
        draw.text((60, 170), self._arabic_display(body), fill=(20, 20, 20), font=self.arabic_font(28))
        return img

    def build_arabic_scan(self) -> Path:
        """Case 5: Arabic scan (tests RTL OCR, Arabic recognition and reading order)."""
        out_path = self.output_dir / "05_arabic_scan.pdf"
        self._write_ground_truth(out_path, "\n".join(self._ARABIC_PAGE_LINES))
        return self._save_image_as_pdf(self.render_arabic_page(), out_path)

    def build_mixed_bidi(self) -> Path:
        """Case 6: Mixed Arabic/English (tests bidi layout)."""
        out_path = self.output_dir / "06_mixed_bidi.pdf"
        lines = REFERENCE_LINES["mixed_bidi"]
        img = Image.new("RGB", (1100, 1400), color=(252, 250, 246))
        draw = ImageDraw.Draw(img)
        draw.text((70, 90), lines[0], font=ImageFont.load_default(size=30), fill=(20, 20, 20))
        # Pillow's RAQM text engine shapes and orders Arabic when available.
        arabic_clause, english_clause = lines[1].split(" Civil Code")
        draw.text((70, 160), "Civil Code" + english_clause, font=ImageFont.load_default(size=30), fill=(20, 20, 20))
        draw.text((600, 160), self._arabic_display(arabic_clause), font=self.arabic_font(30), fill=(20, 20, 20))
        draw.text((70, 230), self._arabic_display(lines[2]), font=self.arabic_font(30), fill=(20, 20, 20))
        self._write_ground_truth(out_path, "\n".join(lines))
        return self._save_image_as_pdf(img, out_path)

    def build_scanned_table(self) -> Path:
        """Case 7: Scanned table (tests structure reconstruction)."""
        out_path = self.output_dir / "07_scanned_table.pdf"
        gt_lines = [
            "Schedule of Deliverables",
            "Milestone Due Date Status",
            "Initial Draft 30 Days Completed",
        ]
        img = Image.new("RGB", (900, 1200), color=(255, 255, 255))
        draw = ImageDraw.Draw(img)
        draw.text((80, 80), "Schedule of Deliverables", fill=(0, 0, 0))
        # Draw table grid lines
        draw.rectangle([80, 120, 820, 270], outline=(0, 0, 0), width=2)
        draw.line([80, 180, 820, 180], fill=(0, 0, 0), width=2)
        draw.line([300, 120, 300, 270], fill=(0, 0, 0), width=1)
        draw.line([560, 120, 560, 270], fill=(0, 0, 0), width=1)
        # Header text
        draw.text((90, 140), "Milestone", fill=(0, 0, 0))
        draw.text((320, 140), "Due Date", fill=(0, 0, 0))
        draw.text((580, 140), "Status", fill=(0, 0, 0))
        # Row 1
        draw.text((90, 210), "Initial Draft", fill=(0, 0, 0))
        draw.text((320, 210), "30 Days", fill=(0, 0, 0))
        draw.text((580, 210), "Completed", fill=(0, 0, 0))
        out_path = self._save_image_as_pdf(img, out_path)
        self._write_ground_truth(out_path, "\n".join(gt_lines))
        return out_path

    def build_images_captions(self) -> Path:
        """Case 8: Images + captions (tests asset association)."""
        out_path = self.output_dir / "08_images_captions.pdf"
        c = canvas.Canvas(str(out_path), pagesize=A4)
        c.drawString(72, 750, "Patent Exhibit A")
        for index, image in enumerate(self._figure_images()):
            c.drawImage(ImageReader(image), 100 + index * 220, 530, width=190, height=150)
        c.drawString(72, 490, REFERENCE_LINES["images_captions"][1])
        c.drawString(72, 465, REFERENCE_LINES["images_captions"][2])
        c.showPage()
        c.save()
        self._write_ground_truth(out_path, "\n".join(REFERENCE_LINES["images_captions"]))
        return out_path

    @staticmethod
    def _figure_images():
        images = []
        for color in ((160, 40, 30), (30, 100, 60)):
            img = Image.new("RGB", (240, 180), (249, 246, 238))
            draw = ImageDraw.Draw(img)
            draw.rectangle((25, 25, 215, 155), outline=color, width=8)
            draw.line((30, 150, 210, 30), fill=color, width=6)
            images.append(img)
        return images

    @classmethod
    def _figure_hashes(cls):
        from .metrics import image_pixel_digest
        return [image_pixel_digest(image) for image in cls._figure_images()]

    def build_rotated_page(self) -> Path:
        """Case 9: A nonempty scanned page with explicit PDF orientation."""
        out_path = self.output_dir / "09_rotated_page.pdf"
        img = Image.new("RGB", (1000, 700), (250, 250, 248))
        draw = ImageDraw.Draw(img)
        draw.text((80, 100), REFERENCE_LINES["rotated_page"][0], font=ImageFont.load_default(size=32), fill=(20, 20, 20))
        self._save_image_as_pdf(img, out_path, pagesize=(842, 595))
        rotated = out_path.with_suffix(".rotated.pdf")
        with pdfium.PdfDocument(out_path) as pdf:
            page = pdf[0]
            page.set_rotation(90)
            page.close()
            pdf.save(str(rotated))
        rotated.replace(out_path)
        self._write_ground_truth(out_path, REFERENCE_LINES["rotated_page"][0])
        return out_path

    def build_skewed_page(self) -> Path:
        """Case 10: Skewed page (tests deskew/preprocessing)."""
        out_path = self.output_dir / "10_skewed_page.pdf"
        gt_text = "Affidavit of Execution"
        img = Image.new("RGB", (700, 900), color=(255, 255, 255))
        draw = ImageDraw.Draw(img)
        draw.text((100, 100), gt_text, fill=(0, 0, 0))
        # Rotate image slightly to simulate skew
        skewed = img.rotate(3.5, resample=Image.BICUBIC, fillcolor=(255, 255, 255))
        out_path = self._save_image_as_pdf(skewed, out_path)
        self._write_ground_truth(out_path, gt_text)
        return out_path

    def build_low_res_scan(self) -> Path:
        """Case 11: Poor low-resolution scan (tests difficult OCR)."""
        out_path = self.output_dir / "11_low_res_scan.pdf"
        gt_text = "Low Resolution Scan"
        img = Image.new("RGB", (300, 400), color=(240, 240, 240))
        draw = ImageDraw.Draw(img)
        draw.text((20, 30), gt_text, fill=(50, 50, 50))
        out_path = self._save_image_as_pdf(img, out_path)
        self._write_ground_truth(out_path, gt_text)
        return out_path

    def build_mixed_digital_scan(self) -> Path:
        """Case 12: Mixed digital/scan PDF (tests selective OCR)."""
        out_path = self.output_dir / "12_mixed_digital_scan.pdf"
        # Page 1: digital
        c = canvas.Canvas(str(out_path), pagesize=A4)
        c.drawString(72, 750, "Page 1: Digital cover page with exact searchable text.")
        c.showPage()
        # Page 2 has no native text; selective OCR must recognize its raster.
        img = Image.new("RGB", (1000, 1400), (250, 250, 248))
        draw = ImageDraw.Draw(img)
        draw.text((70, 100), REFERENCE_LINES["mixed_digital_scan"][1], font=ImageFont.load_default(size=28), fill=(20, 20, 20))
        c.drawImage(ImageReader(img), 0, 0, width=A4[0], height=A4[1])
        c.showPage()
        c.save()
        self._write_ground_truth(out_path, "\n".join(REFERENCE_LINES["mixed_digital_scan"]))
        return out_path

    def build_page_numbering(self) -> Path:
        """Case 13: Roman + Arabic page numbering."""
        out_path = self.output_dir / "13_page_numbering.pdf"
        c = canvas.Canvas(str(out_path), pagesize=A4)
        c.drawString(72, 750, "Preface")
        c.drawString(290, 50, "iii")
        c.showPage()
        c.drawString(72, 750, "Chapter 1: Principles")
        c.drawString(290, 50, "1")
        c.showPage()
        c.save()
        return out_path

    def build_malformed_pdf(self) -> Path:
        """Case 14: Huge/malformed PDF (resource/security handling)."""
        out_path = self.output_dir / "14_malformed_pdf.pdf"
        # Write valid %PDF header followed by corrupt garbage bytes
        with open(out_path, "wb") as f:
            f.write(b"%PDF-1.7\n%malformed data\n<< /Type /Catalog /Pages 2 0 R >>\nxref\n0 2\ntrailer << >>\n%%EOF")
        return out_path

    def build_docx_sample(self) -> Path:
        """Case 15: DOCX (style/footnote/image import)."""
        out_path = self.output_dir / "15_docx_sample.docx"
        doc = docx.Document()
        doc.add_heading("Legal Brief", level=1)
        doc.add_paragraph("The doctrine of res judicata bars re-litigation of the claim.")
        table = doc.add_table(rows=2, cols=2)
        table.cell(0, 0).text = "Party"
        table.cell(0, 1).text = "Role"
        table.cell(1, 0).text = "Petitioner"
        table.cell(1, 1).text = "Appellant"
        doc.save(str(out_path))
        return out_path

    def build_pptx_sample(self) -> Path:
        """Case 16: PPTX (text box/image order)."""
        out_path = self.output_dir / "16_pptx_sample.pptx"
        prs = Presentation()
        # Slide 1
        slide_layout = prs.slide_layouts[0]
        slide = prs.slides.add_slide(slide_layout)
        title = slide.shapes.title
        subtitle = slide.placeholders[1]
        title.text = "Corporate Governance Presentation"
        subtitle.text = "Board duties and stakeholder responsibilities"
        # Speaker notes
        notes = slide.notes_slide.notes_text_frame
        notes.text = "Opening slide remarks for the board."
        prs.save(str(out_path))
        return out_path

#: Expected structural properties per corpus case (QA-001). Keys must match build_all().
#: Values are derived from what each fixture actually draws, so a mismatch means the
#: pipeline lost text, pages, a table, or an image rather than that a number drifted.
#: Scanned fixtures carry no drawn text: their recognition quality is measured through
#: CER/WER against a reference transcript, not through keyword presence.
CASE_EXPECTATIONS: Dict[str, Dict[str, object]] = {
    "born_digital_english": {"page_count": 1, "keywords": ["mutual assent", "consideration"]},
    "two_column_law": {"page_count": 1, "keywords": ["plaintiff", "jurisdiction"]},
    "legal_footnotes": {"page_count": 1, "keywords": ["promissory estoppel"]},
    "mixed_bidi": {"page_count": 1},
    "images_captions": {"page_count": 1, "keywords": ["Patent Exhibit A"], "has_images": True},
    "mixed_digital_scan": {"page_count": 2, "keywords": ["Digital cover page"]},
    "page_numbering": {"page_count": 2, "keywords": ["Preface"]},
    "scanned_table": {"has_table": True},
    "malformed_pdf": {"expects_rejection": True},
    "scanned_english": {"page_count": 1},
    "arabic_scan": {"page_count": 1},
    "rotated_page": {"page_count": 1},
    "skewed_page": {"page_count": 1},
    "low_res_scan": {"page_count": 1},
    "docx_sample": {"page_count": 1},
    "pptx_sample": {"page_count": 1},
}


# Independent authored references, never derived from the pipeline output.
REFERENCE_LINES = {
    "born_digital_english": ["Contract Law Restatement", "An agreement requires mutual assent and valid consideration to be legally binding.", "Performance may be excused only upon impossibility, impracticability, or frustration."],
    "two_column_law": ["The plaintiff filed an action for breach.", "Notice was served under Rule 4.", "The defendant moved to dismiss.", "The court upheld jurisdiction."],
    "legal_footnotes": ["The doctrine of promissory estoppel prevents injustice when a promise is relied upon.[1]", "[1] Restatement (Second) of Contracts § 90."],
    "scanned_english": ["IN THE COURT OF APPEALS", "This appeal concerns the interpretation of indemnity clauses.", "We affirm the judgment of the district court."],
    "arabic_scan": list(BenchmarkCorpusBuilder._ARABIC_PAGE_LINES),
    "mixed_bidi": ["Bilingual Agreement", "البند 1: القانون المدني Civil Code No 131", "تم الاتفاق بين الطرفين على شروط العقد."],
    "scanned_table": ["Schedule of Deliverables", "Milestone Due Date Status", "Initial Draft 30 Days Completed"],
    "images_captions": ["Patent Exhibit A", "Figure 1. Hydraulic brake assembly.", "Figure 2. Valve assembly."],
    "rotated_page": ["Rotated affidavit of execution"],
    "skewed_page": ["Affidavit of Execution"],
    "low_res_scan": ["Low Resolution Scan"],
    "mixed_digital_scan": ["Page 1: Digital cover page with exact searchable text.", "Page 2: Scanned witness statement."],
    "page_numbering": ["Preface", "iii", "Chapter 1: Principles", "1"],
    "docx_sample": ["Legal Brief", "The doctrine of res judicata bars re-litigation of the claim.", "Party Role", "Petitioner Appellant"],
    "pptx_sample": ["Corporate Governance Presentation", "Board duties and stakeholder responsibilities", "Opening slide remarks for the board."],
}
REFERENCE_TABLES = {
    "scanned_table": [[["Milestone", "Due Date", "Status"], ["Initial Draft", "30 Days", "Completed"]]],
    "docx_sample": [[["Party", "Role"], ["Petitioner", "Appellant"]]],
}
