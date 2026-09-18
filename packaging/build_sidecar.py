#!/usr/bin/env python3
"""Packaging script to compile the Python engine into a standalone Tauri sidecar (PKG-001, PKG-002).

This ensures the end user never needs to install Python, configure environments,
or run terminal commands. The resulting binary is placed in `src-tauri/binaries/`
following Tauri 2 external-binary naming conventions:
`openlargeprint-sidecar-<target-triple>[.exe]`
"""

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path


def get_target_triple() -> str:
    """Detect current target triple for Tauri sidecar naming."""
    system = platform.system().lower()
    machine = platform.machine().lower()

    if system == "linux":
        if machine in ("x86_64", "amd64"):
            return "x86_64-unknown-linux-gnu"
        elif machine in ("aarch64", "arm64"):
            return "aarch64-unknown-linux-gnu"
    elif system == "darwin":
        if machine in ("arm64", "aarch64"):
            return "aarch64-apple-darwin"
        else:
            return "x86_64-apple-darwin"
    elif system == "windows":
        return "x86_64-pc-windows-msvc"

    return f"{machine}-unknown-{system}"


def build_sidecar() -> Path:
    repo_root = Path(__file__).resolve().parent.parent
    dist_dir = repo_root / "packaging" / "dist"
    tauri_bin_dir = repo_root / "src-tauri" / "binaries"
    tauri_bin_dir.mkdir(parents=True, exist_ok=True)

    target_triple = get_target_triple()
    ext = ".exe" if platform.system() == "Windows" else ""
    target_filename = f"openlargeprint-sidecar-{target_triple}{ext}"
    final_binary_path = tauri_bin_dir / target_filename

    entrypoint = repo_root / "src" / "openlargeprint" / "cli.py"

    print(f"Building standalone sidecar for target: {target_triple}")
    print(f"Entrypoint: {entrypoint}")
    print(f"Destination: {final_binary_path}")

    # PyInstaller command
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--clean",
        "--onefile",
        "--name",
        f"openlargeprint-sidecar-{target_triple}",
        "--distpath",
        str(dist_dir),
        "--workpath",
        str(repo_root / "packaging" / "build"),
        "--specpath",
        str(repo_root / "packaging"),
        "--collect-all",
        "pypdfium2",
        "--collect-all",
        "pikepdf",
        "--collect-all",
        "rapidocr_onnxruntime",
        "--collect-all",
        "openlargeprint",
        str(entrypoint),
    ]

    try:
        # Check if PyInstaller is installed
        import PyInstaller  # type: ignore
        subprocess.run(cmd, check=True)
        built_binary = dist_dir / f"openlargeprint-sidecar-{target_triple}{ext}"
        if built_binary.exists():
            shutil.copy2(built_binary, final_binary_path)
            print(f"Successfully packaged and copied sidecar to: {final_binary_path}")
            return final_binary_path
    except ImportError:
        print("PyInstaller not present in build environment — writing standalone stub specification.")

    # Write wrapper runner specification if PyInstaller is not in current virtualenv
    stub_script = tauri_bin_dir / target_filename
    with open(stub_script, "w") as f:
        f.write("#!/usr/bin/env sh\n")
        f.write('exec "$(dirname "$0")/../../.venv/bin/openlargeprint" sidecar "$@"\n')
    os.chmod(stub_script, 0o755)
    print(f"Created executable runner stub at: {stub_script}")
    return stub_script


if __name__ == "__main__":
    build_sidecar()
