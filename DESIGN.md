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

Schema version 1.1.0 (`SCHEMA_VERSION` in `ir/models.py`).

```text
Block
  id
  type                 # title | heading | paragraph | list | quote | aside |
                        # footnote | table | image | caption | page_marker
  text                 # may contain "\n" for entries set apart on one line;
                        # "______" marks an answer blank
  level                # heading level 1-3, assigned document-wide by size
  language
  text_direction        # ltr | rtl
  source_page
  source_bounding_box   # merged blocks carry the union of their sources
  extraction_method      # native | ocr_fast | ocr_maximum | office_import
  confidence
  warnings[]            # plain-language notes shown to the reader
  image_asset            # the picture, or a crop of the original lines
  table_structure        # present if type == table
  list_marker            # the source's own marker ("1", "a)", "A:")
  indent_level           # 0-6
  styles[]               # inline bold / italic / underline spans
  role                   # finer meaning: figure_text, dialogue, contents,
                        # running_text, page_number, page_note, edge_text
```

Page-level facts that are not reading content (printed page number, running
heads, text bleeding in from the facing page, hidden text layers) live in
`PageMetadata.details`, so they never interrupt the text but are not lost.

`DocumentIR` itself is versioned (`DOC-003`) with schema tests, so a change to one importer or exporter can't silently break another.

### 2.2 Why this matters

- **Engines become replaceable** — swapping the OCR model pack only touches the engine adapter.
- **Enlargement becomes deterministic** — the DOCX/Reader/PDF exporters style semantic blocks; they never need to know whether a paragraph came from OCR, native PDF text, DOCX, or PPTX.
- **Provenance is preserved** (`PDF-006`, `OUT-005`) — reflowed page N no longer equals source page N, so `source_page`/`source_bounding_box` on each block is what lets the app insert "Original page 152" markers and power the side-by-side review screen.
- **Source comparison becomes trivial** — clicking a reflowed block and highlighting its source region is a lookup, not a new subsystem.

## 3. PDF pipeline (`PDF-001..007`)

Implemented in `importers/pdf/` (`native.py` drives it). Each page goes through
the same steps; a page that fails at any step is replaced by its original page
image with a plain note, and the rest of the book continues.

```text
page ──► 1. read the page's own text, glyph by glyph (textlayer.py)
           │   visible text?  ── yes ──► native page (never recognised again)
           │   no text / hidden layer / garbled ──► scanned page
           ▼
         2. render at 150 dpi (300 dpi when recognising) and find layout regions
           │   PP-DocLayoutV2 (layout/detector.py): titles, text, lists,
           │   tables, pictures, captions, footnotes, headers, page numbers,
           │   and the order to read them in
           ▼
         3. words: native glyphs, or recognised words (scanned.py),
           │   plus recognition of empty text regions and picture text on
           │   native pages (mixed pages)
           ▼
         4. ruling lines on the render (rules.py): answer blanks,
           │   underlines, table grid lines
           ▼
         5. assemble blocks (assemble.py, tables.py) ──► DocumentIR
```

**1. Text layer.** Words are built from PDFium character boxes: a word ends at
a space character, at a gap clearly wider than the line's own letter spacing,
or at a font change. Ligature glyphs are expanded (fi, fl, ffi), phantom spaces
inside ligatures are dropped, symbol-font and private-use glyphs are mapped to
standard characters (`glyphs.py`), and `/Rotate` pages are mapped into display
space. Text drawn in an invisible render mode, or painted underneath a later
page-covering picture (an earlier tool's OCR layer), is counted as hidden: that
page is recognised again rather than trusted. Arabic stored in display order is
flagged, kept as stored, and shown next to the original page.

**Routing.** Native if the page has visible text (at least 40 characters when
more than half the page is a picture) and the text is not mostly replacement
glyphs; otherwise recognised. "Native text only" never recognises; a scanned
page is then kept as its page image with a note.

**2. Layout.** `PPDocLayoutDetector` runs PP-DocLayoutV2 through ONNX Runtime
using rapid-layout's pre/post-processing. Regions are in page space (points,
y down) and converted to IR coordinates only when blocks are made. When the
model file is missing or damaged, `HeuristicLayoutDetector` is used: no model
regions, but embedded pictures are taken from the PDF's image objects, ruled
tables are found from their grid lines, and text is ordered by the geometric
XY-cut below, so nothing is dropped.

