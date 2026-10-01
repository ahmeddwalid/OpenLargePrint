# Windows signing and Smart App Control acceptance

Public Windows releases require an identity from a trusted signing provider. None
is currently provisioned. A development certificate is not acceptance evidence.
Microsoft's current guidance accepts RSA and ECC certificates:
[signing guidance](https://learn.microsoft.com/en-us/windows/apps/develop/smart-app-control/code-signing-for-smart-app-control).

## Build and verification

Provision certificate/private-key access on the build host, set
OLP_CODESIGN_THUMBPRINT to its 40-character certificate thumbprint, then run
packaging/build_windows_app.ps1. Public mode is the default and fails without a
publicly trusted identity. Signing-service provisioning is an external prerequisite;
the script expects a SignTool-compatible certificate-store identity.

The pipeline fingerprints and rebuilds the one-directory Python sidecar, checks
actual health/version, builds the desktop, and signs application executables and
native EXE/DLL/PYD files before NSIS packaging. Existing vendor signatures are
preserved only if public trust and timestamp verification pass. Application-owned
files must match the configured identity. SHA-256 signatures and RFC 3161 timestamps
are required. Tauri's Windows signCommand signs during NSIS packaging, including
the generated uninstaller; actual installed uninstall.exe verification remains
mandatory. Configuration alone does not demonstrate installed acceptance.

packaging/verify_signatures.ps1 -RequirePublicTrust checks Authenticode status,
timestamps, chains, Microsoft AuthRoot membership and optional identity matches.
WinTrust validates timestamped signatures; today's expiry date alone does not
invalidate a correctly timestamped vendor signature. Signing preparation may use
network services for timestamps/revocation. Document conversion remains offline.

-DevelopmentUnsigned explicitly writes local builds to packaging/dist/development.
Those builds cannot be published through the release job. Enforced application
control on this machine blocks new Rust build tools (OS error 4551). Use an
appropriately provisioned build host; changing protection is outside this task.

## Installed acceptance and publication

Test on Windows 11 with Smart App Control enforced, following
[Microsoft testing guidance](https://learn.microsoft.com/en-us/windows/apps/develop/smart-app-control/test-your-app-with-smart-app-control).
Verify installation, launch, OCR subprocess execution, update, and Settings > Apps
removal. Convert all eight test PDFs through the rebuilt GUI and verify final export.
Inspect Code Integrity events for blocked files. After installation, run
packaging/verify_installed_windows.ps1 with the actual install directory and expected
publisher. Record the actual uninstall.exe SHA-256 before removal.

The workflow uploads signed candidates first. Publication uses the protected GitHub
environment windows-sac-accepted. Configure required human reviewers and supply
OLP_SAC_ACCEPTANCE_JSON only after testing the exact candidates. The contract in
packaging/release_acceptance.py requires:

- enforced: true; nonempty tested_by, tested_at, evidence_url.
- signing_thumbprint matching the configured identity.
- installer_sha256 and portable_sha256 matching the exact candidates.
- uninstaller_sha256 for the actual installed uninstaller.
- checks with installation, launch, ocr, update, settings_removal,
  installed_signatures, installed_uninstaller, code_integrity_no_blocks, and
  full_gui_corpus all true.

Missing credentials, invalid signatures, absent acceptance, or artifact hash changes
stop publication. Disabling Smart App Control or trusting a development root does
not satisfy acceptance. No accepted public installer has been delivered in this pass.
