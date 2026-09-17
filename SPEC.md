# OpenLargePrint — SPEC.md (Product Contract)

Status: Draft v0.1
Audience: any AI coding agent or human contributor implementing this product
Role of this document: this is the **source of truth for what the product must do**. `DESIGN.md` explains *how* it is built; `AGENTS.md` and `CLAUDE.md` explain *how agents must behave* while building it. If code conflicts with this file, the code is wrong.

Every requirement below has a stable ID. Reference these IDs in commits, PR descriptions, tests, and issue trackers (e.g. `Implements PDF-002`, `Fixes A11Y-003 regression`).

---

## 1. Problem statement

A person with low vision needs to read ordinary documents — most urgently, dense two-column law books distributed as scanned or born-digital PDFs — at a much larger, reflowed, single-column text size. Their prior workflow was to open a Word document, enlarge the font, and print it; that stopped working once their course material started arriving almost entirely as PDF, and they are not a technical person who can be expected to manage OCR settings, models, or file conversions themselves. Simply enlarging an existing page (zooming a PDF, bumping a font size in place) does not work either: fixed layouts overlap and clip at large sizes. The document must be **understood and rebuilt**, not just magnified — while the experience of using the tool stays as simple as "open it, get a bigger-text version back."

## 2. Non-negotiable principles

These override any individual requirement below if they ever conflict:

1. **Native text beats recognized text.** If exact Unicode text already exists in the source, use it. Never re-OCR text that is already correctly extractable.
2. **Never silently "fix" recognized text with a generative LLM.** Uncertain OCR output stays visibly uncertain and traceable to its source region. Fluent-sounding but silently altered legal or factual text is worse than visible uncertainty.
3. **Never drop content on failure.** One unrecognizable page must degrade to "flagged for review," never to data loss for the rest of the document.
4. **Preserve source-page provenance.** Every reflowed block should be traceable back to its original page number/region.
5. **Local-first and offline by default.** No document content leaves the user's machine during a normal conversion.
6. **Accessibility is not a layer added later.** UI decisions (control size, contrast, text scaling) are first-class requirements, not polish.

## 3. Supported inputs and outputs

**Inputs, in priority order:** **PDF** (born-digital, scanned, mixed, and "broken" text layers) is the primary, highest-priority format — it is what the target reader's law books actually arrive as, and PDF quality must never be traded away in favor of the other formats. DOCX and PPTX are required for v1 as secondary formats. Legacy DOC and PPT are required for v1 via the LibreOffice bridge (`OFF-002`) but may receive less polish than PDF if a genuine trade-off is unavoidable.

**Outputs (per job, user selects which to generate):**
- Large-print **DOCX** (primary, editable, printable) — `OUT-001`
- In-app large-print **Reader** (semantic HTML-like view with instant re-styling) — `OUT-002`
- Reflowed large-print **PDF** (secondary, print-ready) — `OUT-003`
- Optional: original-layout **searchable PDF** (OCR text layer only, no reflow) — `OUT-004`

Print target for the large-print PDF/DOCX: **A4 by default**, with **A3** as a first-class alternate for the whole export or for a chosen page/section selection (`OUT-007..011`).

## 4. Requirements

### 4.1 PDF handling (`PDF-xxx`)

- **PDF-001** — The system must classify every page of an input PDF into one of: native/born-digital, scanned, mixed, or broken-digital, before choosing an extraction strategy. Classification runs on cheap signals (native text presence, character-extraction plausibility, raster coverage, rotation) — not by running OCR first.
- **PDF-002** — For native/born-digital pages, the system must extract exact existing text and layout rather than OCR the rendered page image. OCR must not run on a page confirmed to have usable native text.
- **PDF-003** — For scanned pages, the system must render at an OCR-appropriate resolution, run layout + text recognition, and reconstruct reading order (including multi-column pages) before handing blocks to the shared normalization stage.
- **PDF-004** — For mixed pages, the system must reconcile native text extraction with OCR of only the regions lacking native text, and deduplicate overlaps.
- **PDF-005** — For broken-digital pages (text present but garbled, out of order, or implausible), the system must detect the failure and fall back to the scanned-page path rather than emitting garbled text.
- **PDF-006** — Every extracted block must retain its source page number and source bounding box.
- **PDF-007** — Rotated and skewed pages must be normalized before recognition; orientation must be recorded per page.

