#!/usr/bin/env python3
"""Every place that declares the application version must agree (PKG-001).

The installer name, the engine's health report, the in-app update check and the
release tag all read different files; a mismatch ships an app that thinks it is
another version. Prints ``version=<x.y.z>`` for GitHub Actions on success.

    python packaging/check_versions.py [--tag v0.6.0]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def declared_versions() -> dict[str, str]:
    found: dict[str, str] = {}
    found["pyproject.toml"] = tomllib.loads((ROOT / "pyproject.toml").read_text("utf-8"))["project"]["version"]
    match = re.search(r'__version__\s*=\s*"([^"]+)"', (ROOT / "src/openlargeprint/version.py").read_text("utf-8"))
    found["src/openlargeprint/version.py"] = match.group(1) if match else "?"
    lock = tomllib.loads((ROOT / "uv.lock").read_text("utf-8"))
    found["uv.lock"] = next((p["version"] for p in lock["package"] if p["name"] == "openlargeprint"), "?")
    found["src-tauri/tauri.conf.json"] = json.loads((ROOT / "src-tauri/tauri.conf.json").read_text("utf-8"))["version"]
    found["src-tauri/Cargo.toml"] = tomllib.loads((ROOT / "src-tauri/Cargo.toml").read_text("utf-8"))["package"]["version"]
    cargo_lock = tomllib.loads((ROOT / "src-tauri/Cargo.lock").read_text("utf-8"))
    found["src-tauri/Cargo.lock"] = next(
        (p["version"] for p in cargo_lock["package"] if p["name"] == "openlargeprint-desktop"), "?")
    found["ui/package.json"] = json.loads((ROOT / "ui/package.json").read_text("utf-8"))["version"]
    package_lock = json.loads((ROOT / "ui/package-lock.json").read_text("utf-8"))
    found["ui/package-lock.json"] = package_lock.get("packages", {}).get("", {}).get("version", package_lock.get("version", "?"))
    match = re.search(r"CURRENT_VERSION\s*=\s*'([^']+)'", (ROOT / "ui/src/api/update-checker.ts").read_text("utf-8"))
    found["ui/src/api/update-checker.ts"] = match.group(1) if match else "?"
    found["sbom.json"] = json.loads((ROOT / "sbom.json").read_text("utf-8"))["version"]
    return found


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tag", default="", help="release tag to compare, e.g. v0.6.0")
    args = parser.parse_args()
    found = declared_versions()
    versions = set(found.values())
    problems = []
    if len(versions) != 1:
        problems.append("versions differ: " + ", ".join(f"{k}={v}" for k, v in found.items()))
    version = sorted(versions)[0]
    if args.tag and args.tag != f"v{version}":
        problems.append(f"tag {args.tag} does not match version {version}")
    changelog = (ROOT / "CHANGELOG.md").read_text("utf-8")
    if not re.search(rf"^## \[?{re.escape(version)}\]?", changelog, re.M):
        problems.append(f"CHANGELOG.md has no section for {version}")
    if problems:
        for problem in problems:
            print(f"error: {problem}", file=sys.stderr)
        return 1
    print(f"version={version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
