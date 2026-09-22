# Windows Code Signing Guide

This document details the code signing requirements, certificate options, and signing workflow for Windows distributions of OpenLargePrint.

## 1. Why Code Signing Matters

Code signing verifies the identity of the software publisher and provides cryptographic assurance that the distributed binaries have not been altered or corrupted since compilation.

On Windows 10 and Windows 11, code signing directly affects application distribution:

- **Windows Defender SmartScreen**: Unsigned application installers trigger Microsoft Defender SmartScreen warning dialogs stating "Windows protected your PC: Microsoft Defender SmartScreen prevented an unrecognized app from starting." To install an unsigned application, users must locate and click a "More info" link followed by a secondary "Run anyway" confirmation button.
- **Accessibility and Assistive Technology Considerations**: OpenLargePrint is designed specifically for low-vision readers, many of whom rely on high-magnification screen lenses or screen readers. SmartScreen interstitial modal warnings disrupt accessibility workflows, obscure navigation cues, and present unnecessary friction for non-technical users.
- **Publisher Authenticity**: A signed binary displays the verified publisher name in User Account Control (UAC) elevation prompts and file properties dialogues, confirming provenance and reducing security risk.

- **Windows 11 Smart App Control**: an unsigned application is blocked outright, and unlike SmartScreen there is no
  "Run anyway" path. Microsoft's Smart App Control documentation states: *"If the security service is unable to make a
  confident prediction about the app, then Smart App Control checks to see if the app has a valid signature. If the app
  has a valid signature, Smart App Control will let it run. If the app is unsigned, or the signature is invalid, Smart
  App Control will consider it untrusted and block it for your protection."*

  Two consequences drive the packaging pipeline:

  1. **The installed executables must be signed, not just the installer.** Smart App Control evaluates the binaries
     Windows loads after installation (`openlargeprint-desktop.exe` and `openlargeprint-sidecar.exe`), so signing the
     NSIS installer alone leaves the application blocked after it is installed.
  2. **The certificate must chain to a CA in the Microsoft Trusted Root Program.** A self-signed certificate does not
     satisfy Smart App Control, no matter how the machine's local trust store is configured.
  3. **The NSIS-generated uninstaller is not covered by signing the installer.** `uninstall.exe` is produced by the
     NSIS stub at install time and does not inherit the installer's signature, so on a machine with Smart App Control
     enforced the entry in Settings > Apps cannot run (Code Integrity events 3033 and 3077 name
     `%LOCALAPPDATA%\OpenLargePrint\uninstall.exe`). Removal then has to go through the installer's own uninstall
     path or a manual deletion of the install directory. Fixing this needs an NSIS build hook that signs the generated
     uninstaller during packaging; signing the installer does not address it.

  You can check the state on a machine with:

  ```powershell
  Get-ItemProperty -Path 'HKLM:\SYSTEM\CurrentControlSet\Control\CI\Policy' |
      Select-Object VerifiedAndReputablePolicyState
  ```

  `0` = off, `1` = enforced, `2` = evaluation. When a block occurs, the reason is recorded in the
  `Microsoft-Windows-CodeIntegrity/Operational` event log (events 3033 and 3077).

## 2. Option A: Commercial EV or OV Certificate

Commercial code signing certificates are issued by publicly trusted Certificate Authorities (CAs) conforming to the CA/Browser Forum standards.

### Providers and Pricing

- **Providers**: SSL.com, Sectigo, Certum, DigiCert
- **Approximate Cost**: $70 to $300 per year, depending on certificate tier and validity duration

### Certificate Types

- **Extended Validation (EV) Code Signing**:
  - Provides immediate reputation with Microsoft Defender SmartScreen upon the first installation.
  - Requires strict identity validation of a registered legal organization or sole proprietorship.
  - Private keys must be held on a FIPS 140-2 Level 2 compliant hardware token (such as a physical YubiKey HSM) or in an authenticated cloud HSM signing service (such as SSL.com eSigner or DigiCert ONE).
- **Organization Validation (OV) Code Signing**:
  - Requires identity validation of the contributing entity.
  - In current Windows versions, OV certificates do not confer instant SmartScreen trust. Instead, trust builds cumulatively as download volume grows without reported malware detections.
  - Also requires storage on a physical hardware token or approved cloud HSM.

### Recommended Use

Recommended for official public releases distributed by registered non-profit organizations, academic institutions, or commercial entities.

