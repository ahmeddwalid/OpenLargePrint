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
    if "nsis" not in targets:
        print(f"Error: bundle targets must include 'nsis' for Windows 11 packaging. Got: {targets}")
        return False

    # 5. Check externalBin declaration (PKG-001, PKG-002)
    ext_bin = conf.get("bundle", {}).get("externalBin", [])
    if "binaries/openlargeprint-sidecar" not in ext_bin:
        print(f"Error: bundle.externalBin must contain 'binaries/openlargeprint-sidecar'. Got: {ext_bin}")
        return False

    # 6. Check compiled sidecar binary exists
    sidecar_bin = repo_root / "src-tauri" / "binaries" / "openlargeprint-sidecar-x86_64-pc-windows-msvc.exe"
    if not sidecar_bin.exists():
        print(f"Error: sidecar binary not found at {sidecar_bin}. Run build_sidecar.py first.")
        return False

    # 7. Check accessible Windows icons exist
    icons_dir = repo_root / "src-tauri" / "icons"
    if not (icons_dir / "icon.ico").exists() or not (icons_dir / "icon.png").exists():
        print(f"Error: required application icons (icon.ico, icon.png) missing in {icons_dir}.")
        return False

    # 8. Check UI build assets exist
    ui_index = repo_root / "ui" / "dist" / "index.html"
    if not ui_index.exists():
        print(f"Warning: ui/dist/index.html not built yet. Run 'npm run build' in ui/.")

    print("Packaging verification passed: Tauri 2 configuration, sidecar binary, Windows 11 NSIS targets, icons, and security boundaries are valid.")
    return True


if __name__ == "__main__":
    success = verify_packaging()
    sys.exit(0 if success else 1)
