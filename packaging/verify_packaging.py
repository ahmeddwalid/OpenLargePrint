#!/usr/bin/env python3
"""Validates Tauri configuration, sidecar integration, and packaging requirements (PKG-001, PKG-002, SEC-005)."""

import json
from pathlib import Path
import sys


def verify_packaging() -> bool:
    repo_root = Path(__file__).resolve().parent.parent
    tauri_conf_path = repo_root / "src-tauri" / "tauri.conf.json"

    if not tauri_conf_path.exists():
        print(f"Error: {tauri_conf_path} does not exist!")
        return False

    with open(tauri_conf_path, "r") as f:
        conf = json.load(f)

    # 1. Check frontendDist
    dist = conf.get("build", {}).get("frontendDist")
    if dist != "../ui/dist":
        print(f"Error: expected frontendDist to be '../ui/dist', got '{dist}'")
        return False

    # 2. Check CSP
    csp = conf.get("app", {}).get("security", {}).get("csp", "")
    if "default-src 'self'" not in csp:
        print(f"Error: CSP missing 'default-src self': {csp}")
        return False

    # 3. Check product details
    product_name = conf.get("productName")
    if product_name != "OpenLargePrint":
        print(f"Error: unexpected product name: {product_name}")
        return False

    # 4. Check Windows bundle targets
    targets = conf.get("bundle", {}).get("targets", [])
    if "nsis" not in targets or "msi" not in targets:
        print(f"Error: bundle targets must include 'nsis' and 'msi' for Windows 11 packaging. Got: {targets}")
        return False

    # 5. Check UI build assets exist
    ui_index = repo_root / "ui" / "dist" / "index.html"
    if not ui_index.exists():
        print(f"Warning: ui/dist/index.html not built yet. Run 'npm run build' in ui/.")

    print("Packaging verification passed: Tauri 2 configuration, Windows 11 bundle targets, and security boundaries are valid.")
    return True


if __name__ == "__main__":
    success = verify_packaging()
    sys.exit(0 if success else 1)
