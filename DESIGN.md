# OpenLargePrint — DESIGN.md (Architecture Contract)

Status: Draft v0.1
Role of this document: this is the **source of truth for how the system is built**. `SPEC.md` defines *what* must be true; this file defines the structures, boundaries, and flows that make it true. Requirement IDs from `SPEC.md` are referenced throughout so implementation stays traceable.

---

## 1. Product decision this design follows

Build a **local-first desktop application**: Tauri 2 shell, React + TypeScript UI, a packaged Python processing engine run as a Tauri sidecar. Not a GitHub Pages site, not a hosted web service — the workload (OCR, PDF/Office parsing, local ML models) needs a real runtime and needs to stay off the network by default (`SEC-009`).

```text
┌───────────────────────────────┐
│        Tauri desktop shell     │
│  ┌───────────────────────────┐ │
│  │  React + TypeScript UI     │ │  ← accessibility-first, WCAG 2.2 target
│  └─────────────┬─────────────┘ │
│                │ narrow typed commands
│  ┌─────────────▼─────────────┐ │
│  │     Rust / Tauri bridge    │ │  ← no general shell/filesystem exposure (SEC-005)
│  └─────────────┬─────────────┘ │
└────────────────┼───────────────┘
                 │ JSON-Lines IPC
        ┌────────▼─────────┐
        │  Python sidecar   │
        │ processing engine │
        └───────────────────┘
```

The Python engine must remain usable as a **standalone library/CLI**, independent of Tauri, so it can be tested, benchmarked, and reused without the desktop shell.

## 2. The central abstraction: `DocumentIR`

This is the single most important architectural decision. Every importer normalizes into it; every exporter reads only from it. No importer/exporter pair may have private knowledge of each other.

```text
PDF ─────────────┐
DOCX ────────────┤
PPTX ────────────┤
DOC/PPT adapter ─┤
                 ▼
       extraction / OCR
                 │
                 ▼
          DocumentIR
                 │
       ┌─────────┼──────────┐
       ▼         ▼          ▼
      DOCX      Reader    Large PDF
```

### 2.1 Block schema (`DOC-002`)

```text
Block
  id
  type                 # title | heading | paragraph | list | quote |
                        # footnote | table | image | caption | page_marker
  text / children
  language
  text_direction        # ltr | rtl
  source_page
  source_bounding_box
  extraction_method      # native | ocr_fast | ocr_maximum | office_import
  confidence
  warnings[]
  image_asset            # present if type == image
  table_structure        # present if type == table
```

`DocumentIR` itself is versioned (`DOC-003`) with schema tests, so a change to one importer or exporter can't silently break another.

### 2.2 Why this matters

- **Engines become replaceable** — swapping the OCR model pack only touches the engine adapter.
- **Enlargement becomes deterministic** — the DOCX/Reader/PDF exporters style semantic blocks; they never need to know whether a paragraph came from OCR, native PDF text, DOCX, or PPTX.
- **Provenance is preserved** (`PDF-006`, `OUT-005`) — reflowed page N no longer equals source page N, so `source_page`/`source_bounding_box` on each block is what lets the app insert "Original page 152" markers and power the side-by-side review screen.
- **Source comparison becomes trivial** — clicking a reflowed block and highlighting its source region is a lookup, not a new subsystem.

## 3. PDF classification pipeline (`PDF-001..007`)

A PDF page is one of four kinds, and the *first* operation on any page is classification — never OCR-by-default.

```text
Native/born-digital:
  PDF page → native text/layout extraction → semantic blocks → DocumentIR

Scanned:
  PDF page → render at OCR resolution → layout + OCR →
  reading-order reconstruction → DocumentIR

Mixed:
  native text ───────────┐
                          ├→ reconcile/deduplicate → DocumentIR
  OCR missing regions ────┘

Broken-digital:
  detected via implausible extraction → treated as scanned page
```

Classification signals: presence/plausibility of native text, page-object geometry, raster-image coverage, rotation, and character-count sanity. A PDF rendering/inspection library provides the low-level primitives (text extraction, object bounds) needed for this diagnostic stage.

Validation runs **after** parsing every page, independent of which path was taken:
- output isn't inexplicably empty,
- OCR didn't duplicate an existing native text layer,
- block reading order is geometrically plausible,
- significant image regions are accounted for,
- table blocks have plausible structure,
- text isn't dominated by replacement/gibberish characters,
- a multi-column page wasn't flattened top-to-bottom across both columns.

These are application-level checks (`OCR-005`), not something delegated blindly to a single model's own confidence score.

