# OpenLargePrint — AGENTS.md

Status: Draft v0.1
Audience: **any** AI coding agent working in this repository, regardless of vendor or harness.
Precedence: `SPEC.md` defines what must be true; `DESIGN.md` defines how the system is structured; this file defines how an agent must behave while making changes. If an instruction here ever conflicts with `SPEC.md` or `DESIGN.md`, stop and flag the conflict rather than guessing.

---

## 1. Before you start any task

1. Read `SPEC.md` and `DESIGN.md` in full at the start of a session, not just the section that seems relevant — the non-negotiable principles in `SPEC.md §2` apply everywhere.
2. Identify which requirement ID(s) (e.g. `PDF-002`, `OCR-006`, `A11Y-003`, `SEC-009`) your change touches. Reference them in your commit message and PR description.
3. If a task seems to require violating a principle in `SPEC.md §2` or a security requirement in `SPEC.md §4.12`, stop and raise it instead of proceeding.

## 2. Repository conventions

- The Python processing engine must remain usable as a standalone library/CLI, independent of the Tauri shell. Do not add code that only works when invoked through the sidecar protocol.
- All importer output and all exporter input must go through `DocumentIR` (`DESIGN.md §2`). Do not add an importer→exporter shortcut that bypasses it, even "temporarily."
- New OCR or document-parsing engines are added as adapters implementing the shared engine interface (`DESIGN.md §4`), never as special-cased branches in the pipeline.
- Keep the primary UI decision tree at three visible choices (`UI-001`). New settings default to living behind "More options"/"Advanced" unless there is a specific, documented reason to promote one to the main screen.

## 3. Testing requirements

Every change must be validated against the layer(s) it touches:

- **Schema/IR changes** — run/extend `DocumentIR` schema tests (`DOC-003`).
- **Importer/OCR changes** — run the project benchmark corpus (`DESIGN.md §11`) and report the per-metric results (CER, WER, reading order, table structure, image retention, page-anchor fidelity, speed, peak RAM/VRAM) — not just a pass/fail.
- **Exporter changes** — verify output against at least one native-digital and one scanned sample, and confirm the Reader restyles without re-extraction (`OUT-002`).
- **UI/accessibility changes** — verify keyboard operability, visible focus, and behavior at 200% text scale (`A11Y-002`, `A11Y-003`); do not merge a control smaller than the 44–48px target (`A11Y-001`) without a documented exception.
- **Security-relevant changes** (file parsing, subprocess invocation, IPC surface) — add or update a test that a malformed/oversized/malicious input is handled safely, not just the happy path.
- **New dependency** — add its entry to the SBOM/license inventory (`LIC-001`) before merging.
- **Print/export changes** — verify the exported file's embedded page dimensions match the selected paper size (A4/A3) and print correctly at 100% scale; verify a page/range selection export produces only the selected content (`OUT-007..011`).
- **Any new or changed screen** — run it against the visual craft checklist (`§7`) and attach a screenshot before calling it done (`VIS-001..004`).

## 4. Dependency and licensing policy

- Check both the **code license** and the **model-weight license** separately — they are not always the same for OCR/ML dependencies. Record both in the SBOM (`LIC-001`).
- A dependency that requires a GPU with a non-trivial VRAM floor, or whose recommended path is cloud/Docker-only, may be added as an optional benchmark/comparison engine but must not become a default requirement (`PERF-001`, `OCR-006`).
- A dependency with commercial-use thresholds (revenue/MAU caps) or attribution requirements beyond a permissive open license requires an explicit, recorded decision before it can enter the default distribution (`LIC-002`) — do not add it silently because it tested well.
- When in doubt about a license, do not merge the dependency; flag it for review instead of assuming public availability or "it's just for research" makes it fine.
- See `DESIGN.md §4.1` for the currently chosen default stack (PaddleOCR PP-OCRv6/PP-StructureV3, optional PaddleOCR-VL-1.6, Docling, pypdfium2, pikepdf, OCRmyPDF, LibreOffice) and for named candidates (olmOCR, Surya, MinerU) that are intentionally excluded from the default distribution today. Don't reintroduce an excluded candidate without a fresh `LIC-002` review — FOSS OCR licensing and capability shifts over time, so re-check rather than assuming the old exclusion still holds or still doesn't.

