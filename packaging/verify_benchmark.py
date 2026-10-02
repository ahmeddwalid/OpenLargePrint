"""Persist separate reference-fidelity and execution metrics (QA-001..003).

Run with the source environment. Private generated samples/outputs stay ignored;
the report contains metrics only, never extracted document contents.
"""
from pathlib import Path
import argparse

from openlargeprint.qa import BenchmarkRunner


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--accuracy", action="store_true", help="Compare the installed optional pack; keep baseline reports separate.")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent / "verification"
    runner = BenchmarkRunner(root / "corpus")
    name = "benchmark-results"
    if args.accuracy:
        from openlargeprint.pipeline import PipelineOrchestrator
        from openlargeprint.ocr.router import OcrRouter, RoutingMode
        if "en" not in OcrRouter.available_accuracy_languages():
            raise RuntimeError("Prepare the verified English accuracy pack first.")
        runner.orchestrator = PipelineOrchestrator(routing_mode=RoutingMode.MAXIMUM_ACCURACY)
        name = "accuracy-results"
    report = runner.run_benchmark(root / "benchmark")
    (root / f"{name}.json").write_text(report.model_dump_json(indent=2), encoding="utf-8")
    (root / f"{name}.md").write_text(
        "# Source benchmark results\n\n" + ("Optional English PP-OCRv6 mode. Arabic still falls back with review warnings.\n\n" if args.accuracy else "Baseline mode.\n\n") + report.to_markdown_table() + "\n", encoding="utf-8"
    )
    print(f"Cases: {report.total_cases}; execution passes: {report.passed_cases}; expectation mismatches: {report.expectation_failures}")


if __name__ == "__main__":
    main()
