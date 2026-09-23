# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.2] - 2026-09-23

### Fixed

- Sidecar input uses UTF-8 on Windows, preserving Arabic and other Unicode filenames even under legacy system code pages (`LANG-001`, `SEC-005`).

- Recognition now runs in a reusable spawned worker with a 120-second page timeout and cancellation polling. Failed pages retain their original image, and subsequent pages continue. The frozen entry point supports Windows process spawning (`UI-002..003`, `SEC-008`).
- Mixed PDF pages exclude native text regions from OCR. Progress identifies recognition work correctly, and failed recognition preserves native text and an original-page image (`PDF-002..004`).
- PDF images and tables use the actual text-frame dimensions; tall retained table images fit within the page. DOCX opens in print layout with page-number fields (`OUT-001`, `OUT-003`, `OUT-007..009`).
- Packaged-engine verification now converts a three-page native/scanned document into A4/A3 PDF and DOCX, checks selected-page content, and renders every PDF page. The acceptance harness now applies the requested paper size (`PKG-001..002`, `OUT-010`).
- Windows tests read UTF-8 output explicitly. Rust CI builds the required sidecar resource, and Windows releases stop on engine-test failure.

### Validation and limitations

- A 318-page sample converted in 533 seconds to 1,444 A4 PDF pages and DOCX, with all source-page anchors retained and all PDF dimensions valid. Its 1,058 review warnings still require assessment; this is completion evidence, not a fidelity guarantee.
- The 16-case synthetic corpus completed. Arabic OCR and complex scanned tables remain below release-quality accuracy; maximum-accuracy recognition and durable crash recovery remain unimplemented. Native PDF parsing/rendering still lacks process-isolated deadlines.

## [0.3.0] - 2026-09-22

### Added

- **Page artwork retention (`IMG-001`, `UI-001`)**: an advanced option, off by default, keeps page-filling images (full-page backgrounds and scanned page images) as figures in the converted document for artwork-heavy material. It is off by default because those images are usually the scanned page itself or a canvas background, and carrying them into the output would turn the reflow back into screenshots of the original. Available as `--preserve-page-artwork` in the CLI and as "Keep page artwork" in the desktop advanced settings.
- **Benchmark corpus gate (`QA-001`)**: each corpus case now declares the structure and text it must produce, and every run is compared against it, so a case that loses pages, text, a table, or its images fails instead of being reported as a pass. `python -m openlargeprint.cli benchmark --fail-on-mismatch` runs it, and a CI job (`benchmark-gate`) runs it on every push and pull request.
- **Windows release signing (`PKG-001`, `SEC-006`)**: the packaging pipeline now signs the desktop shell and the engine sidecar *before* the NSIS installer is assembled, then signs the installer, because Windows 11 Smart App Control evaluates the installed executables rather than the installer and blocks unsigned ones with no override. `packaging/sign_windows.ps1` is the single signing entry point (SHA-256, RFC 3161 timestamp, post-sign verification, fails closed) and `packaging/verify_signatures.ps1` is a release gate that inspects real Authenticode state and can pin the expected publisher.

### Changed