## 5. Security review checklist

Before merging anything that touches file parsing, subprocess execution, or the Tauri/webview bridge, confirm:

- [ ] File type is validated by content, not by extension (`SEC-001`).
- [ ] No PDF JavaScript, Office macro, embedded attachment, or external-resource reference is executed (`SEC-002`).
- [ ] Decompression and raster dimensions are bounded (`SEC-003`).
- [ ] The job runs in a disposable, isolated working directory (`SEC-004`).
- [ ] No new general-purpose shell or filesystem command is exposed to the webview (`SEC-005`).
- [ ] Any downloaded model artifact is pinned and hash-verified (`SEC-006`).
- [ ] No document text, image data, or file contents appear in logs (`SEC-007`).
- [ ] Subprocess calls use argument arrays with timeouts and full process-tree termination, never shell string concatenation (`SEC-008`).
- [ ] A standard conversion run still produces zero network traffic (`SEC-009`).

## 6. Accessibility review checklist

Before merging any UI change:

- [ ] Primary controls are at least 44–48 CSS px.
- [ ] The screen remains usable and undistorted at 200% text enlargement.
- [ ] The flow is fully operable by keyboard, with a visible focus indicator at every step.
- [ ] High-contrast and reduced-motion modes still render correctly.
- [ ] File selection has a non-drag-and-drop path.
- [ ] RTL content renders correctly if the change touches any text-bearing UI element.
- [ ] Error/warning messages are in plain language, not raw internal identifiers (`UI-005`).

## 7. Visual craft review checklist (anti-slop gate)

Every screen — the file picker, the options screen, the progress screen, the review screen, the Reader — must clear this checklist before it counts as done (`VIS-001..004` in `SPEC.md`). This is a hard gate, not a style suggestion: a screen that works but reads as generic AI-generated UI is not finished. `DESIGN.md §14` is the positive design process this checklist enforces.

**First-order test:** a screenshot of the screen should not read as AI-generated to someone who has seen a lot of AI-built interfaces. When in doubt, take the screenshot and check it against every item below.

**Surfaces and decoration**
- [ ] No gradient text or gradient fills used decoratively
- [ ] No glassmorphism as a default surface
- [ ] No hero-metric template (big number, small label, gradient background)
- [ ] No glow effects used by default
- [ ] No pure white or pure black surfaces
- [ ] No colored border-left accent stripes thicker than 1px
- [ ] No abstract blob or wave shapes used as background decoration
- [ ] No uniform drop shadow applied to every card by default
- [ ] No uniform border-radius applied everywhere with no variation
- [ ] No dot-grid or graph-paper pattern as a default hero backdrop
- [ ] No pill-shaped "NEW" or "BETA" badges added by default

**Layout**
- [ ] No identical, repeated card grids with no visual hierarchy
- [ ] No three-icon-heading-paragraph feature grid used as the default way to explain features
- [ ] No centered single-column marketing layout applied to non-marketing screens
- [ ] No default hero pattern of centered headline, subheading, and two buttons (solid plus outline)
- [ ] No "trusted by" logo strip with generic placeholder company names
- [ ] No bento-grid layout used as a default structure

**Typography**
- [ ] No Inter or unmodified system-default fonts as the primary typeface
- [ ] No font weights limited to only regular and bold with nothing between
- [ ] No untouched default type scale (unmodified Tailwind or Bootstrap heading sizes, for example)

**Color**
- [ ] No blue or purple as the default accent color
- [ ] No rainbow chart palettes
- [ ] No single accent color repeated at full saturation across every interactive element with no tonal range
- [ ] No diagonal blue-to-purple-to-pink gradient used as a background

**Motion**
- [ ] No staggered fade-up-on-scroll animation applied to every section by default
- [ ] No hover scale-up applied to every card or button as default interactivity
- [ ] No skeleton loading state shown when content actually loads instantly
- [ ] No confetti or celebration animation triggered for routine actions