## 3. Option B: Azure Trusted Signing

Azure Trusted Signing (formerly Microsoft Identity Verification) is a cloud-based signing service managed directly through Microsoft Azure.

### Overview and Pricing

- **Provider**: Microsoft Azure Trusted Signing
- **Approximate Cost**: Flat subscription of approximately $10 per month for standard profile tiers, with per-signature operations included or billed at fractions of a cent

### Characteristics

- **Direct SmartScreen Trust**: Certificates issued via Azure Trusted Signing integrate directly with Microsoft identity infrastructure, providing immediate SmartScreen reputation without physical USB hardware tokens.
- **Cloud Key Management**: Cryptographic keys remain securely managed in Azure hardware security modules. Private keys cannot be leaked from local developer machines or CI build runners.
- **CI/CD Automation**: Integrates cleanly into automated GitHub Actions or Azure DevOps release pipelines.
- **Tooling Support**: Works with standard Windows SDK `signtool.exe` via the `Azure.CodeSigning.Dlib` dynamic library plugin.

### Recommended Use

Recommended for active open-source maintainers who require automated, cloud-based release signing without maintaining physical USB hardware tokens.

## 4. Option C: Self-Signed Certificate for Development

A self-signed certificate can be generated locally for internal development, debugging NSIS installer configurations, and validating packaging pipelines.

A self-signed certificate will not prevent SmartScreen warnings on external machines, and it will **never** satisfy
Smart App Control: only certificates chaining to the Microsoft Trusted Root Program are accepted there. It exists to
exercise the signing and verification plumbing locally, and to test NSIS packaging behaviour.

`packaging/create_self_signed_cert.ps1` now imports the generated certificate into `Cert:\CurrentUser\Root` on the
development machine, which is what `signtool verify /pa` needs in order to report a valid chain. This makes the local
machine trust the certificate; it does not make Windows treat the binary as trusted for Smart App Control purposes.

### Generating a Self-Signed Certificate

Execute the following commands in PowerShell to create a local code signing certificate:

```powershell
# Create self-signed certificate in the CurrentUser certificate store
$cert = New-SelfSignedCertificate `
    -Type CodeSigningCert `
    -Subject "CN=OpenLargePrint Development" `
    -CertStoreLocation "Cert:\CurrentUser\My" `
    -HashAlgorithm SHA256 `
    -NotAfter (Get-Date).AddYears(1)

# Display the resulting thumbprint
Write-Host "Certificate Thumbprint: $($cert.Thumbprint)"
```

### Trusting the Certificate Locally for Testing

To permit test installations without certificate validation errors on the local machine:

```powershell
# Export public key to a temporary file
Export-Certificate -Cert $cert -FilePath "$env:TEMP\OpenLargePrintDev.cer"

# Import into the local Trusted Root Certification Authorities store
Import-Certificate -FilePath "$env:TEMP\OpenLargePrintDev.cer" -CertStoreLocation "Cert:\CurrentUser\Root"
```

## 5. Applying the Certificate

The Windows packaging script ([`packaging/build_windows_app.ps1`](packaging/build_windows_app.ps1)) automatically detects and applies a code signing certificate when the `OLP_CODESIGN_THUMBPRINT` environment variable is defined.

### Using the Automated Packaging Script

1. Define the certificate thumbprint in your PowerShell session:
   ```powershell
   $env:OLP_CODESIGN_THUMBPRINT = "YOUR_CERTIFICATE_THUMBPRINT_HEX_VALUE"
   ```

2. Run the packaging pipeline:
   ```powershell
   powershell -ExecutionPolicy Bypass -File packaging/build_windows_app.ps1
   ```

The script builds the Python sidecar, compiles the frontend, generates icons, runs Tauri packaging, and invokes
`signtool.exe` to sign the produced executables with SHA-256 and an RFC 3161 timestamp.

### Signing order

The pipeline deliberately signs in two phases, because the NSIS bundler seals whatever is in `src-tauri/target/release`
at bundle time:

1. `npx @tauri-apps/cli@2 build --no-bundle` compiles the desktop shell without producing an installer.
2. `packaging/sign_windows.ps1` signs `openlargeprint-desktop.exe` and
   `openlargeprint-sidecar-x86_64-pc-windows-msvc.exe`.
3. `npx @tauri-apps/cli@2 bundle --bundles nsis` assembles the installer around the already-signed executables.
4. `packaging/sign_windows.ps1` signs the installer itself.

Signing only the installer (the previous behaviour) leaves the installed application unsigned, which Smart App Control
blocks. Setting `OLP_REQUIRE_SIGNING=1` makes the build fail instead of producing unsigned artifacts.

### Verification gate

`packaging/verify_signatures.ps1` inspects the real Authenticode state of each artifact and exits non-zero if anything
is unsigned, tampered with, or signed by an unexpected publisher:

```powershell
powershell -ExecutionPolicy Bypass -File packaging/verify_signatures.ps1 `
    -Path packaging/dist/OpenLargePrint_0.2.0_x64-setup.exe `
    -ExpectedPublisherMatch "SignPath Foundation"