- **Interface redesign (`VIS-001..004`, `A11Y-001..005`, `UI-001`)**: the whole UI moved to a rem-based type scale built on bundled Source Sans 3 with Noto Sans Arabic for Arabic text (both OFL, recorded in the SBOM), so 200% text enlargement scales the chrome and the Reader together. The accent moved from terracotta to an olive tone on warm sepia, format and text-size choices became flat option strips instead of a repeated card grid, the export location moved behind a "Save location" disclosure, and reduced-motion and forced-colors media queries were added. All primary controls now target 48px.
- **Review flow reworked (`UI-004`, `UI-005`, `OUT-002`)**: flagged sections are reviewed per block rather than per page; the original page is shown as a bounded preview image next to the converted text; retrying a section shows the repeated recognition result for comparison instead of silently replacing the text; corrections typed during review are carried into exports.
- **Update system hardened (`SEC-006`, `SEC-009`)**: update checks are now opt-in and make no network request until enabled; the installer download is restricted to the OpenLargePrint GitHub release repository and requires a valid SHA-256 release digest, verified in-process instead of through PowerShell; on non-Windows systems no installer asset is offered.
- **Native dialogs on Linux (`SEC-005`, `PKG-001`)**: the open/save file dialogs now use the Tauri dialog plugin outside Windows, so Linux builds no longer require manual path entry.
- **Honest default routing (`UI-001`, `OCR-002`)**: "Automatic" is the default routing mode; the unavailable higher-accuracy pack is disabled in Advanced options instead of being presented as selectable.
- **Removed demo fallbacks (`UI-005`)**: the frontend no longer synthesizes a mock document or progress loop when the desktop bridge is unavailable; it reports a plain-language error instead.
- **Image recovery instead of image loss (`IMG-001`)**: images whose codec cannot be decoded by the lossless reader (JBIG2 without the `jbig2dec` helper, common in scanned books) are now re-decoded through the rendering engine's own decoder instead of being dropped. Recovered copies are normalised to PNG, dimension-bounded before decoding (`SEC-003`), never duplicated over images that decoded losslessly, and reported as re-decoded copies so the substitution stays visible.
- **Trustworthy memory reporting (`PERF-002`)**: peak memory was reported as 0.0 MB on Windows because the process handle was passed to `GetProcessMemoryInfo` with default marshalling and silently truncated; every performance figure in the benchmark and acceptance reports was meaningless. The call now declares its argument and return types, and the value is asserted by a test.
- **Vector figure retention (`IMG-002`)**: the vector-figure region fallback now also captures single-shape artwork while keeping the area and size guards that exclude rules and table hairlines.

## [0.2.0] - 2026-09-21

Reliability and output-fidelity hardening. These changes fix the paths that caused converted
documents to lose images, ignore the configured text size, or render with clipped/corrupt layout.

### Fixed

- **Images retained after conversion (`IMG-001`, `IMG-002`, `IMG-003`, `SEC-004`)**: extracted media is now persisted in a per-job asset store outside the disposable workspace, so it survives conversion and can be re-read; PDF extraction uses the recursive page-image API, pairs IMAGE+FORM bounds, and reports unreadable/oversized images as warnings instead of dropping them; non-embeddable vector artwork is retained via a bounded source-region render. Office image failures now surface as warnings.
- **Configured text size honored (`OUT-001`, `OUT-002`, `OUT-006`, `OUT-009`)**: the HTML Reader emits point sizes (previously points were emitted as pixels, ~25% too small); the configured font family is resolved cross-platform for PDF and HTML; custom point sizes are reachable end to end (CLI, sidecar, desktop UI); the Reader exposes a reading-width control; print output uses the selected size.
- **Layout fidelity (`TBL-001`, `OUT-003`, `OUT-009`)**: PDF list bullets no longer render a literal `&nbsp;`; images are clamped to the usable width and height without distortion; DOCX table body rows can split across pages (only headers are held together); monochrome output applies to table shading, borders, warnings, footnote dividers, and retained table images.
- **Word/PowerPoint page provenance (`OFF-001`, `PDF-006`)**: non-continuous section breaks in DOCX now advance the source page, so page markers and page-range export work for ordinary Word documents rather than reporting a single page.
- **Re-export without re-processing (`OUT-002`, `OUT-010`)**: the engine retains the built document per job, so changing size, paper, monochrome, or page selection in the Reader re-renders from the existing document instead of re-parsing or re-running OCR.
- **Searchable original PDF (`OUT-004`)**: implemented as a distinct output that preserves the sanitized source page appearance and adds an invisible text layer, without reflow.
- **Security (`SEC-002`, `SEC-003`)**: input sanitization no longer silently passes an unsanitized PDF through when it cannot be opened; page rasterization is bounded before allocation.
- **Cross-platform (`PKG-001`)**: sidecar binary resolution, home-directory paths, and open/reveal actions no longer assume Windows.
- **Measurement honesty (`QA-002`, `PERF-002`)**: benchmark metrics no longer self-compare or hardcode values; missing reference transcripts are reported as unavailable rather than as zero error.

### Changed

- Python runtime constraint narrowed to 3.11–3.12 and the default recognizer pinned, matching the shipped runtime.

## [0.1.0] - 2026-09-18

### Added