**5. Assembly.** Words go to the region holding most of them. Inside regions
the assembler splits side-by-side columns, paragraphs, numbered and lettered
items (hanging indents), dialogue lines (speaker marked), run-in bold headings
and numbered headings set larger than the text. Bold/italic/underline inside a
sentence become inline styles. Running heads and page numbers that repeat on
several pages move to page details; footer text that appears once stays as a
page note. Footnotes close the page. A "Figure 4.1" line beside a picture is its
caption. Right-to-left pages are reordered right to left. Heading levels are set
for the whole document from type size against the body median.

Reading order without model guidance uses an XY-cut: horizontal bands are
joined while together they still have a clear vertical gutter, then each column
is read top to bottom. A full-width title or footnote starts a new stretch.

**Confidence.** Recognised blocks below 0.75 get a review note; below 0.7 the
original lines are cropped and shown with the text; a page below 0.5 keeps its
whole page image. Picture-only pages are shown as a picture, without an alarm.

## 4. Recognition (`OCR-001..007`)

```python
class DocumentOcrEngine(Protocol):
    def capabilities(self) -> EngineCapabilities: ...
    def analyze_page(self, image, *, page_num, language_hints, cancellation) -> EnginePageResult: ...
```

`ocr/paddle_engine.py` (`PaddleRapidOcrEngine`) uses RapidOCR 3.9.2 with
PP-OCRv6 small detection and recognition (Latin and Chinese script, shipped in
the RapidOCR wheel) and PP-OCRv5 mobile Arabic recognition (shipped in
`models/weights`). It returns lines with word boxes; `scanned.ocr_words` maps
them back to words using the recognised line text, so the text stays exactly
as recognised. The router keeps one engine per script. Recognition runs in an
isolated subprocess (`ocr/worker.py`) that blocks sockets and name resolution.

Recognised text is never rewritten, by rules or by any generative model
(`OCR-007`). Uncertainty stays visible as notes and original-line crops.

There is one pipeline and it is bundled; there is no optional pack. "Maximum
accuracy" renders scanned pages at 400 dpi instead of 300 and is used when a
page is retried from the review screen.

**Models.** `models/manifest.py` pins every model by size and SHA-256:
`pp_doc_layoutv2`, `PP-OCRv6_det_small`, `PP-OCRv6_rec_small`,
`ch_ppocr_mobile_v2.0_cls` (inside the RapidOCR wheel) and
`arabic_PP-OCRv5_rec_mobile`. `scripts/fetch_models.py` downloads the two that
are not in a wheel for development and release builds; the sidecar build
refuses to run unless all five verify. At run time models are only looked up,
verified once per process, and never downloaded; rapid-layout and RapidOCR are
always given explicit paths so their own downloaders are never reached.

### 4.1 What has and has not been validated

- Native Latin and Arabic text extraction, mixed pages, tables, pictures and
  exercises: unit tests, the synthetic benchmark corpus (`QA-001`) and manual
  page-by-page review of eight real textbooks and scans.
- Latin-script recognition: corpus and real scans.
- Arabic recognition: the model is bundled and routed, and Arabic scans in the
  corpus convert, but its accuracy has not been measured on a real Arabic
  corpus. It must not be advertised as validated.
- A local generative model was considered and rejected: it could rewrite
  source text (`OCR-007`) and the layout model already provides the structure.

## 5. Pictures (`IMG-001..003`)

```text
one embedded image matching the region, no text over it ──► the original pixels
otherwise ──► the region rendered at the picture's own resolution (150-300 dpi)
scanned page ──► crop of the 300 dpi page render
```

