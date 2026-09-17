"""End-to-end document conversion orchestrator with multi-format export and selective slicing (DOC-001, OUT-001..010)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Literal, Optional, Tuple

from openlargeprint.exporters import (
    DocxExporter,
    ExportOptions,
    PdfExporter,
    ReaderExporter,
)
from openlargeprint.importers.pdf.native import NativePdfImporter
from openlargeprint.ir.models import DocumentIR
from openlargeprint.ir.validator import validate_document_ir
from openlargeprint.ocr.router import RoutingMode
from openlargeprint.security import JobWorkspace, detect_file_type, log_safe_info

ExportFormat = Literal["docx", "pdf", "reader"]


@dataclass
class ConversionResult:
    """Result of an end-to-end conversion job."""
    input_path: Path
    output_path: Path
    document_ir: DocumentIR
    format: ExportFormat
    warnings: List[str] = field(default_factory=list)
    success: bool = True


class PipelineOrchestrator:
    """Coordinates the document reconstruction pipeline across all input and output formats."""

    def __init__(self, routing_mode: RoutingMode = RoutingMode.AUTOMATIC):
        self.routing_mode = routing_mode
        self.pdf_importer = NativePdfImporter(routing_mode=routing_mode)
        self.docx_exporter = DocxExporter()
        self.pdf_exporter = PdfExporter()
        self.reader_exporter = ReaderExporter()

    def convert(
        self,
        input_path: Path | str,
        output_path: Path | str,
        options: Optional[ExportOptions] = None,
        export_format: Optional[ExportFormat] = None,
        page_range: Optional[Tuple[int, int]] = None,
    ) -> ConversionResult:
        """Execute full conversion pipeline into target format (DOCX, Large PDF, or HTML Reader)."""
        input_file = Path(input_path).resolve()
        output_file = Path(output_path).resolve()

        if options is None:
            options = ExportOptions()

        # 1. Deduce output format from extension or argument
        if export_format is None:
            ext = output_file.suffix.lower()
            if ext == ".pdf":
                export_format = "pdf"
            elif ext in (".html", ".htm"):
                export_format = "reader"
            else:
                export_format = "docx"

        # 2. Content-based type validation (SEC-001)
        format_type = detect_file_type(input_file)
        if format_type != "pdf":
            raise ValueError(f"Unsupported file format for this pipeline: {format_type}")

        all_warnings: List[str] = []

        # 3. Run in isolated disposable workspace (SEC-004)
        with JobWorkspace() as ws:
            log_safe_info(f"Starting conversion in isolated workspace: {ws.path.name}")

            # 4. Import document into canonical DocumentIR (native, OCR, or mixed)
            doc_ir = self.pdf_importer.import_document(input_file, ws)

            # 5. Validate canonical DocumentIR (DOC-003, DESIGN.md §3)
            ir_warnings = validate_document_ir(doc_ir)
            all_warnings.extend(ir_warnings)

            # 6. Apply selective page slicing if requested (OUT-010)
            if page_range is not None:
                start_p, end_p = page_range
                log_safe_info(f"Applying selective page slicing for pages {start_p} to {end_p}")
                doc_ir = doc_ir.slice_by_source_pages(start_p, end_p)

            # 7. Export to requested format (DOCX, Large-Print PDF, or Reader HTML)
            if export_format == "pdf":
                self.pdf_exporter.export(doc_ir, output_file, options)
            elif export_format == "reader":
                self.reader_exporter.export(doc_ir, output_file, options)
            else:
                self.docx_exporter.export(doc_ir, output_file, options)

        log_safe_info(f"Conversion to {export_format.upper()} finished successfully: {output_file.name}")
        return ConversionResult(
            input_path=input_file,
            output_path=output_file,
            document_ir=doc_ir,
            format=export_format,
            warnings=all_warnings,
            success=True,
        )

    def inspect(self, input_path: Path | str) -> DocumentIR:
        """Inspect and classify a document into DocumentIR without exporting."""
        input_file = Path(input_path).resolve()
        format_type = detect_file_type(input_file)
        if format_type != "pdf":
            raise ValueError(f"Unsupported file format for inspection: {format_type}")

        with JobWorkspace() as ws:
            doc_ir = self.pdf_importer.import_document(input_file, ws)
            return doc_ir
