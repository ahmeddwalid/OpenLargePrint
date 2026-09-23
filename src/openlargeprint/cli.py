"""Standalone CLI interface for OpenLargePrint (DESIGN.md §1, UI-001, UI-005, OUT-010..011)."""

from __future__ import annotations

import argparse
import multiprocessing
import sys
from pathlib import Path

if __name__ == "__main__":
    multiprocessing.freeze_support()

from openlargeprint.exporters import ExportOptions, PaperSize, PresetName
from openlargeprint.ir.serialization import document_to_json
from openlargeprint.ocr.router import RoutingMode
from openlargeprint.pipeline import PipelineOrchestrator


def main() -> int:
    # Ensure UTF-8 output across Windows and all platforms
    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    if sys.stderr and hasattr(sys.stderr, "reconfigure"):
        try:
            sys.stderr.reconfigure(encoding="utf-8")
        except Exception:
            pass

    parser = argparse.ArgumentParser(
        prog="openlargeprint",
        description="OpenLargePrint: Accessible, structure-preserving document reconstruction engine",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Convert command
    convert_parser = subparsers.add_parser("convert", help="Convert a document to large-print DOCX, PDF, or Reader HTML")
    convert_parser.add_argument("input", type=Path, help="Path to input document (PDF, DOCX, PPTX, DOC, PPT)")
    convert_parser.add_argument(
        "-o", "--output", type=Path, required=True, help="Path to write output file (.docx, .pdf, .html)"
    )
    convert_parser.add_argument(
        "--format",
        choices=["docx", "pdf", "reader"],
        default=None,
        help="Explicit output format (default: inferred from output extension)",
    )
    convert_parser.add_argument(
        "--preset",
        choices=[p.value for p in PresetName],
        default=PresetName.LARGE.value,
        help="Text-size preset (default: Large 20pt/1.5)",
    )
    convert_parser.add_argument(
        "--body-pt",
        type=float,
        default=None,
        help="Custom body text size in points (used with --preset Custom)",
    )
    convert_parser.add_argument(
        "--line-spacing",
        type=float,
        default=None,
        help="Custom line-spacing multiplier (used with --preset Custom)",
    )
    convert_parser.add_argument(
        "--paper-size",
        choices=[p.value for p in PaperSize],
        default=PaperSize.A4.value,
        help="Paper size target: A4 (default) or A3",
    )
    convert_parser.add_argument(
        "--page-range",
        nargs=2,
        type=int,
        metavar=("START", "END"),
        help="Export only a selected page range (e.g. --page-range 2 5)",
    )
    convert_parser.add_argument(
        "--mode",
        choices=[m.value for m in RoutingMode],
        default=RoutingMode.AUTOMATIC.value,
        help="Recognition routing mode: Automatic (default), Fast, or Maximum accuracy",
    )
    convert_parser.add_argument(
        "--no-page-markers",
        action="store_true",
        help="Do not insert 'Original page N' transition markers",
    )
    convert_parser.add_argument(
        "--preserve-page-artwork",
        action="store_true",
        help=(
            "Keep page-filling images instead of omitting them. Off by default: these are "
            "usually the scanned page itself or a canvas background"
        ),
    )

    # Inspect command
    inspect_parser = subparsers.add_parser(
        "inspect", help="Inspect and classify document structure without exporting"
    )
    inspect_parser.add_argument("input", type=Path, help="Path to input document (PDF, DOCX, PPTX, DOC, PPT)")
    inspect_parser.add_argument(
        "--json", action="store_true", help="Output raw DocumentIR JSON"
    )

    # Benchmark command
    benchmark_parser = subparsers.add_parser(
        "benchmark",
        help="Run the rights-safe benchmark corpus and report per-metric results (QA-001)",
    )
    benchmark_parser.add_argument(
        "--corpus-dir", type=Path, default=None,
        help="Directory to build the synthetic corpus in (default: a temporary directory)",
    )
    benchmark_parser.add_argument(
        "--out-dir", type=Path, default=None,
        help="Directory to write converted benchmark outputs to",
    )
    benchmark_parser.add_argument(
        "--fail-on-mismatch", action="store_true",
        help="Exit non-zero when a case disagrees with its expected structure or text",
    )

    # Sidecar command
    subparsers.add_parser(
        "sidecar", help="Run the JSON-Lines sidecar protocol loop for desktop shell integration (DESIGN.md §9)"
    )

    args = parser.parse_args()

    try:
        if args.command == "convert":
            routing_mode = RoutingMode(args.mode)
            orchestrator = PipelineOrchestrator(
                routing_mode=routing_mode,
                preserve_page_artwork=bool(getattr(args, "preserve_page_artwork", False)),
            )

            preset_enum = PresetName(args.preset)
            paper_size_enum = PaperSize(args.paper_size)
            options = ExportOptions(
                preset=preset_enum,
                paper_size=paper_size_enum,
                include_page_markers=not args.no_page_markers,
                custom_body_pt=args.body_pt,
                custom_line_spacing=args.line_spacing,
            )

            page_range = tuple(args.page_range) if args.page_range else None

            result = orchestrator.convert(
                input_path=args.input,
                output_path=args.output,
                options=options,
                export_format=args.format,
                page_range=page_range,
            )

            print(f"Successfully converted: {args.input.name} -> {args.output.name}")
            print(f"  Format: {result.format.upper()}")
            print(f"  Preset: {args.preset} ({options.body_pt}pt, line spacing {options.line_spacing})")
            print(f"  Paper size: {args.paper_size}")
            if page_range:
                print(f"  Selected range: Pages {page_range[0]} to {page_range[1]}")
            print(f"  Total pages processed: {result.document_ir.metadata.page_count}")
            print(f"  Total semantic blocks: {len(result.document_ir.blocks)}")
            print("  Note: Print at 100% / actual size (not 'fit to page') to preserve text size.")

            if result.warnings:
                print("\nWarnings:")
                for w in result.warnings:
                    print(f"  - {w}")
            return 0

        elif args.command == "inspect":
            orchestrator = PipelineOrchestrator()
            doc_ir = orchestrator.inspect(args.input)
            if args.json:
                print(document_to_json(doc_ir))
            else:
                print(f"Document: {args.input.name}")
                print(f"Page count: {doc_ir.metadata.page_count}")
                print("\nPage classifications:")
                for page in doc_ir.pages:
                    details = page.details
                    print(
                        f"  Page {page.page_number}: {page.classification.value} "
                        f"(chars: {details.get('char_count', 0)}, "
                        f"raster coverage: {details.get('raster_coverage', 0):.1%}, "
                        f"rotation: {page.rotation}°)"
                    )
                print(f"\nExtracted blocks: {len(doc_ir.blocks)}")
            return 0

        elif args.command == "benchmark":
            from openlargeprint.qa import BenchmarkRunner

            report = BenchmarkRunner(corpus_dir=args.corpus_dir).run_benchmark(out_dir=args.out_dir)
            print(report.to_markdown_table())
            print(
                f"\nCases: {report.total_cases} | converted: {report.passed_cases} "
                f"| conversion failures: {report.failed_cases}"
            )
            if report.expectation_failures:
                print(f"Expectation mismatches: {report.expectation_failures}")
                for case_name, case_result in report.results.items():
                    for mismatch in case_result.expectation_mismatches:
                        print(f"  - {case_name}: {mismatch}")
            if args.fail_on_mismatch and report.expectation_failures:
                return 1
            return 0

        elif args.command == "sidecar":
            from openlargeprint.sidecar import SidecarRunner
            runner = SidecarRunner()
            runner.run_loop()
            return 0

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