## 4. OCR engine abstraction and routing (`OCR-001..007`)

```python
class DocumentOcrEngine(Protocol):
    def capabilities(self) -> EngineCapabilities:
        ...

    def analyze_page(
        self,
        image: PageImage,
        *,
        language_hints: tuple[str, ...],
        cancellation: CancellationToken,
    ) -> EnginePageResult:
        ...
```

```text
Engine A (default, CPU-friendly)
Engine B (optional, maximum accuracy)
Engine C (future / benchmark-only)
        │
        ▼
EnginePageResult
        │
        ▼
DocumentIR
```

Routing modes exposed to the user (`UI-001` keeps this out of the primary screen):

| User setting | Internal behavior |
|---|---|
| Automatic | Native-first; lightweight OCR when needed; escalate difficult pages |
| Fast | Prefer the lightweight recognition/layout pipeline |
| Maximum accuracy | Permit the heavier document-VLM-class model on difficult structured pages |

The default installer ships only the lightweight, CPU-friendly engine pack. The maximum-accuracy pack is an optional, separately downloaded model, verified against a hash manifest before load (`SEC-006`, `OCR-003`). Platform support for the maximum-accuracy pack is only claimed after it is packaged and validated per-platform (`PKG-001`) — do not assume "the framework is cross-platform" implies the model stack is.

### 4.1 Implemented recognition stack and remaining work

The current baseline is `rapidocr-onnxruntime==1.4.4`, using the three ONNX models bundled in its wheel: PP-OCRv4 detection, mobile-v2 orientation classification, and PP-OCRv4 Chinese/English recognition. `models/manifest.py` and `sbom.json` pin the observed bytes; the adapter verifies all three SHA-256 values before initialization. Python release environments are constrained to 3.11–3.12, matching the runtime's published compatibility range: https://pypi.org/project/rapidocr-onnxruntime/1.4.4/.

Layout, column ordering, and table reconstruction currently use application heuristics, not PP-StructureV3 inference. The recognizer does not advertise Arabic or full document-layout support. CPU inference uses at most eight intra-operation threads and one inter-operation thread via the runtime's actual flat configuration keys. No GPU dependency is required by the base distribution; packaged RTX acceleration remains unverified.

Maximum accuracy currently delegates to the standard adapter and attaches an explicit warning. It must not be described as VLM inference or automatically mark a page verified. The earlier layout/table/VLM catalog entries did not correspond to integrated, verified runtime artifacts and have been removed. A genuine optional higher-accuracy pack and verified Arabic recognition remain required work (`OCR-002..003`, `LANG-002`), subject to code/weight license review and corpus validation.

PaddleOCR structure models, Docling, and optional VLM adapters are candidates, not shipped features. Existing exclusions of olmOCR, Surya, and MinerU from the default distribution remain in effect until a fresh `LIC-002` review. Any future model choice must have a real artifact, verified license and digest, Windows/Linux execution evidence, and quality results on the project corpus.

## 5. Image handling (`IMG-001..003`)

```text
Original embedded asset
        ↓ if unavailable
High-quality cropped page rendering
        ↓ if structure is unknowable
Full original source region/page fallback
```

Prefer lossless extraction of the original embedded image object when present; fall back to rendering the source region at a suitable resolution when it isn't recoverable as a discrete asset. Aspect ratio is never distorted at any tier.

## 6. Tables and footnotes (`TBL-xxx`, `FN-xxx`)

Tables: enlarged semantic table → landscape/split presentation → accessible linearized text or retained source-table image + extracted text. Never silently collapse into scrambled prose.

Footnotes: body prose and footnote blocks are distinguished during extraction and their relationship preserved through reflow; rendered as large-print notes beneath the relevant content or as endnotes depending on the output preset. Minimum readable sizes are enforced for footnotes/captions/tables regardless of the ratio implied by the source page's original typography (`FN-002`).

## 7. Office and legacy formats (`OFF-001..003`)

DOCX/PPTX are imported directly into `DocumentIR` with structure preserved. DOC/PPT go through an isolated, headless legacy-format bridge that converts them into a modern intermediate first — OpenLargePrint does not implement the old binary formats itself. That bridge process runs under a disposable profile, is invoked with argument arrays (never shell string interpolation), and supports timeouts and full process-tree termination, because it is parsing untrusted input (`SEC-008`).

## 8. Output renderers (`OUT-001..011`)

All three primary outputs (DOCX, Reader, large-print PDF) are pure functions of `DocumentIR` plus a style/preset — never of the original file directly, and never of each other.

