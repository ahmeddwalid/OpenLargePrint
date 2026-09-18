"""Rights-safe synthetic benchmark corpus builder covering all 16 cases from DESIGN.md §11 (QA-001)."""

from __future__ import annotations

import io
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFont
import pypdfium2 as pdfium
from reportlab.lib.pagesizes import A4, letter
from reportlab.pdfgen import canvas
import docx
from pptx import Presentation

from openlargeprint.security.isolation import log_safe_info


class BenchmarkCorpusBuilder:
    """Builds a complete, rights-safe synthetic benchmark corpus on demand."""

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
        return out_path

    def build_two_column_law(self) -> Path:
        """Case 2: Two-column law page (tests reading order flow)."""
        out_path = self.output_dir / "02_two_column_law.pdf"
        c = canvas.Canvas(str(out_path), pagesize=letter)
        # Left column
        c.setFont("Helvetica", 10)
        c.drawString(50, 700, "Left column paragraph 1: The plaintiff filed an action for breach.")
        c.drawString(50, 680, "Left column paragraph 2: Notice was served in accordance with Rule 4.")
        # Right column
        c.drawString(320, 700, "Right column paragraph 1: The defendant filed a motion to dismiss.")
        c.drawString(320, 680, "Right column paragraph 2: The court held that jurisdiction was proper.")
        c.showPage()
        c.save()
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
        img = Image.new("RGB", (800, 1100), color=(250, 250, 248))
        draw = ImageDraw.Draw(img)
        draw.text((60, 80), "IN THE COURT OF APPEALS", fill=(20, 20, 20))
        draw.text((60, 130), "This appeal concerns the interpretation of indemnity clauses.", fill=(30, 30, 30))
        draw.text((60, 170), "We affirm the judgment of the district court.", fill=(30, 30, 30))
        return self._save_image_as_pdf(img, out_path)

    def build_arabic_scan(self) -> Path:
        """Case 5: Arabic scan (tests RTL OCR)."""
        out_path = self.output_dir / "05_arabic_scan.pdf"
        img = Image.new("RGB", (800, 1100), color=(252, 250, 246))
        draw = ImageDraw.Draw(img)
        draw.text((300, 100), "عقد بيع ابتدائي وتنازل", fill=(10, 10, 10))
        draw.text((200, 160), "تم الاتفاق بين الطرفين على البنود والشروط المذكورة أدناه.", fill=(20, 20, 20))
        return self._save_image_as_pdf(img, out_path)

    def build_mixed_bidi(self) -> Path:
        """Case 6: Mixed Arabic/English (tests bidi layout)."""
        out_path = self.output_dir / "06_mixed_bidi.pdf"
        c = canvas.Canvas(str(out_path), pagesize=A4)
        c.setFont("Helvetica", 11)
        c.drawString(72, 750, "Bilingual Agreement / Arabic Clause")
        c.drawString(72, 720, "Clause 1: The governing law is Civil Code No 131.")
        c.showPage()
        c.save()
        return out_path

    def build_scanned_table(self) -> Path:
        """Case 7: Scanned table (tests structure reconstruction)."""
        out_path = self.output_dir / "07_scanned_table.pdf"
        img = Image.new("RGB", (900, 1200), color=(255, 255, 255))
        draw = ImageDraw.Draw(img)
        draw.text((80, 80), "Schedule of Deliverables", fill=(0, 0, 0))
        # Draw table grid lines
        draw.rectangle([80, 120, 820, 360], outline=(0, 0, 0), width=2)
        draw.line([80, 180, 820, 180], fill=(0, 0, 0), width=2)
        draw.line([80, 270, 820, 270], fill=(0, 0, 0), width=1)
        draw.line([300, 120, 300, 360], fill=(0, 0, 0), width=1)
        draw.line([560, 120, 560, 360], fill=(0, 0, 0), width=1)
        # Header text
        draw.text((90, 140), "Milestone", fill=(0, 0, 0))
        draw.text((320, 140), "Due Date", fill=(0, 0, 0))
        draw.text((580, 140), "Status", fill=(0, 0, 0))
        # Row 1
        draw.text((90, 210), "Initial Draft", fill=(0, 0, 0))
        draw.text((320, 210), "30 Days", fill=(0, 0, 0))
        draw.text((580, 210), "Completed", fill=(0, 0, 0))
        return self._save_image_as_pdf(img, out_path)

    def build_images_captions(self) -> Path:
        """Case 8: Images + captions (tests asset association)."""
        out_path = self.output_dir / "08_images_captions.pdf"
        c = canvas.Canvas(str(out_path), pagesize=A4)
        c.drawString(72, 750, "Patent Exhibit A")
        # Draw a synthetic graphic diagram
        c.rect(100, 500, 300, 200, fill=0, stroke=1)
        c.line(100, 500, 400, 700)
        c.drawString(100, 475, "Figure 1. Schematic diagram of the hydraulic brake assembly.")
        c.showPage()
        c.save()
        return out_path

    def build_rotated_page(self) -> Path:
        """Case 9: Rotated page (tests orientation handling)."""
        out_path = self.output_dir / "09_rotated_page.pdf"
        pdf = pdfium.PdfDocument.new()
        p = pdf.new_page(842, 595)
        p.set_rotation(90)
        p.close()
        pdf.save(str(out_path))
        pdf.close()
        return out_path

    def build_skewed_page(self) -> Path:
        """Case 10: Skewed page (tests deskew/preprocessing)."""
        out_path = self.output_dir / "10_skewed_page.pdf"
        img = Image.new("RGB", (700, 900), color=(255, 255, 255))
        draw = ImageDraw.Draw(img)
        draw.text((100, 100), "Affidavit of Execution", fill=(0, 0, 0))
        # Rotate image slightly to simulate skew
        skewed = img.rotate(3.5, resample=Image.BICUBIC, fillcolor=(255, 255, 255))
        return self._save_image_as_pdf(skewed, out_path)

    def build_low_res_scan(self) -> Path:
        """Case 11: Poor low-resolution scan (tests difficult OCR)."""
        out_path = self.output_dir / "11_low_res_scan.pdf"
        img = Image.new("RGB", (300, 400), color=(240, 240, 240))
        draw = ImageDraw.Draw(img)
        draw.text((20, 30), "Low Resolution Scan", fill=(50, 50, 50))
        return self._save_image_as_pdf(img, out_path)

    def build_mixed_digital_scan(self) -> Path:
        """Case 12: Mixed digital/scan PDF (tests selective OCR)."""
        out_path = self.output_dir / "12_mixed_digital_scan.pdf"
        # Page 1: digital
        c = canvas.Canvas(str(out_path), pagesize=A4)
        c.drawString(72, 750, "Page 1: Digital cover page with exact searchable text.")
        c.showPage()
        # Page 2: digital with image
        c.drawString(72, 750, "Page 2: Second section.")
        c.showPage()
        c.save()
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
