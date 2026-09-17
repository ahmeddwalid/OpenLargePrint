# OpenLargePrint — PROMPT.md (Master Project Brief)

Give this file to a fresh coding agent as its starting brief. It summarizes the mission, the chosen architecture, and where to find the detailed contracts. It is deliberately not exhaustive — `SPEC.md`, `DESIGN.md`, and `AGENTS.md` are exhaustive; this is the orientation.

## Mission

Build **OpenLargePrint**: an application that takes ordinary documents — **PDF is the highest-priority format**, with Word (.doc/.docx) and PowerPoint (.ppt/.pptx) required as secondary formats, including scanned and dense two-column law books — and turns them into genuinely readable large-print versions for someone with low vision who is not a technical person. Their old workflow was opening a Word document, bumping the font size, and printing it; that broke down once their course material started arriving almost entirely as PDF, and they can't be expected to manage OCR settings, models, or file conversions themselves. The core problem this solves is not "make the text bigger." A 12-point two-column law-book page enlarged in place to 20-point type overlaps and clips. The application has to **understand the document's structure and rebuild it** at the new size, single-column, with headings, lists, tables, footnotes, and images preserved in the right relationship to each other — while the experience from the user's side stays as simple as "upload a document, get one back with bigger text."

The most important design instinct to hold onto: **do not treat OCR as the application — treat OCR as one recovery technique inside a document-reconstruction system.** If a page already has exact, extractable text, use that. Only recognize what genuinely needs recognizing.

## Chosen architecture (do not relitigate without strong reason)

- **Desktop shell:** Tauri 2 — native installer, file dialogs, OS integration, a narrow secure bridge to the backend.
- **UI:** React + TypeScript + Vite — a deliberately large, accessible interface, not a conventional dense desktop UI.
- **Processing engine:** a Python sidecar (bundled via Tauri's sidecar mechanism, so the end user never installs Python or opens a terminal) handling OCR, PDF parsing, Office conversion, and document reconstruction.
- **Canonical model:** a single custom `DocumentIR` that every importer normalizes into and every exporter reads from. This is the decision that keeps the codebase maintainable as OCR engines and input formats change over time — see `DESIGN.md §2`.
- **Primary output:** a large-print DOCX (editable, printable, familiar). Secondary outputs: an in-app Reader (instant re-styling, no re-extraction) and a reflowed large-print PDF.

Why not a website: the workload — local OCR models, PDF/Office parsing, LibreOffice conversion — needs a real runtime and needs to run offline by default for privacy. A static site can't host this; a server-hosted version would also mean uploading potentially sensitive documents (e.g. a person's private law-school materials) to a third party, which this project explicitly avoids.

## Product priorities, in order

1. **Correctness over cleverness.** Native text extraction beats OCR beats a fluent-but-wrong reconstruction, every time. Never let a generative model "smooth over" recognized text — for legal material, a wrong character can change a date, an amount, or a negation.
2. **Never lose the user's document.** A page that can't be processed reliably gets flagged for review with the original preserved — it never disappears, and it never silently corrupts the rest of the conversion.
3. **Accessibility is the product, not a feature.** Big, keyboard-operable, screen-reader-friendly, works at 200% zoom, Arabic/RTL tested from day one.
4. **Simplicity on the surface, power underneath.** The home screen is "choose a document → choose a text size → convert." Everything about OCR engines, models, or DPI lives behind "More options," never on the main screen.
5. **Local-first, offline by default.** After models are installed, a normal conversion produces zero network traffic.
6. **Traceability to the source.** Every reflowed page should be able to point back to "Original page N," because a law-book reader still needs to reference the official pagination.
7. **Printed output is a first-class goal, not an afterthought.** Default to A4; make A3 a first-class option, for the whole book or for just a chosen page/section, since paper size directly affects how easily the reader can read a printed page. Exported files must print correctly at 100% scale — see `SPEC.md OUT-007..011`.
8. **Real visual craft, not template chrome.** Every screen has to look like it was designed for this reader and this content, not assembled from generic AI-interface defaults — see `DESIGN.md §14` and the gate in `AGENTS.md §7`.