**Icons**
- [ ] No emoji used as icons
- [ ] No sparkle or star icon attached to AI features by default
- [ ] No icon attached to every single label or list item regardless of whether it adds clarity
- [ ] No arrow icon added to a button for decoration when there's no navigation behind it

**Copy**
- [ ] No exclamation points or cheerleading tone in UI copy
- [ ] No em dashes in UI copy
- [ ] No instance of "deep dive" anywhere in the copy
- [ ] No instance of "delve" anywhere in the copy
- [ ] No marketing buzzwords: seamless, effortless, unlock, empower, elevate, streamline, revolutionize, cutting-edge, leverage, robust, supercharge, game-changing
- [ ] No throat-clearing phrases like "it's important to note" or "in today's world"
- [ ] No "not just X, but Y" sentence construction
- [ ] No rhetorical-question section headers ("Ready to get started?")
- [ ] No generic CTA copy ("Get Started," "Learn More," "Unlock Now") used without regard to context

**Content and data**
- [ ] No lorem ipsum or placeholder text left in shipped copy
- [ ] No generic placeholder names (Jane Doe, Acme Corp, John Smith)
- [ ] No fake testimonials attributed to vague personas with stock headshots
- [ ] No unsourced stat claims ("10,000+ happy users," "99.9% uptime") without real data behind them
- [ ] No obviously fake or evenly-incrementing dummy data in charts and tables
- [ ] No stock photography of generic people smiling at laptops

**Completeness**
- [ ] No unimplemented stubs or placeholder functionality
- [ ] No default favicon left in place (Vite, Next, React logos)
- [ ] No default browser tab title left in place ("React App," "Vite + React," "Document")
- [ ] No dead links or unfinished routes left behind
- [ ] No placeholder alt text, labels, or TODO comments left in shipped code

This is a desktop tool, not a marketing site, so some items above (hero patterns, "trusted by" strips, testimonials, generic CTAs) will rarely come up literally. The point is that the same defaults don't creep in wherever they *could* apply — a completed-conversion screen dressed up like a landing page, a settings panel styled as a SaaS card grid, filler copy in a dialog. Treat every item as "does this apply here, and if so, does it pass," not as a list to skip because the product isn't a marketing page.

## 8. Document-integrity rules

These follow directly from `SPEC.md §2` and are restated here because they are the easiest rules for an agent to accidentally violate while "helpfully" improving something:

- Do not OCR a page that already has usable native text.
- Do not convert every PDF page into a screenshot/raster "for simplicity" — that throws away exact text and defeats the entire project.
- Do not pass recognized text through a generative LLM to smooth or "correct" it.
- Do not drop a page or document section on extraction/OCR failure — flag it for review and preserve the original.
- Do not lose the source-page/bounding-box reference for a block.
- Do not flatten a table into unordered prose without a visible warning.
- Do not mechanically inherit the source document's footnote/body font-size ratio if it would produce an unreadably small result.

## 9. Anti-patterns specific to this project

- Do not expose OCR-engine names, DPI settings, model versions, or backend internals on the default screen — that belongs in an Advanced/About view.
- Do not claim a platform (especially macOS for GPU/VLM-class models) is supported because the framework compiles there — platform support is only claimed after the packaged pipeline passes the benchmark corpus on that platform (`PKG-001`).
- Do not optimize the pipeline around a single OCR engine's quirks in a way that breaks the engine-swap abstraction in `DESIGN.md §4`.
- Do not reduce control sizes or information density purely to fit more UI elements on screen — this is an accessibility-first product by design.
- Do not add network calls to the standard conversion path, even for "just checking for updates" — keep that fully separate and opt-in.

## 10. Handoff requirements

When you finish a task or session:

1. Note which requirement IDs were implemented, changed, or are still open.
2. Update `DESIGN.md` if you changed a structural decision (schema, IPC protocol, engine routing) — do not let the doc drift from the code.
3. Update the SBOM/license inventory if dependencies changed.
4. Leave benchmark-corpus results (or a note on why they weren't run) for any change touching extraction, OCR, or export.
5. Flag any principle-level tension you noticed, even if you worked around it — don't silently resolve a conflict between `SPEC.md` and expedience.
