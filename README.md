<p align="center">
  <img src="logo.svg" alt="OpenLargePrint logo" width="180">
</p>

<h1 align="center">OpenLargePrint</h1>

<p align="center">Open-source, local-first desktop application that reconstructs dense PDFs, law books, and Office documents into large-print publications for low-vision readers.</p>

<p align="center">
  <a href="https://github.com/ahmeddwalid/OpenLargePrint/releases/latest/download/OpenLargePrint-Setup-x64.exe">
    <img src="https://img.shields.io/badge/Download_installer-Windows_11-5f7340?style=for-the-badge" alt="Download the latest OpenLargePrint installer for Windows">
  </a>
</p>

<p align="center">Installs on Windows 11 and does not need Python or a terminal. The <a href="https://github.com/ahmeddwalid/OpenLargePrint/releases">releases page</a> also carries the portable archive, its SHA-256 checksums, and older versions.</p>

<p align="center"><sub>Windows 11 Smart App Control refuses unsigned applications. Until a signing certificate is configured, installs on a machine with Smart App Control enforced need the steps in <a href="SIGNING.md">SIGNING.md</a>.</sub></p>

## Overview

When low-vision readers encounter materials with dense layouts (such as two-column law textbooks, academic papers, and scanned legal documents), basic magnification tools like standard PDF zoom fail. Fixed-layout pages clip text, require constant horizontal scrolling, and overlap columns when magnified.

OpenLargePrint parses and reconstructs the underlying structure of a document instead of magnifying static page images. The application extracts native text, runs optical character recognition (OCR) where needed, reconstructs multi-column reading order, normalizes content into a canonical document model ([`DocumentIR`](src/openlargeprint/ir/models.py)), and reflows the text into single-column large-print output.

All processing occurs locally on the computer. No document content, text, or images leave the device.

## Development status

Windows x86_64 is the primary release target; Fedora/Linux x86_64 is the secondary target. This checkout is undergoing reliability hardening. A successful build or synthetic test run does not establish full platform support (`PKG-001`). Final packaged Windows CPU/GPU tests, Linux desktop tests, screen-reader checks, and physical printing remain release gates.

The installed OCR baseline is RapidOCR 1.4.4 with bundled PP-OCRv4 Chinese/English recognition. Arabic native-text rendering and Arabic scan recognition are separate capabilities: the bundled recognizer does **not** provide verified Arabic OCR. Maximum accuracy currently uses standard recognition with an explicit review warning; a real higher-accuracy pack remains open. The three shipped model hashes are verified before inference. Unimplemented model catalog entries have been removed.

Quality reports distinguish measured text error from missing reference transcripts. Reading-order/table heuristics are diagnostics, not claims of accuracy. See [DESIGN.md](DESIGN.md) for the completion gates and latest validation limits.

## Core Capabilities

- **Local-first and offline execution**: Document analysis, OCR, and rendering run on the local machine with zero external network calls during conversion ([`SEC-009`](SPEC.md)).
- **Native text priority**: If extractable Unicode text exists in a digital PDF, OpenLargePrint extracts it directly. OCR is applied only to scanned pages or image regions lacking native text ([`PDF-002`](SPEC.md)).
- **Reading order reconstruction**: Layout analysis detects multi-column layouts, tables, and images, preserving logical reading order for low-vision reading ([`OCR-001`](SPEC.md), [`PDF-003`](SPEC.md)).
- **Arabic and bidirectional text support**: Supports Arabic script reshaping, right-to-left reading order, and mixed Arabic and English bidirectional text ([`LANG-001`](SPEC.md), [`LANG-002`](SPEC.md)).
- **Multiple output formats**: Exports reflowed large-print PDF files (A4 and A3 paper sizes), editable large-print DOCX documents, and an in-app interactive Reader ([`OUT-001`](SPEC.md) through [`OUT-007`](SPEC.md)).
- **Source provenance and side-by-side review**: Each reflowed block retains its source page number and bounding box coordinates. Pages with low OCR confidence are flagged for side-by-side review against the original page image ([`PDF-006`](SPEC.md), [`UI-004`](SPEC.md)).
- **Accessible interface**: Built to WCAG 2.2 standards with controls meeting or exceeding 48px target sizes, visible keyboard focus indicators, high-contrast color modes, and full operability at 200% text enlargement ([`A11Y-001`](SPEC.md) through [`A11Y-005`](SPEC.md)).
- **Opt-in update system**: With update checks enabled, the app checks GitHub releases and can download a checksum-verified installer directly from the app without manual browser navigation. Disabled by default; fully separate from offline document conversion.

