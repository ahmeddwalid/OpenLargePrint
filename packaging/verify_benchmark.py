"""Persist separate reference-fidelity and execution metrics (QA-001..003).

Run with the source environment. Private generated samples/outputs stay ignored;
the report contains metrics only, never extracted document contents.
"""
from pathlib import Path
import argparse

from openlargeprint.qa import BenchmarkRunner


def main() -> None:
    argparse.ArgumentParser(description=__doc__.splitlines()[0]).parse_args()
    root = Path(__file__).resolve().parent / "verification"
    runner = BenchmarkRunner(root / "corpus")
    name = "benchmark-results"
    report = runner.run_benchmark(root / "benchmark")
    (root / f"{name}.json").write_text(report.model_dump_json(indent=2), encoding="utf-8")
    (root / f"{name}.md").write_text(
        "# Source benchmark results\n\n" + report.to_markdown_table() + "\n", encoding="utf-8"
    )
    print(f"Cases: {report.total_cases}; execution passes: {report.passed_cases}; expectation mismatches: {report.expectation_failures}")


if __name__ == "__main__":
    main()
