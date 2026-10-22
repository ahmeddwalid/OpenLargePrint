#!/usr/bin/env python3
"""Turn failing tests in a JUnit XML report into GitHub Actions error annotations.

    python packaging/annotate_failures.py pytest-results.xml

Annotations appear on the run summary, so a failure can be read without
downloading the whole log.
"""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET


def escape(text: str) -> str:
    return text.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    try:
        root = ET.parse(sys.argv[1]).getroot()
    except (OSError, ET.ParseError) as exc:
        print(f"No test report to read ({exc}).")
        return 0
    shown = 0
    for case in root.iter("testcase"):
        for problem in list(case.findall("failure")) + list(case.findall("error")):
            name = f"{case.get('classname', '')}.{case.get('name', '')}"
            detail = (problem.get("message") or "") + "\n" + (problem.text or "")
            lines = detail.strip().splitlines()
            print(f"::error title={escape(name)}::{escape(chr(10).join(lines[-40:]))}")
            shown += 1
            if shown >= 10:
                return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