## Supported Formats

### Input Formats

- **PDF (.pdf)**: Born-digital documents, scanned books, mixed digital and scanned pages, and documents with corrupted text layers.
- **Word (.docx)**: Direct structural import of paragraphs, headings, lists, tables, and images.
- **PowerPoint (.pptx)**: Direct structural import of slides, text frames, shapes, and notes.
- **Legacy Word (.doc) and PowerPoint (.ppt)**: Converted through an isolated headless LibreOffice bridge into modern intermediate formats before processing ([`OFF-002`](SPEC.md)).

### Output Formats

- **Large-Print PDF (.pdf)**: Single-column reflowed layout at user-selected font sizes (18pt, 20pt, 24pt, 28pt, or custom). Supports A4 (default) and A3 page sizes with physical page dimensions embedded.
- **Large-Print Word (.docx)**: Fully editable document structured with semantic styles and matching page setups for word processors.
- **In-App Reader**: Interactive viewer allowing adjustments to font size, line spacing, margins, and color schemes without reprocessing the source document ([`OUT-002`](SPEC.md)).
- **Searchable PDF**: Retains the original visual layout of scanned documents while embedding an OCR text layer ([`OUT-004`](SPEC.md)).

## Downloads and Release Verification

Pre-compiled packages for Windows 10 and 11 (64-bit) are available on the [GitHub Releases](https://github.com/ahmeddwalid/OpenLargePrint/releases) page.

### Current Release: v0.3.2

| Package | Format | File Size | Description |
|---|---|---|---|
| [`OpenLargePrint-Setup-x64.exe`](https://github.com/ahmeddwalid/OpenLargePrint/releases/latest/download/OpenLargePrint-Setup-x64.exe) | NSIS Installer | ~117 MB | Standard Windows installer with start menu and context menu integration. This link always fetches the newest stable release |
| [`OpenLargePrint_0.3.2_windows_x64_portable.zip`](https://github.com/ahmeddwalid/OpenLargePrint/releases/download/v0.3.2/OpenLargePrint_0.3.2_windows_x64_portable.zip) | Portable Archive | ~117 MB | Standalone folder; extract and run `OpenLargePrint.exe` without installation |

### Checksums (SHA-256)

Download [SHA256SUMS.txt](https://github.com/ahmeddwalid/OpenLargePrint/releases/latest/download/SHA256SUMS.txt) from the same release as the installer.

The installer keeps one name across releases so the download link above stays valid; the release tag carries the version.

To verify the downloaded installer on Windows PowerShell:

```powershell
Get-FileHash -Algorithm SHA256 OpenLargePrint-Setup-x64.exe
```

### Code signing and Smart App Control

These releases are **not yet code-signed**, which has two separate consequences on Windows:

- **SmartScreen** may warn on first run. The warning can be dismissed with "More info" and "Run anyway".
- **Smart App Control** (Windows 11) blocks the application outright. There is no override button: unsigned executables are treated as untrusted, and the block applies to the installed `openlargeprint-desktop.exe` and `openlargeprint-sidecar.exe` as well as to the installer. If Smart App Control is enabled on your machine, the application cannot be started until a signed release is published.

The packaging pipeline signs the desktop shell, the engine sidecar, and the installer before the installer is assembled, and the release workflow refuses to publish artifacts that fail signature verification once a signing certificate is configured. Certificate options, the development-certificate workflow, and the exact commands are documented in [`SIGNING.md`](SIGNING.md).

## Installation and Updates

### Installer Behavior

- Installs the complete standalone desktop shell and bundled Python processing engine.
- Does not require pre-installed Python, Node.js, or command-line tools.
- Runs under standard user accounts without requiring administrator privileges.
- Registers an optional Windows Explorer context menu entry ("Enlarge with OpenLargePrint") for supported file types.

### Software Updates

OpenLargePrint includes an opt-in update checker that communicates with GitHub Releases:
- Update checks are disabled by default and make no network request until enabled under "More options".
- When enabled and a newer version is detected, an accessible notification banner appears with release details and a direct "Download and install update" action.
- The download is restricted to the OpenLargePrint release repository, must carry a valid SHA-256 release digest, and is verified in-process before the installer is launched. Windows installers are the only asset offered; other platforms show the release page instead.
- The update check is completely separate from document conversion, which never touches the network. Users in air-gapped environments can simply leave update checks disabled.

## System Requirements

- **Operating System**: Windows 10 or Windows 11 (64-bit). Linux and macOS support is in development.
- **Processor**: Standard x64 processor (Intel or AMD). A dedicated GPU is not required; default layout analysis and OCR run on CPU.
- **Memory**: Development target: 16 GB RAM, 8+ CPU cores, optional NVIDIA RTX GPU with 8 GB VRAM. Long-book RAM/VRAM acceptance limits still require measurement on target hardware.
- **Disk Space**: Approximately 500 MB for the installed application and OCR model runtime.

## Building from Source

### Prerequisites

- **Python**: Version 3.11 or 3.12 (3.12 recommended for release builds) with the `uv` package manager ([https://astral.sh/uv](https://astral.sh/uv))
- **Node.js**: Version 20 or later with `npm`
- **Rust**: Current stable toolchain via `rustup` ([https://rustup.rs](https://rustup.rs))
- **Visual Studio Build Tools**: C++ x64 workload for compiling native dependencies on Windows

### Build Instructions

1. Clone the repository:
   ```bash
   git clone https://github.com/ahmeddwalid/OpenLargePrint.git
   cd OpenLargePrint
   ```

2. Set up the Python environment and dependencies:
   ```bash
   uv sync --locked --dev --extra dev --python 3.12
   ```

3. Install frontend dependencies:
   ```bash
   cd ui
   npm ci
   cd ..
   ```

4. Build the complete desktop installer:
   ```powershell
   powershell -ExecutionPolicy Bypass -File packaging/build_windows_app.ps1
   ```

The packaging pipeline produces the standalone installer executable in `src-tauri/target/release/bundle/nsis/` and release assets in `packaging/dist/`.

For day-to-day development on Windows (hot reload, dependency sync, sidecar setup):
```powershell
.\dev_windows.ps1
```
Or to run all test suites on Windows:
```powershell
.\dev_windows.ps1 -Test
```

### Fedora/Linux build

Install the native desktop build prerequisites, then use the same locked Python and frontend setup above:

```bash
sudo dnf install gcc gcc-c++ make pkgconf-pkg-config openssl-devel webkit2gtk4.1-devel libsoup3-devel librsvg2-devel patchelf rpm-build
uv run python packaging/build_sidecar.py
npm --prefix ui run build
uv run python packaging/verify_packaging.py
cd src-tauri
npx -y @tauri-apps/cli@2 build --bundles rpm,appimage
```

Build Linux release artifacts on Linux and Windows release artifacts on Windows. Development sidecar wrappers are not valid release artifacts. The verifier launches the packaged engine and checks its health response; full corpus conversion and installed-app acceptance are additional gates.

### Export safety and limits

Invalid or out-of-range page selections are rejected. Failed exports preserve an existing destination file; the original input cannot be overwritten. Oversized source pages use bounded raster resolution rather than unbounded allocations. Pages that cannot be extracted retain a rendered original when possible and remain flagged for review. If rendering also fails, the output explicitly directs the reader to the original document.

Searchable PDF preserves native PDF objects and adds invisible text on text-free pages. It does not repair mixed or broken existing text layers. If recognition produces no text, the export fails without replacing an existing destination.

## Running Tests

Run the Python engine test suite:

```bash
uv run pytest tests/ -v
```

Run the frontend test suite:

```bash
cd ui
npm test -- --run
```

Run the Rust Tauri checks:

```bash
cd src-tauri
cargo check
```

## Technical Documentation

- [SPEC.md](SPEC.md): Product requirements contract and normative specifications.
- [DESIGN.md](DESIGN.md): System architecture, intermediate representation, and IPC design.
- [CONTRIBUTING.md](CONTRIBUTING.md): Contribution guidelines and code standards.
- [CHANGELOG.md](CHANGELOG.md): Version history and release notes.
- [SIGNING.md](SIGNING.md): Windows code signing and SmartScreen trust documentation.

## License

OpenLargePrint is free software licensed under the GNU General Public License v3.0 (GPL-3.0-or-later). See the [LICENSE](LICENSE) file for the complete license terms.