- **DOCX** — first-class, editable output matching the workflow the target user already knows: open, read, adjust if needed, print.
- **Reader** — semantic view; changing 20pt → 28pt is a style change against `DocumentIR`, not a re-extraction. Exposes at minimum: text size (A−/A+), line spacing, reading width, theme, and a heading/page-marker navigation sidebar.
- **Large-print PDF** — generated by reflowing `DocumentIR` into a new single-column layout at the chosen size; never produced by scaling the original PDF page in place.

Text-size presets (`OUT-006`):

| Preset | Body text | Line spacing |
|---|---:|---:|
| Comfortable | 18 pt | 1.4 |
| Large (default) | 20 pt | 1.5 |
| Extra Large | 24 pt | 1.5 |
| Very Large | 28 pt | 1.55 |
| Custom | any sensible value | custom |

### 8.1 Paper size and print export (`OUT-007..011`)

- The large-print PDF exporter takes paper size as an explicit parameter alongside the text-size preset — **A4 by default**, **A3** as a first-class alternate. Choosing A3 re-runs reflow against the larger physical page (a different target width and margins), rather than scaling an A4-authored page up; a naive scale-up exaggerates margins and line length instead of producing a genuinely well-proportioned large page.
- DOCX export sets its page size to match the same choice, so opening the file in a word processor already reflects the intended paper size.
- Both PDF and DOCX exports embed the true physical page dimensions for the chosen size. The export screen carries a short, plain-language reminder to print at 100%/actual size rather than "fit to page" — printer-side scaling would otherwise silently defeat the chosen text size.
- From the Reader, the user can select one or more pages or a contiguous range and export just that selection as its own print-ready file, at either paper size, independent of exporting the whole book. Because every export is a pure function of `DocumentIR` plus parameters (§2), this "export just this chapter, bigger" path re-renders from the already-built `DocumentIR` — it never re-extracts or re-runs OCR, which is what makes it fast and reliable rather than a special one-off feature.
- The paper-size choice lives on the primary export/conversion screen (`UI-006`), not behind "More options" — unlike OCR-engine internals, it directly determines whether the printed page is actually usable to the reader.
- **Color fidelity & Monochrome print toggle (`OUT-001`, `OUT-003`)**: By default, documents retain their source color attributes across both PDF and DOCX exporters. For users outputting to black-and-white laser printers, an optional `monochrome: true` setting forces all typography to pure black (`#000000`), table borders to solid black, and raster image assets to contrast-enhanced grayscale, eliminating muddy halftone dithering on monochrome toner printers.

### 8.2 Export transactions and searchable originals

Pipeline exports write to a sibling temporary file and atomically replace the destination only after successful completion and a final cancellation check. Selecting the original input as the destination is rejected. Source-page selections are validated against real page counts; malformed, empty-list, reversed, and out-of-range selections fail explicitly.

The optional searchable-original operation (`OUT-004`) is distinct from the three reflow exporters: it preserves the sanitized source PDF objects and adds invisible OCR overlays only to text-free pages. Its `DocumentIR` is a page inventory, not a reconstructed document. It preserves selected-page dimensions and native content without rasterizing the original. Mixed/broken existing text-layer repair remains open; this operation must not claim that capability.

PDF table body rows may split within a row across pages while headers repeat. Source-page rasterization is bounded before allocation to 16 million pixels and the existing dimension safety limits; resolution decreases for oversized pages. When extraction fails or yields no usable content, a bounded original-page image is retained. If even rendering fails, the output explicitly flags the missing page and directs the reader to the original.

## 9. IPC and job model

Rust/Tauri bridge ↔ Python sidecar communicate over JSON-Lines. The bridge exposes only narrow, typed commands to the webview — never a general shell or filesystem API (`SEC-005`).

```text
Tauri desktop process
        │
        ▼
React accessibility UI
        │
        ▼ narrow typed commands
Rust/Tauri bridge
        │
        ▼ JSON-Lines IPC
Python processing sidecar
        │
        ├── file validation
        ├── PDF classifier
        ├── native extraction
        ├── OCR engine router
        ├── Office import
        ├── DocumentIR normalization
        ├── validation
        └── exporters
```

The sidecar reads cancellation and health commands while a single worker processes a document, keeping PDFium work serialized. Other commands during active processing receive a busy response. Output events are serialized with a lock. Durable crash-resume checkpoints remain unimplemented; current checkpoints are progress/review events. Jobs checkpoint per page or in small chunks (`UI-003`): a failed page is marked for review and preserved in its original form; the rest of the document is not discarded.