### 4.2 OCR and recognition (`OCR-xxx`)

- **OCR-001** — OCR engines must be implemented behind a common interface (capabilities + `analyze_page`) so any engine can be swapped without touching the rest of the pipeline.
- **OCR-002** — The system must ship at least one CPU-friendly OCR/layout pipeline as the default ("Automatic"/"Fast" modes) and support an optional higher-accuracy model pack for "Maximum accuracy" mode.
- **OCR-003** — The higher-accuracy model pack must be an optional download, never bundled in the base installer.
- **OCR-004** — OCR output must carry per-block confidence and warning metadata.
- **OCR-005** — A page whose recognized output is dominated by replacement/gibberish characters, has implausible reading order, or duplicates native text must be flagged for review rather than accepted silently.
- **OCR-006** — OCR must run entirely on-device for the default engine pack; any engine requiring a GPU-only or cloud dependency must be optional and never the default.
- **OCR-007** — Recognized text must never be passed to a generative LLM for "correction" or rewriting as part of the standard pipeline (ties to Principle 2 above).

### 4.3 Canonical document model (`DOC-xxx`)

- **DOC-001** — All importers (PDF extraction, OCR, DOCX/PPTX import, legacy Office import) must normalize into one shared `DocumentIR` representation. No exporter may special-case a specific importer's output.
- **DOC-002** — `DocumentIR` blocks must carry: type (title/heading/paragraph/list/quote/footnote/table/image/caption/page-marker), text or children, language, text direction, source page, source bounding box, extraction method, confidence, warnings, and (where applicable) image asset or table structure.
- **DOC-003** — `DocumentIR` must be versioned and covered by schema tests so importer/exporter changes cannot silently break compatibility.

### 4.4 Office and legacy formats (`OFF-xxx`)

- **OFF-001** — DOCX and PPTX must be imported with structure (headings, lists, tables, images, speaker notes where relevant) preserved into `DocumentIR`.
- **OFF-002** — Legacy DOC/PPT must be converted via an isolated headless LibreOffice bridge into a modern intermediate before entering the standard pipeline; OpenLargePrint must not attempt to parse legacy binary formats itself.
- **OFF-003** — The LibreOffice bridge must run under a disposable profile with a controlled adapter (argument arrays, timeouts, process-tree termination), since it parses untrusted input.

### 4.5 Output generation (`OUT-xxx`)

- **OUT-001** — DOCX export must apply the selected text-size/line-spacing preset, single-column reflow, and preserve document hierarchy (headings, lists, quotes, tables, captions).
- **OUT-002** — The Reader must re-style instantly (font size, line spacing, reading width, theme) without re-running extraction or OCR, because it operates purely on `DocumentIR` + CSS-equivalent styling.
- **OUT-003** — Large-print PDF export must be generated from `DocumentIR`, never by directly enlarging the original PDF page in place.
- **OUT-004** — Optional "searchable original PDF" output must preserve the original page appearance and add a text layer only; it must not attempt reflow.
- **OUT-005** — Every output format must support optional source-page markers ("Original page 152") inserted at the correct transition point in reflowed content.
- **OUT-006** — Text-size presets (minimum set): Comfortable 18pt/1.4, Large (default) 20pt/1.5, Extra Large 24pt/1.5, Very Large 28pt/1.55, and Custom. These are product presets, not medical/clinical claims, and must be labeled as such if surfaced to the user.
- **OUT-007** — The large-print PDF (and the DOCX page setup) must default to **A4** and must offer **A3** as a first-class alternate paper size for the same export, not a hidden or advanced-only setting.
- **OUT-008** — Choosing A3 must re-run reflow against the larger physical page (different target width/margins), never simply scale up an A4-authored page — a naive scale-up produces disproportionate margins and line length instead of a genuinely well-laid-out large page.
- **OUT-009** — Exported PDF and DOCX files must embed the true physical page dimensions for the chosen paper size, and the export screen must carry a short, plain-language reminder to print at 100%/actual size rather than "fit to page," since printer-side scaling would otherwise defeat the chosen text size.
- **OUT-010** — From the Reader, the user must be able to select one or more pages or a contiguous range and export just that selection as its own print-ready file, at either paper size, independent of exporting the whole document — for example, reprinting a single chapter at A3 without regenerating the whole book.
- **OUT-011** — The export/print action, including the A4/A3 paper-size choice, must be reachable from the primary conversion or Reader screen in at most two steps; it must not require opening a separate "advanced print settings" dialog.

