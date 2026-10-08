"""Full-book engine verification; GUI/SAC acceptance remains a separate gate.

Records content-free metrics and produces both large-print sizes from one IR.
Run: .venv/Scripts/python.exe packaging/verify_test_documents.py
"""
from __future__ import annotations
import json
import time
from pathlib import Path
import pypdfium2 as pdfium
from openlargeprint.exporters import ExportOptions, PdfExporter, PaperSize, PresetName
from openlargeprint.ir.models import BlockType
from openlargeprint.pipeline import PipelineOrchestrator
from openlargeprint.qa.benchmark import get_current_ram_mb
from openlargeprint.security import JobAssetStore


def main():
    root = Path(__file__).resolve().parents[1]
    output = root / "packaging/verification/books"
    output.mkdir(parents=True, exist_ok=True)
    records = []
    for index, source in enumerate(sorted((root / "test-documents").glob("*.pdf")), 1):
        started = time.monotonic()
        last = [0.0]
        def progress(page, total, stage, message):
            if page == total or time.monotonic() - last[0] > 30:
                print(json.dumps({"case": index, "page": page, "total": total,
                    "stage": stage, "elapsed_seconds": round(time.monotonic() - started, 1)}), flush=True)
                last[0] = time.monotonic()
        record = {"input": source.name, "gui_acceptance": "not measured",
            "cer": None, "wer": None, "reading_order_ground_truth": None,
            "table_ground_truth": None, "image_retention_ground_truth": None,
            "peak_vram_mb": None, "child_process_peak_ram_mb": None}
        try:
            with pdfium.PdfDocument(source) as original:
                expected = len(original)
            result = PipelineOrchestrator().convert(source, output / f"book-{index}-20pt.pdf",
                ExportOptions(preset=PresetName.LARGE), export_format="pdf", progress_callback=progress,
                asset_store=JobAssetStore(job_id=f"full-book-{index}"))
            ir = result.document_ir
            anchors = [b.source_page for b in ir.blocks if b.type == BlockType.PAGE_MARKER]
            record.update({"source_pages": expected, "processed_pages": len(ir.pages),
                "page_anchor_fidelity": len(set(anchors) & set(range(1, expected + 1))) / expected,
                "retained_images": sum(b.image_asset is not None for b in ir.blocks),
                "tables": sum(b.type == BlockType.TABLE for b in ir.blocks),
                "flagged_blocks": sum(bool(b.warnings) for b in ir.blocks),
                "extract_and_export_seconds": round(time.monotonic() - started, 2)})
            assert len(ir.pages) == expected and set(anchors) == set(range(1, expected + 1))
            PdfExporter().export(ir, output / f"book-{index}-28pt.pdf", ExportOptions(preset=PresetName.VERY_LARGE))
            # Restyling and selection use the same IR, without another parse or OCR.
            PdfExporter().export(ir.slice_by_source_pages(1, min(4, expected)),
                output / f"book-{index}-selected-A3.pdf", ExportOptions(preset=PresetName.VERY_LARGE, paper_size=PaperSize.A3))
            for suffix, dimensions in (("20pt", (595.276, 841.890)), ("28pt", (595.276, 841.890)),
                                       ("selected-A3", (841.890, 1190.551))):
                with pdfium.PdfDocument(output / f"book-{index}-{suffix}.pdf") as exported:
                    assert len(exported) > 0
                    for page in exported:
                        try:
                            assert all(abs(a - b) < 1 for a, b in zip(page.get_size(), dimensions))
                        finally:
                            page.close()
                    record[f"output_pages_{suffix}"] = len(exported)
            record["complete"] = True
        except Exception as error:
            record.update({"complete": False, "error_type": type(error).__name__})
        record.update({"elapsed_seconds": round(time.monotonic() - started, 2),
                       "process_lifetime_peak_ram_mb": round(get_current_ram_mb(), 1)})
        records.append(record)
        (output / "results.json").write_text(json.dumps(records, indent=2), encoding="utf-8")
        print(json.dumps(record), flush=True)
    raise SystemExit(1 if len(records) != 8 or any(not r["complete"] for r in records) else 0)


if __name__ == "__main__":
    main()