## 10. Threat model and security boundaries

Every input file is untrusted (`SEC-001..004, 007, 008`). Concretely:

- Content-based type validation — never trust the file extension.
- No active-content execution: PDF JavaScript, Office macros, embedded attachments, and document-controlled external resources never run.
- Bounded decompression/raster dimensions to prevent resource-exhaustion from a malicious file.
- Each job gets a disposable, randomly-named working directory.
- The webview never receives a general shell-command or unrestricted filesystem bridge.
- Downloaded models are pinned and hash-verified before load.
- Logs never contain extracted text, images, or document contents.
- Subprocesses (LibreOffice, OCR) run with argument arrays, timeouts, and full process-tree termination — never shell string concatenation.
- After model installation, a standard conversion produces zero network traffic, verifiable in CI (`SEC-009`).

## 11. Testing strategy and benchmark corpus (`QA-001..003`)

Quality is judged against a project-owned, rights-safe benchmark corpus rather than upstream leaderboard numbers alone:

| Test document | What it catches |
|---|---|
| Born-digital English PDF | unnecessary OCR / exact text preservation |
| Two-column law page | reading order |
| Legal footnotes | body/note separation |
| Scanned English page | baseline OCR |
| Arabic scan | RTL OCR |
| Mixed Arabic/English | bidi assumptions |
| Scanned table | structure reconstruction |
| Images + captions | asset association |
| Rotated page | orientation |
| Skewed page | preprocessing |
| Poor low-resolution scan | difficult OCR |
| Mixed digital/scan PDF | selective OCR |
| Roman + Arabic page numbering | logical page labels |
| Huge/malformed PDF | resource/security handling |
| DOCX | style/footnote/image import |
| PPTX | text box/image order |
| Legacy DOC/PPT | legacy-format bridge |

Track separately: character error rate, word error rate, reading-order correctness, table-structure correctness, image retention, page-anchor fidelity, speed, and peak RAM/VRAM. Do not compress these into one accuracy number.

### 11.1 Measurement limitations

CER and WER are calculated only when a reference transcript exists; otherwise they are null/N/A. WER uses token-level Levenshtein distance and may exceed 1 when insertions dominate. Reported reading-order/table scores remain plausibility heuristics, not ground-truth correctness. RAM is the process lifetime peak, excludes child processes, and is not an isolated per-case measurement. VRAM is unmeasured. A completed conversion is reported separately from fidelity acceptance.

The generated corpus is a smoke-test corpus, not release-quality coverage: the mixed-bidi, mixed-digital/scan, Arabic font rendering, rotated-content, and image-reference fixtures need stronger real-content ground truth. Real rights-safe books, annotated structures, long-document stress tests, and target-machine measurements remain release blockers.

## 12. Licensing enforcement as code (`LIC-001..002`)

CI generates an SBOM / license inventory with fields: component, version, code license, model-weight license, download source, SHA-256, native code (y/n), network behavior, and whether it parses untrusted content. A dependency whose code and model-weight licenses differ, or that imposes commercial thresholds, requires an explicit recorded decision before it can become part of the default distribution.

## 13. Accessibility implementation notes (`A11Y-001..005`)

- Primary controls target 44–48 CSS px (exceeding the WCAG 2.2 24×24px minimum).
- Layout and controls remain usable and undistorted at 200% text enlargement.
- Full keyboard operability with visible focus; at least one screen reader in the test matrix.
- High-contrast and reduced-motion modes supported; file selection never depends solely on drag-and-drop.
- RTL rendering is tested in the UI itself, not only in exported documents.

## 14. Visual design direction (avoiding the generic AI look)

This product's UI is a working tool for someone who reads for hours, not a marketing site — but the visual craft bar still applies to every screen: the file picker, the options screen, the progress screen, the review screen, and the Reader. The full checklist is in `AGENTS.md §7`; `VIS-001..004` in `SPEC.md` make it a release gate. This section is the positive direction the checklist is meant to enforce.

### Ground the design in what this actually is

This is closer to a library or bookbinding object than a SaaS dashboard. The audience is one specific low-vision reader working through law books, not a generic user base. Let the material culture of paper, type, and reading — not tech-dashboard chrome — inform typography, color, and layout. A calm, legible, unhurried interface serves this reader better than anything that reads as a product demo.

### Process, before writing any UI code

