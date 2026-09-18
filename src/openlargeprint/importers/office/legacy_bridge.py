"""Isolated headless LibreOffice bridge for legacy DOC and PPT conversion (OFF-002, OFF-003, SEC-008)."""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
from pathlib import Path
from typing import List, Literal, Optional

from openlargeprint.security import JobWorkspace, log_safe_info


class LibreOfficeBridge:
    """Safely converts legacy binary Office files (.doc, .ppt) to modern OOXML (.docx, .pptx)."""

    def __init__(self, timeout_seconds: int = 60):
        self.timeout_seconds = timeout_seconds

    @staticmethod
    def find_libreoffice_binary() -> Optional[str]:
        """Locate headless LibreOffice executable on current system."""
        for candidate in ("libreoffice", "soffice"):
            bin_path = shutil.which(candidate)
            if bin_path:
                return bin_path

        # Standard Windows installation paths
        if os.name == "nt":
            win_candidates = [
                r"C:\Program Files\LibreOffice\program\soffice.exe",
                r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
            ]
            for wc in win_candidates:
                if Path(wc).exists():
                    return wc

        return None

    def convert_to_modern(
        self,
        file_path: Path,
        target_format: Literal["docx", "pptx"],
        workspace: JobWorkspace,
    ) -> Path:
        """Convert legacy binary file into modern OOXML inside an isolated workspace.
        
        Enforces OFF-003 and SEC-008:
        - Argument array (never shell string concatenation)
        - Disposable temporary user profile (-env:UserInstallation)
        - Strict timeout with process group tree termination (SIGKILL / taskkill)
        """
        input_file = Path(file_path).resolve()
        if not input_file.exists():
            raise FileNotFoundError(f"Input file not found: {input_file}")

        lo_bin = self.find_libreoffice_binary()
        if not lo_bin:
            raise RuntimeError(
                "LibreOffice is required to convert legacy binary .doc and .ppt documents, "
                "but no 'libreoffice' or 'soffice' executable was found on PATH (OFF-002)."
            )

        # 1. Create disposable user installation profile directory inside the isolated workspace (OFF-003)
        profile_dir = workspace.path / "lo_disposable_profile"
        profile_dir.mkdir(parents=True, exist_ok=True)
        profile_uri = profile_dir.as_uri()

        # 2. Build controlled argument array (SEC-008)
        cmd: List[str] = [
            lo_bin,
            "--headless",
            "--invisible",
            "--nocrashreport",
            "--nodefault",
            "--nofirststartwizard",
            f"-env:UserInstallation={profile_uri}",
            "--convert-to",
            target_format,
            str(input_file),
            "--outdir",
            str(workspace.path.resolve()),
        ]

        log_safe_info(f"Invoking LibreOffice bridge conversion to {target_format.upper()}")

        # 3. Launch subprocess in a dedicated session/process group for full tree termination (SEC-008)
        popen_kwargs = {}
        if os.name == "nt":
            popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | 0x08000000
        else:
            popen_kwargs["start_new_session"] = True

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            **popen_kwargs,
        )

        try:
            stdout, stderr = process.communicate(timeout=self.timeout_seconds)
        except subprocess.TimeoutExpired:
            # Kill entire process group on timeout (SEC-008)
            if os.name == "nt":
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(process.pid)],
                    capture_output=True,
                    creationflags=0x08000000,
                )
            else:
                try:
                    os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                except OSError:
                    pass
            process.communicate()
            raise TimeoutError(
                f"LibreOffice conversion process exceeded timeout limit of {self.timeout_seconds}s (SEC-008)."
            )

        if process.returncode != 0:
            err_msg = stderr.decode(errors="replace").strip()
            raise RuntimeError(
                f"LibreOffice legacy bridge failed with exit code {process.returncode}: {err_msg}"
            )

        # 4. Locate and validate the resulting modern document
        expected_output = workspace.path / f"{input_file.stem}.{target_format}"
        if not expected_output.exists():
            # Fallback scan for any file matching target_format in workspace
            matches = list(workspace.path.glob(f"*.{target_format}"))
            if matches:
                expected_output = matches[0]
            else:
                raise FileNotFoundError(
                    f"LibreOffice completed with exit code 0 but no .{target_format} file was generated."
                )

        if expected_output.stat().st_size == 0:
            raise ValueError(f"LibreOffice generated an empty {target_format.upper()} document.")

        log_safe_info(f"LibreOffice bridge successfully converted legacy document to {expected_output.name}")
        return expected_output