```

The release workflow runs this gate before publishing once signing is configured. Both scripts fail closed: a signing or
verification failure is an error, never a warning.

### Manual Signing with SignTool

To sign an executable manually using `signtool.exe` (included in the Windows SDK):

```powershell
& "C:\Program Files (x86)\Windows Kits\10\bin\10.0.22621.0\x64\signtool.exe" sign `
    /sha1 $env:OLP_CODESIGN_THUMBPRINT `
    /fd SHA256 `
    /tr "http://timestamp.digicert.com" `
    /td SHA256 `
    "src-tauri\target\release\bundle\nsis\OpenLargePrint_0.2.0_x64-setup.exe"
```

Parameters:
- `/sha1`: Specifies the SHA-1 thumbprint of the signing certificate in the Windows Certificate Store.
- `/fd SHA256`: Specifies SHA-256 as the file digest algorithm.
- `/tr "http://timestamp.digicert.com"`: Specifies the RFC 3161 timestamp authority URL.
- `/td SHA256`: Specifies SHA-256 as the timestamp digest algorithm.

### Signing with Azure Trusted Signing

When using Azure Trusted Signing with the `signtool` dlib plugin:

```powershell
signtool.exe sign `
    /v /debug `
    /dlib "C:\Tools\Azure.CodeSigning.Dlib\x64\Azure.CodeSigning.Dlib.dll" `
    /dmdf "C:\Tools\signing-metadata.json" `
    "src-tauri\target\release\bundle\nsis\OpenLargePrint_0.2.0_x64-setup.exe"
```

## 6. Verifying Signatures

### Command-Line Verification

Verify the digital signature and timestamp using `signtool.exe` with the Default Authenticode Verification Policy (`/pa`):

```powershell
signtool.exe verify /pa /v "src-tauri\target\release\bundle\nsis\OpenLargePrint_0.2.0_x64-setup.exe"
```

A successful verification prints the signing certificate chain, timestamp details, and the confirmation message:

```text
Successfully verified: src-tauri\target\release\bundle\nsis\OpenLargePrint_0.2.0_x64-setup.exe
Number of files successfully Verified: 1
```

### Graphical Verification via File Explorer

1. Open Windows File Explorer and navigate to the compiled installer executable.
2. Right-click the `.exe` file and select **Properties**.
3. In the Properties window, select the **Digital Signatures** tab.
4. Select the signature from the **Signature list** and click **Details**.
5. Verify that the Digital Signature Information pane states: "This digital signature is OK."
6. Click **View Certificate** to review the certificate chain, validity dates, and subject details.

## 7. Local Development under Smart App Control

Smart App Control blocks unsigned executables, which includes anything built locally: `cargo build` output, the
PyInstaller sidecar, and any installer produced by `packaging/build_windows_app.ps1`. A development machine therefore
needs a deliberate decision, documented here so it is not rediscovered by trial and error.

| Option | Effect | Notes |
|---|---|---|
| Enable **Developer Mode** (Settings > System > For developers) | Smart App Control turns itself off on that machine | The recommended development answer. Microsoft lists a configured developer mode as a reason Smart App Control disables itself |
| Turn Smart App Control **off** in Windows Security > App & browser control | Unsigned builds run | A real security downgrade, and re-enabling has historically required resetting Windows |
| Sign with the development certificate | `signtool verify /pa` passes locally | Does **not** satisfy Smart App Control; use it to exercise the plumbing only |

Verification that the machine is unblocked for development work:

```powershell
Get-ItemProperty -Path 'HKLM:\SYSTEM\CurrentControlSet\Control\CI\Policy' |
    Select-Object VerifiedAndReputablePolicyState
```

`0` means Smart App Control is off; `1` means it is enforced and unsigned local builds will be blocked.