- **PDF Classification**: Diagnostic pipeline that categorizes PDF pages into native digital, scanned, mixed, or broken-digital types using character counts, vector geometry, and raster coverage before routing to extraction ([`PDF-001`](SPEC.md), [`PDF-005`](SPEC.md)).
- **Native Text Extraction**: Direct extraction of text, font metrics, and page objects via `pypdfium2` and `pikepdf` without OCR on verified digital pages ([`PDF-002`](SPEC.md)).
- **OCR Pipeline**: CPU-friendly layout analysis and optical character recognition powered by PaddleOCR (via RapidOCR ONNX runtime) with column detection and reading-order reconstruction ([`OCR-001`](SPEC.md), [`OCR-002`](SPEC.md), [`PDF-003`](SPEC.md)).
- **Canonical Document Model (`DocumentIR`)**: Versioned intermediate document representation preserving semantic block types (headings, paragraphs, quotes, lists, tables, footnotes, captions, images), source bounding boxes, and provenance metadata ([`DOC-001`](SPEC.md), [`DOC-002`](SPEC.md), [`DOC-003`](SPEC.md)).
- **Large-Print PDF Exporter**: Generates reflowed, single-column large-print PDF files supporting A4 (default) and A3 page sizes with true physical page dimensions embedded ([`OUT-003`](SPEC.md), [`OUT-007`](SPEC.md), [`OUT-008`](SPEC.md)).
- **Large-Print DOCX Exporter**: Generates formatted Microsoft Word documents using semantic styles and customizable font presets ([`OUT-001`](SPEC.md), [`OUT-006`](SPEC.md)).
- **In-App Semantic HTML Reader**: Interactive reader with instant client-side adjustments for font size, line spacing, margins, and contrast themes without re-running document processing ([`OUT-002`](SPEC.md)).
- **Searchable PDF Exporter**: Preserves original visual layout while embedding an OCR text layer ([`OUT-004`](SPEC.md)).
- **Office Document Importers**: Native DOCX and PPTX structural importers preserving hierarchy, tables, lists, and images ([`OFF-001`](SPEC.md)).
- **Legacy Office Bridge**: Isolated, headless LibreOffice conversion bridge for legacy binary formats (.doc and .ppt) ([`OFF-002`](SPEC.md), [`OFF-003`](SPEC.md)).
- **Arabic and Bidirectional Support**: Arabic script reshaping, right-to-left layout analysis, and bidirectional text reconciliation ([`LANG-001`](SPEC.md), [`LANG-002`](SPEC.md)).
- **Side-by-Side Review Screen**: Verification screen displaying original source page regions next to recognized text blocks for flagged or low-confidence pages ([`UI-004`](SPEC.md)).
- **Accessible User Interface**: Desktop interface built to WCAG 2.2 standards with 48px minimum touch and pointer targets, full keyboard navigation, visible focus indicators, high-contrast themes, and 200% text enlargement support ([`A11Y-001`](SPEC.md) through [`A11Y-005`](SPEC.md), [`UI-001`](SPEC.md)).
- **Windows Explorer Context Menu Integration**: Shell extension registering "Enlarge with OpenLargePrint" on supported document file types (.pdf, .docx, .doc, .pptx, .ppt) for quick processing ([`PKG-001`](SPEC.md)).
- **Windows NSIS Installer & Portable Bundle**: Standalone Windows installer and portable archive bundling the Tauri desktop shell and Python sidecar runtime without requiring pre-installed runtimes ([`PKG-001`](SPEC.md), [`PKG-002`](SPEC.md)).
- **Cryptographic Release Manifest**: Automated SHA-256 digest generation (`SHA256SUMS.txt`) verifying installer integrity.
- **In-App Update System**: Background release checker and direct installer download/launch mechanism for Windows releases while preserving offline zero-network conversion isolation ([`SEC-009`](SPEC.md)).
- **Licensing**: Licensed under the GNU General Public License v3.0 (GPL-3.0-or-later) with a complete dependency license inventory ([`LIC-001`](SPEC.md)).
- **Software Bill of Materials (SBOM)**: Machine-readable dependency inventory tracking code licenses, model-weight licenses, and security attributes ([`LIC-001`](SPEC.md), [`LIC-002`](SPEC.md)).
- **Security Boundaries**: Content-based file validation, bounded resource limits, sandboxed temporary execution directories, and zero network traffic during conversions ([`SEC-001`](SPEC.md) through [`SEC-009`](SPEC.md)).
