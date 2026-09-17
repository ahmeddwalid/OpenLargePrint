"""End-to-end document conversion orchestrator with OCR routing (DOC-001, OCR-001, SEC-004)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from openlargeprint.exporters import DocxExporter, ExportOptions
from openlargeprint.importers.pdf.native import NativePdfImporter
from openlargeprint.ir.models import DocumentIR
from openlargeprint.ir.validator import validate_document_ir
from openlargeprint.ocr.router import RoutingMode
from openlargeprint.security import JobWorkspace, detect_file_type, log_safe_info


@dataclass
class ConversionResult:
    """Result of an end-to-end conversion job."""
    input_path: Path
    output_path: Path
    document_ir: DocumentIR
    warnings: List[str] = field(default_factory=list)
    success: bool = True


class PipelineOrchestrator:
    """Coordinates the full document reconstruction pipeline."""

    def __init__(self, routing_mode: RoutingMode = RoutingMode.AUTOMATIC):
        self.routing_mode = routing_mode
        self.pdf_importer = NativePdfImporter(routing_mode=routing_mode)
        self.docx_exporter = DocxExporter()

    def convert(
        self,
        input_path: Path | str,
        output_path: Path | str,
        options: Optional[ExportOptions] = None,
    ) -> ConversionResult:
        """Execute full conversion pipeline in an isolated disposable workspace (SEC-004)."""
        input_file = Path(input_path).resolve()
        output_file = Path(output_path).resolve()

        if options is None:
            options = ExportOptions()

        # 1. Content-based type validation (SEC-001)
        format_type = detect_file_type(input_file)
        if format_type != "pdf":
            raise ValueError(f"Unsupported file format for this pipeline: {format_type}")

        all_warnings: List[str] = []

        # 2. Run in isolated disposable workspace (SEC-004)
        with JobWorkspace() as ws:
            log_safe_info(f"Starting conversion in isolated workspace: {ws.path.name}")

            # 3. Import document into canonical DocumentIR (native or OCR)
            doc_ir = self.pdf_importer.import_document(input_file, ws)

            # 4. Validate canonical DocumentIR (DOC-003, DESIGN.md §3)
            ir_warnings = validate_document_ir(doc_ir)
            all_warnings.extend(ir_warnings)

            # 5. Export to large-print DOCX using the unmodified DocxExporter (OUT-001)
            self.docx_exporter.export(doc_ir, output_file, options)

        log_safe_info("Conversion finished successfully")
        return ConversionResult(
            input_path=input_file,
            output_path=output_file,
            document_ir=doc_ir,
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
