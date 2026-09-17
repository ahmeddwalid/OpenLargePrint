"""Standalone CLI interface for OpenLargePrint (DESIGN.md §1, UI-001, UI-005)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from openlargeprint.exporters import ExportOptions, PaperSize, PresetName
from openlargeprint.ir.serialization import document_to_json
from openlargeprint.ocr.router import RoutingMode
from openlargeprint.pipeline import PipelineOrchestrator


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="openlargeprint",
        description="OpenLargePrint: Accessible, structure-preserving document reconstruction engine",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Convert command
    convert_parser = subparsers.add_parser("convert", help="Convert a document to large-print DOCX")
    convert_parser.add_argument("input", type=Path, help="Path to input PDF document")
    convert_parser.add_argument(
        "-o", "--output", type=Path, required=True, help="Path to write output DOCX file"
    )
    convert_parser.add_argument(
        "--preset",
        choices=[p.value for p in PresetName if p != PresetName.CUSTOM],
        default=PresetName.LARGE.value,
        help="Text-size preset (default: Large 20pt/1.5)",
    )
    convert_parser.add_argument(
        "--paper-size",
        choices=[p.value for p in PaperSize],
        default=PaperSize.A4.value,
        help="Paper size target: A4 (default) or A3",
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

    # Inspect command
    inspect_parser = subparsers.add_parser(
        "inspect", help="Inspect and classify document structure without exporting"
    )
    inspect_parser.add_argument("input", type=Path, help="Path to input PDF document")
    inspect_parser.add_argument(
        "--json", action="store_true", help="Output raw DocumentIR JSON"
    )

    args = parser.parse_args()

    try:
        if args.command == "convert":
            routing_mode = RoutingMode(args.mode)
            orchestrator = PipelineOrchestrator(routing_mode=routing_mode)

            preset_enum = PresetName(args.preset)
            paper_size_enum = PaperSize(args.paper_size)
            options = ExportOptions(
                preset=preset_enum,
                paper_size=paper_size_enum,
                include_page_markers=not args.no_page_markers,
            )

            result = orchestrator.convert(args.input, args.output, options)
            print(f"Successfully converted: {args.input.name} -> {args.output.name}")
            print(f"  Preset: {args.preset} ({options.body_pt}pt, line spacing {options.line_spacing})")
            print(f"  Paper size: {args.paper_size}")
            print(f"  Routing mode: {args.mode}")
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

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