Vector drawings the model did not mark are found by clustering path objects
and kept. Tiny decorative marks are skipped and counted in page details.
Aspect ratio is never changed; exporters enlarge pictures with the text, up to
2.2 times their pixel size.

## 6. Tables and footnotes (`TBL-xxx`, `FN-xxx`)

`tables.build_table` makes a grid from vertical ruling lines or, without them,
from white space that runs through every row. Rows follow horizontal rules, or
an empty first cell continues the row above. A bold first row becomes the
header; a one-row ruled table with empty rows below is a table to fill in.
Doubtful grids keep a crop of the source table. When no grid can be found the
rows are kept as lines with a note. Exporters show tables that fit as tables,
split wide ones into parts that repeat the first column, and list very wide
ones row by row, always with a note and with the caption kept.

Footnotes: model footnote regions, numbered footer text, and small numbered text
at the foot of the page become footnote blocks at the end of their page.
Minimum readable sizes are enforced for footnotes/captions/tables (`FN-002`).

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

The sidecar reads cancellation and health commands while a single worker processes a document, keeping PDFium work serialized. Other commands during active processing receive a busy response. Output events are serialized with a lock. CPU recognition runs in a separate spawned process, reused across pages and closed after import. A 120-second recognition deadline includes model initialization; cancellation is checked every 100 ms. A timed-out or failed recognition worker is terminated and recreated for the next page. This isolates native OCR hangs from the command loop and works with Windows spawn and the frozen sidecar entry point. Raster input travels through a disposable local PNG and results through local pipes, with no network transport. Mixed pages mask native text regions before recognition; recognition failures retain native text and an original-page image for review (`PDF-002..004`, `UI-002..003`, `SEC-008`).

Durable crash-resume checkpoints remain unimplemented; current checkpoints are progress/review events. Jobs checkpoint per page or in small chunks (`UI-003`): a failed page is marked for review and preserved in its original form; the rest of the document is not discarded. Native PDF parsing and rendering are not yet isolated behind per-page deadlines.

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

CER and WER are calculated only when a reference transcript exists; otherwise they are null/N/A. WER uses token-level Levenshtein distance and may exceed 1 when insertions dominate. Separate reference measurements compare authored reading-order units, table cells, and original image pixels including dimensions. Missing/misrecognized reading units reduce that reference score as well as inversions. Unexpected reconstructed tables are structural mismatches. The existing order/table plausibility heuristics remain separate. RAM is the process lifetime peak, excludes child processes, and is not an isolated per-case measurement. VRAM is unmeasured. A completed conversion is reported separately from fidelity acceptance.

The generated corpus is a smoke-test corpus, not release-quality coverage. It now has actual mixed-script and native/scanned content, nonblank rotated scans, distinct embedded originals, nonoverlapping columns, fitting Arabic text, and independent per-case transcripts/reference manifests. Real rights-safe books, expert-annotated structures, robust Arabic recognition, long-document final-GUI stress tests, and target-machine measurements remain release blockers.

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
| Packaging | Windows and Linux installers, tested in CI |

Milestone 1 proves the core hypothesis with no OCR at all: one healthy digital PDF → extract exact text + images → `DocumentIR` → 20pt DOCX. Milestone 2 proves the abstraction holds under OCR: one scanned PDF → OCR/layout → the *same* `DocumentIR` → the *same* DOCX exporter, unmodified.

## 16. Packaging (`PKG-001..002`)

The engine is frozen with PyInstaller (`packaging/build_sidecar.py`) together
with its models and fonts. Windows uses a one-directory engine with the
`_internal` runtime beside it, inside an NSIS per-user installer and a portable
zip. Linux uses a one-file engine inside an AppImage, an RPM and a DEB. The
release workflow builds each on its own runner, converts test documents with the
packaged engine (and on Windows with the silently installed copy and the
portable copy), and publishes only when both platforms pass, with
`SHA256SUMS.txt`.

Windows signing is optional (`SIGNING.md`): with a certificate thumbprint
configured, every executable is signed before the installer is assembled;
without one the release is unsigned. macOS is not built or supported.
