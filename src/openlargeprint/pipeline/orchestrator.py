"""End-to-end document conversion orchestrator with multi-format export and selective slicing (DOC-001, OUT-001..010)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re
from openlargeprint.security.isolation import atomic_output
from typing import List, Literal, Optional, Set, Tuple, Union

from openlargeprint.exporters import (
    DocxExporter,
    ExportOptions,
    PdfExporter,
    ReaderExporter,
    SearchablePdfExporter,
)
from openlargeprint.importers.base import CancelCheck, CheckpointCallback, ProgressCallback
from openlargeprint.importers.office import (
    DocxImporter,
    LibreOfficeBridge,
    PptxImporter,
)
from openlargeprint.importers.pdf.native import NativePdfImporter
from openlargeprint.ir.models import (
    DocumentIR,
    DocumentMetadata,
    PageClassification,
    PageMetadata,
)
from openlargeprint.ir.validator import validate_document_ir
from openlargeprint.ocr.router import RoutingMode
from openlargeprint.security import (
    JobAssetStore,
    JobWorkspace,
    detect_file_type,
    log_safe_info,
    sanitize_document,
)

ExportFormat = Literal["docx", "pdf", "reader", "searchable_pdf"]


@dataclass
class ConversionResult:
    """Result of an end-to-end conversion job."""
    input_path: Path
    output_path: Path
    document_ir: DocumentIR
    format: ExportFormat
    warnings: List[str] = field(default_factory=list)
    success: bool = True
    asset_root: Optional[Path] = None


def parse_page_range(
    range_spec: Optional[Union[str, Tuple[int, int], List[int], Set[int]]],
    total_pages: int,
) -> Optional[Set[int]]:
    """Parse a page range specification into a 1-indexed set of page numbers (OUT-010).

    Supports:
    - None -> None (process all pages)
    - "1-5, 8, 11-13" -> {1, 2, 3, 4, 5, 8, 11, 12, 13}
    - (1, 5) -> {1, 2, 3, 4, 5}
    - [1, 2, 8] -> {1, 2, 8}
    """
    if range_spec is None:
        return None
    message = f"Invalid page selection. Choose pages between 1 and {total_pages}."
    if type(total_pages) is not int or total_pages < 1:
        raise ValueError("The document has no selectable pages.")
    pages: Set[int] = set()
    if isinstance(range_spec, str):
        cleaned = range_spec.strip()
        if not cleaned:
            return None
        for part in cleaned.split(","):
            match = re.fullmatch(r"\s*([0-9]*)\s*-\s*([0-9]*)\s*", part)
            if match and any(match.groups()):
                start = int(match[1]) if match[1] else 1
                end = int(match[2]) if match[2] else total_pages
                if not 1 <= start <= end <= total_pages:
                    raise ValueError(message)
                pages.update(range(start, end + 1))
            elif re.fullmatch(r"\s*[0-9]+\s*", part):
                pages.add(int(part))
            else:
                raise ValueError(message)
    elif isinstance(range_spec, tuple):
        if len(range_spec) != 2 or any(type(p) is not int for p in range_spec):
            raise ValueError(message)
        start, end = range_spec
        if not 1 <= start <= end <= total_pages:
            raise ValueError(message)
        pages.update(range(start, end + 1))
    elif isinstance(range_spec, (list, set, frozenset)):
        if any(type(p) is not int for p in range_spec):
            raise ValueError(message)
        pages.update(range_spec)
    else:
        raise ValueError(message)
    if not pages or any(p < 1 or p > total_pages for p in pages):
        raise ValueError(message)
    return pages


class PipelineOrchestrator:
    """Coordinates the document reconstruction pipeline across all input and output formats."""

    def __init__(self, routing_mode: RoutingMode = RoutingMode.AUTOMATIC):
        self.routing_mode = routing_mode
        self.pdf_importer = NativePdfImporter(routing_mode=routing_mode)
        self.docx_importer = DocxImporter()
        self.pptx_importer = PptxImporter()
        self.legacy_bridge = LibreOfficeBridge()
        self.docx_exporter = DocxExporter()
        self.pdf_exporter = PdfExporter()
        self.reader_exporter = ReaderExporter()
        self.searchable_exporter = SearchablePdfExporter()

    def _import_by_format(
        self,
        input_file: Path,
        format_type: str,
        workspace: JobWorkspace,
        progress_callback: Optional[ProgressCallback] = None,
        cancel_check: Optional[CancelCheck] = None,
        checkpoint_callback: Optional[CheckpointCallback] = None,
        selected_pages: Optional[Set[int]] = None,
    ) -> DocumentIR:
        """Route to appropriate format importer or legacy bridge (DOC-001, OFF-001..003)."""
        if format_type == "pdf":
            return self.pdf_importer.import_document(
                input_file, workspace, progress_callback, cancel_check, checkpoint_callback, selected_pages=selected_pages
            )
        elif format_type == "docx":
            return self.docx_importer.import_document(
                input_file, workspace, progress_callback, cancel_check, checkpoint_callback
            )
        elif format_type == "pptx":
            return self.pptx_importer.import_document(
                input_file, workspace, progress_callback, cancel_check, checkpoint_callback
            )
        elif format_type == "doc":
            modern_path = self.legacy_bridge.convert_to_modern(input_file, "docx", workspace)
            return self.docx_importer.import_document(
                modern_path, workspace, progress_callback, cancel_check, checkpoint_callback
            )
        elif format_type == "ppt":
            modern_path = self.legacy_bridge.convert_to_modern(input_file, "pptx", workspace)
            return self.pptx_importer.import_document(
                modern_path, workspace, progress_callback, cancel_check, checkpoint_callback
            )
        else:
            raise ValueError(f"Unsupported file format for this pipeline: {format_type}")

    def convert(
        self,
        input_path: Path | str,
        output_path: Path | str,
        options: Optional[ExportOptions] = None,
        export_format: Optional[ExportFormat] = None,
        page_range: Optional[Union[Tuple[int, int], List[int], Set[int], str]] = None,
        progress_callback: Optional[ProgressCallback] = None,
        cancel_check: Optional[CancelCheck] = None,
        checkpoint_callback: Optional[CheckpointCallback] = None,
        asset_store: Optional[JobAssetStore] = None,
    ) -> ConversionResult:
        """Execute full conversion pipeline into target format (DOCX, Large PDF, or HTML Reader).

        When ``asset_store`` is provided, extracted media is persisted outside the
        disposable workspace so the UI and re-export paths can still read it (IMG-001).
        """
        input_file = Path(input_path).resolve()
        output_file = Path(output_path).resolve()
        if input_file == output_file or (output_file.exists() and input_file.samefile(output_file)):
            raise ValueError("Choose an output file different from the original document.")
        if export_format is not None and export_format not in ("docx", "pdf", "reader", "searchable_pdf"):
            raise ValueError("Choose DOCX, PDF, Reader, or searchable PDF output.")

        if options is None:
            options = ExportOptions()
        if asset_store is None:
            asset_store = JobAssetStore()

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

        all_warnings: List[str] = []

        # 3. Run in isolated disposable workspace (SEC-004); media persists in asset_store
        with JobWorkspace(asset_store=asset_store) as ws:
            log_safe_info(f"Starting conversion in isolated workspace: {ws.path.name}")

            # 3.1 Sanitize input document to neutralize active content (SEC-002)
            clean_file, stripped_items = sanitize_document(input_file, ws.path)
            if stripped_items:
                all_warnings.append(
                    f"Active content was removed for security ({len(stripped_items)} items neutralized)."
                )

            # Resolve page selection if requested (OUT-010)
            selected_pages: Optional[Set[int]] = None
            if page_range is not None:
                if format_type == "pdf":
                    import pypdfium2 as pdfium
                    with pdfium.PdfDocument(clean_file) as temp_pdf:
                        selected_pages = parse_page_range(page_range, len(temp_pdf))

            # 3.2 Searchable original-layout PDF (OUT-004): preserve appearance, add
            # a text layer only. This path never reflows and never re-extracts layout.
            if export_format == "searchable_pdf":
                if format_type != "pdf":
                    raise ValueError("Searchable PDF export is only available for PDF input.")
                doc_ir = self._build_page_inventory(clean_file)
                with atomic_output(output_file) as temporary:
                    self.searchable_exporter.export(
                        clean_file,
                        temporary,
                        ocr_engine=self.pdf_importer.ocr_engine,
                        selected_pages=selected_pages,
                        cancel_check=cancel_check,
                    )
                if selected_pages is not None:
                    doc_ir = doc_ir.slice_by_source_pages_set(selected_pages)
                log_safe_info(f"Searchable PDF generated: {output_file.name}")
                return ConversionResult(
                    input_path=input_file,
                    output_path=output_file,
                    document_ir=doc_ir,
                    format="searchable_pdf",
                    warnings=all_warnings,
                    success=True,
                    asset_root=asset_store.assets_dir if asset_store is not None else None,
                )

            # 4. Import document into canonical DocumentIR
            doc_ir = self._import_by_format(
                clean_file,
                format_type,
                ws,
                progress_callback=progress_callback,
                cancel_check=cancel_check,
                checkpoint_callback=checkpoint_callback,
                selected_pages=selected_pages,
            )

            # 5. Validate canonical DocumentIR (DOC-003, DESIGN.md §3)
            if format_type != "pdf" and page_range is not None:
                selected_pages = parse_page_range(page_range, doc_ir.metadata.page_count)
            ir_warnings = validate_document_ir(doc_ir)
            all_warnings.extend(ir_warnings)
            all_warnings.extend(w for b in doc_ir.blocks for w in b.warnings if w not in all_warnings)

            # 6. Apply selective page slicing if requested and not already sliced (OUT-010)
            if selected_pages is not None:
                log_safe_info(f"Applying selective page slicing for pages {sorted(selected_pages)}")
                doc_ir = doc_ir.slice_by_source_pages_set(selected_pages)

            # 7. Export to requested format (DOCX, Large-Print PDF, or Reader HTML)
            if cancel_check and cancel_check():
                raise InterruptedError("Conversion cancelled.")
            with atomic_output(output_file) as temporary:
                if export_format == "pdf":
                    self.pdf_exporter.export(doc_ir, temporary, options)
                elif export_format == "reader":
                    self.reader_exporter.export(doc_ir, temporary, options)
                else:
                    self.docx_exporter.export(doc_ir, temporary, options)
                if cancel_check and cancel_check():
                    raise InterruptedError("Conversion cancelled.")

        log_safe_info(f"Conversion to {export_format.upper()} finished successfully: {output_file.name}")
        return ConversionResult(
            input_path=input_file,
            output_path=output_file,
            document_ir=doc_ir,
            format=export_format,
            warnings=all_warnings,
            success=True,
            asset_root=asset_store.assets_dir if asset_store is not None else None,
        )

    def _build_page_inventory(self, file_path: Path) -> DocumentIR:
        """Build a page/classification-only DocumentIR without extraction or OCR (OUT-004)."""
        import pypdfium2 as pdfium

        from openlargeprint.importers.pdf.classifier import classify_pdf_page

        pages: List[PageMetadata] = []
        with pdfium.PdfDocument(file_path) as pdf:
            for idx in range(len(pdf)):
                try:
                    pages.append(classify_pdf_page(pdf[idx], idx + 1))
                except Exception:
                    pages.append(
                        PageMetadata(
                            page_number=idx + 1,
                            width=595.0,
                            height=842.0,
                            classification=PageClassification.SCANNED,
                        )
                    )

        return DocumentIR(
            schema_version="1.0.0",
            metadata=DocumentMetadata(
                title=file_path.stem.replace("_", " "),
                source_file_name=file_path.name,
                page_count=len(pages),
            ),
            pages=pages,
            blocks=[],
        )

    def inspect(self, input_path: Path | str) -> DocumentIR:
        """Inspect and classify a document into DocumentIR without exporting."""
        input_file = Path(input_path).resolve()
        format_type = detect_file_type(input_file)

        with JobWorkspace(asset_store=JobAssetStore()) as ws:
            clean_file, _stripped = sanitize_document(input_file, ws.path)
            doc_ir = self._import_by_format(clean_file, format_type, ws)
            return doc_ir

    def retry_page(
        self,
        input_path: Path | str,
        page_number: int,
        routing_mode: RoutingMode = RoutingMode.MAXIMUM_ACCURACY,
    ) -> DocumentIR:
        """Re-process a single flagged page at higher accuracy (UI-004)."""
        input_file = Path(input_path).resolve()
        fmt = detect_file_type(input_file)
        with JobWorkspace(asset_store=JobAssetStore()) as ws:
            clean_file, _ = sanitize_document(input_file, ws.path)
            # Use a fresh importer honouring the requested routing mode so the
            # retry actually re-runs extraction/OCR rather than returning cached blocks.
            retry_importer = NativePdfImporter(routing_mode=routing_mode) if fmt == "pdf" else None
            if retry_importer is not None:
                import pypdfium2 as pdfium
                with pdfium.PdfDocument(clean_file) as pdf:
                    selected = parse_page_range([page_number], len(pdf))
                full = retry_importer.import_document(clean_file, ws, selected_pages=selected)
            else:
                full = self._import_by_format(clean_file, fmt, ws)
            retried_blocks = [b for b in full.blocks if b.source_page == page_number]
            return DocumentIR(
                schema_version=full.schema_version,
                metadata=full.metadata,
                pages=[p for p in full.pages if p.page_number == page_number],
                blocks=retried_blocks,
            )