### 4.6 Images (`IMG-xxx`)

- **IMG-001** — When the source PDF contains an embedded original image, it must be extracted losslessly rather than recreated via screenshot/render.
- **IMG-002** — When no embeddable original exists, the system must fall back to a high-quality cropped render of the source region, and finally to a full source-page fallback if structure cannot be determined.
- **IMG-003** — Image aspect ratio must never be distorted at any fallback tier.

### 4.7 Tables (`TBL-xxx`)

- **TBL-001** — Tables must first attempt an enlarged semantic table; if it cannot fit the target page width, fall back to landscape/split presentation; if still infeasible, fall back to an accessible linearized representation or a retained source-table image plus extracted text.
- **TBL-002** — A table must never be silently flattened into scrambled/unordered prose without a visible warning.

### 4.8 Footnotes (`FN-xxx`)

- **FN-001** — Footnotes must be distinguished from body text and their association preserved through reflow.
- **FN-002** — Reflowed footnote/caption/table text must respect enforced minimum readable sizes, not a fixed ratio mechanically inherited from the source document's original type-size ratio.

### 4.9 Language and direction (`LANG-xxx`)

- **LANG-001** — Language and text-direction metadata must be preserved end-to-end from extraction/OCR through every export format.
- **LANG-002** — Arabic (RTL) and mixed Arabic/English (bidi) documents must be part of the core test corpus from the first OCR milestone, not added later.

### 4.10 Interface behavior (`UI-xxx`)

- **UI-001** — The default/home flow must reduce to three visible decisions: choose a document, choose a text size, convert. All OCR-engine, DPI, model, or backend terminology must live behind an explicit "More options" / "Advanced" area, never on the primary screen.
- **UI-002** — Progress must report meaningful state ("Recognizing scanned text — page 85 of 512"), not a generic spinner, and must support cancellation.
- **UI-003** — Long documents must checkpoint per page or in small chunks; a single failed page must not discard already-converted pages.
- **UI-004** — A review screen must show the original source region and the converted large-print block side-by-side for any flagged page, with an option to retry at higher accuracy or accept as-is.
- **UI-005** — Failure messaging must be in plain language ("3 pages may need review"), never raw internal engine/model identifiers.
- **UI-006** — The primary conversion or Reader screen must offer an A4/A3 paper-size choice for the large-print PDF directly, without requiring the "More options"/Advanced area.

### 4.11 Accessibility (`A11Y-xxx`)

- **A11Y-001** — Primary interactive controls must meet or exceed a 44–48 CSS-pixel target size (deliberately exceeding the WCAG 2.2 24×24px minimum pointer target).
- **A11Y-002** — The interface itself must remain usable and undistorted at 200% text enlargement, consistent with WCAG 2.2's Resize Text intent (content and functionality both preserved).
- **A11Y-003** — The application must be fully operable by keyboard alone, with visible focus indicators, and must be tested with at least one screen reader.
- **A11Y-004** — The interface must support high-contrast and reduced-motion modes and must not rely on drag-and-drop as the only way to select a file.
- **A11Y-005** — RTL content must render correctly throughout the UI, not just in document output.

### 4.12 Security and privacy (`SEC-xxx`)

- **SEC-001** — All input files must undergo content-based type validation; a file extension must never be trusted on its own.
- **SEC-002** — No active content (PDF JavaScript, Office macros, embedded attachments, document-controlled external resources) may execute during conversion.
- **SEC-003** — Decompression, image dimensions, and archive contents must be bounded to prevent resource-exhaustion attacks from malicious input files.
- **SEC-004** — Every conversion job must run in a disposable, isolated working directory.
- **SEC-005** — The UI process must not expose a general shell-command or unrestricted filesystem bridge to the frontend webview; only narrow, typed commands are permitted.
- **SEC-006** — Downloaded models must be pinned by version and verified against a hash manifest before being loaded.
- **SEC-007** — Logs must never contain extracted document text, images, or user file contents.
- **SEC-008** — All child processes (LibreOffice, OCR subprocesses) must be invoked with argument arrays (never shell string concatenation) and must support timeouts and full process-tree termination.
- **SEC-009** — After required models are installed, a standard conversion run must generate zero network traffic; this must be verifiable in CI.