1. **Token system first.** Write down a 4–6 color palette as actual named hex values (not "primary/secondary" placeholders), the typeface(s) and their roles (one or two families, clearly distinct if two), a one- or two-sentence layout concept per screen, and the design principles specific to this product.
2. **Review against the brief.** For each choice, ask whether it's what any similar app would default to, or a decision made for this reader and this content. Revise anything that's a default rather than a choice, and note what changed and why.
3. **Build, then critique.** Screenshot every finished screen and check it against `AGENTS.md §7` before calling it done.

### Shipped token system (as implemented in `ui/src/styles/theme.css`)

- **Palette**: warm sepia backgrounds (`#f3efdf` primary, `#e9e5d8` surface, `#dddcca` raised), ink-toned text (`#2d261e` primary), and an olive accent (`#485a34`, hover `#344425`) chosen for reading comfort rather than as a default accent; a high-contrast dark theme mirrors the same hues. Warning/success tones are reserved for semantic states.
- **Typefaces**: Source Sans 3 (bundled, OFL) as the interface family with a variable 200–900 weight range; Noto Sans Arabic (bundled, OFL) for Arabic UI and Reader text; Georgia as the Reader serif option. Both bundles ship their OFL license files and are recorded in `sbom.json`.
- **Scale and targets**: rem-based type scale so the 200% text-enlargement setting scales chrome and Reader together; primary controls target 48 CSS px (`A11Y-001`); focus rings are 3px in the accent color.
- **Structure**: format and text-size choices are flat bordered option strips rather than repeated cards; the export destination lives behind a "Save location" disclosure to keep the main flow at three decisions (`UI-001`); reduced-motion and forced-colors media queries are active.

### Known AI-generated-design tells to avoid as unexamined defaults

- A warm cream background with a high-contrast serif display and a terracotta/warm-clay accent.
- A near-black background with a single bright acid-green or vermilion accent.
- A broadsheet layout of hairline rules, zero border-radius, and dense newspaper-style columns.
- The "SaaS-card kit": content chopped into identical rounded cards, one border-radius used everywhere regardless of hierarchy, the same soft grey drop shadow under every card, gradient washes as decoration.
- Template chrome that shows up regardless of subject: tracked-out ALL-CAPS eyebrow labels above headings, meta text joined with middle dots, "WORD — fragment" labels with a spaced em dash, a tinted near-black standing in for true black, a monospace face for small data labels, a decorative arrow appended to buttons that don't navigate anywhere.

None of these are banned outright — they're defaults, and a deliberate choice for a specific reason is different from reaching for one because it's familiar. The test is whether the choice was made for this product or would show up in any similar app regardless of subject.

### What this means for OpenLargePrint specifically

- No blue/purple default accent, no gradient hero, no glassmorphism, no glow — the full list is in `AGENTS.md §7`.
- Typography is not a footnote here: the whole product is about text legibility, so type choices (family, weight range, scale, line length, line height) deserve the same deliberate attention a book designer would give them, both for the small-scale UI chrome and for the large-print output itself.
- Motion should answer the user's action (a job completing, a page turning) rather than decorate the screen. Fade-up-on-scroll and hover-scale effects serve no one here.
- Copy is instruction for a non-technical reader, not marketing copy: plain verbs, sentence case, exact description of what a control does ("Convert," "Export as A3"), never sales language.
- Empty and error states get specific, real language ("Page 317 could not be recognized reliably — the original page has been preserved," not a generic icon and "Something went wrong!").

## 15. Roadmap (vertical slices, not infrastructure-first)

| Phase | Deliverable |
|---|---|
| Foundation | Repo, CI, Tauri/React shell, accessible UI primitives, Python sidecar |
| Canonical model | `DocumentIR`, schema tests, sidecar protocol |
| Digital PDF | Native extraction, images, page anchors, DOCX export |
| Scan OCR | Default OCR/layout engine integration |
| High accuracy | Optional maximum-accuracy model pack |
| Review | Original/reflow side-by-side, warning navigation, per-page retry |
| Reader | Large semantic view |
| Complex structure | Tables, footnotes, multi-column, captions |
| Languages | Arabic/RTL and mixed-script release corpus |
| Office | DOCX/PPTX and legacy-format bridge |
| PDF output | Reflowed large-print PDF |
| Hardening | Fuzzing, resource limits, offline verification, license/SBOM |
| Packaging | Windows/Linux/macOS validated installers |

Milestone 1 proves the core hypothesis with no OCR at all: one healthy digital PDF → extract exact text + images → `DocumentIR` → 20pt DOCX. Milestone 2 proves the abstraction holds under OCR: one scanned PDF → OCR/layout → the *same* `DocumentIR` → the *same* DOCX exporter, unmodified.
