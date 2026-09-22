"""Release signing gates for Windows artifacts (PKG-001, SEC-006).

Windows 11 Smart App Control blocks unsigned executables outright, with no user
override. These tests pin the two properties that make the release pipeline
survive a Smart App Control machine:

  1. The signing helper signs every evaluated binary and fails closed.
  2. The packaging pipeline signs the desktop shell and the sidecar *before*
     the NSIS bundle is assembled, so the installed executables carry
     signatures and not only the installer.
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SIGN_SCRIPT = REPO_ROOT / "packaging" / "sign_windows.ps1"
VERIFY_SCRIPT = REPO_ROOT / "packaging" / "verify_signatures.ps1"
PACKAGING_SCRIPT = REPO_ROOT / "packaging" / "build_windows_app.ps1"


def test_signing_helper_fails_closed_and_timestamps():
    """The signing helper must use SHA-256, RFC 3161 timestamps, and verify (PKG-001)."""
    text = SIGN_SCRIPT.read_text(encoding="utf-8")

    assert '$ErrorActionPreference = "Stop"' in text
    assert "signtool" in text.lower()
    assert "/fd" in text and "SHA256" in text          # digest algorithm pinned
    assert "/tr" in text and "/td" in text             # RFC 3161 timestamping
    assert "verify /pa" in text or "verify\", \"/pa" in text  # post-sign verification


def test_packaging_pipeline_signs_binaries_before_bundling():
    """The desktop shell and sidecar must be signed before the installer is bundled (PKG-001)."""
    text = PACKAGING_SCRIPT.read_text(encoding="utf-8")

    assert "sign_windows.ps1" in text, "packaging must call the shared signing helper"
    assert "openlargeprint-desktop.exe" in text
    assert "openlargeprint-sidecar" in text

    # Signing must happen before the bundler runs, otherwise unsigned executables
    # are sealed inside the installer.
    sign_index = text.index("sign_windows.ps1")
    bundle_index = text.index("bundle --bundles nsis")
    assert sign_index < bundle_index, "binaries must be signed before the NSIS bundle step"


def test_signature_verifier_exists_and_fails_on_missing_signature():
    """The verifier must inspect real Authenticode state and exit non-zero (PKG-001, SEC-006)."""
    text = VERIFY_SCRIPT.read_text(encoding="utf-8")

    assert "Get-AuthenticodeSignature" in text
    assert "exit 1" in text
    assert "'Valid'" in text
