# Contributing to OpenLargePrint

OpenLargePrint welcomes contributions. All contributions are submitted under the GNU General Public License v3.0 or later, matching the project license in [LICENSE](LICENSE). No Contributor License Agreement (CLA) is required.

Before starting work on a contribution, read [SPEC.md](SPEC.md) and [DESIGN.md](DESIGN.md) to understand product requirements and system architecture. In addition, review [AGENTS.md](AGENTS.md) for testing guidelines, security boundaries, and copy standards.

## Core Invariants

All contributions must adhere to the non-negotiable principles defined in [SPEC.md §2](SPEC.md#L15-L25):

- Native text takes priority over recognized text. Never run optical character recognition on a page confirmed to have usable native text ([`PDF-002`](SPEC.md)).
- Never route recognized text through a generative language model to smooth or alter output ([`OCR-007`](SPEC.md)).
- Never drop a page or document section on failure. Flag problematic pages for user review and preserve original content ([`UI-004`](SPEC.md)).
- Preserve source-page provenance. Every reflowed block must retain its original page number and bounding box coordinates ([`PDF-006`](SPEC.md)).
- Conversions run completely offline. Standard conversions must generate zero network traffic ([`SEC-009`](SPEC.md)).
- Accessibility is a first-class requirement. Controls, focus states, and text scaling must meet accessibility standards ([`A11Y-001`](SPEC.md) through [`A11Y-005`](SPEC.md)).

## Development Environment Setup

### Prerequisites

Install the following development tools:

- **Python 3.11 or later** with `uv` package manager ([https://astral.sh/uv](https://astral.sh/uv))
- **Node.js 20 or later** with `npm`
- **Rust stable toolchain** installed via `rustup` ([https://rustup.rs](https://rustup.rs))
- **Tauri CLI v2** installed via `cargo install tauri-cli --version "^2.0.0"` or run through `npx @tauri-apps/cli`
- **Microsoft Visual Studio C++ Build Tools** (on Windows) with the x64 C++ build tools workload

### Setup Instructions

#### Windows (Automated)

Run the development helper script in PowerShell:

```powershell
.\dev_windows.ps1
```

This verifies prerequisites, synchronizes dependencies with `uv`, builds the development sidecar into `src-tauri/binaries/` if missing, and launches the desktop app in development mode.

To run the full test suite on Windows instead of launching the app:

```powershell
.\dev_windows.ps1 -Test
```

#### Manual Setup (Linux and Windows)

1. Clone the repository:
   ```bash
   git clone https://github.com/ahmeddwalid/OpenLargePrint.git
   cd openlargeprint
   ```

2. Initialize the Python environment and install project dependencies:
   ```bash
   uv sync --locked --dev --extra dev --python 3.12
   ```

3. Build the development sidecar binary required by Tauri:
   ```bash
   uv run python packaging/build_sidecar.py
   ```

4. Install frontend dependencies:
   ```bash
   cd ui
   npm install
   cd ..
   ```

## Repository Structure

The codebase is organized into several functional areas:

- [`src/openlargeprint/`](src/openlargeprint/): Python processing engine.
  - `importers/`: Native PDF extraction, scanned PDF preprocessing, Office importers (DOCX, PPTX), and legacy LibreOffice bridge.
  - `ocr/`: OCR engine protocol and PaddleOCR / RapidOCR ONNX runtime adapter.
  - `ir/`: Canonical [`DocumentIR`](src/openlargeprint/ir/models.py) data structures and validation schemas.
  - `exporters/`: Large-print PDF, DOCX, and HTML Reader exporters.
  - `sidecar/`: JSON-Lines IPC protocol communicating with the Tauri desktop shell.
  - `text/`: Arabic script reshaping and bidirectional text handling.
- [`src-tauri/`](src-tauri/): Rust desktop shell built on Tauri 2. Manages native OS integration, window configuration, file picker dialogues, and sidecar process lifecycle.
- [`ui/`](ui/): React 19 and TypeScript frontend. Contains the accessible UI components, format selectors, side-by-side review screen, and interactive Reader.
- [`tests/`](tests/): Pytest test suites covering unit tests, schema tests, Arabic RTL handling, security checks, and the rights-safe benchmark corpus.
- [`packaging/`](packaging/): Standalone build scripts, PyInstaller spec files, icon generation tools, and packaging verification gates.

## How to Run and Test

### Python Engine and Tests

Run the full pytest suite:

```bash
uv run pytest tests/ -v
```

Run tests with test coverage reporting:

```bash
uv run pytest tests/ --cov=openlargeprint
```

Invoke the Python CLI directly:

```bash
uv run python -m openlargeprint.cli convert input.pdf -o output.docx --font-size 20
```

### Frontend

Run the Vite development server:

```bash
cd ui
npm run dev
```

Compile and typecheck the frontend bundle:

```bash
cd ui
npm run build
```

### Rust Desktop Shell

Verify Rust code compilation:

```bash
cd src-tauri
cargo check
```

Run Rust clippy checks:

```bash
cd src-tauri
cargo clippy -- -D warnings
```

Run the complete desktop application in development mode:

```bash
cd src-tauri
npx @tauri-apps/cli dev
```

## Code Style Guidelines

- **Python**:
  - Follow existing patterns in [`src/openlargeprint/`](src/openlargeprint/).
  - Use type annotations throughout.
  - All document importers must normalize output directly into [`DocumentIR`](src/openlargeprint/ir/models.py). No importer may bypass [`DocumentIR`](src/openlargeprint/ir/models.py) or communicate directly with an exporter.
  - New OCR engines must implement the [`DocumentOcrEngine`](src/openlargeprint/ocr/base.py) protocol interface.
- **TypeScript and React**:
  - Adhere to the configuration in [`ui/tsconfig.json`](ui/tsconfig.json).
  - Maintain WCAG 2.2 accessibility standards:
    - Primary interactive controls must meet or exceed 48 CSS pixels in width and height ([`A11Y-001`](SPEC.md)).
    - The layout must remain fully legible and operable at 200% text enlargement ([`A11Y-002`](SPEC.md)).
    - Every interactive control must provide a visible keyboard focus indicator ([`A11Y-003`](SPEC.md)).
    - High-contrast modes and reduced-motion preferences must be respected ([`A11Y-004`](SPEC.md)).
- **Rust**:
  - Follow standard `rustfmt` formatting and default `cargo clippy` rules.
  - Expose only narrow, typed commands over the Tauri bridge. Do not expose arbitrary command execution or unrestricted filesystem APIs to the webview ([`SEC-005`](SPEC.md)).
- **Documentation and UI Copy**:
  - Write factual, concise sentences.
  - Do not use exclamation marks in copy.
  - Do not use em dashes in copy (use colons, parentheses, semicolons, or separate sentences instead).
  - Do not use marketing buzzwords (such as seamless, effortless, unlock, empower, elevate, streamline, revolutionize, cutting-edge, leverage, robust, supercharge, or game-changing).

## Pull Request Checklist

Before submitting a pull request, verify the following items:

- [ ] Reference the applicable `SPEC.md` requirement ID(s) (such as `PDF-002`, `OCR-001`, `OUT-007`, `A11Y-003`) in your commit message and PR summary.
- [ ] Run the Python test suite and confirm all tests pass: `uv run pytest tests/ -v`.
- [ ] Verify the frontend builds cleanly without TypeScript errors: `cd ui && npm run build`.
- [ ] Verify the Rust shell compiles cleanly: `cd src-tauri && cargo check`.
- [ ] Update [sbom.json](sbom.json) if any dependencies or model weights are added, updated, or removed ([`LIC-001`](SPEC.md)).
- [ ] Update [DESIGN.md](DESIGN.md) if your changes modify architecture, schemas, or IPC boundaries.
- [ ] Confirm no external network calls are made during the conversion process ([`SEC-009`](SPEC.md)).
- [ ] If changing UI components, verify the screen passes the accessibility checklist and visual craft rules in [AGENTS.md §6 and §7](AGENTS.md#L57-L146).

## Visual verification harness

The anti-slop gate in [AGENTS.md §7](AGENTS.md) requires screenshots of every finished screen. A small
harness under [`ui/`](ui/audit.html) renders the file picker flow, progress, review, and Reader screens
against a recorded conversion fixture ([`ui/audit-data.json`](ui/audit-data.json)) so screenshots can be
regenerated without a fresh document conversion:

```bash
cd ui
npm run dev
# open http://localhost:1420/audit.html?view=review&theme=sepia
```

`view` accepts `review`, `complete`, `reader`, and `progress`; `theme` accepts the app theme names;
`scale=200%` exercises the 200% text-enlargement check ([`A11Y-002`](SPEC.md)).

## Licensing of Contributions

All contributions submitted to OpenLargePrint become part of the project codebase under the terms of the GNU General Public License v3.0 or later, the same license as the [LICENSE](LICENSE) file. By contributing, you agree that your work is licensed under GPL-3.0-or-later without requiring a separate contributor license agreement.
