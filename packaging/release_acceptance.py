"""Fail-closed publication gate for recorded enforced-mode SAC acceptance.

The protected release environment supplies human test evidence. Signature tests
alone cannot substitute for an installed acceptance run (PKG-001).
"""
import argparse
import hashlib
import json
import re
from pathlib import Path

REQUIRED_CHECKS = ("installation", "launch", "ocr", "update", "settings_removal",
    "installed_signatures", "installed_uninstaller", "code_integrity_no_blocks", "full_gui_corpus")


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def verify_acceptance(record, installer, portable, thumbprint):
    if record.get("enforced") is not True:
        raise ValueError("Smart App Control enforced-mode acceptance is missing.")
    checks = record.get("checks", {})
    if any(checks.get(key) is not True for key in REQUIRED_CHECKS):
        raise ValueError("All installed acceptance checks and full GUI corpus checks are required.")
    if not all(isinstance(record.get(key), str) and record[key].strip()
               for key in ("tested_by", "tested_at", "evidence_url")):
        raise ValueError("Acceptance reviewer, date, and evidence URL are required.")
    if not re.fullmatch(r"[a-fA-F0-9]{64}", record.get("uninstaller_sha256", "")):
        raise ValueError("The actual installed uninstaller hash is required.")
    if not thumbprint or record.get("signing_thumbprint", "").lower() != thumbprint.lower():
        raise ValueError("Acceptance does not match the configured signing identity.")
    if record.get("installer_sha256", "").lower() != digest(installer):
        raise ValueError("Acceptance does not match this installer.")
    if record.get("portable_sha256", "").lower() != digest(portable):
        raise ValueError("Acceptance does not match this portable payload.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for name in ("acceptance", "installer", "portable", "thumbprint"):
        parser.add_argument(f"--{name}", required=True)
    args = parser.parse_args()
    verify_acceptance(json.loads(Path(args.acceptance).read_text(encoding="utf-8-sig")),
                      args.installer, args.portable, args.thumbprint)
    print("Exact-artifact enforced Smart App Control acceptance verified.")