### 4.13 Performance and resource limits (`PERF-xxx`)

- **PERF-001** — The default ("Automatic"/"Fast") OCR path must be practical on an ordinary CPU-only laptop; GPU-only engines are never the default.
- **PERF-002** — Peak RAM/VRAM, and per-page speed must be tracked as first-class benchmark metrics, not folded into a single accuracy number.

### 4.14 Quality and testing (`QA-xxx`)

- **QA-001** — The project must maintain its own rights-safe benchmark corpus (see `DESIGN.md §Testing strategy`) rather than relying solely on upstream leaderboard claims.
- **QA-002** — Metrics must be tracked separately for character error rate, word error rate, reading-order correctness, table-structure correctness, image retention, page-anchor fidelity, speed, and peak memory.
- **QA-003** — Every OCR engine or model swap must be validated against the full benchmark corpus before becoming a default.

### 4.15 Packaging and platform claims (`PKG-xxx`)

- **PKG-001** — A platform (Windows/macOS/Linux) may only be marked "supported" after the full packaged pipeline — including the chosen OCR model pack — passes the acceptance benchmark corpus on that platform. Framework cross-platform capability is not sufficient evidence on its own.
- **PKG-002** — The base installer must not require the end user to install Python, open a terminal, or manage a virtual environment.

### 4.16 Dependency and licensing policy (`LIC-xxx`)

- **LIC-001** — Every dependency (code and, separately, any model weights) must have its license recorded in a machine-readable SBOM/license inventory (fields: component, version, code license, model-weight license, download source, SHA-256, native code, network behavior, whether it parses untrusted content).
- **LIC-002** — A dependency whose license terms differ for code vs. model weights, or which imposes revenue/MAU-based commercial licensing thresholds, must not become part of the default required distribution without an explicit, recorded decision.

### 4.17 Visual craft ("anti-slop") requirements (`VIS-xxx`)

- **VIS-001** — Every screen must pass the visual craft checklist in `AGENTS.md §7` before it is considered complete. The checklist covers decorative surfaces, layout, typography, color, motion, icons, copy, content/data authenticity, and completeness (no stubs, no placeholder text, no default browser chrome left in place). This is a hard gate, not a style preference — a screen that functions correctly but fails the checklist is not done.
- **VIS-002** — The interface must read as a deliberate, subject-grounded design (see `DESIGN.md §14`), not a templated default: no generic SaaS-card kit, no unmodified default type scale, no blue/purple gradient hero, no stock "trusted by" or testimonial content.
- **VIS-003** — All shipped copy must be real, specific, and free of placeholder text, generic names, unsourced statistics, and filler/marketing phrasing.
- **VIS-004** — The first-order acceptance test for any screen is: a screenshot of it should not read as AI-generated to someone who has seen a lot of AI-built interfaces.

## 5. Explicit non-goals (v1)

- Not a general-purpose OCR product or SaaS.
- Not a cloud service; not designed around multi-user hosting.
- Not a medical device; text-size presets are not clinical recommendations.
- Not a tool for bypassing DRM or copyright on the input documents themselves — the user is responsible for their right to convert the source material.

## 6. Release criteria (v1 "done")

A release is v1-complete when:
1. All `PDF-*`, `DOC-*`, `OUT-001..011`, `UI-001..006`, `A11Y-001..003`, and `SEC-001..009` requirements pass their tests.
2. The benchmark corpus (see `DESIGN.md`) passes on at least one CPU-only configuration with the default engine pack.
3. At least one Arabic and one mixed Arabic/English document convert correctly end to end.
4. A malformed/oversized PDF and a macro-laden DOCX are handled safely without crash or resource exhaustion (`SEC-002`, `SEC-003`).
5. Zero network traffic is observed during a standard offline conversion run (`SEC-009`).
6. A full-document export and a selected-pages export both produce correctly A4- and A3-sized print-ready output that prints accurately at 100% scale (`OUT-007..011`).
7. Every shipped screen passes the visual craft checklist (`VIS-001..004`).