## Where the details live

- **`SPEC.md`** — the full requirements list with stable IDs (`PDF-xxx`, `OCR-xxx`, `DOC-xxx`, `OFF-xxx`, `OUT-xxx`, `IMG-xxx`, `TBL-xxx`, `FN-xxx`, `LANG-xxx`, `UI-xxx`, `A11Y-xxx`, `SEC-xxx`, `PERF-xxx`, `QA-xxx`, `PKG-xxx`, `LIC-xxx`, `VIS-xxx`), acceptance criteria, and release criteria. This is the contract for "is it done."
- **`DESIGN.md`** — the architecture: `DocumentIR` schema, the PDF classification pipeline (native/scanned/mixed/broken), the OCR engine abstraction and routing modes, image/table/footnote handling, the Tauri↔sidecar IPC model, the threat model, and the benchmark-corpus testing strategy. This is the contract for "how is it built."
- **`AGENTS.md`** — behavioral rules for any coding agent working in this repo: testing requirements per layer, dependency/licensing policy, security and accessibility review checklists, document-integrity rules, and a list of anti-patterns specific to this project. This is the contract for "how do I work here."
- **`CLAUDE.md`** — a short, Claude-specific pointer to the three files above plus the non-negotiable invariants restated as a quick-reference.

## Build order (do not skip ahead)

Build in vertical slices, not infrastructure-first:

1. **Prove the core hypothesis with no OCR at all:** one healthy digital PDF → extract exact text and images → `DocumentIR` → 20pt DOCX. If this doesn't work cleanly, nothing downstream matters.
2. **Prove the abstraction holds under OCR:** one scanned PDF → OCR/layout recognition → the *same* `DocumentIR` → the *same* DOCX exporter, unmodified.
3. From there: mixed PDFs, source-page anchors, the Reader, tables, footnotes, Arabic/RTL, Office import (DOCX/PPTX, then legacy DOC/PPT via the LibreOffice bridge), the review UI, model management, security hardening, and packaging — in that rough order, per `DESIGN.md §14`.

## Definition of done (v1)

See `SPEC.md §6` for the full release criteria. In short: every `PDF-*`, `DOC-*`, core `OUT-*`, core `UI-*`, `A11Y-001..003`, and all `SEC-*` requirements pass their tests; the benchmark corpus passes on a CPU-only configuration; at least one Arabic and one mixed Arabic/English document convert correctly; malformed/malicious input is handled safely; and a standard conversion run produces zero network traffic.

## What not to do (the shortcuts that will quietly wreck this project)

- Don't OCR everything "to keep it simple" — it throws away exact text that already exists.
- Don't screenshot every page instead of extracting structure.
- Don't run OCR output through an LLM to make it read more smoothly.
- Don't drop a page that fails to process.
- Don't lose the mapping back to the original page.
- Don't flatten a table into unordered text.
- Don't give the frontend a general shell or filesystem bridge.
- Don't add a new OCR or parsing dependency without checking both its code license and its model-weight license.
- Don't shrink UI controls or hide the three-step main flow to cram in more settings.
- Don't claim a platform is supported just because the app framework compiles there — the packaged model stack has to actually pass the benchmark corpus on that platform first.
- Don't ship a screen with generic AI-interface defaults (gradient hero, SaaS-card kit, blue/purple accent, unmodified Inter/system font) — run every screen against the checklist in `AGENTS.md §7` before calling it done.
- Don't treat A3 printing as a bolt-on nice-to-have — it's a first-class export option for the whole book or a page selection, defaulting to A4.

Read `SPEC.md`, `DESIGN.md`, and `AGENTS.md` before writing the first line of code.
