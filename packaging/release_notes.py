#!/usr/bin/env python3
"""Release notes: the CHANGELOG section for the version, then what to download.

    python packaging/release_notes.py 0.6.0 > release-notes.md
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

DOWNLOADS = """
## Which file to download

| Computer | File |
| --- | --- |
| Windows 10 or 11 (64-bit) | `OpenLargePrint-Setup-x64.exe` (installer) |
| Windows, without installing | `OpenLargePrint_{v}_windows_x64_portable.zip` |
| Linux (any distribution) | `OpenLargePrint_{v}_linux_x86_64.AppImage` |
| Fedora, openSUSE, RHEL | `OpenLargePrint_{v}_linux_x86_64.rpm` |
| Ubuntu, Debian, Mint | `OpenLargePrint_{v}_linux_amd64.deb` |

The Windows files are not code-signed. Windows may show "Windows protected your
PC": choose **More info**, then **Run anyway**. On Windows 11 with Smart App
Control turned on, unsigned apps are blocked; see the README.

Check a download with `SHA256SUMS.txt`:
`sha256sum -c SHA256SUMS.txt --ignore-missing` (Linux) or
`Get-FileHash OpenLargePrint-Setup-x64.exe` (Windows PowerShell).

Converting documents never uses the internet. Everything happens on your computer.
"""


def main() -> int:
    version = sys.argv[1]
    text = (ROOT / "CHANGELOG.md").read_text("utf-8")
    match = re.search(rf"^## \[?{re.escape(version)}\]?[^\n]*\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    if not match:
        print(f"CHANGELOG.md has no section for {version}", file=sys.stderr)
        return 1
    print(match.group(1).strip())
    print(DOWNLOADS.replace("{v}", version))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
