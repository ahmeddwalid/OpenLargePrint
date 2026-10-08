# Windows code signing

## Current state

Windows releases are **unsigned**. No publicly trusted code-signing identity is
configured yet. The effect for users:

- **SmartScreen** shows "Windows protected your PC" the first time. **More info**
  then **Run anyway** continues. This is expected for unsigned software.
- **Smart App Control** (Windows 11), when enforced, blocks unsigned apps with no
  override. The app cannot run on such a computer until a signed release exists.

A development or self-signed certificate does not help users: their computers do
not trust it. Never publish with one, and never ask users to trust a
development root.

## Turning signing on

Signing is already wired into the build and switches on when an identity exists:

1. Get a publicly trusted code-signing identity usable by SignTool on a Windows
   build host (an Authenticode certificate, or a signing service such as Azure
   Trusted Signing that exposes one). Microsoft's guidance for Smart App Control:
   [code signing for Smart App Control](https://learn.microsoft.com/en-us/windows/apps/develop/smart-app-control/code-signing-for-smart-app-control).
2. Make the certificate available on the release runner and set the repository
   variable `OLP_CODESIGN_THUMBPRINT` to its 40-character thumbprint.
3. Tag a release as usual.

With the thumbprint set, `packaging/build_windows_app.ps1`:

- signs the desktop executable, the engine executable and every EXE, DLL and PYD
  in the engine runtime **before** the installer is assembled, so the installed
  files are signed and not only the installer;
- signs the generated uninstaller through Tauri's `signCommand` hook;
- signs the installer itself;
- uses SHA-256 digests and RFC 3161 timestamps, and checks every signature with
  `packaging/verify_signatures.ps1 -RequirePublicTrust` (Authenticode status,
  timestamp, chain to a Microsoft AuthRoot certificate, expected thumbprint).

Set `OLP_REQUIRE_SIGNING=1` to make an unsigned build fail instead of continuing.
`-DevelopmentUnsigned` writes local test builds to `packaging/dist/development`.

Signing contacts the timestamp and revocation services. Document conversion stays
offline.

## Before announcing a signed release

Test the signed installer on Windows 11 with Smart App Control enforced
([Microsoft's test guidance](https://learn.microsoft.com/en-us/windows/apps/develop/smart-app-control/test-your-app-with-smart-app-control)):
install, start, convert a scanned PDF (this starts the recognition subprocess),
update, and remove through Settings > Apps, and check the Code Integrity event log
for blocked files. `packaging/verify_installed_windows.ps1` checks the installed
files' signatures; `packaging/release_acceptance.py` can record that test against
the exact installer and zip hashes.
